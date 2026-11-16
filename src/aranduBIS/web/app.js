"use strict";

const $ = id => document.getElementById(id);
const PALETA = [[74, 134, 197], [217, 138, 61], [106, 168, 79], [162, 120, 200], [150, 130, 60],
  [90, 170, 170], [200, 180, 70], [150, 150, 160], [220, 130, 170], [120, 190, 120]];

const vista = new Vista3D($("cv"));
let seq = 0, tempo = null;

const fmt = (x, d = 3) => x == null ? "—" : Number(x).toLocaleString("pt-BR", { maximumFractionDigits: d });
let ultimaMsg = { t: "", erro: false };
const msg = (t, erro = false) => { ultimaMsg = { t, erro }; const s = $("r_msg"); s.textContent = t; s.className = "fim" + (erro ? " erro" : ""); };
const vazio = V => {
  V.hidden = false;
  if (ultimaMsg.erro) { V.className = "veredito ruim"; V.textContent = ultimaMsg.t; }
  else { V.className = "veredito neutro"; V.textContent = "Calculando… ou ainda sem resultado."; }
};
const elemento = Estado.elemento;
const corDe = i => PALETA[i % PALETA.length];

async function chama(url, corpo) {
  const oc = typeof Ocupado !== "undefined" && corpo !== undefined ? Ocupado.inicia(url) : null;
  let ok = false;
  try {
    const r = await fetch(url, corpo === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo), signal: oc ? oc.sinal : undefined });
    const d = await r.json();
    if (typeof Malha !== "undefined" && corpo !== undefined) Malha.registra(url, d);
    if (!r.ok) throw new Error(d.erro || "erro");
    ok = true;
    return d;
  } catch (x) {
    if (x && x.name === "AbortError") throw new Error("Cálculo cancelado.");
    throw x;
  } finally { if (oc) Ocupado.termina(oc.id, ok); }
}

function agenda() { clearTimeout(tempo); tempo = setTimeout(constroi, 250); }

async function constroi() {
  const meu = ++seq;
  if (!esq || !esq.elementos.length) { malha = null; vista.limpa(); rodape(); return; }
  msg("Construindo…");
  try {
    const m = await chama("/api/constroi", esq);
    if (meu !== seq) return;
    malha = m;
    const cores = m.zonas.map(z => {
      const i = esq.elementos.findIndex(e => z.startsWith(e.nome + "."));
      const c = corDe(Math.max(i, 0));
      return m.camadas[m.zonas.indexOf(z)] === "estrutura" ? c.map(v => 0.55 * v + 70) : c;
    });
    vista.defineMalha(m, cores);
    aplicaVisibilidade();
    msg("Pronto");
  } catch (e) {
    if (meu !== seq) return;
    msg(e.message, true);
  }
  rodape();
  if (typeof Secao3D !== "undefined") Secao3D.atualiza();
  if (typeof PeleCor !== "undefined") PeleCor.atualiza();
  if (typeof Nervura3D !== "undefined") Nervura3D.atualiza();
  if (typeof No3D !== "undefined") No3D.atualiza();
  abaConteudo();
}

const ocultos = new Set();

function aplicaVisibilidade() {
  if (!malha) return;
  malha.zonas.forEach((z, k) => {
    const dono = esq.elementos.find(e => z.startsWith(e.nome + "."));
    const escondido = dono && ocultos.has(dono.nome);
    const camadaOk = filtroCamada === "tudo" || malha.camadas[k] === filtroCamada;
    vista.visivel[k] = !escondido && camadaOk ? 1 : 0;
  });
  if (filtroCamada !== "tudo" && !malha.camadas.some(c => c === filtroCamada))
    msg(filtroCamada === "estrutura"
      ? "Esta aeronave não tem estrutura declarada: adicione nervuras, longarinas ou tubos na aba Estrutura de uma asa, ou uma treliça."
      : "Nada na camada aero.", true);
  const e = elemento();
  vista.destaque = e ? new Set(malha.zonas.map((z, k) => z.startsWith(e.nome + ".") ? k : -1).filter(k => k >= 0)) : null;
  vista.desenha();
}

