"use strict";

const Controle = (() => {
  const CAMPOS = [
    { g: "Condição", k: "V", cfg: "analise.velocidade_cruzeiro", r: "Velocidade (m/s)", d: "Velocidade em que se avalia a rolagem." },
    { k: "beta", r: "Glissada β (°)", d: "Ângulo de derrapagem da condição (0 = voo simétrico).", zero: true, p: 0 },
    { g: "Ailerons", k: "sobe_max", cfg: "controle.sobe_max", r: "Máx. para cima (°)", d: "Batente do aileron para cima." },
    { k: "desce_max", cfg: "controle.desce_max", r: "Máx. para baixo (°)", d: "Batente para baixo (só vale em sobe e desce)." },
    { g: "Critérios", k: "pb2V_min", cfg: "controle.pb2V_min", r: "pb/2V mínimo", d: "Hipótese de projeto: use o requisito da equipe." },
    { k: "t_inclinacao_max", cfg: "controle.t_inclinacao_max", r: "Tempo máx. (s)", d: "Tempo para atingir a inclinação do critério." },
    { k: "inclinacao", cfg: "controle.inclinacao", r: "Inclinação (°)", d: "Ângulo de rolagem do critério de tempo." },
  ];
  const CHAVE = "aranduBIS.controle";
  const NOMES = { sobe_desce: "Sobe e desce", so_sobe: "Só sobe" };
  const COR = { sobe_desce: "#4a86c5", so_sobe: "#d98a3d" };
  let v = {}, res = null, tempo = null, seq = 0;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = c.p === undefined ? null : c.p; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (Analise.nome() === "controle") { parametros(); agenda(); } });
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Ailerons";
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
    P.append(el("div", "Massa, CG e inércias: as da vista Dinâmica de voo.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 400); }

  function corpo() {
    const d = Dinamica.dados().v, I = {};
    ["Ixx", "Iyy", "Izz", "Ixz"].forEach(k => { if (d[k] !== null && d[k] !== undefined) I[k] = d[k]; });
    return { esquema: esq, V: v.V, rho: d.rho || 1.1, x_cg: d.x_cg, massa_kg: d.massa_kg > 0 ? d.massa_kg : null, modo_inercia: d.modo,
             raios: { rx: d.rx, ry: d.ry, rz: d.rz }, inercias: Object.keys(I).length ? I : null,
             sobe_max: v.sobe_max, desce_max: v.desce_max, pb2V_min: v.pb2V_min, t_inclinacao_max: v.t_inclinacao_max, inclinacao: v.inclinacao, beta: v.beta, ncrit: +Padroes.get("polares.ncrit_banco") || 4 };
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando…");
    try {
      const r = await chama("/api/controle", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito";
    if (!res) { V.textContent = "—"; return; }
    const o = res.opcoes, bons = Object.keys(o).filter(k => o[k].ok_pb2V && o[k].ok_tempo);
    V.classList.add(bons.length ? "ok" : "ruim");
    V.innerHTML = (bons.length ? `<b>Cumprem o critério:</b> ${bons.map(k => NOMES[k]).join(" e ")}` : "<b>Nenhuma opção cumpre o critério</b>")
      + " · " + Object.keys(o).map(k => `${NOMES[k]}: pb/2V ${fmt(o[k].pb2V, 3)}, ${o[k].tempo_inclinacao_s === null ? "—" : fmt(o[k].tempo_inclinacao_s, 2) + " s"} até ${fmt(res.criterios.inclinacao, 0)}°`).join(" · ");
  }

  function graficos() {
    const C = $("graficos2"); C.innerHTML = "";
    if (!res) return;
    const a = el("div", "", "graf"), b = el("div", "", "graf"); C.append(a, b);
    const desenha = () => {
      const k = res.curva;
      Grafico.desenha(a, { titulo: "Taxa de rolagem × deflexão", xlab: "deflexão do aileron (°)", ylab: "pb/2V",
        series: ["sobe_desce", "so_sobe"].map(n => ({ nome: NOMES[n], x: k.deflexao, y: k[n], cor: COR[n] })),
        refs: [{ tipo: "h", valor: res.criterios.pb2V_min, rotulo: "mínimo", cor: "#c85a5a" }] });
      const t = Array.from({ length: 61 }, (_, i) => i * 0.05), tau = res.tau_rolagem_s;
      const phi = o => t.map(x => (o.p_regime_graus_s || 0) * (x - tau * (1 - Math.exp(-x / tau))));
      Grafico.desenha(b, { titulo: "Inclinação × tempo (comando total)", xlab: "t (s)", ylab: "ângulo de rolagem (°)",
        series: Object.keys(res.opcoes).map(n => ({ nome: NOMES[n], x: t, y: phi(res.opcoes[n]), cor: COR[n] })),
        refs: [{ tipo: "h", valor: res.criterios.inclinacao, rotulo: `${fmt(res.criterios.inclinacao, 0)}°`, cor: "#999" },
               { tipo: "v", valor: res.criterios.t_inclinacao_max, rotulo: "tempo máx.", cor: "#c85a5a" }] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && Analise.nome() === "controle") desenha(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = ""; A.append(el("div", "Opções de aileron", "at"));
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    const o = res.opcoes, ks = Object.keys(o);
    const lin = (r, f) => `<tr><td>${r}</td>${ks.map(k => `<td>${f(o[k])}</td>`).join("")}</tr>`;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>grandeza</th>${ks.map(k => `<th>${NOMES[k]}</th>`).join("")}</tr>`
      + lin("Deflexão para cima / para baixo (°)", x => `${fmt(x.sobe, 0)} / ${fmt(x.desce, 0)}`)
      + lin("Momento de rolagem Cl do comando", x => fmt(x.Cl_comando, 4))
      + lin("pb/2V em regime", x => `${fmt(x.pb2V, 3)} ${x.ok_pb2V ? "(ok)" : "(FORA)"}`)
      + lin("Taxa de rolagem em regime (°/s)", x => x.p_regime_graus_s === null ? "—" : fmt(x.p_regime_graus_s, 0))
      + lin(`Tempo até ${fmt(res.criterios.inclinacao, 0)}° (s)`, x => x.tempo_inclinacao_s === null ? "—" : `${fmt(x.tempo_inclinacao_s, 2)} ${x.ok_tempo ? "(ok)" : "(FORA)"}`)
      + lin("Margem de estol local (° de α acima do equilíbrio)", x => !x.estol_local ? "—" : (x.estol_local.ilimitado ? "> " : "") + fmt(x.estol_local.delta_alpha_graus, 1))
      + lin("cl pedido / cl máx. do perfil, faixa crítica", x => !x.estol_local || x.estol_local.cl_demanda === null ? "—" : `${fmt(x.estol_local.cl_demanda, 2)} / ${fmt(x.estol_local.cl_max_perfil, 2)} (y = ${fmt(Math.abs(x.estol_local.y_critico), 2)} m)`)
      + lin("Guinada adversa Cn/Cl (negativo = adversa)", x => x.guinada_adversa === null ? "—" : fmt(x.guinada_adversa, 2))
      + lin("Charneira (fração da corda)", x => fmt(x.xc, 2));
    C.append(t);
    C.append(el("div", `Constante de tempo da rolagem τ = ${fmt(res.tau_rolagem_s, 2)} s (Ixx = ${fmt(res.Ixx, 2)} kg·m², ${res.origem_inercia}); Clp = ${fmt(res.Cl_p, 3)}. Ailerons: ` + res.ailerons.map(a => `${a.nome} (${a.elemento})`).join(", ") + ".", "nota"));
    const sem = res.estol_sem_comando;
    if (sem && sem.superficie) C.append(el("div", `Sem deflexão, o estol local só começa ${fmt(sem.delta_alpha_graus, 1)}° acima do equilíbrio (cl máx. 2D do perfil ${fmt(sem.cl_max_perfil, 2)}, em ${sem.superficie}). Margem = quanto α pode subir, com o aileron todo deflexionado, até o cl pedido pelo VLM igualar o cl máx. 2D do perfil na região do aileron para fora.`, "nota"));
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "VLM invíscido: a autoridade real é menor, e o aileron para baixo separa antes do que o modelo mostra (é o argumento do só sobe). Critérios são hipóteses de projeto, ajustáveis nas Configurações.", "nota"));
  }

  function mostra() { if (Analise.nome() !== "controle") return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }

  Analise.registra("controle", { pinta() { parametros(); $("graficos2").className = "graficos"; agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
