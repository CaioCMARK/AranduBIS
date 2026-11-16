# AranduBIS

Programa de projeto e otimização de aeronaves de competição SAE AeroDesign. Roda no seu computador, numa janela própria ou no navegador.

Reúne modelagem da aeronave (asas, cauda, fuselagem, treliças, trem de pouso), aerodinâmica (VLM com polares de perfil, UVLM no tempo, efeito solo), massa e CG, propulsão (hélices APC medidas e BEMT), decolagem, estabilidade estática e dinâmica (inclusive a resposta a um comando rápido do piloto), cargas e estrutura (viga da asa, torção, flambagem, flutter, vibração da cauda e do motor, treliças e cascas por elementos finitos, pouso dinâmico), fabricação (nervuras em DXF para corte a laser, STL da forma externa e do esqueleto estrutural, chapeado planificado em faixas) e otimização com restrições e pontuação segundo as regras da competição.

## Por onde começar

0. Na primeira abertura aparece o diálogo **Primeiros passos** (depois, pelo botão de mesmo nome na barra superior): ele resume as cinco etapas e abre um exemplo pronto. Cada etapa mostra também uma dica curta do que fazer a seguir.
1. Abra um exemplo (menu "Exemplos", por exemplo `monoplano/monoplano_a.json`) e percorra as etapas na ordem das abas: **1 Geometria**, **2 Análise**, **3 Estrutura**, **4 Otimizar**, **5 Resultados**.
2. Na etapa 1, clique numa seção da asa na vista 3D (ou na aba "Seção") para ver o perfil daquela estação e arrastar bordo de ataque e bordo de fuga.
3. O botão **Boas práticas** abre os manuais de cada método: o que ele resolve, como operar, como conferir o resultado e os erros comuns. Cada vista da etapa 3 tem o atalho "? teoria e boas práticas".
4. Antes de levar um número para o relatório ou para a oficina, leia "Verificar e validar" e "Discretização e convergência" nos manuais.

## Como rodar (Windows, sem instalar nada)

1. Abra a página de [Releases](https://github.com/CaioCMARK/AranduBIS/releases/latest) e baixe **AranduBIS-windows-x64.zip**.
2. Clique com o botão direito no zip, escolha **Extrair tudo** e abra a pasta extraída `AranduBIS`.
3. Dê dois cliques em **AranduBIS.exe**.
4. Uma janela preta de console abre e, em seguida, o programa abre numa janela própria. Se preferir o navegador, rode `AranduBIS.exe --navegador` e acesse `http://127.0.0.1:8741/`.
5. Para encerrar, feche a janela de console (ou aperte Ctrl+C nela).

Observações:

- O Windows pode mostrar o aviso "O Windows protegeu o computador", porque o executável não é assinado. Clique em **Mais informações** e depois em **Executar assim mesmo**.
- Na primeira análise o programa leva alguns segundos a mais, pois compila as rotinas numéricas. As seguintes são rápidas.
- Os projetos que você salvar ficam na pasta `dados`, criada ao lado de onde o programa foi aberto.
- Mantenha as pastas `cases` e `data` ao lado do `AranduBIS.exe`: elas trazem os exemplos, as regras da competição, as polares de perfis e os dados de hélices.
- Tudo roda localmente; o programa só escuta no seu próprio computador (`127.0.0.1`).

## Como rodar a partir do código

Requer Python 3.11 ou mais novo.

```bash
git clone https://github.com/CaioCMARK/AranduBIS.git
cd AranduBIS
pip install -e .
python -m aranduBIS
```

A interface abre em `http://127.0.0.1:8741/`. Opções (valem também para o `AranduBIS.exe`): `--porta 8800` muda a porta, `--sem-navegador` não abre nada sozinho, `--janela` abre numa janela própria (requer `pip install pywebview`) e `--navegador` força o navegador.

Para rodar os testes:

```bash
pip install -e ".[dev]"
python -m pytest
```

## Exemplos incluídos

- `cases/geometria/monoplano/`: dois monoplanos de exemplo com estrutura completa (nervuras, longarinas, treliças, trem de pouso). Três variantes (`monoplano_otimizado_*`) saíram do otimizador: `python cases/otimiza/roda_monoplano_generico.py 8` roda o problema genérico `cases/otimiza/monoplano_generico.json` com 8 núcleos e salva o histograma da população.
- `cases/geometria/generico/`: aeronave genérica e asas com canard (inclui `asa_canard_eixo_a_frente`, a correção da divergência do canard).
- `cases/geometria/laboratorio/`: laboratório de configurações estranhas (vertical na ponta, Burgess-Dunne, BWB tipo X-48, duto na cauda, asa em caixa, tandem), comparadas na mesma régua; ver o manual "Laboratório de configurações". `cases/otimiza/laboratorio/` pontua e otimiza cada uma pela regra SAE 2026 (`resume.py` imprime a tabela).
- `cases/regras/`: regras da competição (2024 a 2026) usadas na pontuação.
- `cases/otimiza/`: exemplos de problemas de otimização e seus resultados.

Na interface, abra um dos exemplos e percorra as etapas na ordem das abas.

## Ferramentas externas opcionais

- **CalculiX** (`ccx`): usado pela verificação do chapeado em casca. Se não estiver no PATH, aponte o executável na variável de ambiente `ARANDUBIS_CCX`; sem ele, a vista avisa e o resto do programa funciona normalmente.
- **ffmpeg**: as animações em vídeo usam o ffmpeg que vem com `imageio-ffmpeg` (já incluído no executável); sem ele, a exportação sai em GIF.

## Dados de terceiros

- Polares de perfis calculadas com XFOIL (`data/polares.npz`).
- Curvas de desempenho de hélices APC Thin Electric (`data/apc_props`, ver `data/apc_props/FONTE.md`).
- Coordenadas de perfis de bases públicas e de seus autores (`cases/geometria`).

Esses dados pertencem aos respectivos autores e fabricantes. A origem dos métodos, dos dados e dos valores padrão está em `REFERENCIAS.md`. Licença: MIT (ver `LICENSE`), exceto os dados de terceiros acima.
