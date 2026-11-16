# Referências e origem dos dados

Este arquivo registra de onde vêm os métodos, os dados e os valores padrão do AranduBIS.
A primeira parte lista só o que o próprio código já cita. As colunas "Origem" ou "Fonte que usei"
são para o autor preencher com a referência exata (livro, edição, artigo, ensaio próprio).

## Métodos e normas citados no código

| Assunto | Onde | Referência citada no código | Fonte que usei (preencher) |
|---|---|---|---|
| Polares de perfil (e^N, Ncrit) | `nucleo/aero/polares.py` | XFOIL | |
| Aerodinâmica 3D (malha de vórtices) | `nucleo/aero/vlm.py` | não citada | |
| Hélice (BEMT) | `nucleo/aero/bemt.py` | Glauert; perda de Prandtl; resíduo de Ning, *Wind Energy* 17 (2014); Adkins & Liebeck, *J. Propulsion Power* 10(5) (1994) | |
| Flutter no tempo (UVLM 3D + modos) | `nucleo/estrutura/flutter_tempo.py` | Newmark (aceleração média); lápis de matrizes: Hua & Sarkar, *IEEE Trans. ASSP* 38(5) (1990); asa de Goland: Goland, *J. Appl. Mech.* 12 (1945); seção típica: Hodges & Pierce, *Introduction to Structural Dynamics and Aeroelasticity* | |
| Efeito solo no tempo (imagens no UVLM, partículas e hélice) | `nucleo/aero/uvlm.py` (`Solo`) | Katz & Plotkin (método das imagens); par de vórtices sobre o chão: Lamb, *Hydrodynamics*, §155 | |
| Hélice girante (linha sustentadora + partículas) | `nucleo/aero/rll.py` | Betz, *Z. Flugtech. Motorluftschiffahrt* 10 (1919) (enrolamento); Pedrizzetti, *J. Fluid Mech.* 245 (1992) (relaxação, opcional); Katz & Plotkin cap. 13 (esteira de anéis) | |
| Partículas de vórtice (VPM) | `nucleo/aero/vpm.py` | Winckelmans & Leonard, J. Comput. Phys. 109 (1993); Cottet & Koumoutsakos, *Vortex Methods* (2000); anel: Lamb §163, Saffman (1970) | |
| VLM não estacionário (esteira de anéis) | `nucleo/aero/uvlm.py` | Katz & Plotkin, *Low-Speed Aerodynamics*, 2ª ed., cap. 13; Wagner (aprox. R. T. Jones), Küssner (aprox. Sears-Sparks), Theodorsen (NACA TR 496) | |
| Arrasto parasita por componentes | `nucleo/aero/arrasto.py`, `limites.py` | Hoerner, Raymer | |
| Qualidades de voo | `nucleo/aero/dinamica.py` | MIL-F-8785C, classe I | |
| Raios de giro | `nucleo/configuracao.py` | Roskam | |
| Rajada de projeto | `nucleo/configuracao.py`, `web/cargas.js` | Pratt-Cooper | |
| Margem de reversão e divergência | `nucleo/configuracao.py` | FAR 23.629(c) | |
| Flutter | `nucleo/estrutura/flutter.py` | Theodorsen | |
| Torção em parede fina | `web/torcao.js` | Bredt-Batho | |
| Flambagem de casca cilíndrica | `web/flambagem.js` | Donnell | |
| Treliça da cauda | `web/cauda.js` | Euler-Bernoulli | |
| Otimização (estratégias rand-to-best e rand/1) | `nucleo/otimiza/` | não citada | |

## Dados de terceiros incluídos no repositório

- `data/polares.npz`: polares calculadas com XFOIL.
- `data/apc_props/`: curvas de desempenho de hélices APC Thin Electric, baixadas do site do fabricante (ver `data/apc_props/FONTE.md`). Conferir os termos de uso da APC antes de redistribuir.
- `cases/geometria/naca4412_cp_expt_coles_wadcock.dat`: dado experimental de Coles e Wadcock (AIAA J. 17(4), 1979), obtido no NASA Turbulence Modeling Resource. A fonte está no cabeçalho do arquivo.
- Outras coordenadas de perfis em `cases/geometria`: bases públicas e seus autores.

