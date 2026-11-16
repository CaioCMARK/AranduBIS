# Como usar estes manuais

O AranduBIS serve para aeronaves de qualquer arranjo: monoplanos, biplanos, tandem, canard, asa voadora, corpo e asa integrados, multi-superfície. Ele automatiza muita coisa: escolhe malha, passo de tempo, modos de vibração e elementos, e avisa quando a geometria foge do que o método aguenta. Isso acelera o trabalho, mas não substitui saber o que está sendo calculado. Cada manual tem quatro partes:

1. **O que o método resolve**: a física e as hipóteses, com as equações principais.
2. **Como operar**: o que mexer, em que ordem, com que valores de partida.
3. **Como conferir**: como saber se o número na tela é confiável.
4. **Erros comuns**: o que costuma dar errado em projeto de aeronaves.

> Regra de ouro: nenhum resultado vale mais que a verificação que você fez nele. Antes de levar um número para um relatório, um ensaio ou a oficina, faça pelo menos uma das conferências do manual da área.

## O fluxo do programa

O programa tem cinco etapas, nas abas do alto:

1. **Geometria**: monte ou abra a aeronave (asas, cauda, fuselagem, motor, massas).
2. **Análise**: aerodinâmica, estabilidade, hélice e desempenho.
3. **Estrutura**: cargas, viga, flambagem, aeroelasticidade, vibração e fabricação.
4. **Otimizar**: variáveis, restrições e a função objetivo que você escolher.
5. **Resultados**: compare as alternativas e leve a escolhida de volta à geometria.

Cada vista mostra, logo acima do gráfico, uma legenda "O que você está vendo" com os eixos e as cores. Passe o mouse sobre o nome de um campo para ver a dica.

## Onde está cada coisa

- **Rodapé → "malha"**: abre a discretização da última análise. Mostra o que foi usado, se veio do automático ou de um valor seu e por quê. Também lista os avisos de geometria e tem o botão de teste de convergência do VLM.
- **Configurações → Discretização**: onde você fixa um valor no lugar do automático (campo vazio = automático). Também tem o orçamento de tempo das análises pesadas.
- **"? teoria e boas práticas"** embaixo de cada vista da etapa 3: abre o manual daquela análise.

## Configurações pouco convencionais

Quando a aeronave foge do monoplano com cauda, algumas hipóteses merecem atenção:

- **Sem cauda (asa voadora, BWB)**: a estabilidade depende da incidência e do enflechamento. Verifique a margem estática e o equilíbrio antes de qualquer otimização.
- **Superfícies sobrepostas (biplano, tandem, caixa)**: a esteira de uma asa atinge a outra. Aumente a malha e confira a convergência.
- **Canard**: o eixo elástico e o centro aerodinâmico definem a divergência. Veja o manual de flutter.
- **Fuselagem sustentadora**: ela entra como corpo com superfícies; confira o que a análise considerou.
- **Várias hélices ou hélice no escoamento da asa**: use o manual da hélice para saber o que está acoplado e o que não está.

Em qualquer arranjo, compare o resultado com uma conta simples (área × pressão dinâmica × coeficiente) antes de confiar.

## Por onde começar

- Nunca rodou VLM? Leia [VLM: malha de vórtices](#vlm) e depois [Discretização e convergência](#discretizacao).
- Vai dimensionar a asa? [Viga da asa](#estrutura), depois [Flutter](#flutter).
- Vai fabricar? [Fabricação: nervuras, planificação e STL](#fabricacao).
- Vai escrever relatório ou artigo? [Verificar e validar](#verificacao): é o que um revisor pergunta.


## Privacidade e rede

O programa roda inteiro no seu computador. O servidor interno só aceita conexões da própria máquina (`127.0.0.1`), recusa pedidos vindos de outras páginas e só entrega arquivos da pasta do programa e das pastas de dados que você configurou. Nada do seu projeto é enviado para fora. Se precisar abrir em outra porta, use `--porta N`.

## Cálculos demorados

Quando uma análise leva mais de meio segundo, aparece um aviso "Calculando…" com o tempo decorrido e o botão **Cancelar**. A primeira análise depois de abrir o programa demora mais, porque as rotinas numéricas são preparadas nesse momento; as seguintes são rápidas. Cancelar faz a tela parar de esperar; o resultado daquele cálculo é descartado.
