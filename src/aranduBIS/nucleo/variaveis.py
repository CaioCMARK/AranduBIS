from __future__ import annotations

from dataclasses import dataclass, field

from .formula import compilar, avaliar as _avalia, nomes_usados

NASCEM_LIVRES = {"asa", "empenagem", "fuselagem", "perfil", "trem", "massa"}

@dataclass
class Variavel:
    nome: str
    grupo: str
    minimo: float
    maximo: float
    padrao: float
    unidade: str = ""
    descricao: str = ""
    so_se: str = ""
    discreta: tuple = ()
    livre: bool = field(default=False)

    def __post_init__(self):
        if self.minimo > self.maximo or not (self.minimo <= self.padrao <= self.maximo):
            raise ValueError(f"{self.nome}: faixa [{self.minimo}, {self.maximo}] nao contem o padrao {self.padrao}")

class Catalogo:

    def __init__(self, variaveis: list[Variavel]):
        self.v: dict[str, Variavel] = {}
        for x in variaveis:
            if x.nome in self.v:
                raise ValueError(f"variavel repetida: {x.nome}")
            x.livre = x.grupo in NASCEM_LIVRES
            self.v[x.nome] = x
        self.fixos: dict[str, float] = {}

    def _alvo(self, quem: str) -> list[Variavel]:
        if quem in self.v:
            return [self.v[quem]]
        g = [x for x in self.v.values() if x.grupo == quem]
        if not g:
            raise KeyError(f"nao existe variavel nem grupo '{quem}'")
        return g

    def liberar(self, quem: str) -> None:
        for x in self._alvo(quem):
            x.livre = True
            self.fixos.pop(x.nome, None)

    def travar(self, quem: str, valor: float | None = None) -> None:
        alvo = self._alvo(quem)
        if valor is not None:
            if len(alvo) != 1:
                raise ValueError("um valor so pode ser fixado numa variavel, nao num grupo")
            x = alvo[0]
            if not (x.minimo <= valor <= x.maximo):
                raise ValueError(f"{x.nome}: {valor} fora da faixa [{x.minimo}, {x.maximo}]")
            self.fixos[x.nome] = float(valor)
        for x in alvo:
            x.livre = False
            if valor is None:
                self.fixos.pop(x.nome, None)

    def ativa(self, x: Variavel, genes: dict) -> bool:
        if not x.so_se:
            return True
        ctx = {n: 0.0 for n in nomes_usados(x.so_se, x.nome)}
        ctx.update({k: float(v) for k, v in genes.items() if k in ctx})
        return bool(_avalia(compilar(x.so_se, x.nome), ctx, x.nome))

    def livres(self, genes: dict | None = None) -> list[Variavel]:
        genes = genes or {}
        return [x for x in self.v.values() if x.livre and self.ativa(x, genes)]

    def contagem(self, genes: dict | None = None) -> dict:
        c: dict[str, int] = {}
        for x in self.livres(genes):
            c[x.grupo] = c.get(x.grupo, 0) + 1
        c["total"] = sum(c.values())
        return c

    def projeto(self, vetor: dict, genes: dict | None = None) -> dict:
        genes = genes or {}
        saida = {}
        for x in self.v.values():
            if not self.ativa(x, genes):
                continue
            if x.livre and x.nome in vetor:
                saida[x.nome] = float(vetor[x.nome])
            else:
                saida[x.nome] = self.fixos.get(x.nome, x.padrao)
        return saida

def asa(prefixo: str, n_max: int = 5, b=(0.6, 3.2, 2.4), corda=(0.12, 0.9, 0.3), so_se: str = "") -> list[Variavel]:
    p = prefixo
    v = [Variavel(f"{p}_b", "asa", *b[:2], b[2], "m", "envergadura", so_se=so_se),
         Variavel(f"{p}_corda_raiz", "asa", *corda[:2], corda[2], "m", "corda da raiz", so_se=so_se),
         Variavel(f"{p}_incidencia", "asa", -4.0, 12.0, 2.0, "graus", "incidencia da raiz", so_se=so_se)]
    for i in range(1, n_max):
        cond = f"n_secoes_{p} >= {i + 1}" + (f" and ({so_se})" if so_se else "")
        v += [Variavel(f"{p}_frac_y{i}", "asa", 0.1, 1.0, i / (n_max - 1), "", f"trecho {i}: fracao da semi-envergadura", so_se=cond),
              Variavel(f"{p}_corda{i}", "asa", 0.15, 1.0, 1.0 - 0.15 * i, "", f"corda da secao {i} / corda da raiz", so_se=cond),
              Variavel(f"{p}_xle{i}", "asa", -0.25, 0.5, 0.0, "", f"bordo de ataque da secao {i}, em cordas de raiz", so_se=cond),
              Variavel(f"{p}_torcao{i}", "asa", -6.0, 2.0, 0.0, "graus", f"torcao da secao {i}", so_se=cond),
              Variavel(f"{p}_zle{i}", "asa", -0.15, 0.35, 0.0, "", f"altura da secao {i}, em semi-envergaduras (gaivota/diedro)", so_se=cond),
              Variavel(f"{p}_perfil{i}", "perfil", 0, 97, 0, "", f"indice do perfil na secao {i} (banco de polares)",
                       so_se=cond, discreta=tuple(range(98)))]
    return v

def empenagem(prefixo: str, so_se: str = "") -> list[Variavel]:
    p = prefixo
    return [Variavel(f"{p}_area", "empenagem", 0.02, 0.6, 0.15, "m2", "area", so_se=so_se),
            Variavel(f"{p}_alongamento", "empenagem", 2.0, 8.0, 4.0, "", "alongamento", so_se=so_se),
            Variavel(f"{p}_afilamento", "empenagem", 0.3, 1.0, 0.7, "", "afilamento", so_se=so_se),
            Variavel(f"{p}_braco", "empenagem", -1.5, 2.5, 1.0, "m", "distancia ao CG, positiva para tras", so_se=so_se),
            Variavel(f"{p}_incidencia", "empenagem", -6.0, 6.0, 0.0, "graus", "incidencia", so_se=so_se),
            Variavel(f"{p}_diedro", "empenagem", 0.0, 60.0, 0.0, "graus", "diedro (cauda em V)", so_se=so_se)]

def comandos(prefixo: str) -> list[Variavel]:
    return [Variavel(f"{prefixo}_corda_rel", "comandos", 0.15, 0.4, 0.25, "", "corda do comando / corda local"),
            Variavel(f"{prefixo}_env_rel", "comandos", 0.2, 0.9, 0.5, "", "envergadura do comando / semi-envergadura")]

def fuselagem_e_trem() -> list[Variavel]:
    return [Variavel("boom_comprimento", "fuselagem", 0.4, 2.0, 1.0, "m", "comprimento do boom"),
            Variavel("x_asa", "fuselagem", 0.0, 0.8, 0.3, "m", "posicao da asa"),
            Variavel("x_cg_massas", "massa", -0.2, 0.4, 0.1, "m", "posicao do CG via bateria e carga"),
            Variavel("trem_x", "trem", 0.0, 0.8, 0.3, "m", "posicao do trem principal"),
            Variavel("trem_altura", "trem", 0.05, 0.3, 0.12, "m", "altura do trem")]

def monta(n_max_asa: int = 5) -> Catalogo:
    v = (asa("asa", n_max_asa) + asa("asa2", n_max_asa, so_se="n_asas >= 2")
         + empenagem("cauda", so_se="cauda == 1") + empenagem("canard", so_se="canard == 1")
         + comandos("aileron") + comandos("profundor") + fuselagem_e_trem())
    return Catalogo(v)