O AranduBIS não inclui o AVL (licença GPL). Quem quiser usá-lo informa o caminho do executável nas configurações.

## Valores padrão: todos vêm da literatura ou de uma função

Nenhum padrão do programa é calibrado em uma aeronave ou usuário. Os valores e fórmulas estão em
`nucleo/referencias.py`, e as opções com valor automático (marcadas na tela de configurações) são
recalculadas a partir das outras. As que vêm direto da literatura (fator de segurança, rajadas, fator de pouso,
materiais, atrito etc.) mostram a fonte e o botão "referência". Qualquer uma pode receber o valor do usuário, e
"voltar ao automático" ou "voltar ao valor de referência" descarta esse valor.

### Critério de cargas: 14 CFR Parte 23, categoria normal

| Grandeza | Padrão | Fonte |
|---|---|---|
| Vc do V-n | velocidade de cruzeiro da análise (entrada do projeto) | não há valor universal |
| Vd | 1,25 Vc | 14 CFR 23.335(b)(1): Vd não menor que 1,25 Vc |
| n máximo de manobra | 2,1 + 24000/(W + 10000), W em lb, teto 3,8 (3,8 para qualquer massa até 1868 kg) | 14 CFR 23.337(a)(1) |
| n mínimo | −0,4 × n máximo | 14 CFR 23.337(b)(1) |
| Rajada em Vc / em Vd | 50 ft/s = 15,24 m/s / 25 ft/s = 7,62 m/s | 14 CFR 23.333(c)(1) |
| Fator de segurança | 1,5 | 14 CFR 23.303 |
| Fator de pouso | 2,67 (piso do fator de inércia) | 14 CFR 23.473(g) |
| Giro no solo (vertical, lateral) | 1,0 e 0,5 do peso | 14 CFR 25.495 |
| Margem aeroelástica | 1,2 × Vd | 14 CFR 23.629(c) |
| Fator K de Euler das barras | 1,0 (articulada, conservador) | Euler |

Aviso: a rajada de 15,24 m/s é a de uma aeronave tripulada. Numa aeronave de 15 m/s ela é severa e a carga
fica limitada pelo estol; se o seu regulamento ou o seu local justificar outro valor, fixe-o.
A Parte 23 também pede Vc ≥ 33 √(W/S) nós (23.335(a)), que numa aeronave pequena fica muito acima da velocidade
de voo; o programa usa a velocidade que você informa, e esse requisito não é verificado.

### Atmosfera e pista

| Grandeza | Padrão | Fonte |
|---|---|---|
| Densidade do ar | ISA na altitude-densidade (0 m dá 1,225 kg/m³): ρ = 1,225 (1 − 2,25577·10⁻⁵ h)^4,25588 | atmosfera padrão |
| Atrito de rolagem μ | 0,05 (grama firme); concreto seco 0,02 a 0,05, terra firme 0,04, grama macia 0,07 | USNTPS, Flight Test Manual, cap. 9, tab. 9.2 |

### Materiais (valores médios, não admissíveis estatísticos)

