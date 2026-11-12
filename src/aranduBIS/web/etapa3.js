"use strict";

const Etapa3 = (() => {
  const ITENS = [["cargas", "Cargas (V-n e envergadura)"], ["asa", "Asa: longarina e chapeado"], ["torcao", "Torção e reversão de comando"], ["flutter", "Flutter e vibração (GVT)"], ["flambagem", "Nervuras e flambagem do chapeado"], ["cauda", "Cauda e treliça (elementos finitos)"], ["trem", "Trem de pouso (pouso e taxi)"], ["massa", "Massa, CG e inércias"]];
  const MODULOS = {};
  let ativo = "cargas";

  function lista() {
    const L = $("lista3"); L.innerHTML = "";
    ITENS.forEach(([k, n]) => {
      const d = Object.assign(document.createElement("div"), { className: "el" + (k === ativo ? " sel" : ""), textContent: n });
      d.onclick = () => { ativo = k; lista(); pinta(); };
      L.append(d);
    });
  }

  function pinta() { $("veredito3").hidden = true; $("graficos3").innerHTML = ""; $("conteudo3").innerHTML = ""; MODULOS[ativo].pinta(); }

  return {
    registra(nome, m) { MODULOS[nome] = m; },
    entra() { lista(); pinta(); },
    nome: () => ativo,
    ativa: () => document.body.dataset.etapa === "3",
  };
})();
