"use strict";

const Otimiza = (() => {
  const CHAVE = "aranduBIS.otimiza";
  const SECOES = [["variaveis", "Variáveis"], ["restricoes", "Restrições"], ["regra", "Regra e cenário"], ["analise", "Análise"], ["arvore", "Árvore de topologias"]];
  const AN_CAMPOS = [
    { g: "Condições de voo", k: "rho", r: "Densidade do ar (kg/m³)", p: 1.225 },
    { k: "V", r: "Velocidade de referência (m/s)", p: 12 },
    { k: "ncrit", r: "N crítico (transição)", p: 4 },
    { g: "Tração (sem motor/hélice reais)", k: "T0", r: "Tração estática (N)", p: 45 },
    { k: "V0", r: "Velocidade de tração zero (m/s)", p: 28 },
    { g: "Decolagem", k: "pista_m", r: "Distância até o obstáculo (m)", p: 55 },
    { k: "obstaculo_m", r: "Altura do obstáculo (m)", p: 0.9 },
    { g: "Carga, CG e estrutura", k: "carga_ref_kg", r: "Carga de referência p/ CG (kg)", p: 9 },
    { k: "carga_x", r: "Posição da carga (m, ou nome de variável)", p: "", texto: true },
    { k: "massa_projeto", r: "Massa de projeto p/ cargas V-n (kg)", p: 18 },
    { g: "Calibração", k: "fator_massas", r: "Fator sobre as massas de sistema (1 = sem ajuste)", p: 1.0 },
  ];
  let v = { variaveis: [], restricoes: [], regraNome: null, regraOrigem: null, regraJson: null, cenario: {}, analise: {}, avancado: "{}",
            execucao: { populacao: 16, geracoes: 20, semente: 0, estrategia: "melhor" }, ultimoProblema: null,
            arvore: [], arvoreSemente: "" };
  let secao = "variaveis", jobId = null, poll = null, ultimoEstado = null, listaRegras = [], seqRegra = 0;

  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function lista() {
    const L = $("lista4"); L.innerHTML = "";
    SECOES.forEach(([k, n]) => {
      const d = el("div", n, "el" + (k === secao ? " sel" : ""));
      d.onclick = () => { secao = k; lista(); pintaSecao(); };
      L.append(d);
    });
  }

  function folhasDoEsquema() {
    const fora = new Set(["nome", "tipo"]);
    const out = [];
    const anda = (no, prefixo) => {
      if (no === null || no === undefined) return;
      if (typeof no === "number") { out.push({ caminho: prefixo, valor: no }); return; }
      if (Array.isArray(no)) { no.forEach((item, i) => anda(item, `${prefixo}[${i}]`)); return; }
      if (typeof no === "object") {
        for (const [k, val] of Object.entries(no)) { if (!fora.has(k)) anda(val, `${prefixo}.${k}`); }
      }
    };
    (esq && esq.elementos || []).forEach(e => anda(e, e.nome));
    return out;
  }
  const caminhosDoEsquema = () => folhasDoEsquema().map(f => f.caminho);

  // ---- Escolha de parâmetros direto da aeronave (sem digitar caminho) ----
  let escolhaAberta = false, escolhaFiltro = "", escolhaPct = 20;
  const escolhidos = new Set();

  const nomeDoCaminho = (c, usados) => {
    let n = c.replace(/\]/g, "").replace(/[^A-Za-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    if (!n || /^\d/.test(n)) n = "v_" + n;
    let k = n, i = 2;
    while (usados.has(k)) k = n + "_" + i++;
    usados.add(k);
    return k;
  };
  const faixaDe = (val, pct) => {
    if (val === 0) return [-0.1, 0.1];
    const a = val * (1 - pct / 100), b = val * (1 + pct / 100);
    return [+Math.min(a, b).toPrecision(4), +Math.max(a, b).toPrecision(4)];
  };

  function painelEscolha(C, repinta) {
    const caixa = document.createElement("div");
    caixa.style.cssText = "margin:6px;border:1px solid var(--linha);background:var(--painel);padding:6px";
    if (!esq || !esq.elementos.length) { caixa.append(nota("Abra ou desenhe uma aeronave na etapa 1 para escolher parâmetros.")); C.append(caixa); return; }
    const barra = document.createElement("div"); barra.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px";
    const busca = document.createElement("input"); busca.type = "search"; busca.placeholder = "filtrar: asa, corda, ainc, posicao…"; busca.value = escolhaFiltro; busca.style.flex = "1 1 14em";
    const pct = entrada("number", escolhaPct, x => { if (x > 0 && x <= 90) escolhaPct = x; }, { min: 1, max: 90, step: 1 }); pct.style.width = "5em"; pct.title = "Faixa criada em torno do valor atual";
    const bAdd = el("button", ""), bFecha = el("button", "Fechar");
    barra.append(busca, el("span", "faixa ±"), pct, el("span", "%"), bAdd, bFecha);
    const lista = document.createElement("div"); lista.style.cssText = "max-height:230px;overflow:auto;border:1px solid var(--linha);font-family:monospace;font-size:12px";
    const usadas = new Set(v.variaveis.map(x => x.alvo));
    const todas = folhasDoEsquema().filter(f => !usadas.has(f.caminho));
    const atualizaBotao = () => { bAdd.textContent = `Adicionar selecionados (${escolhidos.size})`; bAdd.disabled = escolhidos.size === 0; };
    const pintaLista = () => {
      lista.innerHTML = "";
      const f = escolhaFiltro.trim().toLowerCase();
      const vis = todas.filter(x => !f || x.caminho.toLowerCase().includes(f));
      vis.slice(0, 300).forEach(x => {
        const r = document.createElement("label"); r.style.cssText = "display:flex;gap:8px;padding:1px 6px;cursor:pointer";
        const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = escolhidos.has(x.caminho);
        cb.onchange = () => { cb.checked ? escolhidos.add(x.caminho) : escolhidos.delete(x.caminho); atualizaBotao(); };
        const val = el("span", String(+x.valor.toPrecision(6))); val.style.cssText = "margin-left:auto;opacity:.7";
        r.append(cb, el("span", x.caminho), val); lista.append(r);
      });
      if (!vis.length) lista.append(nota(todas.length ? "Nenhum parâmetro com esse filtro." : "Todos os parâmetros numéricos já são variáveis."));
      else if (vis.length > 300) lista.append(nota(`Mostrando 300 de ${vis.length}: refine o filtro.`));
    };
    busca.oninput = () => { escolhaFiltro = busca.value; pintaLista(); };
    bFecha.onclick = () => { escolhaAberta = false; repinta(); };
    bAdd.onclick = () => {
      const nomes = new Set(v.variaveis.map(x => x.nome));
      todas.filter(x => escolhidos.has(x.caminho)).forEach(x => {
        const [lo, hi] = faixaDe(x.valor, escolhaPct);
        v.variaveis.push({ nome: nomeDoCaminho(x.caminho, nomes), alvo: x.caminho, minimo: lo, maximo: hi, padrao: x.valor });
      });
      escolhidos.clear(); guarda(); repinta();
    };
    atualizaBotao(); pintaLista();
    caixa.append(barra, lista, nota("Cada parâmetro marcado vira uma variável com faixa em torno do valor atual; ajuste nome e limites na tabela depois."));
    C.append(caixa);
  }

  function listaAlvos() {
    let dl = document.getElementById("lista_alvos4");
    if (!dl) { dl = document.createElement("datalist"); dl.id = "lista_alvos4"; document.body.append(dl); }
    dl.innerHTML = "";
    caminhosDoEsquema().forEach(c => dl.append(new Option(c)));
    return dl;
  }

  function secaoVariaveis(C) {
    C.append(nota('Use “Escolher parâmetros da aeronave” para marcar o que otimizar. Ou digite o alvo à mão: caminho no esquema, como “asa.secoes[1].corda” ou “canard.posicao[0]”, com sugestões enquanto digita.'));
    listaAlvos();
    const abre = el("button", escolhaAberta ? "▾ Escolher parâmetros da aeronave" : "▸ Escolher parâmetros da aeronave"); abre.style.margin = "4px 6px";
    abre.onclick = () => { escolhaAberta = !escolhaAberta; pintaSecao(); };
    C.append(abre);
    if (escolhaAberta) painelEscolha(C, pintaSecao);
    const t = document.createElement("table"); t.className = "edita";
    t.innerHTML = "<tr><th>nome</th><th>alvo</th><th>mínimo</th><th>máximo</th><th>padrão</th><th></th></tr>";
    v.variaveis.forEach((x, i) => {
      const tr = document.createElement("tr");
      const campo = (chave, tipo) => {
        const td = document.createElement("td"); const inp = entrada(tipo, x[chave], val => { x[chave] = val; guarda(); });
        if (chave === "alvo") inp.setAttribute("list", "lista_alvos4");
        td.append(inp); return td;
      };
      tr.append(campo("nome", "text"), campo("alvo", "text"), campo("minimo", "number"), campo("maximo", "number"), campo("padrao", "number"));
      const rm = document.createElement("td"); const b = el("button", "✕"); b.title = "Remover variável";
      b.onclick = () => { v.variaveis.splice(i, 1); guarda(); pintaSecao(); };
      rm.append(b); tr.append(rm); t.append(tr);
    });
    C.append(t);
    const add = el("button", "+ variável"); add.style.margin = "4px 6px";
    add.onclick = () => { v.variaveis.push({ nome: "x" + (v.variaveis.length + 1), alvo: "", minimo: 0, maximo: 1, padrao: 0.5 }); guarda(); pintaSecao(); };
    C.append(add);
  }

  function secaoRestricoes(C) {
    C.append(nota("fórmula: um resultado da avaliação — por exemplo margem_estatica, margem_estrutural, margem_reversao, margem_divergencia, envergadura, CL_max, massa_decolagem."));
    const t = document.createElement("table"); t.className = "edita";
    t.innerHTML = "<tr><th>nome</th><th>fórmula</th><th>tipo</th><th>limite</th><th></th></tr>";
    v.restricoes.forEach((x, i) => {
      const tr = document.createElement("tr");
      const td1 = document.createElement("td"); td1.append(entrada("text", x.nome, val => { x.nome = val; guarda(); }));
      const td2 = document.createElement("td"); td2.append(entrada("text", x.formula, val => { x.formula = val; guarda(); }));
      const td3 = document.createElement("td"); const sel = document.createElement("select");
      [["min", "mínimo"], ["max", "máximo"]].forEach(([k, n]) => sel.add(new Option(n, k)));
      sel.value = x.tipo || "min"; sel.onchange = () => { x.tipo = sel.value; guarda(); }; td3.append(sel);
      const td4 = document.createElement("td"); td4.append(entrada("number", x.limite, val => { x.limite = val; guarda(); }));
      tr.append(td1, td2, td3, td4);
      const rm = document.createElement("td"); const b = el("button", "✕"); b.title = "Remover restrição";
      b.onclick = () => { v.restricoes.splice(i, 1); guarda(); pintaSecao(); };
      rm.append(b); t.append(tr);
    });
    C.append(t);
    const add = el("button", "+ restrição"); add.style.margin = "4px 6px";
    add.onclick = () => { v.restricoes.push({ nome: "restricao" + (v.restricoes.length + 1), formula: "margem_estatica", limite: 0.05, tipo: "min" }); guarda(); pintaSecao(); };
    C.append(add);
  }

  async function secaoRegra(C) {
    const meu = ++seqRegra;
    if (!listaRegras.length) { try { listaRegras = (await chama("/api/regras")).regras; } catch (e) { msg(e.message, true); } }
    if (meu !== seqRegra) return;
    const sel = document.createElement("select"); sel.title = "Regra de pontuação (opcional)";
    sel.add(new Option("(sem regra: só as restrições de projeto contam)", ""));
    const porOrigem = {};
    listaRegras.forEach(r => { (porOrigem[r.origem] = porOrigem[r.origem] || []).push(r); });
    Object.entries(porOrigem).forEach(([origem, rs]) => {
      const g = document.createElement("optgroup"); g.label = origem === "fabrica" ? "De fábrica" : "Seus";
      rs.forEach(r => g.append(new Option(r.nome, r.nome + "@" + r.origem)));
      sel.append(g);
    });
    sel.value = v.regraNome ? v.regraNome + "@" + v.regraOrigem : "";
    sel.onchange = async () => {
      if (!sel.value) { v.regraNome = null; v.regraOrigem = null; v.regraJson = null; guarda(); pintaSecao(); return; }
      const [nome, origem] = sel.value.split("@");
      try {
        v.regraJson = await chama(`/api/regra?nome=${encodeURIComponent(nome)}&origem=${origem}`);
        v.regraNome = nome; v.regraOrigem = origem;
        v.cenario = Object.assign({}, v.regraJson.cenario || {}, v.cenario); guarda(); pintaSecao();
      } catch (e) { msg(e.message, true); }
    };
    C.append(sel);
    if (!v.regraJson) { C.append(nota("Sem regra, o objetivo precisa vir do JSON avançado (campo “objetivo”) ou a busca não terá o que maximizar.")); return; }
    if (v.regraJson.fonte) C.append(nota(v.regraJson.fonte));
    const G = document.createElement("div"); G.className = "prop";
    Object.entries(v.cenario).forEach(([k, val]) => {
      const inp = entrada(typeof val === "number" ? "number" : "text", val, x => { v.cenario[k] = x; guarda(); });
      G.append(el("label", k), inp);
    });
    C.append(G);
    const add = el("button", "+ campo do cenário"); add.style.margin = "4px 8px";
    add.onclick = () => { const k = prompt("Nome do campo (ex.: NR):"); if (k) { v.cenario[k] = 0; guarda(); pintaSecao(); } };
    C.append(add);
  }

  function secaoAnalise(C) {
    let G = null;
    AN_CAMPOS.forEach(c => {
      if (c.g) { C.append(el("div", c.g, "grupo-par")); G = document.createElement("div"); G.className = "prop"; C.append(G); }
      const atual = v.analise[c.k] !== undefined ? v.analise[c.k] : c.p;
      const inp = entrada(c.texto ? "text" : "number", atual, x => { v.analise[c.k] = x; guarda(); });
      inp.title = c.r;
      G.append(el("label", c.r), inp);
    });
    C.append(el("div", "Malha", "grupo-par"));
    const M = document.createElement("div"); M.className = "prop";
    const chk = document.createElement("input"); chk.type = "checkbox"; chk.checked = v.analise.malha_rapida !== false;
    chk.onchange = () => { v.analise.malha_rapida = chk.checked; guarda(); pintaSecao(); };
    M.append(el("label", "Triagem rápida (malha grossa)"), chk);
    C.append(M);
    C.append(nota("Com a malha grossa cada avaliação é bem mais rápida (erro de pontuação de 1 a 3 %, mesma ordenação dos projetos). Desligue para uma busca final mais lenta e exata."));
    if (v.analise.malha_rapida !== false) {
      const G2 = document.createElement("div"); G2.className = "prop";
      G2.append(el("label", "n_span"), entrada("number", v.analise.n_span ?? 12, x => { v.analise.n_span = x; guarda(); }));
      G2.append(el("label", "n_chord"), entrada("number", v.analise.n_chord ?? 2, x => { v.analise.n_chord = x; guarda(); }));
      C.append(G2);
    }
    const D = document.createElement("details");
    D.innerHTML = "<summary>Avançado: JSON extra do problema (massas, grandezas, dimensionamento, retira, analise.torcao/trim_decolagem, objetivo…)</summary>";
    const ta = document.createElement("textarea"); ta.value = v.avancado || "{}"; ta.spellcheck = false;
    const ap = el("button", "Aplicar");
    ap.onclick = () => { try { JSON.parse(ta.value); v.avancado = ta.value; guarda(); msg("Aplicado."); } catch (e) { msg("JSON inválido: " + e.message, true); } };
    D.append(ta, ap); C.append(D);
  }

  function pintaSecao() {
    const C = $("conteudo4"); C.innerHTML = "";
    if (secao === "variaveis") return secaoVariaveis(C);
    if (secao === "restricoes") return secaoRestricoes(C);
    if (secao === "regra") return secaoRegra(C);
    if (secao === "arvore") return secaoArvore(C);
    return secaoAnalise(C);
  }

  function snapshotAtual(nome) {
    return {
      nome, esq: JSON.parse(JSON.stringify(esq)), variaveis: JSON.parse(JSON.stringify(v.variaveis)),
      restricoes: JSON.parse(JSON.stringify(v.restricoes)), regraNome: v.regraNome, regraOrigem: v.regraOrigem,
      regraJson: v.regraJson, cenario: JSON.parse(JSON.stringify(v.cenario)), analise: JSON.parse(JSON.stringify(v.analise)),
      avancado: v.avancado,
    };
  }

  function montaProblemaDeSnapshot(snap) {
    const esqAntigo = esq;
    const vAntigo = { variaveis: v.variaveis, restricoes: v.restricoes, regraJson: v.regraJson, cenario: v.cenario, analise: v.analise, avancado: v.avancado };
    esq = snap.esq;
    Object.assign(v, { variaveis: snap.variaveis, restricoes: snap.restricoes, regraJson: snap.regraJson, cenario: snap.cenario, analise: snap.analise, avancado: snap.avancado });
    try { return montaProblema(); } finally { esq = esqAntigo; Object.assign(v, vAntigo); }
  }

  function secaoArvore(C) {
    C.append(nota("Em vez de otimizar as dimensões de UMA aeronave, a busca escolhe ENTRE as topologias salvas aqui — \"a partir de restrições e pontuação, o otimizador decide a aeronave\". Monte o problema normalmente nas outras seções (com a aeronave certa carregada na etapa 1), depois salve como uma topologia; troque a aeronave e repita para a próxima. Com 2 ou mais salvas, o botão Iniciar roda a árvore."));
    const t = document.createElement("table"); t.className = "edita";
    t.innerHTML = "<tr><th>topologia</th><th>aeronave</th><th>variáveis</th><th></th></tr>";
    (v.arvore || []).forEach((snap, i) => {
      const tr = document.createElement("tr");
      tr.append(el("td", snap.nome), el("td", snap.esq.nome || "—"), el("td", String(snap.variaveis.length)));
      const rm = document.createElement("td"); const b = el("button", "✕"); b.title = "Remover topologia";
      b.onclick = () => { v.arvore.splice(i, 1); if (v.arvoreSemente === snap.nome) v.arvoreSemente = ""; guarda(); pintaSecao(); painelExecucao(); };
      rm.append(b); tr.append(rm); t.append(tr);
    });
    C.append(t);
    const add = el("button", "+ salvar a configuração atual como topologia"); add.style.margin = "6px";
    add.onclick = () => {
      const nome = (prompt("Nome curto para esta topologia (ex: biplano, asa_voadora):") || "").trim();
      if (!nome) return;
      if (v.arvore.some(s => s.nome === nome)) { msg("Já existe uma topologia com esse nome.", true); return; }
      if (!esq || !esq.elementos.length) { msg("Carregue ou desenhe uma aeronave na etapa 1.", true); return; }
      if (!v.variaveis.length) { msg("Adicione ao menos uma variável em “Variáveis” antes de salvar.", true); return; }
      try { montaProblema(); } catch (e) { msg("Problema inválido: " + e.message, true); return; }
      v.arvore.push(snapshotAtual(nome)); guarda(); pintaSecao(); painelExecucao();
      msg(`Topologia “${nome}” salva. Troque a aeronave na etapa 1 e ajuste o problema para a próxima.`);
    };
    C.append(add);
    if (v.arvore.length) {
      const G = document.createElement("div"); G.className = "prop"; G.style.margin = "6px";
      const sel = document.createElement("select"); sel.add(new Option("(nenhuma — sorteia tudo do zero)", ""));
      v.arvore.forEach(snap => sel.add(new Option(snap.nome, snap.nome)));
      sel.value = v.arvoreSemente || ""; sel.onchange = () => { v.arvoreSemente = sel.value; guarda(); };
      G.append(el("label", "Semear a busca com"), sel); C.append(G);
      C.append(nota("Semear usa a aeronave salva na topologia escolhida como primeiro indivíduo dela, em vez de sortear — as outras topologias continuam exploradas do zero."));
    }
  }

  function montaProblema() {
    const base = JSON.parse(JSON.stringify(esq));
    let extra = {};
    if (v.avancado && v.avancado.trim()) {
      try { extra = JSON.parse(v.avancado); } catch (e) { throw new Error("JSON avançado inválido: " + e.message); }
    }
    if (!v.variaveis.every(x => x.nome && x.alvo)) throw new Error("Toda variável precisa de nome e alvo.");
    const ligacoes = v.variaveis.map(x => ({ alvo: x.alvo, formula: x.nome })).concat(extra.ligacoes || []);
    const variaveis = v.variaveis.map(x => ({ nome: x.nome, minimo: +x.minimo, maximo: +x.maximo, padrao: +x.padrao }));
    const malha = v.analise.malha_rapida !== false ? { n_span: +(v.analise.n_span ?? 12), n_chord: +(v.analise.n_chord ?? 2) } : undefined;
    const analiseBase = {};
    AN_CAMPOS.forEach(c => { const val = v.analise[c.k]; if (val !== undefined && val !== "" && val !== null) analiseBase[c.k] = val; });
    const { ligacoes: _l, analise: _a, base: _b, variaveis: _v, restricoes: _r, regra: _rg, cenario: _c, ...resto } = extra;
    const P = Padroes.get;
    const cargas = { Vc: P("estrutura.V_c"), Vd: P("estrutura.V_d"), U_c: P("estrutura.rajada_Vc"), U_d: P("estrutura.rajada_Vd"), fator_seguranca: P("estrutura.fator_seguranca") };
    Object.keys(cargas).forEach(k => { if (cargas[k] === undefined || cargas[k] === null) delete cargas[k]; });
    const analise = Object.assign({}, analiseBase, { cargas }, malha ? { malha } : {}, extra.analise || {});
    return Object.assign({ base, variaveis, ligacoes, restricoes: v.restricoes.filter(x => x.nome && x.formula), regra: v.regraJson || undefined, cenario: v.cenario }, resto, { analise });
  }

  function painelExecucao() {
    const P = $("par4"); P.innerHTML = "";
    const G = document.createElement("div"); G.className = "prop";
    const campo = (rot, chave, extra) => { const i = entrada("number", v.execucao[chave], x => { v.execucao[chave] = x; guarda(); }, extra || {}); G.append(el("label", rot), i); };
    campo("População", "populacao", { min: 4, max: 300, step: 1 });
    campo("Gerações", "geracoes", { min: 1, max: 500, step: 1 });
    campo("Semente", "semente", { step: 1 });
    const l = el("label", "Estratégia"); const sel = document.createElement("select");
    [["melhor", "melhor (rand-to-best)"], ["aleatoria", "aleatória (rand/1)"]].forEach(([k, n]) => sel.add(new Option(n, k)));
    sel.value = v.execucao.estrategia; sel.onchange = () => { v.execucao.estrategia = sel.value; guarda(); };
    l.style.gridColumn = "1 / -1"; sel.style.gridColumn = "1 / -1";
    sel.title = "melhor (rand-to-best): converge mais rápido. aleatória (rand/1): explora mais o espaço de projeto.";
    G.append(l, sel);
    P.append(G);
    P.append(nota("Roda em vários núcleos (um a menos que a máquina tem) nesta mesma tela."));
    if ((v.arvore || []).length >= 2) P.append(nota(`Árvore ativa: escolhe entre ${v.arvore.length} topologias (${v.arvore.map(s => s.nome).join(", ")}).`));
    const btns = document.createElement("div"); btns.style.cssText = "padding:4px 8px;display:flex;gap:6px";
    const bIni = el("button", (v.arvore || []).length >= 2 ? "Iniciar árvore" : "Iniciar"); bIni.id = "b_otim_ini"; bIni.onclick = iniciar;
    const bPar = el("button", "Parar"); bPar.id = "b_otim_par"; bPar.onclick = parar;
    btns.append(bIni, bPar); P.append(btns);
    atualizaBotoes();
  }

  function atualizaBotoes() {
    const rodando = !!(ultimoEstado && ultimoEstado.estado === "rodando");
    const bIni = $("b_otim_ini"), bPar = $("b_otim_par");
    if (bIni) bIni.disabled = rodando;
    if (bPar) bPar.disabled = !rodando;
  }

  function iniciar() {
    if ((v.arvore || []).length >= 2) return iniciarArvore();
    if (!esq || !esq.elementos.length) { msg("Carregue ou desenhe uma aeronave na etapa 1.", true); return; }
    if (!v.variaveis.length) { msg("Adicione ao menos uma variável em “Variáveis”.", true); return; }
    let problema;
    try { problema = montaProblema(); } catch (e) { msg(e.message, true); return; }
    chama("/api/otimiza/inicia", { problema, execucao: v.execucao }).then(r => {
      jobId = r.id; ultimoEstado = null; v.ultimoProblema = problema; guarda();
      msg("Otimização iniciada."); atualizaBotoes(); renderVeredito(); renderGraficos();
      clearInterval(poll); poll = setInterval(consulta, 1000); consulta();
    }).catch(e => msg(e.message, true));
  }

  function iniciarArvore() {
    let topologias;
    try {
      topologias = {};
      for (const snap of v.arvore) topologias[snap.nome] = montaProblemaDeSnapshot(snap);
    } catch (e) { msg(e.message, true); return; }
    const corpo = { topologias, execucao: v.execucao };
    if (v.arvoreSemente) {
      const semente = v.arvore.find(s => s.nome === v.arvoreSemente);
      if (semente) corpo.semear = { topologia: semente.nome, esq: semente.esq };
    }
    chama("/api/otimiza/inicia_arvore", corpo).then(r => {
      jobId = r.id; ultimoEstado = null; v.ultimoProblema = topologias; guarda();
      msg("Árvore de topologias iniciada."); atualizaBotoes(); renderVeredito(); renderGraficos();
      clearInterval(poll); poll = setInterval(consulta, 1000); consulta();
    }).catch(e => msg(e.message, true));
  }

  function parar() {
    if (!jobId) return;
    chama("/api/otimiza/para", { id: jobId }).catch(e => msg(e.message, true));
  }

  async function consulta() {
    if (!jobId) return;
    try {
      const r = await chama("/api/otimiza/estado?id=" + encodeURIComponent(jobId));
      ultimoEstado = r; renderVeredito(); renderGraficos(); atualizaBotoes();
      if (r.estado !== "rodando") {
        clearInterval(poll); poll = null;
        if (r.estado === "concluido") msg("Otimização concluída. Veja a etapa 5.");
        else if (r.estado === "erro") msg("Erro na otimização: " + r.erro, true);
        else msg("Otimização interrompida.");
      }
    } catch (e) { clearInterval(poll); poll = null; msg(e.message, true); }
  }

  const LEGENDA = { rodando: "Rodando…", concluido: "Concluída", parado: "Interrompida", erro: "Erro" };

  function renderVeredito() {
    const V = $("veredito4"); V.hidden = false;
    if (!ultimoEstado) { V.className = "veredito neutro"; V.textContent = "Ajuste o problema à esquerda e clique em Iniciar."; return; }
    const h = ultimoEstado.historico, ult = h.length ? h[h.length - 1] : null;
    const ocupado = ultimoEstado.estado === "rodando" && !ult;
    V.className = "veredito " + (ultimoEstado.estado === "concluido" ? "ok" : ultimoEstado.estado === "erro" ? "ruim" : "neutro") + (ocupado ? " ocupado" : "");
    V.innerHTML = `<b>${LEGENDA[ultimoEstado.estado] || ultimoEstado.estado}</b>`
      + (ult ? ` · geração ${ult.geracao}/${ultimoEstado.geracoes_total} · melhor <b>${fmt(ult.melhor_objetivo, 2)}</b> (${ult.melhor_viavel ? "viável" : "inviável"})`
            + ` · ${ult.n_viaveis} viáveis · diversidade ${fmt(ult.diversidade, 2)} · ${fmt(ultimoEstado.tempo_s, 0)} s`
            : (ocupado ? ` · avaliando a primeira geração (${fmt(ultimoEstado.tempo_s, 0)} s)…` : ""))
      + (ultimoEstado.erro ? ` · ${ultimoEstado.erro}` : "");
  }

  function renderGraficos() {
    const C = $("graficos4");
    if (!C._a) { C.innerHTML = ""; C._a = el("div", "", "graf"); C._b = el("div", "", "graf"); C.append(C._a, C._b); }
    const h = (ultimoEstado && ultimoEstado.historico) || [];
    const xs = h.map(r => r.geracao);
    C.parentElement.classList.toggle("vazio", !h.length);
    const desenhaTudo = () => {
      Grafico.desenha(C._a, {
        vazio: "A curva aparece quando a otimização começar", titulo: "Pontuação por geração", xlab: "geração", ylab: "pontuação",
        series: [{ nome: "melhor", x: xs, y: h.map(r => r.melhor_objetivo), cor: "#4a86c5" }, { nome: "média (viáveis)", x: xs, y: h.map(r => r.media_objetivo), cor: "#6aa84f" }],
      });
      Grafico.desenha(C._b, {
        vazio: "A diversidade aparece quando a otimização começar", titulo: "Diversidade da população", xlab: "geração", ylab: "diversidade", yMin: 0,
        series: [{ nome: "diversidade", x: xs, y: h.map(r => r.diversidade), cor: "#d98a3d" }],
      });
    };
    desenhaTudo();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (Etapas && document.body.dataset.etapa === "4") desenhaTudo(); }); }
  }

  return {
    entra() {
      lista(); pintaSecao(); painelExecucao(); renderVeredito(); renderGraficos();
      if (jobId && !poll && ultimoEstado && ultimoEstado.estado === "rodando") { poll = setInterval(consulta, 1000); consulta(); }
    },
    ultimoProblema: () => v.ultimoProblema,
    ultimoEstado: () => ultimoEstado,
  };
})();
