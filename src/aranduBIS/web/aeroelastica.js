"use strict";

const Aeroelastica3 = (() => {
  const CAMPOS = [
    { k: "V", r: "Velocidade (m/s)", d: "Vazio = a Vc da vista Cargas." , vazio: true },
    { k: "n", r: "Fator de carga n", d: "1 = voo reto nivelado; use o n de manobra para ver a carga limite." },
  ];
  const CHAVE = "aranduBIS.aeroelastica";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a"];
  let v = { V: null, n: 1 }, res = null, tempo = null, seq = 0, sel = null;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "aeroelastica";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Aeroelasticidade estática";
    const G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Ponto de voo", "grupo-par"), G);
    CAMPOS.forEach(c => {
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null && c.vazio) { v[c.k] = null; guarda(); agenda(); return; }
        if (x === null || !(x > 0)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; guarda(); agenda();
      });
      i.title = c.d; if (c.vazio) i.placeholder = "Vc de Cargas"; G.append(l, i);
    });
    if (res && res.asas) {
      const s = document.createElement("select"); res.asas.forEach(a => s.add(new Option(a.nome, a.nome)));
      sel = res.asas.some(a => a.nome === sel) ? sel : res.asas[0].nome; s.value = sel;
      s.onchange = () => { sel = s.value; graficos(); };
      const G2 = document.createElement("div"); G2.className = "prop"; G2.append(el("label", "Asa"), s);
      P.append(el("div", "Gráficos", "grupo-par"), G2);
    }
    P.append(el("div", "Rigidez e linha elástica: vista Torção. Massa, CG e densidade: vista Cargas.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  function corpo() {
    const c = Cargas3.corpo(), t = Torcao3.dados().v;
    return { esquema: esq, rho: c.rho, V: v.V > 0 ? v.V : c.Vc, n: v.n, massa_kg: c.massa_kg, materiais: Asa3.materiais(), x_ca_c: t.x_ca_c, cl_alpha_2d: t.cl_alpha_2d,
             calib_GJ: t.calib_GJ, calib_EI: t.calib_EI, ea_desloc_c: t.ea_desloc_c };
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Iterando o VLM com a asa deformada (cada iteração equilibra a aeronave de novo)…");
    try {
      const r = await chama("/api/aeroelastica", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  const asaSel = () => res.asas.find(a => a.nome === sel) || res.asas[0];

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; V.textContent = "—"; return; }
    if (!res.convergiu) { V.classList.add("ruim"); V.innerHTML = `<b>Sem solução estática:</b> ${res.motivo} Reforce a torção (feche a caixa, aumente GJ) ou mova a linha elástica para a frente do centro aerodinâmico.`; return; }
    const w = res.asas.map(a => a.torcao_ponta_graus), fl = Math.min(...res.asas.map(a => a.razao_fletor ?? 1));
    V.classList.add(Math.abs(res.variacao_alpha_graus) > 3 ? "neutro" : "ok");
    V.innerHTML = `<b>Convergiu em ${res.iteracoes.length} iterações:</b> torção na ponta ${fmt(Math.min(...w), 2)}° a ${fmt(Math.max(...w), 2)}° · alpha de trim ${fmt(res.variacao_alpha_graus >= 0 ? res.variacao_alpha_graus : res.variacao_alpha_graus, 2)}° a mais que a asa rígida · fletor na raiz ${fmt(100 * (fl - 1), 1)} % no pior caso`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res || !res.asas) return;
    const a = asaSel(), g = [0, 1].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: "Torção elástica por asa (+ = bordo de ataque para cima)", xlab: "y (m)", ylab: "graus",
        series: res.asas.map((x, i) => ({ nome: x.nome, x: x.y, y: x.theta_graus, cor: COR[i % COR.length] })) });
      const s = [{ nome: "asa rígida", x: a.y_faixa, y: a.L_rigida, cor: COR[0] }];
      if (a.L_flexivel) s.push({ nome: "asa flexível", x: a.y_faixa, y: a.L_flexivel, cor: COR[1], tracejado: true });
      Grafico.desenha(g[1], { titulo: `Sustentação por metro, ${a.nome}`, xlab: "y (m)", ylab: "N/m", series: s });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && res.asas && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Resumo", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table"), f = res.flexivel, r = res.rigida;
    t.innerHTML = `<tr><th></th><th>asa rígida</th><th>asa flexível</th></tr>`
      + `<tr><td>alpha de trim (°)</td><td>${fmt(r.alpha, 2)}</td><td>${f ? fmt(f.alpha, 2) : "—"}</td></tr>`
      + `<tr><td>deflexão do comando de arfagem (°)</td><td>${fmt(r.deflexao, 2)}</td><td>${f ? fmt(f.deflexao, 2) : "—"}</td></tr>`
      + `<tr><td>CL</td><td>${fmt(r.CL, 3)}</td><td>${f ? fmt(f.CL, 3) : "—"}</td></tr>`
      + (res.asas || []).map(a => `<tr><td>${a.nome}: fletor na raiz (N·m)</td><td>${fmt(a.fletor_raiz_rigida, 2)}</td><td>${a.fletor_raiz_flexivel === undefined ? "—" : fmt(a.fletor_raiz_flexivel, 2) + " (" + fmt(100 * (a.razao_fletor - 1), 1) + " %)"}</td></tr>`).join("");
    C.append(t);
    C.append(el("div", `Ponto: V ${fmt(res.V, 1)} m/s, n ${fmt(res.n, 2)}, massa ${fmt(res.massa_kg, 2)} kg (${res.origem_massa}), CL ${fmt(res.CL_alvo, 3)}. Iterações (mudança máxima da torção, em graus): `
      + res.iteracoes.map(h => fmt(h.mudanca_graus, 3)).join(" → "), "nota"));
    C.append(el("div", "Asa sem enflechamento: só a torção muda a incidência. Washout (ponta para baixo) pede mais alpha e leva carga para a raiz; washin faz o contrário e, se a linha elástica está atrás do centro aerodinâmico, pode divergir. "
      + "O peso da asa não entra no torque. A flexão da asa não refaz o diedro.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("aeroelastica", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
