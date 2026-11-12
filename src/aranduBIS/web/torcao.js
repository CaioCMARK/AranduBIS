"use strict";

const Torcao3 = (() => {
  const CAMPOS = [
    { g: "Calibração com ensaio", k: "calib_EI", r: "EI (× modelo)", d: "1 = parede fina com os módulos de Configurações. Troque pelo fator do ensaio de flexão ou do GVT (vista Calibração com ensaio)." },
    { k: "calib_GJ", cfg: "estrutura.calib_GJ", r: "GJ (× modelo)", d: "1 = parede fina (Bredt-Batho). Troque pelo fator do ensaio de torção estática." },
    { k: "ea_desloc_c", cfg: "estrutura.ea_desloc_c", r: "Linha elástica (Δ x/c, + para trás)", d: "Correção do GVT sobre a linha elástica calculada.", zero: true },
    { g: "Aerodinâmica das faixas", k: "x_ca_c", cfg: "estrutura.x_ca_c", r: "Centro aerodinâmico (x/c)", d: "Hipótese: 0,25." },
    { k: "cl_alpha_2d", cfg: "estrutura.cl_alpha_2d", r: "cl-α 2D (1/rad)", d: "Teoria de faixas: 2π é conservador." },
    { k: "eficiencia_comando", cfg: "estrutura.eficiencia_comando", r: "Eficiência do aileron", d: "Perda viscosa sobre cl-δ e cm-δ de perfil fino." },
    { g: "Requisito", k: "margem_aeroelastica", cfg: "estrutura.margem_aeroelastica", r: "Margem (× Vd)", d: "Reversão e divergência acima de 1,2 × Vd." },
  ];
  const CHAVE = "aranduBIS.torcao";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a"];
  let v = {}, res = null, fe = null, tempo = null, seq = 0, seqFe = 0, sel = null;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = null; });
  if (!(v.calib_EI > 0)) v.calib_EI = 1;
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (ativa()) { parametros(); agenda(); } });
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "torcao";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Torção";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null || (!c.zero && !(x > 0))) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; Padroes.toca(v, c.k); guarda(); agenda();
      });
      i.title = c.d; G.append(l, i);
    });
    if (res) {
      const s = document.createElement("select"); res.asas.forEach(a => s.add(new Option(a.nome, a.nome)));
      sel = res.asas.some(a => a.nome === sel) ? sel : res.asas[0].nome; s.value = sel;
      s.onchange = () => { sel = s.value; graficos(); baixo(); };
      const G2 = document.createElement("div"); G2.className = "prop"; G2.append(el("label", "Asa"), s);
      P.append(el("div", "Gráficos", "grupo-par"), G2);
    }
    P.append(el("div", "Materiais: Configurações. Velocidade de mergulho e densidade: as da vista Cargas e da Análise.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 400); }

  function corpo() {
    const c = Cargas3.corpo();
    return { esquema: esq, rho: c.rho, Vd: c.Vd, materiais: Asa3.materiais(), margem_aeroelastica: v.margem_aeroelastica, x_ca_c: v.x_ca_c,
             cl_alpha_2d: v.cl_alpha_2d, eficiencia_comando: v.eficiencia_comando, calib_GJ: v.calib_GJ, calib_EI: v.calib_EI, ea_desloc_c: v.ea_desloc_c };
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando a torção…");
    try {
      const r = await chama("/api/torcao", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
    calculaFE(corpo());
  }

  async function calculaFE(base) {
    const meu = ++seqFe;
    fe = null;
    if (!res) return;
    try {
      const r = await chama("/api/torcao_fe", Object.assign({}, Cargas3.corpo(), base, { esquema: esq }));
      if (meu !== seqFe) return;
      fe = r.erro ? { erro: r.erro } : r;
    } catch (e) { if (meu !== seqFe) return; fe = { erro: e.message }; }
    if (ativa()) { graficos(); baixo(); }
  }

  const asaSel = () => res.asas.find(a => a.nome === sel) || res.asas[0];

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; V.textContent = "—"; return; }
    if (res.VR === null) { V.classList.add("neutro"); V.innerHTML = "<b>Sem reversão de comando verificável:</b> nenhuma asa declara aileron. Só a divergência é checada."; return; }
    const ok = res.margem_VR >= 0; V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${ok ? "Reversão acima do requisito" : "Reversão abaixo do requisito"}:</b> VR ${fmt(res.VR, 1)} m/s (${res.pior}) contra ${fmt(res.V_requerida, 1)} m/s exigidos · margem ${fmt(100 * res.margem_VR, 0)} %`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const a = asaSel(), f = fe && !fe.erro ? fe.asas.find(x => x.nome === a.nome) : null;
    const g = (f ? [0, 1, 2, 3, 4, 5] : [0, 1, 2, 3]).map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: `Rigidez de torção GJ, ${a.nome}`, xlab: "y (m)", ylab: "N·m²",
        series: [{ nome: "GJ", x: a.y, y: a.GJ, cor: COR[0] }] });
      Grafico.desenha(g[1], { titulo: "Linha elástica e centro aerodinâmico", xlab: "y (m)", ylab: "x/c",
        series: [{ nome: "linha elástica", x: a.y, y: a.ea_c, cor: COR[1] }, { nome: "centro aerodinâmico", x: a.y, y: a.y.map(() => a.ca_c), cor: COR[2], tracejado: true }] });
      const cv = a.curva;
      if (cv.V.length) {
        const refs = [{ tipo: "v", valor: a.V_requerida, rotulo: `${fmt(a.fator, 2)} Vd`, cor: "#c85a5a" }, { tipo: "h", valor: 0, rotulo: "", cor: "#999" }];
        Grafico.desenha(g[2], { titulo: "Efetividade do aileron L / L rígido", xlab: "V (m/s)", ylab: "razão", yMin: -1, yMax: 1.1,
          series: [{ nome: "L / L rígido", x: cv.V, y: cv.razao.map(r => Math.max(-1, r)), cor: COR[0] }], refs });
        const fg = Array.from({ length: 40 }, (_, i) => 0.25 + i * 0.1), base = a.VR === null ? null : a.VR / Math.sqrt(a.calib_GJ);
        if (base) Grafico.desenha(g[3], { titulo: "Reversão em função do GJ", xlab: "GJ (× modelo)", ylab: "VR (m/s)",
          series: [{ nome: "VR", x: fg, y: fg.map(k => base * Math.sqrt(k)), cor: COR[3] }],
          refs: [{ tipo: "h", valor: a.V_requerida, rotulo: "exigido", cor: "#c85a5a" }, { tipo: "v", valor: a.calib_GJ, rotulo: "atual", cor: "#999" }] });
      } else { g[2].textContent = "Sem aileron declarado nesta asa."; }
      if (f) {
        Grafico.desenha(g[4], { titulo: `Flecha sob carga limite, ${f.nome} (${f.caso})`, xlab: "y (m)", ylab: "m",
          series: [{ nome: "elementos finitos", x: f.y, y: f.w_fe, cor: COR[0] }, { nome: "integração analítica", x: f.y, y: f.w_analitica, cor: COR[1], tracejado: true }] });
        Grafico.desenha(g[5], { titulo: "Torção sob carga limite (+ = bordo de ataque para cima)", xlab: "y (m)", ylab: "graus",
          series: [{ nome: "elementos finitos", x: f.y, y: f.theta_fe_graus, cor: COR[0] }, { nome: "integração analítica", x: f.y, y: f.theta_analitica_graus, cor: COR[1], tracejado: true }] });
      }
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Resumo", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>asa</th><th>Kθ (N·m/rad, ponta)</th><th>GJ raiz (N·m²)</th><th>GJ mín. (N·m²)</th><th>linha elástica − CA (x/c)</th><th>VR (m/s)</th><th>margem VR</th><th>GJ mínimo (× modelo)</th><th>divergência</th></tr>`
      + res.asas.map(a => `<tr><td>${a.nome}</td><td>${fmt(a.K_theta, 3)}</td><td>${fmt(a.GJ[0], 1)}</td><td>${fmt(Math.min(...a.GJ), 2)}</td>`
        + `<td>${fmt(a.folga_ea_ca_c.min, 3)} a ${fmt(a.folga_ea_ca_c.max, 3)}</td><td>${a.VR === null ? "—" : fmt(a.VR, 1)}</td>`
        + `<td>${a.margem_VR === null ? "—" : fmt(100 * a.margem_VR, 0) + " %"}</td><td>${a.GJ_minimo === null ? "—" : fmt(a.GJ_minimo, 2)}</td>`
        + `<td>${a.VD === null ? "não ocorre" : fmt(a.VD, 1) + " m/s"}</td></tr>`).join("");
    C.append(t);
    const a = asaSel(), nf = a.fechada.filter(x => x).length;
    C.append(el("div", `${a.nome}: caixa-D fechada em ${nf} de ${a.fechada.length} estações (y de ${fmt(a.y[0], 2)} a ${fmt(a.y[a.y.length - 1], 2)} m); onde o chapeado acaba antes da longarina a seção é aberta e o GJ cai por duas ou três ordens de grandeza. `
      + `Linha elástica = centro de cisalhamento da caixa fechada (fluxo de cisalhamento com os tubos como áreas concentradas).`, "nota"));
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
    if (!fe) C.append(el("div", "Verificação por elementos finitos: calculando as cargas do diagrama V-n (a vista Cargas deixa isso em memória)…", "nota"));
    else if (fe.erro) C.append(el("div", "Verificação por elementos finitos indisponível: " + fe.erro, "nota"));
    else {
      const tf = document.createElement("table");
      tf.innerHTML = `<tr><th>asa</th><th>caso de carga</th><th>flecha na ponta (m)</th><th>analítica (m)</th><th>FE / analítica</th><th>flecha / semi-envergadura</th><th>torção na ponta (°)</th><th>analítica (°)</th><th>FE / analítica</th></tr>`
        + fe.asas.map(b => `<tr><td>${b.nome}</td><td>${b.caso}</td><td>${fmt(b.flecha_ponta_fe_m, 4)}</td><td>${fmt(b.flecha_ponta_analitica_m, 4)}</td>`
          + `<td>${b.razao_flecha === null ? "—" : fmt(b.razao_flecha, 3)}</td><td>${fmt(b.flecha_pct_fe, 1)} %</td><td>${fmt(b.torcao_ponta_fe_graus, 2)}</td>`
          + `<td>${fmt(b.torcao_ponta_analitica_graus, 2)}</td><td>${b.razao_torcao === null ? "—" : fmt(b.razao_torcao, 3)}</td></tr>`).join("");
      C.append(el("div", "Verificação por elementos finitos", "grupo-par"), tf);
      C.append(el("div", `Semi-asa como viga (${fe.asas[0].n_nos} nós) com a rigidez EI e GJ desta página, sob a carga líquida (sustentação menos o peso da asa) do caso de maior fletor do diagrama V-n. É um segundo solver para as mesmas contas: razão perto de 1 confirma a integração analítica.`, "nota"));
      fe.avisos.forEach(x => C.append(el("div", x, "nota")));
    }
    C.append(el("div", "Teoria de faixas, uma semi-asa em balanço, sem montantes entre as asas (conservador), sem enflechamento. Fora daqui: flutter (precisa de massa e inércia da asa), a deformação sob torção refeita no VLM e a torção da cauda (passo 3.4).", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("torcao", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  function aplica(patch) { Object.keys(patch).forEach(k => { v[k] = patch[k]; Padroes.toca(v, k); }); guarda(); if (ativa()) { parametros(); agenda(); } }
  return { dados: () => ({ v, res }), aplica };
})();
