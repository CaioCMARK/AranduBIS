"use strict";

const Ocupado = (() => {
  const pend = new Map();
  let seq = 0, caixa = null, relogio = null, aquecido = false;
  const LEVES = ["/api/geometria", "/api/secoes", "/api/nervuras/posicoes", "/api/materiais", "/api/configuracao"];

  function monta() {
    if (caixa) return caixa;
    caixa = document.createElement("div"); caixa.className = "ocupado"; caixa.hidden = true;
    caixa.setAttribute("role", "status"); caixa.setAttribute("aria-live", "polite");
    const giro = document.createElement("span"); giro.className = "giro"; giro.setAttribute("aria-hidden", "true");
    const txt = document.createElement("span"); txt.className = "ocupado-txt";
    const bt = document.createElement("button"); bt.textContent = "Cancelar"; bt.title = "Para de esperar por este cálculo. O que já foi calculado é descartado.";
    bt.onclick = cancela;
    caixa.append(giro, txt, bt); document.body.append(caixa);
    return caixa;
  }

  function pinta() {
    const c = monta(), agora = performance.now();
    const vivos = [...pend.values()].filter(p => !p.leve && agora - p.t0 > 600);
    if (!vivos.length) { c.hidden = true; document.body.classList.remove("calculando"); return; }
    const s = Math.round((agora - Math.min(...vivos.map(p => p.t0))) / 1000);
    let t = `Calculando… ${s} s`;
    if (!aquecido && s >= 4) t += " · na primeira análise o programa prepara as rotinas numéricas; as próximas são rápidas";
    c.querySelector(".ocupado-txt").textContent = t; c.hidden = false; document.body.classList.add("calculando");
  }

  function inicia(url) {
    const id = ++seq, ctl = new AbortController();
    pend.set(id, { url, t0: performance.now(), ctl, leve: LEVES.some(l => url.startsWith(l)) });
    if (!relogio) relogio = setInterval(pinta, 500);
    return { id, sinal: ctl.signal };
  }
  function termina(id, ok) {
    const p = pend.get(id); pend.delete(id);
    if (p && !p.leve && ok && performance.now() - p.t0 > 1500) aquecido = true;
    if (!pend.size) { clearInterval(relogio); relogio = null; }
    pinta();
  }
  function cancela() { pend.forEach(p => { if (!p.leve) p.ctl.abort(); }); }

  return { inicia, termina, cancela, pendentes: () => [...pend.values()].filter(p => !p.leve).length };
})();
