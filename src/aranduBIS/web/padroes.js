"use strict";

const Padroes = (() => {
  const val = {}, ouvintes = [];
  function atualiza(d) {
    (d.opcoes || []).forEach(o => { val[o.chave] = o.valor; });
    if (val["aparencia.tema"] !== undefined) Tema.escolhe(val["aparencia.tema"]);
    ouvintes.forEach(f => f());
  }
  fetch("/api/configuracao").then(r => r.json()).then(atualiza).catch(() => {  });
  return {
    atualiza,
    get: k => val[k],
    aoMudar: f => ouvintes.push(f),
    aplica(v, campos) {
      const t = v.__tocado = v.__tocado || {};
      campos.forEach(c => { if (c.cfg && !t[c.k] && val[c.cfg] !== undefined) v[c.k] = val[c.cfg]; });
    },
    toca(v, k) { (v.__tocado = v.__tocado || {})[k] = true; },
  };
})();
