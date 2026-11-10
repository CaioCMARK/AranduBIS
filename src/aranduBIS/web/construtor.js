"use strict";

const Construtor = (() => {
  let MATERIAIS = ["balsa"];
  fetch("/api/materiais").then(r => r.json()).then(d => { MATERIAIS = d.materiais.map(m => m.nome); }).catch(() => {});

  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const bloco = (C, t) => { const b = el("div", "", "bloco"); b.append(el("h5", t)); C.append(b); return b; };
  const botao = (txt, ao, dica) => { const b = el("button", txt); if (dica) b.title = dica; b.onclick = ao; b.style.margin = "4px 6px 4px 0"; return b; };
  function selecao(valor, opcoes, ao) {
    const s = document.createElement("select");
    opcoes.forEach(o => s.add(new Option(o, o)));
    s.value = valor; s.onchange = () => ao(s.value); return s;
  }
  function tabela(B, cab, linhas, remove) {
    const t = document.createElement("table"), h = document.createElement("tr");
    cab.forEach(c => h.append(el("th", c))); if (remove) h.append(el("th")); t.append(h);
    linhas.forEach((cels, i) => {
      const tr = document.createElement("tr");
      cels.forEach(c => { const td = document.createElement("td"); td.append(c instanceof Node ? c : document.createTextNode(c)); tr.append(td); });
      if (remove) { const td = document.createElement("td"), b = el("button", "✕"); b.title = "Remover"; b.onclick = () => remove(i); td.append(b); tr.append(td); }
      t.append(tr);
    });
    B.append(t); return t;
  }
  const num = (v, ao) => entrada("number", v, x => ao(x ?? 0));
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

  function trelica(C, e) {
    e.nos = e.nos || []; e.barras = e.barras || []; e.tubos = e.tubos || {};
    const usados = t => e.barras.filter(b => b[2] === t).length;
    const tipos = () => Object.keys(e.tubos);

    const comprimento = e.barras.reduce((s, b) => s + (e.nos[b[0]] && e.nos[b[1]] ? dist(e.nos[b[0]], e.nos[b[1]]) : 0), 0);
    C.append(el("div", `${e.nos.length} nós · ${e.barras.length} barras · ${fmt(comprimento, 2)} m de tubo. Barras que dividem um nó formam junta rígida na análise de estrutura.`, "nota"));

    const T = bloco(C, "Tipos de tubo");
    tabela(T, ["nome", "D ext (mm)", "D int (mm)", "material", "barras"],
      tipos().map(n => {
        const q = e.tubos[n];
        return [n, entrada("number", +(q.de * 1000).toFixed(4), v => muda(() => { q.de = (v || 0) / 1000; })),
          entrada("number", +((q.di || 0) * 1000).toFixed(4), v => muda(() => { q.di = (v || 0) / 1000; })),
          selecao(q.material || "tubo_carbono", [...new Set([q.material || "tubo_carbono", ...MATERIAIS])], v => muda(() => { q.material = v; })), String(usados(n))];
      }),
      i => {
        const n = tipos()[i];
        if (usados(n)) return msg(`O tubo ${n} é usado em ${usados(n)} barras: troque o tipo delas antes.`, true);
        muda(() => { delete e.tubos[n]; }); abaConteudo();
      });
    T.append(botao("+ tipo de tubo", () => {
      let k = 1; while (e.tubos["T" + k]) k++;
      muda(() => { e.tubos["T" + k] = { de: 0.004, di: 0.003, material: "tubo_carbono" }; }); abaConteudo();
    }));

    const N = bloco(C, "Nós (m)");
    tabela(N, ["#", "x", "y", "z", "barras"],
      e.nos.map((p, i) => [String(i), ...[0, 1, 2].map(k => num(p[k], v => muda(() => { p[k] = v; }))), String(e.barras.filter(b => b[0] === i || b[1] === i).length)]),
      i => {
        const ligadas = e.barras.filter(b => b[0] === i || b[1] === i).length;
        if (ligadas && !confirm(`O nó ${i} liga ${ligadas} barra(s): remover o nó remove essas barras. Continuar?`)) return;
        muda(() => {
          e.barras = e.barras.filter(b => b[0] !== i && b[1] !== i).map(b => [b[0] > i ? b[0] - 1 : b[0], b[1] > i ? b[1] - 1 : b[1], ...b.slice(2)]);
          e.nos.splice(i, 1);
        }); abaConteudo();
      });
    const bn = el("div"); N.append(bn);
    bn.append(botao("+ nó", () => {
      const u = e.nos[e.nos.length - 1] || [0, 0, 0];
      muda(() => e.nos.push([+(u[0] + 0.1).toFixed(5), u[1], u[2]])); abaConteudo();
    }, "Novo nó 0,1 m à frente do último"));
    bn.append(botao("Espelhar em y", () => espelha(e), "Copia nós e barras com y trocado de sinal (a treliça simétrica da fuselagem: desenhe um lado e espelhe)"));
    bn.append(botao("Remover nós soltos", () => {
      const vivo = new Set(e.barras.flatMap(b => [b[0], b[1]])), mapa = {}; let k = 0;
      e.nos.forEach((_, i) => { if (vivo.has(i)) mapa[i] = k++; });
      if (k === e.nos.length) return msg("Não há nós soltos.");
      muda(() => { e.nos = e.nos.filter((_, i) => vivo.has(i)); e.barras = e.barras.map(b => [mapa[b[0]], mapa[b[1]], ...b.slice(2)]); }); abaConteudo();
    }));

    const B = bloco(C, "Barras");
    const ids = e.nos.map((_, i) => i);
    tabela(B, ["de nó", "a nó", "tubo", "comprimento (mm)"],
      e.barras.map(b => {
        const ok = e.nos[b[0]] && e.nos[b[1]];
        return [entrada("number", b[0], v => muda(() => { b[0] = Math.round(v ?? 0); })), entrada("number", b[1], v => muda(() => { b[1] = Math.round(v ?? 0); })),
          selecao(b[2] in e.tubos ? b[2] : tipos()[0], tipos(), v => muda(() => { b[2] = v; })), ok ? fmt(1000 * dist(e.nos[b[0]], e.nos[b[1]]), 1) : "nó inválido"];
      }),
      i => { muda(() => e.barras.splice(i, 1)); abaConteudo(); });
    B.append(botao("+ barra", () => {
      if (e.nos.length < 2) return msg("Crie pelo menos dois nós.", true);
      if (!tipos().length) return msg("Crie um tipo de tubo antes.", true);
      const n = e.nos.length;
      muda(() => e.barras.push([n - 2, n - 1, tipos()[0]])); abaConteudo();
    }, "Liga os dois últimos nós; depois ajuste os números"));
    void ids;
  }

  function espelha(e) {
    const ja = new Set(e.nos.map(p => p.map(x => x.toFixed(5)).join()));
    if (!e.nos.some(p => Math.abs(p[1]) > 1e-9)) return msg("Todos os nós estão em y = 0: nada para espelhar.", true);
    muda(() => {
      const n0 = e.nos.length, idx = {};
      e.nos.slice(0, n0).forEach((p, i) => {
        if (Math.abs(p[1]) < 1e-9) { idx[i] = i; return; }
        const q = [p[0], -p[1], p[2]], chave = q.map(x => x.toFixed(5)).join();
        if (ja.has(chave)) { idx[i] = e.nos.findIndex(r => r.map(x => x.toFixed(5)).join() === chave); return; }
        idx[i] = e.nos.length; e.nos.push(q);
      });
      const tem = new Set(e.barras.map(b => Math.min(b[0], b[1]) + "-" + Math.max(b[0], b[1])));
      e.barras.slice().forEach(b => {
        const a = idx[b[0]], c = idx[b[1]], k = Math.min(a, c) + "-" + Math.max(a, c);
        if (a !== c && !tem.has(k)) { tem.add(k); e.barras.push([a, c, ...b.slice(2)]); }
      });
    }); abaConteudo();
  }

  function placa(C, e) {
    e.contorno = e.contorno || [];
    const G = bloco(C, "Chapa"), g = el("div", "", "prop"); G.append(g);
    const l = (r, w) => { const a = el("label", r); g.append(a, w); };
    l("posição y (m)", entrada("number", e.y ?? 0, v => muda(() => { e.y = v ?? 0; })));
    l("material", selecao(e.material || MATERIAIS[0], [...new Set([e.material || MATERIAIS[0], ...MATERIAIS])], v => muda(() => { e.material = v; })));
    G.append(el("div", "Contorno no plano x–z, extrudado na espessura (nas Propriedades), centrado em y.", "nota"));

    const P = bloco(C, "Contorno (m)");
    tabela(P, ["#", "x", "z"], e.contorno.map((p, i) => [String(i), num(p[0], v => muda(() => { p[0] = v; })), num(p[1], v => muda(() => { p[1] = v; }))]),
      i => {
        if (e.contorno.length <= 3) return msg("A chapa precisa de pelo menos 3 pontos.", true);
        muda(() => e.contorno.splice(i, 1)); abaConteudo();
      });
    const b = el("div"); P.append(b);
    b.append(botao("+ ponto", () => {
      const u = e.contorno[e.contorno.length - 1] || [0, 0];
      muda(() => e.contorno.push([+(u[0] + 0.05).toFixed(4), u[1]])); abaConteudo();
    }));
    b.append(botao("Retângulo…", () => {
      const w = parseFloat(prompt("Largura em x (m):", "0.3")), h = parseFloat(prompt("Altura em z (m):", "0.2"));
      if (!(w > 0 && h > 0)) return;
      muda(() => { e.contorno = [[0, 0], [w, 0], [w, h], [0, h]]; }); abaConteudo();
    }, "Substitui o contorno por um retângulo"));
    if (e.contorno.length >= 3) {
      const C2 = e.contorno; let A = 0;
      C2.forEach((p, i) => { const q = C2[(i + 1) % C2.length]; A += p[0] * q[1] - q[0] * p[1]; });
      P.append(el("div", `Área ${fmt(Math.abs(A) / 2 * 1e4, 1)} cm² · volume ${fmt(Math.abs(A) / 2 * (e.espessura || 0) * 1e6, 1)} cm³`, "nota"));
    }
  }

  return { trelica, placa };
})();
