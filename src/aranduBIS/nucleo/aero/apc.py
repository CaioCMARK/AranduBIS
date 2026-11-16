from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

PASTA = Path(__file__).resolve().parents[4] / "data" / "apc_props"

_RPM = re.compile(r"PROP RPM\s*=\s*(\d+)")
_NOME = re.compile(r"^\s*(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)E\b")

POLEGADA = 0.0254

@dataclass(frozen=True)
class Helice:

    nome: str
    D_pol: float
    passo_pol: float
    rpm: np.ndarray
    J: list[np.ndarray]
    CT: list[np.ndarray]
    CP: list[np.ndarray]

    @property
    def D(self) -> float:
        return self.D_pol * POLEGADA

    def __repr__(self) -> str:
        return (f"<APC {self.nome}: {len(self.rpm)} blocos de "
                f"{self.rpm[0]:.0f} a {self.rpm[-1]:.0f} rpm>")

    def coeficientes(self, J, rpm: float) -> tuple[np.ndarray, np.ndarray]:
        J = np.atleast_1d(np.asarray(J, dtype=float))
        rpm = float(np.clip(rpm, self.rpm[0], self.rpm[-1]))
        i = int(np.clip(np.searchsorted(self.rpm, rpm) - 1, 0, len(self.rpm) - 2))
        r0, r1 = self.rpm[i], self.rpm[i + 1]
        w = 0.0 if r1 == r0 else (rpm - r0) / (r1 - r0)

        def em(k):
            return (np.interp(J, self.J[k], self.CT[k]),
                    np.interp(J, self.J[k], self.CP[k]))

        ct0, cp0 = em(i)
        ct1, cp1 = em(i + 1)
        return (1 - w) * ct0 + w * ct1, (1 - w) * cp0 + w * cp1

    def tracao_e_torque(self, V: float, rpm: float, rho: float):
        n = rpm / 60.0
        if n <= 0:
            return 0.0, 0.0
        J = V / (n * self.D)
        ct, cp = self.coeficientes(J, rpm)
        T = float(ct[0]) * rho * n ** 2 * self.D ** 4
        P = float(cp[0]) * rho * n ** 3 * self.D ** 5
        return T, P / (2.0 * np.pi * n)

def _ler(caminho: Path) -> Helice:
    linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    if not linhas:
        raise ValueError(f"{caminho.name}: arquivo vazio")
    m = _NOME.match(linhas[0])
    if not m:
        raise ValueError(f"{caminho.name}: primeira linha nao traz o modelo "
                         f"<D>x<passo>E: {linhas[0][:40]!r}")
    D_pol, passo_pol = float(m.group(1)), float(m.group(2))

    rpms: list[float] = []
    blocos: list[list[tuple[float, float, float]]] = []
    atual: list[tuple[float, float, float]] | None = None
    for linha in linhas:
        achou = _RPM.search(linha)
        if achou:
            rpms.append(float(achou.group(1)))
            atual = []
            blocos.append(atual)
            continue
        if atual is None:
            continue
        campos = linha.split()
        if len(campos) < 5:
            continue
        try:
            v = [float(c) for c in campos[:5]]
        except ValueError:
            continue
        atual.append((v[1], v[3], v[4]))

    bons = [(r, b) for r, b in zip(rpms, blocos) if len(b) >= 2]
    if not bons:
        raise ValueError(f"{caminho.name}: nenhum bloco de rotacao utilizavel")
    bons.sort(key=lambda rb: rb[0])
    return Helice(
        nome=f"{m.group(1)}x{m.group(2)}E".replace(".0x", "x"),
        D_pol=D_pol, passo_pol=passo_pol,
        rpm=np.array([r for r, _ in bons], dtype=float),
        J=[np.array([t[0] for t in b]) for _, b in bons],
        CT=[np.array([t[1] for t in b]) for _, b in bons],
        CP=[np.array([t[2] for t in b]) for _, b in bons],
    )

@lru_cache(maxsize=1)
def catalogo() -> dict[str, Helice]:
    if not PASTA.is_dir():
        return {}
    saida = {}
    for arq in sorted(PASTA.glob("PER3_*.dat")):
        try:
            h = _ler(arq)
        except ValueError:
            continue
        saida[h.nome] = h
    return dict(sorted(saida.items(), key=lambda kv: (kv[1].D_pol, kv[1].passo_pol)))

def mais_proxima(D_pol: float, passo_pol: float) -> Helice | None:
    cat = catalogo()
    if not cat:
        return None
    return min(cat.values(),
               key=lambda h: (3.0 * (h.D_pol - D_pol)) ** 2
               + (h.passo_pol - passo_pol) ** 2)

D_MAXIMO_POL = 27.0
