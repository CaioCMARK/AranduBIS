"use strict";

const Secao3D = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, a, pai) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (pai) pai.append(e); return e; };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const rad = d => d * Math.PI / 180;
  let dados = null, isel = 0, espelha = true, tempo = null, seq = 0, arrasto = false, assina = "";

  const ehAsa = e => e && (e.tipo || "asa") === "asa" && Array.isArray(e.secoes);
  const mostraAneis = () => ehAsa(elemento()) && (aba === "Seção" || aba === "Seções") && dados && dados.asa === elemento().nome;

  function atualiza() {
    clearTimeout(tempo);
    tempo = setTimeout(async () => {
      const e = elemento();
      if (!ehAsa(e)) { dados = null; sincroniza(); return; }
      const meu = ++seq;
      try {
        const r = await chama("/api/secoes", { esquema: esq, asa: e.nome });
        if (meu !== seq) return;
        dados = r.erro ? null : r;
        if (dados) isel = Math.max(0, Math.min(isel, dados.secoes.length - 1));
      } catch (x) { if (meu !== seq) return; dados = null; }
      sincroniza();
      if (aba === "Seção" && !arrasto) abaConteudo();
    }, 150);
  }

  function sincroniza() {
    const mostra = mostraAneis();
    const sig = mostra ? dados.asa + "|" + isel + "|" + dados.secoes.map(s => s.xle + "," + s.zle + "," + s.corda + "," + s.ainc + "," + s.y).join(";") : "";
    if (sig === assina) { if (typeof Nervura3D !== "undefined" && Nervura3D.ativo()) Nervura3D.atualiza(); return; }
    assina = sig;
    vista.aneis = mostra ? dados.secoes.map((s, i) => ({ pts: s.anel3d, sel: i === isel })) : null;
    vista.desenha();
    if (typeof Nervura3D !== "undefined") Nervura3D.atualiza();
  }

  function clica(px, py) {
    if (!mostraAneis()) return;
    let melhor = null, d0 = 14;
    dados.secoes.forEach((s, i) => {
      let d = Infinity;
      for (const p of s.anel3d) { const q = vista.projetaXY(p[0], p[1], p[2]); if (q) d = Math.min(d, Math.hypot(q[0] - px, q[1] - py)); }
      if (d < d0) { d0 = d; melhor = i; }
    });
    if (melhor === null) return;
    isel = melhor; aba = "Seção"; abas(); abaConteudo(); sincroniza();
  }

  const pos = (t, u, w) => [t.xle + t.c * (u * Math.cos(t.a) + w * Math.sin(t.a)), t.zle + t.c * (-u * Math.sin(t.a) + w * Math.cos(t.a))];

  function superficies(anel) {
    const n = (anel.length + 2) / 2, ba = n - 1;
    const sup = anel.slice(0, ba + 1).reverse(), inf = [anel[ba]].concat(anel.slice(ba + 1), [anel[0]]);
    return { sup, inf };
  }
  const interp = (cv, u) => {
    for (let i = 0; i < cv.length - 1; i++) if (u >= cv[i][0] && u <= cv[i + 1][0]) { const f = (u - cv[i][0]) / Math.max(cv[i + 1][0] - cv[i][0], 1e-12); return cv[i][1] + f * (cv[i + 1][1] - cv[i][1]); }
    return cv[cv.length - 1][1];
  };

  function pinta(C, e) {
    const S = e.secoes;
    if (!dados || dados.asa !== e.nome) { C.append(el("div", "Carregando as seções…", "nota")); atualiza(); return; }
    isel = Math.max(0, Math.min(isel, S.length - 1));
    const d = dados.secoes[isel], s = S[isel];
    const raiz = el("div"); raiz.style.cssText = "display:flex;height:100%;min-height:200px;gap:6px";
    const esqd = el("div"); esqd.style.cssText = "width:232px;flex:none;overflow:auto;padding:4px 6px";
    const dir = el("div"); dir.style.cssText = "flex:1;min-width:0;position:relative";
    raiz.append(esqd, dir); C.append(raiz);

    const nav = el("div", "", "prop"); nav.style.gridTemplateColumns = "auto 1fr auto";
    const ant = el("button", "◀"), prox = el("button", "▶");
    ant.disabled = isel === 0; prox.disabled = isel === S.length - 1;
    ant.onclick = () => { isel--; abaConteudo(); sincroniza(); }; prox.onclick = () => { isel++; abaConteudo(); sincroniza(); };
    nav.append(ant, el("div", `Seção ${isel + 1} de ${S.length} · y = ${fmt(d.y, 4)} m`), prox);
    esqd.append(nav);

    const G = el("div", "", "prop");
    const aplica = (k, v) => aplicaCampo(e, isel, k, v);
    [["y", "y (m)"], ["xle", "xle (m)"], ["zle", "zle (m)"], ["corda", "corda (m)"], ["ainc", "incidência (°)"]].forEach(([k, r]) => {
      G.append(el("label", r), entrada("number", s[k], v => { if (v === null) { abaConteudo(); return; } aplica(k, v); }));
    });
    esqd.append(G);
    const m = el("label"); const cx = document.createElement("input"); cx.type = "checkbox"; cx.checked = espelha;
    cx.onchange = () => { espelha = cx.checked; };
    m.append(cx, " espelhar em −y (asa simétrica)"); m.style.cssText = "display:block;padding:2px 8px"; esqd.append(m);
    const B = el("div"); B.style.cssText = "padding:4px 8px;display:flex;gap:6px;flex-wrap:wrap";
    const dv = el("button", "Dividir com a próxima"); dv.disabled = isel >= S.length - 1;
    dv.title = "Insere uma seção no meio entre esta e a próxima (valores interpolados).";
    dv.onclick = () => muda(() => { const a = S[isel], b = S[isel + 1], n = { ...a }; ["y", "xle", "zle", "corda", "ainc"].forEach(k => { n[k] = +(0.5 * (a[k] + b[k])).toFixed(5); }); S.splice(isel + 1, 0, n); isel++; });
    const rm = el("button", "Remover"); rm.disabled = S.length <= 2; rm.onclick = () => { muda(() => { S.splice(isel, 1); isel = Math.min(isel, S.length - 1); }); };
    B.append(dv, rm); esqd.append(B);
    const info = [];
    if (d.perfil) info.push("perfil " + d.perfil);
    if (d.nervura) info.push("tem nervura");
    if (d.longarinas.length) info.push(d.longarinas.length + " longarina" + (d.longarinas.length > 1 ? "s" : ""));
    if (d.tubos.length) info.push(d.tubos.length + " tubo" + (d.tubos.length > 1 ? "s" : ""));
    if (d.controles.length) info.push("comando: " + d.controles.join(", "));
    esqd.append(el("div", info.join(" · ") || "sem estrutura declarada nesta estação", "nota"));
    esqd.append(el("div", "Arraste o bordo de ataque (azul) para mover a seção e o bordo de fuga (laranja) para mudar corda e incidência. Clique numa seção na vista 3D para escolhê-la.", "nota"));

    desenha(dir, d, s);
  }

  function desenha(dir, d, s) {
    const t = { xle: s.xle, zle: s.zle, c: s.corda, a: rad(s.ainc) };
    const { sup, inf } = superficies(d.anel);
    const caixa = () => {
      const pts = d.anel.map(([u, w]) => pos(t, u, w)).concat([[t.xle, t.zle]]);
      const xs = pts.map(p => p[0] * 1000), zs = pts.map(p => -p[1] * 1000);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs), mx = Math.max(0.12 * (x1 - x0), 12), mz = Math.max(0.5 * (x1 - x0) * 0.25, 18);
      return [x0 - mx, z0 - mz, (x1 - x0) + 2 * mx, (z1 - z0) + 2 * mz];
    };
    const vb = caixa();
    const svg = sv("svg", { viewBox: vb.join(" "), preserveAspectRatio: "xMidYMid meet" }); svg.style.cssText = "width:100%;height:100%;touch-action:none;display:block";
    dir.append(svg);
    const k = () => vb[2] / Math.max(dir.clientWidth || 600, 1);
    const P = (u, w) => { const q = pos(t, u, w); return [q[0] * 1000, -q[1] * 1000]; };
    const gSt = sv("g", {}, svg), gPerfil = sv("g", {}, svg), gAl = sv("g", {}, svg);
    const txt = sv("text", { fill: "currentColor", "font-size": 12, opacity: .8 }, svg); txt.style.fontSize = "12px";

    function redesenha() {
      const kk = k();
      gSt.innerHTML = ""; gPerfil.innerHTML = ""; gAl.innerHTML = "";
      d.longarinas.forEach(l => { const u = l.x_mm / 1000 / t.c; const a = P(u, interp(sup, u)), b = P(u, interp(inf, u)); sv("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: "#a278c8", "stroke-width": Math.max(l.largura_mm, 1.5 * kk) }, gSt); });
      d.tubos.forEach(tb => { const u = tb.x_mm / 1000 / t.c, r = tb.d_mm / 2 / 1000 / t.c; const w = tb.lado === "meio" ? 0.5 * (interp(sup, u) + interp(inf, u)) : tb.lado === "extradorso" ? interp(sup, u) - r : interp(inf, u) + r; const q = P(u, w);
        sv("circle", { cx: q[0], cy: q[1], r: tb.d_mm / 2, fill: "none", stroke: "#6aa84f", "stroke-width": 1.5 * kk }, gSt); });
      if (dados.chapeado_ate_xc) [sup, inf].forEach(cv => { const pts = cv.filter(p => p[0] <= dados.chapeado_ate_xc + 1e-9).map(p => P(p[0], p[1])); if (pts.length > 1) sv("polyline", { points: pts.map(p => p.join(",")).join(" "), fill: "none", stroke: "#d98a3d", "stroke-width": Math.max(dados.chapeado_mm || 1, 1.2 * kk), "stroke-linecap": "round", opacity: .8 }, gSt); });
      sv("polygon", { points: d.anel.map(([u, w]) => P(u, w).join(",")).join(" "), fill: "#4a86c5", "fill-opacity": .18, stroke: "#4a86c5", "stroke-width": 1.8 * kk }, gPerfil);
      const le = P(0, 0), te = P(1, 0);
      sv("line", { x1: le[0], y1: le[1], x2: te[0], y2: te[1], stroke: "currentColor", "stroke-opacity": .5, "stroke-dasharray": `${5 * kk} ${4 * kk}`, "stroke-width": 1 * kk }, gPerfil);
      const alca = (p, cor, nome, rot) => { const c = sv("circle", { cx: p[0], cy: p[1], r: 6 * kk, fill: cor, stroke: "#000", "stroke-opacity": .5, "stroke-width": kk }, gAl); c.style.cursor = "grab"; c.dataset.alca = nome; c.append(Object.assign(document.createElementNS(NS, "title"), { textContent: rot })); return c; };
      alca(le, "#38b6ff", "le", "Bordo de ataque: move a seção (xle, zle)").addEventListener("pointerdown", ev => inicia(ev, "le"));
      alca(te, "#ff9f43", "te", "Bordo de fuga: muda corda e incidência").addEventListener("pointerdown", ev => inicia(ev, "te"));
      txt.setAttribute("x", vb[0] + 8 * kk); txt.setAttribute("y", vb[1] + 16 * kk); txt.setAttribute("font-size", 12 * kk);
      txt.textContent = `corda ${(t.c * 1000).toFixed(1)} mm · incidência ${(t.a * 180 / Math.PI).toFixed(2)}° · BA em x ${(t.xle * 1000).toFixed(1)}, z ${(t.zle * 1000).toFixed(1)} mm`;
    }
    redesenha();
    new ResizeObserver(() => { if (!arrasto) redesenha(); }).observe(dir);

    function aqui(ev) { const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; const q = p.matrixTransform(svg.getScreenCTM().inverse()); return [q.x / 1000, -q.y / 1000]; }
    function inicia(ev, qual) {
      ev.preventDefault(); ev.stopPropagation(); arrasto = true;
      const alvo = ev.target; alvo.setPointerCapture && alvo.setPointerCapture(ev.pointerId);
      const off = qual === "le" ? (() => { const q = aqui(ev); return [t.xle - q[0], t.zle - q[1]]; })() : [0, 0];
      const move = e2 => {
        const q = aqui(e2);
        if (qual === "le") { t.xle = Math.round((q[0] + off[0]) * 1e5) / 1e5; t.zle = Math.round((q[1] + off[1]) * 1e5) / 1e5; }
        else { const dx = q[0] - t.xle, dz = q[1] - t.zle; t.c = Math.max(0.01, Math.round(Math.hypot(dx, dz) * 1e5) / 1e5); t.a = Math.round(Math.atan2(-dz, dx) * 180 / Math.PI * 1e3) / 1e3 * Math.PI / 180; }
        redesenha();
      };
      const fim = () => {
        window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", fim); arrasto = false;
        const novo = { xle: t.xle, zle: t.zle, corda: t.c, ainc: +(t.a * 180 / Math.PI).toFixed(3) };
        aplicaVarios(e0(), isel, novo);
      };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", fim);
    }
  }

  const e0 = () => elemento();

  function parceira(S, i) {
    if (!espelha) return -1;
    const y = S[i].y; if (Math.abs(y) < 1e-9) return -1;
    return S.findIndex((q, j) => j !== i && Math.abs(q.y + y) < 1e-9 && ["xle", "zle", "corda", "ainc"].every(k => Math.abs((q[k] || 0) - (S[i][k] || 0)) < 1e-9));
  }
  function aplicaVarios(e, i, valores) {
    if (!e) return;
    const S = e.secoes, j = parceira(S, i);
    muda(() => { Object.assign(S[i], valores); if (j >= 0) Object.assign(S[j], valores); });
  }
  function aplicaCampo(e, i, k, v) {
    if (k === "y") { const S = e.secoes; const ant = S[i - 1], prox = S[i + 1]; if ((ant && v <= ant.y) || (prox && v >= prox.y)) { msg("O y precisa ficar entre o da seção anterior e o da próxima.", true); abaConteudo(); return; } }
    if (k === "corda" && !(v > 0)) { msg("A corda precisa ser maior que zero.", true); abaConteudo(); return; }
    if (k === "y") { muda(() => { e.secoes[i].y = v; }); return; }
    aplicaVarios(e, i, { [k]: v });
  }

  vista.aoClicar = clica;
  return { pinta, atualiza, sincroniza, clica, dados: () => ({ dados, isel }) };
})();
