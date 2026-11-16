"use strict";

const Manual = (() => {
  const TOPICOS = [
    ["comecar", "Como usar estes manuais"],
    ["interface", "Interface: ferramentas, atalhos e editores"],
    ["discretizacao", "Discretização e convergência"],
    ["vlm", "VLM: malha de vórtices"],
    ["uvlm", "UVLM: aerodinâmica no tempo"],
    ["helice", "Hélice: BEMT e sopro"],
    ["estrutura", "Viga da asa: flexão e torção"],
    ["flutter", "Flutter e vibração"],
    ["laboratorio", "Laboratório de configurações"],
    ["fabricacao", "Fabricação: nervuras, planificação e STL"],
    ["chapeado", "Chapeado em casca (CalculiX)"],
    ["cauda", "Treliças em elementos finitos"],
    ["verificacao", "Verificar e validar"],
  ];
  const dlg = $("dlg_manual"), L = $("manual_lista"), T = $("manual_texto");
  let atual = "comecar";
  const cache = {};

  const esc = t => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  function inline(t) {
    return esc(t).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
      .replace(/\[([^\]]+)\]\(#([a-z_]+)\)/g, '<a href="#" data-topico="$2">$1</a>');
  }
  function md(txt) {
    const out = [], ls = txt.replace(/\r/g, "").split("\n");
    let i = 0;
    while (i < ls.length) {
      const l = ls[i];
      if (/^```/.test(l)) { const b = []; i++; while (i < ls.length && !/^```/.test(ls[i])) b.push(ls[i++]); i++; out.push(`<pre class="eq">${esc(b.join("\n"))}</pre>`); continue; }
      const h = l.match(/^(#{1,3})\s+(.*)/); if (h) { out.push(`<h${h[1].length + 2}>${inline(h[2])}</h${h[1].length + 2}>`); i++; continue; }
      if (/^\|/.test(l)) {
        const rows = []; while (i < ls.length && /^\|/.test(ls[i])) rows.push(ls[i++]);
        const cel = r => r.replace(/^\||\|$/g, "").split("|").map(c => inline(c.trim()));
        const corpo = rows.filter((r, k) => !(k === 1 && /^\|[\s:|-]+\|$/.test(r)));
        out.push("<table>" + corpo.map((r, k) => "<tr>" + cel(r).map(c => k ? `<td>${c}</td>` : `<th>${c}</th>`).join("") + "</tr>").join("") + "</table>");
        continue;
      }
      if (/^\s*[-*]\s+/.test(l) || /^\s*\d+\.\s+/.test(l)) {
        const ord = /^\s*\d+\./.test(l), it = [];
        while (i < ls.length && (/^\s*[-*]\s+/.test(ls[i]) || /^\s*\d+\.\s+/.test(ls[i]) || (/^\s{2,}\S/.test(ls[i]) && it.length))) {
          if (/^\s{2,}\S/.test(ls[i]) && !/^\s*([-*]|\d+\.)\s+/.test(ls[i])) it[it.length - 1] += " " + ls[i].trim();
          else it.push(ls[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
          i++;
        }
        out.push(`<${ord ? "ol" : "ul"}>` + it.map(x => `<li>${inline(x)}</li>`).join("") + `</${ord ? "ol" : "ul"}>`);
        continue;
      }
      if (/^>\s?/.test(l)) { const b = []; while (i < ls.length && /^>\s?/.test(ls[i])) b.push(ls[i++].replace(/^>\s?/, "")); out.push(`<blockquote>${inline(b.join(" "))}</blockquote>`); continue; }
      if (!l.trim()) { i++; continue; }
      const p = []; while (i < ls.length && ls[i].trim() && !/^(#|```|\||>|\s*[-*]\s|\s*\d+\.\s)/.test(ls[i])) p.push(ls[i++]);
      out.push(`<p>${inline(p.join(" "))}</p>`);
    }
    return out.join("\n");
  }

  function lista() {
    L.innerHTML = "";
    TOPICOS.forEach(([k, n]) => {
      const d = Object.assign(document.createElement("div"), { className: "el" + (k === atual ? " sel" : ""), textContent: n });
      d.onclick = () => mostra(k); L.append(d);
    });
  }

  async function mostra(k) {
    atual = k; lista();
    try {
      if (!cache[k]) { const r = await fetch(`/web/manuais/${k}.md`); if (!r.ok) throw new Error("manual não encontrado"); cache[k] = await r.text(); }
      T.innerHTML = md(cache[k]);
    } catch (e) { T.textContent = e.message; }
    T.scrollTop = 0;
    T.querySelectorAll("a[data-topico]").forEach(a => { a.onclick = ev => { ev.preventDefault(); mostra(a.dataset.topico); }; });
  }

  async function abre(k) { if (!dlg.open) dlg.showModal(); await mostra(k || atual); }
  $("manual_fechar").onclick = () => dlg.close();
  $("b_manual").onclick = () => abre();
  return { abre, md, TOPICOS };
})();

const Malha = (() => {
  const dlg = $("dlg_malha"), A = $("malha_abas"), C = $("malha_corpo"), R = $("r_malha");
  const NOMES = { "/api/equilibrio": "Equilíbrio", "/api/cargas": "Cargas", "/api/limites": "Limites", "/api/decolagem": "Decolagem",
    "/api/aeroelastica": "Aeroelasticidade", "/api/torcao": "Torção", "/api/flutter": "Flutter", "/api/uvlm": "UVLM", "/api/chapeado_fe": "Chapeado FE",
    "/api/torcao_fe": "Torção FE", "/api/asa": "Asa", "/api/dinamica": "Dinâmica", "/api/controle": "Controle", "/api/massa_asa": "Massa da asa" };
  const MANUAL_DA_AREA = { "VLM": "vlm", "Estrutura": "estrutura", "Flutter": "flutter", "Chapeado (CalculiX)": "chapeado", "Asa em casca": "chapeado" };
  const reg = new Map();
  let ultima = null, conv = null;

  function registra(url, d) {
    if (!d || url.includes("/convergencia/") || (!d.discretizacao_usada && !d.avisos_discretizacao)) return;
    const nome = NOMES[url] || url.replace("/api/", "");
    reg.set(nome, { usadas: d.discretizacao_usada || [], avisos: d.avisos_discretizacao || [], quando: new Date() });
    ultima = nome; rodape();
    if (dlg.open) pinta();
  }

  function rodape() {
    const r = reg.get(ultima); if (!r) return;
    const eq = r.usadas.filter(u => u.origem === "usuario").length;
    R.textContent = `malha: ${eq ? eq + " fixado" + (eq > 1 ? "s" : "") + " manualmente" : "automática"}` + (r.avisos.length ? ` · ${r.avisos.length} aviso${r.avisos.length > 1 ? "s" : ""}` : "");
    R.classList.toggle("alerta", r.avisos.length > 0);
  }

  function pinta() {
    A.innerHTML = ""; C.innerHTML = "";
    if (!reg.size) { C.append(Object.assign(document.createElement("div"), { className: "nota", textContent: "Nenhuma análise rodou ainda nesta sessão." })); return; }
    [...reg.keys()].forEach(k => { const d = Object.assign(document.createElement("div"), { textContent: k, className: k === ultima ? "at" : "" }); d.onclick = () => { ultima = k; pinta(); rodape(); }; A.append(d); });
    const r = reg.get(ultima);
    if (r.avisos.length) {
      const h = Object.assign(document.createElement("h5"), { textContent: "Avisos de geometria e de malha" }); C.append(h);
      r.avisos.forEach(a => C.append(Object.assign(document.createElement("div"), { className: "aviso", textContent: a })));
    }
    if (r.usadas.length) {
      const t = document.createElement("table");
      t.innerHTML = "<tr><th>área</th><th>item</th><th>valor</th><th>origem</th><th>por quê</th></tr>" + r.usadas.map(u =>
        `<tr><td>${u.area}</td><td>${u.rotulo}</td><td>${typeof u.valor === "number" ? fmt(u.valor, 4) : u.valor}</td><td>${u.origem === "usuario" ? "<b>manual</b>" : "auto"}</td><td>${u.motivo}</td></tr>`).join("");
      C.append(t);
      const areas = [...new Set(r.usadas.map(u => u.area))].filter(a => MANUAL_DA_AREA[a]);
      const n = Object.assign(document.createElement("div"), { className: "nota" });
      n.innerHTML = "“auto” segue uma regra de convergência medida; “manual” foi fixado em Configurações → Discretização. Teoria: "
        + areas.map(a => `<a href="#" data-m="${MANUAL_DA_AREA[a]}">${a}</a>`).join(", ") + (areas.length ? ", " : "")
        + '<a href="#" data-m="discretizacao">discretização e convergência</a>.';
      n.querySelectorAll("a").forEach(x => { x.onclick = ev => { ev.preventDefault(); Manual.abre(x.dataset.m); }; });
      C.append(n);
    }
    if (r.usadas.some(u => u.area === "VLM")) {
      const b = Object.assign(document.createElement("button"), { textContent: "Testar convergência do VLM (meia malha, malha atual, malha dobrada)" });
      b.onclick = testa; C.append(b);
      if (conv) C.append(tabelaConv(conv));
    }
  }

  async function testa() {
    if (!esq || !esq.elementos.length) return;
    conv = { calculando: true }; pinta();
    try { conv = await chama("/api/convergencia/vlm", { esquema: esq, rho: +Padroes.get("analise.rho") || 1.1 }); }
    catch (e) { conv = { erro: e.message }; }
    pinta();
  }

  function tabelaConv(c) {
    const d = document.createElement("div");
    if (c.calculando) { d.className = "nota"; d.textContent = "Rodando o VLM em cinco malhas (a mais fina tem o dobro de painéis na corda: pode levar meio minuto)…"; return d; }
    if (c.erro) { d.className = "aviso"; d.textContent = c.erro; return d; }
    for (const f of c.familias) {
      const t = document.createElement("table");
      t.innerHTML = `<tr><th colspan="${f.malhas.length + 4}">${f.nome}</th></tr><tr><th>grandeza</th>` + f.malhas.map(m => `<th>${m}</th>`).join("")
        + "<th>extrapolado (Richardson)</th><th>ordem p</th><th>GCI da malha atual</th></tr>"
        + f.grandezas.map(g => `<tr><td>${g.nome}</td>` + g.valores.map(v => `<td>${fmt(v, 5)}</td>`).join("")
          + `<td>${g.extrapolado == null ? "—" : fmt(g.extrapolado, 5)}</td><td>${g.p == null ? "—" : fmt(g.p, 2)}</td>`
          + `<td class="${g.gci != null && g.gci > 0.02 ? "ruim" : ""}">${g.gci == null ? (g.nota || "—") : fmt(100 * g.gci, 2) + " %"}</td></tr>`).join("");
      d.append(t);
    }
    d.append(Object.assign(document.createElement("div"), { className: "nota", textContent: c.nota }));
    return d;
  }

  R.onclick = () => { pinta(); dlg.showModal(); };
  $("malha_fechar").onclick = () => dlg.close();
  $("malha_cfg").onclick = () => { dlg.close(); Config.abre("Discretização"); };
  $("malha_manual").onclick = () => Manual.abre("discretizacao");
  return { registra };
})();
