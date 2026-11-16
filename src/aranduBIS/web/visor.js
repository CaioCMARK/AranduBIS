"use strict";

// Visualizador expandido da esteira: corpo (painéis do VLM), anéis e partículas em 3D, com vistas, giro, zoom e a
// linha do tempo (deslizante, tocar/pausar, velocidade) e o CL do instante embaixo. Canvas 2D com projeção ortográfica:
// sem dependências, roda em qualquer navegador e no .exe.
const Visor = (() => {
  const dlg = $("dlg_visor"), cv = $("visor_cv"), cl = $("visor_cl"), sl = $("visor_t"), info = $("visor_info");
  const ctx = cv.getContext("2d"), cctx = cl.getContext("2d");
  const VISTAS = { iso: [-135, 24], lateral: [-90, 0], topo: [-90, 89.9], frontal: [180, 0] };
  // plasma: fraco (azul-roxo) a forte (amarelo)
  const STOPS = [[0, [13, 8, 135]], [0.25, [126, 3, 168]], [0.5, [204, 71, 120]], [0.75, [248, 149, 64]], [1, [240, 249, 33]]];
  const PAL = Array.from({ length: 256 }, (_, i) => {
    const t = i / 255; let k = 0; while (k < STOPS.length - 2 && t > STOPS[k + 1][0]) k++;
    const [t0, a] = STOPS[k], [t1, b] = STOPS[k + 1], f = (t - t0) / (t1 - t0);
    return `rgb(${a.map((v, j) => Math.round(v + f * (b[j] - v))).join(",")})`;
  });
  let D = null, q = 0, az = -135, el = 24, zoom = 1, pan = [0, 0], c0 = [0, 0, 0], escala = 1, tocando = false, ult = 0, vel = 1;
  const mostra = { corpo: true, aneis: true, part: true };
  let corpoQ = [];

  function base() {
    const a = az * Math.PI / 180, e = el * Math.PI / 180;
    const d = [Math.cos(e) * Math.cos(a), Math.cos(e) * Math.sin(a), Math.sin(e)];        // do alvo para a câmera
    let r = [-d[1], d[0], 0]; const nr = Math.hypot(r[0], r[1]) || 1; r = [r[0] / nr, r[1] / nr, 0];
    if (Math.abs(e) > 1.5) r = [Math.sin(a), -Math.cos(a), 0].map(v => -v);
    const u = [d[1] * r[2] - d[2] * r[1], d[2] * r[0] - d[0] * r[2], d[0] * r[1] - d[1] * r[0]];
    return { d, r, u };
  }

  function ajusta() {
    const P = [];
    for (let i = 0; i < D.corpo.length; i += 3) P.push([D.corpo[i], D.corpo[i + 1], D.corpo[i + 2]]);
    const f = D.quadros[D.quadros.length - 1];
    if (f.X) for (let i = 0; i < f.X.length; i += 9) P.push([f.X[i], f.X[i + 1], f.X[i + 2]]);
    f.aneis.forEach(a => { for (let i = 0; i < a.p.length; i += 9) P.push([a.p[i], a.p[i + 1], a.p[i + 2]]); });
    [D.quadros[0], f].forEach(g => { if (g.solo) P.push(g.solo.p0); });
    const lo = [0, 1, 2].map(j => Math.min(...P.map(p => p[j]))), hi = [0, 1, 2].map(j => Math.max(...P.map(p => p[j])));
    c0 = lo.map((v, j) => 0.5 * (v + hi[j]));
    escala = Math.max(...hi.map((v, j) => v - lo[j])) || 1;
    zoom = 1; pan = [0, 0];
  }

  function tamanho() {
    const dpr = window.devicePixelRatio || 1;
    for (const c of [cv, cl]) { c.width = Math.max(10, c.clientWidth * dpr); c.height = Math.max(10, c.clientHeight * dpr); }
  }

  function desenha() {
    if (!D) return;
    const W = cv.width, H = cv.height, { d, r, u } = base(), s = zoom * 0.9 * Math.min(W, H * 1.6) / escala;
    const proj = (x, y, z) => { const p = [x - c0[0], y - c0[1], z - c0[2]];
      return [W / 2 + pan[0] + s * (p[0] * r[0] + p[1] * r[1] + p[2] * r[2]), H / 2 + pan[1] - s * (p[0] * u[0] + p[1] * u[1] + p[2] * u[2]), p[0] * d[0] + p[1] * d[1] + p[2] * d[2]]; };
    const fundo = getComputedStyle(document.body).getPropertyValue("--vista").trim() || "#20242b";
    ctx.fillStyle = fundo; ctx.fillRect(0, 0, W, H);
    const f = D.quadros[q], dpr = window.devicePixelRatio || 1;
    if (mostra.corpo) {
      const L = [0.3, -0.4, 0.86];
      const pol = corpoQ.map(Q => {
        const P = Q.map(p => proj(p[0], p[1], p[2]));
        return { P, z: (P[0][2] + P[1][2] + P[2][2] + P[3][2]) / 4, luz: 0.45 + 0.55 * Math.abs(Q.n[0] * L[0] + Q.n[1] * L[1] + Q.n[2] * L[2]) };
      }).sort((a, b) => a.z - b.z);
      ctx.lineWidth = 0.5 * dpr;
      for (const p of pol) {
        const g = Math.round(140 * p.luz + 40);
        ctx.fillStyle = `rgba(${g},${g + 10},${g + 30},0.92)`; ctx.strokeStyle = "rgba(30,40,60,0.35)";
        ctx.beginPath(); p.P.forEach((v, i) => i ? ctx.lineTo(v[0], v[1]) : ctx.moveTo(v[0], v[1])); ctx.closePath(); ctx.fill(); ctx.stroke();
      }
    }
    if (f.solo) {
      // chão: grade no plano (ponto p0, normal n), cobrindo o corpo e a esteira
      const n = f.solo.n, p0 = f.solo.p0, e1 = [n[2], 0, -n[0]], e2 = [0, 1, 0];
      const L = escala * 0.75, nl = 12, pt = (a, b) => proj(p0[0] + a * e1[0] + b * e2[0], p0[1] + a * e1[1] + b * e2[1], p0[2] + a * e1[2] + b * e2[2]);
      const cx = (c0[0] - p0[0]) * e1[0] + (c0[2] - p0[2]) * e1[2], cy = c0[1] - p0[1];
      ctx.fillStyle = "rgba(110,140,90,0.18)"; ctx.beginPath();
      [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([a, b], i) => { const q = pt(cx + a * L, cy + b * L); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
      ctx.closePath(); ctx.fill();
      ctx.strokeStyle = "rgba(140,170,110,0.35)"; ctx.lineWidth = 0.6 * dpr; ctx.beginPath();
      for (let i = 0; i <= nl; i++) {
        const u = -L + 2 * L * i / nl;
        let a = pt(cx + u, cy - L), b = pt(cx + u, cy + L); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]);
        a = pt(cx - L, cy + u); b = pt(cx + L, cy + u); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]);
      }
      ctx.stroke();
    }
    if (mostra.aneis) {
      ctx.strokeStyle = "rgba(120,170,230,0.55)"; ctx.lineWidth = 0.7 * dpr; ctx.beginPath();
      for (const a of f.aneis) {
        const [nr, nc] = a.n, at = (i, j) => { const k = 3 * (i * nc + j); return proj(a.p[k], a.p[k + 1], a.p[k + 2]); };
        for (let i = 0; i < nr; i++) for (let j = 0; j < nc; j++) {
          const p = at(i, j);
          if (j + 1 < nc) { const b = at(i, j + 1); ctx.moveTo(p[0], p[1]); ctx.lineTo(b[0], b[1]); }
          if (i + 1 < nr) { const b = at(i + 1, j); ctx.moveTo(p[0], p[1]); ctx.lineTo(b[0], b[1]); }
        }
      }
      ctx.stroke();
    }
    if (f.pas) {
      // pás da hélice girante: a linha ligada de cada pá, grossa
      ctx.strokeStyle = "rgba(240,150,60,0.95)"; ctx.lineWidth = 2.6 * dpr; ctx.lineCap = "round"; ctx.beginPath();
      for (const a of f.pas) for (let i = 0; i + 5 < a.length; i += 3) {
        const p = proj(a[i], a[i + 1], a[i + 2]), b = proj(a[i + 3], a[i + 4], a[i + 5]);
        ctx.moveTo(p[0], p[1]); ctx.lineTo(b[0], b[1]);
      }
      ctx.stroke(); ctx.lineCap = "butt";
    }
    if (mostra.part && f.X) {
      const n = f.w.length, ord = f._ord || (f._ord = Array.from({ length: n }, (_, i) => i).sort((a, b) => f.w[a] - f.w[b]));
      const t = Math.max(1.5, 2.2 * dpr * Math.sqrt(zoom));
      for (const i of ord) {
        const p = proj(f.X[3 * i], f.X[3 * i + 1], f.X[3 * i + 2]);
        ctx.fillStyle = PAL[f.w[i]]; ctx.fillRect(p[0] - t / 2, p[1] - t / 2, t, t);
      }
    }
    triedro(d, r, u, dpr);
    sl.value = q;
    info.textContent = `t = ${fmt(f.t, 3)} s · CL = ${fmt(f.CL, 3)}` + (f.n_part ? ` · ${f.n_part} partículas (mostrando ${f.w.length})` : "") + ` · quadro ${q + 1}/${D.quadros.length}`;
    graficoCL();
  }

  function triedro(d, r, u, dpr) {
    const o = [44 * dpr, cv.height - 44 * dpr], L = 26 * dpr;
    [["x", [1, 0, 0], "#d9534f"], ["y", [0, 1, 0], "#5cb85c"], ["z", [0, 0, 1], "#5b9bd5"]].forEach(([n, e, cor]) => {
      const x = o[0] + L * (e[0] * r[0] + e[1] * r[1] + e[2] * r[2]), y = o[1] - L * (e[0] * u[0] + e[1] * u[1] + e[2] * u[2]);
      ctx.strokeStyle = cor; ctx.lineWidth = 2 * dpr; ctx.beginPath(); ctx.moveTo(o[0], o[1]); ctx.lineTo(x, y); ctx.stroke();
      ctx.fillStyle = cor; ctx.font = `${11 * dpr}px sans-serif`; ctx.fillText(n, x + 2 * dpr, y - 2 * dpr);
    });
  }

  function graficoCL() {
    const W = cl.width, H = cl.height, Q = D.quadros, dpr = window.devicePixelRatio || 1;
    cctx.clearRect(0, 0, W, H);
    // o 1º quadro leva o impulso de massa aparente da partida: fica fora da escala
    const t0 = Q[0].t, t1 = Q[Q.length - 1].t || 1, ys = (Q.length > 3 ? Q.slice(1) : Q).map(f => f.CL), y0 = Math.min(...ys), y1 = Math.max(...ys) + 1e-9;
    const px = t => 8 * dpr + (W - 16 * dpr) * (t - t0) / (t1 - t0 || 1), py = y => H - 6 * dpr - (H - 14 * dpr) * (y - y0) / (y1 - y0);
    cctx.strokeStyle = "#4a86c5"; cctx.lineWidth = 1.5 * dpr; cctx.beginPath();
    const yc = y => py(Math.max(y0, Math.min(y1, y)));
    Q.forEach((f, i) => i ? cctx.lineTo(px(f.t), yc(f.CL)) : cctx.moveTo(px(f.t), yc(f.CL))); cctx.stroke();
    cctx.strokeStyle = "#ca835c"; cctx.beginPath(); cctx.moveTo(px(Q[q].t), 0); cctx.lineTo(px(Q[q].t), H); cctx.stroke();
    cctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--suave") || "#999"; cctx.font = `${10 * dpr}px sans-serif`;
    cctx.fillText(`CL ${fmt(y1, 3)}`, 10 * dpr, 11 * dpr); cctx.fillText(fmt(y0, 3), 10 * dpr, H - 8 * dpr);
  }

  function anda(ts) {
    if (!tocando) return;
    if (ts - ult > 1000 / (12 * vel)) { ult = ts; q = (q + 1) % D.quadros.length; desenha(); }
    requestAnimationFrame(anda);
  }
  function toca(sim) { tocando = sim; $("visor_play").textContent = sim ? "⏸" : "▶"; if (sim) requestAnimationFrame(anda); }

  // interação: arrastar gira, Shift + arrastar (ou botão direito) desloca, roda dá zoom, duplo clique reajusta
  let arr = null;
  cv.addEventListener("pointerdown", ev => { arr = { x: ev.clientX, y: ev.clientY, pan: ev.shiftKey || ev.button === 2 }; cv.setPointerCapture(ev.pointerId); });
  cv.addEventListener("pointermove", ev => {
    if (!arr) return;
    const dx = ev.clientX - arr.x, dy = ev.clientY - arr.y, dpr = window.devicePixelRatio || 1; arr.x = ev.clientX; arr.y = ev.clientY;
    if (arr.pan) { pan[0] += dx * dpr; pan[1] += dy * dpr; } else { az -= dx * 0.4; el = Math.max(-89.9, Math.min(89.9, el + dy * 0.4)); }
    desenha();
  });
  cv.addEventListener("pointerup", () => { arr = null; });
  cv.addEventListener("contextmenu", ev => ev.preventDefault());
  cv.addEventListener("wheel", ev => { ev.preventDefault(); zoom *= Math.exp(-ev.deltaY * 0.0015); desenha(); }, { passive: false });
  cv.addEventListener("dblclick", () => { zoom = 1; pan = [0, 0]; desenha(); });
  sl.oninput = () => { q = +sl.value; desenha(); };
  cl.addEventListener("click", ev => {
    const x = ev.offsetX / cl.clientWidth, Q = D.quadros, t = Q[0].t + x * (Q[Q.length - 1].t - Q[0].t);
    q = Q.reduce((m, f, i) => Math.abs(f.t - t) < Math.abs(Q[m].t - t) ? i : m, 0); desenha();
  });
  $("visor_play").onclick = () => toca(!tocando);
  $("visor_vel").onchange = ev => { vel = +ev.target.value; };
  dlg.querySelectorAll("[data-visor-vista]").forEach(b => { b.onclick = () => { [az, el] = VISTAS[b.dataset.visorVista]; desenha(); }; });
  dlg.querySelectorAll("[data-visor-mostra]").forEach(c => { c.onchange = () => { mostra[c.dataset.visorMostra] = c.checked; desenha(); }; });
  $("visor_fechar").onclick = () => { toca(false); dlg.close(); };
  window.addEventListener("resize", () => { if (dlg.open) { tamanho(); desenha(); } });
  document.addEventListener("keydown", ev => {
    if (!dlg.open || ev.target.tagName === "INPUT" && ev.target.type !== "range") return;
    if (ev.key === " ") { ev.preventDefault(); toca(!tocando); }
    if (ev.key === "ArrowRight") { q = Math.min(D.quadros.length - 1, q + 1); desenha(); }
    if (ev.key === "ArrowLeft") { q = Math.max(0, q - 1); desenha(); }
  });

  function abre(dados, titulo) {
    D = dados; q = D.quadros.length - 1; [az, el] = VISTAS.iso;
    corpoQ = [];
    for (let i = 0; i < D.corpo.length; i += 12) {
      const Q = [0, 1, 2, 3].map(k => [D.corpo[i + 3 * k], D.corpo[i + 3 * k + 1], D.corpo[i + 3 * k + 2]]);
      const a = Q[2].map((v, j) => v - Q[0][j]), b = Q[3].map((v, j) => v - Q[1][j]);
      const n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]], m = Math.hypot(...n) || 1;
      Q.n = n.map(v => v / m); corpoQ.push(Q);
    }
    sl.max = D.quadros.length - 1; sl.value = q;
    $("visor_tit").textContent = titulo || "Esteira";
    $("visor_leg").hidden = !D.quadros.some(f => f.X);
    dlg.showModal(); tamanho(); ajusta(); desenha();
  }
  return { abre, desenha };
})();
