"use strict";

const Tema = (() => {
  const CHAVE = "aranduBIS.tema", VALIDOS = ["auto", "escuro", "cinza", "claro"];
  const escuro = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const ouvintes = [];
  let escolha = "cinza";
  try { const g = localStorage.getItem(CHAVE); if (VALIDOS.includes(g)) escolha = g; } catch (e) {  }

  function resolvido() { return escolha !== "auto" ? escolha : (escuro && escuro.matches ? "escuro" : "claro"); }
  function aplica() {
    document.documentElement.setAttribute("data-tema", resolvido());
    ouvintes.forEach(f => f());
  }
  if (escuro && escuro.addEventListener) escuro.addEventListener("change", () => { if (escolha === "auto") aplica(); });
  aplica();
  return {
    escolhe(nome) {
      if (!VALIDOS.includes(nome) || nome === escolha) return;
      escolha = nome;
      try { localStorage.setItem(CHAVE, nome); } catch (e) {  }
      aplica();
    },
    aoMudar: f => ouvintes.push(f),
    cor: nome => getComputedStyle(document.documentElement).getPropertyValue(nome).trim(),
  };
})();
