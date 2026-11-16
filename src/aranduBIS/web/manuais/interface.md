# Interface: ferramentas, atalhos e editores

O programa tem duas interfaces sobre os mesmos cálculos. A **nova** (padrão) reúne as ferramentas dentro da vista 3D. A **clássica** continua disponível em **Configurações → Interface**, sem os recursos novos. A troca recarrega a página e não mexe na aeronave aberta se ela estiver salva.

## O que há na tela

- **Barra de menus**: **Arquivo**, **Editar**, **Exibir**, **Etapa**, **Ferramentas** e **Ajuda**, com os atalhos ao lado de cada item. Abrem com o clique, passam de um para o outro com o mouse ou com as setas e fecham com Esc. À direita fica o nome da aeronave.
- **Barra de ícones**: novo, abrir, salvar, desfazer, refazer, a busca de comandos (Ctrl+K), **Exportar** e as configurações.
- **Abas das etapas**, de 1 a 5. O selo ao lado do nome indica o estado: anel vazio = ainda sem resultado; círculo cheio = sem pendências; losango dourado = a etapa tem aviso. O selo muda quando você visita a etapa e ela mostra um veredito.
- **Vista 3D**, com a paleta de ferramentas à esquerda, a barra de câmera, sombreado e camadas no alto e o cubo de orientação no canto. Clique numa face do cubo para alinhar a vista.
- **Inspetor**, no alto do painel direito: mostra o nó, a nervura ou a medida selecionada e aceita valores digitados.
- **Barra de status**: ferramenta ativa, coordenadas do que está selecionado, massa, CG, envergadura, malha e a última mensagem. Erros também aparecem num aviso no canto, que some sozinho.
- Os botões no fim da linha das etapas (ou **[** e **]**) recolhem os painéis laterais.

## Ferramentas da vista

| Ferramenta | Tecla | O que faz |
|---|---|---|
| Selecionar | V | Clique numa peça para selecioná-la; arraste para girar. |
| Nervuras | R | Move, cria, gira e remove nervuras da asa. |
| Nós e barras | B | Move nós, cria barras, define juntas, apoios e ligações. |
| Seção | S | Clique num anel da asa para editar aquela seção. |
| Chapa 2D | C | Abre o editor 2D da chapa selecionada. |
| Perfil 2D | F | Abre o editor 2D do perfil da asa selecionada. |
| Medir | D | Dois cliques medem a distância; o terceiro mede o ângulo no segundo ponto. |

Se a peça selecionada não serve para a ferramenta, o programa seleciona a primeira que serve. **Esc** volta para Selecionar.

## Contorno e menus de contexto

A peça selecionada ganha um **contorno dourado** na vista 3D, além do realce de cor, para achá-la no meio da aeronave.

O **botão direito** abre um menu no lugar do clique:

- numa peça da vista ou numa linha da lista de elementos: editar o perfil (asas), a chapa (placas), as seções, as nervuras ou os nós (treliças), ocultar, mostrar só este, mostrar todos, duplicar e remover;
- no vazio da vista: vistas padrão, mostrar todos e a busca de comandos.

Para deslocar a vista continue usando Shift+arrastar ou o botão direito arrastando; o menu só abre se o mouse não se moveu.

## Atalhos gerais

| Tecla | Ação |
|---|---|
| 1 a 5 | ir para a etapa (fora das ferramentas de edição, que usam os números) |
| Ctrl+K | procurar qualquer comando, análise, exemplo ou elemento |
| ? | lista de atalhos |
| Ctrl+Z / Ctrl+Y | desfazer / refazer |
| [ e ] | recolher os painéis laterais |

A lista completa, com os atalhos de cada ferramenta, abre com **?**.

## Nós e barras: grupo, cópia e espelho

