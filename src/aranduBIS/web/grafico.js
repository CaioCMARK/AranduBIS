"use strict";

const Grafico = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#c85a5a", "#a278c8", "#5aaaaa"];

  const no = (tag, attrs = {}, txt) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (txt !== undefined) e.textContent = txt;
    return e;
  };

  function passo(min, max, n) {
    const bruto = (max - min) / Math.max(n, 1), mag = Math.pow(10, Math.floor(Math.log10(bruto || 1)));
    const f = bruto / mag, p = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
    return p;
  }

  function eixo(min, max, n) {
    if (!(max > min)) { max = min + 1; }
    const p = passo(min, max, n), a = Math.floor(min / p) * p, b = Math.ceil(max / p) * p, t = [];
    for (let v = a; v <= b + p / 2; v += p) t.push(+v.toFixed(10));
    return { min: a, max: b, ticks: t };
  }

  const fmt = v => Math.abs(v) >= 1000 || (v !== 0 && Math.abs(v) < 0.01) ? v.toExponential(1) : String(+v.toFixed(3));

  function nomeArquivo(titulo) {
    return (titulo || "grafico").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") + ".png";
  }

  function baixarPNG(svg, titulo) {
    const W = +svg.getAttribute("width"), H = +svg.getAttribute("height");
    const clone = svg.cloneNode(true);
    const cor = getComputedStyle(document.body).color;
    const fundo = getComputedStyle(document.documentElement).getPropertyValue("--painel").trim() || "#fff";
    clone.setAttribute("style", `color:${cor}`);
    clone.insertBefore(no("rect", { x: 0, y: 0, width: W, height: H, fill: fundo }), clone.firstChild);
    const xml = new XMLSerializer().serializeToString(clone);
    const img = new Image();
    img.onload = () => {
      const esc = 2;
      const c = document.createElement("canvas"); c.width = W * esc; c.height = H * esc;
      const ctx = c.getContext("2d"); ctx.scale(esc, esc); ctx.drawImage(img, 0, 0, W, H);
      c.toBlob(blob => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = nomeArquivo(titulo);
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      });
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
  }

  function desenha(alvo, o) {
    alvo.innerHTML = "";
    const W = Math.max(alvo.clientWidth, 260), H = Math.max(alvo.clientHeight, 160);
    const m = { e: 54, d: 14, c: o.titulo ? 24 : 10, b: 38 };
    const svg = no("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": o.titulo || "gráfico" });
    let x0 = Infinity, x1 = -Infinity, y0 = o.yMin ?? Infinity, y1 = o.yMax ?? -Infinity;
    const vale = v => v !== null && v !== undefined && Number.isFinite(v);
    for (const s of o.series) s.x.forEach((x, i) => {
      if (!vale(x) || !vale(s.y[i])) return;
      x0 = Math.min(x0, x); x1 = Math.max(x1, x);
      if (o.yMin === undefined) y0 = Math.min(y0, s.y[i]);
      if (o.yMax === undefined) y1 = Math.max(y1, s.y[i]);
    });
    for (const r of o.refs || []) {
      if (r.tipo === "h") { if (o.yMin === undefined) y0 = Math.min(y0, r.valor); if (o.yMax === undefined) y1 = Math.max(y1, r.valor); }
      else { x0 = Math.min(x0, r.valor); x1 = Math.max(x1, r.valor); }
    }
    for (const p of o.pontos || []) { x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); }
    if (!Number.isFinite(x0)) { svg.append(no("text", { x: W / 2, y: H / 2, "text-anchor": "middle", fill: "currentColor", opacity: .6 }, "Sem dados")); alvo.append(svg); return; }
    if (o.yMax === undefined && Number.isFinite(y0) && y1 > y0) y1 += (y1 - y0) * 0.14;
    const X = eixo(x0, x1, Math.max(3, W / 90)), Y = eixo(y0, y1, Math.max(3, H / 55));
    const px = v => m.e + (v - X.min) / (X.max - X.min) * (W - m.e - m.d);
    const py = v => H - m.b - (v - Y.min) / (Y.max - Y.min) * (H - m.b - m.c);
    for (const t of Y.ticks) {
      svg.append(no("line", { x1: m.e, x2: W - m.d, y1: py(t), y2: py(t), stroke: "currentColor", opacity: t === 0 ? .45 : .12 }));
      svg.append(no("text", { x: m.e - 6, y: py(t) + 3.5, "text-anchor": "end", fill: "currentColor", "font-size": 10.5, opacity: .75 }, fmt(t)));
    }
    for (const t of X.ticks) {
      svg.append(no("line", { x1: px(t), x2: px(t), y1: m.c, y2: H - m.b, stroke: "currentColor", opacity: .08 }));
      svg.append(no("text", { x: px(t), y: H - m.b + 14, "text-anchor": "middle", fill: "currentColor", "font-size": 10.5, opacity: .75 }, fmt(t)));
    }
    svg.append(no("rect", { x: m.e, y: m.c, width: W - m.e - m.d, height: H - m.c - m.b, fill: "none", stroke: "currentColor", opacity: .35 }));
    if (o.xlab) svg.append(no("text", { x: (m.e + W - m.d) / 2, y: H - 6, "text-anchor": "middle", fill: "currentColor", "font-size": 11 }, o.xlab));
    if (o.ylab) svg.append(no("text", { x: 12, y: (m.c + H - m.b) / 2, "text-anchor": "middle", fill: "currentColor", "font-size": 11, transform: `rotate(-90 12 ${(m.c + H - m.b) / 2})` }, o.ylab));
    if (o.titulo) svg.append(no("text", { x: m.e, y: 15, fill: "currentColor", "font-size": 12, "font-weight": 600 }, o.titulo));
    for (const r of o.refs || []) {
      const cor = r.cor || "#ca835c";
      const a = r.tipo === "h" ? { x1: m.e, x2: W - m.d, y1: py(r.valor), y2: py(r.valor) } : { x1: px(r.valor), x2: px(r.valor), y1: m.c, y2: H - m.b };
      svg.append(no("line", { ...a, stroke: cor, "stroke-width": 1.5, "stroke-dasharray": "6 4" }));
      if (r.rotulo) {
        const direita = r.tipo === "v" && px(r.valor) > W * 0.7;
        svg.append(no("text", { x: r.tipo === "h" ? W - m.d - 4 : px(r.valor) + (direita ? -4 : 4), y: r.tipo === "h" ? py(r.valor) - 4 : H - m.b - 6, "text-anchor": r.tipo === "h" || direita ? "end" : "start", fill: cor, "font-size": 10.5 }, r.rotulo));
      }
    }
    o.series.forEach((s, k) => {
      const cor = s.cor || COR[k % COR.length];
      let d = "", aberto = false;
      s.x.forEach((x, i) => {
        if (!vale(x) || !vale(s.y[i])) { aberto = false; return; }
        d += `${aberto ? "L" : "M"}${px(x).toFixed(1)} ${py(s.y[i]).toFixed(1)}`; aberto = true;
      });
      svg.append(no("path", { d, fill: "none", stroke: cor, "stroke-width": 2, "stroke-dasharray": s.tracejado ? "5 3" : "none" }));
    });
    for (const p of o.pontos || []) {
      const cor = p.cor || "#ffd447";
      svg.append(no("circle", { cx: px(p.x), cy: py(p.y), r: 5, fill: cor, stroke: "#000", "stroke-opacity": .4 }));
      if (p.rotulo) svg.append(no("text", { x: px(p.x) + 8, y: py(p.y) - 6, fill: "currentColor", "font-size": 10.5 }, p.rotulo));
    }
    if (o.series.length > 1 || o.series.some(s => s.nome)) {
      let lx = m.e + 8;
      o.series.forEach((s, k) => {
        if (!s.nome) return;
        const cor = s.cor || COR[k % COR.length];
        svg.append(no("line", { x1: lx, x2: lx + 16, y1: m.c + 10, y2: m.c + 10, stroke: cor, "stroke-width": 2, "stroke-dasharray": s.tracejado ? "5 3" : "none" }));
        const t = no("text", { x: lx + 20, y: m.c + 14, fill: "currentColor", "font-size": 10.5 }, s.nome);
        svg.append(t); lx += 28 + s.nome.length * 6.2;
      });
    }
    alvo.append(svg);
    const b = document.createElement("button");
    b.type = "button"; b.className = "graf-baixar"; b.title = "Baixar gráfico (PNG)"; b.textContent = "⤓";
    b.onclick = e => { e.stopPropagation(); baixarPNG(svg, o.titulo); };
    alvo.append(b);
  }

  function liga(alvo, fn) {
    new ResizeObserver(() => fn()).observe(alvo);
  }

  return { desenha, liga };
})();
