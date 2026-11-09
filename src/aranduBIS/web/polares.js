"use strict";

const Polares = (() => {
  const CAMPOS = [
    { g: "Condição", k: "x_cg", r: "Posição do CG x (m)", d: "Vazio = soma das massas do modelo." },
    { k: "V", cfg: "analise.velocidade_voo", r: "Velocidade (m/s)", p: 12, d: "Define o Reynolds de cada faixa. Use a velocidade de estol esperada." },
    { k: "rho", cfg: "analise.rho", r: "Densidade do ar (kg/m³)", p: 1.1, d: "1330 m de altitude-densidade ≈ 1,06." },
    { g: "Corrida no solo", k: "alpha_solo", r: "Ângulo de ataque no solo (°)", d: "Vazio = pela reta que toca o chão nas rodas." },
    { k: "CdA", r: "Arrasto parasita CdA (m²)", d: "Vazio = estimado por componentes (fuselagem, rodas, tubos, motor, deriva). Preencha se você mediu." },
    { k: "altura", r: "Altura sobre o chão h (m)", d: "Do ponto de referência ao chão. Vazio = pelas rodas do modelo. Efeito solo: imagem do sistema de vórtices." },
    { g: "Banco de polares", k: "ncrit", cfg: "polares.ncrit_banco", r: "Ncrit do banco (4 ou 7)", p: 4, d: "4 = ar livre turbulento; 7 = ar mais limpo. Se o perfil só existe num deles, o outro é usado e avisado." },
  ];
  const CHAVE = "aranduBIS.polares";
  let v = {}, res = null, tempo = null, seq = 0;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = c.p === undefined ? null : c.p; });
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const PADROES = CAMPOS.concat([{ k: "com_solo", cfg: "analise.efeito_solo" }]);
  const aplicaPadroes = () => { Padroes.aplica(v, PADROES); v.ncrit = +v.ncrit; };
  aplicaPadroes();
  Padroes.aoMudar(() => { aplicaPadroes(); if (Analise.nome() === "polares") { parametros(); agenda(); } });
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "CL e CD da aeronave";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        const nulavel = ["x_cg", "alpha_solo", "CdA", "altura"].includes(c.k);
        if (x === null && nulavel) v[c.k] = null;
        else if (x === null || (c.k === "CdA" && !(x >= 0)) || (!nulavel && !(x > 0)) || (c.k === "ncrit" && x !== 4 && x !== 7)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        else v[c.k] = x;
        Padroes.toca(v, c.k); guarda(); agenda();
      });
      i.title = c.d;
      if (v[c.k] === null) i.placeholder = { x_cg: "do modelo", alpha_solo: "da geometria", CdA: "estimado", altura: "pelas rodas" }[c.k] || "";
      G.append(l, i);
    });
    const ls = el("label", "Efeito solo na corrida"); ls.title = "Desligado = voo livre: pessimista no arrasto induzido (a asa baixa de um biplano chega a perder 40 %).";
    const cs = document.createElement("input"); cs.type = "checkbox"; cs.checked = v.com_solo !== false;
    cs.onchange = () => { v.com_solo = cs.checked; Padroes.toca(v, "com_solo"); guarda(); agenda(); };
    P.append(ls, cs);
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 300); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando o CL máximo (teoria de faixas, alguns segundos)…");
    try {
      const r = await chama("/api/limites", { esquema: esq, x_cg: v.x_cg, V: v.V, rho: v.rho, ncrit: v.ncrit, alpha_solo: v.alpha_solo, CdA: v.CdA, altura: v.altura, com_solo: v.com_solo !== false });
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito";
    if (!res) { V.textContent = "—"; return; }
    const c = res.corrida, aprox = res.polares.some(p => p.origem === "aproximado");
    V.classList.add(aprox || !res.convergiu ? "ruim" : "ok");
    V.innerHTML = `<b>CL máximo da aeronave = ${fmt(res.CL_max, 2)}</b> em α = ${fmt(res.alpha_estol, 1)}°`
      + (res.inicio_estol_rel !== null ? ` · o estol começa a ${fmt(100 * res.inicio_estol_rel, 0)} % da semi-envergadura` : "")
      + ` · na corrida (α = ${fmt(c.alpha, 1)}°): CL ${fmt(c.CL, 2)}, CD ${fmt(c.CD, 3)}`
      + (aprox ? " · <b>há perfil APROXIMADO: confira abaixo</b>" : "");
  }

  function graficos() {
    const C = $("graficos2"); C.innerHTML = "";
    const a = el("div", "", "graf"), b = el("div", "", "graf"); C.append(a, b);
    if (!res) return;
    const c = res.curva;
    const desenha = () => {
      Grafico.desenha(a, { titulo: "CL da aeronave × α (com viscosidade)", xlab: "α (°)", ylab: "CL",
        series: [{ x: c.alpha, y: c.CL, cor: "#4a86c5" }], pontos: [{ x: res.alpha_estol, y: res.CL_max, rotulo: "CL máx" }] });
      Grafico.desenha(b, { titulo: "Polar da aeronave (com parasita)", xlab: "CD", ylab: "CL",
        series: [{ x: c.CD, y: c.CL, cor: "#d98a3d" }], pontos: [{ x: res.corrida.CD, y: res.corrida.CL, rotulo: "corrida" }] });
    };
    desenha();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (res && Analise.nome() === "polares") desenha(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = ""; A.append(el("div", "Perfis e corrida", "at"));
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>superfície</th><th>perfil do modelo</th><th>polar usada</th><th>origem</th></tr>"
      + res.polares.map(p => `<tr><td>${p.superficie}</td><td>${p.perfil}</td><td>${p.polar}</td><td class="${p.origem === "aproximado" ? "aviso-aprox" : ""}">${p.origem}</td></tr>`).join("");
    C.append(t);
    const k = res.corrida, q = document.createElement("table");
    const lin = (r, x, u) => `<tr><td>${r}</td><td>${x}</td><td>${u}</td></tr>`;
    q.innerHTML = "<tr><th>corrida (α = " + fmt(k.alpha, 2) + "°, " + k.origem + ")</th><th>valor</th><th></th></tr>"
      + lin("CL", fmt(k.CL, 3), "") + lin("CD induzido", fmt(k.CDi, 4), "") + lin("CD de perfil (polares)", fmt(k.CDp, 4), "")
      + (res.solo.usado ? lin("Efeito solo", "h = " + fmt(res.solo.h, 3) + " m (" + res.solo.origem + ")", "em voo livre: CL " + fmt(res.solo.livre.CL, 2) + ", CD " + fmt(res.solo.livre.CD, 3)) : "")
      + lin("CD parasita (estimado)", fmt(k.CD_parasita, 4), "") + lin("CD total", fmt(k.CD, 4), "ref. S = " + fmt(k.S_ref, 3) + " m²")
      + res.parasita.partes.map(p => lin("· " + p.nome, fmt(p.CD, 4), "CdA " + fmt(p.CdA, 4) + " m²")).join("");
    C.append(q);
    const b = el("button", "Usar CL máximo, CL e CD de corrida na Decolagem"); b.title = "Preenche CL máximo, CL e CD de corrida e a área S da aba Decolagem";
    b.onclick = () => {
      Decolagem.aplica("CL_max", +res.CL_max.toFixed(3), "polares"); Decolagem.aplica("CL_corrida", +k.CL.toFixed(3), "polares");
      Decolagem.aplica("CD_corrida", +k.CD.toFixed(4), "polares"); Decolagem.aplica("S", +k.S_ref.toFixed(4), "polares");
      const t = res.solo.tabela;
      Decolagem.aplicaSolo(res.solo.usado && t ? { h0: res.solo.h, h: t.map(x => x.h), K: t.map(x => +x.K.toFixed(5)) } : null);
      msg("CL máximo, CL e CD de corrida, área e o efeito solo levados para a Decolagem.");
    };
    C.append(b);
    res.parasita.notas.forEach(a => C.append(el("div", a, "nota")));
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
  }

  function mostra() { if (Analise.nome() !== "polares") return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }

  Analise.registra("polares", { pinta() { parametros(); $("graficos2").className = "graficos"; agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
