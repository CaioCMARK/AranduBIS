"use strict";

const Estrutura = (() => {
  let MATERIAIS = ["balsa"];
  fetch("/api/materiais").then(r => r.json()).then(d => { MATERIAIS = d.materiais.map(m => m.nome); }).catch(() => {});

  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function selecao(valor, opcoes, ao) {
    const s = document.createElement("select");
    opcoes.forEach(o => s.add(new Option(o, o)));
    s.value = valor;
    s.onchange = () => ao(s.value);
    return s;
  }

  function bloco(C, titulo) {
    const b = el("div", "", "bloco"); b.append(el("h5", titulo)); C.append(b); return b;
  }

  function tabela(B, cabecalho, linhas, ao_remover) {
    const t = document.createElement("table");
    const h = document.createElement("tr");
    cabecalho.forEach(c => h.append(el("th", c)));
    h.append(el("th")); t.append(h);
    linhas.forEach((cels, i) => {
      const tr = document.createElement("tr");
      cels.forEach(c => { const td = document.createElement("td"); td.append(c); tr.append(td); });
      const rm = document.createElement("td"), b = el("button", "✕"); b.title = "Remover";
      b.onclick = () => ao_remover(i); rm.append(b); tr.append(rm); t.append(tr);
    });
    B.append(t);
  }

  const est = e => e.estrutura || (e.estrutura = {});
  const lista = (o, k) => (o[k] || []).join(" ");
  function textoLista(o, k, ao) {
    const w = entrada("text", lista(o, k), v => {
      const n = v.trim() ? v.trim().split(/[\s,;]+/).map(parseFloat) : [];
      if (n.some(Number.isNaN)) { msg("Use números separados por espaço.", true); return; }
      ao(n);
    });
    w.style.textAlign = "left";
    return w;
  }

  const LEIS = { uniforme: "uniforme", raiz: "mais densa na raiz", ponta: "mais densa na ponta", secoes: "nas seções do modelo" };
  const iguais = (a, b) => Math.abs(a - b) < 1e-6;

  function limitesY(e) {
    const ys = (e.secoes || []).map(s => s.y).filter(v => typeof v === "number");
    if (!ys.length) return null;
    const lo = Math.min(...ys), hi = Math.max(...ys), simetrica = lo < 0 && hi > 0 && iguais(-lo, hi);
    return { lo: simetrica ? 0 : lo, hi, simetrica };
  }

  function nervuras(C, e) {
    const B = bloco(C, "Nervuras"), n = (e.estrutura || {}).nervuras || { y: [], espessura: 0.00238, material: "balsa" }, liga = () => { est(e).nervuras = n; };
    const lim = limitesY(e), refaz = () => abaConteudo();
    const g = el("div", "", "prop"); B.append(g);
    linha(g, "espessura (m)", entrada("number", n.espessura, v => muda(() => { liga(); n.espessura = v; })));
    linha(g, "material", selecao(n.material || "balsa", MATERIAIS, v => muda(() => { liga(); n.material = v; })));
    linha(g, "ângulo das nervuras (°)", entrada("number", n.angulo ?? 0, v => { if (v === null || Math.abs(v) >= 80) { msg("O ângulo deve ficar entre -80° e 80°.", true); refaz(); return; } muda(() => { liga(); n.angulo = v; }); refaz(); }));
    g.lastChild.title = "Giro das nervuras em planta, em torno do eixo vertical a 25 % da corda. 0° = nervura alinhada ao escoamento. As nervuras da raiz e da ponta ficam retas.";
    linha(g, "passo máximo (mm)", entrada("number", n.passo_max_mm ?? "", v => { muda(() => { liga(); if (v === null || v <= 0) delete n.passo_max_mm; else n.passo_max_mm = v; }); refaz(); }));
    g.lastChild.title = "Distância máxima entre nervuras vizinhas que você aceita (depende do entelamento ou do chapeado). Acima dela o programa avisa. Vazio = sem aviso.";

    const bed = el("button", Nervura3D.ativo() ? "Terminar edição na vista 3D" : "Editar na vista 3D");
    bed.title = "Arraste as nervuras ao longo da envergadura na vista 3D, gire com Q/E, crie com Ctrl+clique e remova com Delete.";
    bed.onclick = () => { Nervura3D.liga(!Nervura3D.ativo()); refaz(); };
    if (document.documentElement.dataset.interface !== "nova") B.append(bed);
    const gg = el("div", "", "prop"); gg.style.borderTop = "1px solid var(--linha)"; B.append(gg);
    let qtd = n.y && n.y.length ? n.y.length : 8, lei = "uniforme";
    linha(gg, lim && lim.simetrica ? "quantidade por semi-asa" : "quantidade na asa", entrada("number", qtd, v => { if (v !== null && v >= 2) qtd = Math.round(v); }));
    const sl = selecao(LEIS[lei], Object.values(LEIS), v => { lei = Object.keys(LEIS).find(k => LEIS[k] === v); });
    linha(gg, "distribuição", sl);
    const bg = el("button", "Gerar posições");
    bg.title = "Substitui a lista abaixo por posições calculadas com a quantidade e a distribuição escolhidas.";
    bg.onclick = async () => {
      try {
        const r = await chama("/api/nervuras/posicoes", { esquema: esq, asa: e.nome, n: qtd, lei });
        if (r.erro) { msg(r.erro, true); return; }
        muda(() => { liga(); n.y = r.y; n.angulos = (n.angulos || []).filter(a => r.y.some(y => iguais(y, a[0]))); });
        refaz();
      } catch (x) { msg(x.message, true); }
    };
    gg.append(el("label", ""), bg);

    const ordem = (n.y || []).map((y, k) => k).sort((a, b) => n.y[a] - n.y[b]);
    const angDe = y => { const a = (n.angulos || []).find(q => iguais(q[0], y)); return a ? a[1] : ""; };
    const linhas = ordem.map(k => {
      const y = n.y[k];
      const ey = entrada("number", +y.toFixed(4), v => {
        if (v === null || (lim && (v < lim.lo - 1e-9 || v > lim.hi + 1e-9))) { msg(lim ? `A posição deve ficar entre ${+lim.lo.toFixed(3)} e ${+lim.hi.toFixed(3)} m.` : "Posição inválida.", true); refaz(); return; }
        muda(() => { liga(); const antigo = n.y[k]; n.y[k] = v; (n.angulos || []).forEach(a => { if (iguais(a[0], antigo)) a[0] = v; }); }); refaz();
      });
      const ea = entrada("number", angDe(y), v => {
        if (v !== null && Math.abs(v) >= 80) { msg("O ângulo deve ficar entre -80° e 80°.", true); refaz(); return; }
        muda(() => { liga(); n.angulos = (n.angulos || []).filter(a => !iguais(a[0], n.y[k])); if (v !== null) n.angulos.push([n.y[k], v]); if (!n.angulos.length) delete n.angulos; }); refaz();
      });
      ea.placeholder = String(n.angulo ?? 0); ea.title = "Vazio = usa o ângulo geral.";
      return [ey, ea];
    });
    if (linhas.length) tabela(B, ["y (m)", "ângulo (°)"], linhas, i => { muda(() => { const y = n.y[ordem[i]]; n.y.splice(ordem[i], 1); n.angulos = (n.angulos || []).filter(a => !iguais(a[0], y)); if (!n.angulos.length) delete n.angulos; }); refaz(); });
    else B.append(el("div", "Nenhuma nervura. Gere posições acima ou adicione uma.", "nota"));

    const ba = el("button", "+ nervura"); ba.title = "Adiciona uma nervura no meio do maior vão entre nervuras.";
    ba.onclick = () => {
      if (!lim) { msg("A asa não tem seções.", true); return; }
      const pts = [...new Set([lim.lo, ...(n.y || []).filter(v => v >= lim.lo - 1e-9 && v <= lim.hi + 1e-9), lim.hi].map(v => +v.toFixed(6)))].sort((a, b) => a - b);
      let k = 0; for (let i = 1; i + 1 < pts.length; i++) if (pts[i + 1] - pts[i] > pts[k + 1] - pts[k]) k = i;
      const y = +(0.5 * (pts[k] + pts[k + 1])).toFixed(4);
      muda(() => { liga(); n.y = [...(n.y || []), y]; }); refaz();
    };
    B.append(ba);

    const info = el("div", "", "nota"); B.append(info);
    if (n.y && n.y.length) chama("/api/nervuras/posicoes", { esquema: esq, asa: e.nome, y: n.y }).then(r => {
      if (r.erro) { info.textContent = r.erro; return; }
      const mmf = v => Math.round(v);
      let txt = `${r.n_total} nervuras no total (inclui as pontas${r.simetrica ? " e o lado espelhado" : ""}) · distância entre nervuras de ${mmf(r.passo_min_mm)} a ${mmf(r.passo_max_mm)} mm.`;
      if (n.passo_max_mm && r.passo_max_mm > n.passo_max_mm + 1e-6) { txt += ` Atenção: o maior vão (${mmf(r.passo_max_mm)} mm) passa do passo máximo de ${n.passo_max_mm} mm.`; info.style.color = "var(--aviso, #d98a3d)"; }
      info.textContent = txt;
    }).catch(() => {});
    B.append(el("div", lim && lim.simetrica ? "Informe só o lado positivo (de 0 até a ponta): o programa espelha na asa simétrica e já coloca nervuras nas pontas." : "Informe as posições y ao longo da asa; as pontas ganham nervura automaticamente.", "nota"));
  }

  const TIPOS_LG = { alma: "Alma + tubinhos", tubo: "Tubo (carbono)", caixao: "Viga caixão / I" };
  const NOVA_LG = {
    alma: () => ({ tipo: "alma", xc: 0.25, largura: 0.00238, material: "balsa" }),
    tubo: () => ({ tipo: "tubo", xc: 0.25, de: 0.012, di: 0.010, material: "tubo_carbono" }),
    caixao: () => ({ tipo: "caixao", xc: 0.25, largura_caixa: 0.02, n_almas: 2, espessura_alma: 0.0016, material_alma: "balsa",
                     espessura_mesa: 0.003, material_mesa: "spruce" }),
  };
  const mm = v => v === undefined || v === null || v === "" ? "" : +(1000 * v).toFixed(3);
  const deMm = v => v === "" || v === null ? undefined : v / 1000;

  function longarinas(C, e) {
    const B = bloco(C, "Longarinas"), L = (e.estrutura || {}).longarinas || [];
    L.forEach((l, i) => {
      const t = l.tipo || "alma", g = el("div", "", "prop"); g.style.borderTop = "1px solid var(--linha)"; B.append(g);
      linha(g, `longarina ${i + 1}`, selecao(t, Object.keys(TIPOS_LG), v => { muda(() => { const n = NOVA_LG[v](); Object.keys(l).forEach(k => { if (!["x", "xc", "xc_y", "y"].includes(k)) delete l[k]; }); Object.assign(l, n, { xc: l.xc ?? n.xc }); if (l.x !== undefined || l.xc_y) delete l.xc; }); abaConteudo(); }));
      g.lastChild.querySelector && Array.from(g.querySelectorAll("select option")).forEach(o => { o.textContent = TIPOS_LG[o.value] || o.value; });
      if (l.xc_y) linha(g, "posição", el("span", "varia com y (xc_y no arquivo)"));
      else if (l.x !== undefined) linha(g, "x do BA (m)", entrada("number", l.x, v => muda(() => { l.x = v; })));
      else linha(g, "posição (x/c)", entrada("number", l.xc, v => muda(() => { l.xc = v; })));
      if (t === "alma") {
        linha(g, "espessura da alma (mm)", entrada("number", mm(l.largura), v => muda(() => { l.largura = deMm(v); })));
        linha(g, "material", selecao(l.material || "balsa", MATERIAIS, v => muda(() => { l.material = v; })));
      } else if (t === "tubo") {
        linha(g, "Ø externo (mm)", entrada("number", mm(l.de), v => muda(() => { l.de = deMm(v); })));
        linha(g, "Ø interno (mm)", entrada("number", mm(l.di), v => muda(() => { l.di = deMm(v); })));
        linha(g, "altura no perfil", selecao(l.lado || "meio", ["meio", "extradorso", "intradorso"], v => muda(() => { l.lado = v; })));
        linha(g, "material", selecao(l.material || "tubo_carbono", MATERIAIS, v => muda(() => { l.material = v; })));
      } else {
        linha(g, "almas", selecao(String(l.n_almas ?? 2), ["2", "1"], v => muda(() => { l.n_almas = +v; })));
        g.lastChild.querySelectorAll && g.lastChild.querySelectorAll("option").forEach(o => { o.textContent = o.value === "2" ? "2 (caixão)" : "1 (viga I)"; });
        linha(g, "largura da caixa (mm)", entrada("number", mm(l.largura_caixa), v => muda(() => { l.largura_caixa = deMm(v); })));
        linha(g, "espessura da alma (mm)", entrada("number", mm(l.espessura_alma), v => muda(() => { l.espessura_alma = deMm(v); })));
        linha(g, "material da alma", selecao(l.material_alma || "balsa", MATERIAIS, v => muda(() => { l.material_alma = v; })));
        linha(g, "espessura da mesa (mm)", entrada("number", mm(l.espessura_mesa), v => muda(() => { l.espessura_mesa = deMm(v); })));
        linha(g, "largura da mesa (mm)", entrada("number", mm(l.largura_mesa ?? l.largura_caixa), v => muda(() => { l.largura_mesa = deMm(v); })));
        linha(g, "material da mesa", selecao(l.material_mesa || "spruce", MATERIAIS, v => muda(() => { l.material_mesa = v; })));
      }
      linha(g, "y de / até (m)", (() => { const w = el("span"); w.style.display = "flex"; w.style.gap = "4px";
        w.append(entrada("number", (l.y || ["", ""])[0], v => muda(() => { l.y = [v, (l.y || [0, 0])[1]]; if (l.y.every(q => q === "" || q === null)) delete l.y; })),
                 entrada("number", (l.y || ["", ""])[1], v => muda(() => { l.y = [(l.y || [0, 0])[0], v]; })));
        return w; })());
      const rm = el("button", "remover esta longarina"); rm.onclick = () => { muda(() => L.splice(i, 1)); abaConteudo(); }; g.append(rm);
    });
    const novo = selecao("", ["", ...Object.keys(TIPOS_LG)], v => { if (!v) return; muda(() => { est(e).longarinas = L; L.push(NOVA_LG[v]()); }); abaConteudo(); });
    novo.options[0].textContent = "+ longarina…"; Array.from(novo.options).slice(1).forEach(o => { o.textContent = TIPOS_LG[o.value]; });
    B.append(novo);
    B.append(el("div", "Alma + tubinhos: alma de madeira na altura do perfil com os tubos de reforço abaixo. Tubo: um tubo passando pela asa. Viga caixão: duas almas e duas mesas (com uma alma, viga I). y vazio = de ponta a ponta.", "nota"));
  }

  function tubos(C, e) {
    const B = bloco(C, "Tubos de reforço (tubinhos)"), L = (e.estrutura || {}).tubos || [];
    tabela(B, ["x (m)", "lado", "Ø ext (m)", "Ø int (m)", "y de", "y até"], L.map(t => [
      entrada("number", t.x, v => muda(() => { t.x = v; })),
      selecao(t.lado || "extradorso", ["extradorso", "intradorso", "meio"], v => muda(() => { t.lado = v; })),
      entrada("number", t.de, v => muda(() => { t.de = v; })),
      entrada("number", t.di, v => muda(() => { t.di = v; })),
      entrada("number", (t.y || [0, 0])[0], v => muda(() => { t.y = [v, (t.y || [0, 0])[1]]; })),
      entrada("number", (t.y || [0, 0])[1], v => muda(() => { t.y = [(t.y || [0, 0])[0], v]; }))]),
      i => { muda(() => L.splice(i, 1)); abaConteudo(); });
    const b = el("button", "+ tubo");
    b.onclick = () => { muda(() => { est(e).tubos = L; L.push({ x: 0.07, lado: "extradorso", de: 0.003, di: 0.002, y: [0, 0.5] }); }); abaConteudo(); };
    B.append(b);
  }

  function chapeado(C, e) {
    const B = bloco(C, "Chapeado"), ch = (e.estrutura || {}).chapeado;
    const on = el("label"); const cx = document.createElement("input"); cx.type = "checkbox"; cx.checked = !!ch;
    on.append(cx, " ter chapeado"); B.append(on);
    cx.onchange = () => { muda(() => { if (cx.checked) est(e).chapeado = { ate_xc: 0.25, espessura: 0.001, material: "balsa" }; else delete est(e).chapeado; }); abaConteudo(); };
    if (!ch) return;
    const g = el("div", "", "prop"); B.append(g);
    linha(g, "até x/c", entrada("number", ch.ate_xc, v => muda(() => { ch.ate_xc = v; })));
    linha(g, "espessura (m)", entrada("number", ch.espessura, v => muda(() => { ch.espessura = v; })));
    linha(g, "material", selecao(ch.material || "balsa", MATERIAIS, v => muda(() => { ch.material = v; })));
  }

  const DOBRADICAS = { "": "— (não declarada)", fita: "Fita adesiva ou filme", chanfro: "Fita com chanfro triangular", batente: "Chapeado rolando sobre o batente (chapa vertical)", flexivel: "Charneira viva (pele ou filme)", pino: "Dobradiça de nylon com pino", pivo: "Pivô: a longarina é o tubo-eixo (all-moving)" };

  function selecaoRotulos(valor, mapa, ao) {
    const s = document.createElement("select");
    Object.entries(mapa).forEach(([k, r]) => s.add(new Option(r, k)));
    s.value = valor; s.onchange = () => ao(s.value); return s;
  }

  function comandos(C, e) {
    const B = bloco(C, "Superfícies de comando"), L = e.controles || [];
    B.append(el("div", "Cada comando é um trecho da envergadura com eixo (charneira). Para um estabilizador inteiro móvel (all-moving) marque “gira inteira”; para um pedaço que age como aileron, deixe desmarcado e defina o trecho. Valores sem dado do desenho são hipóteses.", "nota"));
    L.forEach((c, i) => {
      const card = el("div", "", "bloco"), g = el("div", "", "prop"); card.append(g);
      const l = (r, w, dica) => { const a = el("label", r); if (dica) a.title = dica; g.append(a, w); };
      const eixo = "x" in c ? "x" : "corda" in c ? "corda" : "xc";
      const rm = el("button", "✕ remover"); rm.onclick = () => { muda(() => { L.splice(i, 1); if (!L.length) delete e.controles; }); abaConteudo(); };
      const cab = el("div"); cab.append(el("b", c.nome + "  "), rm); card.prepend(cab);
      l("nome", entrada("text", c.nome, v => muda(() => { c.nome = v; })));
      l("y de (m)", entrada("number", c.y[0], v => muda(() => { c.y = [v ?? 0, c.y[1]]; })), "Em |y|: vale para os dois lados");
      l("y até (m)", entrada("number", c.y[1], v => muda(() => { c.y = [c.y[0], v ?? 0]; })));
      l("eixo definido por", selecaoRotulos(eixo, { corda: "corda da superfície (m)", x: "x da charneira (m), reto", xc: "fração da corda" }, v => muda(() => {
        const val = c.x ?? c.corda ?? c.xc ?? 0.75; delete c.x; delete c.corda; delete c.xc;
        c[v] = v === "xc" ? 0.75 : v === "x" ? +(val > 1 ? val : 0.2).toFixed(4) : 0.06; }) ), "x: eixo reto e paralelo à longarina (corda varia). corda: eixo paralelo ao bordo de fuga.");
      l("valor do eixo", entrada("number", c[eixo], v => muda(() => { c[eixo] = v; })));
      l("modo", selecaoRotulos(c.modo || "sim", { sim: "simétrico (profundor, flape)", anti: "diferencial (aileron)", lado: "só um lado (leme de meia deriva)" }, v => muda(() => { c.modo = v; })));
      l("deflexão (°)", entrada("number", c.deflexao || 0, v => muda(() => { c.deflexao = v ?? 0; })), "Positivo desce o bordo de fuga");
      l("batente (°)", entrada("number", c.limite ?? "", v => muda(() => { if (v === null) delete c.limite; else c.limite = v; })));
      l("altura do eixo", selecaoRotulos(c.charneira || "meio", { meio: "meio do perfil", extradorso: "extradorso", intradorso: "intradorso" }, v => muda(() => { c.charneira = v; })));
      const mv = document.createElement("input"); mv.type = "checkbox"; mv.checked = !!c.movel; mv.onchange = () => muda(() => { if (mv.checked) c.movel = true; else delete c.movel; });
      l("gira inteira", mv, "All-moving: a seção inteira gira em torno do eixo");
      l("dobradiça", selecaoRotulos(c.dobradica || "", DOBRADICAS, v => muda(() => { if (v) c.dobradica = v; else delete c.dobradica; })), "Entra na massa (g por metro de charneira, hipótese do catálogo)");
      if (c.dobradica) l("massa (g/m)", entrada("number", c.massa_g_m ?? "", v => muda(() => { if (v === null) delete c.massa_g_m; else c.massa_g_m = v; })), "Vazio: usa o valor do catálogo");
      B.append(card);
    });
    const b = el("button", "+ comando");
    b.onclick = () => {
      const ymax = Math.max(...(e.secoes || [{ y: 1 }]).map(s => Math.abs(s.y)));
      muda(() => { e.controles = L; L.push({ nome: nomeUnicoComando(e), y: [+(0.6 * ymax).toFixed(3), +(0.95 * ymax).toFixed(3)], corda: 0.06, deflexao: 0, modo: "anti", charneira: "meio" }); }); abaConteudo();
    };
    B.append(b);
  }

  const nomeUnicoComando = e => { let n = 1; const u = new Set((e.controles || []).map(c => c.nome)); while (u.has("comando_" + n)) n++; return "comando_" + n; };

  return {
    pinta(C, e) {
      if ((e.tipo || "asa") !== "asa") return C.append(el("div", "Estrutura interna só existe para asas.", "nota"));
      nervuras(C, e); longarinas(C, e); tubos(C, e); chapeado(C, e); comandos(C, e);
      const nota = el("div", "As peças de estrutura aparecem na camada “estrutura” da vista e entram na massa e no CG.", "nota");
      C.append(nota);
    },
  };
})();
