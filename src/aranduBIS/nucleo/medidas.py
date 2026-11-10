from __future__ import annotations

import numpy as np

from .modelador import aeronave_geometria as AG

def _pontos(A, esq, excluir):
    fora = tuple(str(n) + "." for n in excluir)
    usa = np.array([not z.startswith(fora) for z in A.zonas]) if fora else np.ones(len(A.zonas), bool)
    T = A.T[usa[np.asarray(A.zona)]]
    return A.V[np.unique(T)]

def _sustenta(el):
    if el.get("tipo", "asa") != "asa" or el.get("camada") == "estrutura" or el.get("sustenta") is False:
        return False
    rol = abs(float(el.get("rolagem", 0.0))) % 180.0
    return min(rol, 180.0 - rol) < 45.0

def raio_do_cone(P, altura):
    z = P[:, 2] - P[:, 2].min()
    if z.max() >= altura:
        return float("inf")
    k = 1.0 / (1.0 - z / altura)

    def f(c):
        return float(np.max(np.hypot(P[:, 0] - c[0], P[:, 1] - c[1]) * k))

    c = np.array([0.5 * (P[:, 0].min() + P[:, 0].max()), 0.5 * (P[:, 1].min() + P[:, 1].max())])
    passo, melhor = 0.25 * max(np.ptp(P[:, 0]), np.ptp(P[:, 1]), 1e-6), f(c)
    while passo > 1e-5:
        andou = False
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            t = c + passo * np.array(d, float); v = f(t)
            if v < melhor - 1e-12:
                c, melhor, andou = t, v, True
        if not andou:
            passo *= 0.5
    return melhor

def medidas(esq: dict, excluir=(), cone_altura: float | None = None) -> dict:
    A = AG.constroi(esq)
    P = _pontos(A, esq, excluir)
    lo, hi = P.min(0), P.max(0)
    sup = [el["nome"] for el in esq.get("elementos", []) if _sustenta(el) and el["nome"] not in excluir]
    r = {"envergadura": float(hi[1] - lo[1]), "comprimento": float(hi[0] - lo[0]), "altura": float(hi[2] - lo[2]),
         "n_superficies": len(sup), "superficies": sup, "excluidos": list(excluir),
         "extremos": {"x": [float(lo[0]), float(hi[0])], "y": [float(lo[1]), float(hi[1])], "z": [float(lo[2]), float(hi[2])]}}
    if cone_altura:
        rc = raio_do_cone(P, float(cone_altura))
        r["raio_cone"] = None if not np.isfinite(rc) else rc
        r["cone_altura"] = float(cone_altura)
    return r
