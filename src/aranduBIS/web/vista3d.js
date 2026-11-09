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
    this.visivel = new Uint8Array(m.zonas.length).fill(1);
    const [lo, hi] = m.bbox;
    this.centro = [0, 1, 2].map(i => (lo[i] + hi[i]) / 2);
    this.raio = Math.max(Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2, 1e-6);
    this.cg = m.cg_m;
    this.desenha();
  }

  limpa() { this.malha = null; this.cg = null; this.desenha(); }

  vista(nome) {
    const P = Math.PI;
    const v = { iso: [-2.2, 0.38], lateral: [-P / 2, 0], topo: [-P / 2, P / 2 - 0.001], frontal: [0, 0] }[nome];
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
    const sx = rx, sy = z * B.cp - ry * B.sp, prof = ry * B.cp + z * B.sp;
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
    g.fillStyle = Tema.cor("--vista") || "#0f1722"; g.fillRect(0, 0, W, H);
    if (!this.malha) {
      g.fillStyle = "#7f8da1"; g.font = "13px Segoe UI, sans-serif"; g.textAlign = "center";
      g.fillText("Abra uma aeronave ou insira um elemento", W / 2, H / 2);
      return;
    }
    const { V, T, N, zona, nt } = this.malha, B = this._base();
    const esc = (Math.min(W, H) * 0.6 / this.raio) * this.cam.zoom;
    const nv = V.length / 3, P = new Float32Array(nv * 3);
    for (let i = 0; i < nv; i++) {
      const q = this._projeta(V[3 * i], V[3 * i + 1], V[3 * i + 2], B, esc, W, H);
      P[3 * i] = q[0]; P[3 * i + 1] = q[1]; P[3 * i + 2] = q[2];
    }
    const ordem = [];
    for (let t = 0; t < nt; t++) {
      if (!this.visivel[zona[t]]) continue;
      const a = T[3 * t] * 3, b = T[3 * t + 1] * 3, c = T[3 * t + 2] * 3;
      ordem.push([(P[a + 2] + P[b + 2] + P[c + 2]) / 3, t]);
    }
    ordem.sort((u, v) => v[0] - u[0]);
    const luz = [0.4, -0.5, 0.75], ll = Math.hypot(...luz);
    const cache = new Map();
    for (const [, t] of ordem) {
      const a = T[3 * t] * 3, b = T[3 * t + 1] * 3, c = T[3 * t + 2] * 3;
      const z = zona[t];
      const nx = N[3 * t], ny = N[3 * t + 1], nz = N[3 * t + 2];
      const sh = Math.min(1, 0.32 + 0.68 * Math.abs((nx * luz[0] + ny * luz[1] + nz * luz[2]) / ll));
      const chave = z * 40 + Math.round(sh * 39);
      let cor = cache.get(chave);
      if (!cor) {
        const [r, gg, bb] = this.cores[z] || [160, 160, 160];
        const real = this.destaque && this.destaque.has(z) ? 1.25 : 1;
        cor = `rgb(${Math.min(255, r * sh * real) | 0},${Math.min(255, gg * sh * real) | 0},${Math.min(255, bb * sh * real) | 0})`;
        cache.set(chave, cor);
      }
      g.beginPath();
      g.moveTo(P[a], P[a + 1]); g.lineTo(P[b], P[b + 1]); g.lineTo(P[c], P[c + 1]); g.closePath();
      if (this.modo === "solido") { g.fillStyle = cor; g.fill(); g.strokeStyle = cor; g.lineWidth = 0.6; g.stroke(); }
      else { g.strokeStyle = this.destaque && this.destaque.has(z) ? "#ca835c" : "#6f86a6"; g.lineWidth = 0.5; g.stroke(); }
    }
    this._eixos(g, B, W, H);
    if (this.cg) this._marcaCG(g, B, esc, W, H);
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
      const sx = rx, sy = vz * B.cp - ry * B.sp;
      g.strokeStyle = cor; g.fillStyle = cor; g.lineWidth = 1.5;
      g.beginPath(); g.moveTo(o[0], o[1]); g.lineTo(o[0] + sx * L, o[1] - sy * L); g.stroke();
      g.font = "10px Segoe UI, sans-serif"; g.fillText(nome, o[0] + sx * (L + 7) - 3, o[1] - sy * (L + 7) + 3);
    };
    eixo(1, 0, 0, "#e0615a", "x"); eixo(0, 1, 0, "#5cc16d", "y"); eixo(0, 0, 1, "#5c9bf0", "z");
  }

  _liga() {
    const cv = this.cv;
    let arr = null;
    cv.addEventListener("mousedown", e => { arr = { x: e.clientX, y: e.clientY, pan: e.shiftKey || e.button === 1 || e.button === 2 }; e.preventDefault(); });
    window.addEventListener("mouseup", () => { arr = null; });
    window.addEventListener("mousemove", e => {
      if (!arr) return;
      const dx = e.clientX - arr.x, dy = e.clientY - arr.y;
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
