# Laboratório de configurações

## O que é

Uma pasta de aeronaves estranhas (`cases/geometria/laboratorio/`, abertas na lista de exemplos) e uma régua para compará-las: asa voadora com vertical na ponta, no centro ou para baixo, Burgess-Dunne, asa mista de corpo (tipo X-48) com e sem canard, duto de ducted fan na cauda, asa em caixa, tandem. A lógica está em `aranduBIS/nucleo/aero/laboratorio.py` e `comparativo.py`; `python cases/geometria/laboratorio/monta_laboratorio.py --estudos` regrava os JSON e imprime todas as tabelas.

## A régua (mesma condição para todos)

- Mesmo **peso** (66,8 N, CL = W/(q S_ref)), mesma **envergadura** (2,4 m), V = 15 m/s, ρ = 1,1.
- **CG a 10 % de margem estática** do ponto neutro de cada configuração (não o mesmo x: o ponto neutro muda com a configuração).
- **Trimado** (CL de projeto e Cm = 0): com a empenagem inteira, o canard, o elevon, ou, nas asas voadoras, com o **washout** que zera o Cm.
- Medidas: arrasto induzido D_i (N), eficiência de envergadura e_b = L²/(π q b² D_i), Cn_β, Cl_β, margem estática.

```
D_i = ½ ρ V² S_ref C_Di        e_b = L² / (π q b² D_i)       (e_b = 1: asa elíptica plana)
```

## Verificação

`tests/test_laboratorio.py` confere o D_i do VLM de um biplano reto (sem stagger) contra uma conta independente no plano de Trefftz, com asas elípticas (Prandtl 1924, Munk 1923):

| h/b | D_i biplano / D_i monoplano, VLM | Trefftz |
|---|---|---|
| 0,05 | 0,909 | 0,893 |
| 0,10 | 0,838 | 0,829 |
| 0,15 | 0,789 | 0,781 |
| 0,25 | 0,723 | 0,712 |

Dentro de 2 %. A winglet reproduz o que a literatura dá (10 a 20 % do induzido a sustentação constante, h/b de 0,1 a 0,15).

## Resultados (VLM, potencial, sem descolamento)

**Vertical na ponta ou no centro da asa voadora varrida** (mesmo Cn_β = 0,03):

| | altura | área | D_i | arrasto da deriva | saldo vs. sem vertical | peso |
|---|---|---|---|---|---|---|
| sem vertical | | | 1,87 N | | | |
| pontas, para cima | 0,33 m | 0,112 m² | 1,55 N (e_b 1,28) | 0,20 N | **−0,12 N** | 0,49 N |
| pontas, para baixo | 0,19 m | 0,066 m² | 1,67 N (e_b 1,19) | 0,12 N | −0,08 N | 0,29 N |
| central | 0,51 m | 0,103 m² | 1,87 N | 0,18 N | **+0,18 N** | 0,45 N |

Na ponta o vertical estabiliza **e** paga parte da conta (efeito winglet): o saldo de arrasto é negativo, no centro é positivo. O de baixo pediu menos área para o mesmo Cn_β (0,066 contra 0,112 m²; a causa não foi investigada), dá menos ganho de D_i e muda o diedro efetivo (Cl_β −0,04 contra −0,19 do de cima). A deriva de cima aumenta bastante o diedro efetivo, o que numa asa varrida já excessiva pode pedir reduzir o diedro. Arrasto da deriva: C_f = 0,0065 sobre 2,2 × a área.

**Flutter com massa na ponta (a deriva).** p-k de faixas da asa varrida com uma massa pontual a 96 % da semi-envergadura, V_d = 25 m/s (exigida: 30 m/s). A deriva de 0,112 m² pesa ~50 g (25 g por ponta, balsa de 0,45 kg/m²):

| massa por ponta | x/c da massa | flutter |
|---|---|---|
| 0 / 25 / 50 g | 0,30 e 0,55 | sem flutter até 3 V_d |
| 0 g | 0,80 | sem flutter |
| 25 g | 0,80 | **39,9 m/s** |
| 50 g | 0,80 | 48,9 m/s |

Massa **na frente ou perto do eixo** não faz mal. Massa muito atrás (0,8 c, deriva de bordo de fuga comprido) cria o flutter, mas acima da exigida. Mais massa sobe o flutter porque baixa a frequência de flexão e afasta da de torção. **O que o modelo não vê:** a aerodinâmica da própria deriva (força lateral na ponta que torce e flete a asa) e a flexibilidade da ligação deriva-asa. O p-k de faixas só leva a massa. Confirme no GVT com a deriva montada.