| Grandeza | Padrão | Fonte |
|---|---|---|
| Balsa E (flexão) | 3,4 GPa | Wood Handbook (FPL-GTR-190) cap. 5, balsa a 12 % de umidade, densidade relativa 0,17 |
| Balsa compressão paralela | 14,9 MPa | idem |
| Balsa E transversal | 1,5 % do E (tangencial) ou 4,6 % (radial); padrão 1,5 % | Wood Handbook tab. 5-1 (ET/EL, ER/EL) |
| Balsa G | 3,7 % do E (GLT); GLR seria 5,4 % | Wood Handbook tab. 5-1 |
| Balsa tração paralela | 19,3 MPa (2800 psi, balsa de 160 kg/m³) | Model Aviation, "Simple Structural Test Techniques for RC Aircraft" |
| Balsa cisalhamento paralelo | 1,9 MPa (balsa de 150 kg/m³) | Kotlarewski et al., Eur. J. Wood Prod. 2016, doi:10.1007/s00107-015-0983-0 |
| Balsa compressão transversal YC | 1,1 MPa (densidade média) | Kotlarewski et al., Eur. J. Wood Prod. 74 (2016) 83 |
| Balsa tração transversal YT | 1,1 MPa | **hipótese**: igual à compressão transversal, sem valor publicado acessível; ensaie |
| Carbono YT, YC | 48, 200 MPa | AS4/3501-6, Soden et al. 1998 |
| Balsa Poisson ν_LT | 0,488 (ν_TL = 0,009) | Wood Handbook tab. 5-2 |
| Carbono E1, E2, G12, ν12, XT, XC, S | 126 GPa, 11 GPa, 6,6 GPa, 0,28, 1950, 1480, 79 MPa | lâmina UD AS4/3501-6: Soden, Hinton & Kaddour, Compos. Sci. Technol. 58 (1998) 1011 |
| Spruce (Sitka) E, X, XC, S | 10,8 GPa, 70 MPa (MOR), 38,7 MPa, 7,9 MPa | Wood Handbook tab. 5-3 (12 % de umidade) |
| Spruce G, ν_LT, densidade | 0,061 E, 0,467, 450 kg/m³ | Wood Handbook tab. 5-1, 5-2 e 5-3 (densidade relativa 0,40) |
| Fator de imperfeição do chapeado | automático por painel: γ = 1 − 0,901 (1 − e^(−φ)), φ = √(R/t)/16 | NASA SP-8007, eq. 45 (cilindros isotrópicos em compressão axial) |

Limites que o usuário precisa conhecer: a balsa varia de 2 a 3 vezes com a densidade, então os valores médios
acima não substituem o ensaio do seu lote (use "qualidade da balsa" abaixo de 1). A lâmina de carbono é ideal;
um tubo enrolado real é menos rígido e menos resistente, e o dado do fabricante do tubo deve substituir estes.
Na flambagem de alma o Poisson entra como a média geométrica √(ν_LT ν_TL), a forma usual para placa ortotrópica.
A tração paralela do spruce usa o módulo de ruptura, que fica abaixo dela (lado seguro). O SP-8007 vale para cilindros completos; aplicá-lo ao painel curvo de uma asa é uma
aproximação conservadora.

### Longarinas

| Tipo | O que entra na seção | Torção |
|---|---|---|
| alma + tubinhos | alma de madeira na altura do perfil e os tubos de reforço como mesas | caixa-D (Bredt-Batho) quando o chapeado chega à alma |
| tubo | tubo centrado na linha média (ou junto ao extradorso/intradorso) | G J do tubo, J = π (de⁴ − di⁴)/32 |
| viga caixão / I | duas almas (ou uma, viga I) entre mesas coladas no extradorso e no intradorso | célula retangular de Bredt-Batho; viga I é seção aberta |

Flexão de viga composta: cada peça entra com E A (z − z_LN)² e a própria inércia, e a tensão é verificada na fibra mais
externa de cada peça (σ = M E (z − z_LN)/EI). O cortante se divide entre almas e tubo na proporção de G × área
efetiva; no tubo τ_máx = 2V/A (parede fina). Com caixa-D e viga caixão juntas, as rigidezes de torção são somadas
como células em paralelo, uma aproximação da seção multicelular. O modelo de casca (FEM) ainda só representa
alma + tubinhos.

### Chapeado em casca (CalculiX)

A vista Nervuras e flambagem pode simular a baia crítica no CalculiX (GPL, programa externo: `ccx` no PATH ou em
ARANDUBIS_CCX). Modelo: caixa-D entre duas nervuras em S8R, balsa ortotrópica com a fibra na envergadura, nervuras rígidas
no próprio plano, tensão de flexão linear em z vinda da análise de viga, sucção no extradorso. Três contas: flambagem
linear (*BUCKLE); compressão não linear com imperfeição de 0,5 t na forma do 1º modo, com o critério "a pele sai uma
espessura do lugar"; e pressão mais compressão até a carga de ruptura (abaulamento). A pressão é hipótese: salto de
pressão da placa plana, Δp(ξ) = (2/π)·√((1−ξ)/ξ)·l/c, médio na região do chapeado, metade no extradorso.

