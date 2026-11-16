"use strict";

(() => {
  const ABA = ".etapas > div, .abas > div", ITEM = ".el, #lista2 > div, #lista3 > div, #lista4 > div, #lista5 > div, #manual_lista > div";
  function decora(raiz) {
    raiz.querySelectorAll(".etapas, .abas").forEach(g => { if (!g.hasAttribute("role")) g.setAttribute("role", "tablist"); });
    raiz.querySelectorAll(ABA).forEach(d => {
      if (!d.hasAttribute("role")) { d.setAttribute("role", "tab"); d.tabIndex = 0; }
      d.setAttribute("aria-selected", d.classList.contains("at") ? "true" : "false");
    });
    raiz.querySelectorAll(ITEM).forEach(d => {
      if (d.onclick || d.classList.contains("el")) { if (!d.hasAttribute("tabindex")) { d.tabIndex = 0; d.setAttribute("role", "option"); } d.setAttribute("aria-selected", d.classList.contains("sel") || d.classList.contains("at") ? "true" : "false"); }
    });
    raiz.querySelectorAll("#lista, #lista2, #lista3, #lista4, #lista5").forEach(l => { if (!l.hasAttribute("role")) l.setAttribute("role", "listbox"); });
  }
  let pend = false;
  const agenda = () => { if (pend) return; pend = true; setTimeout(() => { pend = false; decora(document); }, 60); };
  new MutationObserver(agenda).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  document.addEventListener("keydown", ev => {
    const t = ev.target;
    if (!t || !t.matches || !(t.matches(ABA) || t.matches(ITEM))) return;
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); t.click(); return; }
    const dir = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
    if (!dir) return;
    const irmaos = [...t.parentElement.children].filter(x => x.tabIndex === 0), i = irmaos.indexOf(t), alvo = irmaos[i + dir];
    if (alvo) { ev.preventDefault(); alvo.focus(); }
  });
  decora(document);
})();