**Burgess-Dunne (1917) contra monoplano de mesma área e envergadura** (gap/b = 0,15, stagger de 0,12 m, derivas nas pontas): D_i 1,41 N contra 1,93 N (**−27 %**, e_b 1,42 contra 1,03). A comparação a washout igual (4°, sem trimar) separa o efeito de empilhar: **−22 %**, que é o que a teoria do biplano dá (−22 % em h/b = 0,15, tabela acima). O resto vem de o Burgess-Dunne trimar com 2,8° de washout contra 7,9° do monoplano (o stagger e as duas asas dão braço). O custo que o VLM não conta: o escoamento entre as asas (interferência viscosa), a estrutura de interplano e o peso.

**BWB tipo X-48** (corpo grosso de 0,9 m de corda na raiz, bordo de ataque a 55° até y = 0,35 m e a 30° depois, derivas nas pontas, elevons em |y| ≥ 0,5 m): D_i 1,63 N (e_b 1,22). Rotação no efeito solo a 0,2 m de altura (CL de rotação 0,9): o elevon sozinho equilibra até CL = 1,01 e o **canard todo móvel até 1,12**, a 14° de alpha em ambos (o que limita é o alpha, não a deflexão). Ou seja, o canard ajuda (+11 % de CL equilibrado), mas o BWB desta escala, com o CG a 10 % de margem, rotaciona bem sem ele. Com o CG mais à frente o canard deve valer mais (não testado). No cruzeiro o canard não ajuda (e_b 1,20 contra 1,22).

**Duto na cauda** (anel de 8 painéis, raio 0,15 m, comprimento 0,30 m, no lugar da empenagem; CG fixo a 0,12 m): Cn_β 0,135 contra 0,057 da cauda convencional equivalente (o anel é um vertical enorme), mas em arfagem rende menos (C_mα +0,14 contra −0,47: ainda instável com esse CG). O VLM dá a sustentação do anel, **não o fluxo da hélice dentro dele**. Empuxo estático pela teoria do disco (Küchemann e Weber): T = (2 ρ A_e P²)^(1/3), A_e a área de saída; com P = 400 W, D = 0,30 m e FM = 0,7: 20,4 N (duto cilíndrico) e 21,7 N (difusor de σ = 1,2, que descola fácil).

**Asa em caixa e tandem** (monoplano com cauda convencional como referência, todos trimados): caixa D_i 1,60 N (e_b 1,24) contra 1,97 N (e_b 1,01), **−19 %**; tandem 2,07 N (e_b 0,96): o tandem não paga induzido, a vantagem dele é a margem de CG, não o arrasto.

## Caso de estudo: pontuação por uma regra de competição e otimização (`laboratorio_otim.py`)

O exemplo abaixo usa a regra SAE AeroDesign 2026 que acompanha o programa em `cases/regras/`. Qualquer outra regra de pontuação entra do mesmo jeito: o que importa aqui é comparar configurações na mesma régua.

Cada configuração ganha a **mesma estrutura** (4 tubos de carbono a 30 % da corda, nervuras e longarina de balsa, entelagem; dimensionados pela parede) e o **mesmo sistema de massas** do exemplo do canard (servos, eletrônica, bateria, cablagem, motopropulsor, fuselagem e trem), e passa pela cadeia inteira do programa: peso vazio, CG com 9 kg de carga, margem estática, CL máximo, trim na decolagem (flape só do meio da semi-envergadura para fora nas asas voadoras), massa máxima em 55 m, regra SAE 2026. Variáveis de todas: b, escala das cordas, posição da carga, incidência, washout, diâmetro do tubo; cada uma acrescenta as suas (enflechamento, altura das derivas, tamanho e braço da cauda ou do canard, stagger e gap). Restrições: margem estática ≥ 5 %, margem estrutural ≥ 0, trim fecha com deflexão ≤ 20°, **Cn_β ≥ 0,03**, varredura e comprimento (abaixo) (o caminho do exemplo não olha estabilidade direcional), mais as da regra. Evolução diferencial com 18 indivíduos e 30 gerações (≈ 540 avaliações, malha grossa), depois os 8 melhores reavaliados na malha cheia. Caixa, tandem, derivas nas pontas e duto rodaram com limites de busca mais folgados (`SEGURO=1`: margem estática 6 %, estrutural 3 %, Cn_β 0,04; caixa e tandem com 24 × 36) para o ponto sobreviver à malha cheia; os outros rodaram com os limites reais.

