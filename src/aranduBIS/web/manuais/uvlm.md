# UVLM: aerodinâmica no tempo

## O que resolve

O mesmo VLM, mas marchando no tempo. A cada passo dt, a asa larga uma fileira de anéis no bordo de fuga com a circulação que ela acabou de perder (Kelvin: a circulação total se conserva). A esteira guarda a história, e por isso a resposta tem "memória".

```
Kutta implícito: Γ_esteira,1 = Γ_bordo de fuga (no mesmo instante)
F = ρ Γ (V_local × dl)  +  ρ (dΓ/dt) A n
      circulatório           massa aparente
```

O segundo termo é a força para acelerar o ar em volta (massa aparente). Ele domina em frequência alta.

Casos e a teoria clássica de comparação:

| Caso | Teoria 2D | Para quê |
|---|---|---|
| Partida impulsiva | Wagner: Φ(s) = 1 − 0,165e^(−0,0455s) − 0,335e^(−0,3s) | atraso da sustentação |
| Rajada degrau | Küssner: Ψ(s) = 1 − 0,5e^(−0,13s) − 0,5e^(−s) | carga de rajada |
| Rajada 1-cos | (sem fórmula fechada) | CS-23 / 14 CFR 23.333, H = 25 cordas |
| Mergulho harmônico | Theodorsen C(k) | base do flutter |

s = 2Vt/c (semicordas percorridas), k = ωc/(2V) (frequência reduzida).

## Como operar

- **Rajada 1-cos** é o caso de projeto. A razão "ΔCL de pico / ΔCL quase estático" mostra o alívio de rajada que a fórmula de Pratt estima (o Kg).
- **Esteira rígida** (padrão): rápida e linear, suficiente para cargas.
- **Esteira livre**: só quando o enrolamento importa (ângulo alto, interação asa-cauda). O custo cresce com o quadrado dos nós.
- **Discretização automática** pelo caso e por k. No modo manual, campo vazio continua automático.

## Como conferir

- O CL final da partida impulsiva deve bater com o VLM estacionário (linha tracejada).
- O primeiro passo tem um pico (o impulso de massa aparente da partida, em teoria um delta). Ele fica fora dos gráficos.
- Nos casos harmônicos, o erro de amplitude é ≈ 1,2·k/n_chord. Para 5 %, n_chord ≥ 24k.
- Dobre os passos por corda: a resposta não deve mudar mais que alguns %.

## Esteira de partículas de vórtice (VPM)

Na esteira de anéis cada anel é um quadrilátero que se deforma com o escoamento: quando a esteira enrola forte (ponta, asa-cauda), os anéis esticam e se cruzam. Na esteira de partículas, cada aresta vira uma **partícula**: posição x_p, intensidade vetorial α_p = Γ·dl (m³/s) e núcleo σ. Sem conectividade, nada degenera.

```
u(x)     = −(1/4π) Σ_q g(ρ)/r³ (r × α_q)        ρ = |r|/σ      (Biot-Savart regularizado)
dα_p/dt  = (α_p · ∇) u(x_p)                      estiramento: o tubo de vórtice afina e gira
dx_p/dt  = u(x_p)                                 convecção
σ²       cresce 2ν dt                             difusão viscosa
g gaussiano = erf(ρ/√2) − √(2/π) ρ e^(−ρ²/2)
```

Junção com a asa: as 3 primeiras fileiras continuam anéis (a 1ª é o Kutta). Quando uma fileira vira partículas, a aresta da frente dela continua como segmento ligado ao último anel (a "fronteira"). Assim as duas circulações grandes e opostas (anel de um lado, partícula do outro) não ficam separadas perto da asa. Sem isso o CL caía 20 %.

**Fusão:** partículas velhas da mesma linha de vórtice se juntam aos pares (α soma, núcleo dobra). O número cresce com log₂ dos passos em vez de linearmente, e o custo cai ~7×.

**Como conferir:**
- Anel de vórtice isolado: velocidade no eixo do núcleo U = Γ/(4πR)[ln(8R/σ) − 1 − (ln 2 − γ)/2]. O programa bate a 0,1 %.
- A mesma asa com esteira de anéis livres e de partículas: o CL no tempo bate a 0,5 %.
- O vórtice de ponta migra para dentro da semienvergadura ao enrolar (Betz).

**Custo:** partículas × partículas (N², sem FMM ainda). O vídeo da esteira (botão MP4) mostra a nuvem colorida por |α|.