function lista() {
  const L = $("lista"); L.innerHTML = "";
  esq.elementos.forEach((e, i) => {
    const d = document.createElement("div");
    d.className = "el" + (i === sel ? " sel" : "");
    const cx = document.createElement("input");
    cx.type = "checkbox"; cx.checked = !ocultos.has(e.nome); cx.title = "Mostrar ou ocultar";
    cx.onclick = ev => { ev.stopPropagation(); cx.checked ? ocultos.delete(e.nome) : ocultos.add(e.nome); aplicaVisibilidade(); };
    const c = document.createElement("span"); c.className = "cor"; const [r, g, b] = corDe(i);
    c.style.background = `rgb(${r},${g},${b})`;
    const n = document.createElement("span"); n.textContent = e.nome;
    const t = document.createElement("i"); t.textContent = e.tipo || "asa";
    d.append(cx, c, n, t);
    d.onclick = () => seleciona(i);
    L.append(d);
  });
}

function seleciona(i) {
  sel = i; const tp = esq.elementos[i] && esq.elementos[i].tipo; if ((tp === "trelica" || tp === "placa") && aba === "Estrutura") aba = "Seções";
  if (aba === "Seção" && !temSecoes(esq.elementos[i])) aba = "Seções";
  if (typeof Secao3D !== "undefined") Secao3D.atualiza(); abas(); lista(); props(); abaConteudo(); aplicaVisibilidade();
}

function nomeUnico(base) {
  const usados = new Set(esq.elementos.map(e => e.nome));
  let n = 1, m = base;
  while (usados.has(m)) { n++; m = `${base}_${n}`; }
  return m;
}

const passado = [], futuro = [];
const foto = () => JSON.stringify(esq);
function guarda() {
  const f = foto();
  if (passado[passado.length - 1] === f) return;
  passado.push(f); if (passado.length > 100) passado.shift();
  futuro.length = 0;
}
function restaura(f) {
  esq = JSON.parse(f); sel = Math.min(sel, esq.elementos.length - 1);
  abas(); lista(); props(); abaConteudo(); agenda();
}
function desfaz() { if (!passado.length) return; futuro.push(foto()); restaura(passado.pop()); }
function refaz() { if (!futuro.length) return; passado.push(foto()); restaura(futuro.pop()); }

function muda(fn) { guarda(); fn(); agenda(); lista(); }

function linha(P, rotulo, w) {
  const l = document.createElement("label"); l.textContent = rotulo; P.append(l, w);
}

function entrada(tipo, valor, ao, extra = {}) {
  const w = document.createElement("input"); w.type = tipo; w.value = valor ?? "";
  if (tipo === "number") w.step = "any";
  Object.assign(w, extra);
  const le = () => (tipo === "number" ? (w.value === "" ? null : parseFloat(w.value)) : w.value);
  let ultimo = valor === undefined || valor === null ? "" : String(valor);
  w.onchange = () => { clearTimeout(w._tv); if (w.value === ultimo) return; ultimo = w.value; ao(le()); };
  if (tipo === "number") w.addEventListener("input", () => {
    clearTimeout(w._tv);
    w._tv = setTimeout(() => {
      const P = w.closest("#par2, #par3, #par4, #props");
      if (!P || w.value === "" || isNaN(parseFloat(w.value)) || w.value === ultimo) return;
      const idx = [...P.querySelectorAll("input, select")].indexOf(w);
      ultimo = w.value; ao(le());
      let n = 0;
      const volta = setInterval(() => {
        if (++n > 25) { clearInterval(volta); return; }
        if (document.body.contains(w) || (document.activeElement && document.activeElement !== document.body)) { if (n > 4) clearInterval(volta); return; }
        const novo = [...P.querySelectorAll("input, select")][idx];
        if (novo) { novo.focus(); clearInterval(volta); }
      }, 120);
    }, 650);
  });
  return w;
}

