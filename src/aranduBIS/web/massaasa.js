"use strict";

const MassaAsa3 = (() => {
  const CHAVE = "aranduBIS.massa_asa";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#8e6bbf", "#3aa6a6", "#b09040", "#777"];
  let v = { usar: false, adicionais: [], medidas: {} }, res = null, tempo = null, seq = 0, sel = null;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "massa_asa";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const asas = () => (esq && esq.elementos || []).filter(e => e.tipo === "asa" && e.estrutura);
  const asaSel = () => { const n = asas().map(e => e.nome); sel = n.includes(sel) ? sel : n[0]; return sel; };

  function corpo() { return v.usar ? { usar: true, adicionais: v.adicionais.filter(a => a.massa_kg || a.gramatura_g_m2), medidas: v.medidas } : null; }

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Massa da asa (real)";
    const G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Uso", "grupo-par"), G);
    const c = document.createElement("input"); c.type = "checkbox"; c.checked = !!v.usar;
    c.onchange = () => { v.usar = c.checked; guarda(); agenda(); };
    const l = el("label", "Usar nas vistas Flutter e Calibração"); l.title = "Ligado: a vibração usa esta distribuição por estação em vez de massa total proporcional à corda (a massa, o CG e o raio de giração da vista Flutter deixam de valer).";
    G.append(l, c);
    const G2 = document.createElement("div"); G2.className = "prop";
    const s = document.createElement("select"); asas().forEach(e => s.add(new Option(e.nome, e.nome))); s.value = asaSel() || "";
    s.onchange = () => { sel = s.value; guarda(); mostra(true); };
    G2.append(el("label", "Asa"), s); P.append(el("div", "Medida da semi-asa (balança)", "grupo-par"), G2);
    const m = v.medidas[asaSel()] = v.medidas[asaSel()] || {};
    const G3 = document.createElement("div"); G3.className = "prop"; P.append(G3);
    [["massa_medida_kg", "Massa pesada (kg)", "Semi-asa montada como voa: entelada, com aileron, servo e fios."],
     ["x_cg_medido_c", "CG na corda (x/c)", "Ponto de equilíbrio da semi-asa pendurada, medido do bordo de ataque, em fração da corda local."],
     ["y_cg_medido_m", "CG na envergadura (m)", "Distância do ponto de equilíbrio à raiz."]].forEach(([k, r, d]) => {
      const lb = el("label", r); lb.title = d;
      const i = entrada("number", m[k], x => { if (x === null) delete m[k]; else m[k] = x; guarda(); agenda(); }); i.title = d; i.placeholder = "não medido";
      G3.append(lb, i);
    });
    P.append(el("div", "A massa pesada fecha a conta: o que faltar entre o somado e a balança vira um fator na estrutura do modelo (as adicionais você dá). Quanto mais perto de 1, mais confiável a distribuição.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(true); return; }
    msg("Distribuindo a massa por estação…");
    try {
      const t = Torcao3.dados().v;
      const r = await chama("/api/massa_asa", { esquema: esq, materiais: Asa3.materiais(), x_ca_c: t.x_ca_c, cl_alpha_2d: t.cl_alpha_2d, calib_GJ: t.calib_GJ, calib_EI: t.calib_EI, ea_desloc_c: t.ea_desloc_c,
        massa_real: { usar: true, adicionais: v.adicionais.filter(a => a.massa_kg || a.gramatura_g_m2), medidas: v.medidas } });
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  const atual = () => res && res.asas && (res.asas.find(a => a.nome === asaSel()) || res.asas[0]);

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    const a = atual();
    if (!a) { V.textContent = "Adicione as massas reais (servo, aileron, entelagem) e a massa pesada da semi-asa."; return; }
    const val = a.validacao && a.validacao.massa;
    V.classList.remove("neutro"); V.classList.add(!val || Math.abs(val.erro_pct) < 8 ? "ok" : "ruim");
    const f0 = a.f_hz_hipotese_antiga[0], f1 = a.f_hz[0];
    V.innerHTML = `<b>${a.nome}:</b> semi-asa ${fmt(a.massa_kg, 3)} kg (estrutura do modelo ${fmt(a.massa_estrutura_calculada_kg, 3)} + adicionais ${fmt(a.massa_adicionais_kg, 3)}${a.escala_estrutura !== 1 ? ` · estrutura × ${fmt(a.escala_estrutura, 2)} para fechar a balança` : ""})`
      + ` · CG em x/c ${fmt(a.x_cg_c, 3)}, y ${fmt(a.y_cg_m, 3)} m · 1ª frequência ${fmt(f1, 2)} Hz contra ${fmt(f0, 2)} Hz da hipótese de massa proporcional à corda`
      + (val ? ` · somado do modelo ${fmt(val.erro_pct, 1)} % da balança` : "");
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    const a = atual(); if (!a) return;
    const g = [0, 1, 2].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: "Massa por metro de envergadura (semi-asa)", xlab: "y (m)", ylab: "kg/m",
        series: [{ nome: "total", x: a.y, y: a.m_lin, cor: "#222" }].concat(a.categorias.map((c, i) => ({ nome: c.nome, x: a.y, y: c.m_lin, cor: COR[i % COR.length], tracejado: true }))) });
      Grafico.desenha(g[1], { titulo: "Centro de massa na corda local", xlab: "y (m)", ylab: "x/c", series: [{ nome: "centro de massa", x: a.y, y: a.x_cg_c_local, cor: COR[0] }],
        refs: a.validacao && a.validacao.x_cg_c ? [{ tipo: "h", valor: a.validacao.x_cg_c.medido, rotulo: "medido", cor: "#c85a5a" }] : [] });
      Grafico.desenha(g[2], { titulo: "Raio de giração em torno do CG (× corda)", xlab: "y (m)", ylab: "r/c", series: [{ nome: "r/c", x: a.y, y: a.r_cg_c, cor: COR[1] }] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (atual() && ativa()) desenha(); }); }
  }

  function linhaAdicional(a, i, T) {
    const tr = document.createElement("tr");
    const s = document.createElement("select"); s.add(new Option("todas", "")); asas().forEach(e => s.add(new Option(e.nome, e.nome))); s.value = a.asa || "";
    s.onchange = () => { a.asa = s.value; guarda(); agenda(); };
    const td0 = document.createElement("td"); td0.append(s); tr.append(td0);
    [["nome", "text", "120px"], ["massa_kg", "number", "70px"], ["gramatura_g_m2", "number", "70px"], ["y_m", "number", "60px"], ["y_fim_m", "number", "60px"], ["x_c", "number", "55px"]].forEach(([k, t, w]) => {
      const td = document.createElement("td");
      td.append(entrada(t, a[k], x => { if (x === null || x === "") delete a[k]; else a[k] = x; guarda(); agenda(); }, { style: "width:" + w }));
      tr.append(td);
    });
    const td = document.createElement("td"), b = el("button", "✕"); b.onclick = () => { v.adicionais.splice(i, 1); guarda(); agenda(); mostra(true); }; td.append(b); tr.append(td);
    T.append(tr);
  }

  function modelo() {
    const e = asas().find(x => x.nome === asaSel()) || asas()[0];
    const ponta = e ? Math.max(...e.secoes.map(s => Math.abs(s.y))) : 1, c = e && (e.controles || [])[0];
    return { e, ponta, c };
  }

  function adicionais(C) {
    C.append(el("div", "Massas adicionais por semi-asa (as que o modelo não desenha)", "grupo-par"));
    const T = document.createElement("table");
    T.innerHTML = "<tr><th>asa</th><th>nome</th><th>massa (kg)</th><th>ou filme (g/m²)</th><th>y (m)</th><th>até y (m)</th><th>x/c</th><th></th></tr>";
    v.adicionais.forEach((a, i) => linhaAdicional(a, i, T));
    C.append(T);
    const B = document.createElement("div"); B.className = "prop";
    const novo = (a) => { v.adicionais.push(Object.assign({ asa: asaSel() }, a)); guarda(); agenda(); mostra(true); };
    const bt = (t, f) => { const b = el("button", t); b.onclick = f; B.append(b); };
    bt("+ servo", () => { const m = modelo(); novo({ nome: "servo", massa_kg: 0.02, y_m: m.c ? 0.5 * (m.c.y[0] + Math.min(m.c.y[1], m.ponta)) : 0.5 * m.ponta, x_c: 0.55 }); });
    bt("+ aileron", () => { const m = modelo(); novo({ nome: "aileron", massa_kg: 0.03, y_m: m.c ? m.c.y[0] : 0.6 * m.ponta, y_fim_m: m.c ? Math.min(m.c.y[1], m.ponta) : m.ponta, x_c: 0.82 }); });
    bt("+ entelagem (filme)", () => novo({ nome: "entelagem", gramatura_g_m2: 25, y_m: 0 }));
    bt("+ lastro / cola / outra", () => { const m = modelo(); novo({ nome: "lastro", massa_kg: 0.01, y_m: m.ponta, x_c: 0.1 }); });
    C.append(B);
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Massas", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    adicionais(C);
    const a = atual();
    if (a) {
      const t = document.createElement("table");
      t.innerHTML = "<tr><th>componente</th><th>massa (kg)</th><th>y do CG (m)</th></tr>"
        + a.categorias.map(c => `<tr><td>${c.nome}</td><td>${fmt(c.massa_kg, 4)}</td><td>${fmt(c.y_cg_m, 3)}</td></tr>`).join("");
      C.append(el("div", "Composição da semi-asa " + a.nome, "grupo-par"), t);
      const f = document.createElement("table");
      f.innerHTML = "<tr><th>modo</th><th>com esta massa (Hz)</th><th>massa proporcional à corda (Hz)</th><th>mudança</th></tr>"
        + a.f_hz.map((x, i) => `<tr><td>${i + 1} (${a.natureza[i] === "flexao" ? "flexão" : "torção"})</td><td>${fmt(x, 2)}</td><td>${fmt(a.f_hz_hipotese_antiga[i], 2)}</td><td>${fmt(100 * (x / a.f_hz_hipotese_antiga[i] - 1), 1)} %</td></tr>`).join("");
      C.append(el("div", "Frequências em vácuo com a rigidez atual (para confrontar com o GVT)", "grupo-par"), f);
      if (a.validacao) {
        const r = a.validacao, L = [];
        if (r.massa) L.push(`massa: ${fmt(r.massa.modelo_sem_ajuste, 3)} kg somado contra ${fmt(r.massa.medido, 3)} kg pesado (${fmt(r.massa.erro_pct, 1)} %)`);
        if (r.x_cg_c) L.push(`CG na corda: x/c ${fmt(r.x_cg_c.modelo, 3)} contra ${fmt(r.x_cg_c.medido, 3)} (${fmt(r.x_cg_c.erro_c, 3)} corda)`);
        if (r.y_cg_m) L.push(`CG na envergadura: ${fmt(r.y_cg_m.modelo, 3)} m contra ${fmt(r.y_cg_m.medido, 3)} m (${fmt(1000 * r.y_cg_m.erro_m, 0)} mm)`);
        C.append(el("div", "Validação com a balança: " + L.join(" · "), "nota"));
      }
      a.avisos.forEach(x => C.append(el("div", x, "nota")));
    }
    (res && res.avisos || []).forEach(x => C.append(el("div", x, "nota")));
    C.append(el("div", "A estrutura do modelo (nervuras, longarinas, tubos, chapeado, entelagem, dobradiças) é fatiada em y pelo volume ou pela área de cada peça. As adicionais são pontuais (só “y”) "
      + "ou espalhadas entre “y” e “até y”, na fração da corda “x/c”; a entelagem por gramatura usa a área de pele do modelo. A asa é tratada como simétrica.", "nota"));
  }

  function mostra(forca) { if (!ativa()) return; if (forca || !document.activeElement || document.activeElement.tagName !== "INPUT") { parametros(); veredito(); graficos(); baixo(); } }
  Etapa3.registra("massa_asa", { pinta() { parametros(); veredito(); baixo(); agenda(); } });
  return { dados: () => ({ v, res }), corpo };
})();
