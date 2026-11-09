from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

class ConfiguracaoInvalida(ValueError):
    pass

@dataclass(frozen=True)
class Opcao:
    chave: str
    grupo: str
    rotulo: str
    padrao: object
    ajuda: str
    escolhas: tuple = ()
    minimo: float | None = None
    maximo: float | None = None
    habilita: str = ""

    @property
    def tipo(self) -> str:
        if self.escolhas:
            return "escolha"
        if isinstance(self.padrao, bool):
            return "booleano"
        return "texto" if isinstance(self.padrao, str) else "numero"

OPCOES: tuple[Opcao, ...] = (
    Opcao("polares.fonte", "Polares", "De onde vêm as polares", "banco",
          "banco: usa as polares já calculadas (rápido, funciona sem instalar nada). "
          "xfoil: calcula cada perfil na hora. avl: roda o AVL na aeronave inteira "
          "(mais fiel ao conjunto, exige o AVL instalado).",
          escolhas=("banco", "xfoil", "avl")),
    Opcao("polares.avl_caminho", "Polares", "Caminho do AVL", "",
          "Arquivo avl.exe. O programa não traz o AVL (licença GPL): "
          "baixe-o e aponte aqui.", habilita="polares.fonte=avl"),
    Opcao("polares.xfoil_caminho", "Polares", "Caminho do XFOIL", "",
          "Arquivo xfoil.exe, só se a fonte for xfoil.", habilita="polares.fonte=xfoil"),
    Opcao("polares.ncrit_modo", "Polares", "Ncrit", "auto",
          "auto: o programa escolhe pelo nível de turbulência do túnel ou do ar. "
          "fixo: usa o valor abaixo em todas as polares.",
          escolhas=("auto", "fixo")),
    Opcao("polares.ncrit", "Polares", "Valor fixo de Ncrit", 9.0,
          "Fator de amplificação da transição (e^N). 9 = ar calmo padrão; "
          "valores menores antecipam a transição.", minimo=1.0, maximo=14.0,
          habilita="polares.ncrit_modo=fixo"),
    Opcao("polares.mach_critico_modo", "Polares", "Mach crítico", "auto",
          "auto: calculado do perfil. fixo: usa o valor abaixo.",
          escolhas=("auto", "fixo")),
    Opcao("polares.mach_critico", "Polares", "Valor fixo de Mach crítico", 0.7,
          "Acima disto a correção de compressibilidade deixa de valer.",
          minimo=0.3, maximo=1.0, habilita="polares.mach_critico_modo=fixo"),
    Opcao("polares.reynolds_minimo", "Polares", "Reynolds mínimo da tabela", 40000.0,
          "Abaixo disto o programa extrapola e avisa.", minimo=1e4, maximo=1e6),
    Opcao("polares.ncrit_banco", "Polares", "Ncrit do banco de polares", "4",
          "Qual variante do banco usar: 4 = ar livre turbulento, 7 = ar mais limpo. "
          "Se o perfil só existe numa delas, a outra é usada e a tela avisa.", escolhas=("4", "7")),
    Opcao("analise.velocidade_voo", "Padrões da análise", "Velocidade de decolagem (m/s)", 12.0,
          "Usada no Reynolds de cada faixa e no CL máximo. A aeronave costuma decolar perto de 12 m/s.",
          minimo=3.0, maximo=60.0),
    Opcao("analise.velocidade_cruzeiro", "Padrões da análise", "Velocidade de cruzeiro (m/s)", 15.0,
          "Usada no equilíbrio e na estabilidade.", minimo=3.0, maximo=60.0),
    Opcao("analise.rho", "Padrões da análise", "Densidade do ar (kg/m³)", 1.1,
          "1,225 ao nível do mar; 1,06 a 1330 m de altitude-densidade.", minimo=0.5, maximo=1.4),
    Opcao("analise.CL_alvo", "Padrões da análise", "CL a equilibrar", 0.8,
          "CL em que a aeronave deve voar equilibrada (cruzeiro).", minimo=0.1, maximo=3.0),
    Opcao("analise.efeito_solo", "Padrões da análise", "Efeito solo na corrida", True,
          "Considera o chão (imagem do sistema de vórtices) no CL e no CD da corrida e da subida."),
    Opcao("tracao.potencia_w", "Padrões da tração", "Potência na bateria (W)", 600.0,
          "Limite do regulamento da bateria. Muda de ano para ano.", minimo=50.0, maximo=5000.0),
    Opcao("tracao.V_max", "Padrões da tração", "Tração até a velocidade (m/s)", 18.0,
          "Fim da curva T(V). A aeronave raramente passa de 15 m/s.", minimo=5.0, maximo=60.0),
    Opcao("tracao.v_celula", "Padrões da tração", "Tensão por célula sob carga (V)", 3.6,
          "Hipótese para a tensão do pack (células × este valor). Meça a sua bateria.", minimo=2.8, maximo=4.2),
    Opcao("tracao.perdas_realistas", "Padrões da tração", "Perdas realistas do motor", True,
          "Enrolamento a 70 °C, perdas em vazio crescendo com a rotação e ESC com curva."),
    Opcao("tracao.motor", "Padrões da tração", "Motor inicial", "Scorpion SII-4035-330",
          "Nome exato do motor do catálogo."),
    Opcao("tracao.helice", "Padrões da tração", "Hélice inicial", "22x10E",
          "Nome exato da hélice APC, ex. 22x10E."),
    Opcao("decolagem.pista_m", "Padrões da decolagem", "Distância até o obstáculo (m)", 55.0,
          "Muda de ano para ano e de regulamento.", minimo=5.0, maximo=500.0),
    Opcao("decolagem.obstaculo_m", "Padrões da decolagem", "Altura do obstáculo (m)", 0.9,
          "Altura que a aeronave precisa ter nessa distância.", minimo=0.0, maximo=10.0),
    Opcao("decolagem.altitude_densidade_m", "Padrões da decolagem", "Altitude-densidade (m)", 1330.0,
          "Define a densidade do ar da decolagem (atmosfera padrão).", minimo=-500.0, maximo=5000.0),
    Opcao("decolagem.mu", "Padrões da decolagem", "Atrito de rolagem μ", 0.062,
          "Depende da pista e das rodas. Meça o da sua.", minimo=0.005, maximo=0.5),
    Opcao("decolagem.d_alpha_rotacao", "Padrões da decolagem", "Giro até sair do solo (°)", 6.0,
          "Quanto a atitude muda da corrida até a saída.", minimo=0.0, maximo=30.0),
    Opcao("decolagem.taxa_rotacao", "Padrões da decolagem", "Taxa de rotação (°/s)", 20.0,
          "Velocidade com que o piloto levanta o nariz.", minimo=1.0, maximo=200.0),
    Opcao("decolagem.margem_rotacao", "Padrões da decolagem", "Início da rotação (× V de estol)", 1.02,
          "Fração da velocidade de estol em que começa a puxar.", minimo=0.5, maximo=2.0),
    Opcao("avl.n_secoes", "Análise", "Painéis em envergadura (AVL)", 20,
          "Mais painéis, mais fiel e mais lento.", minimo=6, maximo=60,
          habilita="polares.fonte=avl"),
    Opcao("otimizacao.mostrar_individuos", "Otimização", "Indivíduos mostrados", "alguns",
          "A otimização é a etapa mais pesada. nenhum: só o resultado final. "
          "alguns: uma amostra por geração (abaixo). todos: cada indivíduo "
          "avaliado (lento e usa muita memória).", escolhas=("nenhum", "alguns", "todos")),
    Opcao("otimizacao.individuos_max", "Otimização", "Quantos por geração", 20,
          "Número de indivíduos mostrados em cada geração (os melhores primeiro).",
          minimo=1, maximo=10000, habilita="otimizacao.mostrar_individuos=alguns"),
    Opcao("otimizacao.a_cada_geracoes", "Otimização", "Mostrar a cada N gerações", 1,
          "1 mostra todas as gerações; 5 mostra uma em cada cinco.",
          minimo=1, maximo=1000),
    Opcao("pastas.base", "Pastas da equipe", "Base de dados", "",
          "Pasta com os dados da equipe (polares, ensaios, tabelas)."),
    Opcao("pastas.relatorios", "Pastas da equipe", "Relatórios", "",
          "Pasta com os relatórios (PDF, texto)."),
    Opcao("pastas.desenhos", "Pastas da equipe", "Desenhos", "",
          "Pasta com os desenhos e as aeronaves (.json, imagens, PDF)."),
    Opcao("vista.malha_ao_abrir", "Interface", "Abrir já em modo malha", False,
          "Mostra a triangulação em vez do sólido ao abrir uma aeronave."),
)

