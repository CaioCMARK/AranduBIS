"use strict";

const Estado = (() => {
  const v = { esq: null, sel: -1, malha: null, aba: "Seções", filtroCamada: "tudo" };
  const ouvintes = new Set();
  const api = {
    chaves: Object.keys(v),
    ouve(fn) { ouvintes.add(fn); return () => ouvintes.delete(fn); },
    avisa(chave) { for (const f of [...ouvintes]) { try { f(chave, v[chave], v[chave]); } catch (x) { console.error(x); } } },
    elemento: () => (v.esq && v.esq.elementos[v.sel]) || null,
  };
  for (const k of Object.keys(v)) {
    const prop = {
      enumerable: true,
      get: () => v[k],
      set: x => {
        const antes = v[k];
        v[k] = x;
        if (antes !== x) for (const f of [...ouvintes]) { try { f(k, x, antes); } catch (e) { console.error(e); } }
      },
    };
    Object.defineProperty(api, k, prop);
    if (typeof window !== "undefined") Object.defineProperty(window, k, { ...prop, configurable: true });
  }
  return api;
})();

if (typeof module !== "undefined") module.exports = { Estado };
