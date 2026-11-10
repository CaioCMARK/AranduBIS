"use strict";

const Asa3 = (() => {
  const ITENS = [["tubo_comp", "Tubo de carbono, compressão", "#4a86c5"], ["tubo_tr", "Tubo de carbono, tração", "#6aa84f"],
                 ["pele_comp", "Chapeado, compressão", "#d98a3d"], ["pele_tr", "Chapeado, tração", "#a278c8"], ["alma_cis", "Alma de balsa, cisalhamento", "#c85a5a"]];
  const CAMPOS = [{ k: "qualidade_balsa", cfg: "estrutura.qualidade_balsa", r: "Qualidade da balsa (×)", d: "Multiplica as tensões admissíveis da balsa. 1 = valor de referência." },
                  { k: "qualidade_carbono", cfg: "estrutura.qualidade_carbono", r: "Qualidade do carbono (×)", d: "Multiplica as tensões admissíveis do tubo. 1 = valor de referência." }];
  const CHAVE = "aranduBIS.asa";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#a278c8", "#5aaaaa"];
  let v = {}, res = null, tempo = null, seq = 0, sel = null, caso = null;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = null; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (ativa()) { parametros(); agenda(); } });
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "asa";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const pc = x => x >= 900 ? "> 900 %" : fmt(100 * x, 0) + " %";

  function materiais() {
    const g = k => +Padroes.get("estrutura." + k);
    const m = { balsa: { E: g("balsa_E") * 1e9, X: g("balsa_X") * 1e6, XC: g("balsa_XC") * 1e6, S: g("balsa_S") * 1e6 },
                tubo_carbono: { E: g("tubo_E") * 1e9, X: g("tubo_X") * 1e6, XC: g("tubo_XC") * 1e6 } };
    Object.values(m).forEach(o => Object.keys(o).forEach(k => { if (!(o[k] > 0)) delete o[k]; }));
    return m;
  }

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Asa";
    P.append(el("div", "Qualidade do lote", "grupo-par"));
    const G = document.createElement("div"); G.className = "prop"; P.append(G);
    CAMPOS.forEach(c => {
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null || !(x > 0)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; Padroes.toca(v, c.k); guarda(); agenda();
      });
      i.title = c.d; G.append(l, i);
    });
    if (res) {
      const nomes = res.asas.map(a => a.nome);
      sel = nomes.includes(sel) ? sel : nomes[0];
      const s = document.createElement("select"); nomes.forEach(n => s.add(new Option(n, n))); s.value = sel;
      s.onchange = () => { sel = s.value; mostra(); };
      const c2 = document.createElement("select"); const cs = res.asas.find(a => a.nome === sel).casos.map(c => c.caso);
      caso = cs.includes(caso) ? caso : cs[0]; cs.forEach(n => c2.add(new Option(n.replace("_", " "), n))); c2.value = caso;
      c2.onchange = () => { caso = c2.value; graficos(); };
      const G2 = document.createElement("div"); G2.className = "prop";
      G2.append(el("label", "Asa"), s, el("label", "Caso (tensões e flecha)"), c2); P.append(el("div", "Gráficos", "grupo-par"), G2);
    }
    P.append(el("div", "Tensões admissíveis, módulos e a procedência de cada número: Configurações → Materiais da estrutura. Carga: vista Cargas.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  function corpo() {
    return Object.assign(Cargas3.corpo(), { materiais: materiais(), qualidade_balsa: v.qualidade_balsa, qualidade_carbono: v.qualidade_carbono });
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando cargas e margens da asa…");
    try {
      const r = await chama("/api/asa", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  const nomeItem = k => ITENS.find(i => i[0] === k)[1];

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; V.textContent = "—"; return; }
    const c = res.critico, ok = c.margem >= 0;
    V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${ok ? "Todas as margens positivas" : "Margem negativa"}:</b> pior caso ${pc(c.margem)} em ${nomeItem(c.item).toLowerCase()}, ${c.asa}, ${c.caso.replace("_", " ")}, y = ${fmt(c.y, 2)} m · flecha máx. ${fmt(Math.max(...res.asas.map(a => a.flecha_max_pct)), 1)} % da semi-envergadura · carga de ruptura = ${fmt(res.asas[0].fator_seguranca, 2)} × limite`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const a = res.asas.find(x => x.nome === sel) || res.asas[0], k = a.casos.find(c => c.caso === caso) || a.casos[0];
    const g = [0, 1, 2, 3].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      const minimo = it => a.y.map((_, j) => Math.min(...a.casos.map(c => c.margens[it][j])) * 100);
      Grafico.desenha(g[0], { titulo: `Margem de segurança por estação, ${a.nome}`, xlab: "y (m)", ylab: "margem (%)", yMin: 0, yMax: 300,
        series: ITENS.map(([it, n, cor]) => ({ nome: n, x: a.y, y: minimo(it).map(x => Math.min(x, 300)), cor })),
        refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#c85a5a" }] });
      Grafico.desenha(g[1], { titulo: `Tensão nos tubos (${k.caso.replace("_", " ")})`, xlab: "y (m)", ylab: "MPa",
        series: [{ nome: "compressão", x: a.y, y: k.tensao_MPa.tubo_comp, cor: ITENS[0][2] }, { nome: "tração", x: a.y, y: k.tensao_MPa.tubo_tr, cor: ITENS[1][2] }],
        refs: [{ tipo: "h", valor: a.admissiveis_MPa.tubo_comp, rotulo: "admissível", cor: "#c85a5a" }] });
      Grafico.desenha(g[2], { titulo: "Flecha da semi-asa em carga limite", xlab: "y (m)", ylab: "mm",
        series: a.casos.map((c, i) => ({ nome: c.caso.replace("_", " "), x: a.y, y: c.flecha.map(w => 1000 * w), cor: COR[i % COR.length] })) });
      Grafico.desenha(g[3], { titulo: "Rigidez de flexão EI", xlab: "y (m)", ylab: "N·m²",
        series: [{ nome: "EI", x: a.y, y: a.estacoes.EI, cor: "#4a86c5" }] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Margens mínimas", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>asa</th><th>verificação</th><th>admissível (MPa)</th><th>margem mínima</th><th>caso</th><th>y (m)</th></tr>`
      + res.asas.map(a => ITENS.map(([it, n]) => {
        const pior = a.casos.reduce((p, c) => c.minimos[it].margem < p.m ? { m: c.minimos[it].margem, caso: c.caso, y: c.minimos[it].y } : p, { m: Infinity });
        return `<tr><td>${a.nome}</td><td>${n}</td><td>${fmt(a.admissiveis_MPa[it], 1)}</td><td>${pc(pior.m)}${pior.m < 0 ? " (FORA)" : ""}</td><td>${pior.caso.replace("_", " ")}</td><td>${fmt(pior.y, 2)}</td></tr>`;
      }).join("")).join("");
    C.append(t);
    res.asas.forEach(a => {
      const e = a.estacoes;
      C.append(el("div", `${a.nome}: altura da longarina ${fmt(1000 * e.h[0], 1)} mm na raiz e ${fmt(1000 * e.h[e.h.length - 1], 1)} mm na ponta; longarina a ${fmt(100 * e.x_longarina_c[0], 0)} % da corda na raiz; chapeado até ${fmt(100 * e.x_chapeado_c[0], 0)} % na raiz e ${fmt(100 * e.x_chapeado_c[e.x_chapeado_c.length - 1], 0)} % na ponta; EI na raiz ${fmt(e.EI[0], 0)} N·m²; flecha máx. ${fmt(a.flecha_max_pct, 1)} % (${a.flecha_max_caso.replace("_", " ")}).`, "nota"));
    });
    C.append(el("div", `Materiais: ${res.asas[0].fontes.balsa}. ${res.asas[0].fontes.tubo_carbono}.`, "nota"));
    C.append(el("div", "Flexão de viga composta com a rigidez de cada parte (alma, tubos, chapeado) e cisalhamento médio na alma. Ainda não entram: flambagem do chapeado e das almas, torção e divergência, juntas coladas, montantes entre as asas. Não conta como atestado estrutural.", "nota"));
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }

  Etapa3.registra("asa", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { materiais, corpo, dados: () => ({ v, res }) };
})();