function props() {
  const P = $("props"), e = elemento(); P.innerHTML = "";
  $("tit_props").textContent = e ? `Propriedades — ${e.nome}` : "Propriedades";
  if (!e) { P.append(Object.assign(document.createElement("div"), { className: "nota", textContent: "Selecione um elemento." })); return; }
  const G = document.createElement("div"); G.className = "prop";
  linha(G, "nome", entrada("text", e.nome, v => {
    v = v.trim();
    if (!/^[A-Za-z0-9_]+$/.test(v) || esq.elementos.some((o, k) => k !== sel && o.nome === v)) { msg("Nome inválido ou repetido (use letras, números e _).", true); props(); return; }
    ocultos.delete(e.nome); muda(() => { e.nome = v; }); props();
  }));
  linha(G, "tipo", Object.assign(document.createElement("span"), { textContent: e.tipo || "asa" }));
  const cam = document.createElement("select");
  ["aero", "estrutura"].forEach(c => cam.add(new Option(c, c)));
  cam.value = e.camada || (e.tipo === "trelica" ? "estrutura" : "aero");
  cam.onchange = () => muda(() => { e.camada = cam.value; });
  linha(G, "camada", cam);
  if ((e.tipo || "asa") === "asa" && typeof e.perfil !== "undefined")
    linha(G, "perfil", entrada("text", e.perfil, v => muda(() => { e.perfil = v; })));
  if (e.tipo === "ponto") linha(G, "massa (kg)", entrada("number", e.massa, v => muda(() => { e.massa = v ?? 0; })));
  if (e.tipo === "placa") linha(G, "espessura (m)", entrada("number", e.espessura, v => muda(() => { e.espessura = v; })));
  const trio = (rot, chave, padrao) => {
    const box = document.createElement("div"); box.className = "tres";
    const v = e[chave] || padrao;
    [0, 1, 2].forEach(k => box.append(entrada("number", v[k], x => muda(() => {
      const a = (e[chave] || padrao).slice(); a[k] = x ?? 0; e[chave] = a; }))));
    linha(G, rot, box);
  };
  trio("posição x y z (m)", "posicao", [0, 0, 0]);
  if (e.tipo !== "ponto") ["rolagem", "arfagem", "guinada"].forEach(c =>
    linha(G, `${c} (°)`, entrada("number", e[c] || 0, v => muda(() => { e[c] = v ?? 0; }))));
  P.append(G);
  if (typeof No3D !== "undefined" && No3D.suportado(e) && document.documentElement.dataset.interface !== "nova") {
    const be = document.createElement("button"); be.textContent = No3D.ativo() ? "Terminar edição na vista 3D" : (e.tipo === "trelica" ? "Mover nós na vista 3D" : "Mover na vista 3D");
    be.title = "Arraste a peça (ou os nós) direto na vista 3D, com passo de 1 mm, ímã nos outros nós e simetria em y.";
    be.onclick = () => { No3D.liga(!No3D.ativo()); props(); }; be.style.margin = "4px 8px"; P.append(be);
  }

  if (e.tipo === "roda") {
    const centro = [(e.posicao || [0, 0, 0])[0], e.y ?? (e.posicao || [0, 0, 0])[1], (e.posicao || [0, 0, 0])[2]];
    const preso = esq.elementos.map(t => t.tipo === "trelica" ? (t.vinculos || []).filter(v => v.tipo === "roda" && v.alvo === e.nome).map(v => ({ t, v })) : []).flat()[0];
    const bx = document.createElement("div"); bx.className = "nota";
    const bt = document.createElement("button");
    if (preso) {
      bx.textContent = `Presa ao nó ${preso.v.no} de ${preso.t.nome} por junta de rotação (parafuso no eixo y). `;
      bt.textContent = "Soltar"; bt.onclick = () => { muda(() => { preso.t.vinculos = preso.t.vinculos.filter(v => v !== preso.v); if (!preso.t.vinculos.length) delete preso.t.vinculos; Juntas.define(preso.t, preso.v.no, "solda"); }); props(); };
    } else {
      bx.textContent = "Sem ligação declarada: a análise do trem usa o nó da treliça mais próximo do centro da roda (até 2 cm). ";
      bt.textContent = "Prender ao nó mais próximo"; bt.title = "Declara a ligação da roda com o tubo como junta de rotação em torno do eixo y.";
      bt.onclick = () => {
        let mel = null;
        esq.elementos.forEach(t => { if (t.tipo !== "trelica") return; const o = t.posicao || [0, 0, 0]; (t.nos || []).forEach((p, i) => { const d = Math.hypot(p[0] + o[0] - centro[0], p[1] + o[1] - centro[1], p[2] + o[2] - centro[2]); if (!mel || d < mel.d) mel = { t, i, d }; }); });
        if (!mel) { msg("Não há treliça no modelo.", true); return; }
        if (mel.d > 0.05) { msg(`O nó mais próximo está a ${Math.round(mel.d * 1000)} mm do centro da roda: aproxime a roda ou crie um nó no eixo.`, true); return; }
        muda(() => { mel.t.vinculos = (mel.t.vinculos || []).filter(v => !(v.tipo === "roda" && v.alvo === e.nome)); mel.t.vinculos.push({ no: mel.i, tipo: "roda", alvo: e.nome }); Juntas.define(mel.t, mel.i, "parafuso:y"); });
        props();
      };
    }
    bx.append(bt); P.append(bx);
  }

  const D = document.createElement("details");
  D.innerHTML = "<summary>Avançado: JSON do elemento</summary>";
  const ta = document.createElement("textarea"); ta.value = JSON.stringify(e, null, 2); ta.spellcheck = false;
  const ap = document.createElement("button"); ap.textContent = "Aplicar";
  ap.onclick = () => {
    try { const novo = JSON.parse(ta.value); guarda(); esq.elementos[sel] = novo; agenda(); lista(); props(); msg("Aplicado."); }
    catch (x) { msg("JSON inválido: " + x.message, true); }
  };
  D.append(ta, ap); P.append(D);
}

