"use strict";

const Dinamica = (() => {
  const CAMPOS = [
    { g: "Condição", k: "V", cfg: "analise.velocidade_cruzeiro", r: "Velocidade (m/s)", p: 15, d: "Velocidade da condição de voo equilibrado." },
    { k: "rho", cfg: "analise.rho", r: "Densidade do ar (kg/m³)", p: 1.1, d: "" },
    { k: "x_cg", r: "Posição do CG x (m)", d: "Vazio = soma das massas do modelo.", nulo: true },
    { g: "Massa e inércias", k: "massa_kg", cfg: "dinamica.massa_kg", r: "Massa total (kg)", d: "0 ou vazio = soma das massas declaradas no modelo.", nulo: true },
    { k: "modo", cfg: "dinamica.modo_inercia", r: "Origem das inércias", d: "auto, modelo ou raio de giro.", escolha: ["auto", "modelo", "raio"] },
    { k: "rx", cfg: "dinamica.raio_x", r: "Raio de giro Rx/b", d: "Fração da envergadura (estimativa por raio de giro)." },
    { k: "ry", cfg: "dinamica.raio_y", r: "Raio de giro Ry/L", d: "Fração do comprimento." },
    { k: "rz", cfg: "dinamica.raio_z", r: "Raio de giro Rz/média(b, L)", d: "Fração da média entre envergadura e comprimento." },
    { k: "Ixx", r: "Ixx (kg·m²)", d: "Inércia em rolagem. Vazio = do modelo.", nulo: true },
    { k: "Iyy", r: "Iyy (kg·m²)", d: "Inércia em arfagem.", nulo: true },
    { k: "Izz", r: "Izz (kg·m²)", d: "Inércia em guinada.", nulo: true },
    { k: "Ixz", r: "Ixz (kg·m²)", d: "Produto de inércia; vazio com as outras três preenchidas = 0.", nulo: true },
  ];
  const CHAVE = "aranduBIS.dinamica";
  let v = {}, res = null, tempo = null, seq = 0;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = c.p === undefined ? null : c.p; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (Analise.nome() === "dinamica") { parametros(); agenda(); } });
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function seletor(ops, atual, aoMudar) {
    const s = document.createElement("select");
    ops.forEach(o => { const e = el("option", o); e.value = o; s.append(e); });
    s.value = atual; s.onchange = () => aoMudar(s.value);
    return s;
  }

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Dinâmica de voo";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = c.escolha ? seletor(c.escolha, v[c.k], x => { v[c.k] = x; Padroes.toca(v, c.k); guarda(); agenda(); }) : entrada("number", v[c.k], x => {
        if (x === null && c.nulo) v[c.k] = null;
        else if (x === null || (c.k !== "x_cg" && c.k !== "Ixz" && !(x > 0))) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        else v[c.k] = x;
        Padroes.toca(v, c.k); guarda(); agenda();
      });
      i.title = c.d; if (!c.escolha && c.nulo && v[c.k] === null) i.placeholder = "do modelo";
      G.append(l, i);
    });
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 300); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    const I = {}; ["Ixx", "Iyy", "Izz", "Ixz"].forEach(k => { if (v[k] !== null) I[k] = v[k]; });
    try {
      const r = await chama("/api/dinamica", { esquema: esq, V: v.V, rho: v.rho, x_cg: v.x_cg, massa_kg: v.massa_kg > 0 ? v.massa_kg : null, modo_inercia: v.modo, raios: { rx: v.rx, ry: v.ry, rz: v.rz }, inercias: Object.keys(I).length ? I : null });
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito";
    if (!res) { V.textContent = "—"; return; }
    const ruins = res.avaliacao.filter(a => !a.ok), m = res.modos, dr = m.dutch_roll, e = m.espiral;
    V.classList.add(ruins.length ? "ruim" : "ok");
    V.innerHTML = (ruins.length ? `<b>${ruins.length} critério(s) fora do limite:</b> ${ruins.map(a => a.nome).join("; ")}` : "<b>Todos os critérios dentro do limite de referência</b>")
      + ` · a ${fmt(res.V, 0)} m/s, CL = ${fmt(res.CL, 2)}, α = ${fmt(res.alpha, 1)}°`
      + (dr ? ` · dutch roll ζ = ${fmt(dr.zeta, 2)}` : "") + (e ? ` · espiral ${e.estavel ? "estável" : "instável, dobra em " + fmt(e.t_metade_ou_dobro, 1) + " s"}` : "");
  }

  function graficos() {
    const C = $("graficos2"); C.innerHTML = "";
    if (!res) return;
    const a = el("div", "", "graf"), b = el("div", "", "graf"); C.append(a, b);
    const desenha = () => {
      const r = res.resposta;
      Grafico.desenha(a, { titulo: "Derrapagem de 5° (lateral)", xlab: "t (s)", ylab: "graus",
        series: [{ nome: "β", x: r.t, y: r.beta, cor: "#4a86c5" }, { nome: "φ (rolagem)", x: r.t, y: r.phi, cor: "#d98a3d" }],
        refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#999" }] });
      Grafico.desenha(b, { titulo: "Perturbação de 5° em α (curto período)", xlab: "t (s)", ylab: "graus",
        series: [{ nome: "α", x: r.t, y: r.alpha, cor: "#6aa84f" }, { nome: "q (°/s)", x: r.t, y: r.q, cor: "#a278c8" }],
        refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#999" }] });
    };
    desenha();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (res && Analise.nome() === "dinamica") desenha(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = ""; A.append(el("div", "Critérios e modos", "at"));
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>critério</th><th>valor</th><th>limite</th><th></th></tr>"
      + res.avaliacao.map(a => `<tr title="${a.texto}"><td>${a.nome}</td><td>${isFinite(a.valor) ? fmt(a.valor, 3) : "estável"}</td><td>${a.limite}</td><td class="${a.ok ? "" : "aviso-aprox"}">${a.ok ? "ok" : "FORA"}</td></tr>`).join("");
    C.append(t);
    const m = res.modos, q = document.createElement("table");
    const lin = (r, x, u) => `<tr><td>${r}</td><td>${x}</td><td>${u}</td></tr>`;
    q.innerHTML = "<tr><th>modo</th><th>valor</th><th></th></tr>"
      + (m.curto_periodo.oscilatorio ? lin("Curto período", `ω = ${fmt(m.curto_periodo.omega, 2)} rad/s, ζ = ${fmt(m.curto_periodo.zeta, 2)}`, `período ${fmt(m.curto_periodo.periodo, 2)} s`) : lin("Curto período", "superamortecido", m.curto_periodo.raizes.map(x => fmt(x, 2)).join(" e ") + " 1/s"))
      + lin("Fugoide (aprox.)", `ω = ${fmt(m.fugoide.omega, 2)} rad/s, ζ = ${fmt(m.fugoide.zeta, 2)}`, "Lanchester")
      + (m.rolagem ? lin("Rolagem", `τ = ${fmt(m.rolagem.tau, 3)} s`, `λ = ${fmt(m.rolagem.lambda, 2)} 1/s`) : "")
      + (m.espiral ? lin("Espiral", m.espiral.estavel ? "estável" : "instável", `${m.espiral.estavel ? "metade" : "dobra"} em ${fmt(m.espiral.t_metade_ou_dobro, 1)} s`) : "")
      + (m.dutch_roll ? lin("Dutch roll", `ω = ${fmt(m.dutch_roll.omega, 2)} rad/s, ζ = ${fmt(m.dutch_roll.zeta, 2)}`, `período ${fmt(m.dutch_roll.periodo, 2)} s`) : lin("Dutch roll", "sem par complexo", ""))
      + lin("Massa", `${fmt(res.m, 2)} kg (${res.origem_massa})`, "") + lin("Ixx, Iyy, Izz, Ixz", ["Ixx", "Iyy", "Izz", "Ixz"].map(k => fmt(res.inercias[k], 3)).join(", "), `kg·m² (${res.origem_inercia})`);
    C.append(q);
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Derivadas do potencial (sem separação); CY_p, CY_r e efeitos de α-ponto desprezados; limites de referência MIL-F-8785C para aeronaves leves, não norma do AeroDesign.", "nota"));
  }

  function mostra() { if (Analise.nome() !== "dinamica") return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }

  Analise.registra("dinamica", { pinta() { parametros(); $("graficos2").className = "graficos"; agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
