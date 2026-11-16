"use strict";

class Vista3D {
  constructor(canvas) {
    this.cv = canvas;
    this.ctx = canvas.getContext("2d");
    this.cam = { yaw: -2.2, pitch: 0.38, zoom: 1, px: 0, py: 0 };
    this.malha = null;
    this.cores = [];
    this.visivel = null;
    this.modo = "solido";
    this.destaque = null;
    this.centro = [0, 0, 0];
    this.raio = 1;
    this.cg = null;
    this.aneis = null;
    this.sobreId = null;
    this.paleta = [null];
    this.legenda = null;
    this.aoClicar = null;
    this.extra = null;
    this.pontos = null;
    this.hud = null;
    this.ferramenta = null;
    this.aoMover = null;
    this.aoDesenhar = null;
    this.estilo = null;
    this.solo = null;
    this._liga();
    new ResizeObserver(() => this.desenha()).observe(canvas.parentElement);
    Tema.aoMudar(() => this.desenha());
  }

  defineMalha(m, cores) {
    const V = Float32Array.from(m.V), T = Uint32Array.from(m.T);
    const nt = T.length / 3, N = new Float32Array(nt * 3);
    for (let t = 0; t < nt; t++) {
      const a = T[3 * t] * 3, b = T[3 * t + 1] * 3, c = T[3 * t + 2] * 3;
      const ux = V[b] - V[a], uy = V[b + 1] - V[a + 1], uz = V[b + 2] - V[a + 2];
      const vx = V[c] - V[a], vy = V[c + 1] - V[a + 1], vz = V[c + 2] - V[a + 2];
      let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      const l = Math.hypot(nx, ny, nz) || 1;
      N[3 * t] = nx / l; N[3 * t + 1] = ny / l; N[3 * t + 2] = nz / l;
    }
    this.malha = { V, T, N, zona: Int32Array.from(m.zona), nt };
    this.cores = cores;
    this.sobreId = null;
    this.visivel = new Uint8Array(m.zonas.length).fill(1);
    const [lo, hi] = m.bbox;
    this.centro = [0, 1, 2].map(i => (lo[i] + hi[i]) / 2);
    this.raio = Math.max(Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2, 1e-6);
    this.cg = m.cg_m;
    const maior = Math.max(hi[0] - lo[0], hi[1] - lo[1]), passo = maior > 4 ? 0.5 : maior > 1.5 ? 0.25 : 0.1, f = v => Math.floor(v / passo) * passo, c = v => Math.ceil(v / passo) * passo;
    this.solo = { z: lo[2], x0: f(lo[0]) - passo, x1: c(hi[0]) + passo, y0: f(lo[1]) - passo, y1: c(hi[1]) + passo, passo };
    this.desenha();
  }

  limpa() { this.malha = null; this.cg = null; this.sobreId = null; this.legenda = null; this.desenha(); }

  defineSobre(ids, paleta, legenda) { this.sobreId = ids; this.paleta = paleta; this.legenda = legenda || null; this.desenha(); }

  limpaSobre() { this.sobreId = null; this.paleta = [null]; this.legenda = null; this.desenha(); }

  vista(nome) {
    const P = Math.PI;
    const v = { iso: [-2.2, 0.38], lateral: [0, 0], topo: [-P / 2, P / 2 - 0.001], frontal: [P / 2, 0] }[nome];
    if (v) { this.cam.yaw = v[0]; this.cam.pitch = v[1]; }
    this.ajusta();
  }

  ajusta() { Object.assign(this.cam, { zoom: 1, px: 0, py: 0 }); this.desenha(); }

  _base() {
    const { yaw, pitch } = this.cam;
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    return { cy, sy, cp, sp };
  }

  _projeta(x, y, z, B, esc, W, H) {
    x -= this.centro[0]; y -= this.centro[1]; z -= this.centro[2];
    const rx = x * B.cy - y * B.sy, ry = x * B.sy + y * B.cy;
    const sx = rx, sy = z * B.cp + ry * B.sp, prof = ry * B.cp - z * B.sp;
    return [W / 2 + this.cam.px + sx * esc, H / 2 + this.cam.py - sy * esc, prof];
  }

