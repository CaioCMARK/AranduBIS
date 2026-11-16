# Hélice: BEMT e sopro

## O que resolve

A **teoria do elemento de pá com momento (BEMT)** corta a pá em faixas e, em cada uma, iguala duas contas da mesma força:

```
elemento de pá:  dT/dr = ½ ρ W² B c (cl cos φ − cd sin φ)        dQ/dr = ½ ρ W² B c (cl sin φ + cd cos φ) r
momento:         dT/dr = 4π r ρ (V + v_a) v_a F                  dQ/dr = 4π r³ ρ (V + v_a)(v_t/r) F
φ = atan[(V + v_a) / (Ωr − v_t)]      α = β − φ      F = perda de ponta e de cubo de Prandtl
```

O ângulo de entrada φ de cada faixa sai do resíduo de Ning (2014): R(φ) = sin φ (1 − k) − (V/Ωr) cos φ (1 + k′). Ele é liso, tem raiz garantida e vale também com a hélice parada (V = 0). Os coeficientes seguem o padrão APC/UIUC:

```
J = V/(nD)     CT = T/(ρ n² D⁴)     CP = P/(ρ n³ D⁵)     η = J·CT/CP     n em rot/s
```

**Teto teórico:** o disco atuador ideal (Froude) dá η_i = 2/(1 + √(1 + Tc)), com Tc = T/(½ρV²A). Nenhuma hélice real passa disso: a rotação do sopro, o número finito de pás e o arrasto do perfil tiram eficiência.

## Projeto ótimo (Adkins & Liebeck, 1994)

Para uma tração pedida, a distribuição de corda e de torção com a menor perda induzida (condição de Betz com a função de Prandtl). No programa ele serve de **verificação cruzada**: a análise BEMT da hélice projetada tem de devolver a tração, a potência e a eficiência do projeto. Bate a 1 %, com e sem arrasto.

## Sopro na asa

Do BEMT sai v_a e v_t em cada anel do disco. Atrás dele o sopro é um tubo de corrente que contrai:

```
v_a(x) = v_a0 [1 + x/√(x² + R²)]        (2 v_a0 longe: cilindro de vórtice semi-infinito)
π(r'²ᵢ₊₁ − r'²ᵢ)(V + v_a(x)) = vazão do anel no disco      (massa conservada anel por anel)
v_t(x) r' = k(x) v_t0 r                 (momento angular conservado)
```

Essa velocidade entra no VLM como velocidade local nos pontos de controle. A asa no sopro ganha pressão dinâmica (mais CL). A rotação inclina o escoamento: um lado da asa ganha ângulo e o outro perde.

## Hélice girante: linha sustentadora + partículas

O BEMT e o sopro acima são **médias no tempo e no azimute**. Para ver a hélice e a asa se enxergando no tempo (o sopro em hélice batendo na asa e na cauda, a carga cíclica com a hélice inclinada, a partida), a vista **UVLM** tem a opção **Hélice girante**. Cada pá vira uma **linha sustentadora girante**:

```
u_rel = u_ar − ω × r        φ = atan(U_axial / U_tangencial)        α = β − φ
Γ = ½ W c cl(α, Re)          (ponto fixo a cada subpasso: Γ muda a esteira perto da pá, que muda u_ar)
```

u_ar é tudo o que chega na pá: a corrente, a asa, a esteira de partículas e as outras pás. A pá larga a esteira como a asa do UVLM: 2 fileiras de anéis e dali para trás **partículas de vórtice** (seção de partículas no manual do UVLM). A hélice gira dψ por subpasso; o passo da asa é um número inteiro de subpassos.

**Enrolamento de Betz.** Depois de meia volta, as partículas que cada pá largou num subpasso viram 3: o **vórtice de ponta** (as pernas de fora do pico de Γ somadas, no centroide delas: Betz, 1919), o **de raiz** e o largado no tempo. A vorticidade se conserva e a esteira longe fica ~8 vezes mais barata.

Juntar partículas **ao longo** da hélice (como na esteira da asa) é errado aqui: a corda de uma curva fica para dentro dela, e somando nível após nível uma volta inteira vira um vetor quase só axial no eixo. A vorticidade azimutal some, e é ela que acelera o sopro (o sopro na asa caía para um terço).

**Verificação (tests/test_rll.py):**

- Isolada: T e P a 4 % do BEMT.
- Velocidade no disco (média azimutal) a 15 % da do BEMT, que já inclui o F de Prandtl.
- **Teoria de momento na esteira longe**, 1,5 D atrás do disco. Lá a pressão volta à ambiente e T = ρ ∫(V + u) u dA. O fluxo fecha com a tração das pás a 10 % com dψ = 10°.
  - O erro cai em 1ª ordem: 10 % com 14,6°, 6 % com 10°, 5 % com 7,5°.
  - O motivo é o núcleo das partículas, proporcional ao arco do subpasso.
- Trator na frente de uma asa: o ganho de CL fica a 30 % do BEMT + sopro no VLM. O giro trocado espelha a carga.

**Ponto fixo da circulação.** A pá enxerga as pernas do próprio primeiro anel: subir Γ num elemento põe downwash nele e upwash nos vizinhos. Com elementos estreitos (raiz e ponta em cosseno), o mapa Γ → Γ′ tem um modo serrilhado com fator < −1. Por isso a iteração é sub-relaxada, para por tolerância e corta o fator pela metade se o resíduo cresce. Aceitar a última avaliação sem relaxar deixava o serrilhado crescer de passo em passo até explodir.

## Como operar

- Escolha a hélice do catálogo, o perfil da pá e o ponto (rpm, V). A posição vem do elemento "helice" do modelo.
- Compare as curvas BEMT com as da APC (tracejado). Diferenças de 10 a 15 % são esperadas com a forma típica da pá.
- Para o efeito na asa, olhe a carga na envergadura com e sem o sopro.

## Como conferir

- **Projeto ótimo × análise** (automático nos testes).
- **Disco ideal:** η do BEMT < η_i sempre.
- **Estações:** dobre em Configurações → Discretização. T e P mudam < 0,1 %.
- **Ensaio:** a validação de verdade é contra túnel (UIUC volume 4: APC Thin Electric de 12 a 21"), com a geometria medida da pá.

## Erros comuns

- Tratar a curva da APC como ensaio: é cálculo do fabricante (o arquivo diz "Simulation").
- Reynolds da pá abaixo da grade das polares (perto do cubo e na ponta em rotação baixa): a polar usa a borda da grade.
- Esquecer o sentido de giro: a rotação do sopro muda a carga dos dois lados da asa e cria momento de rolagem.
- Usar o BEMT para a interação no tempo (sopro batendo na cauda em manobra): para isso use a **Hélice girante** na vista UVLM.
- Na hélice girante, rodar menos tempo do que o sopro leva para passar pela última superfície: o CL ainda não chegou ao regime (o programa avisa).
- Esperar que a hélice girante e o BEMT + sopro deem o mesmo ΔCL: o tubo de partículas não é uniforme (vórtices de ponta concentrados, redemoinho de verdade) e tem ~10 % menos quantidade de movimento com dψ = 15°. Diferenças de 15 a 30 % no ganho de CL são do modelo, não erro.
