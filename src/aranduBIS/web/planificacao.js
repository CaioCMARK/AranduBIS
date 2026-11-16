"use strict";

const Planifica3 = (() => {
  const CHAVE = "aranduBIS.planificacao";
  let v = { asa: "", modo: "auto", n_vao: 6, limite_pct: 0, margem_cola_mm: 5, folha_largura_mm: 1000, folha_altura_mm: 300, espaco_mm: 6, moldura: true, rotulos: true, cortes_txt: "", modos: {} };
  let res = null, tempo = null, seq = 0, sel = null;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {}
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "planificacao";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {} };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, a) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); return e; };
  const COR = { ok: "#5fa86a", atencao: "#d6a93b", nao: "#c85a5a" };
  const ROTULO = { ok: "desdobra bem", atencao: "pede cuidado", nao: "emendar" };
  const MODOS = [["", "automático"], ["envolvente", "envolvendo o bordo de ataque"], ["separado", "extradorso e intradorso"]];

  function campo(P, rot, dica, k, min) {
    const l = el("label", rot); l.title = dica;
    const i = entrada("number", v[k], x => { if (x === null || x < (min ?? 0)) { msg("Valor inválido em “" + rot + "”.", true); return; } v[k] = x; guarda(); agenda(); });
    i.title = dica; P.append(l, i);
  }

  function cortesY() {
    return String(v.cortes_txt || "").split(/[\s,;]+/).map(Number).filter(x => isFinite(x) && x !== 0 && String(x) !== "");
  }

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Chapeado planificado";
    let G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Asa", "grupo-par"), G);
    const s = document.createElement("select");
    const asas = (esq && esq.elementos || []).filter(e => e.tipo === "asa" && e.estrutura && e.estrutura.chapeado).map(e => e.nome);
    asas.forEach(n => s.add(new Option(n, n))); s.value = asas.includes(v.asa) ? v.asa : (asas[0] || "");
    s.onchange = () => { v.asa = s.value; sel = null; v.modos = {}; guarda(); agenda(); };
    G.append(el("label", "Asa"), s);
    P.append(el("div", "Cortes", "grupo-par"));
    G = document.createElement("div"); G.className = "prop"; P.append(G);
    const m = document.createElement("select");
    [["auto", "Automático"], ["envolvente", "Envolvendo o bordo de ataque"], ["separado", "Extradorso e intradorso separados"]].forEach(([k, t]) => m.add(new Option(t, k)));
    m.value = v.modo; m.title = "Padrão para todas as faixas. Envolvente: uma peça por faixa, contornando o bordo de ataque. Separado: duas peças por faixa, com emenda no bordo de ataque. Automático escolhe a que deforma menos quando a envolvente passa do limite. Cada faixa pode ter o seu modo na tabela.";
    m.onchange = () => { v.modo = m.value; guarda(); agenda(); };
    const lm = el("label", "Modo padrão"); lm.title = m.title; G.append(lm, m);
    const ct = entrada("text", v.cortes_txt, x => { v.cortes_txt = String(x || ""); guarda(); agenda(); });
    ct.placeholder = "vazio = nas nervuras"; ct.title = "Posições em y, em mm, onde a pele é cortada, separadas por vírgula (por exemplo 200, 500, 900). Vazio: as faixas vão de nervura a nervura. Em asa simétrica, digite só o lado positivo.";
    const lc = el("label", "Cortes em y (mm)"); lc.title = ct.title; G.append(lc, ct);
    G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Critério", "grupo-par"), G);
    campo(G, "Limite de deformação (%)", "Quanto o material aceita esticar ou encolher ao assentar. Zero ou vazio: vale o padrão do material (balsa 0,3 %, filme termocontrátil 3 %). É uma hipótese: confirme com um teste de bancada.", "limite_pct");
    campo(G, "Divisões por faixa", "Pontos ao longo da faixa usados para medir a curvatura. Mais divisões medem melhor e demoram mais.", "n_vao", 2);
    G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Peça e chapa", "grupo-par"), G);
    campo(G, "Margem de cola (mm)", "Sobra nas bordas que encostam nas nervuras, para colar a pele.", "margem_cola_mm");
    campo(G, "Largura da chapa (mm)", "", "folha_largura_mm", 1);
    campo(G, "Altura da chapa (mm)", "", "folha_altura_mm", 1);
    campo(G, "Espaço entre peças (mm)", "", "espaco_mm");
    if (res) {
      const b = el("button", "Baixar DXF das faixas"); b.onclick = () => {
        const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([res.dxf], { type: "application/dxf" })); a.download = "chapeado_" + res.asa + ".dxf"; a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      };
      P.append(el("div", "Exportar", "grupo-par"), b);
    }
    P.append(el("div", "Camadas do DXF: CORTE (contorno com a margem de cola), MARCAS (linha do bordo de ataque, para alinhar), GRAVACAO (nome da faixa) e FOLHA (moldura da chapa). Cada faixa sai duas vezes, a segunda espelhada, quando a asa é simétrica.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 350); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(); return; }
    msg("Desdobrando as faixas…");
    try {
      const corpo = Object.assign({ esquema: esq }, v, { cortes_y_mm: cortesY() });
      const r = await chama("/api/planificacao", corpo);
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); if (!sel || !res.faixas.some(f => f.i === sel.faixa)) sel = pior(); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function pior() {
    let b = null;
    res.faixas.forEach(f => { if (!b || f.deformacao_max_pct > b.d) b = { faixa: f.i, d: f.deformacao_max_pct }; });
    return b && { faixa: b.faixa, peca: 0 };
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { V.textContent = "Escolha uma asa com chapeado declarado (estrutura.chapeado) no modelo."; return; }
    V.classList.remove("neutro"); V.classList.add(res.resumo.nao ? "ruim" : res.resumo.atencao ? "neutro" : "ok");
    V.innerHTML = `<b>${res.asa}:</b> ${res.faixas.length} faixas até ${fmt(100 * res.ate_xc, 0)} % da corda, de ${res.material}. `
      + `${res.resumo.ok} desdobram bem · ${res.resumo.atencao} pedem cuidado · ${res.resumo.nao} precisam de emenda. Limite de ${fmt(res.limite_pct, 2)} % de deformação. ${res.folhas} chapa${res.folhas > 1 ? "s" : ""} de ${fmt(res.folha_mm[0], 0)} × ${fmt(res.folha_mm[1], 0)} mm.`;
  }

  const corMapa = (p, lim) => `hsl(${(120 * (1 - Math.min(p / (lim * 3), 1))).toFixed(0)}, 62%, 46%)`;
  const seleciona = i => { sel = { faixa: i, peca: 0 }; redesenha(); baixo(); };

  function titulo(txt, expl) {
    const b = el("div", "", "painel-tit");
    b.append(el("b", txt), el("span", " — " + expl));
    return b;
  }

  function planta(d) {
    const e = (esq.elementos || []).find(q => q.nome === res.asa); if (!e || !e.secoes) return;
    const S = e.secoes.map(q => [Math.abs(+q.y), +q.xle || 0, +q.corda]).sort((a, b) => a[0] - b[0]);
    const interp = (y, c) => { const ay = Math.abs(y); let k = 0; while (k < S.length - 2 && ay > S[k + 1][0]) k++; const a = S[k], b = S[Math.min(k + 1, S.length - 1)]; const t = b[0] > a[0] ? Math.min(Math.max((ay - a[0]) / (b[0] - a[0]), 0), 1) : 0; return a[c] + t * (b[c] - a[c]); };
    const ya = Math.min(...res.faixas.map(f => f.y0_m)), yb = Math.max(...res.faixas.map(f => f.y1_m));
    const xs = [], ys = [];
    const LE = y => interp(y, 1), TE = y => interp(y, 1) + interp(y, 2);
    for (let k = 0; k <= 40; k++) { const y = ya + (yb - ya) * k / 40; xs.push(LE(y), TE(y)); ys.push(y); }
    const x0 = Math.min(...xs), x1 = Math.max(...xs), W = Math.max(d.clientWidth - 8, 300), pad = 22, esc = Math.min((W - 2 * pad) / (yb - ya), 140 / (x1 - x0));
    const Wp = (yb - ya) * esc + 2 * pad, Hp = (x1 - x0) * esc + 2 * pad;
    const svg = sv("svg", { width: Wp, height: Hp, viewBox: `0 0 ${Wp} ${Hp}` });
    const X = y => pad + (y - ya) * esc, Y = x => pad + (x - x0) * esc;
    res.faixas.forEach(f => {
      const n = 8, pts = [];
      for (let k = 0; k <= n; k++) { const y = f.y0_m + (f.y1_m - f.y0_m) * k / n; pts.push([X(y), Y(LE(y))]); }
      for (let k = n; k >= 0; k--) { const y = f.y0_m + (f.y1_m - f.y0_m) * k / n; pts.push([X(y), Y(Math.min(LE(y) + res.ate_xc * interp(y, 2), TE(y)))]); }
      const ativo = sel && sel.faixa === f.i;
      const pg = sv("polygon", { points: pts.map(q => q.map(z => z.toFixed(1)).join(",")).join(" "), fill: COR[f.status], "fill-opacity": ativo ? .75 : .4, stroke: ativo ? "currentColor" : COR[f.status], "stroke-width": ativo ? 1.6 : .7, style: "cursor:pointer" });
      const tt = sv("title", {}); tt.textContent = `F${String(f.i).padStart(2, "0")} · ${ROTULO[f.status]} · ${fmt(f.deformacao_max_pct, 3)} %`; pg.append(tt);
      pg.onclick = () => seleciona(f.i); svg.append(pg);
    });
    const ctn = [], cte = [];
    for (let k = 0; k <= 40; k++) { const y = ya + (yb - ya) * k / 40; ctn.push(`${X(y).toFixed(1)},${Y(LE(y)).toFixed(1)}`); cte.push(`${X(y).toFixed(1)},${Y(TE(y)).toFixed(1)}`); }
    svg.append(sv("polyline", { points: ctn.join(" "), fill: "none", stroke: "currentColor", "stroke-width": 1.2 }));
    svg.append(sv("polyline", { points: cte.join(" "), fill: "none", stroke: "currentColor", "stroke-width": 1.2, "stroke-opacity": .6 }));
    const tx = (x, y, s, a) => { const t = sv("text", { x, y, "font-size": 9, fill: "currentColor", opacity: .65, "text-anchor": a || "start" }); t.textContent = s; svg.append(t); };
    tx(pad, 11, "bordo de ataque (frente)"); tx(pad, Hp - 5, "bordo de fuga (trás)");
    tx(Wp - pad, Hp - 5, `y = ${fmt(1000 * yb, 0)} mm →`, "end");
    d.append(svg);
  }

  function chapas(d) {
    const W = res.folha_mm[0], H = res.folha_mm[1], n = res.folhas, gap = 24, pxw = Math.max(d.clientWidth - 8, 300);
    const esc = pxw / W, svg = sv("svg", { width: pxw, height: n * (H + gap) * esc, viewBox: `0 0 ${W} ${n * (H + gap)}` });
    const Y = (k, z) => k * (H + gap) + (H - z);
    for (let k = 0; k < n; k++) {
      svg.append(sv("rect", { x: 0, y: Y(k, H), width: W, height: H, fill: "none", stroke: "currentColor", "stroke-opacity": .35, "stroke-width": 1 / esc }));
      const t = sv("text", { x: 3, y: Y(k, H) - 3, fill: "currentColor", "font-size": 9, opacity: .6 }); t.textContent = `chapa ${k + 1} de ${fmt(W, 0)} × ${fmt(H, 0)} mm`; svg.append(t);
    }
    res.chapas.forEach(c => {
      const pts = c.contorno.map(q => `${q[0].toFixed(2)},${Y(c.folha, q[1]).toFixed(2)}`).join(" ");
      const ativo = sel && sel.faixa === c.faixa;
      const pg = sv("polygon", { points: pts, fill: COR[c.status], "fill-opacity": ativo ? .55 : .28, stroke: COR[c.status], "stroke-width": (ativo ? 2.2 : 1.2) / esc, style: "cursor:pointer" });
      pg.onclick = () => seleciona(c.faixa); svg.append(pg);
      const m = c.contorno.reduce((a, q) => [a[0] + q[0] / c.contorno.length, a[1] + q[1] / c.contorno.length], [0, 0]);
      const t = sv("text", { x: m[0], y: Y(c.folha, m[1]), "text-anchor": "middle", fill: "currentColor", "font-size": Math.min(10, Math.max(4, c.altura_mm * 0.25)), opacity: .8, style: "pointer-events:none" });
      t.textContent = c.rot + (c.espelho ? "'" : ""); svg.append(t);
    });
    d.append(svg);
  }

  function detalhe(d) {
    const f = res.faixas.find(q => q.i === sel.faixa); if (!f) return;
    const lim = res.limite_pct, pxw = Math.max(Math.min(d.clientWidth - 8, 760), 300);
    f.pecas.forEach(p => {
      const W = p.largura_mm, H = p.altura_mm, pad = 14, esc = pxw / (W + 2 * pad);
      const svg = sv("svg", { width: pxw, height: (H + 2 * pad + 14) * esc, viewBox: `${-pad} ${-pad} ${W + 2 * pad} ${H + 2 * pad + 14}` });
      const Vt = p.v, m1 = p.m1, nk = p.nk, nq = nk - 1;
      const baixa0 = Vt.slice(0, nk).reduce((a, q) => a + q[1], 0) < Vt.slice((m1 - 1) * nk).reduce((a, q) => a + q[1], 0);
      for (let j = 0; j < m1 - 1; j++) for (let k = 0; k < nq; k++) {
        const a = j * nk + k, b = a + 1, c = (j + 1) * nk + k + 1, dd = (j + 1) * nk + k;
        const e = Math.max(p.estr[2 * (j * nq + k)], p.estr[2 * (j * nq + k) + 1]);
        svg.append(sv("polygon", { points: [a, b, c, dd].map(i => `${Vt[i][0].toFixed(2)},${(H - Vt[i][1]).toFixed(2)}`).join(" "), fill: corMapa(e, lim), stroke: "none" }));
      }
      if (p.linha_bordo_ataque) svg.append(sv("polyline", { points: p.linha_bordo_ataque.map(q => `${q[0].toFixed(2)},${(H - q[1]).toFixed(2)}`).join(" "), fill: "none", stroke: "#fff", "stroke-width": 1.4 / esc * 0.9, "stroke-dasharray": `${5 / esc * 0.9},${3 / esc * 0.9}` }));
      const tx = (x, y, s, a) => { const t = sv("text", { x, y, "font-size": 10 / Math.max(esc, .6) * 0.9, fill: "currentColor", opacity: .75, "text-anchor": a || "start" }); t.textContent = s; svg.append(t); };
      tx(0, -3, `borda colada na nervura em y = ${fmt(1000 * (baixa0 ? f.y1_m : f.y0_m), 0)} mm`);
      tx(0, H + 10 / Math.max(esc, .6) * 0.9, `borda colada na nervura em y = ${fmt(1000 * (baixa0 ? f.y0_m : f.y1_m), 0)} mm`);
      if (p.linha_bordo_ataque) tx(W / 2, H / 2 - 4, "linha tracejada: bordo de ataque", "middle");
      const bw = 50; svg.append(sv("line", { x1: W - bw, y1: H + 8, x2: W, y2: H + 8, stroke: "currentColor", "stroke-width": 1.5 / esc })); tx(W - bw / 2, H + 8 - 3 / esc, "50 mm", "middle");
      d.append(svg);
      d.append(el("div", `${p.nome}: ${fmt(p.largura_mm, 0)} × ${fmt(p.altura_mm, 0)} mm. Deformação máxima ${fmt(p.deformacao_max_pct, 3)} % (média ${fmt(p.deformacao_media_pct, 3)} %), variação de área até ${fmt(p.var_area_max_pct, 3)} %, déficit angular máximo ${fmt(p.defeito_angular_max_graus, 3)}°.`, "nota"));
    });
    const leg = el("div", "", "legenda-cor");
    leg.innerHTML = `<span>0 %</span><i style="background:linear-gradient(90deg, ${corMapa(0, lim)}, ${corMapa(lim * 1.5, lim)}, ${corMapa(lim * 3, lim)})"></i><span>${fmt(3 * lim, 2)} % ou mais</span><em>(o limite do material é ${fmt(lim, 2)} %)</em>`;
    d.append(leg);
  }

  let a1 = null, a2 = null, a3 = null;
  function redesenha() {
    if (!res || !a1) return;
    a1.innerHTML = ""; a2.innerHTML = ""; a3.innerHTML = "";
    a1.append(titulo("① Onde estão as faixas", "a asa vista de cima; cada trecho colorido é uma faixa de chapeado. Verde desdobra bem, amarelo pede cuidado, vermelho precisa de emenda. Clique para escolher uma."));
    planta(a1);
    a2.append(titulo("② Chapas a cortar", "as peças já arrumadas na chapa, em tamanho real (mm). O apóstrofo marca a cópia espelhada para o outro lado da asa."));
    chapas(a2);
    const f = sel && res.faixas.find(q => q.i === sel.faixa);
    a3.append(titulo(`③ Faixa F${f ? String(f.i).padStart(2, "0") : ""} desdobrada`, "como a peça fica plana. As cores mostram quanto cada ponto precisaria esticar ou encolher para assentar na asa."));
    if (f) detalhe(a3);
  }

  function previa() {
    const C = $("graficos3"); C.innerHTML = ""; C.className = "graficos coluna";
    if (!res) return;
    a1 = el("div", "", "graf"); a2 = el("div", "", "graf"); a3 = el("div", "", "graf");
    a1.style.padding = a2.style.padding = a3.style.padding = "0 8px 6px"; a2.style.overflow = "auto"; C.append(a1, a2, a3);
    redesenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) redesenha(); }); }
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Faixas", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>faixa</th><th>y (mm)</th><th>peças</th><th>corte desta faixa</th><th>deformação máx. (%)</th><th>déficit angular (°)</th><th>situação</th></tr>"
      + res.faixas.map(f => `<tr style="cursor:pointer${sel && sel.faixa === f.i ? ";outline:1px solid currentColor" : ""}" data-f="${f.i}"><td>F${String(f.i).padStart(2, "0")}</td><td>${fmt(1000 * f.y0_m, 0)} a ${fmt(1000 * f.y1_m, 0)}</td><td>${f.quantidade} × ${f.pecas.length}</td><td class="sel-modo"></td><td>${fmt(f.deformacao_max_pct, 3)}</td><td>${fmt(Math.max(...f.pecas.map(p => p.defeito_angular_max_graus)), 3)}</td><td style="color:${COR[f.status]}">${ROTULO[f.status]}</td></tr>`).join("");
    t.querySelectorAll("tr[data-f]").forEach(r => {
      const f = res.faixas.find(q => q.i === +r.dataset.f);
      r.onclick = () => seleciona(f.i);
      const s = document.createElement("select"); MODOS.forEach(([k, n]) => s.add(new Option(n + (k === "" && f.modo_pedido === "auto" ? ` (usou ${f.modo})` : ""), k)));
      s.value = v.modos[f.chave] || ""; s.title = "Fixa o modo de corte só desta faixa. Automático segue o modo padrão.";
      s.onclick = ev => ev.stopPropagation();
      s.onchange = () => { if (s.value) v.modos[f.chave] = s.value; else delete v.modos[f.chave]; guarda(); agenda(); };
      r.querySelector(".sel-modo").append(s);
    });
    C.append(t);
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
    C.append(el("div", "Como ler: uma superfície só se desdobra sem esticar quando curva em uma direção por vez (curvatura gaussiana nula). O déficit angular mede isso em cada ponto da malha. A deformação é o que sobra quando a faixa é achatada e comparada com a forma 3D. "
      + "Faixas em vermelho precisam de emenda ou de umedecer e forçar a pele. Os limites por material são hipóteses: confirme com um teste de bancada. Ficam fora: a ponta da asa, a raiz junto à fuselagem e as nervuras inclinadas.", "nota"));
  }

  function mostra() { if (!ativa()) return; parametros(); veredito(); previa(); baixo(); }
  Etapa3.registra("planificacao", { pinta() { parametros(); veredito(); baixo(); agenda(); } });
  const corpoPara = nome => Object.assign({ esquema: esq }, v, { asa: nome, modos: nome === v.asa ? v.modos : {}, cortes_y_mm: nome === v.asa ? cortesY() : [] });
  return { dados: () => ({ v, res }), corpoPara };
})();
