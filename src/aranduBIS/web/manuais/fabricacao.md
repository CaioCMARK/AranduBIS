# Fabricação: nervuras, planificação e STL

Esta vista leva o modelo da tela para a bancada. Ela cobre três saídas: nervuras planas para corte, o chapeado desdobrado em faixas e o STL para impressão 3D ou CAD.

## O que cada saída faz

- **Nervuras (DXF)**: cada nervura em tamanho real, em milímetros, com o recorte da longarina, furos e entalhes dos tubos, recesso do chapeado e compensação de corte. As peças são arrumadas em chapas do tamanho que você informar.
- **Chapeado planificado**: a pele entre duas nervuras é uma superfície curva. A vista a divide em faixas, achata cada uma e mede quanto precisaria esticar ou encolher para assentar. O DXF traz o contorno com a margem de cola, a linha do bordo de ataque para alinhar e o nome de cada faixa.
- **STL (em Exportar)**: a forma externa fechada em milímetros, ou o esqueleto com a estrutura interna (nervuras, longarinas, tubos e treliças).

## Posição, quantidade e ângulo das nervuras

Na aba Estrutura da asa você gera as posições por quantidade e distribuição (uniforme, mais densa na raiz, mais densa na ponta, ou nas seções do modelo) e depois edita cada nervura: posição, ângulo em planta, adicionar e remover. O passo máximo é só um aviso. Um revestimento de filme pede nervuras próximas, e um chapeado de chapa fina pede nervuras que impeçam a flambagem entre elas.

## Como ler o desdobramento

Uma superfície só se desdobra sem esticar quando sua curvatura gaussiana é zero: curvar em uma direção só, como num cilindro ou cone. Numa casca com curvatura nas duas direções, como uma esfera, o material precisa esticar ou enrugar. O programa mede isso de duas formas:

- **Déficit angular** em cada ponto da malha: dois pi menos a soma dos ângulos em torno do ponto. Zero significa plano.
- **Deformação** ao achatar: a mudança de comprimento de cada aresta da malha, em porcentagem, depois de achatar a faixa.

Cada faixa recebe uma situação:

- **Desdobra bem**: a deformação máxima fica abaixo do limite do material.
- **Pede cuidado**: passa do limite, mas até quatro vezes. Dá para forçar a pele umedecendo a chapa, vaporizando ou aquecendo o filme.
- **Precisa de emenda**: passa muito. Corte a faixa em duas, por exemplo no bordo de ataque, ou use faixas mais estreitas.

Os limites por material são hipóteses (por exemplo 0,3 % para balsa, 3 % para filme termocontrátil). Você pode digitar o seu. Confirme com um teste de bancada em uma tira do material.

## Ver na aeronave inteira

Na etapa 1, o seletor "Cor: desdobramento do chapeado" (ao lado dos botões Tudo, Aero e Estrutura) pinta a pele de cada asa com a mesma escala de cores: verde desdobra bem, vermelho precisa de emenda. O resto da asa fica cinza. Use com o botão Aero para esconder a estrutura. A cor acompanha as mudanças na geometria.

## Controle manual

- **Corte da pele**: automático (a vista escolhe), envolvendo o bordo de ataque ou separado em extradorso e intradorso. Também dá para fixar o modo de uma faixa na tabela.
- **Posição dos cortes**: por padrão as faixas vão de nervura a nervura. Você pode digitar as posições em y dos cortes.
- **Limite de deformação** e **margem de cola**.

## Como conferir

- Meça no modelo físico a largura de uma faixa e compare com a peça do DXF.
- Corte uma faixa em papel antes do material bom e cole na estrutura.
- Para o STL, confira a escala (a unidade é milímetro) e abra no fatiador: o programa avisa quando a malha tem arestas abertas.

## Erros comuns

- Imprimir o STL fechado como peça única. A forma externa vem como superfícies separadas; para impressão normal serve, mas pode precisar de reparo da malha no fatiador.
- Esquecer a espessura do chapeado ao posicionar as nervuras: a nervura tem recesso do bordo de ataque até onde a pele termina.
- Confiar no limite padrão do material sem testar uma tira.
- Ignorar o aviso de nervuras inclinadas: as faixas seguem as estações em y, não o plano inclinado.


