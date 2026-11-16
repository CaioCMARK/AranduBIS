# Chapeado em casca (CalculiX)

## O que resolve

Uma baia de chapeado entre duas nervuras é modelada em elementos de casca S8R (quadráticos, 8 nós), com a balsa ortotrópica (fibra na envergadura) e as nervuras rígidas no próprio plano. Três contas:

1. **Flambagem linear** (`*BUCKLE`): autovalor λ e primeiro modo.
2. **Não linear com imperfeição**: imperfeição inicial na forma do modo 1 (meia espessura), carga crescente. "Flambou" quando a pele sai uma espessura do lugar. A razão sobre λ dá o fator de imperfeição medido.
3. **Pressão mais compressão** até a carga última: abaulamento e tensões. Tsai-Hill nos eixos do material:

```
(σ₁/X)² − σ₁σ₂/X² + (σ₂/Y)² + (τ₁₂/S)² ≤ 1
```

Referência analítica para placa ortotrópica simplesmente apoiada (Lekhnitskii):

```
σ_cr = (π²/(b² t)) · [D₁₁ (mb/a)² + 2(D₁₂ + 2D₆₆) + D₂₂ (a/(mb))²]
```

## Como operar

- Precisa do CalculiX (`ccx`) instalado. O programa avisa se não achar.
- Malha automática: elemento de ~8 mm no contorno (≥ 4 por meia-onda de flambagem).
- Leia o fator em que a pele flamba contra a carga de projeto. Abaixo de 1, a pele flamba antes e a carga passa para a longarina.

## Como conferir

- Placa plana ortotrópica: o programa bate com Lekhnitskii em −2,8 %.
- Cilindro: Donnell (casca curva), canard 4,72 contra 4,98 MPa.
- Refine a malha (Configurações → Discretização → Chapeado) e veja se λ muda menos de 2 %.

## Erros comuns

- Elemento grande demais: a meia-onda não cabe e o λ sai alto (contra a segurança).
- Esquecer a pressão de sucção: o abaulamento entre nervuras muda a forma do perfil.
- Ler a flambagem linear como carga de colapso: a imperfeição real derruba bastante.
