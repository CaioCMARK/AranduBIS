"use strict";

const Arquivos = (() => {
  const dlg = document.getElementById("dlg_arquivos");
  const NOMES = { base: "Base de dados", relatorios: "Relatórios", desenhos: "Desenhos" };
  let pasta = "desenhos", sub = "";

  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const tam = n => n == null ? "" : n < 1024 ? n + " B" : n < 1048576 ? (n / 1024).toFixed(0) + " kB" : (n / 1048576).toFixed(1) + " MB";
  const url = (p, c) => `/api/arquivo?pasta=${encodeURIComponent(p)}&caminho=${encodeURIComponent(c)}`;

  function abas() {
    const A = document.getElementById("arq_abas"); A.innerHTML = "";
    Object.entries(NOMES).forEach(([k, n]) => {
      const d = el("div", n, k === pasta ? "at" : ""); d.onclick = () => { pasta = k; sub = ""; carrega(); }; A.append(d);
    });
  }

  async function carrega() {
    abas();
    const C = document.getElementById("arq_corpo"); C.innerHTML = "";
    const r = await fetch(`/api/arquivos?pasta=${pasta}&sub=${encodeURIComponent(sub)}`);
    const d = await r.json();
    if (!r.ok) { C.append(el("div", d.erro, "nota")); const b = el("button", "Abrir configurações"); b.onclick = () => { dlg.close(); Config.abre(); }; C.append(b); return; }
    C.append(el("div", d.raiz + (d.sub ? " / " + d.sub : ""), "nota"));
    const t = document.createElement("table");
    if (d.sub) {
      const tr = document.createElement("tr"), td = el("td", "⬑ subir");
      td.colSpan = 3; td.style.cursor = "pointer";
      td.onclick = () => { sub = d.sub.includes("/") ? d.sub.slice(0, d.sub.lastIndexOf("/")) : ""; carrega(); };
      tr.append(td); t.append(tr);
    }
    d.itens.forEach(i => {
      const tr = document.createElement("tr"), n = el("td", (i.pasta ? "📁 " : "") + i.nome);
      n.style.textAlign = "left"; n.style.cursor = "pointer";
      const acao = el("td");
      if (i.pasta) n.onclick = () => { sub = i.caminho; carrega(); };
      else if (i.nome.toLowerCase().endsWith(".json")) {
        const b = el("button", "Abrir na Geometria");
        b.onclick = async () => {
          try {
            const esq = await (await fetch(url(pasta, i.caminho))).json();
            if (!esq || !Array.isArray(esq.elementos)) { msg("Esse .json não é uma aeronave.", true); return; }
            dlg.close(); carrega_aeronave(esq, i.nome);
          } catch (x) { msg("Arquivo inválido: " + x.message, true); }
        };
        acao.append(b);
        n.onclick = b.onclick;
      } else n.onclick = () => window.open(url(pasta, i.caminho), "_blank", "noopener");
      tr.append(n, el("td", tam(i.tamanho)), acao); t.append(tr);
    });
    C.append(t);
    if (!d.itens.length) C.append(el("div", "Pasta vazia.", "nota"));
  }

  document.getElementById("arq_fechar").onclick = () => dlg.close();
  return { abre: () => { dlg.showModal(); carrega(); } };
})();
