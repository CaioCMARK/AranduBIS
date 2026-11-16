"use strict";

const Flutter3 = (() => {
  // rótulo da rotação do aileron no modo: relativa à torção, ou "aileron sozinho" quando a asa quase não torce
  const rotAileron = (beta, alfaMax) => {
    const r = alfaMax > 0 ? Math.abs(beta) / alfaMax : Infinity;
    return r > 100 ? " · aileron girando sozinho (a asa quase não torce)" : ` · aileron ${fmt(beta / (alfaMax || 1), 1)} × a torção máx.`;
  };
  const CAMPOS = [
    { g: "Massa da asa", k: "massa_asa_kg", r: "Massa da semi-asa (kg)", d: "Vazio = soma dos itens estruturais do modelo (nervuras, longarina, tubos, chapeado). Informe a massa pesada, com aileron, servo e entelagem.", vazio: true },
    { k: "x_cg_c", r: "Centro de massa (x/c)", d: "Vazio = posição média dos itens de massa do modelo. Decide o flutter: quanto mais atrás da linha elástica, menor a velocidade.", vazio: true },
    { k: "r_giro_c", r: "Raio de giração (× corda)", d: "Em torno do centro de massa. Asa com caixa e nervuras: 0,25 a 0,30. Calibre com a frequência de torção do GVT." },
    { g: "Cálculo", k: "zeta_s", r: "Amortecimento estrutural", d: "0 = nenhum (conservador). Valores típicos de asa de balsa e carbono: 0,01 a 0,03.", zero: true },
    { k: "V_max_rel", r: "Velocidade máxima (× Vd)", d: "Até onde varrer a velocidade." },
  ];
  const CHAVE = "aranduBIS.flutter";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#8e6bbf", "#3aa6a6", "#b09040", "#777"];
  const CAMPOS_AIL = [
    { k: "massa_g", r: "Massa de um aileron (g)", d: "Pese o aileron com a dobradiça e o horn. Vazio = estimada pela fração de área da semi-asa.", vazio: true },
    { k: "x_cg_pct", r: "CG atrás da dobradiça (% da corda do aileron)", d: "33 % = cunha de balsa (centroide do triângulo). 0 = balanceado; negativo = contrapeso à frente da dobradiça.", neg: true },
    { k: "r_giro_pct", r: "Raio de giração na dobradiça (% da corda do aileron)", d: "41 % = cunha de balsa (raiz de 1/6)." },
    { k: "f_b", r: "Frequência do comando com a asa parada (Hz)", d: "0 = comando frouxo (folga no servo ou no link): o pior caso. Meça batendo no aileron com o servo ligado.", zero: true },
  ];
  let ail = { ativo: true, massa_g: null, x_cg_pct: 33.3, r_giro_pct: 40.8, f_b: 0 }, varr = null, t3d = null;
  let v = { massa_asa_kg: null, x_cg_c: null, r_giro_c: 0.28, zeta_s: 0, V_max_rel: 3 }, res = null, tempo = null, seq = 0, sel = null, modo = 0;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); Object.assign(ail, v.__ail || {}); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "flutter";
  const guarda = () => { try { v.__ail = ail; localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Flutter";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null && c.vazio) { v[c.k] = null; guarda(); agenda(); return; }
        if (x === null || (!c.zero && !(x > 0)) || (c.zero && x < 0)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; guarda(); agenda();
      });
      i.title = c.d; if (c.vazio) i.placeholder = "do modelo"; G.append(l, i);
    });
    P.append(el("div", "Aileron", "grupo-par"));
    const GA = document.createElement("div"); GA.className = "prop"; P.append(GA);
    const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = ail.ativo !== false;
    cb.onchange = () => { ail.ativo = cb.checked; varr = null; guarda(); parametros(); agenda(); };
    GA.append(el("label", "Aileron como grau de liberdade"), cb);
    if (ail.ativo !== false) CAMPOS_AIL.forEach(c => {
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", ail[c.k], x => {
        if (x === null && c.vazio) { ail[c.k] = null; varr = null; guarda(); agenda(); return; }
        if (x === null || (!c.zero && !c.neg && !(x > 0)) || (c.zero && x < 0)) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        ail[c.k] = x; varr = null; guarda(); agenda();
      });
      i.title = c.d; if (c.vazio) i.placeholder = "estimada"; GA.append(l, i);
    });
    if (res) {
      const s = document.createElement("select"); res.asas.forEach(a => s.add(new Option(a.nome, a.nome)));
      sel = res.asas.some(a => a.nome === sel) ? sel : res.asas[0].nome; s.value = sel;
      s.onchange = () => { sel = s.value; modo = asaSel().modo_flutter ?? 0; graficos(); baixo(); };
      const G2 = document.createElement("div"); G2.className = "prop"; G2.append(el("label", "Asa"), s);
      P.append(el("div", "Gráficos", "grupo-par"), G2);
    }
    if (typeof MassaAsa3 !== "undefined" && MassaAsa3.corpo()) P.append(el("div", "Massa, centro de massa e raio de giração vêm da vista Massa da asa (real): os três campos acima ficam sem efeito.", "nota"));
    P.append(el("div", "Rigidez, linha elástica, densidade e Vd: as das vistas Torção, Cargas e Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  function corpo() {
    const c = Cargas3.corpo(), t = Torcao3.dados().v;
    return { esquema: esq, rho: c.rho, Vd: c.Vd, materiais: Asa3.materiais(), margem_aeroelastica: t.margem_aeroelastica, x_ca_c: t.x_ca_c, cl_alpha_2d: t.cl_alpha_2d,
             calib_GJ: t.calib_GJ, calib_EI: t.calib_EI, ea_desloc_c: t.ea_desloc_c, massa_asa_kg: v.massa_asa_kg, x_cg_c: v.x_cg_c, r_giro_c: v.r_giro_c, zeta_s: v.zeta_s, V_max_rel: v.V_max_rel,
             massa_real: typeof MassaAsa3 !== "undefined" ? MassaAsa3.corpo() : null,
             aileron: ail.ativo === false ? null : { massa_kg: ail.massa_g ? ail.massa_g / 1000 : null, x_cg: ail.x_cg_pct / 100, r_giro: ail.r_giro_pct / 100, f_b: ail.f_b, zeta: v.zeta_s } };
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Calculando o flutter (modos de vibração e método p-k)…");
    try {
      const r = await chama("/api/flutter", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); modo = asaSel().modo_flutter ?? 0; }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  const asaSel = () => res.asas.find(a => a.nome === sel) || res.asas[0];

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; vazio(V); return; }
    if (res.VF === null) { V.classList.add("neutro"); V.innerHTML = `<b>Sem flutter</b> até ${fmt(res.asas[0].V[res.asas[0].V.length - 1], 1)} m/s com estes dados (massa, centro de massa e rigidez). Confirme no GVT.`; return; }
    const ok = res.margem_VF >= 0; V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${ok ? "Flutter acima do requisito" : "Flutter abaixo do requisito"}:</b> ${fmt(res.VF, 1)} m/s (${res.pior}) contra ${fmt(res.V_requerida, 1)} m/s exigidos · margem ${fmt(100 * res.margem_VF, 0)} %`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const a = asaSel(), g = [0, 1, 2].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      const refs = [{ tipo: "v", valor: a.V_requerida, rotulo: `${fmt(a.fator, 2)} Vd`, cor: "#c85a5a" }];
      if (a.VF !== null) refs.push({ tipo: "v", valor: a.VF, rotulo: "flutter", cor: "#999" });
      Grafico.desenha(g[0], { titulo: `Frequência × velocidade, ${a.nome}`, xlab: "V (m/s)", ylab: "Hz",
        series: a.freq_hz.map((f, i) => ({ nome: `modo ${i + 1} (${a.natureza[i]})`, x: a.V, y: f, cor: COR[i % COR.length] })), refs });
      Grafico.desenha(g[1], { titulo: "Amortecimento × velocidade (cruzar zero = flutter)", xlab: "V (m/s)", ylab: "ζ",
        series: a.amortecimento.map((z, i) => ({ nome: `modo ${i + 1}`, x: a.V, y: z, cor: COR[i % COR.length] })),
        refs: refs.concat([{ tipo: "h", valor: 0, rotulo: "", cor: "#999" }]), yMin: -0.3, yMax: 0.5 });
      const f = a.formas; if (modo >= f.h.length) modo = 0;
      const mx = Math.max(...f.h[modo].map(Math.abs)) || 1, ma = Math.max(...f.alfa[modo].map(Math.abs)) || 1;
      Grafico.desenha(g[2], { titulo: `Forma do modo ${modo + 1} (${fmt(a.f_vacuo_hz[modo], 1)} Hz, ${a.natureza[modo]})` + (f.beta ? rotAileron(f.beta[modo], Math.max(...f.alfa[modo].map(Math.abs))) : ""), xlab: "y (m)", ylab: "normalizado",
        series: [{ nome: "flexão (h)", x: f.y, y: f.h[modo].map(x => x / mx), cor: COR[0] }, { nome: "torção (α)", x: f.y, y: f.alfa[modo].map(x => x / ma), cor: COR[1] }] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Resumo", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>asa</th><th>massa semi-asa (kg)</th><th>centro de massa (x/c)</th><th>frequências em vácuo (Hz)</th><th>flutter (m/s)</th><th>frequência de flutter (Hz)</th><th>margem</th><th>divergência</th></tr>`
      + res.asas.map(a => `<tr><td>${a.nome}</td><td>${fmt(a.massa_semi_asa_kg, 3)}<br><small>${a.origem_massa}</small></td><td>${fmt(a.x_cg_c, 3)}<br><small>${a.origem_x_cg}</small></td>`
        + `<td>${a.f_vacuo_hz.slice(0, 6).map((f, i) => `${i + 1}: ${fmt(f, 1)} (${a.natureza[i]})`).join("<br>")}</td>`
        + `<td>${a.VF === null ? "—" : fmt(a.VF, 1)}</td><td>${a.f_flutter_hz === null ? "—" : fmt(a.f_flutter_hz, 1)}</td>`
        + `<td>${a.margem_VF === null ? "—" : fmt(100 * a.margem_VF, 0) + " %"}</td><td>${a.VD === null ? "—" : fmt(a.VD, 1) + " m/s"}</td></tr>`).join("");
    C.append(t);
    const s = document.createElement("select"); asaSel().f_vacuo_hz.forEach((f, i) => s.add(new Option(`modo ${i + 1} — ${fmt(f, 1)} Hz`, i))); s.value = modo;
    s.onchange = () => { modo = +s.value; graficos(); };
    const L = el("label", "Forma do modo: "); L.append(s); C.append(L);
    const aa = asaSel().aileron;
    if (aa) {
      C.append(el("div", `${aa.nome}: ${fmt(1000 * aa.massa_kg, 0)} g (${aa.origem_massa}), corda ${fmt(1000 * aa.corda_m[0], 0)} a ${fmt(1000 * aa.corda_m[1], 0)} mm, dobradiça a ${fmt(100 * aa.dobradica_xc, 0)} % da corda, CG ${fmt(100 * aa.x_cg, 0)} % atrás dela, comando ${aa.f_b ? fmt(aa.f_b, 1) + " Hz" : "frouxo"}.`, "nota"));
      const bv = el("button", varr === "rodando" ? "Varrendo…" : "Varrer rigidez do comando e balanceamento"); bv.disabled = varr === "rodando";
      bv.onclick = async () => { varr = "rodando"; baixo(); try { const r = await chama("/api/flutter", Object.assign(corpo(), { varre_aileron: true, asa_varredura: asaSel().nome })); varr = r.erro ? { erro: r.erro } : r.asas.find(x => x.nome === asaSel().nome).varredura; } catch (e) { varr = { erro: e.message }; } baixo(); };
      C.append(bv);
      if (varr && varr !== "rodando") {
        if (varr.erro) C.append(el("div", varr.erro, "nota erro"));
        else {
          const g1 = el("div", "", "graf"), g2 = el("div", "", "graf"); C.append(g1, g2);
          const teto = asaSel().V[asaSel().V.length - 1], vv = arr => arr.map(x => x === null ? teto : x);
          const ref = [{ tipo: "h", valor: asaSel().V_requerida, rotulo: "exigida", cor: "#c85a5a" }];
          Grafico.desenha(g1, { titulo: "Flutter × rigidez do comando", xlab: "frequência do aileron com a asa parada (Hz)", ylab: "V de flutter (m/s)",
            series: [{ nome: "V flutter (topo = não houve)", x: varr.f_b, y: vv(varr.VF_f_b), cor: COR[0] }], refs: ref });
          Grafico.desenha(g2, { titulo: "Flutter × balanceamento de massa", xlab: "CG atrás da dobradiça (fração da corda do aileron)", ylab: "V de flutter (m/s)",
            series: [{ nome: "V flutter (topo = não houve)", x: varr.x_cg, y: vv(varr.VF_x_cg), cor: COR[1] }], refs: ref });
        }
      }
    }
    tempo3d(C);
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
    C.append(el("div", "Teoria de faixas de Theodorsen (NACA TR 496, com o aileron como terceiro grau de liberdade) sobre uma semi-asa em balanço, sem efeito de envergadura finita, sem enflechamento e sem montantes entre as asas. "
      + "As frequências em vácuo são as que o ensaio de vibração mede: use-as para calibrar massa, centro de massa, raio de giração e o GJ da vista Torção antes de confiar na velocidade de flutter.", "nota"));
  }

  // conferencia no tempo: UVLM 3D acoplado aos mesmos modos (flutter_tempo.py)
  function tempo3d(C) {
    const a = asaSel();
    C.append(el("div", "Flutter no tempo com o UVLM 3D", "grupo-par"));
    const b = el("button", t3d === "rodando" ? "Marchando no tempo (alguns minutos)…" : `Conferir ${a.nome} no tempo (UVLM 3D)`);
    b.disabled = t3d === "rodando";
    b.title = "Marcha a asa elástica no UVLM em 4 velocidades em volta do flutter do p-k (mesmos modos, massas e rigidezes), tira o amortecimento de cada marcha pelo método do lápis de matrizes e acha onde ele cruza zero. Calcula também a divergência 3D (rigidez aerodinâmica estacionária do UVLM) e, se ela vem antes, marcha a 0,95 e 1,05 V_D para conferi-la no tempo. A aerodinâmica é 3D (perda de ponta, esteira de verdade); o p-k usa faixas 2D.";
    b.onclick = async () => {
      t3d = "rodando"; baixo();
      try { const r = await chama("/api/flutter/tempo", Object.assign(corpo(), { asa: a.nome, forcar: true })); t3d = r.erro ? { erro: r.erro } : r; }
      catch (e) { t3d = { erro: e.message }; }
      baixo();
    };
    C.append(b);
    if (!t3d || t3d === "rodando") return;
    if (t3d.erro) { C.append(el("div", t3d.erro, "nota erro")); return; }
    const r = t3d, ms = r.marchas, V0 = ms[0].V, V1 = ms[ms.length - 1].V;
    const TINTA = getComputedStyle(document.documentElement).getPropertyValue("--tinta").trim() || "#222";   // claro no tema escuro
    const txt = r.VF !== null
      ? `UVLM 3D: flutter a ${fmt(r.VF, 1)} m/s e ${fmt(r.f_flutter_hz, 1)} Hz`
      : `UVLM 3D: sem flutter entre ${fmt(V0, 1)} e ${fmt(V1, 1)} m/s (o amortecimento não cruzou zero)`;
    const pk = r.VF_pk !== null ? ` · p-k de faixas: ${fmt(r.VF_pk, 1)} m/s a ${fmt(r.f_flutter_pk_hz, 1)} Hz` : " · p-k de faixas: sem flutter até 3 Vd";
    C.append(el("div", `${txt}${pk} · ${r.nome}, ${r.simetria === "anti" ? "modos antissimétricos (com o aileron)" : "modos simétricos"}, ${fmt(r.tempo_s, 0)} s.`, "nota"));
    // divergencia: estatica 3D (rigidez aerodinamica do UVLM) e conferida pelo polo real das marchas
    const ds = r.VD_3d_simetrias || {}, VD = r.VD_3d;
    if (VD !== null && VD !== undefined) {
      const antes = r.VF === null || VD < r.VF, abaixo = VD < r.V_requerida;
      const conf = r.VD_marcha !== null && r.VD_marcha !== undefined ? ` Nas marchas (${r.simetria === "anti" ? "antissimétricas" : "simétricas"}), o polo real cruza zero a ${fmt(r.VD_marcha, 1)} m/s: confere a estática da mesma simetria no tempo.` : "";
      C.append(el("div", `Divergência 3D (UVLM, asa engastada): ${fmt(VD, 1)} m/s (simétrica ${ds.simetrico ? fmt(ds.simetrico, 1) : "—"}, antissimétrica ${ds.anti ? fmt(ds.anti, 1) : "—"})`
        + ` · faixas 2D: ${r.VD_faixas ? fmt(r.VD_faixas, 1) + " m/s" : "sem divergência"}.${conf}`
        + (antes ? " Ela vem antes do flutter: é o limite aeroelástico desta asa." : "")
        + (abaixo ? ` Abaixo da exigida (${fmt(r.V_requerida, 1)} m/s): leve a linha elástica para a frente ou aumente o GJ.` : ""), abaixo ? "nota erro" : "nota"));
    }
    const g1 = el("div", "", "graf"), g2 = el("div", "", "graf"), g3 = el("div", "", "graf"); C.append(g1, g3, g2);
    const xa = Math.min(0.8 * V0, r.V_requerida), xb = 1.1 * V1, dentro = r.pk.V.map(x => x >= xa && x <= xb);
    const ser = r.pk.amortecimento.map((z, i) => ({ nome: `p-k modo ${i + 1}`, x: r.pk.V.filter((_, j) => dentro[j]),
      y: z.filter((_, j) => dentro[j]).map(q => Math.max(-0.2, Math.min(0.3, q))), cor: COR[i % COR.length], tracejado: true }));
    ser.push({ nome: "UVLM no tempo (modo menos amortecido)", x: ms.map(m => m.V), y: ms.map(m => m.zeta), cor: TINTA, marcador: "ponto", raio: 4.5, opacidade: 1 });
    const refs = [{ tipo: "h", valor: 0, rotulo: "", cor: "#999" }, { tipo: "v", valor: r.V_requerida, rotulo: "exigida", cor: "#c85a5a" }];
    if (r.VF !== null) refs.push({ tipo: "v", valor: r.VF, rotulo: "flutter (UVLM)", cor: TINTA });
    Grafico.desenha(g1, { titulo: "Amortecimento: p-k de faixas (tracejado) × UVLM 3D no tempo (pontos)", xlab: "V (m/s)", ylab: "ζ", series: ser, refs,
      yMin: -0.2, yMax: 0.3 });
    const pr = ms.filter(m => m.divergencia);
    if (pr.length) {
      const sr = pr.map(m => m.divergencia.s_real), lim = Math.max(1, ...sr.map(Math.abs));
      const rr = [{ tipo: "h", valor: 0, rotulo: "", cor: "#999" }, { tipo: "v", valor: r.V_requerida, rotulo: "exigida", cor: "#c85a5a" }];
      const Vs3 = ds[r.simetria === "anti" ? "anti" : "simetrico"];
      if (Vs3) rr.push({ tipo: "v", valor: Vs3, rotulo: "V_D estática 3D", cor: TINTA });
      if (r.VD_faixas && r.VD_faixas < 1.1 * V1) rr.push({ tipo: "v", valor: r.VD_faixas, rotulo: "V_D faixas", cor: "#888" });
      Grafico.desenha(g3, { titulo: "Divergência no tempo: polo real dominante de cada marcha (Re s > 0: cresce sem oscilar)", xlab: "V (m/s)", ylab: "Re s (1/s)",
        series: [{ nome: "UVLM no tempo", x: pr.map(m => m.V), y: sr, cor: TINTA, marcador: "ponto", raio: 4.5, opacidade: 1 }], refs: rr, yMin: -lim, yMax: lim });
    }
    const cresce = m => (m.zeta !== null && m.zeta <= 0) || (m.divergencia && m.divergencia.diverge);
    // para desenhar, a primeira marcha em que o crescimento aparece na janela (e^1,5 = 4,5 vezes)
    const visivel = m => (m.zeta !== null && m.zeta <= 0) || (m.divergencia && m.divergencia.s_real * m.t[m.t.length - 1] > 1.5);
    const baixa = ms.filter(m => !cresce(m)).pop() || ms[0], alta = ms.find(visivel) || ms.find(cresce) || ms[ms.length - 1];
    Grafico.desenha(g2, { titulo: "Torção na ponta no tempo (relativa ao começo: o modelo é linear, a amplitude é arbitrária)", xlab: "t (s)", ylab: "α ponta / α inicial",
      series: [{ nome: `V = ${fmt(baixa.V, 1)} m/s (ζ = ${fmt(baixa.zeta, 3)})`, x: baixa.t, y: baixa.alfa_ponta_rel, cor: COR[0] }]
        .concat(alta !== baixa ? [{ nome: `V = ${fmt(alta.V, 1)} m/s (${alta.divergencia && alta.divergencia.diverge ? "diverge: Re s = " + fmt(alta.divergencia.s_real, 2) + "/s" : "ζ = " + fmt(alta.zeta, 3)})`, x: alta.t, y: alta.alfa_ponta_rel, cor: COR[3] }] : []) });
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>V (m/s)</th><th>modo menos amortecido</th><th>ζ</th><th>polo real Re s (1/s)</th><th>outros modos identificados</th><th>iterações por passo (máx.)</th></tr>`
      + ms.map(m => `<tr><td>${fmt(m.V, 1)}</td><td>${m.f_hz === null ? "—" : fmt(m.f_hz, 1) + " Hz"}</td><td>${m.zeta === null ? "—" : fmt(m.zeta, 4)}</td>`
        + `<td>${m.divergencia ? fmt(m.divergencia.s_real, 2) + (m.divergencia.diverge ? " (diverge)" : "") : "—"}</td>`
        + `<td>${m.modos.map(x => fmt(x.f_hz, 1) + " Hz: " + fmt(x.zeta, 3)).join(" · ")}</td><td>${m.iter_max}</td></tr>`).join("");
    C.append(t);
    const d = r.discretizacao;
    C.append(el("div", `Malha: ${d.paineis} painéis (${d.superficies.join(", ")}), ${d.n_chord} na corda (${d.motivo_n_chord}); passo = o menor entre c/(${d.passos_por_corda}V) e 1/24 do período do flutter; ${fmt(d.n_ciclos, 0)} ciclos por marcha.`, "nota"));
    C.append(el("div", "Verificação (tests/test_flutter_tempo.py): sem ar, os modos vibram nas frequências naturais com ζ = 0 (Newmark de aceleração média); numa asa de alongamento 40 sobre molas (seção típica de Hodges & Pierce) o flutter no tempo fica a 4 % do p-k de Theodorsen. Asa de Goland: p-k 137 m/s (literatura 137,2); UVLM 3D ~162 m/s a 67,5 rad/s, 2 % abaixo do UVLM do SHARP (165 m/s). Divergência: o polo real das marchas cruza zero na V_D da rigidez aerodinâmica estacionária do mesmo UVLM (0,2 % na asa voadora canard); alongamento 40: V_D 3D = 1,06 × faixas.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("flutter", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  function aplica(patch) { Object.assign(v, patch); guarda(); if (ativa()) { parametros(); agenda(); } }
  return { dados: () => ({ v, res }), aplica };
})();
