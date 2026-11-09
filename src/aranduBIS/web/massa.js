"use strict";

const Massa3 = (() => {
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#a278c8"];
  let res = null, tempo = null, seq = 0;
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "massa";
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Massa e CG";
    P.append(el("div", "MTOW e demais massas vêm do modelo e da vista Cargas. Para trocar a hipótese por massa real, declare bateria, motor, ESC e carga como peças pontuais no modelo (etapa 1).", "nota"));
  }
  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 300); }
  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Somando as massas do modelo…");
    try {
      const c = Cargas3.corpo();
      const r = await chama("/api/massa_estrutural", { esquema: esq, mtow_kg: c.massa_kg });
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; V.textContent = "—"; return; }
    const e = res.envelope, ok = !e || (e.x_dentro && e.z_dentro !== false); V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${fmt(res.total_kg, 2)} kg no modelo</b> (MTOW ${fmt(res.mtow_kg, 2)}): estrutura desenhada ${fmt(res.estrutural_kg, 2)} kg, massa não modelada ${fmt(res.nao_modelada_kg, 2)} kg · CG x = ${fmt(res.cg[0], 3)} m, z = ${fmt(res.cg[2], 3)} m`
      + (e ? ` · ${ok ? "dentro" : "FORA"} do envelope declarado (x ${fmt(e.x[0], 3)} a ${fmt(e.x[1], 3)})` : "");
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1].map(() => el("div", "", "graf")); C.append(...g);
    const S = res.sensibilidade;
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: "Massa por grupo (kg), sem a não modelada", xlab: "grupo (1 = maior)", ylab: "kg",
        series: [{ nome: "kg", x: res.grupos.filter(q => q.grupo !== "ponto").map((_, i) => i + 1), y: res.grupos.filter(q => q.grupo !== "ponto").map(q => q.massa_kg), cor: COR[0] }] });
      Grafico.desenha(g[1], { titulo: "CG em x × massa da estrutura desenhada", xlab: "fator sobre a estrutura", ylab: "x do CG (m)",
        series: [{ nome: "MTOW fixo", x: S.map(s => s.fator_estrutura), y: S.map(s => s.cg_x_mtow_fixo), cor: COR[0] }, { nome: "MTOW livre", x: S.map(s => s.fator_estrutura), y: S.map(s => s.cg_x_mtow_livre), cor: COR[1] }],
        refs: res.envelope ? [{ tipo: "h", valor: res.envelope.x[0], rotulo: "", cor: "#c85a5a" }, { tipo: "h", valor: res.envelope.x[1], rotulo: "", cor: "#c85a5a" }] : [] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Balanço de massa", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>grupo</th><th>massa (kg)</th><th>%</th><th>CG x / z (m)</th><th>maiores itens</th></tr>`
      + res.grupos.map(q => `<tr><td>${q.rotulo}</td><td>${fmt(q.massa_kg, 3)}</td><td>${fmt(100 * q.massa_kg / res.total_kg, 1)}</td><td>${fmt(q.cg[0], 3)} / ${fmt(q.cg[2], 3)}</td><td>${q.itens.slice(0, 3).map(i => i.nome + " " + fmt(1000 * i.massa, 0) + " g").join(", ")}</td></tr>`).join("");
    C.append(t);
    const ic = res.inercias_calculadas, id = res.inercias_declaradas, k = ["Ixx", "Iyy", "Izz", "Ixz"];
    const t2 = document.createElement("table");
    t2.innerHTML = `<tr><th>inércia (kg·m²)</th>${k.map(x => `<th>${x}</th>`).join("")}</tr><tr><td>calculada (massas pontuais)</td>${k.map(x => `<td>${fmt(ic[x], 3)}</td>`).join("")}</tr>`
      + `<tr><td>declarada no modelo</td>${k.map(x => `<td>${id[x] === undefined ? "—" : fmt(id[x], 3)}</td>`).join("")}</tr>`;
    C.append(t2);
    if (res.nao_modelada_sugerida_kg !== undefined) C.append(el("div", `Com o MTOW fixo em ${fmt(res.mtow_kg, 2)} kg, a massa não modelada (“${res.nao_modelada_nome}”) que fecha a conta é ${fmt(res.nao_modelada_sugerida_kg, 2)} kg (declarada: ${fmt(res.nao_modelada_kg, 2)}); CG resultante x = ${fmt(res.cg_mtow_fixo[0], 3)} m.`, "nota"));
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Cada item é massa pontual no próprio CG (sem inércia própria da peça): serve de conferência contra a inércia declarada, não a substitui.", "nota"));
  }

  function mostra() { if (!ativa()) return; parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("massa", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ res }) };
})();