- **Shift+clique** junta o nó ao grupo. Arrastar um nó do grupo move todos juntos.
- **Ctrl+C** copia o grupo (ou o nó selecionado) e **Ctrl+V** cola 20 mm adiante, com as barras internas. O trecho colado fica selecionado para você arrastar.
- **I** espelha o grupo. Sem eixo travado, espelha em y (o outro lado da aeronave). Com **X** ou **Z** travado, espelha naquele eixo em torno do nó selecionado. Nós que já existem no destino são reaproveitados.
- Ao selecionar um nó, as barras ligadas a ele ficam destacadas. Com **Ctrl** pressionado aparece a prévia da barra até o cursor.
- Depois de rodar **Cauda e treliça** na etapa 3, cada nó ganha um anel com a margem da junta: verde = folgada; dourado = abaixo de 50 %; tracejado escuro = insuficiente. Se você mover o nó, o anel some até a próxima análise.

## Nervuras: refinamentos

- Com **Ctrl** pressionado, a posição da nervura nova aparece antes do clique.
- Clicar de novo no mesmo lugar alterna entre anéis sobrepostos.
- Se a asa tem **passo máximo** declarado, os vãos acima dele ficam marcados em dourado e contados no painel da vista.

## Editor 2D de chapas

Abre pela ferramenta **Chapa 2D** ou pelo botão na aba **Contorno** de uma placa. O desenho fica no plano x–z da chapa; a espessura e a posição y continuam nas Propriedades.

- **Marca d'água**: o corte das outras peças no plano da chapa (perfil da asa, tubos, treliça) aparece em cinza, e o cursor gruda nesses pontos. Serve para a chapa casar com o resto sem fazer contas.
- **Mover (V)**: arraste um vértice. Duplo clique num lado cria um vértice. As setas movem 1 mm (Shift: 10 mm).
- **Ponto (P)**: clique num lado para criar um vértice.
- **Furo redondo (F)** e **Furo retangular (R)**: clique e arraste.
- **Arredondar (A)**: clique num vértice para trocar o canto por um arco com o raio do painel.
- O painel mostra as coordenadas do vértice e o comprimento do lado seguinte; os dois aceitam valor digitado. As cotas dos lados aparecem no desenho.
- **Tab** passa ao próximo vértice; **Shift+Tab** alterna entre contorno e furos. **Ctrl+Z / Ctrl+Y** valem dentro do editor.
- **Importar DXF** lê polilinhas fechadas, linhas encadeadas e círculos; o maior laço vira o contorno e os demais viram furos. **Exportar DXF** grava em milímetros.
- **Aplicar** grava na aeronave (e entra no Desfazer geral). O programa recusa contorno que se cruza.

Limites: arcos viram segmentos de reta; não há cotas de ângulo nem restrições geométricas.

## Editor 2D de perfis

Abre pela ferramenta **Perfil 2D**, pelo menu de contexto da asa ou pelo botão ✎ ao lado do campo **perfil** (nas Propriedades vale para a asa inteira; na tabela de seções vale só para aquela seção). O perfil aparece normalizado pela corda, com a forma de origem tracejada para comparação.

- **Mover (V)** e **Ponto (P)** como no editor de chapa; setas movem 0,1 % da corda (Shift: 1 %). A opção "x travado" deixa o ponto correr só na vertical.
- **Gerar NACA de 4 dígitos** substitui o desenho; **Simetrizar** espelha a superfície superior na inferior.
- O painel mostra espessura e curvatura máximas com a posição de cada uma.
- **Importar .dat** lê os formatos Selig e Lednicer (UIUC); **Exportar .dat** grava em formato Selig.
- **Aplicar**: se o desenho ainda é um NACA, o campo vira "NACA mptt"; se você mexeu nos pontos, o programa grava um arquivo `.dat` (na pasta da aeronave, quando ela é sua; senão em `aeronaves/perfis`) e o campo passa a apontar para ele. O desenho que se cruza é recusado.
- As polares vêm do banco de perfis. Um perfil fora do banco (inclusive um desenhado aqui) usa as polares de perfis do banco com ângulo de sustentação nula parecido, e a análise registra esse aviso; confira o resultado com cuidado.

## Janela própria

O executável abre o programa numa janela própria, sem depender de navegador. Para abrir no navegador, rode com `--navegador`. Rodando pelo código, `python -m aranduBIS --janela` usa a janela própria quando o pacote `pywebview` está instalado; sem ele, abre no navegador.
