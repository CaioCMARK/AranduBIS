"use strict";

const Flutter3 = (() => {
  const CAMPOS = [
    { g: "Massa da asa", k: "massa_asa_kg", r: "Massa da semi-asa (kg)", d: "Vazio = soma dos itens estruturais do modelo (nervuras, longarina, tubos, chapeado). Informe a massa pesada, com aileron, servo e entelagem.", vazio: true },
    { k: "x_cg_c", r: "Centro de massa (x/c)", d: "Vazio = posição média dos itens de massa do modelo. Decide o flutter: quanto mais atrás da linha elástica, menor a velocidade.", vazio: true },
    { k: "r_giro_c", r: "Raio de giração (× corda)", d: "Em torno do centro de massa. Asa com caixa e nervuras: 0,25 a 0,30. Calibre com a frequência de torção do GVT." },
    { g: "Cálculo", k: "zeta_s", r: "Amortecimento estrutural", d: "0 = nenhum (conservador). Valores típicos de asa de balsa e carbono: 0,01 a 0,03.", zero: true },
    { k: "V_max_rel", r: "Velocidade máxima (× Vd)", d: "Até onde varrer a velocidade." },
  ];
  const CHAVE = "aranduBIS.flutter";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#8e6bbf", "#3aa6a6", "#b09040", "#777"];
  let v = { massa_asa_kg: null, x_cg_c: null, r_giro_c: 0.28, zeta_s: 0, V_max_rel: 3 }, res = null, tempo = null, seq = 0, sel = null, modo = 0;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "flutter";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
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
    if (res) {
      const s = document.createElement("select"); res.asas.forEach(a => s.add(new Option(a.nome, a.nome)));
      sel = res.asas.some(a => a.nome === sel) ? sel : res.asas[0].nome; s.value = sel;
      s.onchange = () => { sel = s.value; modo = asaSel().modo_flutter ?? 0; graficos(); baixo(); };
      const G2 = document.createElement("div"); G2.className = "prop"; G2.append(el("label", "Asa"), s);
      P.append(el("div", "Gráficos", "grupo-par"), G2);
    }
    P.append(el("div", "Rigidez, linha elástica, densidade e Vd: as das vistas Torção, Cargas e Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  function corpo() {
    const c = Cargas3.corpo(), t = Torcao3.dados().v;
    return { esquema: esq, rho: c.rho, Vd: c.Vd, materiais: Asa3.materiais(), margem_aeroelastica: t.margem_aeroelastica, x_ca_c: t.x_ca_c, cl_alpha_2d: t.cl_alpha_2d,
             calib_GJ: t.calib_GJ, calib_EI: t.calib_EI, ea_desloc_c: t.ea_desloc_c, massa_asa_kg: v.massa_asa_kg, x_cg_c: v.x_cg_c, r_giro_c: v.r_giro_c, zeta_s: v.zeta_s, V_max_rel: v.V_max_rel };
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
    if (!res) { V.className = "veredito neutro"; V.textContent = "—"; return; }
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
      const f = a.formas, mx = Math.max(...f.h[modo].map(Math.abs)) || 1, ma = Math.max(...f.alfa[modo].map(Math.abs)) || 1;
      Grafico.desenha(g[2], { titulo: `Forma do modo ${modo + 1} (${fmt(a.f_vacuo_hz[modo], 1)} Hz, ${a.natureza[modo]})`, xlab: "y (m)", ylab: "normalizado",
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
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
    C.append(el("div", "Teoria de faixas de Theodorsen sobre uma semi-asa em balanço, sem efeito de envergadura finita (conservador), sem enflechamento e sem montantes entre as asas. "
      + "As frequências em vácuo são as que o ensaio de vibração mede: use-as para calibrar massa, centro de massa, raio de giração e o GJ da vista Torção antes de confiar na velocidade de flutter.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("flutter", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  function aplica(patch) { Object.assign(v, patch); guarda(); if (ativa()) { parametros(); agenda(); } }
  return { dados: () => ({ v, res }), aplica };
})();
