"use strict";

const Cargas3 = (() => {
  const CAMPOS = [
    { g: "Velocidades", k: "Vc", cfg: "estrutura.V_c", r: "Cruzeiro Vc (m/s)", d: "Velocidade de cruzeiro do diagrama V-n." },
    { k: "Vd", cfg: "estrutura.V_d", r: "Mergulho Vd (m/s)", d: "Velocidade de mergulho; precisa ser maior que Vc." },
    { g: "Fatores de carga", k: "n_max", cfg: "estrutura.n_max", r: "Máximo de manobra", d: "Fator de carga limite de manobra." },
    { k: "n_min", cfg: "estrutura.n_min", r: "Mínimo (negativo)", d: "0 = sem carga negativa de projeto.", zero: true },
    { k: "fator_seguranca", cfg: "estrutura.fator_seguranca", r: "Fator de segurança", d: "Carga de ruptura = fator × carga limite." },
    { g: "Rajada vertical", k: "U_c", cfg: "estrutura.rajada_Vc", r: "Em Vc (m/s)", d: "Rajada de projeto em cruzeiro (Pratt-Cooper)." },
    { k: "U_d", cfg: "estrutura.rajada_Vd", r: "Em Vd (m/s)", d: "Rajada reduzida em mergulho." },
    { g: "Aeronave", k: "CL_max", cfg: "estrutura.CL_max", r: "CL máximo (0 = calcular)", d: "0 usa a teoria de faixas com as polares do banco.", zero: true },
    { k: "massa_kg", r: "Massa (kg, 0 = modelo)", d: "0 usa a massa das peças declaradas no modelo.", zero: true, p: 0 },
  ];
  const CHAVE = "aranduBIS.cargas";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#a278c8", "#5aaaaa"];
  let v = {}, res = null, tempo = null, seq = 0, sup = null;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = c.p === undefined ? null : c.p; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (ativa()) { parametros(); agenda(); } });
  const ativa = () => document.body.dataset.etapa === "3";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Cargas";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null || (!c.zero && !(x > 0)) || (c.k === "n_min" && x > 0) || (c.k !== "n_min" && x < 0)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; Padroes.toca(v, c.k); guarda(); agenda();
      });
      i.title = c.d; G.append(l, i);
    });
    if (res) {
      P.append(el("div", "Superfície do gráfico", "grupo-par"));
      const s = document.createElement("select");
      Object.keys(res.criticos).sort().forEach(n => s.add(new Option(n, n)));
      s.value = sup && res.criticos[sup] ? sup : (sup = s.options[0].value);
      s.onchange = () => { sup = s.value; graficos(); };
      const G2 = document.createElement("div"); G2.className = "prop"; G2.append(el("label", "Superfície"), s); P.append(G2);
    }
    P.append(el("div", "Valores de partida: documento de referência (hipóteses editáveis em Configurações).", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  function corpo() {
    return { esquema: esq, rho: +Padroes.get("analise.rho") || 1.1, Vc: v.Vc, Vd: v.Vd, n_max: v.n_max, n_min: v.n_min,
             fator_seguranca: v.fator_seguranca, U_c: v.U_c, U_d: v.U_d, CL_max: v.CL_max > 0 ? v.CL_max : null,
             massa_kg: v.massa_kg > 0 ? v.massa_kg : null, cl_min_rel: +Padroes.get("estrutura.cl_min_rel") || 0.5,
             ncrit: +Padroes.get("polares.ncrit_banco") || 4 };
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando as cargas (equilibra a aeronave em cada ponto do diagrama)…");
    try {
      const r = await chama("/api/cargas", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { V.textContent = "—"; return; }
    const vn = res.vn;
    V.innerHTML = `<b>V-n:</b> Vs ${fmt(vn.Vs, 1)} · Va ${fmt(vn.Va, 1)} · Vc ${fmt(vn.Vc, 1)} · Vd ${fmt(vn.Vd, 1)} m/s · n de projeto ${fmt(vn.n_projeto, 2)} · massa ${fmt(res.massa_kg, 2)} kg (${res.origem_massa}) · CL máx. ${fmt(vn.CL_max, 2)} (${res.origem_CL_max})`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1, 2, 3].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      const k = res.vn.curvas;
      const pts = res.vn.pontos.map(p => ({ x: p.V, y: p.n, rotulo: "", cor: p.origem === "rajada" ? "#d98a3d" : "#4a86c5" }));
      const series = [{ nome: "manobra +", x: k.V, y: k.manobra_pos, cor: "#4a86c5" }, { nome: "rajada +", x: k.rajada_V, y: k.rajada_pos, cor: "#d98a3d" },
                      { nome: "rajada −", x: k.rajada_V, y: k.rajada_neg, cor: "#d98a3d", tracejado: true }];
      if (res.vn.n_min < 0) series.push({ nome: "manobra −", x: k.V, y: k.manobra_neg, cor: "#4a86c5", tracejado: true });
      Grafico.desenha(g[0], { titulo: "Diagrama V-n", xlab: "velocidade (m/s)", ylab: "fator de carga n", series, pontos: pts,
        refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#999" }] });
      const nomes = s => s.superficies.find(x => x.nome === sup);
      const cs = res.casos.filter(c => nomes(c));
      const serie = (campo) => cs.map((c, i) => { const s = nomes(c); return { nome: c.nome, x: s.y, y: s[campo], cor: COR[i % COR.length] }; });
      Grafico.desenha(g[1], { titulo: `Carga por metro, ${sup} (semi-asa)`, xlab: "y (m)", ylab: "N/m (sustentação − peso da asa)", series: serie("liquida_por_m") });
      Grafico.desenha(g[2], { titulo: "Esforço cortante", xlab: "y (m)", ylab: "N", series: serie("cortante") });
      Grafico.desenha(g[3], { titulo: "Momento fletor", xlab: "y (m)", ylab: "N·m", series: serie("fletor") });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Pontos críticos", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const nomes = Object.keys(res.criticos).sort();
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>ponto do diagrama</th><th>V (m/s)</th><th>n</th><th>α (°)</th><th>comando (°)</th>${nomes.map(n => `<th>${n}: cortante / fletor na raiz (N · N·m)</th>`).join("")}</tr>`
      + res.casos.map(c => `<tr><td>${c.nome.replace("_", " ")}</td><td>${fmt(c.V, 1)}</td><td>${fmt(c.n, 2)}</td><td>${fmt(c.alpha, 1)}</td><td>${fmt(c.deflexao, 1)}</td>`
        + nomes.map(n => { const s = c.superficies.find(x => x.nome === n); return `<td>${s ? fmt(s.cortante_raiz, 1) + " / " + fmt(s.fletor_raiz, 1) : "—"}</td>`; }).join("") + "</tr>").join("");
    C.append(t);
    const u = document.createElement("table");
    u.innerHTML = `<tr><th>superfície</th><th>caso crítico</th><th>fletor na raiz, limite (N·m)</th><th>fletor de ruptura ×${fmt(res.fator_seguranca, 2)} (N·m)</th><th>cortante de ruptura (N)</th></tr>`
      + nomes.map(n => { const c = res.criticos[n]; return `<tr><td>${n}</td><td>${c.caso.replace("_", " ")}</td><td>${fmt(c.fletor_raiz, 1)}</td><td>${fmt(c.fletor_ultimo, 1)}</td><td>${fmt(c.cortante_ultimo, 1)}</td></tr>`; }).join("");
    C.append(u);
    C.append(el("div", `Carga de cada faixa vem do VLM com a aeronave equilibrada (trim) em n·peso; o alívio inercial usa a massa da própria asa, distribuída pela corda. CG do modelo: x ${fmt(res.x_cg, 3)} m, z ${fmt(res.z_cg, 3)} m. As forças são normais à corda; a carga limite é a do diagrama, a de ruptura vale o fator de segurança vezes ela.`, "nota"));
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Fora desta etapa por enquanto: os esforços nos montantes entre as asas (a divisão da carga entre elas é a do VLM), a deriva e o pouso. VLM linear: perto do estol a carga real é menor.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  const lista = () => { const L = $("lista3"); L.innerHTML = ""; L.append(Object.assign(document.createElement("div"), { className: "el sel", textContent: "Cargas (V-n e envergadura)" })); };

  return { entra() { lista(); parametros(); agenda(); if (res) mostra(); }, dados: () => ({ v, res }) };
})();
