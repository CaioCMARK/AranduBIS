"use strict";

// Hélice pelo BEMT (forma típica APC Thin Electric) comparada com o catálogo do fabricante, e o sopro dela na asa (VLM).
const Helice2 = (() => {
  const CHAVE = "aranduBIS.helice";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#8e6bbf"];
  let v = { helice: "22x10E", perfil: "CLARK_Y_AIRFOIL@n7", rpm: 4500, V: 12, alpha: 4, sentido: 1, rho: null };
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  let cat = null, res = null, tempo = null, seq = 0, sup = null;
  const PERFIS = ["CLARK_Y_AIRFOIL@n7", "E420@n4", "EPPLER_334_AIRFOIL@n7", "MH_80_12_72@n7", "NACA6412@n7", "RAF_6_AIRFOIL_12_LE_rad_0_012@n7", "S1223@n7"];
  const ativa = () => Analise.nome() === "helice";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function seletor(rot, k, opcoes, dica) {
    const l = el("label", rot); l.title = dica;
    const s = document.createElement("select"); opcoes.forEach(([a, b]) => s.add(new Option(b, a))); s.value = v[k];
    s.onchange = () => { v[k] = s.value; guarda(); agenda(); };
    return [l, s];
  }

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Hélice (BEMT)";
    const G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Hélice", "grupo-par"), G);
    if (!cat) { G.append(el("label", "Carregando o catálogo…")); return; }
    G.append(...seletor("Hélice APC", "helice", cat.helices.map(h => [h.nome, h.nome]), "Diâmetro e passo do catálogo; a forma da pá é a média das APC Thin Electric."));
    G.append(...seletor("Perfil da pá", "perfil", PERFIS.map(p => [p, p.replace(/@n\d/, "").replace(/_AIRFOIL/, "")]), "Polares do banco (XFOIL), estendidas além do estol por Viterna. As APC E usam perfil fino arqueado, perto do Clark Y."));
    G.append(...seletor("Sentido de giro", "sentido", [["1", "horário visto de trás"], ["-1", "anti-horário visto de trás"]], "Define o lado da rotação do sopro (a asa de um lado ganha ângulo, a do outro perde)."));
    const G2 = document.createElement("div"); G2.className = "prop"; P.append(el("div", "Ponto de operação", "grupo-par"), G2);
    [["rpm", "Rotação (rpm)", "Rotação do motor no ponto."], ["V", "Velocidade (m/s)", "0 = estático."], ["alpha", "Ângulo de ataque da aeronave (°)", "Para o sopro na asa (VLM)."], ["rho", "Densidade (kg/m³)", "Vazio = a de Configurações."]].forEach(([k, r, d]) => {
      const l = el("label", r); l.title = d;
      const i = entrada("number", v[k], x => { if (x === null && k === "rho") { v.rho = null; guarda(); agenda(); return; }
        if (x === null || (k !== "alpha" && k !== "V" && !(x > 0)) || (k === "V" && x < 0)) { msg("Valor inválido em “" + r + "”.", true); parametros(); return; }
        v[k] = x; guarda(); agenda(); });
      i.title = d; if (k === "rho") i.placeholder = "Configurações"; G2.append(l, i);
    });
    if (res && res.sopro) {
      const s = document.createElement("select"); res.sopro.superficies.forEach(q => s.add(new Option(q.nome, q.nome)));
      sup = res.sopro.superficies.some(q => q.nome === sup) ? sup : (res.sopro.afetadas[0] || res.sopro.superficies[0].nome); s.value = sup;
      s.onchange = () => { sup = s.value; graficos(); };
      const G3 = document.createElement("div"); G3.className = "prop"; G3.append(el("label", "Carga na envergadura de"), s);
      P.append(el("div", "Gráficos", "grupo-par"), G3);
    }
    const n = el("div", "A hélice fica na posição do elemento “helice” do modelo, com o eixo para trás (+x). O sopro entra no VLM como velocidade local nos pontos de controle. ", "nota");
    const a = Object.assign(document.createElement("a"), { href: "#", textContent: "Teoria e boas práticas" }); a.onclick = ev => { ev.preventDefault(); Manual.abre("helice"); };
    n.append(a); P.append(n);
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 300); }

  async function calcula() {
    const meu = ++seq;
    msg("BEMT e sopro…");
    try {
      const r = await chama("/api/helice", Object.assign({}, v, { esquema: esq, rho: v.rho > 0 ? v.rho : (+Padroes.get("analise.rho") || 1.1), sentido: +v.sentido }));
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { vazio(V); return; }
    const p = res.ponto, s = res.sopro;
    V.innerHTML = `<b>${res.helice} a ${fmt(res.rpm, 0)} rpm e ${fmt(res.V, 1)} m/s:</b> T = ${fmt(p.T, 1)} N · P = ${fmt(p.P, 0)} W · η = ${fmt(p.eta, 3)}`
      + (p.eta_ideal ? ` (disco ideal ${fmt(p.eta_ideal, 3)})` : "")
      + (s ? ` · sopro: CL ${fmt(s.CL_sem, 3)} → ${fmt(s.CL_com, 3)} (${fmt(100 * (s.CL_com / s.CL_sem - 1), 1)} %)` : "");
  }

  function graficos() {
    const C = $("graficos2"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1, 2, 3, 4].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      const c = res.curva, ok = (a, i) => c.CT_apc[i] > -0.02;
      Grafico.desenha(g[0], { titulo: `CT e CP × J a ${fmt(res.rpm, 0)} rpm (traço: APC, cálculo do fabricante)`, xlab: "J = V/nD", ylab: "coeficiente",
        series: [{ nome: "CT BEMT", x: c.J, y: c.CT, cor: COR[0] }, { nome: "CT APC", x: c.J, y: c.CT_apc, cor: COR[0], tracejado: true },
                 { nome: "CP BEMT", x: c.J, y: c.CP, cor: COR[1] }, { nome: "CP APC", x: c.J, y: c.CP_apc, cor: COR[1], tracejado: true }],
        pontos: [{ x: res.ponto.J, y: res.ponto.CT, rotulo: "ponto" }] });
      Grafico.desenha(g[1], { titulo: "Eficiência × J", xlab: "J", ylab: "η", yMin: 0, yMax: 1,
        series: [{ nome: "BEMT", x: c.J, y: c.eta.map(e => Math.max(0, e)), cor: COR[2] }, { nome: "APC", x: c.J, y: c.eta_apc.map(e => Math.max(0, e)), cor: COR[2], tracejado: true }] });
      const p = res.ponto;
      Grafico.desenha(g[2], { titulo: "Na pá: tração por metro (a ponta perde carga pela perda de Prandtl)", xlab: "r/R", ylab: "dT/dr (N/m)",
        series: [{ nome: "dT/dr", x: p.r_R, y: p.dT, cor: COR[0] }] });
      Grafico.desenha(g[4], { titulo: "Na pá: ângulo de ataque e velocidades induzidas no disco", xlab: "r/R", ylab: "α (°) · v (m/s)",
        series: [{ nome: "α (°)", x: p.r_R, y: p.alpha, cor: COR[3] }, { nome: "v axial (m/s)", x: p.r_R, y: p.v_a, cor: COR[4] },
                 { nome: "v tangencial (m/s)", x: p.r_R, y: p.v_t, cor: COR[2], tracejado: true }] });
      if (res.sopro) {
        const q = res.sopro.superficies.find(x => x.nome === sup) || res.sopro.superficies[0];
        Grafico.desenha(g[3], { titulo: `cl na envergadura de ${q.nome}: com e sem o sopro`, xlab: "y (m)", ylab: "cl",
          series: [{ nome: "sem hélice", x: q.y, y: q.cl_sem, cor: "#999" }, { nome: "com o sopro", x: q.y, y: q.cl_com, cor: COR[1] }] });
      } else g[3].textContent = "Abra uma aeronave para ver o sopro na asa.";
    };
    desenha();
    if (!C._obsh) { C._obsh = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = ""; A.append(el("div", "Resumo", "at"));
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    const p = res.ponto, s = res.sopro, t = document.createElement("table");
    t.innerHTML = `<tr><th>D (m)</th><th>passo (pol)</th><th>J</th><th>CT</th><th>CP</th><th>T (N)</th><th>Q (N·m)</th><th>P (W)</th><th>η</th><th>η disco ideal</th></tr>`
      + `<tr><td>${fmt(res.D, 3)}</td><td>${fmt(res.passo_pol, 1)}</td><td>${fmt(p.J, 3)}</td><td>${fmt(p.CT, 4)}</td><td>${fmt(p.CP, 4)}</td><td>${fmt(p.T, 2)}</td><td>${fmt(p.Q, 3)}</td><td>${fmt(p.P, 0)}</td><td>${fmt(p.eta, 3)}</td><td>${p.eta_ideal ? fmt(p.eta_ideal, 3) : "—"}</td></tr>`;
    C.append(t);
    if (s) {
      const t2 = document.createElement("table");
      t2.innerHTML = `<tr><th></th><th>sem hélice</th><th>com o sopro</th><th>variação</th></tr>`
        + [["CL", "CL_sem", "CL_com", 3], ["CDi", "CDi_sem", "CDi_com", 4], ["Cm", "Cm_sem", "Cm_com", 3]].map(([n, a, b, d]) =>
          `<tr><td>${n}</td><td>${fmt(s[a], d)}</td><td>${fmt(s[b], d)}</td><td>${fmt(s[b] - s[a], d)}</td></tr>`).join("")
        + `<tr><td>superfícies no sopro</td><td colspan="3">${s.afetadas.join(", ") || "nenhuma"} · velocidade induzida máxima ${fmt(s.v_max, 1)} m/s</td></tr>`;
      C.append(el("div", `Sopro no VLM (α = ${fmt(res.V ? v.alpha : 0, 1)}°)`, "grupo-par"), t2);
    }
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Verificação (tests/test_bemt.py): a análise BEMT da hélice de mínima perda de Adkins & Liebeck devolve a tração, a potência e a eficiência do projeto a 1 % (com e sem arrasto do perfil); parada, o BEMT converge e respeita o piso do disco atuador; o sopro conserva a massa anel por anel e dobra a velocidade axial longe do disco.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Analise.registra("helice", {
    async pinta() {
      $("graficos2").className = "graficos";
      if (!cat) { parametros(); try { cat = await chama("/api/propulsao", { lista: true }); } catch (e) { msg(e.message, true); return; } }
      parametros(); agenda(); if (res) mostra();
    },
  });
  return { dados: () => ({ v, res }) };
})();
