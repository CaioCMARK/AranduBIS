# Flutter e vibração

## O que resolve

Acoplamento entre a estrutura (flexão, torção e aileron) e a aerodinâmica não estacionária. Acima da velocidade de flutter, um modo tira energia do escoamento a cada ciclo e a amplitude cresce até quebrar.

Modelo: a semi-asa vira uma viga com modos de vibração no vácuo, e a aerodinâmica é calculada faixa a faixa com Theodorsen (NACA TR 496, aileron com as constantes T1–T13). O método p-k procura, para cada V, as raízes do sistema

```
[−ω² M + K − q·Q(k)] x = 0          k = ωb/V,  q = ½ρV²
g(V) = amortecimento do modo        flutter: g cruza zero de − para +
```

A frequência reduzida k e a função de Theodorsen C(k) dão o atraso da sustentação, o mesmo efeito de memória que o [UVLM](#uvlm) mostra no tempo.

## O que decide o flutter

- **Distância do CG da seção ao eixo elástico** (x_α): CG atrás do eixo elástico é o maior vilão.
- **Razão entre as frequências de torção e de flexão**: quanto mais próximas, pior.
- **Aileron**: balanceamento de massa e rigidez do comando. Um aileron solto e desbalanceado flutua em velocidade baixa.
- **Massa real**: servos e lastro na posição certa. Use a vista Massa da asa.

## Como operar

1. Rode Massa da asa com servos, aileron e entelagem declarados.
2. Rode Flutter. A velocidade de flutter (VF) deve passar de 1,2 Vd (margem 14 CFR 23.629).
3. Ligue o aileron e varra a rigidez do comando e o balanceamento.

## Como conferir

- **Modos no vácuo contra GVT** (ensaio de vibração): bata na asa, meça as frequências com o celular (app de espectro) e calibre na vista Calibração.
- **Modos**: o automático usa 8. Se o flutter sair perto do modo mais alto incluído, o programa avisa: aumente os modos e veja se o VF muda.
- **Varredura**: com o VF a menos de dois passos do requisito, aumente as velocidades para o veredito não depender da interpolação.

## Flutter no tempo com o UVLM 3D

O p-k usa **faixas**: cada faixa da asa responde como um perfil 2D de Theodorsen, sem perda de ponta. O botão **Conferir no tempo (UVLM 3D)** marcha a mesma asa (os mesmos modos, massas e rigidezes) com a aerodinâmica 3D do UVLM:

```
Ms q'' + Cs q' + Ks q = Q(t)          Q_r = Σ F_aero(para cima) · w_r(para cima)
w_r(x, y) = −[h_r(y) + (x − x_ea(y)) α_r(y)]      (h para baixo, α nariz para cima: como Theodorsen)
```

A malha não se move (linearizado, como o flutter clássico). O movimento entra na condição de contorno pela velocidade equivalente ẇ + V ∂w/∂x: a inclinação vira velocidade normal.

**Acoplamento forte.** Em cada passo a esteira anda uma vez; depois estrutura (Newmark de aceleração média, que não amortece nada) e aerodinâmica iteram até o deslocamento modal parar de mudar, com relaxação de Aitken. A massa aparente (ρ ∂Γ/∂t) depende da aceleração. Por isso uma passada só (acoplamento fraco) diverge quando a asa é leve, como as de balsa.

Os modos são da **semi-asa** engastada (os mesmos do p-k); o UVLM tem as duas metades. Simétrica ou antissimetricamente, cada metade dá a mesma força generalizada, então Q é a metade da soma.

**Amortecimento.** Do histórico q(t), o **método do lápis de matrizes** (Hua & Sarkar, 1990) ajusta exponenciais complexas e devolve frequência e ζ de cada modo acoplado. O flutter é a velocidade onde o ζ do modo que fica instável cruza zero (o modo é seguido pela frequência de uma velocidade para a outra). O programa marcha em 4 velocidades em volta do flutter do p-k e refina a travessia com mais uma marcha.

**Divergência.** Com V subindo, a frequência da torção cai, o modo vira dois polos reais e um deles passa para Re s > 0: a asa torce sem oscilar. O programa acha isso de dois jeitos:

```
estática 3D:  Q0 = força generalizada em regime por modo, a V_ref (uma marcha até o regime por modo)
              Ks q = (V/V_ref)² Q0 q   →   V_D = V_ref / √μ_max,   μ = autovalores reais > 0 de Ks⁻¹ Q0
no tempo:     Re s do polo real dominante de cada marcha; V_D onde ele troca de sinal
```

A estática custa N marchas curtas (um passo por corda, 40 cordas de esteira) e sai nas duas simetrias. Se ela vem antes das velocidades do flutter, o programa marcha também a 0,95 e 1,05 V_D para conferi-la no tempo. As duas são asa engastada, como o p-k e a aba Torção.

**Verificação (tests/test_flutter_tempo.py):**

- Sem ar, os modos vibram nas frequências naturais com ζ = 0. O período alonga (ωΔt)²/12: 0,4 % com 28 passos por ciclo.
- Asa de alongamento 40 sobre molas (seção típica de Hodges & Pierce): o flutter no tempo fica a 4 % do p-k de Theodorsen. Onde a teoria 2D vale, as duas contas concordam.
- Asa de Goland:
  - p-k de faixas: 137 m/s a 70 rad/s (literatura: 137,2 m/s e 70,7 rad/s).
  - UVLM 3D no tempo: ~162 m/s a ~67,5 rad/s (160 a 163 m/s de 16 × 8 a 32 × 12 painéis, 4 a 8 passos por corda).
  - Referências 3D publicadas: 165 m/s (UVLM do SHARP: o mesmo método, 2 % acima), 146,6 m/s (painel de Morino), 142,9 m/s (CFD acoplado, Mach 0,42). A perda de ponta alivia a torção e o 3D passa das faixas.
  - Até a v15 a força generalizada somava as duas metades contra os modos da semi-asa: aerodinâmica em dobro, 132 m/s. Corrigido; o teste trava o valor novo.
- Divergência: na asa voadora canard (ρ = 1,1), o polo real das marchas cruza zero a 16,05 m/s e a estática 3D da mesma simetria dá 16,02 m/s (0,2 %). Faixas × 3D: alongamento 40, V_D 3D = 1,06 × faixas (a perda de ponta só tira sustentação); Goland (alongamento 6,7), 300 m/s × 252 das faixas (fórmula fechada π²GJ/(4L² e c² a): 252,4).
- No regime, o resultado não depende do passo (tests/test_uvlm.py). Antes, a matriz de influência usava o núcleo singular e a esteira o regularizado: o segmento que dividem não cancelava, e com V Δt do tamanho do painel o centro de pressão andava 0,002 c para a frente. Parece nada, mas mudava a V_D da canard em 3 %, porque ali o eixo elástico fica a 0,006 c do centro aerodinâmico.

**Quando muda a resposta:** superfícies de alongamento baixo (canard, empenagem), eixo elástico perto do centro aerodinâmico e frequência reduzida alta. Na asa voadora canard do exemplo (ρ = 1,1, Vd = 25 m/s):

- p-k de faixas: flutter do canard a 19,5 m/s (57 Hz); divergência só a 26,5 m/s.
- UVLM 3D: o mesmo modo de 57 Hz fica amortecido até 27 m/s (ζ cai de 0,010 para 0,003). Mas o canard **diverge a 15,3 m/s** (antissimétrica; 16,0 simétrica), metade da exigida (30 m/s = 1,2 V_d).
- Qual número onde: 16,0 e 15,3 m/s são com ρ = 1,1 e V_d = 25 m/s (o teste e este texto). A aba do programa abre com ρ = 1,225 e V_d = 18,75 m/s e mostra **15,2 (simétrica) e 14,5 m/s (antissimétrica)**: é o mesmo cálculo, porque V_D ∝ ρ^(-1/2) (16,02 × √(1,1/1,225) = 15,18; 15,27 × 0,948 = 14,47). A V_d não entra na divergência, só na exigida (1,2 V_d: 30 m/s num caso, 22,5 no outro).
- Por quê: o eixo elástico está a 0,256 c e as faixas põem o centro aerodinâmico em 0,25 c (braço de 0,006 c). No 3D o carregamento perto da ponta vai para a frente: centro de pressão de 0,246 c na raiz a 0,207 c na ponta (média 0,239 c), e é na ponta que a torção é maior. O braço triplica.
- A aba Aeroelasticidade estática (VLM, aeronave trimada) converge até 16 m/s e não a 20 m/s. Lá o equilíbrio fixa a carga total do canard e o cm do perfil arqueado domina; a V_D da asa engastada é o limite clássico, do lado seguro.

Na Goland o 3D deu mais que as faixas; na canard, bem menos. Por isso a conferência existe.

**A correção, no exemplo `generico/asa_canard_eixo_a_frente.json`:** o eixo elástico precisa ficar à frente do centro aerodinâmico, não a 0,006 c dele. No modelo base o chapeado (balsa de 1 mm) para em 22 % da corda, antes da longarina de 25 %: a seção é aberta, a torção é mole (9 Hz) e o eixo cai em 0,256 c. A variante põe a longarina da frente em 15 %, a de trás em 60 % e leva o chapeado a 30 %: a caixa D fecha e o eixo vai a 0,113 c. Mesmas condições (ρ = 1,1, V_d = 25):

| | eixo elástico | flutter (p-k) | divergência (3D) |
|---|---|---|---|
| canard base | 0,256 c | 19,5 m/s | 15,3 m/s |
| eixo à frente | 0,113 c | 46 m/s (exigida: 30) | sem divergência (o 3D só acusa outro mecanismo acima de 300 m/s) |

Separar as duas mudanças (só deslocar o eixo para 0,113 c, com a estrutura de antes, pelo campo "deslocamento da linha elástica"): sem flutter até 3 V_d e divergência 3D a 328 m/s. Ou seja, quem tira a divergência é a posição do eixo; a caixa fechada ainda sobe o flutter (19,5 para 46 m/s). Custo: a caixa D fechada e a longarina da frente mais para a frente pesam um pouco mais; pese o canard de verdade.

## Erros comuns

- Massa uniforme no lugar da real: o servo na ponta muda tudo.
- Aileron "travado" no modelo e solto no avião.
- Margem pequena tratada como aprovado: o modelo tem incerteza de 10 a 20 % sem o GVT.
