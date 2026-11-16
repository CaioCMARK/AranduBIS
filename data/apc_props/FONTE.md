# APC Thin Electric — arquivos de desempenho do fabricante

Baixados em 2026-09-10 de `https://www.apcprop.com/files/PER3_<modelo>.dat`.
Índice completo dos 452 modelos em `PER2_TITLEDAT.DAT`, da mesma origem.

## O que veio

As **30 hélices da série E (Thin Electric) de 16 a 27 polegadas** — a faixa
útil para AeroDesign:

    16x4E   16x6E   16x8E   16x10E  16x12E
    17x6E   17x7E   17x8E   17x10E  17x12E
    18x8E   18x10E  18x12E
    19x8E   19x10E  19x12E
    20x8E   20x10E  20x11E  20x13E  20x15E  20.5x14E
    21x13E
    22x10E  22x12E
    24x12E  25x12.5E
    26x13E  26x15E  27x13E

**A 27x13E é a maior Thin Electric que existe.** Não há 28", 30" nem 32" na
série. Isto importa: as seis campanhas por ano do Arandu terminaram todas em
`diametro_helice = 30`, o teto da caixa — propondo um produto que não se compra.

## O que estes arquivos são

Cada arquivo traz `Ct`, `Cp`, rendimento e mais colunas contra razão de avanço,
em blocos de rotação de 1000 rpm até 9000–15000 rpm conforme o tamanho (hélice
grande não gira rápido, e a APC não tabela o que não roda).

Convenção, conferida no cabeçalho de cada arquivo e igual à de
`aero/helice.py` e à do UIUC:

    Ct = T/(rho n^2 D^4)      Cp = P/(rho n^3 D^5)      n em rot/s

## O que estes arquivos NÃO são

**Não são ensaio.** O cabeçalho diz `Simulation Date` e `AIRFOIL AERO DATA
GENERATED USING: POLAR DIAGRAMS` — é cálculo do fabricante, de família parecida
com o BEM deste projeto. Validar o Arandu contra eles seria validar um programa
contra outro.

## Quanto eles valem, medido

O UIUC ensaiou em túnel de vento a 17x12E e a 19x12E, e as duas estão aqui.
`validacao/apc_contra_uiuc.py` compara os 162 pontos em comum:

| faixa de rotação | n | viés de `CT` | dispersão |
|---|---|---|---|
| abaixo de 2400 rpm | 35 | **+12,1%** | 17,5% |
| 2400–3600 rpm | 127 | **−3,9%** | 9,3% |
| tudo | 162 | −0,4% | 13,3% |

Para comparar, o BEM deste projeto contra o **mesmo túnel** deu −9,9% na 17x12
e −23,6% na 19x12.

Ou seja: **na faixa de rotação em que a aeronave opera (~2800 rpm), o dado do
fabricante erra 4% e o BEM daqui erra 10 a 24%.** O `-0,4%` da última linha é
média sobre regimes e esconde isso — não usar esse número.

## Armadilha no nome do arquivo

A APC **omite o ponto decimal** no nome: `PER3_25x125E.dat` é a 25x12.5E e
`PER3_205x14E.dat` é a 20.5x14E. Ler o modelo do nome do arquivo dava passo de
125 polegadas. O modelo correto está na **primeira linha de dentro do arquivo**,
e é de lá que `aero/apc.py` lê.

## Referências

- APC Propellers, *Performance Data*, `https://www.apcprop.com/technical-information/performance-data/`
- Brandt, Deters, Ananda, Dantsker e Selig, *UIUC Propeller Database*, Vols. 1–4,
  Univ. of Illinois at Urbana-Champaign — ver `data/uiuc_props/FONTE.md`
