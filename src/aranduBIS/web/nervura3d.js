"use strict";

const Nervura3D = (() => {
  const PASSO = 0.005, MARGEM = 0.005;
  let ativo = false, sel = null, arr = null, meu = false, previa = null, ultimo = null;

  const ehAsa = e => e && (e.tipo || "asa") === "asa" && Array.isArray(e.secoes);
  const iguais = (a, b) => Math.abs(a - b) < 1e-6;
  const cfg = (e, cria) => {
    if (!e.estrutura) { if (!cria) return null; e.estrutura = {}; }
    if (!e.estrutura.nervuras && cria) e.estrutura.nervuras = { y: [], espessura: 0.00238, material: "balsa" };
    const n = e.estrutura.nervuras || null;
    if (n && !n.y) n.y = [];
    return n;
  };
  const secoes = () => { const e = elemento(), d = Secao3D.dados().dados; return e && d && d.asa === e.nome ? d.secoes : null; };
  const limites = e => {
    const ys = e.secoes.map(s => s.y).filter(v => typeof v === "number"), lo = Math.min(...ys), hi = Math.max(...ys);
    const simetrica = lo < 0 && hi > 0 && iguais(-lo, hi);
    return { lo: simetrica ? 0 : lo, hi, simetrica };
  };
  const angDe = (n, y) => { const a = (n.angulos || []).find(q => iguais(q[0], y)); return a ? a[1] : (n.angulo ?? 0); };

  function anel(S, y, ang) {
    let i = 0; while (i < S.length - 2 && y > S[i + 1].y) i++;
    const a = S[i], b = S[i + 1], f = Math.max(0, Math.min(1, (y - a.y) / Math.max(b.y - a.y, 1e-9)));
    const A = a.anel3d, B = b.anel3d;
    const pts = A.length === B.length ? A.map((p, j) => p.map((v, k) => v + f * (B[j][k] - v))) : (f < 0.5 ? A : B).map(p => p.slice());
    if (ang) {
      const xs = pts.map(p => p[0]), x0 = Math.min(...xs), x25 = x0 + 0.25 * (Math.max(...xs) - x0), t = Math.tan(ang * Math.PI / 180) * (y >= 0 ? 1 : -1);
      pts.forEach(p => { p[1] += (p[0] - x25) * t; });
    }
    return pts;
  }
  const centro = (S, y) => { const P = anel(S, y, 0); return [0, 1, 2].map(k => P.reduce((s, p) => s + p[k], 0) / P.length); };
  const proj = c => vista.projetaXY(c[0], c[1], c[2]);

  function itens(e, n, L, drag) {
    const L2 = [];
    n.y.forEach((y0, k) => {
      const y = drag && drag.k === k ? drag.y : y0, ang = angDe(n, y0);
      L2.push({ k, y0, y, ang, esp: false });
      if (L.simetrica && y > 1e-9) L2.push({ k, y0, y: -y, ang, esp: true });
    });
    return L2;
  }

  function vizinhos(n, L, y0) {
    const o = n.y.filter(v => !iguais(v, y0)), ab = o.filter(v => v < y0), ac = o.filter(v => v > y0);
    return { baixo: ab.length ? Math.max(...ab) : L.lo - MARGEM, cima: ac.length ? Math.min(...ac) : L.hi + MARGEM };
  }
  const prende = (n, L, y0, y) => { const v = vizinhos(n, L, y0); return Math.max(v.baixo + MARGEM, Math.min(v.cima - MARGEM, Math.max(L.lo, Math.min(L.hi, y)))); };

  function atualiza() { pinta(); if (typeof Estado !== "undefined") Estado.avisa("ferramenta"); }
  function pinta() {
    const e = elemento(), S = ativo && ehAsa(e) ? secoes() : null;
    if (!ativo || !ehAsa(e)) { if (meu) { meu = false; vista.extra = null; vista.hud = null; } vista.desenha(); return; }
    meu = true;
    if (!S) { vista.extra = null; vista.hud = ["Carregando as seções…"]; vista.desenha(); return; }
    const n = cfg(e, false) || { y: [] }, L = limites(e), ex = [];
    const fim = L.simetrica ? [L.hi, -L.hi] : [L.lo, L.hi];
    fim.forEach(y => ex.push({ pts: anel(S, y, 0), cor: "rgba(255,255,255,.28)", larg: 1 }));
    itens(e, n, L, arr && arr.arrasta ? arr : null).forEach(it => {
      const s = sel !== null && iguais(it.y0, sel);
      ex.push({ pts: anel(S, it.y, it.ang), cor: s ? "#ffd447" : "#ff9f43", larg: s ? 3 : 1.6 });
    });
    const lim = n.passo_max_mm > 0 ? n.passo_max_mm / 1000 : null, longos = [];
    if (lim) {
      const ys = [L.lo, ...n.y.map((v, k) => (arr && arr.arrasta && arr.k === k ? arr.y : v)).filter(v => v > L.lo + 1e-9 && v < L.hi - 1e-9), L.hi].sort((a, b) => a - b);
      for (let i = 0; i + 1 < ys.length; i++) if (ys[i + 1] - ys[i] > lim + 1e-6) {
        longos.push(ys[i + 1] - ys[i]);
        (L.simetrica ? [1, -1] : [1]).forEach(sg => ex.push({ pts: [centro(S, sg * ys[i]), centro(S, sg * ys[i + 1])], cor: "#e0b84a", larg: 5 }));
      }
    }
    if (previa !== null) ex.push({ pts: anel(S, previa, 0), cor: "rgba(255,212,71,.7)", larg: 1.4 });
    vista.extra = ex;
    const h = [];
    if (sel !== null && n.y.some(v => iguais(v, sel))) {
      const y = arr && arr.arrasta ? arr.y : sel, v = vizinhos(n, L, sel);
      const mm = d => Math.round(d * 1000);
      h.push(`Nervura em y = ${y.toFixed(3)} m · ângulo ${(+angDe(n, sel)).toFixed(1)}°`);
      h.push(`vão: ${mm(y - Math.max(v.baixo, L.lo - 0))} mm atrás · ${mm(Math.min(v.cima, L.hi) - y)} mm à frente`);
    } else h.push(`Editando nervuras: ${n.y.length}${L.simetrica ? " por semi-asa" : ""}`);
    if (longos.length) h.push(`${longos.length} vão${longos.length === 1 ? "" : "s"} acima do passo máximo de ${n.passo_max_mm} mm (maior: ${Math.round(1000 * Math.max(...longos))} mm), em dourado`);
    h.push("Arraste um anel laranja (Alt = sem passo)");
    h.push("Ctrl+clique cria · N cria no maior vão");
    h.push("←/→ move 1 mm (Shift 10) · Q/E gira 1° (Shift 5)");
    h.push("Del remove · Tab troca · Esc sai");
    vista.hud = h; vista.desenha();
  }

  function liga(v) {
    ativo = !!v;
    if (ativo && typeof No3D !== "undefined" && No3D.ativo()) No3D.liga(false);
    vista.ferramenta = ativo ? ferramenta : null;
    if (ativo) vista.aoMover = aoMover; else if (vista.aoMover === aoMover) vista.aoMover = null;
    previa = null;
    if (ativo) { const n = cfg(elemento() || {}, false); if (n && n.y.length && (sel === null || !n.y.some(q => iguais(q, sel)))) sel = n.y[0]; }
    atualiza();
  }

  const aplicaY = (n, antigo, novo) => {
    const k = n.y.findIndex(v => iguais(v, antigo)); if (k < 0) return;
    n.y[k] = novo; (n.angulos || []).forEach(a => { if (iguais(a[0], antigo)) a[0] = novo; });
  };

  function adiciona(e, y) {
    const L = limites(e); y = +Math.max(L.lo + MARGEM, Math.min(L.hi - MARGEM, y)).toFixed(4);
    muda(() => { const n = cfg(e, true); n.y.push(y); });
    sel = y; atualiza();
  }
  function maiorVao(e) {
    const n = cfg(e, false) || { y: [] }, L = limites(e);
    const pts = [L.lo, ...n.y.filter(v => v >= L.lo - 1e-9 && v <= L.hi + 1e-9), L.hi].sort((a, b) => a - b);
    let k = 0; for (let i = 0; i + 1 < pts.length; i++) if (pts[i + 1] - pts[i] > pts[k + 1] - pts[k]) k = i;
    return 0.5 * (pts[k] + pts[k + 1]);
  }

  function aoMover(px, py, ev) {
    const e = elemento(), S = ativo && ehAsa(e) ? secoes() : null;
    if (!S || !(ev.ctrlKey || ev.metaKey)) { if (previa !== null) { previa = null; atualiza(); } return; }
    const L = limites(e);
    let mel = null, d0 = 60;
    for (let i = 0; i <= 240; i++) {
      const y = L.lo + (L.hi - L.lo) * i / 240, q = proj(centro(S, y)); if (!q) continue;
      const d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = y; }
    }
    const novo = mel === null ? null : Math.round(mel / PASSO) * PASSO;
    if (novo !== previa) { previa = novo; atualiza(); }
  }

  const ferramenta = {
    baixo(px, py, ev) {
      const e = elemento(), S = ativo && ehAsa(e) ? secoes() : null; if (!S) return false;
      const L = limites(e);
      if (ev.ctrlKey || ev.metaKey) {
        let mel = null, d0 = 60;
        for (let i = 0; i <= 240; i++) {
          const y = L.lo + (L.hi - L.lo) * i / 240, q = proj(centro(S, y)); if (!q) continue;
          const d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = y; }
        }
        if (mel !== null) adiciona(e, Math.round(mel / PASSO) * PASSO);
        return true;
      }
      const n = cfg(e, false); if (!n) return false;
      const perto = [];
      itens(e, n, L, null).forEach(it => {
        let d0 = 12;
        for (const p of anel(S, it.y, it.ang)) { const q = proj(p); if (q) d0 = Math.min(d0, Math.hypot(q[0] - px, q[1] - py)); }
        if (d0 < 12) perto.push({ it, d: d0 });
      });
      if (!perto.length) { ultimo = null; return false; }
      perto.sort((a, b) => a.d - b.d);
      let mel = perto[0].it;
      if (ultimo && Math.hypot(ultimo.px - px, ultimo.py - py) < 5 && perto.length > 1) {
        const i = perto.findIndex(q => iguais(q.it.y0, sel) && q.it.esp === ultimo.esp);
        if (i >= 0) mel = perto[(i + 1) % perto.length].it;
      }
      ultimo = { px, py, esp: mel.esp };
      sel = mel.y0;
      const c0 = centro(S, mel.y), c1 = centro(S, mel.y + 0.05), q0 = proj(c0), q1 = proj(c1);
      arr = { k: mel.k, y0: mel.y0, y: mel.y0, px, py, sinal: mel.esp ? -1 : 1, sx: q1[0] - q0[0], sy: q1[1] - q0[1], arrasta: false };
      atualiza(); return true;
    },
    move(px, py, ev) {
      if (!arr) return;
      const e = elemento(), n = cfg(e, false), L = limites(e), s2 = arr.sx * arr.sx + arr.sy * arr.sy;
      if (!n || s2 < 1e-6) return;
      const dy = ((px - arr.px) * arr.sx + (py - arr.py) * arr.sy) / s2 * 0.05 * arr.sinal;
      let y = arr.y0 + dy; if (!ev.altKey) y = Math.round(y / PASSO) * PASSO;
      arr.y = +prende(n, L, arr.y0, y).toFixed(4); arr.arrasta = true; atualiza();
    },
    solta() {
      const a = arr; arr = null;
      if (a && a.arrasta && !iguais(a.y, a.y0)) { const e = elemento(); muda(() => { aplicaY(cfg(e, true), a.y0, a.y); }); sel = a.y; }
      atualiza();
    },
  };

  window.addEventListener("keydown", ev => {
    if (!ativo || ev.ctrlKey || ev.metaKey) return;
    const t = ev.target, tag = t && t.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
    const e = elemento(); if (!ehAsa(e)) return;
    const n = cfg(e, false), L = limites(e), k = ev.key, forte = ev.shiftKey;
    if (k === "Escape") { liga(false); if (typeof abaConteudo === "function") abaConteudo(); ev.preventDefault(); return; }
    if (k === "n" || k === "N") { adiciona(e, maiorVao(e)); ev.preventDefault(); return; }
    if (!n || !n.y.length) return;
    if (k === "Tab") {
      const o = n.y.slice().sort((a, b) => a - b), i = o.findIndex(v => sel !== null && iguais(v, sel));
      sel = o[(i + (forte ? -1 : 1) + o.length) % o.length]; atualiza(); ev.preventDefault(); return;
    }
    if (sel === null || !n.y.some(v => iguais(v, sel))) return;
    const y0 = sel;
    if (k === "ArrowLeft" || k === "ArrowRight") {
      const y = +prende(n, L, y0, y0 + (k === "ArrowRight" ? 1 : -1) * (forte ? 0.01 : 0.001)).toFixed(4);
      if (!iguais(y, y0)) { muda(() => aplicaY(cfg(e, true), y0, y)); sel = y; }
      atualiza(); ev.preventDefault(); return;
    }
    if (k === "q" || k === "Q" || k === "e" || k === "E") {
      const d = (k.toLowerCase() === "e" ? 1 : -1) * (forte ? 5 : 1), novo = Math.max(-79, Math.min(79, Math.round((+angDe(n, y0) + d) * 10) / 10));
      muda(() => { const m = cfg(e, true); m.angulos = (m.angulos || []).filter(a => !iguais(a[0], y0)); m.angulos.push([y0, novo]); });
      atualiza(); ev.preventDefault(); return;
    }
    if (k === "Delete" || k === "Backspace") {
      muda(() => { const m = cfg(e, true); m.y = m.y.filter(v => !iguais(v, y0)); m.angulos = (m.angulos || []).filter(a => !iguais(a[0], y0)); if (!m.angulos.length) delete m.angulos; });
      const r = n.y.slice().sort((a, b) => a - b); sel = r.length ? r[0] : null; atualiza(); ev.preventDefault();
    }
  });

  const selecao = () => {
    const e = elemento(); if (!ativo || !ehAsa(e)) return null;
    const n = cfg(e, false); if (!n || sel === null || !n.y.some(v => iguais(v, sel))) return { asa: e.nome, y: null, total: n ? n.y.length : 0 };
    return { asa: e.nome, y: sel, angulo: +angDe(n, sel), total: n.y.length };
  };
  function defineSel(o) {
    const e = elemento(), n = ehAsa(e) && cfg(e, false); if (!ativo || !n || sel === null) return;
    const y0 = sel;
    if (typeof o.y === "number" && isFinite(o.y)) {
      const y = +prende(n, limites(e), y0, o.y).toFixed(4);
      if (!iguais(y, y0)) { muda(() => aplicaY(cfg(e, true), y0, y)); sel = y; }
    }
    if (typeof o.angulo === "number" && isFinite(o.angulo)) {
      const ys = sel, a = Math.max(-79, Math.min(79, o.angulo));
      muda(() => { const m = cfg(e, true); m.angulos = (m.angulos || []).filter(q => !iguais(q[0], ys)); m.angulos.push([ys, a]); });
    }
    atualiza();
  }
  function criaNoVao() { const e = elemento(); if (ativo && ehAsa(e)) adiciona(e, maiorVao(e)); }
  function removeSel() {
    const e = elemento(), n = ehAsa(e) && cfg(e, false); if (!ativo || !n || sel === null) return;
    const y0 = sel;
    muda(() => { const m = cfg(e, true); m.y = m.y.filter(v => !iguais(v, y0)); m.angulos = (m.angulos || []).filter(a => !iguais(a[0], y0)); if (!m.angulos.length) delete m.angulos; });
    const r = (cfg(e, false) || { y: [] }).y.slice().sort((a, b) => a - b); sel = r.length ? r[0] : null; atualiza();
  }

  return { liga, atualiza, ativo: () => ativo, ehAsa, selecao, defineSel, criaNoVao, removeSel, puro: { cfg, limites, angDe, anel, itens, vizinhos, prende, aplicaY, maiorVao } };
})();
