# Treliças em elementos finitos

## O que resolve

A cauda, o trem de pouso e os tubos são modelados como barras e vigas 3D. Cada tubo é um elemento entre dois nós, com rigidez axial, de flexão e de torção:

```
K u = F                  (estático)
(K − ω² M) φ = 0         (modos de vibração)
σ = N/A ± M·r/I          Euler: P_cr = π² E I / (K L)²
```

## Como operar

- Os nós são as junções desenhadas. Apoios: onde a cauda encosta na fuselagem ou o trem no chassi.
- Cargas vêm do diagrama V-n (cauda) e dos casos de pouso (trem).
- Leia a margem de cada barra: escoamento, flambagem de Euler e a zona de solda (trem).

## Como conferir

- **Treliça simples à mão**: método dos nós num triângulo. As forças devem bater.
- **Equilíbrio**: a soma das reações nos apoios deve ser igual à soma das cargas aplicadas. Some à mão a partir da tabela de resultados.
- **Euler**: para barra comprimida, compare P_cr com a fórmula e o fator K certo (biarticulada K = 1, engastada-livre K = 2).

## Erros comuns

- Apoio errado: engastar o que é articulado deixa a estrutura rígida demais.
- Ignorar a flambagem de tubo fino comprimido: o escoamento nunca chega.
- Um elemento por barra para modos altos. Para os primeiros modos basta; para frequências altas, subdivida.


## Juntas, apoios e ligações

Cada nó da treliça pode ser de três tipos (tabela de nós da treliça, coluna **junta**, ou as teclas `1`, `2`, `3` no modo de mover nós da vista 3D):

| Junta | O que faz | Quando usar |
|---|---|---|
| **Solda** (padrão) | As barras do nó giram juntas e passam momento entre si | Tubos colados, amarrados, soldados |
| **Parafuso** (eixo x, y ou z) | As barras giram livres em torno do eixo escolhido; o resto continua preso | Dobradiça, eixo de roda, pino passante |
| **Rótula** | Giram livres em todas as direções (só a torção em torno da própria barra continua no nó) | Terminal esférico, junta que não segura momento |

A primeira barra do nó serve de referência e as outras giram em relação a ela. Se o nó tiver engaste, apoio ou ligação rígida, todas as barras giram em relação a ele.

**Apoios** (coluna **vínculo**, teclas `4`, `5`, `0`): *engaste* prende o nó por completo; *apoio* prende só a translação. Se algum nó tiver vínculo declarado, ele substitui a regra automática (engastar todos os nós com x até o valor de "Apoio" no painel) e a análise avisa. Sem vínculo declarado, nada muda em relação às versões anteriores.

**Rodas**: nas Propriedades de cada roda, "Prender ao nó mais próximo" declara a ligação com o tubo como junta de rotação em torno do eixo y.

**Ligação com a asa** (coluna **liga a**, tecla `6`): marca os nós que prendem uma asa. A vista **Junção asa–treliça** usa esses nós.

### Mecanismo

Juntas articuladas demais deixam a estrutura sem rigidez (um mecanismo). O programa detecta e avisa: volte alguma junta para solda, acrescente uma barra em diagonal ou um apoio. Duas rótulas alinhadas numa asa, por exemplo, deixam a asa girar em torno da linha que passa por elas.

### Comparar solda, parafuso e rótula na junção da asa

A vista **Junção asa–treliça** monta a asa como viga contínua presa aos nós de ligação e resolve a mesma carga com cada tipo de junta. Leia assim:

- **Flexão transmitida**: o momento que a asa passa para a treliça em cada ligação. A solda transmite tudo; o parafuso no eixo x deixa a asa girar em torno de x (o eixo da flexão) e alivia a ligação.
- **Flecha na ponta**: o preço do alívio. Menos momento na ligação significa mais deslocamento.
- **Menor margem da treliça**: só muda se os nós de ligação não estiverem engastados; declare os apoios em outro ponto para ver a treliça trabalhar.

Hipóteses: a carga entra na linha elástica (sem torção), a asa usa o EI e o GJ da vista Asa, a ligação é pontual e sem folga.

### Resistência das juntas

A tabela "Juntas mais solicitadas" compara a força, o momento e a torção que chegam em cada nó com uma resistência estimada:

```
solda:     F_adm = τ_cola · π · d · L_c      M_adm = τ_cola · d · L_c² / 6      T_adm = τ_cola · π · d² / 2 · L_c
           uso = Kt · (F/F_adm + M/M_adm + T/T_adm)
parafuso:  corte duplo  = τ_paraf · 2 · π d_p² / 4      esmagamento = σ_esm · d_p · (d_ext − d_int)
           uso = F / min(corte, esmagamento)
margem = 1/uso − 1
```

Os valores de τ_cola, do comprimento colado L_c, do fator de concentração Kt e do parafuso são **hipóteses** editáveis no painel da vista. Trate o resultado como um mapa de onde reforçar ou ensaiar: a resistência real de uma junta colada depende do preparo da superfície e só um corpo de prova confirma.

### Fora do escopo

Junções extensas (fitas, dobradiças contínuas de aileron), folga, atrito e rigidez parcial da junta não são modelados.
