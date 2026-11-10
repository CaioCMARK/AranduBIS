"use strict";

const Cauda3 = (() => {
  const CAMPOS = [
    { g: "Apoio e cargas", k: "x_apoio", cfg: "estrutura.x_apoio", r: "Apoio: nós com x até (m)", d: "Região da fuselagem onde a treliça é engastada.", zero: true },
    { k: "CL_max_h", cfg: "estrutura.CL_max_h", r: "CL máx. da horizontal", d: "Profundor a fundo em Vd." },
    { k: "tailstrike_peso", cfg: "estrutura.tailstrike_peso", r: "Tailstrike (× peso, 0 = não)", d: "0 = não verifica. Reação vertical na ponta do boom.", zero: true },
    { g: "Barras", k: "K_flambagem", cfg: "estrutura.K_flambagem", r: "K de flambagem", d: "0,5 engastada, 1,0 articulada; 0,8 no Arandu 0.2.0." },
  ];
  const CHAVE = "aranduBIS.cauda";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#a278c8", "#5aaaaa", "#8a8a8a"];
  let v = {}, res = null, tempo = null, seq = 0;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = null; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (ativa()) { parametros(); agenda(); } });
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "cauda";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const pc = x => x >= 900 ? "> 900 %" : fmt(100 * x, 0) + " %";
  const nome = c => c.replace(/_/g, " ");

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Cauda e treliça";
    let G = null;
    CAMPOS.forEach(c => {
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null || (!c.zero && !(x > 0))) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; Padroes.toca(v, c.k); guarda(); agenda();
      });
      i.title = c.d; G.append(l, i);
    });
    if (res) {
      const b = el("button", "Baixar deck BDF (NASTRAN)"); b.onclick = () => {
        const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([res.bdf], { type: "text/plain" })); a.download = "trelica_cauda.bdf"; a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      };
      P.append(el("div", "Exportar", "grupo-par"), b);
    }
    P.append(el("div", "Velocidades, fator de segurança e rajada: as da vista Cargas. Tubos e materiais: modelo e Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  function corpo() {
    const c = Cargas3.corpo();
    return Object.assign(c, { materiais: Asa3.materiais(), x_apoio: v.x_apoio, CL_max_h: v.CL_max_h, tailstrike_peso: v.tailstrike_peso, K_flambagem: v.K_flambagem });
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Montando a treliça e resolvendo os casos (inclui as cargas do V-n)…");
    try {
      const r = await chama("/api/cauda", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; V.textContent = "—"; return; }
    const c = res.critico, ok = c.margem >= 0; V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${ok ? "Todas as barras com margem positiva" : "Margem negativa"}:</b> pior caso ${pc(c.margem)} em ${nome(c.modo)}, ${c.elemento}, ${nome(c.caso)} · ${res.n_barras} barras, ${res.n_nos} nós, ${fmt(res.massa_kg * 1000, 0)} g de tubo · 1º modo ${fmt(res.modos_hz[0], 1)} Hz (sem a massa da empenagem)`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1, 2].map(() => el("div", "", "graf")); C.append(...g);
    const casos = res.casos.filter(c => c.caso !== "trim" || c.perfil.x.length);
    const desenha = () => {
      const s = campo => casos.map((c, i) => ({ nome: nome(c.caso), x: c.perfil.x, y: c.perfil[campo], cor: COR[i % COR.length] }));
      Grafico.desenha(g[0], { titulo: "Deslocamento vertical do boom (carga limite)", xlab: "x (m)", ylab: "mm", series: s("uz") });
      Grafico.desenha(g[1], { titulo: "Torção do boom em torno do seu eixo", xlab: "x (m)", ylab: "graus", series: s("rx") });
      Grafico.desenha(g[2], { titulo: "Margem mínima por trecho (carga de ruptura)", xlab: "x (m)", ylab: "margem (limitada a 2000 %)", yMin: -1, yMax: 20,
        series: casos.map((c, i) => ({ nome: nome(c.caso), x: c.margem_x.x, y: c.margem_x.m, cor: COR[i % COR.length] })), refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#c85a5a" }] });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Casos e barras críticas", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>caso</th><th>carga</th><th>margem mínima</th><th>barra crítica</th><th>modo</th><th>ponta (mm)</th><th>rotação da horizontal (°)</th></tr>`
      + res.casos.map(c => { const b = c.piores[0]; return `<tr><td>${nome(c.caso)}</td><td>${c.descricao}</td><td>${pc(c.margem)}${c.margem < 0 ? " (FORA)" : ""}</td>`
        + `<td>${b.elemento} ${b.tubo}, L ${fmt(1000 * b.L, 0)} mm</td><td>${nome(b.modo)}</td><td>${fmt(c.deslocamento_ponta_mm[2], 1)}</td>`
        + `<td>${c.rotacao_h_graus ? fmt(c.rotacao_h_graus[0], 2) + " / " + fmt(c.rotacao_h_graus[1], 2) + " / " + fmt(c.rotacao_h_graus[2], 2) : "—"}</td></tr>`; }).join("");
    C.append(t);
    C.append(el("div", `Modos de vibração (sem a massa da empenagem, que o modelo ainda não declara): ${res.modos_hz.map(f => fmt(f, 1) + " Hz").join(", ")}. Compare com o GVT para ajustar a rigidez das juntas. Apoio: ${res.apoio_nos} nós com x ≤ ${fmt(res.x_apoio, 2)} m engastados.`, "nota"));
    const curtas = res.casos.flatMap(c => c.curtas.map(b => Object.assign({ caso: c.caso }, b))).sort((a, b) => a.margem - b.margem).slice(0, 3);
    if (curtas.length && curtas[0].margem < 0) C.append(el("div", `Barras curtas (comprimento menor que 10 diâmetros) com margem negativa, tratadas à parte porque a viga de Euler-Bernoulli perde validade nelas: ${curtas.map(b => `${b.elemento} ${b.tubo} ${fmt(1000 * b.L, 0)} mm, ${pc(b.margem)}, ${nome(b.caso)}`).join("; ")}.`, "nota"));
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Elementos finitos de viga com nós rígidos (juntas coladas sem folga nem flexibilidade), fuselagem como apoio rígido. O tailstrike só entra se você informar um valor. A torção em voo é a da deriva em rajada lateral e a do profundor a fundo; flutter fica fora.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("cauda", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