## Editar as nervuras na vista 3D

A ferramenta **Nervuras** da vista 3D (tecla **R**; na interface clássica, o botão **Editar na vista 3D** em Estrutura da asa → Nervuras) mostra cada nervura como um anel laranja sobre a asa (a selecionada fica amarela; as pontas, que são automáticas, ficam cinza).

- **Arrastar** um anel move a nervura ao longo da envergadura, com passo de 5 mm (segure Alt para mover livremente). Ela não passa das vizinhas.
- **Ctrl+clique** sobre a asa cria uma nervura naquele ponto; **N** cria no maior vão.
- **← / →** movem 1 mm (Shift: 10 mm). **Q / E** giram a nervura em planta 1° (Shift: 5°); o ângulo fica só naquela nervura.
- **Tab** troca de nervura, **Delete** remove, **Esc** sai. Tudo entra no Desfazer.

Em asa simétrica só o lado positivo é guardado; o outro lado acompanha.


## Mover nós, rodas e massas na vista 3D

Use a ferramenta **Nós e barras** da vista 3D (tecla **B**; na interface clássica, selecione a peça e use **Mover nós / Mover na vista 3D** nas Propriedades). Vale para treliças, rodas e massas pontuais sem rolagem, arfagem ou guinada. Cada nó vira uma bolinha laranja; a selecionada fica amarela.

- **Arrastar** move no plano escolhido (**P** alterna planta, perfil e frontal; **X / Y / Z** travam um eixo). O passo é de 1 mm e há um ímã nos nós das outras peças, útil para fazer juntas coincidirem. **Alt** desliga passo e ímã.
- **Setas** movem x e z, **,** e **.** movem y (**Shift** multiplica por 10).
- **M** liga ou desliga a simetria em y: o nó (ou a roda) espelhado acompanha.
- **Tab** troca de nó, **Esc** sai. Tudo entra no Desfazer.

### Criar e remover nós e barras

Em treliças:

- **Ctrl+clique no vazio** cria um nó no plano de movimento atual, partindo do nó selecionado, e já o liga a ele com uma barra do tubo ativo (**L** desliga a ligação automática). Passo de 1 mm e ímã nos nós vizinhos valem também aqui.
- **Ctrl+clique em outro nó** cria a barra entre o selecionado e ele; repetir remove a barra.
- **T** troca o tipo de tubo usado nas barras novas.
- **Delete** remove o nó e as barras ligadas a ele.
- Com a simetria (**M**) ligada, o nó e a barra espelhados em y são criados e removidos juntos.

Grupo de nós, copiar e colar, espelhar e o anel com a margem da junta estão descritos no manual "Interface".

## Furos de alívio das nervuras

Em **3 Estrutura → Nervuras para corte a laser**, ligue **Propor furos**. O programa coloca furos redondos ao longo da linha média de cada nervura e os inclui no DXF.

- **Geometria**: cada furo respeita a **borda mínima** até o contorno e a **ponte** até os outros furos (inclusive os de tubo). Furos abaixo do **diâmetro mínimo** são descartados.
- **Conferência**: a nervura é tratada como viga ao longo da corda. A carga é a sustentação da faixa que ela sustenta (fator de carga × peso / área das asas × passo × corda), distribuída por igual, e os apoios são os furos de tubo. Em cada furo o programa calcula o cisalhamento e a flexão da seção líquida e, se a margem ficar negativa, encolhe o furo até passar ou o retira.
- **Resultado**: número de furos, fração de área removida e a menor margem. O botão **Usar o fator de massa na asa** grava o valor em `estrutura.nervuras.alivio`, para a massa e o CG considerarem os furos.

O que fica fora: esmagamento local nos apoios, flambagem da alma, cargas de manuseio e de colagem do revestimento. Trate a proposta como ponto de partida e confira a primeira nervura cortada na mão.
