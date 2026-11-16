"use strict";

const PeleCor = (() => {
  let ativo = false, tempo = null, seq = 0, resumo = "";
  const sel = document.createElement("select");
  sel.id = "s_cor"; sel.title = "Como colorir a aeronave na vista 3D";
  [["", "Cor por elemento"], ["desdobra", "Cor: desdobramento do chapeado"]].forEach(([k, n]) => sel.add(new Option(n, k)));
  const ancora = document.querySelector("[data-camada='estrutura']");
  if (ancora) { const s = document.createElement("span"); s.className = "sep"; ancora.after(s); s.after(sel); }

  const hsl = (p, lim) => {
    const h = 120 * (1 - Math.min(p / (lim * 3), 1)) / 360, s = 0.62, l = 0.46;
    const a = s * Math.min(l, 1 - l), f = n => { const k = (n + h * 12) % 12; return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)); };
    return [Math.round(255 * f(0)), Math.round(255 * f(8)), Math.round(255 * f(4))];
  };
  const css = c => `rgb(${c[0]},${c[1]},${c[2]})`;

  function agenda() { clearTimeout(tempo); tempo = setTimeout(aplica, 500); }

  async function aplica() {
    const meu = ++seq;
    if (!ativo) { vista.limpaSobre(); return; }
    if (typeof malha === "undefined" || !malha || !esq || !esq.elementos.length) { vista.limpaSobre(); return; }
    const asas = esq.elementos.filter(e => e.tipo === "asa" && e.estrutura && e.estrutura.chapeado);
    if (!asas.length) { vista.limpaSobre(); msg("Nenhuma asa tem chapeado declarado: declare na aba Estrutura da asa até onde a pele vai.", true); return; }
    msg("Calculando o desdobramento do chapeado…");
    const nt = malha.zona.length, ids = new Int32Array(nt), paleta = [null, [150, 156, 164]];
    let lim = 0, max = 0, linhas = [];
    try {
      for (const a of asas) {
        const r = await chama("/api/planificacao", Planifica3.corpoPara(a.nome));
        if (meu !== seq) return;
        if (r.erro) { linhas.push(`${a.nome}: ${r.erro.slice(0, 40)}`); continue; }
        let t0 = -1;
        for (let t = 0; t < nt; t++) { if (malha.zonas[malha.zona[t]].startsWith(a.nome + ".")) { t0 = t; break; } }
        if (t0 < 0 || t0 + r.mapa.n > nt) { linhas.push(`${a.nome}: malha não confere`); continue; }
        lim = lim || r.limite_pct;
        const base = paleta.length;
        r.faixas.forEach(f => { paleta.push(hsl(f.deformacao_max_pct, r.limite_pct)); max = Math.max(max, f.deformacao_max_pct); });
        let t = t0;
        r.mapa.rle.forEach(([k, n]) => { ids.fill(k ? base + k - 1 : 1, t, t + n); t += n; });
        linhas.push(`${a.nome}: ${r.resumo.ok} bem · ${r.resumo.atencao} cuidado · ${r.resumo.nao} emendar`);
      }
    } catch (e) { if (meu === seq) msg(e.message, true); return; }
    if (meu !== seq) return;
    const topo = Math.max(3 * (lim || 0.3), 1e-6);
    vista.defineSobre(ids, paleta, { titulo: "Chapeado planificado", limite: (lim || 0).toFixed(2).replace(".", ","), maximo: topo.toFixed(2).replace(".", ",") + " ou mais",
      escala: [[0, css(hsl(0, 1))], [0.5, css(hsl(topo / 2, topo / 3))], [1, css(hsl(topo, topo / 3))]], linhas: linhas.concat(["cinza: sem faixa (fora da pele)"]) });
    msg("Pronto");
  }

  sel.onchange = () => { ativo = sel.value === "desdobra"; if (ativo) aplica(); else vista.limpaSobre(); };
  return { atualiza() { if (ativo) agenda(); }, ativo: () => ativo };
})();
