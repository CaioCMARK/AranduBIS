"use strict";

const Chapa2D = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const r4 = v => +(+v).toFixed(5);

  function corta(V, T, zona, fora, y0) {
    const S = [], nt = T.length / 3;
    for (let t = 0; t < nt; t++) {
      if (fora && fora.has(zona[t])) continue;
      const i = [T[3 * t] * 3, T[3 * t + 1] * 3, T[3 * t + 2] * 3], d = i.map(k => V[k + 1] - y0);
      if ((d[0] > 0 && d[1] > 0 && d[2] > 0) || (d[0] < 0 && d[1] < 0 && d[2] < 0)) continue;
      const P = [];
      for (let a = 0; a < 3; a++) {
        const b = (a + 1) % 3;
        if ((d[a] > 0) === (d[b] > 0)) continue;
        const f = d[a] / (d[a] - d[b]);
        P.push([V[i[a]] + f * (V[i[b]] - V[i[a]]), V[i[a] + 2] + f * (V[i[b] + 2] - V[i[a] + 2])]);
      }
      if (P.length === 2 && Math.hypot(P[0][0] - P[1][0], P[0][1] - P[1][1]) > 1e-7) S.push([P[0][0], P[0][1], P[1][0], P[1][1]]);
    }
    return S;
  }

  const area = P => { let a = 0; P.forEach((p, i) => { const q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; }); return a / 2; };
  const perimetro = P => P.reduce((s, p, i) => { const q = P[(i + 1) % P.length]; return s + Math.hypot(q[0] - p[0], q[1] - p[1]); }, 0);

  function ladoMaisPerto(P, x, z) {
    let mel = { i: -1, d: Infinity, p: null };
    P.forEach((a, i) => {
      const b = P[(i + 1) % P.length], ux = b[0] - a[0], uz = b[1] - a[1], l2 = ux * ux + uz * uz;
      const t = l2 > 0 ? Math.max(0, Math.min(1, ((x - a[0]) * ux + (z - a[1]) * uz) / l2)) : 0;
      const p = [a[0] + t * ux, a[1] + t * uz], d = Math.hypot(x - p[0], z - p[1]);
      if (d < mel.d) mel = { i, d, p };
    });
    return mel;
  }

  function insere(P, x, z) {
    const m = ladoMaisPerto(P, x, z);
    if (m.i < 0) { P.push([r4(x), r4(z)]); return P.length - 1; }
    P.splice(m.i + 1, 0, [r4(m.p[0]), r4(m.p[1])]);
    return m.i + 1;
  }

  function circulo(cx, cz, raio, n = 24) {
    const P = [];
    for (let k = 0; k < n; k++) { const a = 2 * Math.PI * k / n; P.push([r4(cx + raio * Math.cos(a)), r4(cz + raio * Math.sin(a))]); }
    return P;
  }

  function arredonda(P, i, raio, n = 8) {
    const m = P.length; if (m < 3 || !(raio > 0)) return null;
    const a = P[(i - 1 + m) % m], v = P[i], b = P[(i + 1) % m];
    const u = [a[0] - v[0], a[1] - v[1]], w = [b[0] - v[0], b[1] - v[1]], lu = Math.hypot(...u), lw = Math.hypot(...w);
    if (lu < 1e-9 || lw < 1e-9) return null;
    const un = [u[0] / lu, u[1] / lu], wn = [w[0] / lw, w[1] / lw], cs = un[0] * wn[0] + un[1] * wn[1];
    if (Math.abs(cs) > 0.9999) return null;
    const meio = Math.acos(cs) / 2, t = raio / Math.tan(meio);
    if (t > 0.5 * lu + 1e-12 || t > 0.5 * lw + 1e-12) return null;
    const bis = [un[0] + wn[0], un[1] + wn[1]], lb = Math.hypot(...bis), c = [v[0] + bis[0] / lb * raio / Math.sin(meio), v[1] + bis[1] / lb * raio / Math.sin(meio)];
    const p1 = [v[0] + un[0] * t, v[1] + un[1] * t], p2 = [v[0] + wn[0] * t, v[1] + wn[1] * t];
    const a1 = Math.atan2(p1[1] - c[1], p1[0] - c[0]);
    let da = Math.atan2(p2[1] - c[1], p2[0] - c[0]) - a1;
    while (da > Math.PI) da -= 2 * Math.PI;
    while (da < -Math.PI) da += 2 * Math.PI;
    const arco = [];
    for (let k = 0; k <= n; k++) arco.push([r4(c[0] + raio * Math.cos(a1 + da * k / n)), r4(c[1] + raio * Math.sin(a1 + da * k / n))]);
    P.splice(i, 1, ...arco);
    return arco.length;
  }

  function seCruza(P) {
    const m = P.length, cr = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    for (let i = 0; i < m; i++) for (let j = i + 1; j < m; j++) {
      if (j === i + 1 || (i === 0 && j === m - 1)) continue;
      const a = P[i], b = P[(i + 1) % m], c = P[j], d = P[(j + 1) % m];
      if (cr(a, b, c) * cr(a, b, d) < -1e-18 && cr(c, d, a) * cr(c, d, b) < -1e-18) return true;
    }
    return false;
  }

  function dxf(contorno, furos) {
    const L = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"];
    const poli = (P, camada) => {
      L.push("0", "LWPOLYLINE", "8", camada, "90", String(P.length), "70", "1");
      P.forEach(p => L.push("10", (p[0] * 1000).toFixed(3), "20", (p[1] * 1000).toFixed(3)));
    };
    poli(contorno, "CONTORNO");
    (furos || []).forEach(F => poli(F, "FUROS"));
    L.push("0", "ENDSEC", "0", "EOF");
    return L.join("\n") + "\n";
  }

  function leDxf(txt) {
    const lin = txt.split(/\r?\n/).map(s => s.trim()), pares = [];
    for (let i = 0; i + 1 < lin.length; i += 2) pares.push([parseInt(lin[i], 10), lin[i + 1]]);
    let escala = 0.001;
    const iu = pares.findIndex(p => p[0] === 9 && p[1] === "$INSUNITS");
    if (iu >= 0 && pares[iu + 1]) escala = { 1: 0.0254, 4: 0.001, 5: 0.01, 6: 1 }[+pares[iu + 1][1]] || 0.001;
    const lacos = []; let at = null, x = null, linhas = [];
    const fecha = () => { if (at && at.length >= 3) lacos.push(at); at = null; };
    let tipo = null, l = {};
    const fimEntidade = () => {
      if (tipo === "LINE" && ["10", "20", "11", "21"].every(k => k in l)) linhas.push([[l["10"] * escala, l["20"] * escala], [l["11"] * escala, l["21"] * escala]]);
      if (tipo === "CIRCLE" && "40" in l) lacos.push(circulo((l["10"] || 0) * escala, (l["20"] || 0) * escala, l["40"] * escala));
      l = {};
    };
    pares.forEach(([c, v]) => {
      if (c === 0) { fecha(); fimEntidade(); tipo = v; if (v === "LWPOLYLINE") at = []; return; }
      if (tipo === "LWPOLYLINE" && at) { if (c === 10) x = parseFloat(v); else if (c === 20 && x !== null) { at.push([r4(x * escala), r4(parseFloat(v) * escala)]); x = null; } }
      else if (tipo === "LINE" || tipo === "CIRCLE") l[String(c)] = parseFloat(v);
    });
    fecha(); fimEntidade();
    if (linhas.length >= 3) {
      const perto = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6, resto = linhas.slice();
      while (resto.length) {
        const laco = resto.shift().slice();
        let achou = true;
        while (achou && !perto(laco[0], laco[laco.length - 1])) {
          achou = false;
          for (let k = 0; k < resto.length; k++) {
            const [a, b] = resto[k], fim = laco[laco.length - 1];
            if (perto(a, fim)) { laco.push(b); resto.splice(k, 1); achou = true; break; }
            if (perto(b, fim)) { laco.push(a); resto.splice(k, 1); achou = true; break; }
          }
        }
        if (laco.length >= 4 && perto(laco[0], laco[laco.length - 1])) lacos.push(laco.slice(0, -1).map(p => [r4(p[0]), r4(p[1])]));
      }
    }
    if (!lacos.length) return null;
    lacos.sort((a, b) => Math.abs(area(b)) - Math.abs(area(a)));
    return { contorno: lacos[0], furos: lacos.slice(1) };
  }

  const puro = { corta, area, perimetro, ladoMaisPerto, insere, circulo, arredonda, seCruza, dxf, leDxf };
  if (typeof document === "undefined" || !document.body || !document.body.append) return { puro };

  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const sv = (tag, a, pai) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (pai) pai.append(e); return e; };
  const FERR = [["mover", "Mover", "V", "Arraste um vértice. Duplo clique num lado cria um vértice."], ["ponto", "Ponto", "P", "Clique num lado para criar um vértice."],
    ["furo", "Furo redondo", "F", "Clique no centro e arraste o raio."], ["ret", "Furo retangular", "R", "Arraste de um canto ao outro."], ["arco", "Arredondar", "A", "Clique num vértice para arredondar com o raio indicado."]];
  let dlg = null, svg = null, alvo = null, C = null, F = null, marca = [], ferr = "mover", selL = -1, selV = 0, cam = { cx: 0, cz: 0, s: 1000 }, arr = null, passado = [], futuro = [], raio = 0.01, mostraMarca = true, lado = null;

  const laco = k => (k < 0 ? C : F[k]);
  const foto = () => JSON.stringify({ C, F });
  const guarda = () => { passado.push(foto()); if (passado.length > 200) passado.shift(); futuro.length = 0; };
  const volta = (de, para) => { if (!de.length) return; para.push(foto()); const o = JSON.parse(de.pop()); C = o.C; F = o.F; if (!laco(selL)) selL = -1; selV = Math.min(selV, laco(selL).length - 1); pinta(); };
  const tela = (x, z) => { const r = svg.getBoundingClientRect(); return [r.width / 2 + (x - cam.cx) * cam.s, r.height / 2 - (z - cam.cz) * cam.s]; };
  const mundo = (px, py) => { const r = svg.getBoundingClientRect(); return [cam.cx + (px - r.width / 2) / cam.s, cam.cz - (py - r.height / 2) / cam.s]; };
  const local = ev => { const r = svg.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; };

  function gruda(x, z, livre, ignora) {
    if (livre) return [x, z];
    let p = [Math.round(x * 1000) / 1000, Math.round(z * 1000) / 1000], d0 = 9 / cam.s;
    const tenta = q => { const d = Math.hypot(q[0] - x, q[1] - z); if (d < d0) { d0 = d; p = [q[0], q[1]]; } };
    [C, ...F].forEach((L, k) => L.forEach((q, i) => { if (!(ignora && ignora[0] === k - 1 && ignora[1] === i)) tenta(q); }));
    if (mostraMarca) for (const s of marca) { tenta([s[0], s[1]]); tenta([s[2], s[3]]); }
    return p;
  }

  function enquadra() {
    const P = C.length ? C : [[0, 0], [0.3, 0.2]], xs = P.map(p => p[0]), zs = P.map(p => p[1]), r = svg.getBoundingClientRect();
    const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
    cam.cx = (x0 + x1) / 2; cam.cz = (z0 + z1) / 2;
    cam.s = 0.72 * Math.min((r.width || 800) / Math.max(x1 - x0, 0.02), (r.height || 500) / Math.max(z1 - z0, 0.02));
  }

  function pinta() {
    if (!svg) return;
    svg.innerHTML = "";
    const r = svg.getBoundingClientRect(), W = r.width, H = r.height, pt = p => tela(p[0], p[1]);
    const passo = [0.001, 0.005, 0.01, 0.05, 0.1, 0.5].find(p => p * cam.s >= 22) || 1, [xa, zb] = mundo(0, H), [xb, za] = mundo(W, 0);
    let g = "";
    for (let x = Math.ceil(xa / passo) * passo; x <= xb; x += passo) { const X = tela(x, 0)[0].toFixed(1); g += `M${X} 0V${H}`; }
    for (let z = Math.ceil(zb / passo) * passo; z <= za; z += passo) { const Y = tela(0, z)[1].toFixed(1); g += `M0 ${Y}H${W}`; }
    sv("path", { d: g, class: "c2-grade" }, svg);
    const o = tela(0, 0); sv("path", { d: `M${o[0]} 0V${H}M0 ${o[1]}H${W}`, class: "c2-eixos" }, svg);
    if (mostraMarca && marca.length) {
      let d = "";
      for (const s of marca) { const a = tela(s[0], s[1]), b = tela(s[2], s[3]); d += `M${a[0].toFixed(1)} ${a[1].toFixed(1)}L${b[0].toFixed(1)} ${b[1].toFixed(1)}`; }
      sv("path", { d, class: "c2-marca" }, svg);
    }
    const caminho = L => L.map((p, i) => { const q = pt(p); return (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1); }).join("") + "Z";
    if (C.length >= 3) sv("path", { d: caminho(C) + F.filter(L => L.length >= 3).map(caminho).join(""), class: "c2-chapa", "fill-rule": "evenodd" }, svg);
    [C, ...F].forEach((L, k) => { if (L.length >= 2) sv("path", { d: caminho(L), class: "c2-laco" + (k - 1 === selL ? " at" : "") }, svg); });
    if (arr && arr.previa) sv("path", { d: caminho(arr.previa), class: "c2-previa" }, svg);
    const L = laco(selL);
    L.forEach((p, i) => {
      const q = pt(L[(i + 1) % L.length]), a = pt(p), l = Math.hypot(L[(i + 1) % L.length][0] - p[0], L[(i + 1) % L.length][1] - p[1]);
      if (Math.hypot(q[0] - a[0], q[1] - a[1]) > 46) { const t = sv("text", { x: (a[0] + q[0]) / 2, y: (a[1] + q[1]) / 2 - 4, class: "c2-cota" }, svg); t.textContent = (l * 1000).toFixed(1); }
    });
    [C, ...F].forEach((Lk, k) => Lk.forEach((p, i) => { const q = pt(p), s = k - 1 === selL && i === selV; sv("circle", { cx: q[0], cy: q[1], r: s ? 6 : (k - 1 === selL ? 4 : 2.5), class: "c2-no" + (s ? " at" : "") }, svg); }));
    const esc = sv("text", { x: 10, y: H - 10, class: "c2-cota esq" }, svg); esc.textContent = `grade ${passo * 1000} mm`;
    painel();
  }

  function painel() {
    const P = dlg.querySelector(".c2-painel"); P.innerHTML = "";
    const L = laco(selL), v = L[selV], G = el("div", "prop");
    const linha = (rot, campo, dica) => { const l = el("label", "", rot); if (dica) l.title = dica; G.append(l, campo); };
    const num = (val, casas, aoMudar) => { const i = el("input"); i.type = "number"; i.step = "any"; i.value = (+val).toFixed(casas); i.onchange = () => { const x = parseFloat(i.value); if (isFinite(x)) aoMudar(x); }; return i; };
    P.append(el("h5", "", selL < 0 ? "Contorno" : `Furo ${selL + 1} de ${F.length}`));
    if (v) {
      linha("x (mm)", num(v[0] * 1000, 1, x => { guarda(); v[0] = r4(x / 1000); pinta(); }));
      linha("z (mm)", num(v[1] * 1000, 1, x => { guarda(); v[1] = r4(x / 1000); pinta(); }));
      const pr = L[(selV + 1) % L.length], ln = Math.hypot(pr[0] - v[0], pr[1] - v[1]);
      linha("lado seguinte (mm)", num(ln * 1000, 1, x => { if (!(x > 0) || ln < 1e-9) return; guarda(); const f = x / 1000 / ln; pr[0] = r4(v[0] + (pr[0] - v[0]) * f); pr[1] = r4(v[1] + (pr[1] - v[1]) * f); pinta(); }),
        "Comprimento do lado que sai deste vértice. Digitar um valor move o vértice seguinte na mesma direção.");
    }
    linha("raio (mm)", num(raio * 1000, 1, x => { if (x > 0) raio = x / 1000; }), "Raio usado pela ferramenta Arredondar.");
    P.append(G);
    const a = Math.abs(area(C)) - F.reduce((s, f) => s + Math.abs(area(f)), 0);
    P.append(el("div", "nota", `${L.length} vértices · perímetro ${(perimetro(L) * 1000).toFixed(0)} mm`));
    P.append(el("div", "nota", `Área da chapa ${(a * 1e4).toFixed(1)} cm² · ${F.length} furo${F.length === 1 ? "" : "s"}`));
    if (C.length >= 3 && seCruza(C)) P.append(el("div", "nota erro", "O contorno se cruza: ajuste antes de aplicar."));
    const B = el("div", "insp-botoes");
    const bt = (t, f, dica) => { const b = el("button", "", t); b.onclick = f; if (dica) b.title = dica; B.append(b); };
    bt("Remover vértice", removeV, "Del");
    if (selL >= 0) bt("Remover furo", () => { guarda(); F.splice(selL, 1); selL = -1; selV = 0; pinta(); });
    bt(selL < 0 && F.length ? "Ir para os furos" : "Ir para o contorno", () => { selL = selL < 0 && F.length ? 0 : -1; selV = 0; pinta(); }, "Tab alterna entre contorno e furos");
    P.append(B);
    const M = el("label", "c2-marca-op"), cx = el("input"); cx.type = "checkbox"; cx.checked = mostraMarca; cx.onchange = () => { mostraMarca = cx.checked; pinta(); };
    M.append(cx, " mostrar o corte da aeronave neste plano"); P.append(M);
    P.append(el("div", "nota", marca.length ? `Marca d'água: ${marca.length} trechos das outras peças cortadas em y = ${((alvo.y || 0) * 1000).toFixed(0)} mm. O cursor gruda nelas.` : "Nenhuma outra peça cruza o plano desta chapa."));
    dlg.querySelectorAll(".c2-ferr button").forEach(b => b.classList.toggle("on", b.dataset.ferr === ferr));
    dlg.querySelector(".c2-dica").textContent = (FERR.find(f => f[0] === ferr) || [])[3] + " · roda: zoom · arrastar o fundo: deslocar · Alt: sem grade";
  }

  function removeV() {
    const L = laco(selL);
    if (selL < 0 && L.length <= 3) { msg("A chapa precisa de pelo menos 3 pontos.", true); return; }
    guarda();
    if (selL >= 0 && L.length <= 3) { F.splice(selL, 1); selL = -1; selV = 0; } else { L.splice(selV, 1); selV = Math.min(selV, L.length - 1); }
    pinta();
  }

  function perto(px, py, raioPx = 10) {
    let mel = null, d0 = raioPx;
    [C, ...F].forEach((L, k) => L.forEach((p, i) => { const q = tela(p[0], p[1]), d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = [k - 1, i]; } }));
    return mel;
  }

  function baixo(ev) {
    const [px, py] = local(ev), [x, z] = mundo(px, py), v = perto(px, py);
    if (ev.button !== 0 || ev.shiftKey) { arr = { pan: true, px, py, cx: cam.cx, cz: cam.cz }; return; }
    if (ferr === "arco") {
      if (!v) return;
      guarda(); const n = arredonda(laco(v[0]), v[1], raio);
      if (n === null) { passado.pop(); msg("Raio grande demais para este canto (ou lados alinhados).", true); } else { selL = v[0]; selV = v[1]; }
      pinta(); return;
    }
    if (ferr === "ponto") { guarda(); const g = gruda(x, z, ev.altKey); selV = insere(laco(selL), g[0], g[1]); pinta(); return; }
    if (ferr === "furo" || ferr === "ret") { const g = gruda(x, z, ev.altKey); arr = { forma: ferr, x0: g[0], z0: g[1], previa: null }; return; }
    if (v) { selL = v[0]; selV = v[1]; arr = { no: v, moveu: false }; pinta(); return; }
    arr = { pan: true, px, py, cx: cam.cx, cz: cam.cz };
  }

  function move(ev) {
    if (!arr) return;
    const [px, py] = local(ev), [x, z] = mundo(px, py);
    if (arr.pan) { cam.cx = arr.cx - (px - arr.px) / cam.s; cam.cz = arr.cz + (py - arr.py) / cam.s; pinta(); return; }
    if (arr.no) {
      if (!arr.moveu) { guarda(); arr.moveu = true; }
      const g = gruda(x, z, ev.altKey, arr.no), p = laco(arr.no[0])[arr.no[1]];
      p[0] = r4(g[0]); p[1] = r4(g[1]); pinta(); return;
    }
    if (arr.forma) {
      const g = gruda(x, z, ev.altKey);
      arr.previa = arr.forma === "furo" ? circulo(arr.x0, arr.z0, Math.max(Math.hypot(g[0] - arr.x0, g[1] - arr.z0), 0.0005))
        : [[arr.x0, arr.z0], [g[0], arr.z0], [g[0], g[1]], [arr.x0, g[1]]].map(p => p.map(r4));
      pinta();
    }
  }

  function solta() {
    const a = arr; arr = null;
    if (a && a.forma) {
      let P = a.previa;
      if (!P && a.forma === "furo") P = circulo(a.x0, a.z0, raio / 2);
      if (P && Math.abs(area(P)) > 1e-8) { guarda(); F.push(P); selL = F.length - 1; selV = 0; }
      pinta();
    }
  }

  function roda(ev) {
    ev.preventDefault();
    const [px, py] = local(ev), antes = mundo(px, py);
    cam.s = Math.max(40, Math.min(200000, cam.s * (ev.deltaY < 0 ? 1.15 : 1 / 1.15)));
    const depois = mundo(px, py); cam.cx += antes[0] - depois[0]; cam.cz += antes[1] - depois[1];
    pinta();
  }

  function duplo(ev) {
    if (ferr !== "mover") return;
    const [px, py] = local(ev), [x, z] = mundo(px, py);
    if (perto(px, py)) return;
    const m = ladoMaisPerto(laco(selL), x, z);
    if (m.i >= 0 && m.d * cam.s < 12) { guarda(); selV = insere(laco(selL), x, z); pinta(); }
  }

  function tecla(ev) {
    if (!dlg || !dlg.open) return;
    const t = ev.target, campo = t && (t.tagName === "INPUT" || t.tagName === "SELECT");
    if ((ev.ctrlKey || ev.metaKey) && !campo) {
      if (ev.key === "z") { volta(passado, futuro); ev.preventDefault(); ev.stopPropagation(); }
      else if (ev.key === "y") { volta(futuro, passado); ev.preventDefault(); ev.stopPropagation(); }
      return;
    }
    if (campo || ev.ctrlKey || ev.metaKey) return;
    const k = ev.key, f = FERR.find(x => x[2].toLowerCase() === k.toLowerCase());
    if (f) { ferr = f[0]; pinta(); ev.preventDefault(); return; }
    const L = laco(selL);
    if (k === "Delete" || k === "Backspace") { removeV(); ev.preventDefault(); return; }
    if (k === "Tab") {
      if (ev.shiftKey) { selL = selL < F.length - 1 ? selL + 1 : -1; selV = 0; } else selV = (selV + 1) % L.length;
      pinta(); ev.preventDefault(); return;
    }
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[k];
    if (d && L[selV]) { guarda(); const p = (ev.shiftKey ? 0.01 : 0.001); L[selV][0] = r4(L[selV][0] + d[0] * p); L[selV][1] = r4(L[selV][1] + d[1] * p); pinta(); ev.preventDefault(); }
  }

  function monta() {
    dlg = el("dialog", "chapa2d"); dlg.id = "dlg_chapa";
    const topo = el("div", "dlg-topo"), tit = el("b", "", "Editor de chapa");
    const acoes = el("span", "c2-acoes");
    const bt = (t, f, dica, cls) => { const b = el("button", cls || "", t); b.onclick = f; if (dica) b.title = dica; acoes.append(b); return b; };
    const arq = el("input"); arq.type = "file"; arq.accept = ".dxf"; arq.hidden = true;
    arq.onchange = () => { const f = arq.files[0]; if (!f) return; f.text().then(t => { const r = leDxf(t); if (!r) { msg("Não achei contorno fechado no DXF (LWPOLYLINE, LINE ou CIRCLE).", true); return; } guarda(); C = r.contorno; F = r.furos; selL = -1; selV = 0; enquadra(); pinta(); }); arq.value = ""; };
    bt("Importar DXF", () => arq.click(), "Lê polilinhas fechadas, linhas e círculos; o maior laço vira o contorno");
    bt("Exportar DXF", () => { const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([dxf(C, F)], { type: "application/dxf" })), download: (alvo.nome || "chapa") + ".dxf" }); a.click(); URL.revokeObjectURL(a.href); }, "Contorno e furos em milímetros");
    bt("Enquadrar", () => { enquadra(); pinta(); });
    bt("Desfazer", () => volta(passado, futuro), "Ctrl+Z"); bt("Refazer", () => volta(futuro, passado), "Ctrl+Y");
    bt("Cancelar", () => dlg.close());
    bt("Aplicar", aplica, "Grava o contorno e os furos na chapa", "primario");
    topo.append(tit, acoes, arq);
    const corpo = el("div", "c2-corpo"), F2 = el("div", "c2-ferr"); F2.setAttribute("role", "toolbar"); F2.setAttribute("aria-label", "Ferramentas de desenho");
    FERR.forEach(([k, n, t, d]) => { const b = el("button", "", n); b.dataset.ferr = k; b.title = `${n} (${t})\n${d}`; b.onclick = () => { ferr = k; pinta(); }; F2.append(b); });
    const palco = el("div", "c2-palco");
    svg = sv("svg", { class: "c2-svg", role: "img", "aria-label": "Desenho da chapa no plano x–z" }, palco);
    palco.append(el("div", "c2-dica"));
    corpo.append(F2, palco, el("div", "c2-painel"));
    dlg.append(topo, corpo);
    document.body.append(dlg);
    svg.addEventListener("mousedown", ev => { baixo(ev); ev.preventDefault(); });
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", solta);
    svg.addEventListener("wheel", roda, { passive: false });
    svg.addEventListener("dblclick", duplo);
    svg.addEventListener("contextmenu", ev => ev.preventDefault());
    window.addEventListener("keydown", tecla, true);
    new ResizeObserver(() => { if (dlg.open) pinta(); }).observe(palco);
  }

  function aplica() {
    if (C.length < 3) { msg("A chapa precisa de pelo menos 3 pontos.", true); return; }
    if (seCruza(C)) { msg("O contorno se cruza: ajuste antes de aplicar.", true); return; }
    const e = alvo;
    muda(() => { e.contorno = C.map(p => [r4(p[0]), r4(p[1])]); const furos = F.filter(f => f.length >= 3).map(f => f.map(p => [r4(p[0]), r4(p[1])])); if (furos.length) e.furos = furos; else delete e.furos; });
    dlg.close();
    if (typeof abaConteudo === "function") abaConteudo();
    msg("Chapa atualizada.");
  }

  function abre(e) {
    e = e || elemento();
    if (!e || e.tipo !== "placa") { msg("Selecione uma chapa (elemento do tipo placa) para abrir o editor 2D.", true); return; }
    if (!dlg) monta();
    alvo = e; C = (e.contorno || []).map(p => [p[0], p[1]]); F = (e.furos || []).map(f => f.map(p => [p[0], p[1]]));
    if (C.length > 1 && C[0][0] === C[C.length - 1][0] && C[0][1] === C[C.length - 1][1]) C.pop();
    passado = []; futuro = []; selL = -1; selV = 0; ferr = "mover"; marca = [];
    if (malha && vista.malha) {
      const fora = new Set(); malha.zonas.forEach((z, k) => { if (z.startsWith(e.nome + ".")) fora.add(k); });
      marca = corta(vista.malha.V, vista.malha.T, vista.malha.zona, fora, e.y || 0);
      if (marca.length > 40000) marca = marca.filter((_, i) => i % Math.ceil(marca.length / 40000) === 0);
    }
    dlg.querySelector(".dlg-topo b").textContent = `Editor de chapa: ${e.nome} (plano y = ${((e.y || 0) * 1000).toFixed(0)} mm)`;
    dlg.showModal();
    enquadra(); pinta();
  }

  return { abre, puro, estado: () => ({ C, F, selL, selV, ferr, marca: marca.length }) };
})();

if (typeof module !== "undefined") module.exports = { Chapa2D };
