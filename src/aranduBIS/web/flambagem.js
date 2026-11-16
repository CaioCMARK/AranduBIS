"use strict";

const Flamb3 = (() => {
  const CAMPOS = [
    { g: "Chapeado de balsa", k: "knockdown_pele", cfg: "estrutura.knockdown_pele", r: "Imperfeição (× teoria)", d: "0 = automático (NASA SP-8007 por painel, pelo raio e pela espessura). Ou fixe, por exemplo o valor que reproduz o seu modelo de elementos finitos.", zero: true },
    { k: "balsa_E_transv", cfg: "estrutura.balsa_E_transv", r: "E transversal (GPa)", d: "Estimativa: balsa, 3 a 5 % do E na fibra." },
  ];
  const CHAVE = "aranduBIS.flamb";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a"];
  let v = {}, res = null, tempo = null, seq = 0, sel = null;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = null; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (ativa()) { parametros(); agenda(); } });
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "flambagem";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const pc = x => x >= 900 ? "> 900 %" : fmt(100 * x, 0) + " %";

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Nervuras e flambagem";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null || !(x > 0)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; Padroes.toca(v, c.k); guarda(); agenda();
      });
      i.title = c.d; G.append(l, i);
    });
    if (res) {
      const s = document.createElement("select"); res.asas.forEach(a => s.add(new Option(a.nome, a.nome)));
      sel = res.asas.some(a => a.nome === sel) ? sel : res.asas[0].nome; s.value = sel;
      s.onchange = () => { sel = s.value; graficos(); baixo(); };
      const G2 = document.createElement("div"); G2.className = "prop"; G2.append(el("label", "Asa"), s); P.append(el("div", "Gráficos", "grupo-par"), G2);
    }
    P.append(el("div", "Carga, qualidade da balsa e materiais: as das vistas Cargas e Asa e de Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }
  const corpo = () => Object.assign(Asa3.corpo(), { knockdown_pele: v.knockdown_pele, balsa_E_transv: v.balsa_E_transv });

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando cargas, margens da asa e flambagem…");
    try {
      const r = await chama("/api/flambagem", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  const asaSel = () => res.asas.find(a => a.nome === sel) || res.asas[0];

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res || !res.critico) { V.className = "veredito neutro"; vazio(V); return; }
    const c = res.critico, ok = c.margem_pele >= 0; V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${ok ? "Chapeado sem flambagem" : "Chapeado flamba"} (estimativa):</b> pior painel ${pc(c.margem_pele)} em ${res.pior}, y de ${fmt(c.y0, 2)} a ${fmt(c.y1, 2)} m · tensão ${fmt(c.sigma_pele_MPa, 2)} MPa contra ${fmt(c.sigma_cr_MPa, 2)} MPa críticos · o fator de imperfeição precisaria ser ≥ ${fmt(c.knockdown_para_margem_zero, 2)} (usado neste painel: ${fmt(c.knockdown !== undefined ? c.knockdown : v.knockdown_pele, 2)})`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const a = asaSel(), g = [0, 1, 2].map(() => el("div", "", "graf")); C.append(...g);
    const P = a.paineis.filter(p => p.sigma_cr_MPa !== undefined), ym = p => 0.5 * (p.y0 + p.y1);
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: `Tensão no chapeado e crítica por painel, ${a.nome}`, xlab: "y (m)", ylab: "MPa",
        series: [{ nome: "atuante (ruptura)", x: P.map(ym), y: P.map(p => p.sigma_pele_MPa), cor: COR[3] }, { nome: "crítica (casca)", x: P.map(ym), y: P.map(p => p.sigma_cr_MPa), cor: COR[0] },
                 { nome: "crítica (placa plana)", x: P.map(ym), y: P.map(p => p.sigma_cr_plana_MPa), cor: COR[1], tracejado: true }] });
      Grafico.desenha(g[1], { titulo: "Margem por painel", xlab: "y (m)", ylab: "margem (%)", yMin: -100, yMax: 300,
        series: [{ nome: "chapeado", x: P.map(ym), y: P.map(p => Math.min(300, 100 * p.margem_pele)), cor: COR[0] },
                 { nome: "alma (cisalhamento)", x: a.paineis.filter(p => p.margem_alma !== undefined).map(ym), y: a.paineis.filter(p => p.margem_alma !== undefined).map(p => Math.min(300, 100 * p.margem_alma)), cor: COR[2] }],
        refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#c85a5a" }] });
      if (a.sensibilidade) Grafico.desenha(g[2], { titulo: "Margem do pior painel × vão entre nervuras", xlab: "vão (m)", ylab: "margem (%)", yMin: -100, yMax: 300,
        series: [{ nome: "chapeado", x: a.sensibilidade.a, y: a.sensibilidade.margem.map(m => Math.min(300, 100 * m)), cor: COR[0] }],
        refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#c85a5a" }, { tipo: "v", valor: a.pior_pele.a, rotulo: "vão atual", cor: "#999" }] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Painéis entre nervuras", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const a = asaSel();
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>y (m)</th><th>vão</th><th>largura</th><th>raio</th><th>tensão (MPa)</th><th>crítica casca / placa (MPa)</th><th>margem chapeado</th><th>imperfeição mín.</th><th>nervuras falsas</th><th>alma: margem</th></tr>`
      + a.paineis.map(p => `<tr><td>${fmt(p.y0, 2)} a ${fmt(p.y1, 2)}</td><td>${fmt(1000 * p.a, 0)} mm</td><td>${p.b ? fmt(1000 * p.b, 0) + " mm" : "—"}</td><td>${p.R ? fmt(1000 * p.R, 0) + " mm" : "—"}</td>`
        + `<td>${fmt(p.sigma_pele_MPa, 2)}</td><td>${p.sigma_cr_MPa === undefined ? "—" : fmt(p.sigma_cr_MPa, 2) + " / " + fmt(p.sigma_cr_plana_MPa, 2)}</td>`
        + `<td>${p.margem_pele === undefined ? "—" : pc(p.margem_pele) + (p.margem_pele < 0 ? " (FORA)" : "")}</td><td>${p.knockdown_para_margem_zero === undefined ? "—" : fmt(p.knockdown_para_margem_zero, 2)}</td>`
        + `<td>${p.nervuras_falsas === undefined ? "—" : p.nervuras_falsas === null ? "não resolve" : p.nervuras_falsas}</td><td>${p.margem_alma === undefined ? "—" : pc(p.margem_alma)}</td></tr>`).join("");
    C.append(t);
    C.append(el("div", `${a.nome}: nervuras em y = ${a.nervuras.map(x => fmt(x, 2)).join(", ")} m. Chapeado de balsa ${fmt(1000 * a.espessura_chapeado, 1)} mm, fibra na envergadura; E transversal ${fmt(a.E_transv_GPa, 2)} GPa, imperfeição ${a.knockdown_auto ? "automática (SP-8007, por painel)" : fmt(a.knockdown, 2)}.`
      + (a.n_nervuras_falsas ? ` Para fechar a margem onde as nervuras falsas resolvem: ${a.n_nervuras_falsas} nervuras falsas nas duas semi-asas, cerca de ${fmt(a.massa_falsas_g, 0)} g.` : ""), "nota"));
    if (a.paineis_sem_solucao.length) C.append(el("div", `Em ${a.paineis_sem_solucao.length} painéis nenhuma nervura falsa viável (vão ≥ 40 mm) fecha a margem neste modelo: a casca teórica quase não depende do vão. Um FEM de casca de referência mostrou ganho de 0,92 para 1,26 com nervura falsa; este modelo não reproduz esse ganho, então confira o autovalor do FEM antes de decidir.`, "nota"));
    C.append(el("div", "Estimativa analítica (casca cilíndrica de Donnell com redutor de imperfeição), não substitui o FEM de casca nem o ensaio. Alma da longarina: placa plana em cisalhamento com E efetivo médio geométrico. Fora daqui: flambagem global da caixa, das nervuras e da cauda.", "nota"));
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
    casca(C);
  }

  // ---- baia em casca no CalculiX ----
  let fe = null, feRodando = false;
  function casca(C) {
    const B = el("div", "", "bloco"); C.append(B);
    B.append(el("h5", "Baia crítica em casca (CalculiX)"));
    const bt = el("button", feRodando ? "Rodando o CalculiX…" : (fe ? "Rodar de novo" : "Simular a baia crítica no CalculiX"));
    bt.disabled = feRodando;
    bt.onclick = async () => {
      feRodando = true; mostra();
      try { fe = await chama("/api/chapeado_fe", corpo()); } catch (e) { fe = { erro: e.message }; }
      feRodando = false; mostra();
    };
    B.append(bt, el("div", "Caixa-D entre duas nervuras em elementos de casca: flambagem linear, flambagem com imperfeição (não linear) e abaulamento sob a pressão. Leva de alguns segundos a alguns minutos.", "nota"));
    if (!fe) return;
    if (fe.erro) { B.append(el("div", fe.erro, "nota erro")); return; }
    const m = x => x === null || x === undefined ? "—" : pc(x) + (x < 0 ? " (FORA)" : "");
    const t = document.createElement("table");
    t.innerHTML = `<tr><th></th><th>analítico</th><th>casca (CalculiX)</th></tr>`
      + `<tr><td>crítica sem imperfeição (MPa)</td><td>${fmt(fe.analitico.sigma_cr_curvo_MPa, 2)}</td><td>${fmt(fe.sigma_cr_linear_MPa, 2)}</td></tr>`
      + `<tr><td>fator de imperfeição</td><td>${fmt(fe.analitico.knockdown_sp8007, 2)} (SP-8007)</td><td>${fe.knockdown_medido ? fmt(fe.knockdown_medido, 2) : "—"} (pele sai ${fmt(fe.imperfeicao_t, 1)}t → 1t)</td></tr>`
      + `<tr><td>flambagem com imperfeição (MPa)</td><td>${fmt(fe.analitico.sigma_cr_curvo_MPa * fe.analitico.knockdown_sp8007, 2)}</td><td>${fe.sigma_flambagem_MPa ? fmt(fe.sigma_flambagem_MPa, 2) : "—"}</td></tr>`
      + `<tr><td>margem (contra ${fmt(fe.sigma_ref_MPa, 2)} MPa)</td><td>${m(fe.analitico.margem_estimada)}</td><td>${m(fe.margem_fe)}</td></tr>`
      + (fe.tsai_hill && fe.tsai_hill.margem_tsai_hill !== undefined
        ? `<tr><td>ruptura da balsa, Tsai-Hill${fe.tsai_hill.fator < 1 ? " (a " + fmt(100 * fe.tsai_hill.fator, 0) + " % da carga)" : ""}</td><td>só ao longo da fibra</td><td>${m(fe.tsai_hill.margem_tsai_hill)}, domina: ${fe.tsai_hill.domina} `
          + `(σ1 ${fmt(fe.tsai_hill.s1_MPa, 2)}, σ2 ${fmt(fe.tsai_hill.s2_MPa, 2)}, τ12 ${fmt(fe.tsai_hill.s12_MPa, 2)} MPa)</td></tr>` : "");
    B.append(t);
    B.append(el("div", `${fe.asa}, baia y = ${fmt(fe.y0, 3)} a ${fmt(fe.y1, 3)} m, caso ${fe.caso.replace("_", " ")}. Pressão de sucção no extradorso ${fmt(fe.dp_Pa, 0)} Pa (carga de ruptura). `
      + (fe.w_para_fora_mm !== undefined ? `Abaulamento ${fe.abaulamento_convergiu ? "na carga de ruptura" : "até " + fmt(100 * fe.abaulamento_ate_fator, 0) + " % dela (depois não converge: a pele colapsa)"}: ${fmt(fe.w_para_fora_mm, 2)} mm para fora, ${fmt(fe.w_para_dentro_mm, 2)} mm para dentro.` : ""), "nota"));
    const g1 = el("div", "", "graf"), g2 = el("div", "", "graf"); B.append(g1, g2);
    Grafico.desenha(g1, { titulo: "Pele: deslocamento máximo × carga (só compressão, com imperfeição)", xlab: "fração da carga de ruptura", ylab: "mm",
      series: [{ nome: "w máx", x: fe.curva.fator, y: fe.curva.w_max_mm, cor: "#4a86c5" }],
      refs: [{ tipo: "h", valor: 1000 * fe.ts, rotulo: "1 espessura", cor: "#c85a5a" }, { tipo: "v", valor: 1, rotulo: "ruptura", cor: "#999" }] });
    if (fe.perfil_meio) {
      const P = fe.perfil_meio, k = Math.min(20, 0.03 * Math.max(...P.x) / Math.max(1e-6, ...P.x.map((x, i) => Math.hypot(P.x_def[i] - x, P.z_def[i] - P.z[i]))));
      Grafico.desenha(g2, { titulo: `Seção no meio da baia (deslocamento × ${fmt(k, 0)})`, xlab: "x (mm)", ylab: "z (mm)", igualEscala: true,
        series: [{ nome: "original", x: P.x.map(v => 1000 * v), y: P.z.map(v => 1000 * v), cor: "#999" },
                 { nome: "deformada", x: P.x.map((x, i) => 1000 * (x + k * (P.x_def[i] - x))), y: P.z.map((z, i) => 1000 * (z + k * (P.z_def[i] - z))), cor: "#c85a5a" }] });
    }
    fe.avisos.forEach(x => B.append(el("div", x, "nota")));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("flambagem", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
