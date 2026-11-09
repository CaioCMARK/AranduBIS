"use strict";

const Etapas = (() => {
  const vistas = { 1: $("et1"), 2: $("et2") };
  let atual = 1;
  function vai(n) {
    if (!vistas[n] || n === atual) return;
    atual = n;
    Object.entries(vistas).forEach(([k, el]) => { el.hidden = +k !== n; });
    document.querySelectorAll(".etapas div[data-etapa]").forEach(d => d.classList.toggle("at", +d.dataset.etapa === n));
    document.body.dataset.etapa = n;
    if (n === 1) vista.desenha(); else Analise.entra();
  }
  document.querySelectorAll(".etapas div[data-etapa]").forEach(d => { d.onclick = () => vai(+d.dataset.etapa); });
  return { vai };
})();

const Analise = (() => {
  const ITENS = [["equilibrio", "Equilíbrio e estabilidade"], ["dinamica", "Dinâmica de voo (modos)"], ["polares", "CL e CD (polares)"], ["tracao", "Tração do motor e hélice"], ["decolagem", "Decolagem"], ["pontuacao", "Pontuação"]];
  const MODULOS = {};
  let ativo = "equilibrio";

  function lista() {
    const L = $("lista2"); L.innerHTML = "";
    ITENS.forEach(([k, n]) => {
      const d = Object.assign(document.createElement("div"), { className: "el" + (k === ativo ? " sel" : ""), textContent: n });
      d.onclick = () => { ativo = k; lista(); pinta(); };
      L.append(d);
    });
  }

  function pinta() { $("veredito").hidden = true; MODULOS[ativo].pinta(); }

  return {
    registra(nome, m) { MODULOS[nome] = m; },
    entra() { lista(); pinta(); },
    nome: () => ativo,
  };
})();