Ruptura da pele: as tensões das faces da casca são levadas aos eixos da balsa (1 = fibra, na envergadura; 2 = tangente
ao contorno) e verificadas por Tsai-Hill, (σ1/X)² − σ1σ2/X² + (σ2/Y)² + (τ12/S)² ≤ 1, com X e Y de tração ou compressão
conforme o sinal. Na balsa a parcela transversal costuma dominar: a resistência de través é uma ordem de grandeza menor.

Validação: placa ortotrópica de balsa simplesmente apoiada, CalculiX contra Lekhnitskii, −2,8 %; baia do canard de
exemplo, casca sem imperfeição 4,72 MPa contra 4,98 MPa de Donnell. Com a rigidez transversal da balsa (1,5 % da axial),
a curvatura ajuda pouco depois que há imperfeição: o fator medido pode ficar bem abaixo do SP-8007, que é de cilindros
isotrópicos.

### Flutter com aileron

O aileron é o terceiro grau de liberdade de Theodorsen (NACA TR 496): rotação rígida sobre a dobradiça na faixa do aileron,
com as forças não estacionárias completas (sustentação, momento no eixo elástico e momento de charneira, constantes T1 a T13)
somadas por faixa e projetadas nos modos da semi-asa (método p-k). Validações: massa aparente simétrica; comando muito rígido
volta ao caso sem aileron (1 %); aileron desbalanceado e frouxo flutua a baixa velocidade e o balanceado não (comportamento
clássico). Padrões do aileron: massa pela fração de área da semi-asa (estimativa, pese o seu); CG a 1/3 da corda do aileron
atrás da dobradiça e raio de giração √(1/6) da corda (cunha de balsa); comando frouxo (0 Hz), o pior caso.
A massa da asa entra estação por estação, com servos e outras massas pontuais que estiverem na planta dela.

### Aerodinâmica não estacionária (UVLM)

Mesma malha de anéis do VLM. A cada passo a esteira ganha uma fileira no bordo de fuga: a primeira tem a circulação do anel do
bordo de fuga no mesmo instante (Kutta implícito, entra na matriz) e vai até 0,3 V·dt atrás dele (Katz & Plotkin 13.8); as
outras andam com a corrente (esteira rígida) ou com a velocidade local (esteira livre, núcleo de 0,2 % da corda). Forças:
Kutta-Joukowski na circulação líquida de cada aresta, com a velocidade local, mais ρ·dΓ/dt·A·n. Esteira longa é cortada e a
última fileira vira uma cauda de 20 envergaduras (fecha as pernas como a ferradura estacionária). Movimentos e rajadas
linearizados. Validações em `tests/test_uvlm.py`: limite estacionário = VLM (1 %); Wagner a 4 % (AR 60, s de 4 a 10); Küssner a
3 % (s de 3 a 10, 8 painéis na corda); Theodorsen em mergulho, k = 0,4, a 6 % na amplitude e 3° na fase (o erro cai à metade
quando os painéis na corda dobram). Rajada 1-cos com H = 25 cordas: 14 CFR 23.333 / CS-23.

### Discretização (automática ou do usuário)

Cada análise pede a malha a `nucleo/discretizacao.py`: vale o valor fixado em Configurações → Discretização ou a regra
automática, que registra o motivo (a interface mostra no rodapé "malha"). Regras e de onde vêm:
VLM na envergadura pelo alongamento (`n_span_recomendado`); VLM na corda 4 em perfil simétrico e 12 em arqueado (CL de
arqueamento do NACA 4412 converge como ~0,55/n: −14 % com 4, −7 % com 8, −3 % com 16 painéis, extrapolado por Richardson);
estrutura com ≥ 2 estações por baia de nervura; flutter com 8 modos e aviso quando o modo mais alto fica abaixo de 3× a
frequência de flutter; chapeado com elemento de ~8 mm; UVLM harmônico com erro ≈ 1,2·k/n_chord. Limites fixos de passos e
painéis viraram estimativa de tempo e memória contra um orçamento configurável. Estudo de convergência do VLM em três malhas
com Richardson e GCI (Roache, Fs = 1,25). A deflexão de flap/aileron no VLM passou a pesar pela fração de cada painel atrás
da charneira (antes era tudo-ou-nada e a autoridade oscilava com n_chord; com 4 painéis e o critério antigo, o p·b/2V do exemplo B saía 0,18 contra ~0,27
convergido). Manuais de boas práticas em `web/manuais/`.

