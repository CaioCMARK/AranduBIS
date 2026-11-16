from __future__ import annotations

from dataclasses import dataclass

import numpy as np

@dataclass(frozen=True)
class Estacao:

    y: float
    corda: float
    x_le: float = 0.0
    z_le: float = 0.0
    perfil: str | None = None
    torcao: float = 0.0

@dataclass(frozen=True)
class Planform:

    estacoes: tuple[Estacao, ...]
    nome: str = "asa"

    def __post_init__(self) -> None:
        if len(self.estacoes) < 2:
            raise ValueError(f"{self.nome}: precisa de ao menos 2 estações")
        ys = [e.y for e in self.estacoes]
        if ys[0] != 0.0:
            raise ValueError(f"{self.nome}: a primeira estação deve estar na raiz (y=0), veio y={ys[0]}")
        if any(b <= a for a, b in zip(ys, ys[1:])):
            raise ValueError(f"{self.nome}: as estações devem ter y estritamente crescente, veio {ys}")
        if any(e.corda <= 0 for e in self.estacoes):
            raise ValueError(f"{self.nome}: toda corda deve ser positiva")

    @property
    def semi_envergadura(self) -> float:
        return self.estacoes[-1].y

    @property
    def envergadura(self) -> float:
        return 2.0 * self.semi_envergadura

    @property
    def corda_raiz(self) -> float:
        return self.estacoes[0].corda

    @property
    def corda_ponta(self) -> float:
        return self.estacoes[-1].corda

    @property
    def afilamento(self) -> float:
        return self.corda_ponta / self.corda_raiz

    def _trechos(self):
        return zip(self.estacoes, self.estacoes[1:])

    @property
    def area(self) -> float:
        meia = sum(0.5 * (a.corda + b.corda) * (b.y - a.y) for a, b in self._trechos())
        return 2.0 * meia

    @property
    def alongamento(self) -> float:
        return self.envergadura**2 / self.area

    @property
    def mac(self) -> float:
        integral = sum(
            (b.y - a.y) * (a.corda**2 + a.corda * b.corda + b.corda**2) / 3.0
            for a, b in self._trechos()
        )
        return 2.0 * integral / self.area

    def _momento(self, atributo: str, quarto_de_corda: bool = False) -> float:
        total = 0.0
        for a, b in self._trechos():
            dy = b.y - a.y
            c1, c2 = a.corda, b.corda
            if atributo == "y":
                f1, f2 = a.y, b.y
            else:
                f1 = a.x_le + (0.25 * c1 if quarto_de_corda else 0.0)
                f2 = b.x_le + (0.25 * c2 if quarto_de_corda else 0.0)
            total += dy * (c1 * f1 / 1.0 + (c1 * (f2 - f1) + (c2 - c1) * f1) / 2.0 + (c2 - c1) * (f2 - f1) / 3.0)
        return total

    @property
    def y_mac(self) -> float:
        return 2.0 * self._momento("y") / self.area

    @property
    def x_mac(self) -> float:
        return 2.0 * self._momento("x", quarto_de_corda=True) / self.area

    @property
    def offset_mac(self) -> float:
        return self.x_mac - self.mac / 4.0

    def corda_em(self, y: np.ndarray | float) -> np.ndarray:
        ys = np.array([e.y for e in self.estacoes])
        cs = np.array([e.corda for e in self.estacoes])
        return np.interp(np.asarray(y, dtype=float), ys, cs)

    def faixas(self, n: int, cosseno: bool = True) -> tuple[np.ndarray, np.ndarray]:
        if cosseno:
            theta = np.linspace(0.0, np.pi / 2.0, n + 1)
            bordas = self.semi_envergadura * np.sin(theta)
        else:
            bordas = np.linspace(0.0, self.semi_envergadura, n + 1)
        return 0.5 * (bordas[:-1] + bordas[1:]), np.diff(bordas)

    def __repr__(self) -> str:
        return (
            f"<Planform {self.nome}: b={self.envergadura:.4g} m, S={self.area:.4g} m², "
            f"AR={self.alongamento:.4g}, MAC={self.mac:.4g} m, {len(self.estacoes)} estações>"
        )

def asa_reto_trapezoidal(
    b: float, cr: float, afilamento: float, frac_transicao: float, offset_ponta: float = 0.0,
    perfil_raiz: str | None = None, perfil_ponta: str | None = None, nome: str = "asa",
) -> Planform:
    if not 0.0 < frac_transicao < 1.0:
        raise ValueError(f"frac_transicao deve estar em (0,1), veio {frac_transicao}")
    semi = b / 2.0
    y_t = semi * frac_transicao
    ct = cr * afilamento
    return Planform(
        nome=nome,
        estacoes=(
            Estacao(y=0.0, corda=cr, x_le=0.0, perfil=perfil_raiz),
            Estacao(y=y_t, corda=cr, x_le=0.0, perfil=perfil_raiz),
            Estacao(y=semi, corda=ct, x_le=offset_ponta, perfil=perfil_ponta),
        ),
    )

def asa_trapezoidal(
    b: float, cr: float, afilamento: float, offset_ponta: float = 0.0, nome: str = "asa"
) -> Planform:
    semi = b / 2.0
    return Planform(
        nome=nome,
        estacoes=(
            Estacao(y=0.0, corda=cr, x_le=0.0),
            Estacao(y=semi, corda=cr * afilamento, x_le=offset_ponta),
        ),
    )

def endplate(altura: float, corda: float, corda_ponta: float | None = None,
             nome: str = "endplate") -> Planform:
    ct = corda if corda_ponta is None else corda_ponta
    return Planform(nome=nome, estacoes=(
        Estacao(y=0.0, corda=corda),
        Estacao(y=altura, corda=ct),
    ))

def winglet(altura: float, corda_raiz: float, afilamento: float = 0.4,
            enflechamento: float = 0.25, nome: str = "winglet") -> Planform:
    return Planform(nome=nome, estacoes=(
        Estacao(y=0.0, corda=corda_raiz, x_le=0.0),
        Estacao(y=altura, corda=corda_raiz * afilamento, x_le=enflechamento * corda_raiz),
    ))

def asa_eliptica(b: float, cr: float, n: int = 40, nome: str = "asa_eliptica") -> Planform:
    y = np.linspace(0.0, b / 2.0, n)
    c = cr * np.sqrt(np.clip(1.0 - (2.0 * y / b) ** 2, 0.0, None))
    c[-1] = max(c[-1], 1e-6)
    return Planform(nome=nome, estacoes=tuple(Estacao(y=float(yi), corda=float(ci)) for yi, ci in zip(y, c)))
