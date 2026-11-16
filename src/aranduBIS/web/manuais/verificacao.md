# Verificar e validar

Duas perguntas diferentes, e qualquer revisor (banca, cliente, você mesmo daqui a um mês) faz as duas:

- **Verificação**: estou resolvendo as equações certo? (código e malha)
- **Validação**: estou resolvendo as equações certas? (o modelo representa o avião real?)

## Verificação

1. **Solução analítica conhecida**: viga em balanço, placa de Lekhnitskii, Wagner, Küssner, Theodorsen, linha sustentadora. O programa tem esses casos nos testes automáticos (`tests/`), e cada manual cita os seus.
2. **Convergência de malha**: três malhas, Richardson e GCI (ver [Discretização](#discretizacao)). Coloque a tabela no relatório.
3. **Segundo método**: a mesma conta por dois caminhos. Viga analítica contra FE de casca, VLM contra UVLM no limite estacionário.
4. **Conservação**: soma de forças e reações, simetria, circulação total.

## Validação

1. **Ensaio estático**: flecha e torção sob carga conhecida (sacos de areia).
2. **GVT**: frequências naturais da asa batendo com um martelo de borracha e medindo com acelerômetro ou celular.
3. **Voo**: velocidade de estol, distância de decolagem, ângulo de trim medidos contra o previsto.
4. **Túnel ou dados de literatura** para os perfis (polares).

A vista **Calibração** usa GVT e ensaios estáticos para ajustar EI, GJ e o raio de giração.

## Como registrar

Para cada número importante do relatório:

| Campo | Exemplo |
|---|---|
| Método | VLM, 24 × 12 painéis |
| Verificação | GCI 0,8 % (três malhas) |
| Validação | CLα do túnel: −4 % |
| Incerteza | ±5 % |

> Um número sem incerteza não é engenharia, é palpite com casas decimais.