### Esteira de partículas de vórtice

Biot-Savart regularizado com núcleo gaussiano (padrão) ou algébrico de Winckelmans, estiramento no esquema clássico
(α·∇)u com o gradiente analítico do núcleo (e diferenças finitas para a parte dos anéis), difusão por espalhamento de
núcleo. As 3 primeiras fileiras da esteira continuam anéis; ao converter, a aresta da frente fica como segmento de
fronteira, para a circulação líquida perto da asa ficar num segmento só. Núcleo σ = 1,3·V·dt. Fusão aos pares das
partículas velhas da mesma linha de vórtice (α soma, σ dobra) a cada 8·2ⁿ passos. Validações em `tests/test_vpm.py`:
gradiente analítico contra diferenças finitas (1e-10); campo no eixo de um anel longe do núcleo contra a fórmula clássica
(1e-4); velocidade do anel fino no eixo do núcleo contra U = Γ/(4πR)[ln(8R/σ) − 1 − (ln 2 − γ)/2] (0,1 %; a constante sai
de ln(8R/s) − 1 de Kelvin com a média de ln s num tubo gaussiano); anel marchando conserva raio, impulso e |α|; fusão
conserva a vorticidade total; asa retangular com esteira de partículas contra a mesma com anéis livres (CL no tempo a
0,5 %); vórtice de ponta migra para dentro da semienvergadura.

### Hélice: BEMT e sopro

BEMT com perdas de ponta e de cubo de Prandtl; ângulo de entrada de cada faixa pelo resíduo de Ning (2014) em bisseção
vetorizada (raiz garantida, vale parada); Re das polares do banco (XFOIL), estendidas além do estol por Viterna. Geometria
da pá: forma média das APC Thin Electric (c/R em 0,75 R = 0,135, como as APC E 10x7 e 11x7 do UIUC, Brandt 2005, tab.
A.1; demais pontos da corda são forma típica, a conferir com a geometria medida) e passo geométrico constante pelo nome.
Verificação: a análise BEMT da hélice de mínima perda de Adkins & Liebeck devolve T, P e η do projeto a 1 % (sem e com
arrasto do perfil); o disco atuador é teto da eficiência. Contra a curva da APC (cálculo do fabricante, não ensaio) a forma
típica fica a ~15 %. Sopro: disco atuador com cilindro de vórtice semi-infinito (v_a dobra longe), contração anel por anel
pela vazão e rotação pelo momento angular; entra no VLM como velocidade local. Falta a validação contra túnel (UIUC vol. 4).

### Hélice girante: linha sustentadora + partículas

Cada pá é uma linha sustentadora radial (elementos em cosseno) que gira dψ por subpasso; a circulação de cada elemento
sai da polar com a velocidade local (corrente + asa + partículas + pás) por ponto fixo sub-relaxado com corte do fator
quando o resíduo cresce (o mapa Γ → Γ′ tem um modo serrilhado de fator < −1 nos elementos estreitos). A esteira das pás:
2 fileiras de anéis e depois partículas na mesma nuvem da asa, com a fronteira no último anel. Depois de meia volta, as
partículas de cada subpasso de cada pá enrolam em ponta (pernas de fora do pico de Γ, no centroide: Betz), raiz e
radiais; a fusão ao longo da linha (a da esteira da asa) não vale em linha curva: pela corda ela puxa a partícula para
dentro e soma uma volta inteira num vetor axial (o sopro na asa caía a um terço). Para linha curva, `Particulas.funde`
aceita `arco_max` (fusão no meio do arco, |α| = soma dos módulos), não usado na hélice. A asa marcha um passo do UVLM a
cada n_sub subpassos. Verificação (tests/test_rll.py): isolada, T e P a 4 % do BEMT; velocidade axial no disco (média
azimutal) a 15 % do BEMT com F de Prandtl; fluxo de quantidade de movimento 1,5 D atrás (T = ρ∫(V+u)u dA) a 10 % da
tração das pás com dψ = 10°, convergindo em 1ª ordem no dψ (10 % com 14,6°, 6 % com 10°, 5 % com 7,5°: núcleo ∝ arco do
subpasso); trator na frente de uma asa: ΔCL a 30 % do BEMT + sopro no VLM e giro trocado espelha a carga. A relaxação de
Pedrizzetti, testada a 0,3 por subpasso, espalhou a esteira e subiu a tração 20 % em 10 voltas: fica desligada.

