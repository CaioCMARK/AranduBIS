"use strict";

const Equilibrio = (() => {
  const CAMPOS = [
    { g: "Condição de voo", k: "x_cg", r: "Posição do CG x (m)", o: "modelo", d: "Medida do bordo de ataque da raiz da asa, positiva para trás. Vazio = soma das massas do modelo." },
    { k: "V", r: "Velocidade (m/s)", p: 15, o: "você", d: "Velocidade de cruzeiro para o cálculo das cargas." },
    { k: "rho", r: "Densidade do ar (kg/m³)", p: 1.1, o: "você", d: "Padrão a 1330 m de altitude-densidade ≈ 1,06." },
    { k: "CL_alvo", r: "CL a equilibrar", p: 0.8, o: "você", d: "O CL em que a aeronave deve voar equilibrada. Vazio = só estabilidade." },
  ];
  const CHAVE = "aranduBIS.equilibrio";
  let v = {}, res = null, tempo = null, seq = 0;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = c.p === undefined ? null : c.p; });
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Condição de voo";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const caixa = document.createElement("div"); caixa.className = "campo-origem";
      const vazio = c.k === "x_cg" || c.k === "CL_alvo";
      const i = entrada("number", v[c.k], x => {
        if (x === null && vazio) v[c.k] = null;
        else if (x === null || (c.k !== "x_cg" && !(x > 0))) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        else v[c.k] = x;
        guarda(); agenda();
      });
      i.title = c.d; if (vazio && v[c.k] === null) i.placeholder = c.k === "x_cg" ? "do modelo" : "só estabilidade";
      caixa.append(i, el("span", c.k === "x_cg" && v.x_cg === null && res ? res.cg_origem : (v[c.k] === null ? "" : c.o), "origem o-" + c.o));
      G.append(l, caixa);
    });
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 200); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    try {
      const r = await chama("/api/equilibrio", { esquema: esq, x_cg: v.x_cg, V: v.V, rho: v.rho, CL_alvo: v.CL_alvo });
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito";
    if (!res) { V.textContent = "—"; return; }
    const me = 100 * res.margem_estatica, t = res.trim;
    const cmd = res.comando ? `comando de arfagem: <b>${res.comando}</b>` : "sem superfície de comando (asa voadora): equilíbrio só pelo ângulo de ataque";
    if (res.estavel && me >= 5) V.classList.add("ok"); else V.classList.add("ruim");
    V.innerHTML = (res.estavel ? `<b>ESTÁVEL em arfagem</b> · margem estática ${fmt(me, 1)} % da corda média` : `<b>INSTÁVEL em arfagem</b> · margem ${fmt(me, 1)} %`)
      + ` · ponto neutro em x = ${fmt(res.ponto_neutro, 3)} m · ${cmd}`
      + (t ? ` · equilibra em α = ${fmt(t.alpha, 2)}°${res.comando ? `, comando ${fmt(t.deflexao, 2)}°` : ""}${t.atinge_CL_alvo ? "" : " (não chega ao CL pedido)"}` : "");
  }

  function graficos() {
    const C = $("graficos2"); C.innerHTML = "";
    const a = el("div", "", "graf"), b = el("div", "", "graf"); C.append(a, b);
    if (!res) return;
    const s = res.varredura, t = res.trim;
    const desenha = () => {
      Grafico.desenha(a, {
        titulo: "Sustentação × ângulo de ataque", xlab: "α (°)", ylab: "CL",
        series: [{ x: s.alpha, y: s.CL, cor: "#4a86c5" }],
        pontos: t ? [{ x: t.alpha, y: t.CL, rotulo: "equilíbrio" }] : [],
      });
      Grafico.desenha(b, {
        titulo: "Momento de arfagem × ângulo de ataque", xlab: "α (°)", ylab: "Cm em torno do CG",
        series: [{ x: s.alpha, y: s.Cm, cor: "#d98a3d" }], refs: [{ tipo: "h", valor: 0, rotulo: "equilíbrio", cor: "#999" }],
        pontos: t && !res.comando ? [{ x: t.alpha, y: 0, rotulo: "α de equilíbrio" }] : [],
      });
    };
    desenha();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (res && Analise.nome() === "equilibrio") desenha(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = ""; A.append(el("div", "Resumo", "at"));
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    const lin = (r, val, un) => `<tr><td>${r}</td><td>${val}</td><td>${un}</td></tr>`;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>grandeza</th><th>valor</th><th>un.</th></tr>"
      + lin("Área de referência", fmt(res.S_ref, 3), "m²") + lin("Corda média de referência", fmt(res.c_ref, 3), "m")
      + lin("CG usado", fmt(res.x_cg, 3) + " (" + res.cg_origem + ")", "m") + lin("Ponto neutro", fmt(res.ponto_neutro, 3), "m")
      + lin("Margem estática", fmt(100 * res.margem_estatica, 1), "% da corda média")
      + lin("CL_α", fmt(res.CL_alpha, 3), "1/rad") + lin("Cm_α", fmt(res.Cm_alpha, 3), "1/rad")
      + (res.trim ? lin("α de equilíbrio", fmt(res.trim.alpha, 2), "°") + lin("CL de equilíbrio", fmt(res.trim.CL, 3), "") + lin("CD induzido", fmt(res.trim.CDi, 4), "") : "")
      + res.superficies.map(s => lin("Superfície " + s.nome, s.vertical ? "vertical" : (s.referencia ? "asa (referência)" : "estabilizadora/comando"), "")).join("");
    C.append(t);
    (res.avisos || []).forEach(a => C.append(el("div", a, "nota")));
  }

  function mostra() { if (Analise.nome() !== "equilibrio") return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }

  Analise.registra("equilibrio", {
    pinta() { parametros(); $("graficos2").className = "graficos"; agenda(); if (res) mostra(); },
  });
  return { dados: () => ({ v, res }) };
})();
