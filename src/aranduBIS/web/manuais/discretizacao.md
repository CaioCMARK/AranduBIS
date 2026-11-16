# Discretização e convergência

Todo método numérico troca um contínuo (a asa, a esteira, o tempo) por pedaços finitos: painéis, estações, elementos, passos. O resultado depende do tamanho do pedaço, h. Num método consistente o erro cai como uma potência de h:

```
f(h) = f_exato + C·h^p + ...        p = ordem do método
```

Dobrar a malha (h → h/2) divide o erro por 2^p: por 4 se p = 2, por 2 se p = 1. Por isso "mais painéis" nem sempre vale o custo. Depois de certo ponto você paga 4 a 8 vezes o tempo para ganhar a terceira casa decimal.

## O que o automático faz

Cada regra automática vem de um estudo de convergência medido (está nos testes do programa) e diz o motivo na tabela da malha. Exemplos:

| Análise | Regra automática | Por quê |
|---|---|---|
| VLM, envergadura | 24 faixas se AR ≥ 4, 48 se AR ≥ 1 | o vórtice de ponta domina asa curta |
| VLM, corda | 4 em perfil simétrico, 12 em arqueado | o CL de arqueamento converge como 0,55/n |
| Estrutura | 41 estações, ou ≥ 2 por baia de nervura | integração de cortante/fletor com erro ~(Δy)² |
| Flutter | 8 modos, 45 velocidades | modos até ~3× a frequência de flutter |
| UVLM harmônico | n_chord = 1,2·k / 5 % | erro da massa aparente ≈ 1,2·k/n_chord |
| Chapeado FE | elemento de ~8 mm | ≥ 4 elementos por meia-onda de flambagem |

## Como operar

1. Rode com o automático primeiro.
2. Abra a **malha** no rodapé e leia os motivos e os avisos.
3. Para um número que vai para o relatório, faça o **teste de convergência** (botão no painel da malha para o VLM; nas outras áreas, fixe valores em Configurações → Discretização e compare).
4. Só fixe um valor se tiver motivo: geometria fora do comum, estudo de sensibilidade ou máquina lenta.

## Como conferir: três malhas e Richardson

Rode com h, h/2 e h/4 (ou metade, atual e dobro). Com f₁ (grossa), f₂ e f₃ (fina):

```
p      = ln[(f₁ − f₂)/(f₂ − f₃)] / ln 2          ordem observada
f_ext  = f₃ + (f₃ − f₂)/(2^p − 1)                valor para malha infinita
GCI    = 1,25 · |f_ext − f₂| / |f_ext|           erro estimado da malha do meio
```

- **p estável entre famílias e casos**: está no regime assintótico e a extrapolação vale. No VLM, na envergadura, o p observado fica entre 0,5 e 1, porque a singularidade da ponta segura a convergência. Por isso dobrar faixas rende menos do que parece.
- **GCI < 1 a 2 %**: a malha atual serve para projeto.
- **Sinais alternados** (f₁ − f₂ e f₂ − f₃ com sinais opostos): convergência oscilatória, sem p. Use a maior diferença como erro.
- **p muito baixo**: ainda longe do regime assintótico. Refine mais antes de acreditar na extrapolação.

> Ordem de grandeza: num biplano de alongamento moderado com perfil arqueado, é comum o CLα convergir em poucos por cento na envergadura e em menos de 1 % na corda com a malha automática, enquanto 4 painéis na corda ainda deixam o CL mudar mais de 10 % ao dobrar a malha. Daí a regra de 12 painéis na corda para perfil arqueado: o arqueamento é a parte que mais pede malha. Rode o teste de convergência no seu caso; estes números são só referência.

## Orçamento de tempo

Não existe "máximo de painéis" físico. O programa estima o tempo pela malha antes de rodar e compara com o orçamento de Configurações → Discretização (padrão 120 s). Acima dele, a regra automática afina menos onde pode e, se ainda não couber, pede confirmação. Só a falta de memória é recusa firme.

**Segundos de qual computador?** Da primeira vez, o programa mede a sua máquina (~0,5 s) nos três núcleos que pesam nas marchas no tempo:

- segmento de vórtice (VLM, UVLM de anéis);
- partícula com partícula, com gradiente (esteira de partículas);
- segmento com gradiente (anéis agindo nas partículas).

A estimativa é o número de interações de cada tipo dividido pela velocidade medida, corrigido por uma eficiência medida comparando estimativa e tempo real (±30 %). O resultado fica guardado e é refeito se o processador mudar. A mesma análise estima mais segundos num i3 do que num i7: o orçamento é do seu tempo, não da malha.

## Erros comuns

- Achar que mais painéis é sempre melhor. Malha fina demais no VLM com superfícies próximas piora o condicionamento.
- Comparar duas aeronaves com malhas diferentes. A diferença de malha pode ser maior que a diferença de projeto: em estudo comparativo, fixe a malha.
- Ignorar avisos de geometria. Eles apontam onde o método perde a validade, e isso nenhuma malha corrige.