### Flutter no tempo (UVLM 3D)

Os mesmos modos, massas e rigidezes do p-k (`flutter.estrutura_modal`), marchados com o UVLM de esteira rígida
(pequena amplitude). O modo r desloca o ponto (x, y) de w = −[h_r(y) + (x − x_ea)α_r(y)], com h para baixo e α nariz para
cima. O aileron gira os painéis atrás da dobradiça, em modos antissimétricos. Condição de contorno pela velocidade
equivalente ẇ + V ∂w/∂x. Forças generalizadas: Kutta-Joukowski no meio das arestas e ρ ∂Γ/∂t A n no centro dos painéis,
projetados nos modos.

Acoplamento forte com Newmark de aceleração média e relaxação de Aitken. O amortecimento sai do histórico pelo lápis de
matrizes (ordem 2N + 4). Passo: o menor entre c/(4V) e 1/24 do período do modo de flutter.

Durante a verificação apareceu o sinal trocado do termo de taxa em `movimento_arfagem`: pontos atrás do eixo subiam
quando o nariz subia. A fase da sustentação saía atrasada 16° em vez de adiantada 14°. Corrigido, com teste.

Os modos são da semi-asa; o UVLM tem as duas metades e a força generalizada é a metade da soma. Até a v15 entrava a soma
inteira (aerodinâmica em dobro contra a estrutura): a Goland dava 132 m/s, abaixo de todas as referências 3D. Corrigido.

Divergência: polo real (sem oscilar) de maior Re s com energia ≥ 2 % da do modo mais forte, em cada marcha; V_D onde ele
troca de sinal. E a estática 3D: Q0 (força generalizada em regime por modo, a V_ref) por N marchas curtas; V_D = V_ref/√μ,
μ o maior autovalor real positivo de Ks⁻¹Q0, nas duas simetrias. Asa engastada, como a aba Torção.

Verificação: estrutura sem ar com ζ = 0; seção típica de alongamento 40 a 4 % do p-k de Theodorsen. Asa de Goland: p-k
137 m/s (literatura 137,2); UVLM 3D ~162 m/s a ~67,5 rad/s (160 a 163 de 16 × 8 a 32 × 12 painéis), 2 % abaixo do UVLM do
SHARP (165 m/s); as outras referências 3D ficam abaixo (142,9 CFD a Mach 0,42; 146,6 painel de Morino). Divergência: na
asa voadora canard o polo real das marchas cruza zero a 16,05 m/s e a estática da mesma simetria dá 16,02 m/s; faixas ×
3D: alongamento 40, 1,06; Goland, 300 × 252 m/s (fórmula fechada π²GJ/(4L²ec²a) = 252,4, igual à aba Torção).

Também na verificação: a matriz de influência do UVLM usava o núcleo singular e a esteira explícita o regularizado. O
segmento que dividem não cancelava no regime, e com V Δt do tamanho do painel o CL caía 0,6 % e o centro de pressão andava
0,002 c para a frente (V_D da canard: 3 %). Agora a matriz usa o mesmo núcleo; o regime não depende do passo (teste).

### Efeito solo no tempo

Chão plano paralelo à corrente por imagens: segmento A→B com Γ ganha A′→B′ com −Γ; partícula (x, α) ganha (x′, −Rα),
R = I − 2nnᵀ. Entra na matriz (corpo + Kutta implícito, refeita a cada passo se a altura muda), na esteira de anéis, nas
partículas (que são empurradas de volta se o Euler explícito as levar para baixo do chão), nas forças e na hélice girante
(a pá enxerga a própria imagem no ponto fixo). Altura variando: o ar relativo ganha −ḣ n. Verificação
(tests/test_solo_uvlm.py): velocidade normal no chão 1e-14; altura fixa contra o VLM estacionário com solo (VLM.arfada)
a 1 % até h = 0,4 c; subida a 0,3 m/s contra o quase estático (VLM com solo em h(t) e α − atan(ḣ/V)) a 0,6 %; par de
vórtices de partículas sobre o chão: 1/y² + 1/z² constante a 0,5 % (Lamb §155).

