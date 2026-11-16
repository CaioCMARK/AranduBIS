"use strict";

const Massa3 = (() => {
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#a278c8"];
  let res = null, tempo = null, seq = 0;
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "massa";
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Massa e CG";
    P.append(el("div", "MTOW e demais massas vêm do modelo e da vista Cargas. Para trocar a hipótese por massa real, declare bateria, motor, ESC e carga como peças pontuais no modelo (etapa 1).", "nota"));
  }
  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 300); }
  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Somando as massas do modelo…");
    try {
      const c = Cargas3.corpo();
      const r = await chama("/api/massa_estrutural", { esquema: esq, mtow_kg: c.massa_kg });
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; vazio(V); return; }
    const e = res.envelope, ok = !e || (e.x_dentro && e.z_dentro !== false); V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${fmt(res.total_kg, 2)} kg no modelo</b> (MTOW ${fmt(res.mtow_kg, 2)}): estrutura desenhada ${fmt(res.estrutural_kg, 2)} kg, massa não modelada ${fmt(res.nao_modelada_kg, 2)} kg · CG x = ${fmt(res.cg[0], 3)} m, z = ${fmt(res.cg[2], 3)} m`
      + (e ? ` · ${ok ? "dentro" : "FORA"} do envelope declarado (x ${fmt(e.x[0], 3)} a ${fmt(e.x[1], 3)})` : "");
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1].map(() => el("div", "", "graf")); C.append(...g);
    const S = res.sensibilidade;
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: "Massa por grupo (kg), sem a não modelada", xlab: "grupo (1 = maior)", ylab: "kg",
        series: [{ nome: "kg", x: res.grupos.filter(q => q.grupo !== "ponto").map((_, i) => i + 1), y: res.grupos.filter(q => q.grupo !== "ponto").map(q => q.massa_kg), cor: COR[0] }] });
      Grafico.desenha(g[1], { titulo: "CG em x × massa da estrutura desenhada", xlab: "fator sobre a estrutura", ylab: "x do CG (m)",
        series: [{ nome: "MTOW fixo", x: S.map(s => s.fator_estrutura), y: S.map(s => s.cg_x_mtow_fixo), cor: COR[0] }, { nome: "MTOW livre", x: S.map(s => s.fator_estrutura), y: S.map(s => s.cg_x_mtow_livre), cor: COR[1] }],
        refs: res.envelope ? [{ tipo: "h", valor: res.envelope.x[0], rotulo: "", cor: "#c85a5a" }, { tipo: "h", valor: res.envelope.x[1], rotulo: "", cor: "#c85a5a" }] : [] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Balanço de massa", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>grupo</th><th>massa (kg)</th><th>%</th><th>CG x / z (m)</th><th>maiores itens</th></tr>`
      + res.grupos.map(q => `<tr><td>${q.rotulo}</td><td>${fmt(q.massa_kg, 3)}</td><td>${fmt(100 * q.massa_kg / res.total_kg, 1)}</td><td>${fmt(q.cg[0], 3)} / ${fmt(q.cg[2], 3)}</td><td>${q.itens.slice(0, 3).map(i => i.nome + " " + fmt(1000 * i.massa, 0) + " g").join(", ")}</td></tr>`).join("");
    C.append(t);
    const ic = res.inercias_calculadas, id = res.inercias_declaradas, k = ["Ixx", "Iyy", "Izz", "Ixz"];
    const t2 = document.createElement("table");
    t2.innerHTML = `<tr><th>inércia (kg·m²)</th>${k.map(x => `<th>${x}</th>`).join("")}</tr><tr><td>calculada (massas pontuais)</td>${k.map(x => `<td>${fmt(ic[x], 3)}</td>`).join("")}</tr>`
      + `<tr><td>declarada no modelo</td>${k.map(x => `<td>${id[x] === undefined ? "—" : fmt(id[x], 3)}</td>`).join("")}</tr>`;
    C.append(t2);
    if (res.nao_modelada_sugerida_kg !== undefined) C.append(el("div", `Com o MTOW fixo em ${fmt(res.mtow_kg, 2)} kg, a massa não modelada (“${res.nao_modelada_nome}”) que fecha a conta é ${fmt(res.nao_modelada_sugerida_kg, 2)} kg (declarada: ${fmt(res.nao_modelada_kg, 2)}); CG resultante x = ${fmt(res.cg_mtow_fixo[0], 3)} m.`, "nota"));
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Cada item é massa pontual no próprio CG (sem inércia própria da peça): serve de conferência contra a inércia declarada, não a substitui.", "nota"));
    peso(C);
  }

  // ---- calculadora de peso vazio ----
  const CH_PESO = "aranduBIS.peso";
  let po = {}, pres = null, seqPeso = 0;
  try { po = JSON.parse(localStorage.getItem(CH_PESO) || "{}"); } catch (e) { po = {}; }
  const CAMPOS_PESO = [["servo_g", "Servo (g, cada)"], ["helice_g", "Hélice (g)"], ["esc_g", "ESC (g)"], ["receptor_g", "Receptor (g)"],
                       ["cabos_g", "Cabos, conectores, parafusos (g)"], ["cola_pct", "Cola (% da madeira)"], ["mtow_kg", "MTOW do regulamento (kg)"]];
  async function calculaPeso() {
    const meu = ++seqPeso;
    try {
      const opcoes = Object.fromEntries(CAMPOS_PESO.filter(c => c[0] !== "mtow_kg").map(c => [c[0], po[c[0]]]));
      opcoes.celulas = Padroes.get("tracao.celulas"); opcoes.capacidade_Ah = Padroes.get("tracao.capacidade_Ah");
      const r = await chama("/api/peso", { esquema: esq, opcoes, motor: Padroes.get("tracao.motor"), mtow_kg: po.mtow_kg || null });
      if (meu !== seqPeso) return;
      pres = r;
    } catch (e) { if (meu !== seqPeso) return; pres = { erro: e.message }; }
    if (ativa()) baixo();
  }
  function peso(C) {
    const B = el("div", "", "bloco"); C.append(B); B.append(el("h5", "Calculadora de peso vazio"));
    const G = el("div", "", "prop"); B.append(G);
    CAMPOS_PESO.forEach(([k, r]) => { G.append(el("label", r), entrada("number", po[k] ?? "", v => { po[k] = v; try { localStorage.setItem(CH_PESO, JSON.stringify(po)); } catch (e) {} calculaPeso(); })); });
    B.append(el("div", "Motor e bateria vêm de Configurações → Tração (catálogo do motor; bateria pela energia, com a energia específica média de packs 6S 1500 mAh do mercado). Campo vazio = ainda sem número.", "nota"));
    if (!pres) { if (!seqPeso || pres === null) calculaPeso(); return; }
    if (pres.erro) { B.append(el("div", pres.erro, "nota erro")); return; }
    const t = document.createElement("table");
    const lin = (a, b, c) => `<tr><td>${a}</td><td>${b}</td><td>${c}</td></tr>`;
    t.innerHTML = `<tr><th>item</th><th>massa (g)</th><th>origem</th></tr>`
      + `<tr><th colspan="3">Estrutura desenhada: ${fmt(1000 * pres.estrutura_kg, 0)} g</th></tr>`
      + Object.entries(pres.por_parte).map(([k, v]) => lin(k, fmt(1000 * v, 0), "volume ou área × densidade (geometria)")).join("")
      + `<tr><th colspan="3">Montagem: ${fmt(1000 * pres.montagem_kg, 0)} g</th></tr>` + pres.montagem.map(x => lin(x.item, fmt(1000 * x.massa_kg, 0), x.origem)).join("")
      + `<tr><th colspan="3">Sistemas: ${fmt(1000 * pres.sistemas_kg, 0)} g</th></tr>` + pres.sistemas.map(x => lin(x.item, fmt(1000 * x.massa_kg, 0), x.origem)).join("")
      + `<tr><th>Peso vazio</th><th>${fmt(1000 * pres.peso_vazio_kg, 0)} g</th><th>${pres.carga_paga_max_kg !== undefined ? "carga paga máxima no MTOW: " + fmt(pres.carga_paga_max_kg, 2) + " kg" : ""}</th></tr>`;
    B.append(t);
    if (pres.declarados.length) B.append(el("div", "Já declarado no modelo como massa pontual (fora do peso vazio): " + pres.declarados.map(d => `${d.item} ${fmt(1000 * d.massa_kg, 0)} g`).join(", ") + ".", "nota"));
    pres.avisos.forEach(a => B.append(el("div", a, "nota")));
    if (pres.servos.length && po.servo_g) {
      const b = el("button", `Pôr os ${pres.servos.length} servos no modelo (entram na massa da asa e no flutter)`);
      b.onclick = async () => { try { const novo = await chama("/api/peso/servos", { esquema: esq, servo_g: po.servo_g }); muda(() => { esq.elementos = novo.elementos; }); pres = null; msg("Servos inseridos como massas pontuais (Desfazer volta atrás)."); } catch (e) { msg(e.message, true); } };
      B.append(b);
    }
  }

  function mostra() { if (!ativa()) return; parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("massa", { pinta() { pres = null; parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ res }) };
})();
