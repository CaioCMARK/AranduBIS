"use strict";

const Calibracao3 = (() => {
  const CHAVE = "aranduBIS.calibracao";
  let v = { asa: null, ajusta: { EI: true, GJ: true, r_giro: false }, freq: [], flecha: [], torcao: [] }, res = null, seq = 0;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "calibracao";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Calibração";
    P.append(el("div", "Parâmetros a ajustar", "grupo-par"));
    const G = document.createElement("div"); G.className = "prop"; P.append(G);
    [["EI", "EI (flexão)"], ["GJ", "GJ (torção)"], ["r_giro", "Raio de giração"]].forEach(([k, r]) => {
      const c = document.createElement("input"); c.type = "checkbox"; c.checked = !!v.ajusta[k];
      c.onchange = () => { v.ajusta[k] = c.checked; guarda(); };
      G.append(el("label", r), c);
    });
    const ases = (esq && esq.elementos || []).filter(e => e.tipo === "asa" && e.estrutura).map(e => e.nome);
    const s = document.createElement("select"); ases.forEach(n => s.add(new Option(n, n)));
    v.asa = ases.includes(v.asa) ? v.asa : ases[0]; s.value = v.asa || "";
    s.onchange = () => { v.asa = s.value; guarda(); };
    const G2 = document.createElement("div"); G2.className = "prop"; G2.append(el("label", "Asa"), s); P.append(el("div", "Asa", "grupo-par"), G2);
    P.append(el("div", "Massa e centro de massa: os da vista Massa da asa (real), se ligada, ou os da vista Flutter. Quanto mais ensaios independentes (flexão e torção em separado), melhor separados ficam EI e GJ.", "nota"));
  }

  function linhas(titulo, chave, campos, novo) {
    const D = document.createElement("div"); D.className = "prop";
    D.append(el("div", titulo, "grupo-par"));
    const T = document.createElement("table");
    T.innerHTML = "<tr>" + campos.map(c => `<th>${c.r}</th>`).join("") + "<th></th></tr>";
    v[chave].forEach((o, i) => {
      const tr = document.createElement("tr");
      campos.forEach(c => {
        const td = document.createElement("td");
        if (c.opcoes) {
          const s = document.createElement("select"); c.opcoes.forEach(([k, n]) => s.add(new Option(n, k))); s.value = o[c.k];
          s.onchange = () => { o[c.k] = s.value; guarda(); }; td.append(s);
        } else td.append(entrada("number", o[c.k], x => { o[c.k] = x; guarda(); }, { style: "width:80px" }));
        tr.append(td);
      });
      const td = document.createElement("td"), b = el("button", "✕"); b.onclick = () => { v[chave].splice(i, 1); guarda(); mostra(true); }; td.append(b); tr.append(td);
      T.append(tr);
    });
    D.append(T);
    const b = el("button", "+ " + titulo.toLowerCase()); b.onclick = () => { v[chave].push(novo()); guarda(); mostra(true); }; D.append(b);
    return D;
  }

  function formulario(C) {
    const L = a => a && a.y ? a.y[a.y.length - 1] : 1.0;
    C.append(linhas("Frequência do GVT", "freq", [{ k: "tipo", r: "modo", opcoes: [["todos", "qualquer"], ["flexao", "flexão"], ["torcao", "torção"]] }, { k: "ordem", r: "ordem" }, { k: "hz", r: "medida (Hz)" }],
      () => ({ tipo: "todos", ordem: 1, hz: null })));
    C.append(linhas("Ensaio de flexão", "flecha", [{ k: "P_N", r: "carga (N)" }, { k: "y_carga_m", r: "y da carga (m)" }, { k: "y_medida_m", r: "y medido (m)" }, { k: "w_m", r: "flecha (m)" }],
      () => ({ P_N: null, y_carga_m: null, y_medida_m: null, w_m: null })));
    C.append(linhas("Ensaio de torção", "torcao", [{ k: "T_Nm", r: "torque (N·m)" }, { k: "y_carga_m", r: "y do torque (m)" }, { k: "y_medida_m", r: "y medido (m)" }, { k: "theta_graus", r: "giro (°)" }],
      () => ({ T_Nm: null, y_carga_m: null, y_medida_m: null, theta_graus: null })));
    const b = el("button", "Ajustar rigidez às medidas", "primario"); b.onclick = calcula; C.append(b);
  }

  function corpo() {
    const f = typeof Flutter3 !== "undefined" ? Flutter3.dados().v : {}, t = Torcao3.dados().v, c = Cargas3.corpo();
    const ok = a => a.every(o => Object.values(o).every(x => x !== null && x !== ""));
    return { esquema: esq, asa: v.asa, rho: c.rho, Vd: c.Vd, materiais: Asa3.materiais(), x_ca_c: t.x_ca_c, cl_alpha_2d: t.cl_alpha_2d, ea_desloc_c: t.ea_desloc_c,
             massa_asa_kg: f.massa_asa_kg, x_cg_c: f.x_cg_c, r_giro_c: f.r_giro_c || 0.28, massa_real: typeof MassaAsa3 !== "undefined" ? MassaAsa3.corpo() : null, ajusta: Object.keys(v.ajusta).filter(k => v.ajusta[k]),
             observacoes: { frequencias: v.freq.filter(o => ok([o])), flecha: v.flecha.filter(o => ok([o])), torcao: v.torcao.filter(o => ok([o])) } };
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { msg("Abra ou desenhe uma aeronave na etapa 1.", true); return; }
    msg("Ajustando EI e GJ às medidas…");
    try {
      const r = await chama("/api/calibracao", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra(true);
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { V.textContent = "Informe as medidas e clique em “Ajustar rigidez às medidas”."; return; }
    const p = res.parametros, u = res.incerteza_pct;
    V.classList.remove("neutro"); V.classList.add(res.rms_depois_pct < 5 ? "ok" : "ruim");
    V.innerHTML = "<b>Ajuste:</b> " + Object.keys(p).map(k => `${k === "r_giro" ? "raio de giração" : k} × ${fmt(p[k], 3)}${u[k] != null ? " ± " + fmt(u[k], 1) + " %" : ""}`).join(" · ")
      + ` · erro médio ${fmt(res.rms_antes_pct, 1)} % → ${fmt(res.rms_depois_pct, 1)} %`;
  }

  function resultado(C) {
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>medida</th><th>medido</th><th>modelo antes</th><th>erro antes</th><th>modelo depois</th><th>erro depois</th></tr>"
      + res.rotulos.map((r, i) => `<tr><td>${r}</td><td>${fmt(res.medido[i], 4)}</td><td>${res.modelo_antes[i] === null ? "—" : fmt(res.modelo_antes[i], 4)}</td><td>${res.erro_antes_pct[i] === null ? "—" : fmt(res.erro_antes_pct[i], 1) + " %"}</td><td>${fmt(res.modelo_depois[i], 4)}</td><td>${fmt(res.erro_depois_pct[i], 1)} %</td></tr>`).join("");
    C.append(el("div", "Resultado", "grupo-par"), t);
    const b = el("button", "Aplicar nas vistas Torção, Asa e Flutter", "primario");
    b.onclick = () => {
      const p = res.parametros, patch = {};
      if (p.EI) patch.calib_EI = +p.EI.toFixed(4);
      if (p.GJ) patch.calib_GJ = +p.GJ.toFixed(4);
      Torcao3.aplica(patch);
      if (p.r_giro && typeof Flutter3 !== "undefined") Flutter3.aplica({ r_giro_c: +res.r_giro_c.toFixed(4) });
      msg("Calibração aplicada: EI × " + fmt(patch.calib_EI, 3) + ", GJ × " + fmt(patch.calib_GJ, 3) + " sobre o modelo sem calibração.");
    };
    C.append(b);
    C.append(el("div", "Modos do modelo já com o ajuste (para conferir o tipo e a ordem que você casou com o GVT): "
      + res.f_vacuo_hz.slice(0, 10).map((f, i) => `${i + 1}: ${fmt(f, 1)} Hz (${res.natureza[i] === "flexao" ? "flexão" : "torção"})`).join(" · "), "nota"));
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Medidas", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    formulario(C); resultado(C);
    C.append(el("div", "Os multiplicadores valem sobre o modelo sem calibração (um novo ajuste substitui o anterior). Use medidas de uma asa montada como voa (entelada, com aileron e servo) e a massa pesada da vista Flutter.", "nota"));
  }

  function mostra(forca) { if (!ativa()) return; if (forca || !document.activeElement || document.activeElement.tagName !== "INPUT") { parametros(); veredito(); $("graficos3").innerHTML = ""; baixo(); } }
  Etapa3.registra("calibracao", { pinta() { parametros(); veredito(); baixo(); } });
  return { dados: () => ({ v, res }) };
})();
