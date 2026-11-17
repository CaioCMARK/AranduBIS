"use strict";

const Grafico = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const COR = ["#2f93ad", "#e29a2c", "#c4533a", "#7aa35a", "#8a86c4", "#9aa6b2"];

  const ROT = 'Bahnschrift,"DIN Alternate","Roboto Condensed","Arial Narrow",sans-serif', MONO = '"Cascadia Mono",Consolas,"SF Mono","Liberation Mono",monospace';
  const CSS = `.g-sub{stroke:currentColor;opacity:.08;stroke-dasharray:1 3}.g-maj{stroke:currentColor;opacity:.17}.g-zero{stroke:currentColor;opacity:.55}
.g-tick{stroke:currentColor;opacity:.75}.g-moldura{fill:none;stroke:currentColor;opacity:.6}
.gt{fill:currentColor;opacity:.82;font-family:${MONO}}.g-eixo{fill:currentColor;opacity:.88;font-family:${ROT};letter-spacing:.04em}
.g-titulo{fill:currentColor;font-family:${ROT};font-weight:700;letter-spacing:.09em;text-transform:uppercase}
.g-marca{fill:#e29a2c}.g-ponto{stroke:currentColor;stroke-opacity:.85;stroke-width:1}`;
  if (!document.getElementById("estilo-grafico")) { const st = document.createElement("style"); st.id = "estilo-grafico"; st.textContent = CSS; document.head.append(st); }

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
    clone.insertBefore(no("style", {}, CSS), clone.firstChild);
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
      const w2 = s.tipo === "barras" ? (s.largura || 0) / 2 : 0;
      x0 = Math.min(x0, x - w2); x1 = Math.max(x1, x + w2);
      if (s.tipo === "barras" && o.yMin === undefined) y0 = Math.min(y0, 0);
      if (o.yMin === undefined) y0 = Math.min(y0, s.y[i]);
      if (o.yMax === undefined) y1 = Math.max(y1, s.y[i]);
    });
    for (const r of o.refs || []) {
      if (r.tipo === "h") { if (o.yMin === undefined) y0 = Math.min(y0, r.valor); if (o.yMax === undefined) y1 = Math.max(y1, r.valor); }
      else { x0 = Math.min(x0, r.valor); x1 = Math.max(x1, r.valor); }
    }
    for (const p of o.pontos || []) { x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); }
    if (!Number.isFinite(x0)) { svg.append(no("text", { x: W / 2, y: H / 2, "text-anchor": "middle", fill: "currentColor", opacity: .6 }, o.vazio || "Sem dados")); alvo.append(svg); return; }
    if (o.yMax === undefined && Number.isFinite(y0) && y1 > y0) y1 += (y1 - y0) * 0.14;
    const X = eixo(x0, x1, Math.max(3, W / 90)), Y = eixo(y0, y1, Math.max(3, H / 55));
    const px = v => m.e + (v - X.min) / (X.max - X.min) * (W - m.e - m.d);
    const py = v => H - m.b - (v - Y.min) / (Y.max - Y.min) * (H - m.b - m.c);
    const sub = (T, pos, a, b, horiz) => {
      for (let i = 0; i + 1 < T.length; i++) {
        const mid = pos((T[i] + T[i + 1]) / 2);
        svg.append(no("line", horiz ? { x1: a, x2: b, y1: mid, y2: mid, class: "g-sub" } : { x1: mid, x2: mid, y1: a, y2: b, class: "g-sub" }));
      }
    };
    sub(Y.ticks, py, m.e, W - m.d, true); sub(X.ticks, px, m.c, H - m.b, false);
    for (const t of Y.ticks) {
      svg.append(no("line", { x1: m.e, x2: W - m.d, y1: py(t), y2: py(t), class: t === 0 ? "g-zero" : "g-maj" }));
      svg.append(no("line", { x1: m.e - 4, x2: m.e, y1: py(t), y2: py(t), class: "g-tick" }));
      svg.append(no("text", { x: m.e - 7, y: py(t) + 3.5, "text-anchor": "end", class: "gt", "font-size": 10.5 }, fmt(t)));
    }
    for (const t of X.ticks) {
      svg.append(no("line", { x1: px(t), x2: px(t), y1: m.c, y2: H - m.b, class: "g-maj" }));
      svg.append(no("line", { x1: px(t), x2: px(t), y1: H - m.b, y2: H - m.b + 4, class: "g-tick" }));
      svg.append(no("text", { x: px(t), y: H - m.b + 15, "text-anchor": "middle", class: "gt", "font-size": 10.5 }, fmt(t)));
    }
    svg.append(no("rect", { x: m.e, y: m.c, width: W - m.e - m.d, height: H - m.c - m.b, class: "g-moldura" }));
    if (o.xlab) svg.append(no("text", { x: (m.e + W - m.d) / 2, y: H - 6, "text-anchor": "middle", class: "g-eixo", "font-size": 11 }, o.xlab));
    if (o.ylab) svg.append(no("text", { x: 12, y: (m.c + H - m.b) / 2, "text-anchor": "middle", class: "g-eixo", "font-size": 11, transform: `rotate(-90 12 ${(m.c + H - m.b) / 2})` }, o.ylab));
    if (o.titulo) {
      svg.append(no("path", { d: `M${m.e} 9.5l3.5-3.5 3.5 3.5-3.5 3.5z`, class: "g-marca" }));
      svg.append(no("text", { x: m.e + 12, y: 14.5, class: "g-titulo", "font-size": 11.5 }, o.titulo));
    }
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
      if (s.tipo === "barras") {
        const g = no("g", { fill: cor, "fill-opacity": s.opacidade ?? .55, stroke: cor, "stroke-opacity": .9 }), w = s.largura || 0, base = py(Math.max(Y.min, 0));
        s.x.forEach((x, i) => { if (vale(x) && vale(s.y[i])) { const a = px(x - w / 2), b = px(x + w / 2); g.append(no("rect", { x: a.toFixed(1), y: py(s.y[i]).toFixed(1), width: Math.max(b - a - 1, 1).toFixed(1), height: Math.max(base - py(s.y[i]), 0).toFixed(1) })); } });
        svg.append(g); return;
      }
      if (s.marcador === "ponto") {
        const g = no("g", { fill: cor, "fill-opacity": s.opacidade ?? .8 });
        s.x.forEach((x, i) => { if (vale(x) && vale(s.y[i])) g.append(no("circle", { cx: px(x).toFixed(1), cy: py(s.y[i]).toFixed(1), r: s.raio || 1.6 })); });
        svg.append(g); return;
      }
      let d = "", aberto = false;
      s.x.forEach((x, i) => {
        if (!vale(x) || !vale(s.y[i])) { aberto = false; return; }
        d += `${aberto ? "L" : "M"}${px(x).toFixed(1)} ${py(s.y[i]).toFixed(1)}`; aberto = true;
      });
      svg.append(no("path", { d, fill: "none", stroke: cor, "stroke-width": 1.9, "stroke-linejoin": "round", "stroke-dasharray": s.tracejado ? "5 3" : "none" }));
    });
    for (const p of o.pontos || []) {
      const cor = p.cor || "#ffd447";
      svg.append(no("path", { d: `M${px(p.x)} ${py(p.y) - 6.5}l6.5 6.5-6.5 6.5-6.5-6.5z`, fill: cor, class: "g-ponto" }));
      if (p.rotulo) svg.append(no("text", { x: px(p.x) + 8, y: py(p.y) - 6, fill: "currentColor", "font-size": 10.5 }, p.rotulo));
    }
    if (o.series.length > 1 || o.series.some(s => s.nome)) {
      let lx = m.e + 8;
      o.series.forEach((s, k) => {
        if (!s.nome) return;
        const cor = s.cor || COR[k % COR.length];
        if (s.tipo === "barras") svg.append(no("rect", { x: lx, y: m.c + 5, width: 16, height: 9, fill: cor, "fill-opacity": s.opacidade ?? .55, stroke: cor }));
        else svg.append(no("line", { x1: lx, x2: lx + 16, y1: m.c + 10, y2: m.c + 10, stroke: cor, "stroke-width": 2, "stroke-dasharray": s.tracejado ? "5 3" : "none" }));
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