function abas() {
  const A = $("abas"); A.innerHTML = "";
  const tp = elemento() && elemento().tipo, rot = { Seções: tp === "trelica" ? "Tubos e nós" : tp === "placa" ? "Contorno" : "Seções" };
  const lista_ = tp === "trelica" || tp === "placa" ? ["Seções", "Massa e CG"] : temSecoes(elemento()) ? ["Seções", "Seção", "Estrutura", "Massa e CG"] : ["Seções", "Estrutura", "Massa e CG"];
  if (!lista_.includes(aba)) aba = "Seções";
  lista_.forEach(n => {
    const d = document.createElement("div"); d.textContent = rot[n] || n; if (n === aba) d.className = "at";
    d.onclick = () => { aba = n; abas(); abaConteudo(); }; A.append(d);
  });
}

function abaConteudo() {
  const C = $("aba_conteudo"); C.innerHTML = "";
  if (typeof Secao3D !== "undefined") Secao3D.sincroniza();
  if (aba === "Massa e CG") return abaMassa(C);
  const e = elemento();
  if (aba === "Seção" && temSecoes(e)) return Secao3D.pinta(C, e);
  if (!e) return C.append(nota("Selecione um elemento."));
  if (aba === "Estrutura" && e.tipo !== "trelica" && e.tipo !== "placa") return Estrutura.pinta(C, e);
  if (e.tipo === "trelica") return Construtor.trelica(C, e);
  if (e.tipo === "placa") return Construtor.placa(C, e);
  if (Array.isArray(e.secoes)) return abaSecoes(C, e);
  if (e.secoes_lineares) {
    const s = e.secoes_lineares;
    return C.append(nota(`Asa reta definida por seções lineares: y de ${fmt(s.y[0])} a ${fmt(s.y[1])} m, corda ${fmt(s.corda)} m, ${s.n} seções.`));
  }
  C.append(nota(`Elementos do tipo “${e.tipo}” são editados nas Propriedades ou no JSON avançado.`));
}

