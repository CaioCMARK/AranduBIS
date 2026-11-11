"use strict";

const Resultados = (() => {
  let sel = 0;
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function refino() { const est = Otimiza.ultimoEstado(); return (est && est.refino) || null; }

  function lista() {
    const L = $("lista5"); L.innerHTML = "";
    const r = refino();
    if (!r || !r.length) { L.append(nota("Sem resultados ainda. Rode uma otimização na etapa 4.")); return; }
    r.forEach((p, i) => {
      const d = el("div", `${i + 1}. ${fmt(p.pontuacao, 1)}${p.viavel ? "" : " ⚠"}`, "el" + (i === sel ? " sel" : ""));
      d.onclick = () => { sel = i; lista(); pinta(); };
      L.append(d);
    });
  }

  function veredito() {
    const V = $("veredito5"); V.hidden = false;
    const r = refino();
    if (!r || !r.length) { V.className = "veredito neutro"; V.textContent = "Sem execução concluída."; return; }
    const p = r[sel];
    V.className = "veredito " + (p.viavel ? "ok" : "ruim");
    V.innerHTML = `<b>${p.viavel ? "Viável" : "Inviável"}</b> · pontuação <b>${fmt(p.pontuacao, 2)}</b>`
      + (p.falha ? ` · falhou em “${p.falha.etapa}”: ${p.falha.motivo}` : "");
  }

  function graficos() {
    const C = $("graficos5"); C.className = "graficos coluna";
    if (!C._a) { C.innerHTML = ""; C._a = el("div", "", "graf grande"); C.append(C._a); }
    const est = Otimiza.ultimoEstado(); const h = (est && est.historico) || [];
    const desenha = () => Grafico.desenha(C._a, {
      titulo: "Convergência (melhor por geração)", xlab: "geração", ylab: "pontuação",
      series: [{ nome: "melhor", x: h.map(r => r.geracao), y: h.map(r => r.melhor_objetivo), cor: "#4a86c5" },
        { nome: "média (viáveis)", x: h.map(r => r.geracao), y: h.map(r => r.media_objetivo), cor: "#6aa84f" }],
    });
    desenha();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (document.body.dataset.etapa === "5") desenha(); }); }
  }

  function tabelas(C, p) {
    C.append(el("div", "Variáveis", "grupo-par"));
    const t1 = document.createElement("table");
    t1.innerHTML = "<tr><th>variável</th><th>valor</th></tr>"
      + Object.entries(p.x).map(([k, val]) => `<tr><td>${k}</td><td>${fmt(val, 4)}</td></tr>`).join("");
    C.append(t1);

    C.append(el("div", "Restrições", "grupo-par"));
    const t2 = document.createElement("table");
    t2.innerHTML = "<tr><th>nome</th><th>valor</th><th>limite</th><th>tipo</th><th>folga</th><th>ok</th></tr>"
      + (p.restricoes || []).map(c => `<tr><td>${c.nome}</td><td>${c.valor == null ? "—" : fmt(c.valor, 3)}</td>`
        + `<td>${c.limite == null ? "—" : fmt(c.limite, 3)}</td><td>${c.tipo}</td><td>${c.folga == null ? "—" : fmt(c.folga, 3)}</td><td>${c.ok ? "✓" : "✕"}</td></tr>`).join("");
    C.append(t2);

    C.append(el("div", "Resultados", "grupo-par"));
    const t3 = document.createElement("table");
    const res = p.resultados || {};
    const chaves = Object.keys(res).filter(k => typeof res[k] !== "object");
    t3.innerHTML = "<tr><th>grandeza</th><th>valor</th></tr>"
      + chaves.map(k => `<tr><td>${k}</td><td>${typeof res[k] === "number" ? fmt(res[k], 4) : (res[k] ?? "—")}</td></tr>`).join("");
    C.append(t3);
  }

  function painel(p) {
    const P = $("par5"); P.innerHTML = "";
    if (!p) return;
    const b = el("button", "Abrir no editor"); b.style.margin = "6px 8px";
    b.onclick = async () => {
      try {
        const novo = await chama("/api/otimiza/materializa", { problema: Otimiza.ultimoProblema(), x: p.x });
        carrega_aeronave(novo, "otimizado"); Etapas.vai(1); msg("Projeto otimizado aberto na etapa 1.");
      } catch (e) { msg(e.message, true); }
    };
    P.append(b);
    const D = document.createElement("details"); D.innerHTML = "<summary>Avançado: JSON das variáveis (x)</summary>";
    const ta = document.createElement("textarea"); ta.value = JSON.stringify(p.x, null, 2); ta.readOnly = true;
    D.append(ta); P.append(D);
  }

  function pinta() {
    veredito(); graficos();
    const C = $("conteudo5"); C.innerHTML = "";
    const r = refino();
    if (!r || !r.length) { C.append(nota("Sem resultados ainda.")); painel(null); return; }
    tabelas(C, r[sel]); painel(r[sel]);
  }

  return {
    entra() {
      const r = refino();
      sel = r && r.length ? Math.min(sel, r.length - 1) : 0;
      lista(); pinta();
    },
  };
})();
