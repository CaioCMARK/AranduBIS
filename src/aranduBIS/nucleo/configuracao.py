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
    Opcao("avl.n_secoes", "Análise", "Painéis em envergadura (AVL)", 20,
          "Mais painéis, mais fiel e mais lento.", minimo=6, maximo=60,
          habilita="polares.fonte=avl"),
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