const Decolagem = (() => {
  const CAMPOS = [
    { g: "Massa", k: "massa_kg", r: "Massa de decolagem (kg)", p: 12, o: "você", d: "Aeronave pronta para decolar: vazia mais carga." },
    { g: "Aeronave", k: "S", r: "Área de asa S (m²)", p: 1.4, o: "geometria", d: "Soma das superfícies que sustentam. Botão ↻ lê da Geometria." },
    { k: "CL_max", r: "CL máximo", p: 1.6, o: "estimado", d: "Do perfil e da asa. Vem das polares quando a análise de polares existir." },
    { k: "CL_corrida", r: "CL na corrida", p: 0.5, o: "estimado", d: "Sustentação com a aeronave parada no chão (incidência de solo)." },
    { k: "CD_corrida", r: "CD na corrida", p: 0.08, o: "estimado", d: "Arrasto total na atitude de corrida." },
    { g: "Tração", k: "T0", r: "Tração estática (N)", p: 45, o: "você", d: "Tração com a aeronave parada." },
    { k: "V0", r: "Velocidade em que a tração zera (m/s)", p: 28, o: "você", d: "A tração cai em reta de T0 até zero nesta velocidade." },
    { g: "Pista e ar", k: "pista_m", cfg: "decolagem.pista_m", r: "Distância até o obstáculo (m)", p: 55, o: "regulamento", d: "Muda de ano para ano e de regulamento." },
    { k: "obstaculo_m", cfg: "decolagem.obstaculo_m", r: "Altura do obstáculo (m)", p: 0.9, o: "regulamento", d: "Quanto a aeronave precisa estar acima do chão nessa distância." },
    { k: "altitude_densidade_m", cfg: "decolagem.altitude_densidade_m", r: "Altitude-densidade (m)", p: 1330, o: "regulamento", d: "Define a densidade do ar (atmosfera padrão)." },
    { k: "mu", cfg: "decolagem.mu", r: "Atrito de rolagem μ", p: 0.062, o: "hipótese", d: "Depende da pista e das rodas. Meça o da sua." },
    { g: "Rotação", k: "d_alpha_rotacao", cfg: "decolagem.d_alpha_rotacao", r: "Giro até sair do solo (°)", p: 6, o: "hipótese", d: "Quanto a atitude muda da corrida até a saída." },
    { k: "taxa_rotacao", cfg: "decolagem.taxa_rotacao", r: "Taxa de rotação (°/s)", p: 20, o: "hipótese", d: "Velocidade com que o piloto levanta o nariz." },
    { k: "margem_rotacao", cfg: "decolagem.margem_rotacao", r: "Início da rotação (× V de estol)", p: 1.02, o: "hipótese", d: "Fração da velocidade de estol em que começa a puxar." },
  ];
  const CHAVE = "aranduBIS.decolagem";
  let v = {}, res = null, aba = "Resumo", tempo = null, seq = 0;

  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (typeof v[c.k] !== "number") v[c.k] = c.p; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (Analise.nome() === "decolagem") { parametros(); agenda(); } });
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };

  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Parâmetros da decolagem";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const caixa = document.createElement("div"); caixa.className = "campo-origem";
      const i = entrada("number", v[c.k], x => { if (x === null || !(x > 0 || c.k === "CL_corrida")) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; } v[c.k] = x; Padroes.toca(v, c.k); if (v.__o) delete v.__o[c.k]; if ((c.k === "T0" || c.k === "V0") && v.__tab) { delete v.__tab; if (v.__o) { delete v.__o.T0; delete v.__o.V0; } parametros(); } guarda(); agenda(); });
      i.title = c.d;
      const o = (v.__o || {})[c.k] || c.o;
      caixa.append(i, el("span", o, "origem o-" + o));
      if (c.k === "S") {
        const b = el("button", "↻"); b.title = "Ler a área da Geometria";
        b.onclick = lerGeometria; caixa.append(b);
      }
      if (c.k === "massa_kg") {
        const b = el("button", "máx."); b.title = "Usar a maior massa que passa o obstáculo";
        b.onclick = () => {
          if (!res || !res.massa_maxima.massa_kg) { msg("Ainda não há peso máximo calculado.", true); return; }
          v.massa_kg = +(res.massa_maxima.massa_kg).toFixed(2); guarda(); parametros(); agenda();
        };
        caixa.append(b);
      }
      G.append(l, caixa);
    });
    if (v.__solo) {
      const n = el("div", `Arrasto com efeito solo: CD = CD0 + K(h)·CL², h₀ = ${fmt(v.__solo.h0, 3)} m. O arrasto induzido cresce com o CL na rotação e na subida.`, "nota");
      const b = el("button", "tirar o efeito solo"); b.onclick = () => { v.__solo = null; guarda(); parametros(); agenda(); };
      P.append(n, b);
    }
  }

  async function lerGeometria() {
    if (!esq || !esq.elementos.length) { msg("Abra ou desenhe uma aeronave na etapa 1.", true); return; }
    try {
      const r = await chama("/api/aero/resumo", esq);
      if (!r.area_m2) { msg("Nenhuma asa com seções foi reconhecida como sustentação.", true); return; }
      v.S = +r.area_m2.toFixed(4); guarda(); parametros(); agenda();
      msg(`Área lida da geometria: ${fmt(r.area_m2, 3)} m² (${r.superficies.map(s => s.nome).join(", ")}).`);
    } catch (e) { msg(e.message, true); }
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 150); }

  async function calcula() {
    const meu = ++seq;
    const corpo = {
      massa_kg: v.massa_kg,
      aeronave: { S: v.S, CL_max: v.CL_max, CL_corrida: v.CL_corrida, CD_corrida: v.CD_corrida, solo: v.__solo || null },
      tracao: v.__tab ? { v: v.__tab.v, n: v.__tab.n } : { T0: v.T0, V0: v.V0 },
      condicoes: Object.fromEntries(["pista_m", "obstaculo_m", "altitude_densidade_m", "mu", "d_alpha_rotacao", "taxa_rotacao", "margem_rotacao"].map(k => [k, v[k]])),
    };
    try {
      const r = await chama("/api/decolagem", corpo);
      if (meu !== seq) return;
      res = r; msg("Pronto");
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito";
    if (!res) { V.textContent = "—"; return; }
    const mm = res.massa_maxima;
    if (res.transpos) {
      V.classList.add("ok");
      V.innerHTML = `<b>PASSA o obstáculo</b> com folga de ${fmt(res.folga_m, 2)} m · a ${fmt(res.massa_kg, 2)} kg`
        + (mm.massa_kg ? ` · peso máximo que passa: <b>${fmt(mm.massa_kg, 2)} kg</b> (sobram ${fmt(mm.massa_kg - res.massa_kg, 2)} kg)` : "");
    } else {
      V.classList.add("ruim");
      V.innerHTML = `<b>NÃO passa o obstáculo.</b> ${res.motivo}`
        + (mm.massa_kg ? ` Peso máximo que passa: <b>${fmt(mm.massa_kg, 2)} kg</b> (reduzir ${fmt(res.massa_kg - mm.massa_kg, 2)} kg).` : " Nem a menor massa testada passa: veja tração, CL máximo e pista.");
    }
  }

  function graficos() {
    const C = $("graficos2"); C.innerHTML = "";
    const a = el("div", "", "graf"), b = el("div", "", "graf"); C.append(a, b);
    if (!res) return;
    const s = res.serie, ob = res.obstaculo;
    const desenhaTudo = () => {
      Grafico.desenha(a, {
        titulo: "Altura até o obstáculo", xlab: "distância (m)", ylab: "altura (m)", yMin: 0,
        series: [{ nome: "altura", x: s.x, y: s.h, cor: "#4a86c5" }],
        refs: [{ tipo: "v", valor: ob.distancia_m, rotulo: `obstáculo a ${fmt(ob.distancia_m, 0)} m` }, { tipo: "h", valor: ob.altura_m, rotulo: `${fmt(ob.altura_m, 2)} m` }],
        pontos: res.decolou ? [{ x: res.distancia_rotacao_m, y: 0, rotulo: `sai do solo ${fmt(res.distancia_rotacao_m, 1)} m`, cor: "#6aa84f" }] : [],
      });
      const f = s.forcas;
      Grafico.desenha(b, {
        titulo: "Forças na corrida", xlab: "distância (m)", ylab: "força (N)", yMin: 0,
        series: [{ nome: "tração", x: s.x, y: f.T, cor: "#6aa84f" }, { nome: "arrasto", x: s.x, y: f.D, cor: "#c85a5a" },
          { nome: "atrito", x: s.x, y: f.atrito, cor: "#a278c8" }, { nome: "sustentação", x: s.x, y: f.L, cor: "#4a86c5" },
          { nome: "peso", x: s.x, y: f.W, cor: "#999", tracejado: true }],
        refs: [{ tipo: "v", valor: res.distancia_rotacao_m, rotulo: "saída do solo", cor: "#6aa84f" }].filter(r => Number.isFinite(r.valor)),
      });
    };
    desenhaTudo();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (res && Analise.nome() === "decolagem") graficos(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = "";
    ["Resumo", "Peso máximo"].forEach(n => {
      const d = el("div", n, n === aba ? "at" : ""); d.onclick = () => { aba = n; baixo(); }; A.append(d);
    });
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    if (aba === "Resumo") {
      const t = document.createElement("table");
      const lin = (r, val, un) => `<tr><td>${r}</td><td>${val}</td><td>${un}</td></tr>`;
      t.innerHTML = "<tr><th>grandeza</th><th>valor</th><th>un.</th></tr>"
        + lin("Massa", fmt(res.massa_kg, 2), "kg") + lin("Densidade do ar", fmt(res.rho, 4), "kg/m³")
        + lin("Distância até sair do solo", res.decolou ? fmt(res.distancia_rotacao_m, 1) : "—", "m")
        + lin("Velocidade de saída do solo", res.decolou ? fmt(res.velocidade_rotacao_ms, 1) : "—", "m/s")
        + lin("Altura no obstáculo", res.decolou ? fmt(res.altura_obstaculo_m, 2) : "—", "m")
        + lin("Folga sobre o obstáculo", res.decolou ? fmt(res.folga_m, 2) : "—", "m")
        + lin("Peso máximo que passa", res.massa_maxima.massa_kg ? fmt(res.massa_maxima.massa_kg, 2) : "—", "kg");
      C.append(t);
      C.append(el("div", res.numba ? "Cálculo compilado (numba)." : "Cálculo em Python puro: instale numba para ganhar velocidade.", "nota"));
    } else {
      const g = el("div", "", "graf grande"); C.append(g);
      const pts = res.varredura.filter(q => q.altura_m !== null);
      const nao = res.varredura.filter(q => q.altura_m === null);
      const desenha = () => Grafico.desenha(g, {
        titulo: "Altura no obstáculo × massa: onde a aeronave deixa de passar", xlab: "massa de decolagem (kg)", ylab: "altura no obstáculo (m)",
        yMin: 0,
        series: [{ x: pts.map(q => q.massa_kg), y: pts.map(q => q.altura_m), cor: "#4a86c5" }],
        refs: [{ tipo: "h", valor: res.obstaculo.altura_m, rotulo: "obstáculo" }].concat(res.massa_maxima.massa_kg ? [{ tipo: "v", valor: res.massa_maxima.massa_kg, rotulo: `máx. ${fmt(res.massa_maxima.massa_kg, 2)} kg`, cor: "#6aa84f" }] : []),
        pontos: res.decolou ? [{ x: res.massa_kg, y: res.altura_obstaculo_m, rotulo: "agora" }] : [],
      });
      desenha();
      if (nao.length) C.append(el("div", `Acima de ${fmt(Math.min(...nao.map(q => q.massa_kg)), 1)} kg a aeronave não sai do solo na pista.`, "nota"));
    }
  }

  function mostra() { veredito(); graficos(); baixo(); }

  Analise.registra("decolagem", {
    pinta() { parametros(); $("graficos2").className = "graficos"; agenda(); if (res) mostra(); },
  });
  return {
    dados: () => ({ v, res }),
    aplicaSolo(solo) { v.__solo = solo; guarda(); if (Analise.nome() === "decolagem") { parametros(); agenda(); } },
    aplicaTracao(vel, tr, rotulo) {
      v.__tab = { v: vel, n: tr, rotulo }; v.T0 = +tr[0].toFixed(2); v.V0 = +vel[vel.length - 1].toFixed(1);
      v.__o = Object.assign(v.__o || {}, { T0: "hélice", V0: "hélice" }); guarda();
      if (Analise.nome() === "decolagem") { parametros(); agenda(); }
    },
    aplica(k, x, origem) { v[k] = x; (v.__o = v.__o || {})[k] = origem; guarda(); if (Analise.nome() === "decolagem") { parametros(); agenda(); } },
  };
})();
