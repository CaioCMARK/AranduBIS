"use strict";

const Polares = (() => {
  const CAMPOS = [
    { g: "Condição", k: "x_cg", r: "Posição do CG x (m)", d: "Vazio = soma das massas do modelo." },
    { k: "V", r: "Velocidade (m/s)", p: 12, d: "Define o Reynolds de cada faixa. Use a velocidade de estol esperada." },
    { k: "rho", r: "Densidade do ar (kg/m³)", p: 1.1, d: "1330 m de altitude-densidade ≈ 1,06." },
    { g: "Banco de polares", k: "ncrit", r: "Ncrit do banco (4 ou 7)", p: 4, d: "4 = ar livre turbulento; 7 = ar mais limpo. Se o perfil só existe num deles, o outro é usado e avisado." },
  ];
  const CHAVE = "aranduBIS.polares";
  let v = {}, res = null, tempo = null, seq = 0;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = c.p === undefined ? null : c.p; });
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Polares e CL máximo";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null && c.k === "x_cg") v.x_cg = null;
        else if (x === null || (c.k !== "x_cg" && !(x > 0)) || (c.k === "ncrit" && x !== 4 && x !== 7)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        else v[c.k] = x;
        guarda(); agenda();
      });
      i.title = c.d; if (c.k === "x_cg" && v.x_cg === null) i.placeholder = "do modelo";
      G.append(l, i);
    });
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 300); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando o CL máximo (teoria de faixas, alguns segundos)…");
    try {
      const r = await chama("/api/limites", { esquema: esq, x_cg: v.x_cg, V: v.V, rho: v.rho, ncrit: v.ncrit });
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito";
    if (!res) { V.textContent = "—"; return; }
    const aprox = res.polares.some(p => p.origem === "aproximado");
    V.classList.add(aprox || !res.convergiu ? "ruim" : "ok");
    V.innerHTML = `<b>CL máximo da aeronave = ${fmt(res.CL_max, 2)}</b> em α = ${fmt(res.alpha_estol, 1)}°`
      + (res.inicio_estol_rel !== null ? ` · o estol começa a ${fmt(100 * res.inicio_estol_rel, 0)} % da semi-envergadura` : "")
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
      Grafico.desenha(b, { titulo: "Polar da aeronave", xlab: "CD", ylab: "CL",
        series: [{ x: c.CD, y: c.CL, cor: "#d98a3d" }], pontos: [] });
    };
    desenha();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (res && Analise.nome() === "polares") desenha(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = ""; A.append(el("div", "Perfis usados", "at"));
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>superfície</th><th>perfil do modelo</th><th>polar usada</th><th>origem</th></tr>"
      + res.polares.map(p => `<tr><td>${p.superficie}</td><td>${p.perfil}</td><td>${p.polar}</td><td class="${p.origem === "aproximado" ? "aviso-aprox" : ""}">${p.origem}</td></tr>`).join("");
    C.append(t);
    const b = el("button", "Usar este CL máximo na Decolagem"); b.title = "Preenche o CL máximo da aba Decolagem com este valor";
    b.onclick = () => { Decolagem.aplica("CL_max", +res.CL_max.toFixed(3), "polares"); msg(`CL máximo ${fmt(res.CL_max, 2)} levado para a Decolagem.`); };
    C.append(b);
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
  }

  function mostra() { if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }

  Analise.registra("polares", { pinta() { parametros(); $("graficos2").className = "graficos"; agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