| Configuração | P_VOO | PV (kg) | CP (kg) | b (m) | S (m²) | N |
|---|---|---|---|---|---|---|
| Asa voadora, deriva central | 259 | 3,39 | 15,07 | 2,54 | 2,27 | 1 |
| Asa voadora, derivas nas pontas | 251 | 3,46 | 15,49 | 2,88 | 2,33 | 1 |
| BWB tipo X-48 | 249 | 3,26 | 14,76 | 3,04 | 2,18 | 1 |
| Asa em caixa | 223 | 3,46 | 15,61 | 2,57 | 2,43 | 2 |
| Burgess-Dunne | 221 | 3,32 | 14,86 | 2,60 | 2,16 | 2 |
| Tandem | 220 | 3,31 | 15,34 | 2,89 | 2,06 | 2 |
| Monoplano com cauda convencional | 130 | 5,82 | 13,08 | 3,14 | 2,54 | 2 |
| BWB com canard | 123 | 5,53 | 12,08 | 3,56 | 2,12 | 2 |
| Duto na cauda (D 0,30 m, 600 W) | 94* | 6,01 | 7,81 | 3,40 | 2,70 | 2 |

\* Sem ponto viável: a melhor solução ficou com margem estática de 4,9 % (limite 5 %).

**Restrições de construção** (acrescentadas depois de ver as primeiras figuras: um BWB com bordo de ataque a 45° e um canard a 1,5 m do nariz da asa, uma treliça de guindaste): bordo de ataque das partes externas ≤ 30°, do corpo central ≤ 50°, e extensão das superfícies sustentadoras em x ≤ 1,6 m. Sem elas, o monoplano com cauda marcava 194 com um braço de cauda de 4,2 m; com elas, 130. Os braços de cauda e de canard são em metros (não escalam com a corda).

**Como ler.** A ordem é puxada pela própria regra: a asa voadora conta N = 1 (fator_N 0,87 contra 0,72 com duas superfícies), e as configurações compactas pagam menos fator_b = 1,15^−b. O monoplano com cauda é a referência: a diferença para as asas voadoras vale pelo que a regra premia, não prova que asa voadora voa melhor. Nos modelos de duas asas (caixa, tandem) a margem estática em c_ref sai enorme porque o braço entre as asas é grande; o duto perde porque o empuxo estático de 600 W num disco de 0,30 m (teoria do disco, FM 0,7) é bem menor que o da hélice (CP de 8 kg contra 15).

**Limites desta pontuação.** Flutter, divergência e reversão **não entram** na otimização (confira o ótimo antes de construir; a massa de ponta das derivas atrás do eixo elástico derruba o flutter, ver acima). Estrutura só de flexão do tubo; sem descolamento (VLM potencial: o CL máximo vem do critério de CL local do programa); sem arrasto parasita próprio; as derivas e o duto levam 0,45 kg/m² (estimativa); o motor do duto não tem fluxo de hélice no VLM; uma única semente, então o ótimo é um bom ponto, não o ótimo global. As asas voadoras otimizadas ficaram no limite de washout (≈ 11°) e com tubo de 12 mm: reveja com estrutura real. Rodar de novo: `python cases/otimiza/laboratorio/otimiza_laboratorio.py NOME 18 30` e `python cases/otimiza/laboratorio/resume.py`.

## Armadilhas medidas (valem para qualquer modelo seu)

1. **Deriva na ponta**: a raiz dela tem de continuar a ponta da asa (mesma corda, posição, incidência, perfil simétrico na ponta, mesmo número de painéis na corda). Quando a ponta tinha washout e arqueamento e a deriva nascia reta a milímetros dos nós da asa, o par de anéis quase coincidentes deu D_i negativo e e = nan.
2. **Esteira rente a outra superfície**: um canard 3 cm acima do plano da asa deu e_b = 1,96 (impossível: um canard só soma carga num plano de mesma envergadura). A 15 cm, e_b = 1,20. O VLM não avisa. Mantenha as esteiras a mais de ~0,1 m das outras superfícies.
3. **Efeito solo com deriva na ponta**: a esteira da asa passa rente aos pontos de controle da deriva e o resultado oscila com o alpha (CL e C_Di dando saltos). O estudo de rotação roda sem derivas.
4. **Asa voadora sem arqueamento refletido**: o washout que trima passa de 15° com NACA 0012; com o REFLEX-10 do repositório fica em 5 a 8°.

## O que o laboratório não faz

Descolamento, interferência viscosa entre asas, fuselagem, hélice dentro do duto, pressões de estrutura (a pontuação e a otimização estão na seção acima). Os números são para **ordenar** configurações na mesma régua, não para prever o D_i absoluto. Ver [Verificar e validar](#verificacao).
