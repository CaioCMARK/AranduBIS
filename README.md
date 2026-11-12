# AranduBIS

Programa de projeto e otimização de aeronaves de competição SAE AeroDesign. Roda no seu computador e abre a interface no navegador.

Reúne modelagem da aeronave (asas, cauda, fuselagem, treliças, trem de pouso), aerodinâmica (VLM com polares de perfil), massa e CG, propulsão com hélices APC, decolagem, estabilidade estática e dinâmica (inclusive a resposta a um comando rápido do piloto), cargas e estrutura (torção, flambagem, nervuras) e otimização com restrições e pontuação segundo as regras da competição.

## Como rodar (Windows, sem instalar nada)

1. Abra a página de [Releases](https://github.com/CaioCMARK/AranduBIS/releases/latest) e baixe **AranduBIS-windows-x64.zip** (cerca de 120 MB).
2. Clique com o botão direito no zip, escolha **Extrair tudo** e abra a pasta extraída `AranduBIS`.
3. Dê dois cliques em **AranduBIS.exe**.
4. Uma janela preta de console abre e, em seguida, o navegador abre sozinho em `http://127.0.0.1:8741/`. Se não abrir, copie esse endereço para o navegador.
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

A interface abre em `http://127.0.0.1:8741/`.

Para rodar os testes:

```bash
pip install -e ".[dev]"
python -m pytest
```

## Exemplos incluídos

- `cases/geometria/biplano/`: dois biplanos de exemplo com estrutura completa (nervuras, longarinas, treliças, trem de pouso).
- `cases/geometria/generico/`: aeronave genérica e asas com canard.
- `cases/regras/`: regras da competição (2024 a 2026) usadas na pontuação.
- `cases/otimiza/`: exemplos de problemas de otimização e seus resultados.

Na interface, abra um dos exemplos e percorra as etapas na ordem das abas.

## Dados de terceiros

- Polares de perfis calculadas com XFOIL (`data/polares.npz`).
- Curvas de desempenho de hélices APC Thin Electric (`data/apc_props`, ver `data/apc_props/FONTE.md`).
- Coordenadas de perfis de bases públicas e de seus autores (`cases/geometria`).

Esses dados pertencem aos respectivos autores e fabricantes.