## Hélice girante

Marque **Hélice girante** no grupo Caso. A hélice do modelo (elemento "helice", eixo para trás) vira linhas sustentadoras girantes que largam partículas na mesma nuvem da asa. A teoria está no manual da hélice. A asa enxerga as pás e as partículas na condição de contorno e nas forças; a pá enxerga a asa no ponto fixo da circulação.

- **Custo.** Cada passo da asa tem n_sub subpassos da hélice (n_sub = dt·Ω/dψ: 15 a 25 em AeroDesign). Cada subpasso move todas as partículas (custo ∝ N²). A estimativa leva isso em conta: rode antes um caso curto.
- **Duração.** O sopro leva (x da cauda − x da hélice)/V para passar pela aeronave. Antes disso o CL ainda está subindo.
- **dψ.** 15° mostra a física; para números (ΔCL, tração), confira com 10°. O sopro converge em 1ª ordem no dψ.
- **Esteira da hélice.** Some meia envergadura depois da última superfície (o que está longe atrás quase não muda nada na aeronave).

## Efeito solo no tempo

Marque **Efeito solo** no grupo Caso. O chão é um plano paralelo à corrente, feito por **imagens**: cada segmento de vórtice A→B de circulação Γ ganha o espelho A′→B′ com −Γ, e cada partícula (x, α) ganha (x′, −Rα), com R = I − 2nnᵀ. No plano, a velocidade normal das duas se cancela:

```
w(chão) = w_real + w_imagem = 0        (Γ do espelho trocada, geometria refletida)
```

As imagens entram em tudo:

- na matriz (corpo + Kutta);
- na esteira de anéis e nas partículas, que não atravessam o chão;
- nas forças;
- na hélice girante (a pá enxerga a própria imagem dentro do ponto fixo).

**Altura.** É a do ponto de referência (¼ da corda) acima do chão. Vazio = medida pelas rodas no ângulo escolhido (corrida de decolagem).

**Subindo ou descendo.** A razão de subida faz h(t) mudar depois de uma espera (a partida assentar). A atitude fica fixa; o ar relativo ganha a componente vertical, então o ângulo efetivo cai de γ = atan(vs/V). A matriz é refeita a cada passo, porque o chão se move em relação à aeronave. A referência no gráfico é o **quase estático**: o VLM com solo na altura de cada instante, em α − γ.

**Verificação (tests/test_solo_uvlm.py):**

- Velocidade normal no chão: 1e-14 (imagens de anéis, esteira e partículas).
- Altura fixa: o UVLM vai ao VLM com solo a 1 % até h = 0,4 corda, onde o CL é 34 % maior que longe do chão.
- Saindo do chão a 0,3 m/s com V = 12 m/s: acompanha o quase estático a 0,6 %. O efeito solo de uma decolagem lenta é quase estático, como a tabela K(h) da decolagem supõe.
- Par de vórtices de partículas descendo sobre o chão: abre para os lados sobre 1/y² + 1/z² = constante (Lamb, *Hydrodynamics*, §155) a 0,5 %, tendendo a z = b₀/√5.

**Para ver o efeito dinâmico:** descendo 0,5 m/s sobre o chão (arredondamento), a asa voadora canard ficou ~5 % acima do quase estático. É o tipo de coisa que a tabela estática não mostra.

## Erros comuns

- Efeito solo com altura que muda e esteira rígida: a esteira rígida não acompanha o chão (o programa troca para livre).
- Altura pelas rodas com o ângulo de voo: as rodas medem a altura no ângulo escolhido. Para a corrida, use o ângulo de solo.

- Ler o pico de CL como carga real acima do estol. O escoamento é potencial: o CL não satura.
- Comparar uma aeronave completa (várias superfícies, alongamento finito) direto com Theodorsen. A curva de Theodorsen na tela é uma faixa 2D escalada pelo CLα 3D: serve para fase e ordem de grandeza.
- Esteira livre com núcleo grande demais: o enrolamento fica suave, mas as pernas perto das pontas perdem força.
- Partículas com núcleo pela largura da faixa (em vez de V·dt): borra a esteira perto do bordo de fuga e o CL cai.
- Usar partículas para carga de rajada em ângulo pequeno: a esteira rígida dá o mesmo número em 1/4 do tempo. As partículas valem quando o enrolamento importa.
