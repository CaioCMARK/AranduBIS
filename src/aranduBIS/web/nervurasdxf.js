"use strict";

const NervurasDxf3 = (() => {
  const CHAVE = "aranduBIS.nervuras_dxf";
  let v = { asa: "", kerf_mm: 0.15, folga_tubo_mm: 0.1, folga_longarina_mm: 0.1, bf_min_mm: 1.0, parede_min_mm: 1.2, recesso_chapeado: true, folha_largura_mm: 600, folha_altura_mm: 300, espaco_mm: 4, rotulos: true };
  let res = null, tempo = null, seq = 0;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "nervuras_dxf";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, a) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); return e; };

  function campo(P, rot, dica, k, min) {
    const l = el("label", rot); l.title = dica;
    const i = entrada("number", v[k], x => { if (x === null || x < (min ?? 0)) { msg("Valor inválido em “" + rot + "”.", true); parametros(); return; } v[k] = x; guarda(); agenda(); }); i.title = dica;
    P.append(l, i);
  }

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Nervuras para corte (DXF)";
    let G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Asa", "grupo-par"), G);
    const s = document.createElement("select");
    const asas = (esq && esq.elementos || []).filter(e => e.tipo === "asa" && e.estrutura && e.estrutura.nervuras).map(e => e.nome);
    asas.forEach(n => s.add(new Option(n, n))); s.value = asas.includes(v.asa) ? v.asa : (asas[0] || "");
    s.onchange = () => { v.asa = s.value; guarda(); agenda(); };
    G.append(el("label", "Asa"), s);
    G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Corte", "grupo-par"), G);
    campo(G, "Compensação de corte (mm)", "Largura do feixe do laser: o caminho fica metade disso para fora do material e para dentro dos furos. Meça com um quadrado de teste.", "kerf_mm");
    campo(G, "Folga do tubo (mm)", "Diâmetro do furo = diâmetro do tubo + esta folga.", "folga_tubo_mm");
    campo(G, "Folga da longarina (mm)", "Largura do rasgo = largura da alma + esta folga.", "folga_longarina_mm");
    campo(G, "Bordo de fuga mínimo (mm)", "A nervura é truncada onde o perfil fica com esta espessura (balsa não corta ponta de gume).", "bf_min_mm");
    campo(G, "Parede mínima do furo (mm)", "Se a parede entre o tubo e o contorno for menor que isso, o furo vira entalhe aberto.", "parede_min_mm");
    const c = document.createElement("input"); c.type = "checkbox"; c.checked = !!v.recesso_chapeado;
    c.onchange = () => { v.recesso_chapeado = c.checked; guarda(); agenda(); };
    const lc = el("label", "Recesso do chapeado"); lc.title = "Do bordo de ataque até o fim do chapeado a nervura entra a espessura dele, para o chapeado assentar rente."; G.append(lc, c);
    G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Chapa", "grupo-par"), G);
    campo(G, "Largura da chapa (mm)", "Chapa de balsa ou compensado.", "folha_largura_mm", 1);
    campo(G, "Altura da chapa (mm)", "", "folha_altura_mm", 1);
    campo(G, "Espaço entre peças (mm)", "", "espaco_mm");
    if (res) {
      const b = el("button", "Baixar DXF"); b.onclick = () => {
        const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([res.dxf], { type: "application/dxf" })); a.download = "nervuras_" + res.asa + ".dxf"; a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      };
      P.append(el("div", "Exportar", "grupo-par"), b);
    }
    P.append(el("div", "Camadas do DXF: CORTE (vermelho: contornos e furos), GRAVACAO (azul: número da peça dentro da nervura), ROTULO (verde: número fora, não corta) e FOLHA (moldura da chapa). Unidade: mm.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 400); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(true); return; }
    msg("Gerando as nervuras…");
    try {
      const r = await chama("/api/nervuras_dxf", Object.assign({ esquema: esq, materiais: Asa3.materiais() }, v));
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra(true);
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { V.textContent = "Escolha uma asa com nervuras declaradas (estrutura.nervuras.y) no modelo."; return; }
    V.classList.remove("neutro"); V.classList.add(res.avisos.some(a => a.includes("nao cabe")) ? "ruim" : "ok");
    V.innerHTML = `<b>${res.asa}:</b> ${res.n_nervuras} nervuras em ${res.n_pecas} peças de ${fmt(res.espessura_mm, 2)} mm de ${res.material} · ${res.folhas} chapa${res.folhas > 1 ? "s" : ""} de ${fmt(res.folha_mm[0], 0)} × ${fmt(res.folha_mm[1], 0)} mm · ${fmt(res.area_total_cm2, 0)} cm² de material`;
  }

  function previa() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const d = el("div", "", "graf"); d.style.overflow = "auto"; C.append(d);
    const desenha = () => {
      d.innerHTML = "";
      const W = res.folha_mm[0], H = res.folha_mm[1], n = res.folhas, gap = 24, pxw = Math.max(d.clientWidth - 8, 300);
      const esc = pxw / W, svg = sv("svg", { width: pxw, height: n * (H + gap) * esc, viewBox: `0 0 ${W} ${n * (H + gap)}` });
      const Y = (k, z) => k * (H + gap) + (H - z);
      for (let k = 0; k < n; k++) {
        svg.append(sv("rect", { x: 0, y: Y(k, H), width: W, height: H, fill: "none", stroke: "currentColor", "stroke-opacity": .35, "stroke-width": 1 / esc }));
        const t = sv("text", { x: 3, y: Y(k, H) - 3, fill: "currentColor", "font-size": 9, opacity: .6 }); t.textContent = `chapa ${k + 1}`; svg.append(t);
      }
      res.pecas.forEach(p => {
        const pts = p.contorno.map(q => `${q[0].toFixed(2)},${Y(p.folha, q[1]).toFixed(2)}`).join(" ");
        svg.append(sv("polygon", { points: pts, fill: "#d98a3d", "fill-opacity": .18, stroke: "#b9831a", "stroke-width": 1.2 / esc }));
        p.furos.forEach(f => svg.append(sv("circle", { cx: f.c[0], cy: Y(p.folha, f.c[1]), r: f.d / 2, fill: "none", stroke: "#b9831a", "stroke-width": 1.2 / esc })));
        const m = p.contorno.reduce((a, q) => [a[0] + q[0] / p.contorno.length, a[1] + q[1] / p.contorno.length], [0, 0]);
        const t = sv("text", { x: m[0], y: Y(p.folha, m[1]), "text-anchor": "middle", fill: "currentColor", "font-size": Math.min(8, Math.max(3, p.altura_mm * 0.28)), opacity: .75 }); t.textContent = p.nome; svg.append(t);
      });
      d.append(svg);
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Peças", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>peça</th><th>y (mm)</th><th>chapa</th><th>largura (mm)</th><th>altura (mm)</th><th>furos</th></tr>"
      + res.pecas.map(p => `<tr><td>${p.nome}</td><td>${fmt(1000 * p.y_m, 0)}</td><td>${p.folha + 1}</td><td>${fmt(p.largura_mm, 1)}</td><td>${fmt(p.altura_mm, 1)}</td><td>${p.furos.length ? p.furos.map(f => "Ø" + fmt(f.d, 2)).join(", ") : "—"}</td></tr>`).join("");
    C.append(t);
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "O perfil e a corda são os da estação de cada nervura, sem a torção (washout): a nervura é cortada plana e a incidência vem da montagem na longarina. A nervura se parte em duas peças onde a alma da longarina passa. "
      + "Ficam fora: nervuras cruzadas (em X), recorte do aileron e alívios. Confira o primeiro corte em refugo antes da chapa boa.", "nota"));
  }

  function mostra(forca) { if (!ativa()) return; if (forca || !document.activeElement || document.activeElement.tagName !== "INPUT") { parametros(); veredito(); previa(); baixo(); } }
  Etapa3.registra("nervuras_dxf", { pinta() { parametros(); veredito(); baixo(); agenda(); } });
  return { dados: () => ({ v, res }) };
})();
