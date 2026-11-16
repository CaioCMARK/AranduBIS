# VLM: malha de vórtices

## O que resolve

Escoamento potencial, incompressível e linearizado em torno de superfícies finas. Cada painel tem um anel de vórtice: o lado da frente fica a 1/4 do painel e o ponto de controle a 3/4 (a regra 1/4–3/4, que reproduz a placa plana 2D exatamente com um painel só). A condição de contorno é velocidade normal nula em cada ponto de controle:

```
Σⱼ Aᵢⱼ Γⱼ = −(V∞ + Ω×r)·nᵢ          A = matriz de influência (Biot-Savart)
F = ρ Γ (V × dl)                     Kutta-Joukowski em cada segmento
```

Daí saem CL, CDi (arrasto induzido), Cm, ponto neutro e a distribuição de carga na envergadura. A esteira é plana e semi-infinita, saindo do bordo de fuga.

**O que não está no VLM:** viscosidade (arrasto de perfil e estol vêm das polares 2D), espessura, descolamento, sustentação de vórtice de bordo (asa de AR < 1) e compressibilidade.

## Como operar

- Desenhe as superfícies com as seções reais (corda, incidência, diedro, perfil). O arqueamento do perfil entra como geometria da malha.
- Deixe a malha no automático: 24 faixas em asa de AR ≥ 4, 48 em empenagem curta; 12 painéis na corda em perfil arqueado.
- Ailerons, profundor e flaps: a deflexão entra pela fração de cada painel atrás da charneira. A autoridade converge com a malha na corda.

## Como conferir

1. **Teste de convergência** (rodapé → malha → botão). Olhe o GCI de CLα, ponto neutro e CL.
2. **Teoria de linha sustentadora** numa asa retangular de AR alto: CLα ≈ 2π·AR/(AR + 2) por rad. Na elíptica, CDi = CL²/(π·AR).
3. **Simetria**: a carga na envergadura deve ser simétrica em β = 0, sem degrau entre faixas vizinhas.
4. **Efeito solo**: o CDi cai na razão de McCormick (16h/b)²/(1 + (16h/b)²).

## Erros comuns

- **Esteira de uma superfície passando rente aos pontos de controle de outra** (canard alinhado com a asa, deriva sobre a esteira). A velocidade induzida fica quase singular e o resultado passa a depender da malha. O programa avisa. Desloque alguns milímetros em z ou case as malhas.
- **Junção de winglet com nós desalinhados**: a circulação "vaza" e aparece um vórtice falso. A ponta de uma superfície deve começar exatamente onde a outra termina, com a mesma corda.
- **Seções muito próximas** (estação duplicada) fazem faixas vizinhas de tamanhos muito diferentes, e a carga oscila.
- **Ler o CL acima do estol**: o VLM não sabe o que é estol. O limite vem do cl máximo das polares, comparado faixa a faixa.
- **Asa de AR < 1**: subestima o CL em ângulos altos. Use com cuidado e compare com dados de túnel.

Veja também: [Discretização e convergência](#discretizacao), [UVLM](#uvlm).
