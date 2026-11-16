"use strict";

// Exportação de gráficos e relatório da etapa aberta (2 a 5).
// PDF (A4, uma ou mais páginas) ou imagens JPG/PNG, com resolução e cores à escolha.
// Tudo é gerado no navegador: não há dependência extra nem envio de dados.
const Exporta = (() => {
  const id = x => document.getElementById(x);
  const CHAVE = "aranduBIS.exporta";

  const TEMAS = {
    claro: { nome: "Claro (fundo branco)", fundo: "#ffffff", tinta: "#1b2430", suave: "#5b6675", linha: "#c9cfd8", faixa: "#f0f2f5", cinza: false },
    escuro: { nome: "Escuro (como na tela)", fundo: "#1e252e", tinta: "#e3e8ef", suave: "#98a3b3", linha: "#39424f", faixa: "#252d38", cinza: false },
    cinza: { nome: "Cinza", fundo: "#45494f", tinta: "#e8eaed", suave: "#bcc1c8", linha: "#60656d", faixa: "#4d5158", cinza: false },
    pb: { nome: "Preto e branco (impressão)", fundo: "#ffffff", tinta: "#000000", suave: "#444444", linha: "#bbbbbb", faixa: "#f2f2f2", cinza: true },
  };

  const padrao = { formato: "pdf", tema: "claro", dpi: 150, largura: 1600, qualidade: 90, resumo: true };
  let opc = { ...padrao };
  try { opc = { ...padrao, ...JSON.parse(localStorage.getItem(CHAVE) || "{}") }; } catch (e) { opc = { ...padrao }; }
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(opc)); } catch (e) { /* sem armazenamento */ } };

  // ---------- coleta do que está na tela ----------
  const semAcento = t => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "");
  const slug = t => semAcento(t).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "arquivo";

  function celula(td) {
    const c = td.querySelector("input,select");
    return (c ? c.value : td.textContent).replace(/\s+/g, " ").trim();
  }

  function coletar() {
    const n = document.body.dataset.etapa || "1";
    const ids = { graficos: "graficos" + n, veredito: n === "2" ? "veredito" : "veredito" + n, conteudo: n === "2" ? "conteudo2" : "conteudo" + n };
    const G = id(ids.graficos), V = id(ids.veredito), C = id(ids.conteudo);
    const graficos = G ? [...G.querySelectorAll("svg[role=img]")].map(svg => ({ svg, titulo: svg.getAttribute("aria-label") || "gráfico" })) : [];
    const vis = V && !V.hidden && V.textContent.trim() ? { texto: V.textContent.replace(/\s+/g, " ").trim(), ruim: V.classList.contains("ruim"), ok: V.classList.contains("ok") } : null;
    let tabela = null;
    const T = C && C.querySelector("table");
    if (T) {
      const linhas = [...T.querySelectorAll("tr")].map(tr => [...tr.children].map(celula));
      if (linhas.length > 1) tabela = linhas;
    }
    const sel = [...document.querySelectorAll(".el.sel")].find(e => e.offsetParent !== null);
    const etapa = (document.querySelector(`.etapas [data-etapa="${n}"]`) || {}).textContent || "";
    const aba = [...document.querySelectorAll(".abas .at")].find(e => e.offsetParent !== null);
    return {
      etapa: n, etapaNome: etapa.trim(), analise: sel ? sel.textContent.trim() : "", aba: aba ? aba.textContent.trim() : "",
      aeronave: (id("titulo").textContent || "AranduBIS").replace(/^AranduBIS\s*—\s*/, "").trim() || "aeronave",
      graficos, vis, tabela,
    };
  }

  // ---------- desenho ----------
  const FONTE = "Inter, 'Segoe UI', Arial, sans-serif";

  function svgParaCanvas(svg, tema, largura) {
    return new Promise((ok, falha) => {
      const W = +svg.getAttribute("width"), H = +svg.getAttribute("height");
      const clone = svg.cloneNode(true);
      clone.setAttribute("style", `color:${tema.tinta};font-family:${FONTE}`);
      clone.insertBefore(document.createElementNS("http://www.w3.org/2000/svg", "rect"), clone.firstChild);
      const r = clone.firstChild;
      [["x", 0], ["y", 0], ["width", W], ["height", H], ["fill", tema.fundo]].forEach(([k, v]) => r.setAttribute(k, v));
      const xml = new XMLSerializer().serializeToString(clone);
      const img = new Image();
      img.onload = () => {
        const esc = largura / W;
        const c = document.createElement("canvas");
        c.width = Math.round(W * esc); c.height = Math.round(H * esc);
        const ctx = c.getContext("2d");
        ctx.fillStyle = tema.fundo; ctx.fillRect(0, 0, c.width, c.height);
        ctx.drawImage(img, 0, 0, c.width, c.height);
        ok(c);
      };
      img.onerror = () => falha(new Error("não foi possível desenhar o gráfico"));
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
    });
  }

  function emCinza(c) {
    const ctx = c.getContext("2d"), d = ctx.getImageData(0, 0, c.width, c.height), p = d.data;
    for (let i = 0; i < p.length; i += 4) { const g = 0.299 * p[i] + 0.587 * p[i + 1] + 0.114 * p[i + 2]; p[i] = p[i + 1] = p[i + 2] = g; }
    ctx.putImageData(d, 0, 0);
  }

  const paraBytes = (canvas, tipo, q) => new Promise((ok, falha) => canvas.toBlob(async b => {
    if (!b) return falha(new Error("imagem grande demais para este navegador: reduza a resolução"));
    ok(new Uint8Array(await b.arrayBuffer()));
  }, tipo, q));

  function quebra(ctx, texto, larg) {
    const linhas = []; let atual = "";
    for (const w of texto.split(" ")) {
      const t = atual ? atual + " " + w : w;
      if (ctx.measureText(t).width > larg && atual) { linhas.push(atual); atual = w; } else atual = t;
    }
    if (atual) linhas.push(atual);
    return linhas;
  }

  // ---------- relatório em páginas A4 (coordenadas lógicas de 96 dpi: 794 x 1123) ----------
  const PW = 794, PH = 1123, MG = 48;

  async function paginas(dados, tema, dpi) {
    const esc = dpi / 96;
    const out = [];
    let c, ctx, y;
    const nova = () => {
      c = document.createElement("canvas"); c.width = Math.round(PW * esc); c.height = Math.round(PH * esc);
      ctx = c.getContext("2d"); ctx.scale(esc, esc);
      ctx.fillStyle = tema.fundo; ctx.fillRect(0, 0, PW, PH);
      ctx.textBaseline = "alphabetic";
      out.push(c); y = MG;
    };
    const garante = h => { if (y + h > PH - MG - 14) nova(); };
    nova();

    ctx.fillStyle = tema.tinta; ctx.font = `700 22px ${FONTE}`;
    ctx.fillText("AranduBIS — " + dados.aeronave, MG, y + 18); y += 30;
    ctx.fillStyle = tema.suave; ctx.font = `13px ${FONTE}`;
    const sub = [dados.etapaNome, dados.analise, new Date().toLocaleDateString("pt-BR")].filter(Boolean).join("  ·  ");
    ctx.fillText(sub, MG, y + 12); y += 22;
    ctx.strokeStyle = tema.linha; ctx.beginPath(); ctx.moveTo(MG, y); ctx.lineTo(PW - MG, y); ctx.stroke(); y += 16;

    if (opc.resumo && dados.vis) {
      ctx.font = `13px ${FONTE}`;
      const linhas = quebra(ctx, dados.vis.texto, PW - 2 * MG - 20);
      const h = linhas.length * 18 + 14;
      garante(h);
      ctx.fillStyle = dados.vis.ruim ? "#c85050" : dados.vis.ok ? "#46a05a" : tema.linha;
      ctx.fillRect(MG, y, 5, h);
      ctx.fillStyle = tema.faixa; ctx.fillRect(MG + 5, y, PW - 2 * MG - 5, h);
      ctx.fillStyle = tema.tinta;
      linhas.forEach((l, i) => ctx.fillText(l, MG + 16, y + 20 + i * 18));
      y += h + 16;
    }

    const sel = dados.graficosEscolhidos;
    if (sel.length) {
      const gap = 16, cw = (PW - 2 * MG - gap) / 2;
      for (let i = 0; i < sel.length; i += 2) {
        const par = sel.slice(i, i + 2);
        const imgs = [];
        for (const g of par) imgs.push(await svgParaCanvas(g.svg, tema, Math.round(cw * esc * 1.0)));
        const alt = Math.max(...imgs.map(im => im.height / esc));
        garante(alt + 6);
        imgs.forEach((im, k) => ctx.drawImage(im, MG + k * (cw + gap), y, im.width / esc, im.height / esc));
        y += alt + 12;
      }
    }

    if (opc.resumo && dados.tabela) {
      const todas = dados.tabela, LIM = 400, linhas = todas.slice(0, LIM);
      ctx.font = `11px ${FONTE}`;
      const ncol = Math.max(...linhas.map(l => l.length));
      const largMax = Array.from({ length: ncol }, (_, k) => Math.max(
        ...linhas.slice(1).map(l => ctx.measureText(l[k] || "").width), Math.min(ctx.measureText(linhas[0][k] || "").width, 90)) + 12);
      const total = largMax.reduce((a, b) => a + b, 0), disp = PW - 2 * MG, f = Math.min(1, disp / total);
      const lw = largMax.map(w => w * f);
      const corta = (t, w) => { if (ctx.measureText(t).width <= w - 8) return t; while (t.length > 1 && ctx.measureText(t + "…").width > w - 8) t = t.slice(0, -1); return t + "…"; };
      garante(60);
      ctx.fillStyle = tema.tinta; ctx.font = `700 13px ${FONTE}`; ctx.fillText("Resumo", MG, y + 12); y += 22;
      const linha = (l, i, cab) => {
        let alt = 18, partes = null;
        if (cab) {
          ctx.font = `700 11px ${FONTE}`;
          partes = l.map((t, k) => quebra(ctx, t, lw[k] - 8));
          alt = Math.max(18, Math.max(...partes.map(q => q.length)) * 13 + 6);
          ctx.fillStyle = tema.faixa; ctx.fillRect(MG, y, disp, alt);
        } else if (i % 2 === 0) { ctx.fillStyle = tema.faixa; ctx.globalAlpha = .5; ctx.fillRect(MG, y, disp, 18); ctx.globalAlpha = 1; }
        ctx.fillStyle = tema.tinta; ctx.font = `${cab ? "700 " : ""}11px ${FONTE}`;
        let x = MG;
        l.forEach((t, k) => {
          if (cab) partes[k].forEach((q, j) => ctx.fillText(q, x + 4, y + 13 + j * 13));
          else ctx.fillText(corta(t, lw[k]), x + 4, y + 13);
          x += lw[k];
        });
        y += alt;
      };
      linha(linhas[0], 0, true);
      for (let i = 1; i < linhas.length; i++) {
        if (y + 18 > PH - MG - 14) { nova(); linha(linhas[0], 0, true); }
        linha(linhas[i], i, false);
      }
      if (todas.length > LIM) { ctx.fillStyle = tema.suave; ctx.font = `11px ${FONTE}`; ctx.fillText(`(+${todas.length - LIM} linhas não mostradas)`, MG, y + 14); }
    }

    out.forEach((cv, i) => {
      const g = cv.getContext("2d");
      g.setTransform(esc, 0, 0, esc, 0, 0);
      g.fillStyle = tema.suave; g.font = `10px ${FONTE}`;
      g.fillText(`AranduBIS  ·  página ${i + 1} de ${out.length}`, MG, PH - 26);
      if (tema.cinza) emCinza(cv);
    });
    return out;
  }

  // ---------- empacotamento ----------
  const enc = new TextEncoder();
  const juntar = partes => {
    const n = partes.reduce((s, p) => s + p.length, 0), r = new Uint8Array(n);
    let o = 0; partes.forEach(p => { r.set(p, o); o += p.length; });
    return r;
  };

  function montaPDF(jpegs, dpi) {
    const partes = [], pos = [];
    let tam = 0;
    const add = p => { const b = typeof p === "string" ? enc.encode(p) : p; partes.push(b); tam += b.length; };
    const obj = (n, corpo) => { pos[n] = tam; add(`${n} 0 obj\n`); add(corpo); add("\nendobj\n"); };
    const N = jpegs.length;
    add("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
    obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
    obj(2, `<< /Type /Pages /Kids [${jpegs.map((_, i) => `${3 + i * 3} 0 R`).join(" ")}] /Count ${N} >>`);
    const w = (PW * 72 / 96).toFixed(2), h = (PH * 72 / 96).toFixed(2);
    jpegs.forEach((j, i) => {
      const p = 3 + i * 3, im = p + 1, ct = p + 2;
      obj(p, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /XObject << /Im0 ${im} 0 R >> >> /Contents ${ct} 0 R >>`);
      pos[im] = tam;
      add(`${im} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${j.largura} /Height ${j.altura} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${j.bytes.length} >>\nstream\n`);
      add(j.bytes); add("\nendstream\nendobj\n");
      const cont = `q ${w} 0 0 ${h} 0 0 cm /Im0 Do Q`;
      obj(ct, `<< /Length ${cont.length} >>\nstream\n${cont}\nendstream`);
    });
    const total = 3 + N * 3, xref = tam;
    add(`xref\n0 ${total}\n0000000000 65535 f \n`);
    for (let n = 1; n < total; n++) add(String(pos[n]).padStart(10, "0") + " 00000 n \n");
    add(`trailer\n<< /Size ${total} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
    return new Blob([juntar(partes)], { type: "application/pdf" });
  }

  const TAB_CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = TAB_CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };

  function montaZip(arqs) {
    const d = new Date(), hora = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1), data = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
    const locais = [], central = []; let desloc = 0;
    arqs.forEach(a => {
      const nome = enc.encode(a.nome), crc = crc32(a.dados);
      const lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true);
      lh.setUint16(10, hora, true); lh.setUint16(12, data, true); lh.setUint32(14, crc, true);
      lh.setUint32(18, a.dados.length, true); lh.setUint32(22, a.dados.length, true); lh.setUint16(26, nome.length, true); lh.setUint16(28, 0, true);
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true);
      ch.setUint16(12, hora, true); ch.setUint16(14, data, true); ch.setUint32(16, crc, true);
      ch.setUint32(20, a.dados.length, true); ch.setUint32(24, a.dados.length, true); ch.setUint16(28, nome.length, true); ch.setUint32(42, desloc, true);
      locais.push(new Uint8Array(lh.buffer), nome, a.dados);
      central.push(new Uint8Array(ch.buffer), nome);
      desloc += 30 + nome.length + a.dados.length;
    });
    const cen = juntar(central), fim = new DataView(new ArrayBuffer(22));
    fim.setUint32(0, 0x06054b50, true); fim.setUint16(8, arqs.length, true); fim.setUint16(10, arqs.length, true);
    fim.setUint32(12, cen.length, true); fim.setUint32(16, desloc, true);
    return new Blob([juntar(locais), cen, new Uint8Array(fim.buffer)], { type: "application/zip" });
  }

  function baixa(nome, blob) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = nome; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  // ---------- geração ----------
  async function gera(dados, aviso) {
    const tema = TEMAS[opc.tema] || TEMAS.claro;
    const base = [slug(dados.aeronave), slug(dados.analise || dados.etapaNome)].filter(Boolean).join("_");
    if (opc.formato === "pdf") {
      aviso("Montando as páginas…");
      const cs = await paginas(dados, tema, +opc.dpi);
      const jp = [];
      for (const cv of cs) jp.push({ bytes: await paraBytes(cv, "image/jpeg", opc.qualidade / 100), largura: cv.width, altura: cv.height, cinza: tema.cinza });
      baixa(base + ".pdf", montaPDF(jp, +opc.dpi));
      return `PDF com ${cs.length} página${cs.length > 1 ? "s" : ""} gerado.`;
    }
    const tipo = opc.formato === "png" ? "image/png" : "image/jpeg", ext = opc.formato === "png" ? ".png" : ".jpg";
    const arqs = [], usados = new Set();
    for (const g of dados.graficosEscolhidos) {
      aviso(`Desenhando “${g.titulo}”…`);
      const cv = await svgParaCanvas(g.svg, tema, Math.min(8000, Math.max(300, +opc.largura)));
      if (tema.cinza) emCinza(cv);
      let nome = slug(g.titulo), k = 2; while (usados.has(nome)) nome = slug(g.titulo) + "_" + k++;
      usados.add(nome);
      arqs.push({ nome: `${base}_${nome}${ext}`, dados: await paraBytes(cv, tipo, opc.qualidade / 100) });
    }
    if (arqs.length === 1) { baixa(arqs[0].nome, new Blob([arqs[0].dados], { type: tipo })); return "Imagem gerada."; }
    baixa(base + "_graficos.zip", montaZip(arqs));
    return `${arqs.length} imagens em um arquivo .zip.`;
  }

  // ---------- janela ----------
  let dlg = null;

  function monta() {
    dlg = document.createElement("dialog"); dlg.id = "dlg_exporta";
    dlg.innerHTML = `
      <div class="dlg-topo"><b>Exportar</b><button type="button" id="ex_fechar">Fechar</button></div>
      <div class="ex-corpo">
        <div id="ex_vazio" class="nota" hidden></div>
        <fieldset id="ex_graf"><legend>Gráficos</legend><div id="ex_lista"></div></fieldset>
        <fieldset><legend>Formato</legend>
          <label><input type="radio" name="ex_fmt" value="pdf"> PDF (relatório A4)</label>
          <label><input type="radio" name="ex_fmt" value="jpg"> JPG (uma imagem por gráfico)</label>
          <label><input type="radio" name="ex_fmt" value="png"> PNG (uma imagem por gráfico)</label>
        </fieldset>
        <fieldset><legend>Resolução e cores</legend>
          <div class="ex-grade">
            <label id="ex_l_dpi">Resolução da página</label>
            <select id="ex_dpi"><option value="100">100 dpi (leve)</option><option value="150">150 dpi (padrão)</option><option value="200">200 dpi</option><option value="300">300 dpi (impressão)</option></select>
            <label id="ex_l_larg">Largura da imagem (px)</label>
            <input id="ex_larg" type="number" min="300" max="8000" step="100" list="ex_larg_op">
            <datalist id="ex_larg_op"><option value="800"><option value="1200"><option value="1600"><option value="2400"><option value="3600"><option value="5000"></datalist>
            <label>Cores</label>
            <select id="ex_tema"></select>
            <label id="ex_l_q">Qualidade JPEG</label>
            <input id="ex_q" type="range" min="50" max="100" step="5">
          </div>
          <div id="ex_dica" class="nota"></div>
        </fieldset>
        <label id="ex_l_resumo"><input type="checkbox" id="ex_resumo"> Incluir faixa de resultado e tabela de resumo (PDF)</label>
        <div class="ex-rodape"><span id="ex_msg" class="nota"></span><button type="button" id="ex_ok">Exportar</button></div>
        <fieldset id="ex_anim"><legend>Animação dos modos de vibração</legend>
          <div class="ex-grade">
            <label>Formato</label><select id="ex_a_fmt"><option value="mp4">MP4 (recomendado)</option><option value="gif">GIF</option></select>
            <label id="ex_a_l_codec">Codec</label><select id="ex_a_codec"><option value="h264">H.264 (abre em qualquer lugar)</option><option value="h265">H.265 (menor, nem todo player abre)</option></select>
            <label>Largura (px)</label><select id="ex_a_larg"><option value="1280">1280 (HD)</option><option value="1920">1920 (Full HD)</option><option value="1080">1080</option><option value="720">720 (leve)</option></select>
            <label>Quadros por segundo</label><select id="ex_a_fps"><option value="24">24</option><option value="30">30</option><option value="60">60</option></select>
          </div>
          <div class="ex-rodape"><span id="ex_a_msg" class="nota"></span><button type="button" id="ex_a_ok">Gerar animação</button></div>
        </fieldset>
        <fieldset id="ex_geo"><legend>Geometria para fabricação e outros programas</legend>
          <label><input type="checkbox" id="ex_g_dat" checked> Perfis de cada seção (.dat, formato Selig)</label>
          <label><input type="checkbox" id="ex_g_dxf" checked> Nervuras em tamanho real com recortes das longarinas (.dxf, mm)</label>
          <label><input type="checkbox" id="ex_g_csv"> Nervuras em tabela (.csv, mm)</label>
          <label><input type="checkbox" id="ex_g_avl"> Arquivo do AVL (.avl, com os .dat que ele usa)</label>
          <label><input type="checkbox" id="ex_g_montagem"> Folha de montagem (.pdf): peças, massas, posição das nervuras e das faixas de chapeado</label>
          <label><input type="checkbox" id="ex_g_stl_fechado"> Forma externa fechada (.stl, mm): para impressão 3D ou CAD</label>
          <label><input type="checkbox" id="ex_g_stl_esqueleto"> Esqueleto com a estrutura interna (.stl, mm): nervuras, longarinas e treliças</label>
          <div class="ex-rodape"><span id="ex_g_msg" class="nota"></span><button type="button" id="ex_g_ok">Baixar geometria (.zip)</button></div>
        </fieldset>
      </div>`;
    document.body.append(dlg);
    const T = id("ex_tema"); Object.entries(TEMAS).forEach(([k, t]) => T.add(new Option(t.nome, k)));
    id("ex_fechar").onclick = () => dlg.close();
    const le = () => {
      opc.formato = (dlg.querySelector("input[name=ex_fmt]:checked") || {}).value || "pdf";
      opc.dpi = +id("ex_dpi").value; opc.largura = Math.min(8000, Math.max(300, +id("ex_larg").value || 1600));
      opc.tema = T.value; opc.qualidade = +id("ex_q").value; opc.resumo = id("ex_resumo").checked;
      guarda(); mostraCampos();
    };
    dlg.addEventListener("change", le);
    id("ex_ok").onclick = executa;
    id("ex_g_ok").onclick = geometria;
    id("ex_a_ok").onclick = animacao;
    id("ex_a_fmt").onchange = () => { id("ex_a_codec").hidden = id("ex_a_l_codec").hidden = id("ex_a_fmt").value !== "mp4"; };
  }

  async function animacao() {
    const m = t => { id("ex_a_msg").textContent = t; };
    if (typeof esq === "undefined" || !esq || !(esq.elementos || []).length) { m("Abra ou desenhe uma aeronave na etapa 1."); return; }
    const corpo = { esquema: esq, Vd: Padroes.get("estrutura.V_d"), formato: id("ex_a_fmt").value, codec: id("ex_a_codec").value,
                    largura: +id("ex_a_larg").value, fps: +id("ex_a_fps").value, n_modos: 3 };
    id("ex_a_ok").disabled = true; m("Renderizando (pode levar um ou dois minutos)…");
    try {
      const r = await fetch("/api/anima/modos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.erro || "falhou"); }
      const blob = await r.blob();
      baixa(slug(esq.nome || "aeronave") + "_modos." + (corpo.formato === "gif" ? "gif" : "mp4"), blob);
      m(`Pronto: ${(blob.size / 1e6).toFixed(1).replace(".", ",")} MB.`);
    } catch (e) { m("Erro: " + e.message); }
    id("ex_a_ok").disabled = false;
  }

  async function geometria() {
    const m = t => { id("ex_g_msg").textContent = t; };
    if (typeof esq === "undefined" || !esq || !(esq.elementos || []).length) { m("Abra ou desenhe uma aeronave na etapa 1."); return; }
    const formatos = ["dat", "dxf", "csv", "avl", "montagem", "stl_fechado", "stl_esqueleto"].filter(f => id("ex_g_" + f).checked);
    if (!formatos.length) { m("Marque pelo menos um formato."); return; }
    id("ex_g_ok").disabled = true; m("Gerando…");
    try {
      const r = await chama("/api/exporta/fabricacao", { esquema: esq, formatos });
      const arqs = r.arquivos.map(a => ({ nome: a.nome, dados: a.base64 ? Uint8Array.from(atob(a.base64), c => c.charCodeAt(0)) : enc.encode(a.texto) }));
      baixa(slug(esq.nome || "aeronave") + "_geometria.zip", montaZip(arqs));
      m(`${arqs.length} arquivos.` + (r.avisos.length ? " Avisos: " + r.avisos.join("; ") + "." : ""));
    } catch (e) { m("Erro: " + e.message); }
    id("ex_g_ok").disabled = false;
  }

  function mostraCampos() {
    const pdf = opc.formato === "pdf", png = opc.formato === "png";
    id("ex_l_dpi").hidden = id("ex_dpi").hidden = !pdf;
    id("ex_l_larg").hidden = id("ex_larg").hidden = pdf;
    id("ex_l_q").hidden = id("ex_q").hidden = png;
    id("ex_l_resumo").hidden = !pdf;
    id("ex_dica").textContent = opc.tema === "pb"
      ? "Preto e branco converte as cores em tons de cinza: séries de cores parecidas podem ficar difíceis de distinguir."
      : pdf ? "Páginas A4 em JPEG embutido no PDF. 150 dpi serve para tela e impressão comum; 300 dpi para impressão fina."
            : `A imagem sai com ${opc.largura} px de largura (cerca de ${(opc.largura / 300 * 2.54).toFixed(1)} cm a 300 dpi).`;
  }

  let dados = null;

  function abre() {
    if (!dlg) monta();
    dados = coletar();
    const vazio = id("ex_vazio"), tem = dados.graficos.length > 0 || dados.tabela;
    vazio.hidden = !!tem;
    if (!tem) vazio.textContent = dados.etapa === "1"
      ? "A etapa 1 não tem gráficos nem tabela de resultados: abra uma análise nas etapas 2 a 5 para exportá-los. A animação dos modos e a geometria (perfis, nervuras, AVL) saem pelos quadros abaixo."
      : "Esta tela ainda não tem resultados para exportar: rode a análise primeiro.";
    const L = id("ex_lista"); L.innerHTML = "";
    dados.graficos.forEach((g, i) => {
      const l = document.createElement("label"); l.style.display = "block";
      const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = true; cb.dataset.i = i;
      l.append(cb, " " + g.titulo); L.append(l);
    });
    if (!dados.graficos.length) L.textContent = "Nenhum gráfico nesta tela.";
    dlg.querySelector(`input[name=ex_fmt][value=${opc.formato}]`).checked = true;
    id("ex_dpi").value = String(opc.dpi); id("ex_larg").value = opc.largura; id("ex_tema").value = opc.tema;
    id("ex_q").value = opc.qualidade; id("ex_resumo").checked = opc.resumo;
    id("ex_msg").textContent = ""; id("ex_ok").disabled = !tem; id("ex_g_msg").textContent = ""; id("ex_a_msg").textContent = "";
    mostraCampos();
    dlg.showModal();
  }

  async function executa() {
    const aviso = t => { id("ex_msg").textContent = t; };
    dados.graficosEscolhidos = [...id("ex_lista").querySelectorAll("input:checked")].map(cb => dados.graficos[+cb.dataset.i]);
    if (opc.formato !== "pdf" && !dados.graficosEscolhidos.length) { aviso("Marque pelo menos um gráfico."); return; }
    if (opc.formato === "pdf" && !dados.graficosEscolhidos.length && !(opc.resumo && (dados.vis || dados.tabela))) { aviso("Nada marcado para o PDF."); return; }
    id("ex_ok").disabled = true;
    try { aviso(await gera(dados, aviso)); } catch (e) { aviso("Erro: " + e.message); }
    id("ex_ok").disabled = false;
  }

  const b = id("b_exporta");
  if (b) b.onclick = abre;
  return { abre, coletar, paginas, montaPDF, montaZip, TEMAS };
})();
