from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

@dataclass(frozen=True)
class Perfil:

    nome: str
    x: np.ndarray
    y: np.ndarray

    def __post_init__(self) -> None:
        if len(self.x) != len(self.y):
            raise ValueError(f"{self.nome}: x e y têm tamanhos diferentes")
        if len(self.x) < 20:
            raise ValueError(f"{self.nome}: só {len(self.x)} pontos, esperado >= 20")

    @property
    def i_bordo_ataque(self) -> int:
        return int(np.argmin(self.x))

    def superficies(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        i = self.i_bordo_ataque
        xs, ys = self.x[: i + 1][::-1], self.y[: i + 1][::-1]
        xi, yi = self.x[i:], self.y[i:]
        return xs, ys, xi, yi

    def reamostrar(self, n: int = 121) -> Perfil:
        beta = np.linspace(0.0, np.pi, n)
        xc = 0.5 * (1.0 - np.cos(beta))
        xs, ys, xi, yi = self.superficies()
        y_sup = np.interp(xc, xs, ys)
        y_inf = np.interp(xc, xi, yi)
        x = np.concatenate([xc[::-1], xc[1:]])
        y = np.concatenate([y_sup[::-1], y_inf[1:]])
        return Perfil(nome=self.nome, x=x, y=y)

    def _amostrar(self, n: int):
        xs, ys, xi, yi = self.superficies()
        x0 = min(float(xs[0]), float(xi[0]))
        x1 = max(float(xs[-1]), float(xi[-1]))
        corda = x1 - x0
        if corda <= 0:
            raise ValueError(f"{self.nome}: corda nula")
        t = np.linspace(0.0, 1.0, n)
        xq = x0 + corda * t
        return t, corda, np.interp(xq, xs, ys), np.interp(xq, xi, yi)

    @property
    def espessura_maxima(self) -> float:
        _, corda, ys, yi = self._amostrar(400)
        return float(np.max(ys - yi) / corda)

    @property
    def camber_maximo(self) -> float:
        _, corda, ys, yi = self._amostrar(400)
        return float(np.max(0.5 * (ys + yi)) / corda)

    def linha_de_camber(self, n: int = 100) -> tuple[np.ndarray, np.ndarray]:
        t, corda, ys, yi = self._amostrar(n)
        return t, 0.5 * (ys + yi) / corda

    def alpha_sustentacao_nula(self, n: int = 400) -> float:
        xc, zc = self.linha_de_camber(n)
        th = np.arccos(np.clip(1.0 - 2.0 * xc, -1.0, 1.0))
        dz = np.gradient(zc, xc)
        ordem = np.argsort(th)
        return float(-(1.0 / np.pi) * np.trapezoid(dz[ordem] * (np.cos(th[ordem]) - 1.0),
                                                   th[ordem]))

    def __repr__(self) -> str:
        return (f"<Perfil {self.nome}: {len(self.x)} pts, "
                f"t/c={self.espessura_maxima:.4f}, camber={self.camber_maximo:.4f}>")

def ler_perfil(caminho: str | Path, nome: str | None = None) -> Perfil:
    caminho = Path(caminho)
    pontos = []
    for linha in caminho.read_text(encoding="latin-1").splitlines():
        partes = linha.replace(",", ".").split()
        if len(partes) < 2:
            continue
        try:
            a, b = float(partes[0]), float(partes[1])
        except ValueError:
            continue
        pontos.append((a, b))
    if len(pontos) < 20:
        raise ValueError(f"{caminho.name}: só {len(pontos)} pontos reconhecidos")
    arr = np.array(pontos)

    if arr[0, 0] > 1.5 or arr[0, 1] > 1.5:
        n_sup = int(round(arr[0, 0]))
        sup, inf = arr[1:1 + n_sup], arr[1 + n_sup:]
        arr = np.vstack([sup[::-1], inf[1:]])

    elif arr[0, 0] < 0.5:
        i = int(np.argmax(arr[:, 0]))
        sup, inf = arr[:i + 1], arr[i + 1:]
        if len(sup) >= 5 and len(inf) >= 5:
            arr = np.vstack([sup[::-1], inf])

    return Perfil(nome=nome or caminho.stem, x=arr[:, 0], y=arr[:, 1])

def interpolar(a: Perfil, b: Perfil, peso: float, n: int = 121,
               nome: str | None = None) -> Perfil:
    if not 0.0 <= peso <= 1.0:
        raise ValueError(f"peso deve estar em [0,1], veio {peso}")
    ra, rb = a.reamostrar(n), b.reamostrar(n)
    return Perfil(
        nome=nome or f"{a.nome}×{1 - peso:.2f}+{b.nome}×{peso:.2f}",
        x=ra.x, y=(1.0 - peso) * ra.y + peso * rb.y,
    )

def interpolar_polares(pa, pb, peso: float, nome: str | None = None):
    from arandu.aero.polares import Polar

    mesma_forma = (pa.alpha.shape == pb.alpha.shape and pa.re.shape == pb.re.shape)
    if not mesma_forma or not np.allclose(pa.alpha, pb.alpha) or not np.allclose(pa.re, pb.re):
        raise ValueError(
            f"as duas polares precisam da mesma grade (alpha, Re). "
            f"{pa.nome}: {pa.cl.shape}, {pb.nome}: {pb.cl.shape}"
        )
    w = peso
    return Polar(
        nome=nome or f"{pa.nome}×{1 - w:.2f}+{pb.nome}×{w:.2f}",
        alpha=pa.alpha, re=pa.re,
        cl=(1 - w) * pa.cl + w * pb.cl,
        cd=(1 - w) * pa.cd + w * pb.cd,
        cm=(1 - w) * pa.cm + w * pb.cm,
        meta={**pa.meta, "interpolada_de": [pa.nome, pb.nome], "peso": w},
    )
