"use strict";

const PousoDin3 = (() => {
  const CAMPOS = [
    { g: "Pouso", k: "vel_descida", r: "Razão de descida (m/s)", d: "Velocidade vertical no toque. SAE costuma ter 0,5 a 1,5 m/s; um pouso duro passa de 2." },
    { k: "V_toque_rel", r: "Velocidade no toque (× Vs)", d: "Padrão 1,15 (a de aproximação)." },
    { k: "atitude_2p_extra", r: "Atitude a mais, 2 pontos (°)", d: "Quanto o nariz está acima da atitude de três pontos quando as principais tocam.", zero: true },
    { k: "sustentacao_toque_rel", r: "Sustentação no toque (L/W)", d: "1 = a asa ainda sustenta o peso no toque; menor que 1 = pouso com a asa já descarregada (mais duro).", zero: true },
    { g: "Pneu e perna", k: "k_pneu_principal", r: "Pneu principal (N/m por roda)", d: "Estimativa: meça num ensaio de queda ou de compressão. Manda no pico." },
    { k: "k_pneu_bequilha", r: "Pneu da bequilha (N/m)", d: "Estimativa, como o principal." },
    { k: "zeta", r: "Amortecimento (razão)", d: "Estimativa: 0,1 a 0,3 para pneu de borracha ou espuma.", zero: true },
    { k: "k_perna_principal", r: "Perna principal (N/m)", d: "Vazio = a da treliça (flecha da roda sob carga, em elementos finitos).", vazio: true },
    { k: "k_perna_bequilha", r: "Perna da bequilha (N/m)", d: "Vazio = a da treliça.", vazio: true },
    { k: "curso_trem_mm", r: "Batente do trem (mm)", d: "0 = sem batente. Acima do curso a rigidez sobe 10 vezes.", zero: true },
    { g: "Taxi", k: "altura_pista_mm", r: "Altura da pista (mm)", d: "Irregular: valor rms. Lombada e degrau: altura.", zero: true },
    { k: "comprimento_pista_m", r: "Comprimento da lombada (m)", d: "Da lombada ou da rampa do degrau." },
    { k: "V_taxi_rel", r: "Velocidade de rolagem (× Vs)", d: "Até onde a aeronave corre sobre a pista." },
    { k: "sustentacao_taxi_rel", r: "Sustentação no taxi (L/W)", d: "0 = conservador (asa sem sustentar).", zero: true },
    { g: "Modelo", k: "mu_rolamento", r: "Atrito de rolamento", d: "Estimativa: 0,03 a 0,1.", zero: true },
    { k: "CD", r: "CD da aeronave", d: "Estimativa, com trem e flap de pouso.", zero: true },
    { k: "Cm_q", r: "Amortecimento de arfagem (Cmq)", d: "Estimativa: −5 a −15.", neg: true },
  ];
  const PADRAO = { vel_descida: 1.0, V_toque_rel: 1.15, atitude_2p_extra: 6, sustentacao_toque_rel: 1.0, k_pneu_principal: 30000, k_pneu_bequilha: 30000, zeta: 0.15, k_perna_principal: null,
                   k_perna_bequilha: null, curso_trem_mm: 0, altura_pista_mm: 5, comprimento_pista_m: 0.3, V_taxi_rel: 0.8, sustentacao_taxi_rel: 0, mu_rolamento: 0.05, CD: 0.12, Cm_q: -8,
                   perfil_pista: "irregular", aplica_fe: true };
  const CHAVE = "aranduBIS.pouso_din";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a"];
  let v = Object.assign({}, PADRAO), res = null, tempo = null, seq = 0, caso = "pouso_2_pontos";
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "pouso_din";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const nome = c => c.replace(/_/g, " ");
  const pc = x => x >= 900 ? "> 900 %" : fmt(100 * x, 0) + " %";

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Pouso e taxi dinâmicos";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) {
        P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G);
        if (c.g === "Taxi") {
          const s = document.createElement("select"); [["irregular", "irregular (rms)"], ["lombada", "lombada"], ["degrau", "degrau"], ["plana", "plana"]].forEach(([k, n]) => s.add(new Option(n, k)));
          s.value = v.perfil_pista; s.onchange = () => { v.perfil_pista = s.value; guarda(); agenda(); };
          G.append(el("label", "Perfil da pista"), s);
        }
      }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null && c.vazio) { v[c.k] = null; guarda(); agenda(); return; }
        if (x === null || (!c.zero && !c.neg && !(x > 0)) || (c.zero && x < 0)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; guarda(); agenda();
      });
      i.title = c.d; if (c.vazio) i.placeholder = "da treliça"; G.append(l, i);
    });
    const G2 = document.createElement("div"); G2.className = "prop"; P.append(el("div", "Treliça (elementos finitos)", "grupo-par"), G2);
    const c = document.createElement("input"); c.type = "checkbox"; c.checked = !!v.aplica_fe; c.onchange = () => { v.aplica_fe = c.checked; guarda(); agenda(); };
    const lb = el("label", "Aplicar os picos na treliça"); lb.title = "Resolve a treliça com a reação de pico de cada caso (principal e bequilha) e mostra a margem das barras.";
    G2.append(lb, c);
    P.append(el("div", "Massa, Vs e CL máx.: os da vista Cargas. Fator de pouso de projeto, spin-up e solda: os da vista Trem de pouso. Tubos e materiais: modelo e Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 600); }

  function corpo() {
    const c = Cargas3.corpo(), t = Trem3.dados().v;
    const b = Object.assign({ esquema: esq, materiais: Asa3.materiais(), fator_pouso: t.fator_pouso, atrito_pouso: t.atrito_pouso, raio_inercia: t.raio_inercia, raio_solda: t.raio_solda },
      c, v, { fator_seguranca: c.fator_seguranca });
    Object.keys(b).forEach(k => { if (b[k] === null) delete b[k]; });
    return b;
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Simulando o pouso e o taxi (a primeira vez pode levar até 30 s: CL máximo da aeronave)…");
    try {
      const r = await chama("/api/pouso_dinamico", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { V.textContent = "—"; return; }
    const p2 = res.casos.pouso_2_pontos.pico, p3 = res.casos.pouso_3_pontos.pico, tx = res.casos.taxi.pico, pior = Math.max(p2.fator_total, p3.fator_total, tx.fator_total);
    V.classList.remove("neutro"); V.classList.add(pior <= res.fator_pouso_projeto ? "ok" : "ruim");
    const lim = [res.varredura.pouso_3_pontos.razao_limite, res.varredura.pouso_2_pontos.razao_limite].filter(x => x !== null);
    V.innerHTML = `<b>${pior <= res.fator_pouso_projeto ? "Pico dentro do fator de projeto" : "Pico acima do fator de projeto"}:</b> pouso 3 pontos ${fmt(p3.fator_total, 1)} × peso, 2 pontos ${fmt(p2.fator_total, 1)}, taxi ${fmt(tx.fator_total, 1)} (projeto ${fmt(res.fator_pouso_projeto, 1)}) `
      + `· razão de descida que consome o projeto: ${lim.length ? fmt(Math.min(...lim), 2) + " m/s" : "acima de " + fmt(res.varredura.razao[res.varredura.razao.length - 1], 1) + " m/s"}`
      + (res.fe ? ` · treliça com os picos: margem ${pc(res.fe.critico.margem)} (${nome(res.fe.critico.caso)}) contra ${pc(res.fe.margem_estatica)} nos fatores de projeto` : "");
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1, 2].map(() => el("div", "", "graf")); C.append(...g);
    const k = res.casos[caso], W = res.peso_N;
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: `Reação do solo, ${nome(caso)} (× peso)`, xlab: "t (s)", ylab: "N / W",
        series: [{ nome: "principais", x: k.t, y: k.N_principal.map(n => n / W), cor: COR[0] }, { nome: "bequilha", x: k.t, y: k.N_bequilha.map(n => n / W), cor: COR[1] }],
        refs: [{ tipo: "h", valor: res.fator_pouso_projeto, rotulo: "projeto", cor: "#c85a5a" }] });
      Grafico.desenha(g[1], { titulo: `Arfagem e compressão do trem, ${nome(caso)}`, xlab: "t (s)", ylab: "° / mm",
        series: [{ nome: "arfagem (°)", x: k.t, y: k.theta_graus, cor: COR[2] }, { nome: "trem principal (mm)", x: k.t, y: k.delta_principal_mm, cor: COR[0], tracejado: true }, { nome: "bequilha (mm)", x: k.t, y: k.delta_bequilha_mm, cor: COR[1], tracejado: true }] });
      const r = res.varredura;
      Grafico.desenha(g[2], { titulo: "Fator de carga total × razão de descida", xlab: "m/s", ylab: "pico / W",
        series: [{ nome: "3 pontos", x: r.razao, y: r.pouso_3_pontos.fator_total, cor: COR[0] }, { nome: "2 pontos", x: r.razao, y: r.pouso_2_pontos.fator_total, cor: COR[1] }],
        refs: [{ tipo: "h", valor: res.fator_pouso_projeto, rotulo: "projeto", cor: "#c85a5a" }, { tipo: "v", valor: v.vel_descida, rotulo: "agora", cor: "#999" }] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Picos por caso", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const s = document.createElement("select"); Object.keys(res.casos).forEach(k => s.add(new Option(nome(k), k))); s.value = caso;
    s.onchange = () => { caso = s.value; graficos(); }; const L = el("label", "Série no tempo: "); L.append(s); C.append(L);
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>caso</th><th>principais (N)</th><th>bequilha (N)</th><th>× peso (princ. / bequ. / total)</th><th>trem comprime (mm)</th><th>pneu (mm)</th><th>aceleração no CG (g)</th><th>arfagem (°)</th><th>quicadas</th></tr>"
      + Object.entries(res.casos).map(([k, c]) => { const p = c.pico;
        return `<tr><td>${nome(k)}<br><small>${c.descricao}</small></td><td>${fmt(p.N_principal, 0)}</td><td>${fmt(p.N_bequilha, 0)}</td><td>${fmt(p.fator_principal, 2)} / ${fmt(p.fator_bequilha, 2)} / ${fmt(p.fator_total, 2)}</td>`
          + `<td>${fmt(p.delta_principal_mm, 1)} / ${fmt(p.delta_bequilha_mm, 1)}</td><td>${fmt(p.pneu_principal_mm, 1)} / ${fmt(p.pneu_bequilha_mm, 1)}</td><td>${fmt(p.n_cg_max, 2)}</td>`
          + `<td>${fmt(p.theta_min_graus, 1)} a ${fmt(p.theta_max_graus, 1)}</td><td>${c.quicadas ? c.quicadas.n : "—"}</td></tr>`; }).join("");
    C.append(t);
    C.append(el("div", `Rigidez da perna: principal ${fmt(res.rigidez_perna_N_m.principal, 0)} N/m, bequilha ${fmt(res.rigidez_perna_N_m.bequilha, 0)} N/m (${res.rigidez_perna_N_m.origem}); pneu: ${fmt(res.rigidez_pneu_N_m.principal, 0)} / ${fmt(res.rigidez_pneu_N_m.bequilha, 0)} N/m. `
      + `Massa ${fmt(res.massa_kg, 2)} kg (${res.origem_massa}), Iyy ${fmt(res.Iyy, 3)} kg·m², velocidade no toque ${fmt(res.V_toque, 1)} m/s (Vs ${fmt(res.Vs, 1)}), atitude de 3 pontos ${fmt(res.atitude_3_pontos_graus, 2)}°.`, "nota"));
    if (res.fe) {
      const f = document.createElement("table");
      f.innerHTML = "<tr><th>caso (picos aplicados na treliça)</th><th>reação principais / bequilha (N)</th><th>margem mínima</th><th>barra crítica</th><th>modo</th><th>barra do eixo</th></tr>"
        + res.fe.casos.map(c => { const b = c.piores[0], Rp = Object.entries(c.rodas).filter(([n]) => n !== "bequilha").reduce((a, [, w]) => a + w.R, 0), Rn = c.rodas.bequilha ? c.rodas.bequilha.R : 0;
          return `<tr><td>${nome(c.caso)}</td><td>${fmt(Rp, 0)} / ${fmt(Rn, 0)}</td><td>${pc(c.margem)}${c.margem < 0 ? " (FORA)" : ""}</td><td>${b.elemento} ${b.tubo}</td><td>${nome(b.modo)}</td><td>${c.eixo_margem === null ? "—" : pc(c.eixo_margem)}</td></tr>`; }).join("");
      C.append(el("div", "Treliça com os picos dinâmicos", "grupo-par"), f);
    }
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
    C.append(el("div", "Corpo rígido em translação vertical e arfagem, com o pneu e a perna em série (mola e amortecedor), sustentação ainda atuando (cai com a velocidade e com o afundamento), atrito de rolamento freando e estabilidade estática da aeronave. "
      + "Sem massa de roda, sem efeito solo, sem movimento lateral nem pouso de uma roda só. Pontas e hélice não entram.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("pouso_din", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
