"use strict";

const Interface = (() => {
  const CHAVE = "aranduBIS.interface", CHAVE_PAINEIS = "aranduBIS.paineis";
  const nova = document.documentElement.dataset.interface !== "classica";
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const svg = d => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICONES = {
    selecionar: '<path d="M5 3l6 16 2.5-6.5L20 10z"/>',
    nervuras: '<path d="M3 14c3-7 13-8 18-2-5 3-13 4-18 2z"/><path d="M9 9.5v6M14 9v6.5"/>',
    nos: '<circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><circle cx="12" cy="6" r="2"/><path d="M6 16.3l5-8.6M18 16.3l-5-8.6M7 18h10"/>',
    secao: '<path d="M3 13c2-5 12-6 18-1-6 2-14 3-18 1z"/><path d="M12 3v18" stroke-dasharray="3 3"/>',
    chapa: '<path d="M4 20V8l6-4h10v12l-6 4z"/><circle cx="13" cy="12" r="2.2"/>',
    medir: '<path d="M3 17L17 3l4 4L7 21z"/><path d="M7.5 12.5l2 2M10.5 9.5l2 2M13.5 6.5l2 2"/>',
    esq: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    dir: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
    iso: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    lateral: '<path d="M3 13h13l5-3v3l-5 2H3z"/><path d="M8 13V9h4v4"/>',
    topo: '<path d="M12 3v18M4 10h16M9 19h6"/>',
    frontal: '<circle cx="12" cy="12" r="2.5"/><path d="M2 12h7.5M14.5 12H22M12 9.5V6"/>',
    ajusta: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    solido: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" fill="currentColor" fill-opacity=".35"/>',
    malha: '<path d="M4 4h16v16H4zM4 9.3h16M4 14.6h16M9.3 4v16M14.6 4v16"/>',
    tudo: '<path d="M12 4l9 4.5-9 4.5-9-4.5z"/><path d="M3 12.5l9 4.5 9-4.5M3 16.5l9 4.5 9-4.5"/>',
    aero: '<path d="M2 14c4-7 14-8 20-2-6 3-15 4-20 2z"/>',
    estrutura: '<path d="M3 18L9 6l6 12 6-12M3 18h18M9 6h12"/>',
    desfaz: '<path d="M9 7L4 12l5 5"/><path d="M4 12h10a6 6 0 010 12"/>',
    refaz: '<path d="M15 7l5 5-5 5"/><path d="M20 12H10a6 6 0 000 12"/>',
    ajuda: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 115 0c0 1.7-2.5 2-2.5 4M12 17.2v.3"/>',
  };
  const FERR = [
    ["selecionar", "Selecionar", "V", "Clique numa peça para selecioná-la. Arraste para girar a vista."],
    ["nervuras", "Nervuras", "R", "Arraste, crie e remova nervuras da asa."],
    ["nos", "Nós e barras", "B", "Mova nós, ligue barras e defina juntas e apoios."],
    ["secao", "Seção", "S", "Clique num anel para editar a seção da asa."],
    ["chapa", "Chapa 2D", "C", "Abre o editor 2D da chapa selecionada."],
    ["medir", "Medir", "D", "Clique em dois pontos para medir a distância; o terceiro mede o ângulo."],
  ];
  const sem = t => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const emCampo = ev => { const t = ev.target, g = t && t.tagName; return g === "INPUT" || g === "TEXTAREA" || g === "SELECT" || (t && t.isContentEditable); };

  function troca(m) { try { localStorage.setItem(CHAVE, m); } catch (e) {  } location.reload(); }

  function seletor() {
    const corpo = document.getElementById("cfg_corpo");
    if (!corpo || corpo.querySelector("#cfg_interface")) return;
    const o = el("div", "opc"), r = el("label", "", "Interface"), s = el("select");
    s.id = "cfg_interface"; r.htmlFor = s.id;
    s.add(new Option("Nova (ferramentas na vista)", "nova")); s.add(new Option("Clássica", "classica"));
    s.value = nova ? "nova" : "classica";
    s.onchange = () => troca(s.value);
    o.append(r, s, el("div", "ajuda", "A interface nova reúne as ferramentas na vista 3D. A clássica continua disponível, sem os recursos novos. A troca recarrega a página."));
    corpo.prepend(o);
  }
  if (typeof Config !== "undefined") { const abre = Config.abre; Config.abre = async g => { await abre(g); seletor(); }; }

  if (!nova) return { nova: false, troca };

  let ferr = "selecionar";
  const medida = { pts: [] };
  const V = document.querySelector("#et1 .vista");
  vista.estilo = "nova";

  function garante(teste) {
    if (!esq) return false;
    if (teste(elemento())) return true;
    const i = esq.elementos.findIndex(teste);
    if (i < 0) return false;
    seleciona(i);
    return true;
  }

  const MEDIR = {
    baixo(px, py) {
      const p = candidato(px, py);
      if (!p) return false;
      if (medida.pts.length >= 3) medida.pts = [];
      medida.pts.push(p);
      pintaMedida();
      return true;
    },
    move() {  },
    solta() {  },
  };

  function candidato(px, py) {
    let mel = null, d0 = 13;
    const tenta = p => { const q = vista.projetaXY(p[0], p[1], p[2]); if (!q) return; const d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = p.slice(); } };
    if (esq) esq.elementos.forEach(e => {
      if (e.tipo === "trelica") { const o = e.posicao || [0, 0, 0]; (e.nos || []).forEach(n => tenta([n[0] + o[0], n[1] + o[1], n[2] + o[2]])); }
      else if (e.tipo === "roda") { const q = e.posicao || [0, 0, 0]; tenta([q[0], e.y || 0, q[2]]); }
      else if (e.tipo === "ponto") tenta(e.posicao || [0, 0, 0]);
    });
    if (mel) return mel;
    return vista.verticeEm(px, py, 12);
  }

  function resultadoMedida() {
    if (medida.pts.length < 2) return null;
    const [a, b, c] = medida.pts, d = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], r = { dist: Math.hypot(...d), d };
    if (c) {
      const u = [a[0] - b[0], a[1] - b[1], a[2] - b[2]], w = [c[0] - b[0], c[1] - b[1], c[2] - b[2]], nu = Math.hypot(...u), nw = Math.hypot(...w);
      r.dist2 = nw;
      r.angulo = nu > 1e-9 && nw > 1e-9 ? Math.acos(Math.max(-1, Math.min(1, (u[0] * w[0] + u[1] * w[1] + u[2] * w[2]) / (nu * nw)))) * 180 / Math.PI : null;
    }
    return r;
  }

  function pintaMedida() {
    const r = resultadoMedida(), mm = v => (v * 1000).toFixed(1);
    vista.pontos = medida.pts.map((p, i) => ({ p, sel: i === medida.pts.length - 1, forma: "solda" }));
    vista.extra = r ? medida.pts.slice(1).map((p, i) => ({ pts: [medida.pts[i], p], cor: "#ffd447", larg: 2 })) : null;
    vista.hud = r
      ? [`Distância: ${mm(r.dist)} mm`, `Δx ${mm(r.d[0])} · Δy ${mm(r.d[1])} · Δz ${mm(r.d[2])} mm`,
        r.angulo != null ? `Ângulo no 2º ponto: ${r.angulo.toFixed(1)}° · 2º trecho ${mm(r.dist2)} mm` : "Terceiro clique mede o ângulo no 2º ponto", "Depois, clique de novo para outra medida · Esc sai"]
      : [medida.pts.length ? "Clique no segundo ponto" : "Medir: clique no primeiro ponto", "O cursor gruda em nós e vértices · Esc sai"];
    vista.desenha();
    Estado.avisa("ferramenta");
  }

  function limpaMedida() {
    if (ferr !== "medir") return;
    medida.pts = [];
    vista.pontos = null; vista.extra = null; vista.hud = null; vista.ferramenta = null;
    vista.desenha();
  }

  function ativa(nome) {
    if (Etapas.atual() !== 1) Etapas.vai(1);
    if (nome !== "medir") limpaMedida();
    if (nome !== "nervuras" && Nervura3D.ativo()) Nervura3D.liga(false);
    if (nome !== "nos" && No3D.ativo()) No3D.liga(false);
    if (nome === "nervuras") {
      if (garante(e => Nervura3D.ehAsa(e) && !!e.estrutura) || garante(e => !!Nervura3D.ehAsa(e))) Nervura3D.liga(true);
      else { msg("Não há asa no modelo para editar nervuras.", true); nome = "selecionar"; }
    } else if (nome === "nos") {
      if (garante(e => !!e && e.tipo === "trelica" && No3D.suportado(e)) || garante(e => !!No3D.suportado(e))) No3D.liga(true);
      else { msg("Não há treliça, roda ou massa pontual sem rotação para mover.", true); nome = "selecionar"; }
    } else if (nome === "secao") {
      if (garante(temSecoes)) { aba = "Seção"; abas(); abaConteudo(); Secao3D.atualiza(); }
      else { msg("Não há asa com seções no modelo.", true); nome = "selecionar"; }
    } else if (nome === "chapa") {
      if (garante(e => !!e && e.tipo === "placa")) Chapa2D.abre(elemento());
      else msg("Não há chapa no modelo: insira um elemento do tipo Placa.", true);
      nome = "selecionar";
    } else if (nome === "medir") {
      ferr = "medir"; medida.pts = []; vista.ferramenta = MEDIR; pintaMedida();
    }
    ferr = nome;
    props(); abaConteudo();
    sincroniza();
  }

  function sincroniza() {
    if (ferr === "nervuras" && !Nervura3D.ativo()) ferr = "selecionar";
    if (ferr === "nos" && !No3D.ativo()) ferr = "selecionar";
    if (ferr !== "nervuras" && Nervura3D.ativo()) ferr = "nervuras";
    if (ferr !== "nos" && No3D.ativo()) ferr = "nos";
    document.querySelectorAll(".paleta button").forEach(b => { const on = b.dataset.ferr === ferr; b.classList.toggle("on", on); b.setAttribute("aria-pressed", on ? "true" : "false"); });
    V.dataset.ferr = ferr;
    const f = FERR.find(x => x[0] === ferr), m = document.getElementById("r_modo");
    if (m) m.innerHTML = `ferramenta <b>${f[1]}</b>`;
    inspetor(); coordenadas();
  }

  function clique(px, py) {
    if (cliqueCubo(px, py)) return;
    if (ferr === "selecionar") {
      const z = vista.zonaEm(px, py);
      if (z < 0 || !malha) return;
      const nome = malha.zonas[z], i = esq.elementos.findIndex(e => nome.startsWith(e.nome + "."));
      if (i >= 0 && i !== sel) seleciona(i);
      return;
    }
    if (ferr === "secao") Secao3D.clica(px, py);
  }

  function montaVista() {
    const vb = el("div", "vbarra"); vb.setAttribute("role", "toolbar"); vb.setAttribute("aria-label", "Câmera, sombreado e camadas");
    const NOMES = { iso: "Vista isométrica", lateral: "Vista lateral", topo: "Vista de topo", frontal: "Vista frontal", ajusta: "Ajustar à janela", solido: "Sólido", malha: "Malha", tudo: "Todas as camadas", aero: "Só a camada aerodinâmica", estrutura: "Só a estrutura" };
    [["vista", "[data-vista]"], ["modo", "[data-modo]"], ["camada", "[data-camada]"]].forEach(([k, s]) => {
      const g = el("span", "vgrupo");
      document.querySelectorAll("#barra " + s).forEach(b => {
        const chave = b.dataset[k];
        b.title = NOMES[chave] || b.textContent; b.setAttribute("aria-label", b.title);
        if (ICONES[chave]) b.innerHTML = svg(ICONES[chave]);
        b.classList.add("icone");
        g.append(b);
      });
      vb.append(g);
    });
    V.append(vb);

    const pal = el("div", "paleta"); pal.setAttribute("role", "toolbar"); pal.setAttribute("aria-label", "Ferramentas da vista"); pal.setAttribute("aria-orientation", "vertical");
    FERR.forEach(([k, n, t, d]) => {
      const b = el("button", "icone"); b.dataset.ferr = k; b.innerHTML = svg(ICONES[k]);
      b.title = `${n} (${t})\n${d}`; b.setAttribute("aria-label", n);
      b.onclick = () => ativa(k);
      pal.append(b);
    });
    V.append(pal);
    vista.aoClicar = clique;
    vista.aoDesenhar = cubo;
  }

  const FACES = [[[0, -1, 0], "Esq", 0, 0], [[0, 1, 0], "Dir", Math.PI, 0], [[-1, 0, 0], "Frente", Math.PI / 2, 0], [[1, 0, 0], "Trás", -Math.PI / 2, 0],
    [[0, 0, 1], "Topo", -Math.PI / 2, Math.PI / 2 - 0.001], [[0, 0, -1], "Base", -Math.PI / 2, -Math.PI / 2 + 0.001]];
  let facesTela = [];

  function cubo(g, B, esc, W, H) {
    const L = 21, cx = W - 46, cy = H - 46;
    const pr = (x, y, z) => { const rx = x * B.cy - y * B.sy, ry = x * B.sy + y * B.cy; return [cx + rx * L, cy - (z * B.cp + ry * B.sp) * L, ry * B.cp - z * B.sp]; };
    facesTela = [];
    g.save(); g.font = "600 9px Inter, Segoe UI, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
    const lista = FACES.map(f => {
      const n = f[0], u = n[0] ? [0, 1, 0] : [1, 0, 0], w = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]];
      const q = [[1, 1], [1, -1], [-1, -1], [-1, 1]].map(([a, b]) => pr(n[0] + a * u[0] + b * w[0], n[1] + a * u[1] + b * w[1], n[2] + a * u[2] + b * w[2]));
      return { f, q, c: pr(n[0], n[1], n[2]) };
    }).filter(o => o.c[2] < -0.05).sort((a, b) => b.c[2] - a.c[2]);
    const tinta = Tema.cor("--tinta") || "#222", painel = Tema.cor("--painel") || "#fff", linha = Tema.cor("--linha") || "#999";
    lista.forEach(o => {
      g.beginPath(); o.q.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath();
      g.globalAlpha = 0.5 + 0.45 * Math.min(1, -o.c[2]); g.fillStyle = painel; g.fill(); g.globalAlpha = 1;
      g.strokeStyle = linha; g.lineWidth = 1; g.stroke();
      if (-o.c[2] > 0.35) { g.fillStyle = tinta; g.fillText(o.f[1], o.c[0], o.c[1]); }
      facesTela.push(o);
    });
    g.restore();
  }

  function cliqueCubo(x, y) {
    for (let k = facesTela.length - 1; k >= 0; k--) {
      const q = facesTela[k].q; let dentro = false;
      for (let i = 0, j = q.length - 1; i < q.length; j = i++)
        if ((q[i][1] > y) !== (q[j][1] > y) && x < (q[j][0] - q[i][0]) * (y - q[i][1]) / (q[j][1] - q[i][1]) + q[i][0]) dentro = !dentro;
      if (dentro) { vista.olha(facesTela[k].f[2], facesTela[k].f[3]); return true; }
    }
    return false;
  }

  function menu(titulo, itens, dica) {
    const m = el("span", "menu"), b = el("button", "", titulo), pop = el("div", "menu-pop");
    b.title = dica; b.setAttribute("aria-haspopup", "true"); b.setAttribute("aria-expanded", "false");
    pop.hidden = true; pop.setAttribute("role", "menu");
    itens.filter(Boolean).forEach(i => { if (i.tagName === "BUTTON" || i.classList.contains("botao")) i.setAttribute("role", "menuitem"); pop.append(i); });
    const fecha = () => { pop.hidden = true; b.setAttribute("aria-expanded", "false"); };
    b.onclick = ev => { ev.stopPropagation(); const abre = pop.hidden; document.querySelectorAll(".menu-pop").forEach(x => { x.hidden = true; }); pop.hidden = !abre; b.setAttribute("aria-expanded", abre ? "true" : "false"); };
    pop.addEventListener("click", ev => { if (ev.target.tagName !== "SELECT") fecha(); });
    pop.addEventListener("change", fecha);
    document.addEventListener("click", ev => { if (!m.contains(ev.target)) fecha(); });
    document.addEventListener("keydown", ev => { if (ev.key === "Escape" && !pop.hidden) { fecha(); b.focus(); } });
    m.append(b, pop);
    return m;
  }

  function montaBarra() {
    const $i = id => document.getElementById(id);
    const col = document.querySelector("#et1 > aside.col"), h = col.querySelector("h4");
    const ac = el("div", "col-acoes");
    ac.append($i("s_inserir"), $i("b_remove"));
    h.after(ac);
    const barra = $i("barra"), g1 = barra.querySelector(".g1-grupo");
    g1.querySelectorAll(".sep").forEach(x => x.remove());
    [["b_desfaz", "desfaz"], ["b_refaz", "refaz"]].forEach(([id, ic]) => { const b = $i(id); b.setAttribute("aria-label", b.textContent); b.innerHTML = svg(ICONES[ic]); b.classList.add("icone"); });
    const cor = $i("s_cor");
    if (cor) { const g = el("span", "vgrupo"); g.append(cor); document.querySelector(".vbarra").append(g); }
    const at = el("button", "", "Atalhos de teclado"); at.id = "b_atalhos"; at.title = "Lista de atalhos (?)"; at.onclick = atalhos;
    const cm = el("button", "", "Procurar comando…"); cm.id = "b_comandos"; cm.title = "Procurar qualquer comando ou análise (Ctrl+K)"; cm.onclick = comandos;
    const abrir = barra.querySelector("label.botao");
    const arq = menu("Arquivo", [$i("b_novo"), abrir, $i("s_exemplos"), $i("b_salvar"), $i("b_baixar"), $i("b_arquivos")], "Novo, abrir, exemplos, salvar e arquivos do projeto");
    const aj = menu("Ajuda", [$i("b_inicio"), $i("b_manual"), at, cm], "Primeiros passos, boas práticas e atalhos");
    barra.prepend(arq);
    arq.after(el("span", "sep"));
    $i("b_config").before(aj);
    $i("b_exporta").classList.add("primario");
  }

  const SELOS = { pendente: "ainda sem resultado", aviso: "com aviso", ok: "sem pendências" };
  const estados = { 1: "pendente", 2: "pendente", 3: "pendente", 4: "pendente", 5: "pendente" };

  function selo(n, estado) {
    estados[n] = estado;
    const d = document.querySelector(`.etapas div[data-etapa="${n}"]`); if (!d) return;
    let i = d.querySelector(".selo"); if (!i) { i = el("i", "selo"); d.append(i); }
    i.dataset.estado = estado; i.title = SELOS[estado];
    d.setAttribute("aria-label", `${d.firstChild.textContent.trim()}, ${SELOS[estado]}`);
  }

  function montaEtapas() {
    const E = document.querySelector(".etapas");
    for (let n = 1; n <= 5; n++) selo(n, "pendente");
    const ids = { 2: "veredito", 3: "veredito3", 4: "veredito4", 5: "veredito5" };
    Object.entries(ids).forEach(([n, id]) => {
      const v = document.getElementById(id); if (!v) return;
      new MutationObserver(() => {
        if (v.hidden || Etapas.atual() !== +n) return;
        if (v.classList.contains("ruim")) selo(+n, "aviso");
        else if (v.classList.contains("ok")) selo(+n, "ok");
      }).observe(v, { attributes: true, attributeFilter: ["class", "hidden"] });
    });
    const geometria = () => selo(1, esq && esq.elementos.length ? "ok" : "pendente");
    Estado.ouve(k => {
      if (k === "esq") { for (let n = 2; n <= 5; n++) selo(n, "pendente"); geometria(); }
      if (k === "malha") geometria();
    });
    geometria();
    const fim = el("span", "fim paineis");
    [["esq", "Mostrar ou recolher o painel da esquerda ([)"], ["dir", "Mostrar ou recolher o painel da direita (])"]].forEach(([k, t]) => {
      const b = el("button", "icone"); b.innerHTML = svg(ICONES[k]); b.title = t; b.setAttribute("aria-label", t); b.dataset.painel = k;
      b.onclick = () => painel(k);
      fim.append(b);
    });
    E.append(fim);
    let g = {}; try { g = JSON.parse(localStorage.getItem(CHAVE_PAINEIS) || "{}"); } catch (e) {  }
    ["esq", "dir"].forEach(k => { if (g[k]) painel(k, true); });
  }

  function painel(k, forca) {
    const c = "sem-" + k, on = forca === undefined ? !document.body.classList.contains(c) : forca;
    document.body.classList.toggle(c, on);
    const b = document.querySelector(`[data-painel="${k}"]`); if (b) { b.classList.toggle("on", !on); b.setAttribute("aria-pressed", on ? "false" : "true"); }
    try { localStorage.setItem(CHAVE_PAINEIS, JSON.stringify({ esq: document.body.classList.contains("sem-esq"), dir: document.body.classList.contains("sem-dir") })); } catch (e) {  }
    vista.desenha();
  }

  function montaRodape() {
    const R = document.querySelector(".rodape");
    const m = el("span"); m.id = "r_modo";
    const c = el("span"); c.id = "r_coord";
    const u = el("span", "", "m · kg · graus"); u.id = "r_unid"; u.title = "Unidades dos campos, salvo indicação no rótulo";
    R.prepend(m, c);
    document.getElementById("r_msg").before(u);
    const T = el("div", "toast"); T.id = "toast"; T.setAttribute("role", "alert"); T.hidden = true; document.body.append(T);
    let tempo = null;
    const s = document.getElementById("r_msg");
    new MutationObserver(() => {
      if (!s.classList.contains("erro") || !s.textContent) { return; }
      T.textContent = s.textContent; T.hidden = false;
      clearTimeout(tempo); tempo = setTimeout(() => { T.hidden = true; }, 6000);
    }).observe(s, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    T.onclick = () => { T.hidden = true; };
  }

  function coordenadas() {
    const c = document.getElementById("r_coord"); if (!c) return;
    const mm = v => (v * 1000).toFixed(0);
    let t = "";
    if (ferr === "nos") { const s = No3D.selecao(); if (s && s.p) t = `x <b>${mm(s.p[0])}</b> y <b>${mm(s.p[1])}</b> z <b>${mm(s.p[2])}</b> mm`; }
    else if (ferr === "nervuras") { const s = Nervura3D.selecao(); if (s && s.y !== null) t = `y <b>${mm(s.y)}</b> mm`; }
    else if (ferr === "medir") { const r = resultadoMedida(); if (r) t = `distância <b>${(r.dist * 1000).toFixed(1)}</b> mm`; }
    c.innerHTML = t; c.hidden = !t;
  }

  let chaveInsp = "";

  function inspetor() {
    const I = document.getElementById("inspetor"); if (!I) return;
    const no = ferr === "nos" ? No3D.selecao() : null, nv = ferr === "nervuras" ? Nervura3D.selecao() : null, md = ferr === "medir" ? resultadoMedida() : null;
    const chave = no ? `no|${no.elemento}|${no.id}` : nv ? `nv|${nv.asa}|${nv.y}` : ferr === "medir" ? "medir" : "";
    if (chave === chaveInsp && I.contains(document.activeElement) && emCampo({ target: document.activeElement })) return;
    chaveInsp = chave;
    I.innerHTML = ""; I.hidden = !chave;
    if (!chave) return;
    const G = el("div", "prop");
    const linha = (rot, campo, dica) => { const l = el("label", "", rot); if (dica) l.title = dica; G.append(l, campo); };
    const num = (v, casas, aoMudar) => { const i = el("input"); i.type = "number"; i.step = "any"; i.value = v == null ? "" : (+v).toFixed(casas); i.onchange = () => { const x = parseFloat(i.value); if (isFinite(x)) aoMudar(x); }; return i; };
    const sele = (ops, v, aoMudar) => { const s = el("select"); ops.forEach(([k, n]) => s.add(new Option(n, k))); s.value = v; s.onchange = () => aoMudar(s.value); return s; };
    if (no) {
      I.append(el("h5", "", no.id === null ? `${no.elemento}: nenhum nó selecionado` : no.tipo === "trelica" ? `Nó ${no.id} de ${no.elemento}` : no.elemento));
      if (no.p) {
        ["x", "y", "z"].forEach((c, k) => linha(`${c} (mm)`, num(no.p[k] * 1000, 1, v => { const p = No3D.selecao().p; p[k] = v / 1000; No3D.defineSel(p); })));
        if (no.tipo === "trelica") {
          linha("junta", sele(Juntas.OPCOES, no.junta, v => No3D.defineJunta("junta", v)), "Solda transmite momento; parafuso gira em um eixo; rótula gira em todos.");
          linha("vínculo", sele(Juntas.VINCULOS, no.vinculo, v => No3D.defineJunta("vinculo", v)), "Engaste prende translações e rotações; apoio prende só as translações.");
          const asas = esq.elementos.filter(e => (e.tipo || "asa") === "asa" && Array.isArray(e.secoes)).map(e => [e.nome, e.nome]);
          linha("liga a", sele([["", "nenhuma asa"]].concat(asas), no.ligacao, v => No3D.defineJunta("ligacao", v)), "Asa presa à treliça neste nó.");
          G.append(el("label", "", "barras"), el("span", "", String(no.barras)));
        }
      }
      I.append(G);
      I.append(el("div", "nota", `${no.total} ${no.tipo === "trelica" ? "nós" : "ponto"} · o par simétrico acompanha as mudanças`));
    } else if (nv) {
      I.append(el("h5", "", nv.y === null ? `${nv.asa}: nenhuma nervura selecionada` : `Nervura de ${nv.asa}`));
      if (nv.y !== null) {
        linha("y (mm)", num(nv.y * 1000, 1, v => Nervura3D.defineSel({ y: v / 1000 })), "Posição ao longo da envergadura.");
        linha("ângulo (°)", num(nv.angulo, 1, v => Nervura3D.defineSel({ angulo: v })), "Giro em planta em torno de 25 % da corda.");
        I.append(G);
      }
      const B = el("div", "insp-botoes");
      const b1 = el("button", "", "Nova no maior vão"); b1.onclick = () => Nervura3D.criaNoVao();
      B.append(b1);
      if (nv.y !== null) { const b2 = el("button", "", "Remover"); b2.onclick = () => Nervura3D.removeSel(); B.append(b2); }
      I.append(B, el("div", "nota", `${nv.total} nervura${nv.total === 1 ? "" : "s"} nesta asa`));
    } else {
      I.append(el("h5", "", "Medida"));
      if (md) {
        const mm = v => (v * 1000).toFixed(1) + " mm";
        const linhas = [["distância", mm(md.dist)], ["Δx", mm(md.d[0])], ["Δy", mm(md.d[1])], ["Δz", mm(md.d[2])]];
        if (md.angulo != null) linhas.push(["2º trecho", mm(md.dist2)], ["ângulo", md.angulo.toFixed(1) + "°"]);
        linhas.forEach(([a, b]) => G.append(el("label", "", a), el("span", "", b)));
        I.append(G);
      } else I.append(el("div", "nota", "Clique em dois pontos da vista."));
    }
  }

  function montaInspetor() {
    const I = el("div", "inspetor"); I.id = "inspetor"; I.hidden = true;
    document.getElementById("tit_props").after(I);
  }

  const ATALHOS = [
    ["Geral", [["1 a 5", "ir para a etapa"], ["Ctrl+K", "procurar um comando"], ["?", "esta lista"], ["Ctrl+Z / Ctrl+Y", "desfazer / refazer"], ["[ e ]", "recolher os painéis laterais"], ["Esc", "sair da ferramenta"]]],
    ["Ferramentas", FERR.map(f => [f[2], f[1]])],
    ["Vista 3D", [["arrastar", "girar"], ["Shift + arrastar", "deslocar"], ["roda do mouse", "aproximar"], ["cubo no canto", "clique numa face para alinhar a vista"]]],
    ["Nervuras", [["arrastar o anel", "mover (Alt = sem passo)"], ["Ctrl + clique", "criar (a prévia aparece ao segurar Ctrl)"], ["clique repetido", "alternar entre anéis sobrepostos"], ["N", "criar no maior vão"], ["← →", "mover 1 mm (Shift 10)"], ["Q / E", "girar 1° (Shift 5)"], ["Del", "remover"], ["Tab", "próxima"]]],
    ["Nós e barras", [["arrastar o nó", "mover (Alt = sem passo e sem ímã)"], ["X / Y / Z", "travar o eixo"], ["P", "trocar o plano"], ["M", "simetria"], ["← → ↑ ↓ , .", "mover 1 mm (Shift 10)"],
      ["Ctrl + clique", "criar nó, ou ligar/desligar barra"], ["Shift + clique", "juntar o nó ao grupo"], ["Ctrl+C / Ctrl+V", "copiar / colar o grupo"], ["I", "espelhar o grupo (em y, ou no eixo travado)"], ["1 / 2 / 3", "solda / parafuso / rótula"], ["4 / 5 / 0", "engaste / apoio / livre"], ["6", "ligar à asa mais próxima"], ["T", "trocar o tubo"], ["L", "ligar automaticamente"], ["Del", "remover"], ["Tab", "próximo"]]],
  ];

  function dialogo(id, titulo, classe) {
    let d = document.getElementById(id);
    if (d) return d;
    d = el("dialog", classe || ""); d.id = id;
    const topo = el("div", "dlg-topo"), b = el("button", "", "Fechar");
    topo.append(el("b", "", titulo), b); b.onclick = () => d.close();
    d.append(topo, el("div", "dlg-corpo"));
    document.body.append(d);
    return d;
  }

  function atalhos() {
    const d = dialogo("dlg_atalhos", "Atalhos de teclado", "largo"), C = d.querySelector(".dlg-corpo");
    if (!C.childElementCount) {
      C.className = "dlg-corpo atalhos";
      ATALHOS.forEach(([g, L]) => {
        const s = el("section"); s.append(el("h5", "", g));
        const t = el("table");
        L.forEach(([k, n]) => { const r = t.insertRow(); const c = r.insertCell(); k.split(" / ").forEach((p, i) => { if (i) c.append(" / "); c.append(el("kbd", "", p)); }); r.insertCell().textContent = n; });
        s.append(t); C.append(s);
      });
    }
    if (!d.open) d.showModal();
  }

  function listaComandos() {
    const C = [], add = (grupo, titulo, faz, dica) => C.push({ grupo, titulo, faz, dica: dica || "", busca: sem(grupo + " " + titulo) });
    const clica = id => () => document.getElementById(id).click();
    ["Geometria", "Análise", "Estrutura", "Otimizar", "Resultados"].forEach((n, i) => add("Etapa", `${i + 1} ${n}`, () => Etapas.vai(i + 1), String(i + 1)));
    FERR.forEach(f => add("Ferramenta", f[1], () => ativa(f[0]), f[2]));
    [["iso", "Isométrica"], ["lateral", "Lateral"], ["topo", "Topo"], ["frontal", "Frontal"], ["ajusta", "Ajustar à janela"]].forEach(([k, n]) => add("Vista", n, () => document.querySelector(`[data-vista="${k}"]`).click()));
    [["solido", "Sólido"], ["malha", "Malha"]].forEach(([k, n]) => add("Sombreado", n, () => document.querySelector(`[data-modo="${k}"]`).click()));
    [["tudo", "Tudo"], ["aero", "Aerodinâmica"], ["estrutura", "Estrutura"]].forEach(([k, n]) => add("Camada", n, () => document.querySelector(`[data-camada="${k}"]`).click()));
    add("Arquivo", "Novo", clica("b_novo")); add("Arquivo", "Salvar", clica("b_salvar")); add("Arquivo", "Baixar o .json", clica("b_baixar"));
    add("Arquivo", "Exportar…", clica("b_exporta")); add("Arquivo", "Arquivos do projeto", clica("b_arquivos"));
    add("Editar", "Desfazer", clica("b_desfaz"), "Ctrl+Z"); add("Editar", "Refazer", clica("b_refaz"), "Ctrl+Y");
    add("Painel", "Recolher ou mostrar a esquerda", () => painel("esq"), "["); add("Painel", "Recolher ou mostrar a direita", () => painel("dir"), "]");
    add("Ajuda", "Atalhos de teclado", atalhos, "?"); add("Ajuda", "Boas práticas", clica("b_manual")); add("Ajuda", "Configurações", clica("b_config"));
    if (typeof Inicio !== "undefined" && Inicio.abre) add("Ajuda", "Primeiros passos", () => Inicio.abre());
    Analise.itens().forEach(i => add("Análise", i.titulo, () => Analise.abre(i.chave)));
    Etapa3.itens().forEach(i => add("Estrutura", i.titulo, () => Etapa3.abre(i.chave)));
    [...document.getElementById("s_exemplos").options].filter(o => o.value).forEach(o => add("Exemplo", o.textContent, () => { const s = document.getElementById("s_exemplos"); s.value = o.value; s.dispatchEvent(new Event("change")); }));
    if (esq) esq.elementos.forEach((e, i) => add("Elemento", e.nome, () => { Etapas.vai(1); seleciona(i); }, e.tipo || "asa"));
    return C;
  }

  function comandos() {
    const d = dialogo("dlg_comandos", "Comandos", "comandos"), C = d.querySelector(".dlg-corpo");
    C.innerHTML = "";
    const inp = el("input"); inp.type = "search"; inp.placeholder = "Digite para procurar: etapa, ferramenta, análise, exemplo, elemento…"; inp.setAttribute("aria-label", "Procurar comando");
    const L = el("div", "cmd-lista"); L.setAttribute("role", "listbox");
    C.append(inp, L);
    const todos = listaComandos();
    let vis = [], at = 0;
    const pinta = () => {
      const termos = sem(inp.value).split(/\s+/).filter(Boolean);
      vis = todos.filter(c => termos.every(t => c.busca.includes(t))).slice(0, 60);
      at = Math.min(at, Math.max(vis.length - 1, 0));
      L.innerHTML = "";
      vis.forEach((c, i) => {
        const r = el("div", "cmd" + (i === at ? " at" : "")); r.setAttribute("role", "option"); r.setAttribute("aria-selected", i === at ? "true" : "false");
        r.append(el("span", "cmd-grupo", c.grupo), el("span", "cmd-tit", c.titulo));
        if (c.dica) r.append(el("kbd", "", c.dica));
        r.onclick = () => roda(c);
        L.append(r);
      });
      if (!vis.length) L.append(el("div", "nota", "Nada encontrado."));
      const a = L.querySelector(".at"); if (a) a.scrollIntoView({ block: "nearest" });
    };
    const roda = c => { d.close(); c.faz(); };
    inp.oninput = () => { at = 0; pinta(); };
    inp.onkeydown = ev => {
      if (ev.key === "ArrowDown") { at = Math.min(at + 1, vis.length - 1); pinta(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp") { at = Math.max(at - 1, 0); pinta(); ev.preventDefault(); }
      else if (ev.key === "Enter") { if (vis[at]) roda(vis[at]); ev.preventDefault(); }
    };
    pinta();
    if (!d.open) d.showModal();
    inp.focus();
  }

  function teclas(ev) {
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === "k" || ev.key === "K")) { ev.preventDefault(); comandos(); return; }
    if (ev.ctrlKey || ev.metaKey || ev.altKey || emCampo(ev) || document.querySelector("dialog[open]")) return;
    const k = ev.key;
    if (k === "?") { ev.preventDefault(); atalhos(); return; }
    if (k === "[") { painel("esq"); return; }
    if (k === "]") { painel("dir"); return; }
    if (k === "Escape" && ferr === "medir") { ativa("selecionar"); return; }
    if (k === "Escape" && ferr === "secao") { ativa("selecionar"); return; }
    const edita = Nervura3D.ativo() || No3D.ativo();
    if (!edita && k.length === 1 && "12345".includes(k)) { Etapas.vai(+k); return; }
    const f = FERR.find(x => x[2].toLowerCase() === k.toLowerCase());
    if (f && Etapas.atual() === 1) { ev.preventDefault(); ativa(f[0]); }
  }

  montaVista(); montaBarra(); montaEtapas(); montaRodape(); montaInspetor();
  Estado.ouve(k => { if (k === "ferramenta" || k === "sel" || k === "esq") sincroniza(); });
  window.addEventListener("keydown", teclas);
  sincroniza();

  return { nova: true, troca, ativa, ferramenta: () => ferr, atalhos, comandos, painel, selos: () => ({ ...estados }) };
})();
