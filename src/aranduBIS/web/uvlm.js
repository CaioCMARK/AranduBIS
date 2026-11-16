"use strict";

// Aerodinâmica não estacionária: VLM com esteira de anéis no tempo (Katz & Plotkin cap. 13).
const Uvlm3 = (() => {
  const CASOS = [["degrau", "Partida impulsiva (Wagner)"], ["rajada_degrau", "Rajada degrau (Küssner)"], ["rajada_1cos", "Rajada 1-cos (CS-23 / 14 CFR 23)"],
                 ["mergulho", "Mergulho harmônico (Theodorsen)"], ["arfagem", "Arfagem harmônica"]];
  const CAMPOS = [
    { g: "Ponto de voo", k: "V", r: "Velocidade (m/s)", d: "Vazio = a Vc da vista Cargas.", vazio: true },
    { k: "alpha", r: "Ângulo de ataque (°)", d: "Ângulo da aeronave inteira (as incidências do modelo somam).", zero: true },
    { g: "Rajada", k: "w0", r: "Velocidade de pico (m/s, + para cima)", d: "Rajada vertical congelada que entra pelo bordo de ataque em t = 0.", so: ["rajada_degrau", "rajada_1cos"], zero: true },
    { k: "H_cordas", r: "Comprimento H (cordas)", d: "14 CFR 23.333 e CS-23: H = 25 cordas médias.", so: ["rajada_1cos"] },
    { g: "Movimento", k: "f", r: "Frequência (Hz)", d: "Frequência reduzida k = π f c / V. Acima de 0,3, use ≥ 8 painéis na corda.", so: ["mergulho", "arfagem"] },
    { k: "amplitude", r: "Amplitude (m no mergulho, ° na arfagem)", d: "Linearizado: a geometria não se move, só a velocidade nos pontos de controle.", so: ["mergulho", "arfagem"] },
    // discretização: só aparece no modo manual; vazio = o valor automático
    { g: "Discretização (vazio = automático)", k: "n_span", r: "Painéis na envergadura", d: "Por superfície. Automático: o recomendado pelo alongamento de cada uma (24 se AR ≥ 4, 48 se AR ≥ 1).", m: true },
    { k: "n_chord", r: "Painéis na corda", d: "A massa aparente pede painel na corda: erro na amplitude ≈ 1,2 k / n_chord. Rajada degrau: 8.", m: true },
    { k: "passos_por_corda", r: "Passos por corda", d: "dt = c / (passos × V). Wagner quase não depende dele; harmônico e rajada pedem ≥ 40 passos por ciclo ou por rajada.", m: true },
    { k: "cordas", r: "Duração (cordas percorridas)", d: "Automático: 20 cordas na partida e na rajada degrau; H + 10 na rajada 1-cos.", so: ["degrau", "rajada_degrau", "rajada_1cos"], m: true },
    { k: "ciclos", r: "Ciclos", d: "Automático: 3 (o 1º leva o transitório da partida).", so: ["mergulho", "arfagem"], m: true },
    { k: "max_fileiras", r: "Fileiras de esteira", d: "Depois disso a última fileira vira uma cauda de 20 envergaduras. Automático: 30 cordas (rígida) ou 15 (livre).", m: true, aneis: true },
    { k: "fileiras_aneis", r: "Fileiras de anéis antes das partículas", d: "A 1ª é o Kutta implícito; dali para trás a esteira vira partículas. Automático: 3 (com 2 já bate com a esteira de anéis a 0,1 %).", m: true, part: true },
    { k: "idade_fusao", r: "Idade da 1ª fusão (passos)", d: "Partículas da mesma linha de vórtice se juntam aos pares a cada idade·2ⁿ passos (a vorticidade se conserva). Automático: 8 (CL muda < 0,1 %; com 4, ~1 %). 0 desliga.", m: true, part: true },
    { k: "sobreposicao", r: "Núcleo das partículas (× V·dt)", d: "σ = este fator × o espaçamento ao longo da corrente. Automático: 1,3 (as filas se sobrepõem e viram tubos).", m: true, part: true },
    { k: "fileiras_livres", r: "Fileiras que enrolam", d: "Só na esteira livre. Atrás delas a forma congela e só anda com a corrente. Automático: 6 cordas.", m: true, livre: true },
    { k: "nucleo", r: "Núcleo dos vórtices (× corda)", d: "Raio de regularização. Automático 0,002: casa com o VLM estacionário em 0,1 %. Maior suaviza a esteira livre e erra perto das pontas.", m: true },
    { k: "espera_cordas", r: "Espera antes de mudar a altura (cordas)", d: "Com razão de subida ≠ 0: a altura fica parada esse tempo (a partida impulsiva assenta) e depois muda. Automático: 8 cordas (Wagner ≈ 95 %).", m: true, sobe: true },
    { k: "dpsi", r: "Giro da hélice por subpasso (°)", d: "A hélice gira isso por subpasso; o passo da asa vira um número inteiro de subpassos. O núcleo das partículas da hélice é proporcional ao arco do subpasso: com 15° o sopro sai ~10 % fraco em quantidade de movimento, com 10° ~6 % (1ª ordem). Automático: 15°.", m: true, gira: true },
    { k: "n_el", r: "Elementos por pá", d: "Linha sustentadora girante: elementos em cosseno (finos na raiz e na ponta). Automático: 12 (com 20 a tração muda < 0,5 %).", m: true, gira: true },
    { k: "voltas_rolagem", r: "Enrolamento da esteira da hélice (voltas)", d: "Depois disso as partículas de cada subpasso viram 3: vórtice de ponta, de raiz e o largado no tempo (Betz). Automático: 0,5 volta.", m: true, gira: true },
  ];
  const PADRAO = { caso: "rajada_1cos", V: null, alpha: 2, w0: 3, H_cordas: 25, f: 4, amplitude: 0.02, esteira_livre: false, discretizacao: "auto",
                   n_span: null, n_chord: null, passos_por_corda: null, cordas: null, ciclos: null, max_fileiras: null, fileiras_livres: null, nucleo: null,
                   helice_girante: false, helice: "22x10E", rpm: 4500, sentido: 1, dpsi: null, n_el: null, voltas_rolagem: null,
                   solo: false, altura_solo: null, subida: 0, espera_cordas: null };
  const CHAVE = "aranduBIS.uvlm";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#8e6bbf", "#3fa7a0"];
  let v = Object.assign({}, PADRAO), res = null, seq = 0, rodando = false, gravando = false, supSel = null, cat = null;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  if (!v.esteira) v.esteira = v.esteira_livre ? "livre" : "rigida";
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "uvlm";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Aerodinâmica não estacionária";
    const G0 = document.createElement("div"); G0.className = "prop";
    const s = document.createElement("select"); CASOS.forEach(([k, n]) => s.add(new Option(n, k))); s.value = v.caso;
    s.onchange = () => { v.caso = s.value; guarda(); parametros(); };
    G0.append(el("label", "Caso"), s);
    const md = document.createElement("select"); [["auto", "Automática"], ["manual", "Manual"]].forEach(([k, n]) => md.add(new Option(n, k)));
    md.value = v.discretizacao || "auto";
    md.onchange = () => { v.discretizacao = md.value; guarda(); parametros(); };
    const lm = el("label", "Discretização"); lm.title = "Automática: o programa escolhe malha, passo e esteira pelo caso e pela frequência reduzida, com as regras de convergência medidas nos testes. Manual: você fixa o que quiser; campo vazio continua automático.";
    G0.append(lm, md);
    const ch = document.createElement("select");
    [["rigida", "Rígida (rápida, linear)"], ["livre", "Anéis livres (enrola)"], ["particulas", "Partículas de vórtice (VPM)"]].forEach(([k, n]) => ch.add(new Option(n, k)));
    ch.value = v.helice_girante ? "particulas" : v.esteira; ch.disabled = !!v.helice_girante;
    ch.onchange = () => { v.esteira = ch.value; v.esteira_livre = ch.value !== "rigida"; guarda(); parametros(); };
    const lb = el("label", "Esteira"); lb.title = "Rígida: segue a corrente com forma fixa (rápida, linear, boa para cargas). Anéis livres: cada nó anda com a velocidade local e a esteira enrola nas pontas. Partículas: depois de 3 fileiras de anéis a esteira vira uma nuvem de partículas de vórtice com estiramento e difusão (sem anéis que degeneram; base para interação asa-cauda, hélice e solo).";
    G0.append(lb, ch);
    const fz = Object.assign(document.createElement("input"), { type: "checkbox", checked: !!v.forcar });
    fz.onchange = () => { v.forcar = fz.checked; guarda(); };
    const lf = el("label", "Rodar acima do orçamento"); lf.title = "O programa estima o tempo pela malha antes de rodar e recusa o que passa do orçamento de Configurações → Discretização. Marque para rodar assim mesmo (só a falta de memória continua recusada).";
    G0.append(lf, fz);
    const hg = Object.assign(document.createElement("input"), { type: "checkbox", checked: !!v.helice_girante });
    hg.onchange = () => { v.helice_girante = hg.checked; guarda(); parametros(); };
    const so = Object.assign(document.createElement("input"), { type: "checkbox", checked: !!v.solo });
    so.onchange = () => { v.solo = so.checked; guarda(); parametros(); };
    const ls = el("label", "Efeito solo"); ls.title = "Chão plano por imagens (cada vórtice e cada partícula ganha um espelho abaixo do chão com circulação trocada): a velocidade normal no chão é zero. O chão é paralelo à corrente; a altura é a do ponto de referência (¼ da corda) acima dele.";
    G0.append(ls, so);
    const lh = el("label", "Hélice girante"); lh.title = "A hélice do modelo (posição do elemento “helice”) como linha sustentadora girante: cada pá larga a esteira em hélice como partículas de vórtice, que passam pela asa e pela cauda. A asa e a hélice se enxergam no tempo (sopro, redemoinho, carga cíclica). Força a esteira de partículas.";
    G0.append(lh, hg);
    P.append(el("div", "Caso", "grupo-par"), G0);
    if (v.solo) {
      const Gs = document.createElement("div"); Gs.className = "prop";
      P.append(el("div", "Efeito solo", "grupo-par"), Gs);
      const la = el("label", "Altura do solo (m)"); la.title = "Altura do ponto de referência (¼ da corda média, no eixo) acima do chão. Vazio: medida pelas rodas do modelo com a aeronave no ângulo de ataque escolhido (corrida de decolagem).";
      const ia = entrada("number", v.altura_solo, x => { if (x === null) { v.altura_solo = null; guarda(); return; } if (!(x > 0)) { msg("Altura inválida.", true); parametros(); return; } v.altura_solo = x; guarda(); });
      ia.placeholder = res && res.solo ? "rodas: " + fmt(res.solo.h0, 3) : "pelas rodas"; Gs.append(la, ia);
      const lv = el("label", "Razão de subida (m/s)"); lv.title = "0 = altura fixa (corrida no chão). Positivo: sai do chão subindo (decolagem); negativo: desce (arredondamento do pouso). A atitude fica fixa: o ar relativo ganha a componente vertical e o ângulo efetivo cai de atan(vs/V).";
      const iv = entrada("number", v.subida, x => { v.subida = x === null ? 0 : x; guarda(); parametros(); }); Gs.append(lv, iv);
    }
    if (v.helice_girante) {
      const Gh = document.createElement("div"); Gh.className = "prop";
      P.append(el("div", "Hélice girante", "grupo-par"), Gh);
      if (!cat) {
        Gh.append(el("label", "Carregando o catálogo…"));
        chama("/api/propulsao", { lista: true }).then(c => { cat = c; if (ativa()) parametros(); }).catch(e => msg(e.message, true));
      } else {
        const sh = document.createElement("select"); cat.helices.forEach(h => sh.add(new Option(h.nome, h.nome))); sh.value = v.helice;
        sh.onchange = () => { v.helice = sh.value; guarda(); };
        const l1 = el("label", "Hélice APC"); l1.title = "Diâmetro e passo do catálogo; a forma da pá é a média das APC Thin Electric (a mesma do BEMT).";
        Gh.append(l1, sh);
      }
      const l2 = el("label", "Rotação (rpm)"); l2.title = "Rotação constante. O passo da asa vira um número inteiro de subpassos da hélice.";
      const ir = entrada("number", v.rpm, x => { if (!(x > 0)) { msg("Rotação inválida.", true); parametros(); return; } v.rpm = x; guarda(); });
      Gh.append(l2, ir);
      const ss = document.createElement("select"); [["1", "horário visto de trás"], ["-1", "anti-horário visto de trás"]].forEach(([a, b]) => ss.add(new Option(b, a)));
      ss.value = String(v.sentido); ss.onchange = () => { v.sentido = +ss.value; guarda(); };
      const l3 = el("label", "Sentido de giro"); l3.title = "O redemoinho do sopro sobe um lado da asa e desce o outro; trocar o sentido espelha a carga.";
      Gh.append(l3, ss);
    }
    let G = null;
    const manual = v.discretizacao === "manual";
    const autoDe = k => { const e = res && res.discretizacao && res.discretizacao.find(q => q.campo === k); return e ? e.auto : undefined; };
    CAMPOS.forEach(c => {
      if (c.so && !c.so.includes(v.caso)) return;
      if (c.m && !manual) return;
      if (c.livre && v.esteira !== "livre") return;
      if (c.part && v.esteira !== "particulas" && !v.helice_girante) return;
      if (c.aneis && (v.esteira === "particulas" || v.helice_girante)) return;
      if (c.gira && !v.helice_girante) return;
      if (c.sobe && !(v.solo && v.subida)) return;
      if (c.g) { P.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; P.append(G); }
      const l = el("label", c.r); l.title = c.d;
      const i = entrada("number", v[c.k], x => {
        if (x === null && (c.vazio || c.m)) { v[c.k] = null; guarda(); return; }
        if (x === null || (!c.zero && !(x > 0))) { msg("Valor inválido em “" + c.r + "”.", true); parametros(); return; }
        v[c.k] = x; guarda();
      });
      i.title = c.d;
      if (c.vazio) i.placeholder = c.ph || "Vc de Cargas";
      if (c.m) { const a = autoDe(c.k); i.placeholder = a === undefined ? "auto" : a === null ? "auto: pelo alongamento" : "auto: " + fmt(a, 4); }
      G.append(l, i);
    });
    if (res && !res.particulas) {
      const sv = document.createElement("select"); res.esteira_lado.forEach(e => sv.add(new Option(e.nome, e.nome)));
      supSel = res.esteira_lado.some(e => e.nome === supSel) ? supSel : res.esteira_lado[0].nome; sv.value = supSel;
      sv.onchange = () => { supSel = sv.value; graficos(); };
      const G3 = document.createElement("div"); G3.className = "prop"; G3.append(el("label", "Esteira de"), sv);
      P.append(el("div", "Gráficos", "grupo-par"), G3);
    }
    if (v.discretizacao === "manual" && v.esteira === "particulas") {
      const sn = document.createElement("select"); [["gaussiano", "gaussiano (2ª ordem)"], ["winckelmans", "Winckelmans (algébrico)"]].forEach(([k, n]) => sn.add(new Option(n, k)));
      sn.value = v.nucleo_particula || "gaussiano"; sn.onchange = () => { v.nucleo_particula = sn.value; guarda(); };
      const Gn = document.createElement("div"); Gn.className = "prop";
      const ln = el("label", "Núcleo das partículas"); ln.title = "Gaussiano: vorticidade gaussiana, bate com a teoria do anel de vórtice. Winckelmans: algébrico de alta ordem, mais barato (sem exp e erf).";
      Gn.append(ln, sn); P.append(Gn);
    }
    const b = el("button", rodando ? "Calculando…" : "Calcular"); b.disabled = rodando; b.onclick = calcula;
    P.append(b);
    if (res && res.quadros) {
      const b3 = el("button", "Visualização 3D com linha do tempo");
      b3.title = "Abre a esteira em tela grande: gire, aproxime, mude a vista e ande no tempo (deslizante, tocar/pausar).";
      b3.onclick = () => Visor.abre(res.quadros, `${esq.nome || "aeronave"} · ${nomeCaso(res.caso)} · esteira ${{ rigida: "rígida", livre: "de anéis livres", particulas: "de partículas" }[res.esteira]}`
        + (res.helice ? ` · hélice ${res.helice.nome} a ${fmt(res.helice.rpm, 0)} rpm` : "") + (res.solo ? ` · solo a ${fmt(res.solo.h0, 2)} m` : ""));
      P.append(b3);
    }
    const bv = el("button", gravando ? "Gerando o vídeo…" : "Vídeo da esteira (MP4)"); bv.disabled = gravando || rodando;
    bv.title = "Roda o mesmo caso guardando a esteira e baixa um MP4 (H.264) com o corpo, os anéis e as partículas.";
    bv.onclick = video; P.append(bv);
    P.append(el("div", "Todas as superfícies sustentadoras do modelo, cada uma com a sua esteira (a da asa passa pela empenagem). Densidade e Vc: vista Cargas.", "nota"));
  }

  function corpo() {
    const c = Cargas3.corpo();
    return Object.assign({}, v, { esquema: esq, rho: c.rho, V: v.V > 0 ? v.V : c.Vc, instantaneos: true });
  }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    rodando = true; if (ativa()) parametros();
    msg(v.helice_girante ? "Marchando no tempo com a hélice girante (subpassos da hélice dentro de cada passo da asa: pode levar minutos)…"
        : v.esteira === "particulas" ? "Marchando no tempo com a esteira de partículas (pode levar meio minuto)…"
        : v.esteira === "livre" ? "Marchando no tempo com esteira livre (pode levar meio minuto)…" : "Marchando no tempo…");
    try {
      const r = await chama("/api/uvlm", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg(`Pronto em ${fmt(r.tempo_s, 1)} s (estimativa: ${fmt(r.estimativa_s, 0)} s)`); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    rodando = false;
    mostra();
  }

  async function video() {
    if (!esq || !esq.elementos.length) return;
    gravando = true; parametros(); msg("Rodando e gravando a esteira (MP4)…");
    try {
      const r = await fetch("/api/uvlm/video", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo()) });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.erro || "falhou"); }
      const blob = await r.blob(), a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = (esq.nome || "aeronave") + "_esteira_" + v.caso + (v.helice_girante ? "_helice" : "") + (v.solo ? "_solo" : "") + ".mp4"; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      msg(`Vídeo pronto: ${(blob.size / 1e6).toFixed(1).replace(".", ",")} MB.`);
    } catch (e) { msg(e.message, true); }
    gravando = false; if (ativa()) parametros();
  }

  const nomeCaso = k => (CASOS.find(c => c[0] === k) || [k, k])[1];
  // pico depois do primeiro passo (o primeiro leva o impulso de massa aparente da partida, que em teoria é um delta)
  const resto = a => a.slice(1);

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito";
    if (!res) { V.className = "veredito neutro"; V.innerHTML = "<b>Nada calculado ainda:</b> escolha o caso e clique em Calcular."; return; }
    V.classList.add("neutro");
    const cl = resto(res.CL), mx = Math.max(...cl), mn = Math.min(...cl);
    if (res.caso.startsWith("rajada")) {
      const qs = res.CL_alpha * res.w0 / res.V;
      V.innerHTML = `<b>${nomeCaso(res.caso)}:</b> ΔCL de pico ${fmt(mx - res.CL_estacionario, 3)} contra ${fmt(qs, 3)} quase estático (CLα w0/V) · razão ${fmt((mx - res.CL_estacionario) / qs, 2)}`;
    } else if (res.caso === "degrau") {
      V.innerHTML = `<b>Partida impulsiva:</b> CL vai a ${fmt(res.CL[res.CL.length - 1], 3)} (VLM estacionário ${fmt(res.CL_estacionario, 3)}) em ${fmt(res.s[res.s.length - 1] / 2, 0)} cordas`;
    } else {
      V.innerHTML = `<b>${nomeCaso(res.caso)}:</b> CL oscila de ${fmt(mn, 3)} a ${fmt(mx, 3)} · k = ${fmt(res.k, 3)}`;
    }
    if (res.solo) {
      const so = res.solo;
      V.innerHTML += ` · <b>solo:</b> h = ${fmt(so.h0, 3)} m (${so.origem}, h/b = ${fmt(so.h0 / so.b, 3)}): CL do VLM ${fmt(so.CL_solo, 3)} contra ${fmt(so.CL_livre, 3)} longe do chão (+${fmt(100 * (so.CL_solo / so.CL_livre - 1), 1)} %)`
        + (so.subida ? `, ${so.subida > 0 ? "subindo" : "descendo"} ${fmt(Math.abs(so.subida), 2)} m/s depois de ${fmt(so.espera_s, 3)} s` : "");
    }
    if (res.helice) {
      const h = res.helice;
      V.innerHTML += ` · <b>hélice ${h.nome}:</b> T = ${fmt(h.T_media, 2)} N e P = ${fmt(h.P_media, 0)} W na última volta (BEMT isolado: ${fmt(h.T_bemt, 2)} N, ${fmt(h.P_bemt, 0)} W)`;
    }
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = (res.particulas ? [0, 1, 2, 3] : [0, 1, 2]).concat(res.helice ? [4] : []).concat(res.solo && res.solo.subida ? [5] : []).map(() => el("div", "", "graf")); C.append(...g);
    const desenha = () => {
      const x = resto(res.t), s = [{ nome: "UVLM", x, y: resto(res.CL), cor: COR[0] }];
      if (res.ref) s.push({ nome: res.ref.nome, x, y: resto(res.ref.y), cor: COR[3], tracejado: true });
      Grafico.desenha(g[0], { titulo: `CL no tempo: ${nomeCaso(res.caso)}` + (res.solo ? " com efeito solo" : ""), xlab: "t (s)", ylab: "CL", series: s,
        refs: [{ tipo: "h", valor: res.CL_estacionario, rotulo: res.solo ? "VLM com solo" : "VLM estacionário", cor: "#999" }]
          .concat(res.solo ? [{ tipo: "h", valor: res.solo.CL_livre, rotulo: "longe do chão", cor: "#bbb" }] : []) });
      if (res.solo && res.solo.subida) {
        const gi = g.length - 1;
        Grafico.desenha(g[gi], { titulo: "Altura do ponto de referência acima do chão", xlab: "t (s)", ylab: "h (m)",
          series: [{ nome: "h(t)", x: res.t, y: res.solo.h, cor: COR[5] }] });
      }
      Grafico.desenha(g[1], { titulo: `Cm em torno de x = ${fmt(res.x_ref, 3)} m e CD induzido`, xlab: "t (s)", ylab: "coeficiente",
        series: [{ nome: "Cm", x, y: resto(res.Cm), cor: COR[1] }, { nome: "CD", x, y: resto(res.CD), cor: COR[2] }] });
      if (res.particulas) {
        const p = res.particulas, ws = [...p.w].sort((a, b) => a - b), q1 = ws[Math.floor(ws.length / 3)], q2 = ws[Math.floor(2 * ws.length / 3)];
        const faixa = (lo, hi) => p.w.map((w, i) => w >= lo && w < hi ? i : -1).filter(i => i >= 0);
        const grupos = [["|α| fraco", faixa(-1, q1), "#c9a0dc"], ["médio", faixa(q1, q2), "#d98a3d"], ["forte", faixa(q2, Infinity), "#8a1c4a"]];
        const nuvem = (a, b) => grupos.map(([n, idx, cor]) => ({ nome: n, x: idx.map(i => p[a][i]), y: idx.map(i => p[b][i]), cor, marcador: "ponto" }));
        Grafico.desenha(g[2], { titulo: `Partículas vistas de lado (${p.n} no fim)`, xlab: "x (m)", ylab: "z (m)", series: nuvem("x", "z") });
        Grafico.desenha(g[3], { titulo: res.helice ? "Partículas vistas de cima: o sopro em hélice passa pela asa" : "Partículas vistas de cima: o vórtice de ponta enrola", xlab: "x (m)", ylab: "y (m)", series: nuvem("x", "y") });
        if (res.helice) {
          const h = res.helice;
          Grafico.desenha(g[4], { titulo: `Tração da hélice ${h.nome} (média de cada passo da asa)`, xlab: "t (s)", ylab: "T (N)",
            series: [{ nome: "linha girante + partículas", x: h.t, y: h.T, cor: COR[4] }],
            refs: [{ tipo: "h", valor: h.T_bemt, rotulo: "BEMT isolado", cor: "#999" }] });
        }
      } else {
        const e = res.esteira_lado.find(q => q.nome === supSel) || res.esteira_lado[0], rot = ["ponta esquerda", "meio", "ponta direita"];
        Grafico.desenha(g[2], { titulo: `Esteira de ${e.nome} vista de lado`, xlab: "x (m)", ylab: "z (m)",
          series: e.x.map((xx, j) => ({ nome: `${rot[j]} (y = ${fmt(e.y[j], 2)} m)`, x: xx, y: e.z[j], cor: COR[j], tracejado: j === 1 })) });
      }
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Resumo", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = `<tr><th>V (m/s)</th><th>corda ref. (m)</th><th>área ref. (m²)</th><th>CLα (1/rad)</th><th>CL estacionário</th><th>dt (ms)</th><th>passos</th><th>painéis</th><th>anéis na esteira</th><th>partículas</th><th>esteira</th><th>tempo (s)</th></tr>`
      + `<tr><td>${fmt(res.V, 1)}</td><td>${fmt(res.c_ref, 3)}</td><td>${fmt(res.S_ref, 3)}</td><td>${fmt(res.CL_alpha, 3)}</td><td>${fmt(res.CL_estacionario, 3)}</td><td>${fmt(1000 * res.dt, 2)}</td>`
      + `<td>${res.passos}</td><td>${res.paineis}</td><td>${res.aneis_esteira}</td><td>${res.particulas ? res.particulas.n : "—"}</td><td>${{ rigida: "rígida", livre: "anéis livres", particulas: "partículas" }[res.esteira] || res.esteira}</td><td>${fmt(res.tempo_s, 1)}</td></tr>`;
    C.append(t);
    if (res.discretizacao) {
      const td = document.createElement("table");
      td.innerHTML = `<tr><th>discretização (${res.modo_discretizacao === "manual" ? "manual" : "automática"})</th><th>valor</th><th>origem</th><th>automático seria</th><th>por quê (regra automática)</th></tr>`
        + res.discretizacao.map(e => `<tr><td>${e.rotulo}</td><td>${typeof e.valor === "number" ? fmt(e.valor, 4) : e.valor}</td><td>${e.origem}</td>`
          + `<td>${e.auto === null ? "pelo AR" : fmt(e.auto, 4)}</td><td>${e.motivo}</td></tr>`).join("");
      C.append(td);
    }
    if (res.helice) {
      const h = res.helice, th = document.createElement("table");
      th.innerHTML = `<tr><th>hélice</th><th>rpm</th><th>J</th><th>subpassos por passo</th><th>giro por subpasso (°)</th><th>T média (N)</th><th>T BEMT (N)</th><th>P média (W)</th><th>P BEMT (W)</th><th>partículas da hélice</th><th>esteira até (m)</th></tr>`
        + `<tr><td>${h.nome} · ${h.sentido > 0 ? "horário" : "anti-horário"}</td><td>${fmt(h.rpm, 0)}</td><td>${fmt(h.J, 3)}</td><td>${h.n_sub}</td><td>${fmt(h.dpsi, 1)}</td><td>${fmt(h.T_media, 3)}</td><td>${fmt(h.T_bemt, 3)}</td><td>${fmt(h.P_media, 1)}</td><td>${fmt(h.P_bemt, 1)}</td><td>${h.particulas}</td><td>${fmt(h.comprimento_esteira, 2)}</td></tr>`;
      C.append(th);
      C.append(el("div", "Hélice girante (tests/test_rll.py): isolada, a tração e a potência ficam a 4 % do BEMT e a velocidade no disco a 15 % da do BEMT (média azimutal, com a perda de Prandtl); longe atrás, o fluxo de quantidade de movimento da esteira fecha com a tração a 10 % (1ª ordem no giro por subpasso); na frente de uma asa, o ganho de CL fica a 30 % do BEMT + sopro no VLM e o giro trocado espelha a carga.", "nota"));
    }
    if (res.solo) C.append(el("div", "Efeito solo no tempo (tests/test_solo_uvlm.py): a velocidade normal no chão fica em 1e-14 (imagens); com a altura fixa o UVLM vai ao VLM com solo a 1 % até h = 0,4 corda; subindo devagar, acompanha o VLM quase estático a 0,5 %; um par de vórtices de partículas descendo sobre o chão segue a trajetória de Lamb (1/y² + 1/z² constante) a 0,01 %.", "nota"));
    res.avisos.filter(x => !/pede n_span>=/.test(x) || res.modo_discretizacao === "manual").forEach(x => C.append(el("div", x, "nota")));
    C.append(el("div", "Validação (tests/test_uvlm.py): o limite estacionário bate com o VLM em 1 %; numa asa de alongamento 60 a partida impulsiva fica a 4 % de Wagner e a rajada degrau a 3 % de Küssner depois de 3 semicordas; "
      + "mergulho harmônico em k = 0,4 a 6 % e 3° de Theodorsen; a esteira de partículas reproduz a de anéis a 0,5 % e o anel de vórtice isolado anda na velocidade da teoria a 0,1 % (tests/test_vpm.py). O 1º passo (impulso de massa aparente da partida) fica fora dos gráficos.", "nota"));
    C.append(el("div", "Escoamento potencial, sem viscosidade nem estol: o CL não satura. Movimentos e rajadas linearizados (a malha não se move). "
      + "A referência de Theodorsen é uma faixa 2D escalada pelo CLα 3D: mostra a fase e a ordem de grandeza, não a resposta exata de uma asa finita.", "nota"));
  }

  function mostra() { if (!ativa()) return; if (!document.activeElement || document.activeElement.tagName !== "INPUT") parametros(); veredito(); graficos(); baixo(); }
  Etapa3.registra("uvlm", { pinta() { parametros(); mostra(); } });
  return { dados: () => ({ v, res }) };
})();
