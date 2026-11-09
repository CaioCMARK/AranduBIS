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
      w = document.createElement("input"); w.type = "number"; w.value = o.valor;
      w.min = o.minimo; w.max = o.maximo; w.step = "any";
      w.onchange = () => envia({ [o.chave]: parseFloat(w.value) });
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
      if (o.grupo !== grupo) {
        grupo = o.grupo;
        const h = document.createElement("div"); h.className = "grupo"; h.textContent = grupo; corpo.append(h);
      }
      const l = document.createElement("div");
      l.className = "opc" + (o.ativa ? "" : " inerte");
      const rot = document.createElement("label");
      rot.textContent = o.rotulo; rot.htmlFor = "cfg_" + o.chave;
      const w = campo(o);
      w.disabled = !o.ativa;
      const aj = document.createElement("div"); aj.className = "ajuda"; aj.textContent = o.ajuda;
      l.append(rot, w, aj); corpo.append(l);
    }
  }

  async function carrega() { pinta(await (await fetch("/api/configuracao")).json()); }

  document.getElementById("dlg_fechar").onclick = () => dlg.close();
  return { abre: async () => { await carrega(); dlg.showModal(); } };
})();
