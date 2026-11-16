"use strict";

const Config = (() => {
  const dlg = document.getElementById("dlg_config");
  const corpo = document.getElementById("cfg_corpo");
  const aviso = document.getElementById("cfg_aviso");

  async function envia(mudanca) {
    const r = await fetch("/api/configuracao", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(mudanca),
    });
    const d = await r.json();
    if (!r.ok) { mostraErro(d.erro || "recusado"); await carrega(); return; }
    pinta(d);
  }

  function mostraErro(t) { aviso.hidden = false; aviso.textContent = t; aviso.classList.add("erro"); }

  function campo(o) {
    let w;
    if (o.tipo === "escolha") {
      w = document.createElement("select");
      o.escolhas.forEach(e => w.add(new Option(e, e)));
      w.value = o.valor;
      w.onchange = () => envia({ [o.chave]: w.value });
    } else if (o.tipo === "booleano") {
      w = document.createElement("input"); w.type = "checkbox"; w.checked = o.valor;
      w.onchange = () => envia({ [o.chave]: w.checked });
    } else if (o.tipo === "numero") {
      w = document.createElement("input"); w.type = "number"; w.value = o.valor ?? "";
      w.min = o.minimo; w.max = o.maximo; w.step = "any";
      if (o.auto && o.valor === null) w.placeholder = "automático";
      w.onchange = () => envia({ [o.chave]: w.value === "" && o.auto ? null : parseFloat(w.value) });
    } else {
      w = document.createElement("input"); w.type = "text"; w.value = o.valor;
      w.placeholder = "C:\\caminho\\arquivo.exe";
      w.onchange = () => envia({ [o.chave]: w.value.trim() });
    }
    w.id = "cfg_" + o.chave;
    return w;
  }

  function pinta(d) {
    Padroes.atualiza(d);
    aviso.classList.remove("erro");
    aviso.hidden = !d.problemas.length;
    aviso.textContent = d.problemas.join(" ");
    corpo.innerHTML = "";
    let grupo = null;
    for (const o of d.opcoes) {
      if (o.sem_efeito) continue;
      if (o.grupo !== grupo) {
        grupo = o.grupo;
        const h = document.createElement("div"); h.className = "grupo"; h.textContent = grupo; h.dataset.grupo = grupo; corpo.append(h);
        if (grupo === "Discretização") corpo.append(maquina());
      }
      const l = document.createElement("div");
      l.className = "opc" + (o.ativa ? "" : " inerte");
      const rot = document.createElement("label");
      rot.textContent = o.rotulo; rot.htmlFor = "cfg_" + o.chave;
      const w = campo(o);
      w.disabled = !o.ativa;
      const aj = document.createElement("div"); aj.className = "ajuda"; aj.textContent = o.ajuda;
      l.append(rot, w);
      if (o.referencia) {
        const auto = o.derivado || !!o.auto;
        const nome = auto ? "automático" : "referência";
        const b = document.createElement("button"); b.type = "button"; b.className = "auto";
        b.textContent = o.manual ? "voltar ao " + (auto ? "automático" : "valor de referência") : nome;
        b.disabled = !o.manual || !o.ativa;
        b.title = o.manual ? "Descarta o valor fixado e volta ao " + nome
                           : (o.auto ? "Escolhido pelo programa em cada caso: " + o.auto : o.derivado ? "Calculado das outras opções" : "Valor da literatura")
                             + ". Digite outro para fixar um valor.";
        b.onclick = () => envia({ [o.chave]: null });
        l.append(b);
        if (o.auto) aj.textContent = (o.manual ? "Valor fixado por você (o automático seria: " + o.auto + "). " : "Automático: " + o.auto + ". ") + o.ajuda;
        else if (o.fonte) aj.textContent = (o.manual ? "Valor fixado por você. Referência: " : "Fonte: ") + o.fonte + ". " + o.ajuda;
        else if (o.manual) aj.textContent = "Valor fixado por você. " + o.ajuda;
      }
      l.append(aj); corpo.append(l);
    }
  }

  function maquina() {
    const l = document.createElement("div"); l.className = "opc";
    const rot = document.createElement("label"); rot.textContent = "Este computador";
    const val = document.createElement("span"); val.textContent = "medindo…";
    const b = document.createElement("button"); b.type = "button"; b.className = "auto"; b.textContent = "medir de novo";
    const aj = document.createElement("div"); aj.className = "ajuda";
    aj.textContent = "As estimativas de tempo (e o orçamento) usam a velocidade medida aqui nos núcleos das marchas no tempo: segmento de vórtice, partícula com partícula e segmento com gradiente. Medida uma vez (~0,5 s) e refeita se o processador mudar. Num processador mais lento a mesma análise estima mais segundos e esbarra antes no orçamento.";
    const mostra = m => { val.textContent = `${m.cpu} · ${m.nucleos} threads · ${(m.interacoes_por_s / 1e6).toFixed(0)} M segmentos/s · ${(m.particulas_por_s / 1e6).toFixed(0)} M pares de partículas/s` + (m.medido_em ? ` (${m.medido_em})` : ""); };
    const busca = r => fetch("/api/maquina" + (r ? "?recalibrar=1" : "")).then(x => x.json()).then(mostra).catch(e => { val.textContent = e.message; });
    b.onclick = () => { val.textContent = "medindo…"; busca(true); };
    busca(false);
    l.append(rot, val, b, aj);
    return l;
  }

  async function carrega() { pinta(await (await fetch("/api/configuracao")).json()); }

  document.getElementById("dlg_fechar").onclick = () => dlg.close();
  return {
    abre: async (grupo) => {
      await carrega(); dlg.showModal();
      if (grupo) { const h = corpo.querySelector(`[data-grupo="${grupo}"]`); if (h) h.scrollIntoView({ block: "start" }); }
    },
  };
})();
