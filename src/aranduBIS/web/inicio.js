"use strict";

const Inicio = (() => {
  const VISTO = "aranduBIS.inicio.visto", DICA = "aranduBIS.dica.oculta";
  const ETAPAS = [
    [1, "Geometria", "Monte ou abra a aeronave: asas, cauda, fuselagem, motor e massas. Clique numa seção da asa na vista 3D para editar o perfil daquela estação."],
    [2, "Análise", "Veja como a aeronave voa. Comece por Equilíbrio e estabilidade, depois hélice, decolagem e pontuação."],
    [3, "Estrutura", "Confira se a estrutura aguenta. Comece por Cargas, depois Asa (longarina e chapeado) e as demais verificações."],
    [4, "Otimizar", "Escolha as variáveis, as restrições e a regra de pontuação e deixe o programa buscar a melhor configuração."],
    [5, "Resultados", "Compare os melhores projetos encontrados e leve o escolhido de volta para a Geometria."],
  ];
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const ler = c => { try { return localStorage.getItem(c); } catch (e) { return null; } };
  const gravar = (c, v) => { try { localStorage.setItem(c, v); } catch (e) { } };

  const dlg = el("dialog");
  dlg.id = "dlg_inicio";
  function monta() {
    dlg.innerHTML = "";
    const topo = el("div", "", "dlg-topo"); topo.append(el("b", "Primeiros passos"));
    const f = el("button", "Fechar"); f.onclick = () => dlg.close(); topo.append(f);
    const c = el("div", "", "inicio");
    c.append(el("p", "O AranduBIS reúne modelagem da aeronave, análises de voo, verificação estrutural e otimização em um só lugar. O caminho mais curto: abra um exemplo, percorra as cinco etapas na ordem e, antes de confiar num número, leia o manual da análise (botão Boas práticas)."));
    const ol = el("ol", "", "roteiro");
    ETAPAS.forEach(([n, nome, txt]) => {
      const li = el("li"); li.append(el("b", `${n} ${nome}`), el("span", txt));
      li.title = `Ir para ${n} ${nome}`;
      li.onclick = () => { dlg.close(); const d = document.querySelector(`.etapas div[data-etapa="${n}"]`); if (d) d.click(); };
      ol.append(li);
    });
    c.append(ol);
    const bs = el("div", "", "inicio-botoes");
    const b1 = el("button", "Explorar um exemplo", "primario");
    b1.title = "Abre o biplano de exemplo, com estrutura completa";
    b1.onclick = async () => {
      dlg.close();
      try {
        const lista = (await chama("/api/exemplos")).exemplos, n = lista.find(x => x.endsWith("biplano_a.json")) || lista[0];
        if (n) carrega(await chama("/api/exemplo?nome=" + encodeURIComponent(n)), n);
        const d = document.querySelector('.etapas div[data-etapa="1"]'); if (d) d.click();
      } catch (x) { msg(x.message, true); }
    };
    const b2 = el("button", "Começar uma aeronave nova"); b2.onclick = () => { dlg.close(); $("b_novo").click(); };
    const b3 = el("button", "Ler o guia"); b3.onclick = () => { dlg.close(); if (typeof Manual !== "undefined") Manual.abre("comecar"); };
    bs.append(b1, b2, b3); c.append(bs);
    c.append(el("div", "Para abrir esta janela de novo, use Primeiros passos no menu Ajuda (na interface clássica, o botão da barra superior). A tecla ? lista os atalhos e Ctrl+K procura qualquer comando.", "nota"));
    dlg.append(topo, c);
  }
  document.body.append(dlg);

  function abre() { monta(); if (!dlg.open) dlg.showModal(); gravar(VISTO, "1"); }

  const faixa = el("div", "", "dica-etapa");
  function dica() {
    const n = +document.body.dataset.etapa || 1;
    faixa.innerHTML = "";
    if (ler(DICA) === "1") { faixa.hidden = true; return; }
    faixa.hidden = false;
    const [, nome, txt] = ETAPAS[n - 1];
    faixa.append(el("b", `${n} ${nome}: `), el("span", txt));
    if (n < 5) {
      const p = el("button", `Próxima: ${ETAPAS[n][0]} ${ETAPAS[n][1]} →`); p.onclick = () => document.querySelector(`.etapas div[data-etapa="${n + 1}"]`).click();
      faixa.append(p);
    }
    const x = el("button", "✕", "fecha-dica"); x.title = "Ocultar as dicas (volte a mostrá-las em Primeiros passos)"; x.onclick = () => { gravar(DICA, "1"); dica(); };
    faixa.append(x);
  }
  const barra = document.querySelector(".etapas");
  barra.after(faixa);
  new MutationObserver(dica).observe(document.body, { attributes: true, attributeFilter: ["data-etapa"] });
  dica();

  const b = el("button", "Primeiros passos"); b.id = "b_inicio"; b.title = "Roteiro das cinco etapas e atalhos para começar";
  b.onclick = () => { gravar(DICA, "0"); dica(); abre(); };
  const ref = $("b_manual"); ref.before(b);

  if (ler(VISTO) !== "1") setTimeout(abre, 400);
  return { abre };
})();