### Estimativa de tempo pela máquina

Velocidade medida no computador do usuário (segmento de vórtice, par de partículas com gradiente, segmento com gradiente
analítico) × eficiência 0,75 (estimativa contra tempo real do UVLM rígido, livre, de partículas e da hélice girante na
máquina de referência: ±30 %). Gradiente analítico do segmento regularizado (substitui 7 avaliações de diferenças
finitas, 3,6× mais rápido, igual a 3e-10) e núcleo gaussiano como Biot-Savart puro além de 6 núcleos (erro < 1e-7,
3,3× mais rápido com acumulação local).

### Calculadora de peso vazio

Estrutura desenhada (geometria × densidade), cola (hipótese: 10 % da madeira), motor (catálogo), bateria (energia ÷ 133 Wh/kg,
média de packs 6S 1500 mAh do mercado, 218 a 283 g), servos (um por superfície e por lado) e hélice, ESC, receptor e cabos
(informados). Filmes de entelagem: Oralight 36 g/m², Oracover 64 a 109 g/m² conforme a cor (ficha técnica do fabricante).

### Laboratório de configurações

Régua de comparação (comparativo.py): mesmo peso e envergadura, CG a 10 % de margem estática do ponto neutro de cada configuração, trimado (empenagem ou canard inteiros, elevon ou washout). Eficiência de envergadura e_b = L²/(π q b² D_i). Checagem independente: biplano reto contra a conta de Trefftz com asas elípticas (Prandtl 1924, "Induced drag of multiplanes", NACA TN 182, e Munk 1923, "The minimum induced drag of aerofoils", NACA TR 121), dentro de 2 % para h/b de 0,05 a 0,25. Winglet: ganho de 10 a 20 % do induzido a sustentação constante (Whitcomb 1976, NASA TN D-8260; Kroo 2005, "Nonplanar wing concepts for increased aircraft efficiency"). Asa em caixa: Prandtl 1924 (a mesma nota técnica). Empuxo estático de ducted fan: teoria do disco com área de saída A_e, T = (2 ρ A_e P²)^(1/3) (Küchemann e Weber 1953, "Aerodynamics of Propulsion"), figura de mérito padrão 0,7 (estimativa; meça o seu). Arrasto da deriva: placa plana, C_f = 0,0065 sobre 2,2 × a área (estimativa); peso 0,45 kg/m² (balsa de 3 mm com filme: estimativa). Washout de asa voadora com perfil de Cm₀ ≥ 0 (REFLEX-10 gerado em monta_asa_canard.py; Nickel e Wohlfahrt 1994, "Tailless Aircraft in Theory and Practice"). Burgess-Dunne 1917 e BWB tipo X-48 (corpo grosso e muito enflechado): geometrias de projeto, não cópias de desenhos de nenhum avião real.

### Hipóteses de modelagem que continuam como estimativa

`estrutura.cl_min_rel`, `estrutura.x_ca_c`, `estrutura.x_apoio`, `estrutura.CL_max_h`, `estrutura.raio_inercia`,
`estrutura.atrito_pouso`, `estrutura.raio_solda` (0 = junta pontual) e os de dinâmica de voo. São hipóteses do
modelo, descritas como tal na tela, e não valores de nenhuma aeronave.

### Entradas do projeto (sem valor universal)

Velocidades de decolagem e de cruzeiro, CL alvo, massa de projeto na otimização, distância de pista e altura
do obstáculo, potência e baterias seguem o regulamento da competição do ano ou o seu projeto.

Pontuação e otimização das configurações do laboratório (laboratorio_otim.py): estrutura e massas do exemplo asa_canard.json, dimensionadas pela parede dos tubos; regra SAE 2026 do programa; busca por evolução diferencial (Storn e Price 1997, *J. Global Optimization* 11) com violação das restrições normalizada com escala mínima de 0,1; Cn_β ≥ 0,03 por diferença centrada de β = ±0,5° no VLM. Massas e densidade de casca das derivas são estimativas (ver o manual do laboratório); flutter e divergência ficam fora da busca.