_POR_CHAVE = {o.chave: o for o in OPCOES}

def opcao(chave: str) -> Opcao:
    try:
        return _POR_CHAVE[chave]
    except KeyError:
        raise ConfiguracaoInvalida(f"opção desconhecida: {chave}") from None

def validar(chave: str, valor):
    o = opcao(chave)
    if o.tipo == "escolha":
        if valor not in o.escolhas:
            raise ConfiguracaoInvalida(f"{chave}: use {', '.join(o.escolhas)}")
    elif o.tipo == "booleano":
        if not isinstance(valor, bool):
            raise ConfiguracaoInvalida(f"{chave}: use verdadeiro ou falso")
    elif o.tipo == "texto":
        if not isinstance(valor, str):
            raise ConfiguracaoInvalida(f"{chave}: texto")
    else:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ConfiguracaoInvalida(f"{chave}: número")
        if (o.minimo is not None and valor < o.minimo) or (
                o.maximo is not None and valor > o.maximo):
            raise ConfiguracaoInvalida(
                f"{chave}: entre {o.minimo:g} e {o.maximo:g}")
        valor = type(o.padrao)(valor)
    return valor

class Configuracao:

    def __init__(self, mudancas: dict | None = None):
        self._m: dict = {}
        for k, v in (mudancas or {}).items():
            self.definir(k, v)

    def valor(self, chave: str):
        o = opcao(chave)
        return self._m.get(chave, o.padrao)

    def definir(self, chave: str, valor) -> None:
        v = validar(chave, valor)
        if v == opcao(chave).padrao:
            self._m.pop(chave, None)
        else:
            self._m[chave] = v

    def ativa(self, chave: str) -> bool:
        h = opcao(chave).habilita
        if not h:
            return True
        k, v = h.split("=")
        return self.valor(k) == v

    def mudancas(self) -> dict:
        return dict(self._m)

    def problemas(self) -> list[str]:
        p = []
        fonte = self.valor("polares.fonte")
        for f, chave, nome in (("avl", "polares.avl_caminho", "AVL"),
                               ("xfoil", "polares.xfoil_caminho", "XFOIL")):
            if fonte == f:
                c = self.valor(chave)
                if not c:
                    p.append(f"Fonte {f}: informe o caminho do {nome}.")
                elif not Path(c).is_file():
                    p.append(f"{nome} não encontrado em {c}.")
        return p

    def gravar(self, caminho) -> None:
        Path(caminho).write_text(
            json.dumps({"versao": 1, "mudancas": self._m}, indent=2,
                       ensure_ascii=False), encoding="utf8")

    @classmethod
    def ler(cls, caminho) -> "Configuracao":
        p = Path(caminho)
        if not p.is_file():
            return cls()
        d = json.loads(p.read_text(encoding="utf8"))
        return cls({k: v for k, v in d.get("mudancas", {}).items() if k in _POR_CHAVE})
