"use strict";

const Perfil2D = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const r5 = v => +(+v).toFixed(5);

  function naca(cod, n = 60) {
    const s = String(cod).replace(/\D/g, "");
    if (s.length !== 4) return null;
    const m = +s[0] / 100, p = +s[1] / 10, t = +s.slice(2) / 100, X = [], U = [], L = [];
    for (let k = 0; k < n; k++) {
      const x = 0.5 * (1 - Math.cos(Math.PI * k / (n - 1)));
      const yt = 5 * t * (0.2969 * Math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4);
      const yc = m === 0 || p === 0 ? 0 : x < p ? m / (p * p) * (2 * p * x - x * x) : m / ((1 - p) ** 2) * (1 - 2 * p + 2 * p * x - x * x);
      const dy = m === 0 || p === 0 ? 0 : x < p ? 2 * m / (p * p) * (p - x) : 2 * m / ((1 - p) ** 2) * (p - x), th = Math.atan(dy);
      U.push([r5(x - yt * Math.sin(th)), r5(yc + yt * Math.cos(th))]);
      L.push([r5(x + yt * Math.sin(th)), r5(yc - yt * Math.cos(th))]);
      X.push(x);
    }
    return U.reverse().concat(L.slice(1));
  }

  function lados(P) {
    let i = 0;
    P.forEach((p, k) => { if (p[0] < P[i][0]) i = k; });
    return { sup: P.slice(0, i + 1).reverse(), inf: P.slice(i), bf: i };
  }

  function zEm(S, x) {
    if (!S.length) return 0;
    if (x <= S[0][0]) return S[0][1];
    for (let k = 1; k < S.length; k++) {
      if (x <= S[k][0]) { const a = S[k - 1], b = S[k], f = b[0] > a[0] ? (x - a[0]) / (b[0] - a[0]) : 0; return a[1] + f * (b[1] - a[1]); }
    }
    return S[S.length - 1][1];
  }

  function medidas(P) {
    if (!P || P.length < 6) return null;
    const { sup, inf } = lados(P);
    const xs = sup.concat(inf).map(p => p[0]), a = Math.min(...xs), c = Math.max(...xs) - a;
    if (!(c > 1e-9)) return null;
    const norm = S => S.map(p => [(p[0] - a) / c, p[1] / c]);
    const U = norm(sup), I = norm(inf);
    let t = 0, xt = 0, f = 0, xf = 0;
    for (let k = 0; k <= 200; k++) {
      const x = k / 200, zu = zEm(U, x), zi = zEm(I, x), e = zu - zi, m = (zu + zi) / 2;
      if (e > t) { t = e; xt = x; }
      if (Math.abs(m) > Math.abs(f)) { f = m; xf = x; }
    }
    return { corda: c, espessura: t, x_espessura: xt, curvatura: f, x_curvatura: xf };
  }

  function leDat(txt) {
    const L = String(txt).split(/\r?\n/).map(l => l.replace(/,/g, " ").trim().split(/\s+/).slice(0, 2).map(Number)).filter(v => v.length === 2 && isFinite(v[0]) && isFinite(v[1]));
    if (L.length < 10) return null;
    let P;
    if (L[0][0] > 1.5 && L[0][1] > 1.5) {
      const n = Math.round(L[0][0]), R = L.slice(1);
      if (R.length < 2 * n) return null;
      P = R.slice(0, n).reverse().concat(R.slice(n, 2 * n).slice(1));
      if (zEm(lados(P).sup, 0.3) < zEm(lados(P).inf, 0.3)) P = R.slice(n, 2 * n).reverse().concat(R.slice(0, n).slice(1));
    } else {
      P = L.slice();
      const { sup, inf } = lados(P);
      if (zEm(sup, (sup[0][0] + sup[sup.length - 1][0]) / 2 + 0.3) < zEm(inf, 0.3)) P.reverse();
    }
    return P.map(p => [r5(p[0]), r5(p[1])]);
  }

  const dat = (nome, P) => `${nome}\n${P.map(p => `${p[0].toFixed(6)} ${p[1].toFixed(6)}`).join("\n")}\n`;

  function insere(P, x, z) {
    let mel = { i: 0, d: Infinity, p: [x, z] };
    P.forEach((a, i) => {
      const b = P[(i + 1) % P.length], ux = b[0] - a[0], uz = b[1] - a[1], l2 = ux * ux + uz * uz;
      const t = l2 > 0 ? Math.max(0, Math.min(1, ((x - a[0]) * ux + (z - a[1]) * uz) / l2)) : 0;
      const p = [a[0] + t * ux, a[1] + t * uz], d = Math.hypot(x - p[0], z - p[1]);
      if (d < mel.d) mel = { i, d, p };
    });
    if (mel.i === P.length - 1) { P.push([r5(mel.p[0]), r5(mel.p[1])]); return P.length - 1; }
    P.splice(mel.i + 1, 0, [r5(mel.p[0]), r5(mel.p[1])]);
    return mel.i + 1;
  }

  function simetriza(P) {
    const { sup } = lados(P);
    return sup.slice().reverse().concat(sup.slice(1).map(p => [p[0], -p[1]]));
  }

  const puro = { naca, lados, medidas, leDat, dat, insere, simetriza, zEm };
  if (typeof document === "undefined" || !document.body || !document.body.append) return { puro };

  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const sv = (tag, a, pai) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (pai) pai.append(e); return e; };
  const FERR = [["mover", "Mover", "V", "Arraste um ponto. Duplo clique num trecho cria um ponto."], ["ponto", "Ponto", "P", "Clique num trecho para criar um ponto."]];
  let dlg = null, svg = null, alvo = null, P = [], ref = [], sel = 0, ferr = "mover", cam = { cx: 0.5, cz: 0, s: 600 }, arr = null, passado = [], futuro = [], nacaCod = null, travaX = false, nome = "perfil", gerador = { m: 4, p: 4, t: 12 };

  const foto = () => JSON.stringify({ P, nacaCod });
  const guarda = () => { passado.push(foto()); if (passado.length > 200) passado.shift(); futuro.length = 0; };
  const volta = (de, para) => { if (!de.length) return; para.push(foto()); const o = JSON.parse(de.pop()); P = o.P; nacaCod = o.nacaCod; sel = Math.min(sel, P.length - 1); pinta(); };
  const tela = (x, z) => { const r = svg.getBoundingClientRect(); return [r.width / 2 + (x - cam.cx) * cam.s, r.height / 2 - (z - cam.cz) * cam.s]; };
  const mundo = (px, py) => { const r = svg.getBoundingClientRect(); return [cam.cx + (px - r.width / 2) / cam.s, cam.cz - (py - r.height / 2) / cam.s]; };
  const local = ev => { const r = svg.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; };

  function enquadra() {
    const r = svg.getBoundingClientRect(), xs = P.map(p => p[0]), zs = P.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
    cam.cx = (x0 + x1) / 2; cam.cz = (z0 + z1) / 2;
    cam.s = 0.86 * Math.min((r.width || 800) / Math.max(x1 - x0, 0.05), (r.height || 400) / Math.max(z1 - z0, 0.05));
  }

  function pinta() {
    if (!svg) return;
    svg.innerHTML = "";
    const r = svg.getBoundingClientRect(), W = r.width, H = r.height, pt = p => tela(p[0], p[1]);
    const passo = [0.01, 0.05, 0.1, 0.5].find(p => p * cam.s >= 30) || 1, [xa, zb] = mundo(0, H), [xb, za] = mundo(W, 0);
    let g = "";
    for (let x = Math.ceil(xa / passo) * passo; x <= xb; x += passo) g += `M${tela(x, 0)[0].toFixed(1)} 0V${H}`;
    for (let z = Math.ceil(zb / passo) * passo; z <= za; z += passo) g += `M0 ${tela(0, z)[1].toFixed(1)}H${W}`;
    sv("path", { d: g, class: "c2-grade" }, svg);
    const o = tela(0, 0); sv("path", { d: `M${o[0]} 0V${H}M0 ${o[1]}H${W}`, class: "c2-eixos" }, svg);
    const cam_ = L => L.map((p, i) => { const q = pt(p); return (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1); }).join("");
    if (ref.length > 2) sv("path", { d: cam_(ref) + "Z", class: "c2-previa" }, svg);
    if (P.length > 2) sv("path", { d: cam_(P) + "Z", class: "c2-chapa" }, svg);
    if (P.length > 1) sv("path", { d: cam_(P), class: "c2-laco at" }, svg);
    const m = medidas(P);
    if (m) {
      const a = tela(0, 0), b = tela(1, 0);
      sv("path", { d: `M${a[0]} ${a[1]}H${b[0]}`, class: "c2-marca" }, svg);
    }
    P.forEach((p, i) => { const q = pt(p), s = i === sel; sv("circle", { cx: q[0], cy: q[1], r: s ? 6 : 2.8, class: "c2-no" + (s ? " at" : "") }, svg); });
    const esc = sv("text", { x: 10, y: H - 10, class: "c2-cota esq" }, svg); esc.textContent = `grade ${(passo * 100).toFixed(0)} % da corda`;
    painel();
  }

  function painel() {
    const B = dlg.querySelector(".c2-painel"); B.innerHTML = "";
    const G = el("div", "prop"), v = P[sel];
    const linha = (rot, campo, dica) => { const l = el("label", "", rot); if (dica) l.title = dica; G.append(l, campo); };
    const num = (val, casas, aoMudar, passo) => { const i = el("input"); i.type = "number"; i.step = passo || "any"; i.value = (+val).toFixed(casas); i.onchange = () => { const x = parseFloat(i.value); if (isFinite(x)) aoMudar(x); }; return i; };
    B.append(el("h5", "", `Ponto ${sel + 1} de ${P.length}`));
    if (v) {
      linha("x (% corda)", num(v[0] * 100, 2, x => { guarda(); v[0] = r5(x / 100); nacaCod = null; pinta(); }));
      linha("z (% corda)", num(v[1] * 100, 2, x => { guarda(); v[1] = r5(x / 100); nacaCod = null; pinta(); }));
    }
    B.append(G);
    const md = medidas(P);
    if (md) {
      B.append(el("div", "nota", `Espessura máxima ${(md.espessura * 100).toFixed(2)} % em x = ${(md.x_espessura * 100).toFixed(1)} %`));
      B.append(el("div", "nota", `Curvatura máxima ${(md.curvatura * 100).toFixed(2)} % em x = ${(md.x_curvatura * 100).toFixed(1)} %`));
    }
    B.append(el("div", "nota", `${P.length} pontos${nacaCod ? " · NACA " + nacaCod : " · perfil livre"}`));
    if (P.length >= 4 && Chapa2D.puro.seCruza(P)) B.append(el("div", "nota erro", "O contorno se cruza: ajuste antes de aplicar."));
    B.append(el("h5", "", "Gerar NACA de 4 dígitos"));
    const G2 = el("div", "prop"), l2 = (rot, c, d) => { const l = el("label", "", rot); if (d) l.title = d; G2.append(l, c); };
    l2("curvatura (%)", num(gerador.m, 0, x => { gerador.m = Math.max(0, Math.min(9, Math.round(x))); }, "1"), "1.º dígito");
    l2("posição (décimos)", num(gerador.p, 0, x => { gerador.p = Math.max(0, Math.min(9, Math.round(x))); }, "1"), "2.º dígito");
    l2("espessura (%)", num(gerador.t, 0, x => { gerador.t = Math.max(1, Math.min(40, Math.round(x))); }, "1"), "3.º e 4.º dígitos");
    B.append(G2);
    const bt = el("div", "insp-botoes"), b = (t, f, d) => { const e = el("button", "", t); e.onclick = f; if (d) e.title = d; bt.append(e); };
    b("Gerar", () => { guarda(); const c = `${gerador.m}${gerador.p}${String(gerador.t).padStart(2, "0")}`; P = naca(c); nacaCod = c; sel = 0; pinta(); }, "Substitui o desenho pelo NACA indicado");
    b("Simetrizar", () => { guarda(); P = simetriza(P); nacaCod = null; sel = 0; pinta(); }, "Espelha a superfície superior na inferior");
    b("Remover ponto", removeV, "Del");
    B.append(bt);
    const T = el("label", "c2-marca-op"), cx = el("input"); cx.type = "checkbox"; cx.checked = travaX; cx.onchange = () => { travaX = cx.checked; };
    T.append(cx, " arrastar só na vertical (x travado)"); B.append(T);
    const N = el("div", "prop"), ni = el("input"); ni.type = "text"; ni.value = nome; ni.onchange = () => { nome = ni.value.replace(/[^\w-]/g, "_") || "perfil"; ni.value = nome; };
    const ln = el("label", "", "arquivo"); ln.title = "Nome do .dat gravado ao aplicar (só se o perfil deixar de ser NACA)"; N.append(ln, ni); B.append(N);
    dlg.querySelectorAll(".c2-ferr button").forEach(x => x.classList.toggle("on", x.dataset.ferr === ferr));
    dlg.querySelector(".c2-dica").textContent = (FERR.find(f => f[0] === ferr) || [])[3] + " · roda: zoom · arrastar o fundo: deslocar · Alt: sem grade";
  }

  function removeV() {
    if (P.length <= 12) { msg("O perfil precisa de pelo menos 12 pontos.", true); return; }
    guarda(); P.splice(sel, 1); sel = Math.min(sel, P.length - 1); nacaCod = null; pinta();
  }

  function perto(px, py, raioPx = 10) {
    let mel = -1, d0 = raioPx;
    P.forEach((p, i) => { const q = tela(p[0], p[1]), d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = i; } });
    return mel;
  }

  function baixo(ev) {
    const [px, py] = local(ev), [x, z] = mundo(px, py), i = perto(px, py);
    if (ev.button !== 0 || ev.shiftKey) { arr = { pan: true, px, py, cx: cam.cx, cz: cam.cz }; return; }
    if (ferr === "ponto") { guarda(); sel = insere(P, x, z); nacaCod = null; pinta(); return; }
    if (i >= 0) { sel = i; arr = { no: i, moveu: false }; pinta(); return; }
    arr = { pan: true, px, py, cx: cam.cx, cz: cam.cz };
  }

  function move(ev) {
    if (!arr) return;
    const [px, py] = local(ev), [x, z] = mundo(px, py);
    if (arr.pan) { cam.cx = arr.cx - (px - arr.px) / cam.s; cam.cz = arr.cz + (py - arr.py) / cam.s; pinta(); return; }
    if (arr.no !== undefined) {
      if (!arr.moveu) { guarda(); arr.moveu = true; nacaCod = null; }
      const p = P[arr.no];
      if (!travaX) p[0] = r5(ev.altKey ? x : Math.round(x * 1000) / 1000);
      p[1] = r5(ev.altKey ? z : Math.round(z * 1000) / 1000); pinta();
    }
  }

  const solta = () => { arr = null; };

  function roda(ev) {
    ev.preventDefault();
    const [px, py] = local(ev), antes = mundo(px, py);
    cam.s = Math.max(60, Math.min(60000, cam.s * (ev.deltaY < 0 ? 1.15 : 1 / 1.15)));
    const depois = mundo(px, py); cam.cx += antes[0] - depois[0]; cam.cz += antes[1] - depois[1];
    pinta();
  }

  function duplo(ev) {
    if (ferr !== "mover") return;
    const [px, py] = local(ev), [x, z] = mundo(px, py);
    if (perto(px, py) >= 0) return;
    guarda(); sel = insere(P, x, z); nacaCod = null; pinta();
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
    if (k === "Delete" || k === "Backspace") { removeV(); ev.preventDefault(); return; }
    if (k === "Tab") { sel = (sel + (ev.shiftKey ? P.length - 1 : 1)) % P.length; pinta(); ev.preventDefault(); return; }
    const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[k];
    if (d && P[sel]) { guarda(); const q = ev.shiftKey ? 0.01 : 0.001; if (!travaX) P[sel][0] = r5(P[sel][0] + d[0] * q); P[sel][1] = r5(P[sel][1] + d[1] * q); nacaCod = null; pinta(); ev.preventDefault(); }
  }

  function monta() {
    dlg = el("dialog", "chapa2d"); dlg.id = "dlg_perfil";
    const topo = el("div", "dlg-topo"), tit = el("b", "", "Editor de perfil");
    const acoes = el("span", "c2-acoes");
    const bt = (t, f, dica, cls) => { const b = el("button", cls || "", t); b.onclick = f; if (dica) b.title = dica; acoes.append(b); return b; };
    const arq = el("input"); arq.type = "file"; arq.accept = ".dat,.txt"; arq.hidden = true;
    arq.onchange = () => { const f = arq.files[0]; if (!f) return; f.text().then(t => { const r = leDat(t); if (!r) { msg("Não consegui ler este .dat (formato Selig ou Lednicer, com pelo menos 10 pontos).", true); return; } guarda(); P = r; nacaCod = null; sel = 0; nome = f.name.replace(/\.[^.]+$/, "").replace(/[^\w-]/g, "_") || "perfil"; enquadra(); pinta(); }); arq.value = ""; };
    bt("Importar .dat", () => arq.click(), "Selig ou Lednicer (UIUC)");
    bt("Exportar .dat", () => { const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([dat(nome, P)], { type: "text/plain" })), download: nome + ".dat" }); a.click(); URL.revokeObjectURL(a.href); }, "Formato Selig, do bordo de fuga superior ao inferior");
    bt("Enquadrar", () => { enquadra(); pinta(); });
    bt("Desfazer", () => volta(passado, futuro), "Ctrl+Z"); bt("Refazer", () => volta(futuro, passado), "Ctrl+Y");
    bt("Cancelar", () => dlg.close());
    bt("Aplicar", aplica, "Usa este perfil na asa (grava um .dat quando deixa de ser NACA)", "primario");
    topo.append(tit, acoes, arq);
    const corpo = el("div", "c2-corpo"), F2 = el("div", "c2-ferr"); F2.setAttribute("role", "toolbar"); F2.setAttribute("aria-label", "Ferramentas de desenho");
    FERR.forEach(([k, n, t, d]) => { const b = el("button", "", n); b.dataset.ferr = k; b.title = `${n} (${t})\n${d}`; b.onclick = () => { ferr = k; pinta(); }; F2.append(b); });
    const palco = el("div", "c2-palco");
    svg = sv("svg", { class: "c2-svg", role: "img", "aria-label": "Desenho do perfil no plano x–z" }, palco);
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

  async function aplica() {
    if (P.length < 12) { msg("O perfil precisa de pelo menos 12 pontos.", true); return; }
    if (Chapa2D.puro.seCruza(P)) { msg("O contorno se cruza: ajuste antes de aplicar.", true); return; }
    let spec;
    if (nacaCod) spec = "NACA " + nacaCod;
    else {
      try { spec = (await chama("/api/perfil/grava", { nome, pontos: P, pasta: esq._pasta })).perfil; }
      catch (x) { msg(x.message, true); return; }
    }
    const a = alvo;
    muda(() => { a.alvo.perfil = spec; });
    dlg.close();
    if (typeof abaConteudo === "function") abaConteudo();
    if (typeof props === "function") props();
    msg(`Perfil aplicado: ${spec}.`);
  }

  async function abre(e, secao) {
    e = e || elemento();
    if (!e || (e.tipo || "asa") !== "asa") { msg("Selecione uma asa para abrir o editor de perfil.", true); return; }
    const objeto = secao != null && e.secoes && e.secoes[secao] ? e.secoes[secao] : e;
    const spec = objeto.perfil || e.perfil || "NACA 0012";
    let pontos;
    try { pontos = (await chama("/api/perfil/le", { perfil: spec, pasta: esq._pasta, n: 81 })).pontos; }
    catch (x) { msg(x.message, true); return; }
    if (!dlg) monta();
    alvo = { e, alvo: objeto, secao };
    P = pontos.map(p => [r5(p[0]), r5(p[1])]); ref = P.map(p => p.slice());
    const m = /^\s*naca\s*(\d{4})\s*$/i.exec(spec); nacaCod = m ? m[1] : null;
    if (nacaCod) { gerador = { m: +nacaCod[0], p: +nacaCod[1], t: +nacaCod.slice(2) }; }
    nome = (e.nome + (secao != null ? "_s" + (secao + 1) : "")).replace(/[^\w-]/g, "_") + "_perfil";
    passado = []; futuro = []; sel = 0; ferr = "mover";
    dlg.querySelector(".dlg-topo b").textContent = `Editor de perfil: ${e.nome}${secao != null ? ", seção " + (secao + 1) : ""} (${spec})`;
    dlg.showModal();
    enquadra(); pinta();
  }

  return { abre, puro, estado: () => ({ P, sel, nacaCod, ferr }) };
})();

if (typeof module !== "undefined") module.exports = { Perfil2D };
