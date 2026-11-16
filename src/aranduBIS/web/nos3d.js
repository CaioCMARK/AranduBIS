"use strict";

const No3D = (() => {
  const PASSO = 0.001, IMA = 9;
  const PLANOS = [["xy", "planta (x, y)", [0, 1]], ["xz", "perfil (x, z)", [0, 2]], ["yz", "frontal (y, z)", [1, 2]]];
  let ativo = false, sel = null, arr = null, plano = 0, eixo = null, sim = true, tubo = null, autoLiga = true;

  const TIPOS = ["trelica", "roda", "ponto"];
  const iguais = (a, b) => Math.abs(a - b) < 1e-5;
  const rotado = e => ["rolagem", "arfagem", "guinada"].some(c => Math.abs(e[c] || 0) > 1e-9);
  const suportado = e => e && TIPOS.includes(e.tipo) && !rotado(e);
  const off = e => (e.tipo === "trelica" ? (e.posicao || [0, 0, 0]) : [0, 0, 0]);

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

  function atualiza() {
    const e = elemento();
    if (ativo && !suportado(e)) { ativo = false; vista.ferramenta = (typeof Nervura3D !== "undefined" && Nervura3D.ativo()) ? vista.ferramenta : null; }
    if (!ativo) { vista.pontos = null; if (!(typeof Nervura3D !== "undefined" && Nervura3D.ativo())) vista.hud = null; vista.desenha(); return; }
    const A = alcas(e), pts = A.map(a => ({ p: arr && arr.arrasta && arr.id === a.id ? arr.p : (arr && arr.arrasta && arr.esp && arr.esp.id === a.id && arr.esp.e === e ? arr.pe : a.p), sel: sel === a.id, forma: e.tipo === "trelica" ? Juntas.de(e, a.id).split(":")[0] : "solda", vinculo: e.tipo === "trelica" ? Juntas.vinculoDe(e, a.id) : "", ligacao: e.tipo === "trelica" && !!Juntas.ligacaoDe(e, a.id) }));
    vista.pontos = pts;
    const a = A.find(q => q.id === sel), h = [];
    if (a) {
      const p = arr && arr.arrasta ? arr.p : a.p, lig = e.tipo === "trelica" ? e.barras.filter(b => b[0] === sel || b[1] === sel).length : 0;
      h.push(`${e.tipo === "trelica" ? "Nó " + sel : e.nome} · x ${(p[0] * 1000).toFixed(0)}  y ${(p[1] * 1000).toFixed(0)}  z ${(p[2] * 1000).toFixed(0)} mm`);
      h.push(e.tipo === "trelica" ? `liga ${lig} barra${lig === 1 ? "" : "s"} · ${A.length} nós` : "arraste a bolinha para reposicionar");
      if (e.tipo === "trelica") h.push(`junta: ${Juntas.rotulo(Juntas.de(e, sel))} · vínculo: ${Juntas.vinculoDe(e, sel) || "livre"}${Juntas.ligacaoDe(e, sel) ? " · liga a " + Juntas.ligacaoDe(e, sel) : ""}`);
    } else h.push(`Editando ${e.nome}`);
    h.push(eixo ? `Movimento: só no eixo ${eixo.toUpperCase()}` : `Movimento no plano ${PLANOS[plano][1]}`);
    h.push("Arraste uma bolinha (Alt = sem passo e sem ímã)");
    h.push("X/Y/Z trava o eixo · P troca o plano · M simetria " + (sim ? "ligada" : "desligada"));
    h.push("←/→ move x · ↑/↓ move z · , . move y (Shift ×10)");
    if (e.tipo === "trelica") {
      h.push(`Ctrl+clique: cria nó${autoLiga ? " ligado ao selecionado" : ""} · em outro nó, liga/desliga barra`);
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
      sel = mel.id; arr = { id: mel.id, p0: mel.p, p: mel.p, px, py, arrasta: false, esp: null, pe: null };
      atualiza(); return true;
    },
    move(px, py, ev) {
      if (!arr) return; const e = elemento();
      const d = resolve({ p: arr.p0 }, px - arr.px, py - arr.py);
      arr.p = candidato(e, arr.p0, d, px, py, ev.altKey); arr.arrasta = true;
      const es = espelho(e, arr.id, arr.p0);
      arr.esp = es; arr.pe = es ? [arr.p[0], -arr.p[1], arr.p[2]] : null;
      atualiza();
    },
    solta() {
      const a = arr; arr = null;
      if (a && a.arrasta && a.p.some((v, k) => !iguais(v, a.p0[k]))) {
        const e = elemento();
        muda(() => { escreve(e, a.id, a.p); if (a.esp) escreve(a.esp.e, a.esp.id, a.pe); });
      }
      atualiza();
    },
  };

  window.addEventListener("keydown", ev => {
    if (!ativo || ev.ctrlKey || ev.metaKey) return;
    const t = ev.target, tag = t && t.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
    const e = elemento(); if (!suportado(e)) return;
    const k = ev.key, f = ev.shiftKey ? 10 : 1;
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
      const a0 = A.find(q => q.id === sel), es = a0 && espelho(e, sel, a0.p), ids = es && es.e === e ? [sel, es.id] : [sel];
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

  return { liga, atualiza, ativo: () => ativo, suportado };
})();
