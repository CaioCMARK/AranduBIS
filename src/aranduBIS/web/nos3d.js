"use strict";

const No3D = (() => {
  const PASSO = 0.001, IMA = 9;
  const PLANOS = [["xy", "planta (x, y)", [0, 1]], ["xz", "perfil (x, z)", [0, 2]], ["yz", "frontal (y, z)", [1, 2]]];
  let ativo = false, sel = null, arr = null, plano = 0, eixo = null, sim = true, tubo = null, autoLiga = true;
  let meu = false, previa = null, area = null, grupoDe = null, margens = null;
  const chave = p => [0, 1, 2].map(k => Math.round(p[k] * 1000)).join(",");
  const grupo = new Set();

  const TIPOS = ["trelica", "roda", "ponto"];
  const iguais = (a, b) => Math.abs(a - b) < 1e-5;
  const rotado = e => ["rolagem", "arfagem", "guinada"].some(c => Math.abs(e[c] || 0) > 1e-9);
  const suportado = e => e && TIPOS.includes(e.tipo) && !rotado(e);
  const off = e => (e.tipo === "trelica" ? (e.posicao || [0, 0, 0]) : [0, 0, 0]);

  const posDe = (e, a) => {
    if (!arr || !arr.arrasta) return a.p;
    if (arr.id === a.id) return arr.p;
    if (arr.gr && arr.gr.has(a.id)) { const q = arr.gr.get(a.id); return [q[0] + arr.p[0] - arr.p0[0], q[1] + arr.p[1] - arr.p0[1], q[2] + arr.p[2] - arr.p0[2]]; }
    if (arr.esp && arr.esp.id === a.id && arr.esp.e === e) return arr.pe;
    return a.p;
  };
  function alcas(e) {
    if (e.tipo === "trelica") { const o = off(e); return (e.nos || []).map((p, i) => ({ id: i, p: [p[0] + o[0], p[1] + o[1], p[2] + o[2]] })); }
    const q = e.posicao || [0, 0, 0];
    if (e.tipo === "roda") return [{ id: 0, p: [q[0], e.y || 0, q[2]] }];
    return [{ id: 0, p: [q[0], q[1], q[2]] }];
  }
  function escreve(e, id, p) {
    const r = v => +v.toFixed(5);
    if (e.tipo === "trelica") { const o = off(e); e.nos[id] = [r(p[0] - o[0]), r(p[1] - o[1]), r(p[2] - o[2])]; return; }
    const q = (e.posicao || [0, 0, 0]).slice();
    if (e.tipo === "roda") { q[0] = r(p[0]); q[2] = r(p[2]); e.y = r(p[1]); e.posicao = q; return; }
    e.posicao = [r(p[0]), r(p[1]), r(p[2])];
  }
  function espelho(e, id, p) {
    if (!sim || Math.abs(p[1]) < 1e-6) return null;
    const alvo = [p[0], -p[1], p[2]], acha = (o) => alcas(o).find(a => !(o === e && a.id === id) && a.p.every((v, k) => iguais(v, alvo[k])));
    if (e.tipo === "trelica") { const a = acha(e); return a ? { e, id: a.id } : null; }
    for (const o of esq.elementos) if (o !== e && o.tipo === e.tipo) { const a = acha(o); if (a) return { e: o, id: a.id }; }
    return null;
  }
  const proj = p => vista.projetaXY(p[0], p[1], p[2]);

  function atualiza() { pinta(); if (typeof Estado !== "undefined") Estado.avisa("ferramenta"); }
  function pinta() {
    const e = elemento();
    if (ativo && !suportado(e)) { ativo = false; vista.ferramenta = (typeof Nervura3D !== "undefined" && Nervura3D.ativo()) ? vista.ferramenta : null; }
    if (!ativo) { if (meu) { meu = false; vista.pontos = null; vista.extra = null; vista.hud = null; } vista.desenha(); return; }
    meu = true;
    const A = alcas(e);
    if (grupoDe !== e.nome) { grupo.clear(); grupoDe = e.nome; }
    grupo.forEach(i => { if (!A.some(a => a.id === i)) grupo.delete(i); });
    const pts = A.map(a => ({ p: posDe(e, a), margem: margens && e.tipo === "trelica" ? margens[chave(a.p)] : undefined, sel: sel === a.id || grupo.has(a.id), forma: e.tipo === "trelica" ? Juntas.de(e, a.id).split(":")[0] : "solda", vinculo: e.tipo === "trelica" ? Juntas.vinculoDe(e, a.id) : "", ligacao: e.tipo === "trelica" && !!Juntas.ligacaoDe(e, a.id) }));
    vista.pontos = pts;
    const ex = [];
    if (e.tipo === "trelica") {
      const P = {}; A.forEach((q, i) => { P[q.id] = pts[i].p; });
      (e.barras || []).forEach(b => { if ((b[0] === sel || b[1] === sel || (grupo.has(b[0]) && grupo.has(b[1]))) && P[b[0]] && P[b[1]]) ex.push({ pts: [P[b[0]], P[b[1]]], cor: "#ffd447", larg: 2.6 }); });
    }
    if (previa) ex.push({ pts: [previa.a, previa.b], cor: "rgba(255,212,71,.75)", larg: 1.6 });
    vista.extra = ex.length ? ex : null;
    const a = A.find(q => q.id === sel), h = [];
    if (a) {
      const p = arr && arr.arrasta ? arr.p : a.p, lig = e.tipo === "trelica" ? e.barras.filter(b => b[0] === sel || b[1] === sel).length : 0;
      h.push(`${e.tipo === "trelica" ? "Nó " + sel : e.nome} · x ${(p[0] * 1000).toFixed(0)}  y ${(p[1] * 1000).toFixed(0)}  z ${(p[2] * 1000).toFixed(0)} mm`);
      h.push(e.tipo === "trelica" ? `liga ${lig} barra${lig === 1 ? "" : "s"} · ${A.length} nós` : "arraste a bolinha para reposicionar");
      if (margens && e.tipo === "trelica" && chave(a.p) in margens) h.push(`margem da junta na última análise da cauda: ${(100 * margens[chave(a.p)]).toFixed(0)} %`);
      if (grupo.size > 1) h.push(`grupo de ${grupo.size} nós: arraste um deles para mover todos`);
      if (e.tipo === "trelica") h.push(`junta: ${Juntas.rotulo(Juntas.de(e, sel))} · vínculo: ${Juntas.vinculoDe(e, sel) || "livre"}${Juntas.ligacaoDe(e, sel) ? " · liga a " + Juntas.ligacaoDe(e, sel) : ""}`);
    } else h.push(`Editando ${e.nome}`);
    h.push(eixo ? `Movimento: só no eixo ${eixo.toUpperCase()}` : `Movimento no plano ${PLANOS[plano][1]}`);
    h.push("Arraste uma bolinha (Alt = sem passo e sem ímã)");
    h.push("X/Y/Z trava o eixo · P troca o plano · M simetria " + (sim ? "ligada" : "desligada"));
    h.push("←/→ move x · ↑/↓ move z · , . move y (Shift ×10)");
    if (e.tipo === "trelica") {
      h.push(`Ctrl+clique: cria nó${autoLiga ? " ligado ao selecionado" : ""} · em outro nó, liga/desliga barra`);
      h.push("Shift+clique: junta ao grupo · Ctrl+C / Ctrl+V copia e cola · I espelha");
      h.push("1 solda · 2 parafuso (repita: troca o eixo) · 3 rótula");
      h.push("4 engaste · 5 apoio · 0 livre · 6 liga/solta a asa mais próxima");
      h.push(`Del remove nó · T tubo: ${tuboAtual(e) || "(crie um tipo)"} · L ligar auto: ${autoLiga ? "sim" : "não"}`);
    }
    h.push("Tab troca · Esc sai");
    vista.hud = h; vista.desenha();
  }

  const tuboAtual = e => { const t = Object.keys(e.tubos || {}); if (!t.length) return null; if (!tubo || !t.includes(tubo)) tubo = t[0]; return tubo; };
  const temBarra = (e, a, b) => e.barras.findIndex(q => (q[0] === a && q[1] === b) || (q[0] === b && q[1] === a));
  function juntaBarra(e, a, b) {
    if (a === b || a == null || b == null) return false;
    const i = temBarra(e, a, b);
    if (i >= 0) e.barras.splice(i, 1); else e.barras.push([a, b, tuboAtual(e)]);
    return true;
  }
  function criaNo(e, px, py, ev) {
    if (autoLiga && !tuboAtual(e)) { msg("Crie um tipo de tubo na aba Seções antes de ligar barras.", true); return; }
    const A = alcas(e), ref = A.find(a => a.id === sel) || A[0], base = ref ? ref.p : [0, 0, 0], q0 = proj(base);
    const d = q0 ? resolve({ p: base }, px - q0[0], py - q0[1]) : [0, 0, 0];
    const p = candidato(e, base, d, px, py, ev.altKey), de = ref && autoLiga ? ref.id : null;
    const esDe = ref ? espelho(e, ref.id, ref.p) : null, mDe = esDe ? esDe.id : (ref && Math.abs(ref.p[1]) < 1e-6 ? ref.id : null);
    let novoId = null;
    muda(() => {
      e.nos = e.nos || []; e.barras = e.barras || [];
      const n = e.nos.length; novoId = n; e.nos.push([0, 0, 0]); escreve(e, n, p);
      let m = null;
      if (sim && Math.abs(p[1]) > 1e-6) {
        const pm = [p[0], -p[1], p[2]], ex = alcas(e).find(q => q.id !== n && q.p.every((v, k) => iguais(v, pm[k])));
        if (ex) m = ex.id; else { m = e.nos.length; e.nos.push([0, 0, 0]); escreve(e, m, pm); }
      }
      if (de !== null) { juntaBarra(e, de, n); if (m !== null && mDe !== null) juntaBarra(e, mDe, m); }
    });
    sel = novoId; atualiza();
  }
  function ligaBarra(e, a, b) {
    if (!tuboAtual(e)) { msg("Crie um tipo de tubo na aba Seções antes de ligar barras.", true); return; }
    const pa = alcas(e).find(q => q.id === a), pb = alcas(e).find(q => q.id === b);
    const par = (q, id) => { const m = espelho(e, id, q.p); return m ? m.id : (Math.abs(q.p[1]) < 1e-6 ? id : null); };
    const ma = pa && par(pa, a), mb = pb && par(pb, b);
    muda(() => { juntaBarra(e, a, b); if (sim && ma !== null && mb !== null && !(ma === a && mb === b) && !(ma === b && mb === a)) juntaBarra(e, ma, mb); });
    atualiza();
  }
  function removeNos(e, ids) {
    const fora = new Set(ids), mapa = {}; let k = 0;
    e.nos.forEach((_, i) => { if (!fora.has(i)) mapa[i] = k++; });
    e.barras = e.barras.filter(b => !fora.has(b[0]) && !fora.has(b[1])).map(b => [mapa[b[0]], mapa[b[1]], ...b.slice(2)]);
    e.nos = e.nos.filter((_, i) => !fora.has(i));
    Juntas.remapeia(e, mapa);
    return mapa;
  }

  function liga(v) {
    if (v && !suportado(elemento())) { msg("Selecione uma treliça, roda ou massa pontual sem rotação para editar na vista 3D.", true); v = false; }
    ativo = !!v;
    if (ativo && typeof Nervura3D !== "undefined" && Nervura3D.ativo()) Nervura3D.liga(false);
    vista.ferramenta = ativo ? ferramenta : null;
    if (ativo) vista.aoMover = aoMover; else if (vista.aoMover === aoMover) vista.aoMover = null;
    previa = null;
    if (ativo) { const A = alcas(elemento()); if (!A.some(a => a.id === sel)) sel = A.length ? A[0].id : null; }
    atualiza();
  }

  const vet = (a, b, esc) => [(b[0] - a[0]) / esc, (b[1] - a[1]) / esc, (b[2] - a[2]) / esc];
  function resolve(a, dx, dy) {
    const base = a.p, q0 = proj(base), esc = 0.1, S = [0, 1, 2].map(k => { const t = base.slice(); t[k] += esc; const q = proj(t); return [(q[0] - q0[0]) / esc, (q[1] - q0[1]) / esc]; });
    const d = [0, 0, 0];
    if (eixo) {
      const k = "xyz".indexOf(eixo), s = S[k], n2 = s[0] * s[0] + s[1] * s[1];
      if (n2 > 1e-6) d[k] = (dx * s[0] + dy * s[1]) / n2;
    } else {
      const [i, j] = PLANOS[plano][2], det = S[i][0] * S[j][1] - S[i][1] * S[j][0];
      if (Math.abs(det) > 1e-3 * Math.hypot(...S[i]) * Math.hypot(...S[j]) && Math.abs(det) > 1e-9) {
        d[i] = (dx * S[j][1] - dy * S[j][0]) / det; d[j] = (S[i][0] * dy - S[i][1] * dx) / det;
      }
    }
    return d;
  }

  function livres() { return eixo ? ["xyz".indexOf(eixo)] : PLANOS[plano][2]; }

  function candidato(e, p0, d, px, py, livre) {
    let p = [p0[0] + d[0], p0[1] + d[1], p0[2] + d[2]];
    if (!livre) {
      p = p.map((v, k) => (d[k] !== 0 ? Math.round(v / PASSO) * PASSO : v));
      const lv = livres();
      let mel = null, d0 = IMA;
      esq.elementos.forEach(o => { if (!suportado(o)) return; alcas(o).forEach(a => {
        if (arr && o === e && a.id === arr.id) return;
        const q = proj(a.p); if (!q) return; const dd = Math.hypot(q[0] - px, q[1] - py); if (dd < d0) { d0 = dd; mel = a; }
      }); });
      if (mel) lv.forEach(k => { p[k] = mel.p[k]; });
    }
    return p;
  }

  const ferramenta = {
    baixo(px, py, ev) {
      const e = elemento(); if (!ativo || !suportado(e)) return false;
      let mel = null, d0 = 11;
      if (ev && (ev.ctrlKey || ev.metaKey)) {
        if (e.tipo !== "trelica") return true;
        alcas(e).forEach(a => { const q = proj(a.p); if (q) { const d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = a; } } });
        if (mel && sel !== null && mel.id !== sel) ligaBarra(e, sel, mel.id);
        else if (mel) { sel = mel.id; atualiza(); }
        else criaNo(e, px, py, ev);
        return true;
      }
      alcas(e).forEach(a => { const q = proj(a.p); if (q) { const d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = a; } } });
      if (!mel) return false;
      if (ev && ev.shiftKey && e.tipo === "trelica") {
        if (grupo.has(mel.id)) grupo.delete(mel.id); else { if (sel !== null) grupo.add(sel); grupo.add(mel.id); }
        sel = mel.id; atualiza(); return true;
      }
      if (!grupo.has(mel.id)) grupo.clear();
      const A0 = alcas(e), gr = grupo.size > 1 ? new Map([...grupo].filter(i => i !== mel.id).map(i => [i, A0.find(q => q.id === i).p])) : null;
      sel = mel.id; arr = { id: mel.id, p0: mel.p, p: mel.p, px, py, arrasta: false, esp: null, pe: null, gr };
      atualiza(); return true;
    },
    move(px, py, ev) {
      if (!arr) return; const e = elemento();
      const d = resolve({ p: arr.p0 }, px - arr.px, py - arr.py);
      arr.p = candidato(e, arr.p0, d, px, py, ev.altKey); arr.arrasta = true;
      const es = arr.gr ? null : espelho(e, arr.id, arr.p0);
      arr.esp = es; arr.pe = es ? [arr.p[0], -arr.p[1], arr.p[2]] : null;
      atualiza();
    },
    solta() {
      const a = arr; arr = null;
      if (a && a.arrasta && a.p.some((v, k) => !iguais(v, a.p0[k]))) {
        const e = elemento();
        muda(() => {
          escreve(e, a.id, a.p); if (a.esp) escreve(a.esp.e, a.esp.id, a.pe);
          if (a.gr) a.gr.forEach((q, id) => escreve(e, id, [q[0] + a.p[0] - a.p0[0], q[1] + a.p[1] - a.p0[1], q[2] + a.p[2] - a.p0[2]]));
        });
      }
      atualiza();
    },
  };

  function aoMover(px, py, ev) {
    const e = elemento();
    if (!ativo || !suportado(e) || e.tipo !== "trelica" || !(ev.ctrlKey || ev.metaKey) || sel === null) { if (previa) { previa = null; atualiza(); } return; }
    const A = alcas(e), ref = A.find(a => a.id === sel); if (!ref) return;
    let mel = null, d0 = 11;
    A.forEach(a => { const q = proj(a.p); if (q) { const d = Math.hypot(q[0] - px, q[1] - py); if (d < d0) { d0 = d; mel = a; } } });
    let p;
    if (mel) { if (mel.id === sel) { if (previa) { previa = null; atualiza(); } return; } p = mel.p; }
    else { const q0 = proj(ref.p); if (!q0) return; p = candidato(e, ref.p, resolve({ p: ref.p }, px - q0[0], py - q0[1]), px, py, ev.altKey); }
    previa = { a: ref.p, b: p }; atualiza();
  }

  const escolhidos = () => (grupo.size ? [...grupo] : sel !== null ? [sel] : []).sort((a, b) => a - b);

  function copia(e) {
    const ids = escolhidos().filter(i => e.nos[i]); if (!ids.length) return;
    const mapa = {}; ids.forEach((i, k) => { mapa[i] = k; });
    area = { nos: ids.map(i => e.nos[i].slice()), barras: e.barras.filter(b => b[0] in mapa && b[1] in mapa).map(b => [mapa[b[0]], mapa[b[1]], ...b.slice(2)]), juntas: ids.map(i => Juntas.de(e, i)) };
    msg(`${ids.length} nó${ids.length === 1 ? "" : "s"} copiado${ids.length === 1 ? "" : "s"}. Ctrl+V cola deslocado.`);
  }

  function insere(e, nos, barras, juntas) {
    const base = e.nos.length, novos = [];
    muda(() => {
      nos.forEach((p, k) => { e.nos.push(p.map(v => +v.toFixed(5))); novos.push(base + k); if (juntas && juntas[k] && juntas[k] !== "solda") Juntas.define(e, base + k, juntas[k]); });
      barras.forEach(b => { if (temBarra(e, base + b[0], base + b[1]) < 0) e.barras.push([base + b[0], base + b[1], ...b.slice(2)]); });
    });
    grupo.clear(); novos.forEach(i => grupo.add(i)); sel = novos[0];
    atualiza();
  }

  function cola(e) {
    if (!area || !area.nos.length) { msg("Nada copiado: selecione nós e use Ctrl+C.", true); return; }
    const k = livres()[0], d = [0, 0, 0]; d[k] = 0.02;
    insere(e, area.nos.map(p => [p[0] + d[0], p[1] + d[1], p[2] + d[2]]), area.barras, area.juntas);
    msg("Colado 20 mm à frente no eixo " + "xyz"[k] + ": arraste um dos nós para posicionar o grupo.");
  }

  function espelha(e) {
    const ids = escolhidos().filter(i => e.nos[i]); if (!ids.length) return;
    const k = eixo ? "xyz".indexOf(eixo) : 1, o = off(e), piv = k === 1 ? -o[1] : e.nos[sel !== null && e.nos[sel] ? sel : ids[0]][k];
    const mapa = {}, nos = [], reuso = {};
    ids.forEach(i => {
      const p = e.nos[i].slice(); p[k] = 2 * piv - p[k];
      const j = e.nos.findIndex(q => q.every((v, c) => iguais(v, p[c])));
      if (j >= 0) reuso[i] = j; else { mapa[i] = nos.length; nos.push(p); }
    });
    if (!nos.length) { msg("Os nós espelhados já existem.", true); return; }
    const base = e.nos.length, alvo = i => (i in mapa ? base + mapa[i] : reuso[i]);
    const barras = e.barras.filter(b => ids.includes(b[0]) && ids.includes(b[1])).map(b => [alvo(b[0]), alvo(b[1]), ...b.slice(2)]);
    const novos = [];
    muda(() => {
      nos.forEach((p, c) => { e.nos.push(p.map(v => +v.toFixed(5))); novos.push(base + c); });
      ids.forEach(i => { if (i in mapa) { const c = Juntas.de(e, i); if (c !== "solda") Juntas.define(e, base + mapa[i], c); } });
      barras.forEach(b => { if (b[0] !== b[1] && temBarra(e, b[0], b[1]) < 0) e.barras.push(b); });
    });
    grupo.clear(); novos.forEach(i => grupo.add(i)); sel = novos[0];
    msg(`${novos.length} nó${novos.length === 1 ? "" : "s"} espelhado${novos.length === 1 ? "" : "s"} no eixo ${"xyz"[k]}.`);
    atualiza();
  }

  window.addEventListener("keydown", ev => {
    if (!ativo) return;
    const t = ev.target, tag = t && t.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
    const e = elemento(); if (!suportado(e)) return;
    if (ev.ctrlKey || ev.metaKey) {
      if (e.tipo !== "trelica") return;
      if (ev.key === "c" || ev.key === "C") { copia(e); ev.preventDefault(); }
      else if (ev.key === "v" || ev.key === "V") { cola(e); ev.preventDefault(); }
      return;
    }
    const k = ev.key, f = ev.shiftKey ? 10 : 1;
    if ((k === "i" || k === "I") && e.tipo === "trelica") { espelha(e); ev.preventDefault(); return; }
    if (k === "Escape") { liga(false); if (typeof props === "function") { props(); abaConteudo(); } ev.preventDefault(); return; }
    if (k === "p" || k === "P") { plano = (plano + 1) % PLANOS.length; eixo = null; atualiza(); ev.preventDefault(); return; }
    if ("xyzXYZ".includes(k) && k.length === 1) { const c = k.toLowerCase(); eixo = eixo === c ? null : c; atualiza(); ev.preventDefault(); return; }
    if (k === "m" || k === "M") { sim = !sim; atualiza(); ev.preventDefault(); return; }
    if ((k === "t" || k === "T") && e.tipo === "trelica") { const t = Object.keys(e.tubos || {}); if (t.length) { tubo = t[(t.indexOf(tuboAtual(e)) + 1) % t.length]; atualiza(); } ev.preventDefault(); return; }
    if (k === "6" && e.tipo === "trelica" && sel !== null && e.nos[sel]) {
      const a0 = alcas(e).find(q => q.id === sel), es = a0 && espelho(e, sel, a0.p), ids = es && es.e === e ? [sel, es.id] : [sel];
      let alvo = "";
      if (!Juntas.ligacaoDe(e, sel)) {
        let d0 = Infinity;
        esq.elementos.forEach(w => {
          if ((w.tipo || "asa") !== "asa" || !Array.isArray(w.secoes)) return;
          const o = w.posicao || [0, 0, 0], ys = w.secoes.map(s => s.y), y = Math.max(Math.min(...ys), Math.min(Math.max(...ys), a0.p[1] - o[1]));
          const d = Math.hypot(a0.p[1] - o[1] - y, a0.p[2] - o[2] - (w.secoes[0].zle || 0), Math.max(0, (o[0] + (w.secoes[0].xle || 0)) - a0.p[0], a0.p[0] - (o[0] + (w.secoes[0].xle || 0) + w.secoes[0].corda)));
          if (d < d0) { d0 = d; alvo = w.nome; }
        });
        if (!alvo) { msg("Não há asa no modelo para ligar.", true); return; }
      }
      muda(() => ids.forEach(i => Juntas.defineLigacao(e, i, alvo)));
      msg(alvo ? `Nó ligado a ${alvo}.` : "Ligação removida.");
      atualiza(); ev.preventDefault(); return;
    }
    if ("012345".includes(k) && k.length === 1 && e.tipo === "trelica" && sel !== null && e.nos[sel]) {
      const a0 = alcas(e).find(q => q.id === sel), es = a0 && espelho(e, sel, a0.p), ids = es && es.e === e ? [sel, es.id] : [sel];
      muda(() => ids.forEach(i => {
        if (k === "1") Juntas.define(e, i, "solda");
        else if (k === "2") { const c = Juntas.de(e, sel); Juntas.define(e, i, i === sel ? (c.startsWith("parafuso") ? Juntas.proximoParafuso(c) : "parafuso:y") : Juntas.de(e, sel)); }
        else if (k === "3") Juntas.define(e, i, "rotula");
        else if (k === "4") Juntas.defineVinculo(e, i, "engaste");
        else if (k === "5") Juntas.defineVinculo(e, i, "apoio");
        else Juntas.defineVinculo(e, i, "");
      }));
      atualiza(); ev.preventDefault(); return;
    }
    if ((k === "l" || k === "L") && e.tipo === "trelica") { autoLiga = !autoLiga; atualiza(); ev.preventDefault(); return; }
    const A = alcas(e);
    if ((k === "Delete" || k === "Backspace") && e.tipo === "trelica" && sel !== null && e.nos[sel]) {
      const a0 = A.find(q => q.id === sel), es = a0 && espelho(e, sel, a0.p), ids = grupo.size > 1 ? [...grupo] : (es && es.e === e ? [sel, es.id] : [sel]);
      grupo.clear();
      const ord = e.nos.map((_, i) => i).filter(i => !ids.includes(i));
      muda(() => { removeNos(e, ids); });
      const ant = ord.filter(i => i < sel).length; sel = e.nos.length ? Math.min(ant, e.nos.length - 1) : null;
      atualiza(); ev.preventDefault(); return;
    }
    if (k === "Tab" && A.length) {
      const i = A.findIndex(a => a.id === sel); sel = A[(i + (ev.shiftKey ? -1 : 1) + A.length) % A.length].id; atualiza(); ev.preventDefault(); return;
    }
    const a = A.find(q => q.id === sel); if (!a) return;
    const eixoDe = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [2, 1], ArrowDown: [2, -1], ",": [1, -1], ".": [1, 1], "<": [1, -1], ">": [1, 1] }[k];
    if (!eixoDe) return;
    const p = a.p.slice(); p[eixoDe[0]] += eixoDe[1] * f * PASSO;
    const es = espelho(e, a.id, a.p);
    muda(() => { escreve(e, a.id, p); if (es) escreve(es.e, es.id, [p[0], -p[1], p[2]]); });
    atualiza(); ev.preventDefault();
  });

  const pares = e => { const a0 = alcas(e).find(q => q.id === sel), es = a0 && espelho(e, sel, a0.p); return es && es.e === e ? [sel, es.id] : [sel]; };
  const selecao = () => {
    const e = elemento(); if (!ativo || !suportado(e)) return null;
    const a = alcas(e).find(q => q.id === sel);
    if (!a) return { elemento: e.nome, tipo: e.tipo, id: null, total: alcas(e).length };
    const r = { elemento: e.nome, tipo: e.tipo, id: a.id, p: a.p.slice(), total: alcas(e).length };
    if (e.tipo === "trelica" && margens && chave(a.p) in margens) r.margem = margens[chave(a.p)];
    if (e.tipo === "trelica") Object.assign(r, { junta: Juntas.de(e, a.id), vinculo: Juntas.vinculoDe(e, a.id), ligacao: Juntas.ligacaoDe(e, a.id), barras: e.barras.filter(b => b[0] === a.id || b[1] === a.id).length });
    return r;
  };
  function defineSel(p) {
    const e = elemento(); if (!ativo || !suportado(e)) return;
    const a = alcas(e).find(q => q.id === sel); if (!a || !p.every(v => typeof v === "number" && isFinite(v))) return;
    const es = espelho(e, a.id, a.p);
    muda(() => { escreve(e, a.id, p); if (es) escreve(es.e, es.id, [p[0], -p[1], p[2]]); });
    atualiza();
  }
  function defineJunta(campo, valor) {
    const e = elemento(); if (!ativo || !suportado(e) || e.tipo !== "trelica" || sel === null || !e.nos[sel]) return;
    const ids = pares(e);
    muda(() => ids.forEach(i => { if (campo === "junta") Juntas.define(e, i, valor); else if (campo === "vinculo") Juntas.defineVinculo(e, i, valor); else Juntas.defineLigacao(e, i, valor); }));
    atualiza();
  }

  return { liga, atualiza, ativo: () => ativo, suportado, chave, defineMargens: m => { margens = m; if (ativo) atualiza(); }, selecao, defineSel, defineJunta, puro: { alcas, escreve, espelho, temBarra, removeNos, resolve, grupo, copia, cola, espelha, seleciona: i => { sel = i; }, define: o => { if ("plano" in o) plano = o.plano; if ("eixo" in o) eixo = o.eixo; if ("sim" in o) sim = o.sim; } } };
})();
