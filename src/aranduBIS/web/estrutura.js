"use strict";

const Estrutura = (() => {
  let MATERIAIS = ["balsa"];
  fetch("/api/materiais").then(r => r.json()).then(d => { MATERIAIS = d.materiais.map(m => m.nome); }).catch(() => {});

  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function selecao(valor, opcoes, ao) {
    const s = document.createElement("select");
    opcoes.forEach(o => s.add(new Option(o, o)));
    s.value = valor;
    s.onchange = () => ao(s.value);
    return s;
  }

  function bloco(C, titulo) {
    const b = el("div", "", "bloco"); b.append(el("h5", titulo)); C.append(b); return b;
  }

  function tabela(B, cabecalho, linhas, ao_remover) {
    const t = document.createElement("table");
    const h = document.createElement("tr");
    cabecalho.forEach(c => h.append(el("th", c)));
    h.append(el("th")); t.append(h);
    linhas.forEach((cels, i) => {
      const tr = document.createElement("tr");
      cels.forEach(c => { const td = document.createElement("td"); td.append(c); tr.append(td); });
      const rm = document.createElement("td"), b = el("button", "✕"); b.title = "Remover";
      b.onclick = () => ao_remover(i); rm.append(b); tr.append(rm); t.append(tr);
    });
    B.append(t);
  }

  const est = e => e.estrutura || (e.estrutura = {});
  const lista = (o, k) => (o[k] || []).join(" ");
  function textoLista(o, k, ao) {
    const w = entrada("text", lista(o, k), v => {
      const n = v.trim() ? v.trim().split(/[\s,;]+/).map(parseFloat) : [];
      if (n.some(Number.isNaN)) { msg("Use números separados por espaço.", true); return; }
      ao(n);
    });
    w.style.textAlign = "left";
    return w;
  }

  function nervuras(C, e) {
    const B = bloco(C, "Nervuras"), n = (e.estrutura || {}).nervuras || { y: [], espessura: 0.00238, material: "balsa" }, liga = () => { est(e).nervuras = n; };
    const g = el("div", "", "prop"); B.append(g);
    linha(g, "posições y (m)", textoLista(n, "y", v => muda(() => { liga(); n.y = v; })));
    linha(g, "espessura (m)", entrada("number", n.espessura, v => muda(() => { liga(); n.espessura = v; })));
    linha(g, "material", selecao(n.material || "balsa", MATERIAIS, v => muda(() => { liga(); n.material = v; })));
    B.append(el("div", "Informe só o lado positivo: o programa espelha na asa simétrica.", "nota"));
  }

  function longarinas(C, e) {
    const B = bloco(C, "Longarinas"), L = (e.estrutura || {}).longarinas || [];
    tabela(B, ["x (m) do BA", "largura (m)", "material"], L.map(l => [
      entrada("number", l.x, v => muda(() => { l.x = v; })),
      entrada("number", l.largura, v => muda(() => { l.largura = v; })),
      selecao(l.material || "balsa", MATERIAIS, v => muda(() => { l.material = v; }))]),
      i => { muda(() => L.splice(i, 1)); abaConteudo(); });
    const b = el("button", "+ longarina"); b.onclick = () => { muda(() => { est(e).longarinas = L; L.push({ x: 0.07, largura: 0.00238, material: "balsa" }); }); abaConteudo(); };
    B.append(b);
  }

  function tubos(C, e) {
    const B = bloco(C, "Tubos de reforço"), L = (e.estrutura || {}).tubos || [];
    tabela(B, ["x (m)", "lado", "Ø ext (m)", "Ø int (m)", "y de", "y até"], L.map(t => [
      entrada("number", t.x, v => muda(() => { t.x = v; })),
      selecao(t.lado || "extradorso", ["extradorso", "intradorso"], v => muda(() => { t.lado = v; })),
      entrada("number", t.de, v => muda(() => { t.de = v; })),
      entrada("number", t.di, v => muda(() => { t.di = v; })),
      entrada("number", (t.y || [0, 0])[0], v => muda(() => { t.y = [v, (t.y || [0, 0])[1]]; })),
      entrada("number", (t.y || [0, 0])[1], v => muda(() => { t.y = [(t.y || [0, 0])[0], v]; }))]),
      i => { muda(() => L.splice(i, 1)); abaConteudo(); });
    const b = el("button", "+ tubo");
    b.onclick = () => { muda(() => { est(e).tubos = L; L.push({ x: 0.07, lado: "extradorso", de: 0.003, di: 0.002, y: [0, 0.5] }); }); abaConteudo(); };
    B.append(b);
  }

  function chapeado(C, e) {
    const B = bloco(C, "Chapeado"), ch = (e.estrutura || {}).chapeado;
    const on = el("label"); const cx = document.createElement("input"); cx.type = "checkbox"; cx.checked = !!ch;
    on.append(cx, " ter chapeado"); B.append(on);
    cx.onchange = () => { muda(() => { if (cx.checked) est(e).chapeado = { ate_xc: 0.25, espessura: 0.001, material: "balsa" }; else delete est(e).chapeado; }); abaConteudo(); };
    if (!ch) return;
    const g = el("div", "", "prop"); B.append(g);
    linha(g, "até x/c", entrada("number", ch.ate_xc, v => muda(() => { ch.ate_xc = v; })));
    linha(g, "espessura (m)", entrada("number", ch.espessura, v => muda(() => { ch.espessura = v; })));
    linha(g, "material", selecao(ch.material || "balsa", MATERIAIS, v => muda(() => { ch.material = v; })));
  }

  const DOBRADICAS = { "": "— (não declarada)", fita: "Fita adesiva ou filme", flexivel: "Charneira viva (pele ou filme)", pino: "Dobradiça de nylon com pino", pivo: "Pivô (tubo e mancal, all-moving)" };

  function selecaoRotulos(valor, mapa, ao) {
    const s = document.createElement("select");
    Object.entries(mapa).forEach(([k, r]) => s.add(new Option(r, k)));
    s.value = valor; s.onchange = () => ao(s.value); return s;
  }

  function comandos(C, e) {
    const B = bloco(C, "Superfícies de comando"), L = e.controles || [];
    B.append(el("div", "Cada comando é um trecho da envergadura com eixo (charneira). Para um estabilizador inteiro móvel (all-moving) marque “gira inteira”; para um pedaço que age como aileron, deixe desmarcado e defina o trecho. Valores sem dado do desenho são hipóteses.", "nota"));
    L.forEach((c, i) => {
      const card = el("div", "", "bloco"), g = el("div", "", "prop"); card.append(g);
      const l = (r, w, dica) => { const a = el("label", r); if (dica) a.title = dica; g.append(a, w); };
      const eixo = "x" in c ? "x" : "corda" in c ? "corda" : "xc";
      const rm = el("button", "✕ remover"); rm.onclick = () => { muda(() => { L.splice(i, 1); if (!L.length) delete e.controles; }); abaConteudo(); };
      const cab = el("div"); cab.append(el("b", c.nome + "  "), rm); card.prepend(cab);
      l("nome", entrada("text", c.nome, v => muda(() => { c.nome = v; })));
      l("y de (m)", entrada("number", c.y[0], v => muda(() => { c.y = [v ?? 0, c.y[1]]; })), "Em |y|: vale para os dois lados");
      l("y até (m)", entrada("number", c.y[1], v => muda(() => { c.y = [c.y[0], v ?? 0]; })));
      l("eixo definido por", selecaoRotulos(eixo, { corda: "corda da superfície (m)", x: "x da charneira (m), reto", xc: "fração da corda" }, v => muda(() => {
        const val = c.x ?? c.corda ?? c.xc ?? 0.75; delete c.x; delete c.corda; delete c.xc;
        c[v] = v === "xc" ? 0.75 : v === "x" ? +(val > 1 ? val : 0.2).toFixed(4) : 0.06; }) ), "x: eixo reto e paralelo à longarina (corda varia). corda: eixo paralelo ao bordo de fuga.");
      l("valor do eixo", entrada("number", c[eixo], v => muda(() => { c[eixo] = v; })));
      l("modo", selecaoRotulos(c.modo || "sim", { sim: "simétrico (profundor, flape)", anti: "diferencial (aileron)", lado: "só um lado (leme de meia deriva)" }, v => muda(() => { c.modo = v; })));
      l("deflexão (°)", entrada("number", c.deflexao || 0, v => muda(() => { c.deflexao = v ?? 0; })), "Positivo desce o bordo de fuga");
      l("batente (°)", entrada("number", c.limite ?? "", v => muda(() => { if (v === null) delete c.limite; else c.limite = v; })));
      l("altura do eixo", selecaoRotulos(c.charneira || "meio", { meio: "meio do perfil", extradorso: "extradorso", intradorso: "intradorso" }, v => muda(() => { c.charneira = v; })));
      const mv = document.createElement("input"); mv.type = "checkbox"; mv.checked = !!c.movel; mv.onchange = () => muda(() => { if (mv.checked) c.movel = true; else delete c.movel; });
      l("gira inteira", mv, "All-moving: a seção inteira gira em torno do eixo");
      l("dobradiça", selecaoRotulos(c.dobradica || "", DOBRADICAS, v => muda(() => { if (v) c.dobradica = v; else delete c.dobradica; })), "Entra na massa (g por metro de charneira, hipótese do catálogo)");
      if (c.dobradica) l("massa (g/m)", entrada("number", c.massa_g_m ?? "", v => muda(() => { if (v === null) delete c.massa_g_m; else c.massa_g_m = v; })), "Vazio: usa o valor do catálogo");
      B.append(card);
    });
    const b = el("button", "+ comando");
    b.onclick = () => {
      const ymax = Math.max(...(e.secoes || [{ y: 1 }]).map(s => Math.abs(s.y)));
      muda(() => { e.controles = L; L.push({ nome: nomeUnicoComando(e), y: [+(0.6 * ymax).toFixed(3), +(0.95 * ymax).toFixed(3)], corda: 0.06, deflexao: 0, modo: "anti", charneira: "meio" }); }); abaConteudo();
    };
    B.append(b);
  }

  const nomeUnicoComando = e => { let n = 1; const u = new Set((e.controles || []).map(c => c.nome)); while (u.has("comando_" + n)) n++; return "comando_" + n; };

  return {
    pinta(C, e) {
      if ((e.tipo || "asa") !== "asa") return C.append(el("div", "Estrutura interna só existe para asas.", "nota"));
      nervuras(C, e); longarinas(C, e); tubos(C, e); chapeado(C, e); comandos(C, e);
      const nota = el("div", "As peças de estrutura aparecem na camada “estrutura” da vista e entram na massa e no CG.", "nota");
      C.append(nota);
    },
  };
})();
