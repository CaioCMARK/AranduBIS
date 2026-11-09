"use strict";

const Pontuacao = (() => {
  const CH_REGRA = "aranduBIS.regra", CH_VAL = "aranduBIS.regraValores";
  let R = null, valores = {}, out = null, aba = "Itens", tempo = null, seq = 0, lista = [];

  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const guarda = () => { try { localStorage.setItem(CH_REGRA, JSON.stringify(R)); localStorage.setItem(CH_VAL, JSON.stringify(valores)); } catch (e) {  } };

  async function inicia() {
    try { R = JSON.parse(localStorage.getItem(CH_REGRA) || "null"); valores = JSON.parse(localStorage.getItem(CH_VAL) || "{}"); } catch (e) { R = null; }
    lista = (await chama("/api/regras")).regras;
    if (!R || !Array.isArray(R.itens)) {
      const f = lista[0];
      R = f ? await chama(`/api/regra?nome=${encodeURIComponent(f.nome)}&origem=${f.origem}`) : await vazia();
    }
  }

  const vazia = async () => ({ versao: 1, nome: "Nova regra", ano: 0, classe: "", fonte: "", constantes: {}, entradas: [], grandezas: [], itens: [], so_conta_se: "" });

  function agenda() { guarda(); clearTimeout(tempo); tempo = setTimeout(calcula, 200); }

  async function calcula() {
    const meu = ++seq;
    try {
      const r = await chama("/api/regra/avalia", { regra: R, valores });
      if (meu !== seq) return;
      out = r; msg(r.problemas.length ? "A regra tem problemas: veja a lista abaixo." : "Pronto", !!r.problemas.length);
    } catch (e) { if (meu !== seq) return; out = null; msg(e.message, true); }
    resultado(); baixo();
  }

  function cabecalho() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito neutro"; V.innerHTML = "";
    const s = document.createElement("select"); s.title = "Regras de pontuação";
    s.add(new Option("Escolher regra…", ""));
    lista.forEach(r => s.add(new Option(`${r.nome} (${r.origem === "fabrica" ? "de fábrica" : "da equipe"})`, JSON.stringify(r))));
    s.onchange = async () => {
      if (!s.value) return; const r = JSON.parse(s.value);
      if (!confirm("Trocar de regra descarta as edições não salvas. Continuar?")) { s.value = ""; return; }
      R = await chama(`/api/regra?nome=${encodeURIComponent(r.nome)}&origem=${r.origem}`); guarda(); pinta();
    };
    const novo = el("button", "Nova regra"); novo.onclick = async () => { if (confirm("Começar uma regra vazia?")) { R = await vazia(); guarda(); pinta(); } };
    const salva = el("button", "Salvar como…");
    salva.onclick = async () => {
      const n = prompt("Nome do arquivo (letras, números, _ e -):", (R.nome || "regra").toLowerCase().replace(/[^a-z0-9]+/g, "_"));
      if (!n) return;
      try { const r = await chama("/api/regra/grava", { regra: R, nome: n }); msg("Regra gravada em " + r.caminho); lista = (await chama("/api/regras")).regras; cabecalho(); } catch (e) { msg(e.message, true); }
    };
    const nome = document.createElement("input"); nome.value = R.nome; nome.title = "Nome da regra"; nome.className = "nome-regra";
    nome.onchange = () => { R.nome = nome.value; agenda(); };
    const total = el("span", "", "total"); total.id = "pont_total";
    V.append(nome, s, novo, salva, total);
    totalTxt();
  }

  function totalTxt() {
    const t = $("pont_total"); if (!t) return;
    t.innerHTML = out ? (out.conta ? `Pontuação: <b>${fmt(out.total, 2)}</b>` : "<b>Não conta</b>: a condição geral não foi atendida") : "";
  }

  function resultado() {
    totalTxt();
    const C = $("graficos2"); C.innerHTML = ""; C.className = "graficos coluna";
    if (!out) return;
    const maior = Math.max(1e-9, ...out.itens.filter(i => i.conta).map(i => i.valor));
    const t = document.createElement("table"); t.className = "res-pont";
    t.innerHTML = "<tr><th>item</th><th>valor</th><th></th><th>fórmula</th></tr>";
    out.itens.forEach(i => {
      const tr = document.createElement("tr"); if (!i.conta) tr.className = "apagado";
      const estado = i.erro ? `<span class="erro">${i.erro}</span>` : i.aplica ? "" : "não se aplica";
      tr.innerHTML = `<td>${i.nome}</td><td>${i.valor === null ? "—" : fmt(i.valor, 3)}</td>`
        + `<td class="barra-cel">${i.conta && i.valor > 0 ? `<span class="barra-valor" style="width:${Math.max(2, 100 * i.valor / maior)}%"></span>` : estado}</td>`
        + `<td class="formula">${i.formula}${i.quando ? ` <i>quando ${i.quando}</i>` : ""}</td>`;
      t.append(tr);
    });
    C.append(t);
    if (out.problemas.length) { const p = el("div", "", "aviso"); p.innerHTML = "<b>Problemas na regra</b><br>" + out.problemas.map(x => "• " + x).join("<br>"); C.append(p); }
  }

  function entradas() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Entradas da pontuação";
    if (!R.entradas.length) { P.append(el("div", "Esta regra não tem entradas. Crie na aba Entradas.", "nota")); return; }
    const G = el("div", "", "prop"); P.append(G);
    R.entradas.forEach(e => {
      const l = el("label", e.nome + (e.unidade ? ` (${e.unidade})` : "")); l.title = e.descricao || "";
      const v = valores[e.nome] ?? e.padrao ?? 0;
      const i = entrada("number", v, x => { valores[e.nome] = x ?? 0; agenda(); }); i.title = e.descricao || "";
      G.append(l, i);
    });
    const dica = el("div", "", "nota");
    const b1 = el("button", "PV da geometria"), b2 = el("button", "CP = peso máx. − PV");
    b1.title = "Usa a massa total da aeronave desenhada como peso vazio (kg)";
    b1.onclick = () => { if (!malha) { msg("Construa uma aeronave na etapa 1.", true); return; } if (!R.entradas.some(e => e.nome === "PV")) { msg("Esta regra não tem a entrada PV.", true); return; } valores.PV = +malha.massa_kg.toFixed(3); entradas(); agenda(); };
    b2.title = "Carga paga = maior massa que passa o obstáculo (aba Decolagem) menos o peso vazio";
    b2.onclick = () => {
      const d = Decolagem.dados().res;
      if (!d || !d.massa_maxima.massa_kg) { msg("Rode a Decolagem primeiro (ela calcula o peso máximo).", true); return; }
      if (!R.entradas.some(e => e.nome === "CP_bruta")) { msg("Esta regra não tem a entrada CP_bruta.", true); return; }
      valores.CP_bruta = +Math.max(0, d.massa_maxima.massa_kg - (valores.PV || 0)).toFixed(3); entradas(); agenda();
    };
    dica.append(b1, b2); P.append(dica);
  }

  const celula = (valor, ao, tipo = "text", larg) => { const i = entrada(tipo, valor, ao); if (larg) i.style.minWidth = larg; i.style.textAlign = "left"; return i; };

  function tab(cols, linhas, remover) {
    const t = document.createElement("table"); t.className = "edita";
    const h = document.createElement("tr"); cols.forEach(c => h.append(el("th", c))); h.append(el("th")); t.append(h);
    linhas.forEach((cels, i) => {
      const tr = document.createElement("tr");
      cels.forEach(c => { const td = document.createElement("td"); td.append(c); tr.append(td); });
      const rm = document.createElement("td"), b = el("button", "✕"); b.title = "Remover"; b.onclick = () => remover(i); rm.append(b); tr.append(rm); t.append(tr);
    });
    return t;
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = "";
    ["Itens", "Grandezas", "Entradas", "Constantes", "Regra"].forEach(n => {
      const d = el("div", n, n === aba ? "at" : ""); d.onclick = () => { aba = n; baixo(); }; A.append(d);
    });
    const C = $("conteudo2"); C.innerHTML = "";
    const mexeu = () => { agenda(); entradas(); };
    const novoNome = (lst, base) => { let n = 1; const u = new Set(lst.map(x => x.nome)); while (u.has(base + n)) n++; return base + n; };
    if (aba === "Itens") {
      C.append(el("div", "Cada item é uma parcela da pontuação. “Quando” é opcional: o item só conta se a condição for verdadeira.", "nota"));
      C.append(tab(["nome", "fórmula", "quando", "descrição"], R.itens.map(i => [
        celula(i.nome, v => { i.nome = v; mexeu(); }, "text", "8em"), celula(i.formula, v => { i.formula = v; mexeu(); }, "text", "18em"),
        celula(i.quando, v => { i.quando = v; mexeu(); }, "text", "9em"), celula(i.descricao, v => { i.descricao = v; agenda(); }, "text", "16em")]),
        k => { R.itens.splice(k, 1); mexeu(); baixo(); }));
      const b = el("button", "+ item"); b.onclick = () => { R.itens.push({ nome: novoNome(R.itens, "item"), formula: "0", quando: "", descricao: "" }); mexeu(); baixo(); }; C.append(b);
    } else if (aba === "Grandezas") {
      C.append(el("div", "Valores intermediários, em ordem: cada um só enxerga as entradas, as constantes e as grandezas acima dele.", "nota"));
      C.append(tab(["nome", "fórmula", "un.", "descrição"], R.grandezas.map(g => [
        celula(g.nome, v => { g.nome = v; mexeu(); }, "text", "8em"), celula(g.formula, v => { g.formula = v; mexeu(); }, "text", "18em"),
        celula(g.unidade, v => { g.unidade = v; agenda(); }, "text", "4em"), celula(g.descricao, v => { g.descricao = v; agenda(); }, "text", "16em")]),
        k => { R.grandezas.splice(k, 1); mexeu(); baixo(); }));
      const b = el("button", "+ grandeza"); b.onclick = () => { R.grandezas.push({ nome: novoNome(R.grandezas, "g"), formula: "0", unidade: "", descricao: "" }); mexeu(); baixo(); }; C.append(b);
    } else if (aba === "Entradas") {
      C.append(el("div", "Entradas são o que você informa a cada avaliação (peso vazio, carga, tempo, apostas). O valor padrão vale até você mudar.", "nota"));
      C.append(tab(["nome", "padrão", "un.", "descrição"], R.entradas.map(e => [
        celula(e.nome, v => { e.nome = v; mexeu(); }, "text", "8em"), celula(e.padrao ?? 0, v => { e.padrao = v ?? 0; mexeu(); }, "number", "6em"),
        celula(e.unidade || "", v => { e.unidade = v; agenda(); }, "text", "4em"), celula(e.descricao || "", v => { e.descricao = v; agenda(); }, "text", "18em")]),
        k => { R.entradas.splice(k, 1); mexeu(); baixo(); }));
      const b = el("button", "+ entrada"); b.onclick = () => { R.entradas.push({ nome: novoNome(R.entradas, "x"), padrao: 0, unidade: "", descricao: "" }); mexeu(); baixo(); }; C.append(b);
    } else if (aba === "Constantes") {
      C.append(el("div", "Números fixos do regulamento (teto de peso, limites).", "nota"));
      const ks = Object.keys(R.constantes);
      C.append(tab(["nome", "valor"], ks.map(k => [
        celula(k, v => { if (v && v !== k) { R.constantes[v] = R.constantes[k]; delete R.constantes[k]; mexeu(); baixo(); } }, "text", "10em"),
        celula(R.constantes[k], v => { R.constantes[k] = v ?? 0; mexeu(); }, "number", "8em")]),
        i => { delete R.constantes[ks[i]]; mexeu(); baixo(); }));
      const b = el("button", "+ constante"); b.onclick = () => { let n = 1; while (("K" + n) in R.constantes) n++; R.constantes["K" + n] = 0; mexeu(); baixo(); }; C.append(b);
    } else {
      const g = el("div", "", "prop"); C.append(g);
      linha(g, "ano", entrada("number", R.ano || 0, v => { R.ano = v ?? 0; agenda(); }));
      linha(g, "classe", entrada("text", R.classe || "", v => { R.classe = v; agenda(); }));
      linha(g, "fonte (seção do regulamento)", entrada("text", R.fonte || "", v => { R.fonte = v; agenda(); }));
      linha(g, "só conta se (condição geral)", entrada("text", R.so_conta_se || "", v => { R.so_conta_se = v; agenda(); }));
      C.append(el("div", "Fórmulas aceitam contas, comparações, “a if cond else b” e as funções min, max, abs, trunc, floor, ceil, sqrt, exp, log. Nada de código.", "nota"));
    }
  }

  function pinta() {
    if (!R) { inicia().then(pinta).catch(e => msg(e.message, true)); return; }
    cabecalho(); entradas(); baixo(); $("graficos2").innerHTML = ""; calcula();
  }

  Analise.registra("pontuacao", { pinta });
  return {};
})();