  desenha() {
    const cv = this.cv, pai = cv.parentElement;
    const d = window.devicePixelRatio || 1, W = pai.clientWidth, H = pai.clientHeight;
    if (!W || !H) return;
    if (cv.width !== Math.round(W * d) || cv.height !== Math.round(H * d)) {
      cv.width = Math.round(W * d); cv.height = Math.round(H * d);
      cv.style.width = W + "px"; cv.style.height = H + "px";
    }
    const g = this.ctx;
    g.setTransform(d, 0, 0, d, 0, 0);
    if (this.estilo === "nova") { const gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, Tema.cor("--vista") || "#dde1d3"); gr.addColorStop(1, Tema.cor("--vista2") || "#c9cfbc"); g.fillStyle = gr; }
    else g.fillStyle = Tema.cor("--vista") || "#0f1722";
    g.fillRect(0, 0, W, H);
    if (!this.malha) {
      g.fillStyle = "#7f8da1"; g.font = "13px Segoe UI, sans-serif"; g.textAlign = "center";
      g.fillText("Abra uma aeronave ou insira um elemento", W / 2, H / 2);
      return;
    }
    const { V, T, N, zona, nt } = this.malha, B = this._base();
    const esc = (Math.min(W, H) * 0.6 / this.raio) * this.cam.zoom;
    this._ult = { B, esc, W, H };
    const nv = V.length / 3, P = new Float32Array(nv * 3);
    for (let i = 0; i < nv; i++) {
      const q = this._projeta(V[3 * i], V[3 * i + 1], V[3 * i + 2], B, esc, W, H);
      P[3 * i] = q[0]; P[3 * i + 1] = q[1]; P[3 * i + 2] = q[2];
    }
    if (this.estilo === "nova" && this.solo) this._desenhaSolo(g, B, esc, W, H);
    const ordem = [];
    for (let t = 0; t < nt; t++) {
      if (!this.visivel[zona[t]]) continue;
      const a = T[3 * t] * 3, b = T[3 * t + 1] * 3, c = T[3 * t + 2] * 3;
      ordem.push([(P[a + 2] + P[b + 2] + P[c + 2]) / 3, t]);
    }
    this._P = P;
    ordem.sort((u, v) => v[0] - u[0]);
    const luz = [0.4, -0.5, 0.75], ll = Math.hypot(...luz);
    const cache = new Map();
    for (const [, t] of ordem) {
      const a = T[3 * t] * 3, b = T[3 * t + 1] * 3, c = T[3 * t + 2] * 3;
      const z = zona[t];
      const nx = N[3 * t], ny = N[3 * t + 1], nz = N[3 * t + 2];
      const sh = Math.min(1, 0.32 + 0.68 * Math.abs((nx * luz[0] + ny * luz[1] + nz * luz[2]) / ll));
      const sid = this.sobreId ? this.sobreId[t] : 0;
      const chave = (sid ? 100000 + sid : z) * 40 + Math.round(sh * 39);
      let cor = cache.get(chave);
      if (!cor) {
        const [r, gg, bb] = sid ? this.paleta[sid] : (this.cores[z] || [160, 160, 160]);
        const real = this.destaque && this.destaque.has(z) ? 1.25 : 1;
        cor = `rgb(${Math.min(255, r * sh * real) | 0},${Math.min(255, gg * sh * real) | 0},${Math.min(255, bb * sh * real) | 0})`;
        cache.set(chave, cor);
      }
      g.beginPath();
      g.moveTo(P[a], P[a + 1]); g.lineTo(P[b], P[b + 1]); g.lineTo(P[c], P[c + 1]); g.closePath();
      if (this.modo === "solido") { g.fillStyle = cor; g.fill(); g.strokeStyle = cor; g.lineWidth = 0.6; g.stroke(); }
      else { g.strokeStyle = this.destaque && this.destaque.has(z) ? "#ca835c" : "#6f86a6"; g.lineWidth = 0.5; g.stroke(); }
    }
    if (this.aneis || this.extra) this._desenhaAneis(g, B, esc, W, H);
    this._eixos(g, B, W, H);
    if (this.pontos) this._desenhaPontos(g, B, esc, W, H);
    if (this.legenda) this._desenhaLegenda(g, W, H);
    if (this.hud) this._desenhaHud(g, W, H);
    if (this.cg) this._marcaCG(g, B, esc, W, H);
    if (this.aoDesenhar) this.aoDesenhar(g, B, esc, W, H);
  }

  _desenhaSolo(g, B, esc, W, H) {
    const { z, x0, x1, y0, y1, passo } = this.solo;
    g.save(); g.strokeStyle = Tema.cor("--linha") || "#999"; g.globalAlpha = 0.55; g.lineWidth = 1; g.beginPath();
    for (let x = x0; x <= x1 + 1e-9; x += passo) { const a = this._projeta(x, y0, z, B, esc, W, H), b = this._projeta(x, y1, z, B, esc, W, H); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); }
    for (let y = y0; y <= y1 + 1e-9; y += passo) { const a = this._projeta(x0, y, z, B, esc, W, H), b = this._projeta(x1, y, z, B, esc, W, H); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); }
    g.stroke(); g.restore();
  }

  zonaEm(px, py) {
    if (!this.malha || !this._P) return -1;
    const { T, zona, nt } = this.malha, P = this._P;
    let melhor = -1, prof = Infinity;
    for (let t = 0; t < nt; t++) {
      if (!this.visivel[zona[t]]) continue;
      const a = T[3 * t] * 3, b = T[3 * t + 1] * 3, c = T[3 * t + 2] * 3;
      const d1 = (px - P[b]) * (P[a + 1] - P[b + 1]) - (P[a] - P[b]) * (py - P[b + 1]);
      const d2 = (px - P[c]) * (P[b + 1] - P[c + 1]) - (P[b] - P[c]) * (py - P[c + 1]);
      const d3 = (px - P[a]) * (P[c + 1] - P[a + 1]) - (P[c] - P[a]) * (py - P[a + 1]);
      if (((d1 < 0) || (d2 < 0) || (d3 < 0)) && ((d1 > 0) || (d2 > 0) || (d3 > 0))) continue;
      const z = (P[a + 2] + P[b + 2] + P[c + 2]) / 3;
      if (z < prof) { prof = z; melhor = zona[t]; }
    }
    return melhor;
  }

  verticeEm(px, py, raio = 12) {
    if (!this.malha || !this._P) return null;
    const { V, T, zona, nt } = this.malha, P = this._P;
    let mel = -1, d0 = raio;
    for (let t = 0; t < nt; t++) {
      if (!this.visivel[zona[t]]) continue;
      for (let k = 0; k < 3; k++) {
        const i = T[3 * t + k], d = Math.hypot(P[3 * i] - px, P[3 * i + 1] - py);
        if (d < d0) { d0 = d; mel = i; }
      }
    }
    return mel < 0 ? null : [V[3 * mel], V[3 * mel + 1], V[3 * mel + 2]];
  }

  olha(yaw, pitch) { this.cam.yaw = yaw; this.cam.pitch = pitch; this.ajusta(); }

  projetaXY(x, y, z) {
    if (!this._ult) return null;
    const { B, esc, W, H } = this._ult, q = this._projeta(x, y, z, B, esc, W, H);
    return [q[0], q[1]];
  }

  _desenhaAneis(g, B, esc, W, H) {
    for (const a of (this.aneis || []).concat(this.extra || [])) {
      g.beginPath();
      a.pts.forEach((p, i) => { const q = this._projeta(p[0], p[1], p[2], B, esc, W, H); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); });
      g.closePath();
      g.strokeStyle = a.sel ? "#ffd447" : (a.cor || "rgba(255,255,255,.5)"); g.lineWidth = a.larg || (a.sel ? 2.6 : 1);
      g.stroke();
    }
  }

  _desenhaPontos(g, B, esc, W, H) {
    g.save();
    for (const a of this.pontos) {
      const q = this._projeta(a.p[0], a.p[1], a.p[2], B, esc, W, H), x = q[0], y = q[1], r = a.sel ? 7 : 5;
      if (a.vinculo) {
        const R = r + 5;
        g.beginPath();
        if (a.vinculo === "engaste") g.rect(x - R, y - R, 2 * R, 2 * R);
        else { g.moveTo(x, y - R); g.lineTo(x + R, y + R); g.lineTo(x - R, y + R); g.closePath(); }
        g.fillStyle = "rgba(90,110,60,.55)"; g.fill(); g.strokeStyle = "#e9d48a"; g.lineWidth = 1.6; g.stroke();
      }
      if (typeof a.margem === "number") {
        g.beginPath(); g.arc(x, y, r + 4, 0, 7);
        g.strokeStyle = a.margem < 0 ? "#7a4300" : a.margem < 0.5 ? "#e0b84a" : "#7d9440"; g.lineWidth = a.margem < 0 ? 4 : 2.6;
        if (a.margem < 0) g.setLineDash([4, 2]);
        g.stroke(); g.setLineDash([]);
      }
      if (a.ligacao) { g.beginPath(); g.arc(x, y, r + 8, 0, 7); g.strokeStyle = "#e9d48a"; g.lineWidth = 1.6; g.setLineDash([3, 3]); g.stroke(); g.setLineDash([]); }
      g.beginPath();
      if (a.forma === "parafuso") { g.moveTo(x, y - r - 1); g.lineTo(x + r + 1, y); g.lineTo(x, y + r + 1); g.lineTo(x - r - 1, y); g.closePath(); }
      else g.arc(x, y, r, 0, 7);
      g.fillStyle = a.forma === "rotula" ? "rgba(20,26,34,.9)" : (a.sel ? "#ffd447" : "rgba(255,159,67,.9)"); g.fill();
      g.strokeStyle = a.forma === "rotula" ? (a.sel ? "#ffd447" : "#ff9f43") : "rgba(0,0,0,.65)"; g.lineWidth = a.forma === "rotula" ? 2.4 : 1.2; g.stroke();
    }
    g.restore();
  }

  _desenhaHud(g, W, H) {
    let L = this.hud;
    if (this.estilo === "nova") { const k = L.findIndex(t => t.startsWith("Arraste")); if (k > 0) L = L.slice(0, k).concat("? lista os atalhos · Esc sai"); }
    g.save(); g.font = "11px Segoe UI, sans-serif"; g.textAlign = "left";
    const w = Math.max(...L.map(t => g.measureText(t).width)) + 16, h = 8 + 15 * L.length, x = W - w - 12, y = 12;
    g.fillStyle = "rgba(20,26,34,.85)"; g.strokeStyle = "rgba(255,212,71,.55)"; g.lineWidth = 1;
    g.fillRect(x, y, w, h); g.strokeRect(x + .5, y + .5, w, h);
    L.forEach((t, i) => { g.fillStyle = i === 0 ? "#ffd447" : "#c3ccd8"; g.fillText(t, x + 8, y + 18 + 15 * i); });
    g.restore();
  }

  _desenhaLegenda(g, W, H) {
    const L = this.legenda, x = 12, y = 12, w = 210, h = 74 + 14 * (L.linhas || []).length;
    g.save();
    g.fillStyle = "rgba(20,26,34,.82)"; g.strokeStyle = "rgba(255,255,255,.25)"; g.lineWidth = 1;
    g.fillRect(x, y, w, h); g.strokeRect(x + .5, y + .5, w, h);
    g.fillStyle = "#e8edf4"; g.font = "bold 11px Segoe UI, sans-serif"; g.textAlign = "left"; g.fillText(L.titulo, x + 8, y + 16);
    g.font = "10px Segoe UI, sans-serif"; g.fillStyle = "#c3ccd8";
    g.fillText("deformação ao desdobrar a pele (%)", x + 8, y + 30);
    const gr = g.createLinearGradient(x + 8, 0, x + w - 8, 0);
    L.escala.forEach(([f, c]) => gr.addColorStop(f, c));
    g.fillStyle = gr; g.fillRect(x + 8, y + 36, w - 16, 10);
    g.fillStyle = "#c3ccd8"; g.fillText("0", x + 8, y + 59); g.textAlign = "center"; g.fillText(L.limite, x + 8 + (w - 16) / 3, y + 59); g.textAlign = "right"; g.fillText(L.maximo, x + w - 8, y + 59);
    g.textAlign = "left";
    (L.linhas || []).forEach((s, i) => g.fillText(s, x + 8, y + 74 + 14 * i));
    g.restore();
  }

  _marcaCG(g, B, esc, W, H) {
    const [x, y] = this._projeta(this.cg[0], this.cg[1], this.cg[2], B, esc, W, H);
    g.strokeStyle = "#ffd447"; g.lineWidth = 1.5;
    g.beginPath(); g.arc(x, y, 6, 0, 7); g.moveTo(x - 10, y); g.lineTo(x + 10, y);
    g.moveTo(x, y - 10); g.lineTo(x, y + 10); g.stroke();
  }

  _eixos(g, B, W, H) {
    const o = [34, H - 30], L = 22;
    const eixo = (vx, vy, vz, cor, nome) => {
      const rx = vx * B.cy - vy * B.sy, ry = vx * B.sy + vy * B.cy;
      const sx = rx, sy = vz * B.cp + ry * B.sp;
      g.strokeStyle = cor; g.fillStyle = cor; g.lineWidth = 1.5;
      g.beginPath(); g.moveTo(o[0], o[1]); g.lineTo(o[0] + sx * L, o[1] - sy * L); g.stroke();
      g.font = "10px Segoe UI, sans-serif"; g.fillText(nome, o[0] + sx * (L + 7) - 3, o[1] - sy * (L + 7) + 3);
    };
    eixo(1, 0, 0, "#d9a521", "x"); eixo(0, 1, 0, "#5cc16d", "y"); eixo(0, 0, 1, "#5c9bf0", "z");
  }

  _liga() {
    const cv = this.cv;
    let arr = null;
    cv.addEventListener("mousedown", e => {
      arr = { x: e.clientX, y: e.clientY, pan: e.shiftKey || e.button === 1 || e.button === 2, dist: 0 };
      if (e.button === 0 && this.ferramenta) { const r = cv.getBoundingClientRect(); if (this.ferramenta.baixo(e.clientX - r.left, e.clientY - r.top, e)) { arr.ferr = true; arr.pan = false; } }
      e.preventDefault();
    });
    window.addEventListener("mouseup", e => {
      if (arr && arr.ferr) { const r = cv.getBoundingClientRect(); this.ferramenta && this.ferramenta.solta(e.clientX - r.left, e.clientY - r.top, e); arr = null; return; }
      if (arr && arr.dist < 4 && !arr.pan && this.aoClicar) { const r = cv.getBoundingClientRect(); this.aoClicar(e.clientX - r.left, e.clientY - r.top); }
      arr = null;
    });
    window.addEventListener("mousemove", e => {
      if (!arr) { if (this.aoMover && e.target === cv) { const r = cv.getBoundingClientRect(); this.aoMover(e.clientX - r.left, e.clientY - r.top, e); } return; }
      if (arr.ferr) { const r = cv.getBoundingClientRect(); this.ferramenta && this.ferramenta.move(e.clientX - r.left, e.clientY - r.top, e); return; }
      const dx = e.clientX - arr.x, dy = e.clientY - arr.y;
      arr.dist += Math.abs(dx) + Math.abs(dy);
      arr.x = e.clientX; arr.y = e.clientY;
      if (arr.pan) { this.cam.px += dx; this.cam.py += dy; }
      else {
        this.cam.yaw += dx * 0.008;
        this.cam.pitch = Math.max(-1.5, Math.min(1.5, this.cam.pitch + dy * 0.008));
      }
      this.desenha();
    });
    cv.addEventListener("wheel", e => {
      e.preventDefault();
      this.cam.zoom = Math.max(0.2, Math.min(12, this.cam.zoom * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
      this.desenha();
    }, { passive: false });
    cv.addEventListener("contextmenu", e => e.preventDefault());
  }
}
