# Viga da asa: flexão e torção

## O que resolve

A semi-asa é uma viga em balanço engastada na raiz. Em cada estação, a seção (longarina, mesas, tubos, chapeado) vira uma viga composta:

```
EI = Σ Eᵢ [Iᵢ + Aᵢ (zᵢ − z_LN)²]          z_LN = Σ Eᵢ Aᵢ zᵢ / Σ Eᵢ Aᵢ
σᵢ = Eᵢ · M · (z − z_LN) / EI             tensão na fibra mais externa de cada parte
V(y) = ∫ᵧ^(b/2) q dy      M(y) = ∫ᵧ^(b/2) V dy
```

Torção, com o fluxo de cisalhamento de Bredt numa célula fechada (caixa-D):

```
q = T / (2 A_m)          GJ = 4 A_m² / ∮ ds/(G t)
```

Caixa aberta (chapeado termina antes da longarina) tem GJ duas a três ordens de grandeza menor.

**Hipóteses:** viga de Euler-Bernoulli (seção plana), material linear, sem enflechamento. A pele em compressão só trabalha até flambar: ver [Chapeado](#chapeado).

## Como operar

1. Carregue as cargas do diagrama V-n (vista Cargas). O fator de segurança e os materiais vêm de Configurações.
2. Desenhe a longarina: alma com tubos, tubo de carbono ou caixão.
3. Leia as **margens**: margem = admissível / atuante − 1. Positiva passa, negativa falha.
4. Depois rode a torção, a reversão de comando e o flutter.

## Como conferir

- **Viga de seção constante com carga uniforme**: flecha na ponta = q L⁴ / (8 EI), fletor na raiz = q L²/2.
- **Elementos finitos da própria vista** (Torção → verificação FE): a razão FE/analítica perto de 1 confirma a integração.
- **Ensaio estático**: pendure sacos de areia na distribuição de sustentação e meça a flecha. A vista Calibração ajusta EI e GJ pelo ensaio.
- **Estações**: o automático põe ≥ 2 estações por baia de nervura. Se o fletor muda de degrau num ponto (fim do chapeado, junção), refine e veja se o pico muda.

## Erros comuns

- Balsa não é isotrópica. E transversal ≈ 1,5 % do longitudinal, e o critério de falha usado é Tsai-Hill.
- Tubo de carbono colado em balsa: a colagem é o elo fraco. Confira o cisalhamento na interface.
- Torção esquecida: chapeado que acaba antes da longarina abre a caixa e derruba GJ (reversão e flutter caem junto).
- Valores médios de material não são admissíveis: use os fatores de qualidade e o fator de segurança.
