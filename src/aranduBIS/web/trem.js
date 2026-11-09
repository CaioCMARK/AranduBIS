"use strict";

const Trem3 = (() => {
  const CAMPOS = [
    { g: "Pouso", k: "fator_pouso", cfg: "estrutura.fator_pouso", r: "Fator de pouso (× peso)", d: "Reação vertical do solo = fator × peso." },
    { k: "atrito_pouso", cfg: "estrutura.atrito_pouso", r: "Spin-up (× reação)", d: "HIPÓTESE: força para trás nas principais.", zero: true },
    { g: "Taxi", k: "fator_taxi_z", cfg: "estrutura.fator_taxi_z", r: "Vertical (× peso)", d: "Documento de referência: 1,0." },
    { k: "fator_taxi_y", cfg: "estrutura.fator_taxi_y", r: "Lateral (× peso)", d: "Documento de referência: 0,5.", zero: true },
    { g: "Modelo", k: "raio_inercia", cfg: "estrutura.raio_inercia", r: "Raio da massa (m)", d: "HIPÓTESE: a massa se espalha igual nos nós da treliça a menos deste raio do CG." },
  ];
  const CHAVE = "aranduBIS.trem";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a"];
  let v = {}, res = null, tempo = null, seq = 0;
  try { v = JSON.parse(localStorage.getItem(CHAVE) || "{}"); } catch (e) { v = {}; }
  CAMPOS.forEach(c => { if (!(c.k in v)) v[c.k] = null; });
  Padroes.aplica(v, CAMPOS);
  Padroes.aoMudar(() => { Padroes.aplica(v, CAMPOS); if (ativa()) { parametros(); agenda(); } });
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "trem";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const pc = x => x >= 900 ? "> 900 %" : fmt(100 * x, 0) + " %";
  const nome = c => c.replace(/_/g, " ");

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Trem de pouso";
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
    P.append(el("div", "Fator de segurança e massa: os da vista Cargas. Tubos e materiais: modelo e Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 400); }
  const corpo = () => { const c = Cargas3.corpo(); return Object.assign({ esquema: esq, fator_seguranca: c.fator_seguranca, massa_kg: c.massa_kg, materiais: Asa3.materiais() }, v); };

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Resolvendo os casos de pouso…");
    try {
      const r = await chama("/api/trem", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; V.textContent = "—"; return; }
    const c = res.critico, ok = c.margem >= 0; V.classList.add(ok ? "ok" : "ruim");
    V.innerHTML = `<b>${ok ? "Trem e montante com margem positiva" : "Margem negativa"}:</b> pior caso ${pc(c.margem)} em ${nome(c.modo)}, ${c.elemento} ${c.tubo}, ${nome(c.caso)} · peso ${fmt(res.peso_N, 0)} N, CG em x = ${fmt(res.cg[0], 3)} m (principais ${fmt(res.x_principais, 3)}, bequilha ${fmt(res.x_bequilha, 3)})`;
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1].map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      Grafico.desenha(g[0], { titulo: "Margem das 8 barras mais críticas por caso (ruptura)", xlab: "posição na lista", ylab: "margem (%)", yMin: -100, yMax: 300,
        series: res.casos.map((c, i) => ({ nome: nome(c.caso), x: c.piores.map((_, j) => j + 1), y: c.piores.map(b => Math.min(300, 100 * b.margem)), cor: COR[i % COR.length] })),
        refs: [{ tipo: "h", valor: 0, rotulo: "", cor: "#c85a5a" }] });
      const nomes = Object.keys(res.casos[0].rodas);
      Grafico.desenha(g[1], { titulo: "Reação vertical por roda (carga limite)", xlab: "caso (1 = 3 pontos, 2 = 2 pontos, 3 = taxi)", ylab: "N",
        series: nomes.map((n, i) => ({ nome: n, x: res.casos.map((_, j) => j + 1), y: res.casos.map(c => c.rodas[n].R), cor: COR[i % COR.length] })) });
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Casos e barras críticas", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>caso</th><th>carga</th><th>reação principais / bequilha (N)</th><th>margem mínima</th><th>barra crítica</th><th>modo</th><th>barra do eixo</th><th>flecha das rodas (mm)</th><th>a (g): x / z</th></tr>`
      + res.casos.map(c => { const b = c.piores[0], Rp = c.rodas.roda_esq ? c.rodas.roda_esq.R + c.rodas.roda_dir.R : 0, Rn = c.rodas.bequilha ? c.rodas.bequilha.R : 0;
        const d = Object.values(c.deslocamento_rodas_mm).map(x => fmt(Math.abs(x[2]), 1)).join(" / ");
        return `<tr><td>${nome(c.caso)}</td><td>${c.descricao}</td><td>${fmt(Rp, 0)} / ${fmt(Rn, 0)}</td><td>${pc(c.margem)}${c.margem < 0 ? " (FORA)" : ""}</td>`
          + `<td>${b.elemento} ${b.tubo}, L ${fmt(1000 * b.L, 0)} mm</td><td>${nome(b.modo)}</td><td>${c.eixo_margem === null ? "—" : pc(c.eixo_margem)}</td><td>${d}</td><td>${fmt(c.a_g[0], 2)} / ${fmt(c.a_g[2], 2)}</td></tr>`; }).join("");
    C.append(t);
    C.append(el("div", `Equilíbrio por alívio inercial: a massa (${fmt(res.massa_kg, 2)} kg) entra igual em ${res.n_nos_inercia} nós da treliça ao redor do CG e é acelerada até fechar força e momento com a reação do solo; o modelo é apoiado em um nó só e a reação desse apoio sai nula. Reação do solo = fator × peso, sem sustentação residual da asa (conservador); o momento do pneu em torno do eixo da roda é absorvido pelo giro da roda (spin-up), não pela estrutura.`, "nota"));
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Fora desta versão: a bequilha de alumínio, as rodas, os mancais e fixadores em compensado, o amortecimento do pneu (que reduz o pico) e o pouso de uma roda só. Juntas rígidas.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("trem", { pinta() { parametros(); agenda(); if (res) mostra(); } });
  return { dados: () => ({ v, res }) };
})();