const nota = t => Object.assign(document.createElement("div"), { className: "nota", textContent: t });
const temSecoes = e => !!e && (e.tipo || "asa") === "asa" && Array.isArray(e.secoes);

function abaSecoes(C, e) {
  const t = document.createElement("table"), cols = ["y", "xle", "zle", "corda", "ainc"];
  const comPerfil = e.secoes.some(s => s.perfil);
  t.innerHTML = "<tr><th>#</th>" + cols.map(c => `<th>${c}</th>`).join("") + (comPerfil ? "<th>perfil</th>" : "") + "<th></th></tr>";
  e.secoes.forEach((s, i) => {
    const tr = document.createElement("tr");
    tr.append(Object.assign(document.createElement("td"), { textContent: i }));
    cols.forEach(c => {
      const td = document.createElement("td");
      td.append(entrada("number", s[c], v => muda(() => { s[c] = v ?? 0; })));
      tr.append(td);
    });
    if (comPerfil) { const td = document.createElement("td"); td.append(entrada("text", s.perfil || "", v => muda(() => { s.perfil = v; }))); tr.append(td); }
    const rm = document.createElement("td"); const b = document.createElement("button"); b.textContent = "✕"; b.title = "Remover seção";
    b.onclick = () => { if (e.secoes.length <= 2) return msg("Uma asa precisa de pelo menos 2 seções.", true); muda(() => e.secoes.splice(i, 1)); abaConteudo(); };
    rm.append(b); tr.append(rm); t.append(tr);
  });
  C.append(t);
  const add = document.createElement("button"); add.textContent = "+ seção"; add.style.margin = "4px 6px";
  add.onclick = () => {
    const u = e.secoes[e.secoes.length - 1];
    muda(() => e.secoes.push({ ...u, y: +(u.y + 0.1).toFixed(4) })); abaConteudo();
  };
  C.append(add);
}

