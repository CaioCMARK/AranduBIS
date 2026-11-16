"use strict";

const Juncao3 = (() => {
  const COR = { solda: "#4a86c5", "parafuso:x": "#d98a3d", "parafuso:y": "#b58b00", "parafuso:z": "#8a6fb0", rotula: "#6aa84f" };
  const NOME = { solda: "Solda (engaste)", "parafuso:x": "Parafuso no eixo x", "parafuso:y": "Parafuso no eixo y", "parafuso:z": "Parafuso no eixo z", rotula: "Rótula" };
  const CHAVE = "aranduBIS.juncao";
  let v = { tipos: ["solda", "parafuso:x", "rotula"], raio_mm: 60 }, res = null, tempo = null, seq = 0, sel = null;
  try { v = Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "juncao";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Junção asa–treliça";
    P.append(el("div", "Juntas a comparar", "grupo-par"));
    const G = el("div"); G.style.padding = "2px 8px";
    Object.keys(NOME).forEach(k => {
      const l = el("label"); l.style.display = "block";
      const c = document.createElement("input"); c.type = "checkbox"; c.checked = v.tipos.includes(k); c.disabled = k === "solda";
      c.onchange = () => { v.tipos = Object.keys(NOME).filter(q => q === "solda" || (q === k ? c.checked : v.tipos.includes(q))); guarda(); agenda(); };
      l.append(c, " " + NOME[k]); G.append(l);
    });
    P.append(G);
    const G2 = el("div", "", "prop");
    const lr = el("label", "Raio de busca (mm)"); lr.title = "Sem ligação declarada, entram os nós da treliça a até esta distância da longarina.";
    G2.append(lr, entrada("number", v.raio_mm, x => { if (!(x > 0)) { msg("Raio inválido.", true); parametros(); return; } v.raio_mm = x; guarda(); agenda(); }));
    if (res) {
      const s = document.createElement("select"); res.asas.forEach(a => s.add(new Option(a.asa, a.asa)));
      sel = res.asas.some(a => a.asa === sel) ? sel : res.asas[0].asa; s.value = sel;
      s.onchange = () => { sel = s.value; veredito(); graficos(); baixo(); };
      G2.append(el("label", "Asa"), s);
    }
    P.append(el("div", "Modelo", "grupo-par"), G2);
    P.append(el("div", "A asa entra como viga contínua, presa aos nós da treliça. Declare as ligações na tabela de nós da treliça (coluna “liga a”) e os apoios (coluna “vínculo”) na etapa 1. Cargas e materiais: os da vista Cargas e de Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 400); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Comparando as junções…");
    try {
      const r = await chama("/api/juncao", Object.assign({}, Cargas3.corpo(), { esquema: esq, materiais: Asa3.materiais(), tipos: v.tipos, raio_ligacao: v.raio_mm / 1000 }));
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  const asaSel = () => res.asas.find(a => a.asa === sel) || res.asas[0];
  const validas = a => a.variantes.filter(x => !x.mecanismo);
  const pct = x => (x === null || x === undefined ? "—" : (x >= 0 ? "+" : "") + fmt(100 * x, 0) + " %");

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { V.textContent = "Calculando, ou sem asa com longarina ligada à treliça."; return; }
    const a = asaSel(), vs = validas(a), base = vs.find(x => x.tipo === a.referencia), outras = vs.filter(x => x !== base);
    if (!outras.length) { V.innerHTML = `<b>${a.asa}:</b> só a solda segura a asa com estes pontos de ligação.`; return; }
    const m = outras.reduce((p, x) => (x.flexao_transmitida_Nm < p.flexao_transmitida_Nm ? x : p));
    V.innerHTML = `<b>${a.asa}, caso ${a.caso}:</b> com ${NOME[m.tipo].toLowerCase()} o momento de flexão que passa para a treliça muda ${pct(m.delta.flexao_transmitida_Nm)} `
      + `(${fmt(base.flexao_transmitida_Nm, 1)} → ${fmt(m.flexao_transmitida_Nm, 1)} N·m) e a flecha na ponta muda ${pct(m.delta.flecha_ponta_mm)} (${fmt(base.flecha_ponta_mm, 1)} → ${fmt(m.flecha_ponta_mm, 1)} mm).`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const a = asaSel(), vs = validas(a), g = [0, 1, 2, 3].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: `Deformada da asa, ${a.asa}`, xlab: "y (m)", ylab: "deslocamento (mm)",
        series: vs.map(x => ({ nome: NOME[x.tipo], x: x.y, y: x.w_mm, cor: COR[x.tipo] })) });
      Grafico.desenha(g[1], { titulo: "Momento fletor na longarina", xlab: "y (m)", ylab: "N·m",
        series: vs.map(x => ({ nome: NOME[x.tipo], x: x.y, y: x.fletor_Nm, cor: COR[x.tipo] })) });
      Grafico.desenha(g[2], { titulo: "Momento de flexão transmitido em cada ligação", xlab: "y da ligação (m)", ylab: "N·m",
        series: vs.map(x => ({ nome: NOME[x.tipo], x: x.ligacoes.map(l => l.y), y: x.ligacoes.map(l => l.flexao_Nm), cor: COR[x.tipo], marcador: "ponto", raio: 4 })) });
      Grafico.desenha(g[3], { titulo: "Menor margem das barras da treliça", xlab: "junta", ylab: "margem",
        series: [{ nome: "margem", x: vs.map((_, i) => i + 1), y: vs.map(x => Math.min(x.margem_trelica ?? 0, 5)), cor: "#4a86c5", marcador: "ponto", raio: 5 }],
        refs: [{ tipo: "h", valor: 0, rotulo: "limite", cor: "#999" }] });
    };
    desenha();
    if (!C._obsj) { C._obsj = true; Grafico.liga(C, () => { if (res && ativa()) graficos(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Comparação", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const a = asaSel(), t = document.createElement("table");
    t.innerHTML = "<tr><th>junta</th><th>flecha na ponta (mm)</th><th>Δ</th><th>fletor na ligação (N·m)</th><th>flexão transmitida (N·m)</th><th>Δ</th><th>momento total transmitido (N·m)</th><th>menor margem da treliça</th><th>barra crítica</th></tr>"
      + a.variantes.map(x => x.mecanismo
        ? `<tr><td>${NOME[x.tipo]}</td><td colspan="8" style="text-align:left">vira mecanismo: estes pontos de ligação não seguram a asa com esta junta</td></tr>`
        : `<tr><td>${NOME[x.tipo]}</td><td>${fmt(x.flecha_ponta_mm, 1)}</td><td>${pct(x.delta.flecha_ponta_mm)}</td><td>${fmt(x.fletor_na_ligacao_Nm, 1)}</td><td>${fmt(x.flexao_transmitida_Nm, 1)}</td>`
          + `<td>${pct(x.delta.flexao_transmitida_Nm)}</td><td>${fmt(x.momento_transmitido_Nm, 1)}</td><td>${x.margem_trelica === null ? "—" : x.margem_trelica >= 99 ? "sem carga" : fmt(100 * x.margem_trelica, 0) + " %"}</td>`
          + `<td>${x.barra_critica ? x.barra_critica.elemento + " (" + x.barra_critica.modo + ")" : "—"}</td></tr>`).join("");
    C.append(t);
    C.append(el("div", `${a.asa}: ${a.n_ligacoes} nó(s) de ligação ${a.declaradas ? "declarados" : "achados por proximidade"}; caso de carga ${a.caso}. Δ é a variação em relação à solda.`, "nota"));
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
    C.append(el("div", "Como ler: a solda transmite todo o momento da asa para a treliça; o parafuso deixa a asa girar em torno do eixo dele e a rótula em qualquer direção. Menos momento transmitido alivia a concentração de tensões na ligação, ao custo de mais flecha. A resistência da própria junta está na vista Cauda e treliça.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("juncao", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
