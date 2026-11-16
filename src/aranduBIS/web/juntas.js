"use strict";

const Juntas = (() => {
  const OPCOES = [["solda", "solda"], ["parafuso:y", "parafuso (eixo y)"], ["parafuso:x", "parafuso (eixo x)"], ["parafuso:z", "parafuso (eixo z)"], ["rotula", "rótula"]];
  const VINCULOS = [["", "livre"], ["engaste", "engaste"], ["apoio", "apoio (translação)"]];

  function de(e, i) {
    const j = (e.juntas || []).find(q => q.no === i);
    if (!j || j.tipo === "solda" || !j.tipo) return "solda";
    return j.tipo === "parafuso" ? "parafuso:" + (j.eixo_livre || "y") : "rotula";
  }
  function define(e, i, codigo) {
    e.juntas = (e.juntas || []).filter(q => q.no !== i);
    if (codigo && codigo !== "solda") {
      const [tipo, eixo] = codigo.split(":");
      e.juntas.push(tipo === "parafuso" ? { no: i, tipo, eixo_livre: eixo || "y" } : { no: i, tipo: "rotula" });
    }
    if (!e.juntas.length) delete e.juntas;
  }
  function vinculoDe(e, i) {
    const v = (e.vinculos || []).find(q => q.no === i && (q.tipo === "engaste" || q.tipo === "apoio"));
    return v ? v.tipo : "";
  }
  function defineVinculo(e, i, tipo) {
    e.vinculos = (e.vinculos || []).filter(q => !(q.no === i && (q.tipo === "engaste" || q.tipo === "apoio")));
    if (tipo === "engaste") e.vinculos.push({ no: i, tipo: "engaste" });
    else if (tipo === "apoio") e.vinculos.push({ no: i, tipo: "apoio", graus: [1, 2, 3] });
    if (!e.vinculos.length) delete e.vinculos;
  }
  function remapeia(e, mapa) {
    ["juntas", "vinculos"].forEach(c => {
      if (!e[c]) return;
      e[c] = e[c].filter(q => mapa[q.no] !== undefined).map(q => ({ ...q, no: mapa[q.no] }));
      if (!e[c].length) delete e[c];
    });
  }
  function copia(e, deNo, paraNo) {
    define(e, paraNo, de(e, deNo));
    defineVinculo(e, paraNo, vinculoDe(e, deNo));
    defineLigacao(e, paraNo, ligacaoDe(e, deNo));
  }
  function ligacaoDe(e, i) {
    const v = (e.vinculos || []).find(q => q.no === i && q.tipo === "ligacao");
    return v ? v.alvo || "" : "";
  }
  function defineLigacao(e, i, alvo) {
    e.vinculos = (e.vinculos || []).filter(q => !(q.no === i && q.tipo === "ligacao"));
    if (alvo) e.vinculos.push({ no: i, tipo: "ligacao", alvo });
    if (!e.vinculos.length) delete e.vinculos;
  }
  const rotulo = codigo => (OPCOES.find(o => o[0] === codigo) || OPCOES[0])[1];
  const proximoParafuso = codigo => ({ "parafuso:y": "parafuso:x", "parafuso:x": "parafuso:z", "parafuso:z": "parafuso:y" }[codigo] || "parafuso:y");

  return { OPCOES, VINCULOS, de, define, vinculoDe, defineVinculo, remapeia, copia, rotulo, proximoParafuso, ligacaoDe, defineLigacao };
})();

if (typeof module !== "undefined") module.exports = Juntas;
