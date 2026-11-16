"use strict";

const Etapa3 = (() => {
  const ITENS = [["cargas", "Cargas (V-n e envergadura)"], ["asa", "Asa: longarina e chapeado"], ["torcao", "Torção e reversão de comando"], ["massa_asa", "Massa da asa (real, por estação)"], ["flambagem", "Nervuras e flambagem do chapeado"], ["nervuras_dxf", "Nervuras para corte a laser (DXF)"], ["planificacao", "Chapeado planificado (faixas planas)"], ["flutter", "Flutter e vibração (GVT)"], ["aeroelastica", "Aeroelasticidade estática (VLM + torção)"], ["uvlm", "Aerodinâmica não estacionária (UVLM: rajada, Wagner)"], ["calibracao", "Calibração com ensaio (GVT e estáticos)"], ["juncao", "Junção asa–treliça (solda × parafuso)"], ["cauda", "Cauda e treliça (elementos finitos)"], ["vibracao", "Vibração da cauda e do motor"], ["trem", "Trem de pouso (pouso e taxi)"], ["pouso_din", "Pouso e taxi dinâmicos (no tempo)"], ["massa", "Massa, CG e inércias"]];
  const GRUPOS = { cargas: "Asa", asa: "Asa", torcao: "Asa", massa_asa: "Asa", flambagem: "Asa", nervuras_dxf: "Asa", planificacao: "Asa", flutter: "Aeroelasticidade e vibração", aeroelastica: "Aeroelasticidade e vibração", uvlm: "Aeroelasticidade e vibração", calibracao: "Aeroelasticidade e vibração", juncao: "Cauda e motor", cauda: "Cauda e motor", vibracao: "Cauda e motor", trem: "Trem de pouso", pouso_din: "Trem de pouso", massa: "Massa" };
  const DESCR = {
    cargas: "Fator de carga e esforços ao longo da envergadura. Comece por aqui.",
    asa: "Dimensiona a longarina e o chapeado, com as margens de segurança.",
    torcao: "Rigidez à torção e reversão de comando.",
    massa_asa: "Massa real da asa em cada estação.",
    flambagem: "Flambagem do chapeado e nervuras necessárias.",
    nervuras_dxf: "Nervuras planas prontas para corte a laser (DXF).",
    planificacao: "Desdobra o chapeado em faixas planas e mostra onde ele aceita ou não a curvatura.",
    flutter: "Velocidade crítica de flutter da semi-asa.",
    aeroelastica: "Divergência e reversão com a asa flexível.",
    uvlm: "Resposta no tempo a rajada e a comando.",
    calibracao: "Ajusta o modelo com ensaios (GVT e estáticos).",
    juncao: "Compara prender a asa na treliça por solda, parafuso ou rótula.",
    cauda: "Treliça da cauda em elementos finitos.",
    vibracao: "Modos da cauda e do motor contra a rotação da hélice.",
    trem: "Esforços e margens do trem de pouso.",
    pouso_din: "Pouso e táxi simulados no tempo.",
    massa: "Massa, CG e inércias do conjunto.",
  };
  const COMO_LER = {
    cargas: "Três gráficos ao longo da envergadura da semi-asa: o diagrama V-n (fator de carga contra velocidade, com os limites de manobra e de rajada), o esforço cortante e o momento fletor (o que a viga precisa aguentar em cada posição) e a carga por metro. Os valores crescem na raiz, onde a asa se prende.",
    asa: "Mostra como a viga da asa responde à carga limite: a flecha (quanto a ponta sobe), a rigidez de flexão EI ao longo da asa, a tensão nas mesas ou no tubo e a margem de segurança por estação. A margem é em porcentagem: negativa significa que o limite é ultrapassado; quanto maior, mais folga.",
    torcao: "Mostra como a asa torce sob carga: a torção em cada estação (positivo = bordo de ataque para cima), a rigidez de torção GJ, a posição do eixo elástico em relação ao centro aerodinâmico e a efetividade do aileron (quanto do comando sobra com a asa flexível).",
    massa_asa: "Reparte a massa da asa por estação: massa por metro de envergadura, posição do centro de massa na corda local e raio de giração. Serve para conferir o balanço de massa usado no flutter.",
    flambagem: "Compara a tensão no chapeado com a tensão crítica de flambagem em cada painel entre nervuras. A margem é em porcentagem: negativa indica painel que flamba. O gráfico de vão mostra como a margem melhora ao aproximar as nervuras.",
    nervuras_dxf: "Mostra as nervuras já arrumadas nas chapas, em tamanho real (milímetros). Cada contorno é uma peça; os círculos são furos de tubos e alívios. O arquivo DXF tem as mesmas peças para o corte a laser.",
    planificacao: "Três painéis: onde estão as faixas de chapeado na asa vista de cima, as peças arrumadas nas chapas e a faixa escolhida desdobrada, com as cores indicando quanto cada ponto precisaria esticar ou encolher para assentar.",
    flutter: "Mostra o amortecimento dos modos em função da velocidade. Enquanto o amortecimento é positivo, o modo se acalma; quando cruza zero, começa o flutter. A velocidade desse cruzamento tem que ficar acima da máxima de voo com folga.",
    aeroelastica: "Mostra a asa flexível sob carga: a torção elástica por estação e a sustentação por metro. Se a torção aumenta a sustentação, a asa tende à divergência; se diminui, o comando perde efetividade.",
    uvlm: "Mostra a resposta no tempo a uma rajada, a um comando ou ao solo: o coeficiente de sustentação, o de momento, a esteira vista de lado e, quando há hélice, a tração. A escala de tempo está no eixo horizontal.",
    calibracao: "Compara os modos de vibração medidos em ensaio com os do modelo e mostra os ajustes de rigidez e massa que aproximam os dois.",
    juncao: "Compara a mesma asa presa à treliça por juntas diferentes: a deformada da asa, o momento fletor na longarina, o momento que passa para a treliça em cada ponto de ligação e a menor margem das barras. A solda é a referência; as outras linhas mostram quanto cada junta alivia a ligação e quanto a asa cede a mais.",
    cauda: "Mostra a treliça da cauda sob carga limite: o deslocamento vertical, a torção em torno do eixo e a menor margem de segurança por trecho. Margem negativa indica barra que rompe na carga de ruptura.",
    vibracao: "Mostra as frequências dos modos contra a rotação do motor e da hélice (diagrama de Campbell). Onde uma linha de excitação cruza um modo há ressonância; a tabela indica a velocidade de voo em que isso ocorre.",
    trem: "Mostra as reações em cada roda e a margem das barras mais críticas do trem de pouso em cada caso de carga.",
    pouso_din: "Simula o pouso e o táxi no tempo: arfagem, compressão do trem, reação do solo (em múltiplos do peso) e o fator de carga contra a razão de descida.",
    massa: "Soma as massas da aeronave: o centro de gravidade contra a massa da estrutura desenhada e a massa por grupo de componentes. A parte não modelada entra pelo valor que você informar.",
  };
  const MODULOS = {};
  // manual de boas práticas de cada vista
  const MANUAL = { nervuras_dxf: "fabricacao", planificacao: "fabricacao", cargas: "vlm", asa: "estrutura", torcao: "estrutura", massa_asa: "flutter", flutter: "flutter", aeroelastica: "vlm",
                   uvlm: "uvlm", calibracao: "verificacao", flambagem: "chapeado", juncao: "cauda", cauda: "cauda", trem: "cauda", pouso_din: "verificacao", massa: "verificacao" };
  let ativo = "cargas";

  function lista() {
    const L = $("lista3"); L.innerHTML = "";
    let grupo = null;
    ITENS.forEach(([k, n]) => {
      if (GRUPOS[k] !== grupo) { grupo = GRUPOS[k]; L.append(Object.assign(document.createElement("div"), { className: "grupo-lista", textContent: grupo })); }
      const d = Object.assign(document.createElement("div"), { className: "el com-desc" + (k === ativo ? " sel" : "") });
      const tx = document.createElement("span"); tx.className = "tx"; tx.append(n);
      if (DESCR[k]) { const s = document.createElement("small"); s.className = "desc"; s.textContent = DESCR[k]; tx.append(s); d.title = DESCR[k]; }
      d.append(tx);
      d.onclick = () => { ativo = k; lista(); pinta(); };
      if (k === ativo && MANUAL[k] && typeof Manual !== "undefined") {
        const q = Object.assign(document.createElement("a"), { href: "#", textContent: "? teoria e boas práticas", className: "ajuda-vista" });
        q.onclick = ev => { ev.preventDefault(); ev.stopPropagation(); Manual.abre(MANUAL[k]); };
        tx.append(q);
      }
      L.append(d);
    });
  }

  function pinta() { const lg = $("legenda3"); lg.hidden = !COMO_LER[ativo]; $("legenda3_txt").textContent = COMO_LER[ativo] || ""; $("veredito3").hidden = true; $("graficos3").innerHTML = ""; $("graficos3").className = "graficos"; $("conteudo3").innerHTML = ""; MODULOS[ativo].pinta(); }

  return {
    registra(nome, m) { MODULOS[nome] = m; },
    entra() { lista(); pinta(); },
    nome: () => ativo,
    ativa: () => document.body.dataset.etapa === "3",
  };
})();