function abaMassa(C) {
  if (!malha) return C.append(nota("Sem aeronave construída."));
  const t = document.createElement("table");
  t.innerHTML = "<tr><th>item</th><th>massa (g)</th><th>x</th><th>y</th><th>z</th><th>origem</th></tr>";
  malha.itens_massa.forEach(it => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${it.nome}</td><td>${fmt(it.massa * 1000, 1)}</td><td>${fmt(it.cg[0])}</td><td>${fmt(it.cg[1])}</td><td>${fmt(it.cg[2])}</td><td style="text-align:left">${it.origem}</td>`;
    t.append(tr);
  });
  C.append(t);
  if (!malha.itens_massa.length) C.append(nota("Nenhum elemento declara massa ou material. Informe `material` ou `massa` para entrar na conta."));
}

function rodape() {
  if (!malha) { ["r_massa", "r_cg", "r_env", "r_tri"].forEach(i => $(i).textContent = ""); return; }
  $("r_massa").innerHTML = `massa <b>${fmt(malha.massa_kg * 1000, 0)} g</b>`;
  $("r_cg").innerHTML = malha.cg_m ? `CG x = <b>${fmt(malha.cg_m[0])} m</b>` : "CG —";
  const [lo, hi] = malha.bbox;
  $("r_env").innerHTML = `envergadura <b>${fmt(hi[1] - lo[1], 2)} m</b>`;
  $("r_tri").textContent = `${malha.n_triangulos} triângulos`;
}

function carrega(novo, nome) {
  esq = novo; passado.length = 0; futuro.length = 0; ocultos.clear(); sel = esq.elementos.length ? 0 : -1;
  $("titulo").textContent = `AranduBIS — ${esq.nome || nome || "aeronave"}`;
  lista(); props(); abas(); abaConteudo(); constroi();
}

$("b_novo").onclick = () => carrega({ versao: 1, nome: "nova_aeronave", unidade: "m", elementos: [], marcas: [] });
Object.entries(Modelos.rotulos).forEach(([k, r]) => $("s_inserir").add(new Option(r, k)));
$("s_inserir").onchange = ev => {
  const tipo = ev.target.value; ev.target.value = ""; if (!tipo) return;
  if (!esq) $("b_novo").click();
  guarda();
  esq.elementos.push(Modelos.novo(tipo, nomeUnico(tipo)));
  sel = esq.elementos.length - 1; abas(); lista(); props(); abaConteudo(); agenda();
};
$("b_desfaz").onclick = desfaz;
$("b_refaz").onclick = refaz;
document.addEventListener("keydown", ev => {
  if (!(ev.ctrlKey || ev.metaKey) || ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  if (ev.key === "z") { ev.preventDefault(); desfaz(); }
  if (ev.key === "y") { ev.preventDefault(); refaz(); }
});
$("b_remove").onclick = () => {
  const e = elemento(); if (!e) return;
  if (!confirm(`Remover “${e.nome}”?`)) return;
  guarda(); esq.elementos.splice(sel, 1); sel = Math.min(sel, esq.elementos.length - 1); abas(); lista(); props(); abaConteudo(); agenda();
};
$("b_abrir").onchange = ev => {
  const f = ev.target.files[0]; if (!f) return;
  f.text().then(t => { try { carrega(JSON.parse(t), f.name); } catch (x) { msg("Arquivo inválido: " + x.message, true); } });
  ev.target.value = "";
};
$("s_exemplos").onchange = async ev => {
  const n = ev.target.value; if (!n) return;
  try { carrega(await chama("/api/exemplo?nome=" + encodeURIComponent(n)), n); } catch (x) { msg(x.message, true); }
  ev.target.value = "";
};
$("b_salvar").onclick = async () => {
  if (!esq) return;
  try { msg("Gravado em " + (await chama("/api/grava", esq)).caminho); } catch (x) { msg(x.message, true); }
};
$("b_baixar").onclick = () => {
  if (!esq) return;
  const limpo = Object.fromEntries(Object.entries(esq).filter(([k]) => !k.startsWith("_")));
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(new Blob([JSON.stringify(limpo, null, 2)], { type: "application/json" })),
    download: (esq.nome || "aeronave") + ".json" });
  a.click(); URL.revokeObjectURL(a.href);
};
$("b_config").onclick = () => Config.abre();
$("b_arquivos").onclick = () => Arquivos.abre();
const carrega_aeronave = carrega;

document.querySelectorAll("[data-vista]").forEach(b => b.onclick = () =>
  b.dataset.vista === "ajusta" ? vista.ajusta() : vista.vista(b.dataset.vista));
document.querySelectorAll("[data-modo]").forEach(b => b.onclick = () => {
  vista.modo = b.dataset.modo; vista.desenha();
  document.querySelectorAll("[data-modo]").forEach(x => x.classList.toggle("on", x === b));
});
document.querySelectorAll("[data-camada]").forEach(b => b.onclick = () => {
  filtroCamada = b.dataset.camada; aplicaVisibilidade();
  document.querySelectorAll("[data-camada]").forEach(x => x.classList.toggle("on", x === b));
});

(async () => {
  try {
    const ex = (await chama("/api/exemplos")).exemplos, S = $("s_exemplos");
    ex.forEach(n => S.add(new Option(n.replace(/\.json$/, ""), n)));
    const primeiro = ex.find(n => n.endsWith("generico.json")) || ex[0];
    if (primeiro) carrega(await chama("/api/exemplo?nome=" + encodeURIComponent(primeiro)), primeiro);
    else abas();
  } catch (x) { msg(x.message, true); abas(); }
})();
