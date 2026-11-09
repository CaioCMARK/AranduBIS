from __future__ import annotations

import numpy as np

from .modelo import Modelo
from .solver import Sistema

E0 = 1e9
CORDAL = 100.0

def modelo_asa(y, c, EI, GJ, ea_c, ca_c, q_por_m, EA=None, momento_por_m=None) -> Modelo:
    y, c, EI, GJ, ea_c, q = (np.asarray(v, float) for v in (y, c, EI, GJ, ea_c, q_por_m))
    n = len(y)
    m = Modelo()
    m.material(1, E0, E0, rho=0.0)
    for i in range(n):
        m.no(i + 1, ea_c[i] * c[i], y[i], 0.0)
        m.no(1001 + i, ca_c * c[i], y[i], 0.0)
    ea = np.zeros(n) + 1e-3 if EA is None else np.asarray(EA, float) / E0
    for i in range(n - 1):
        k = 0.5 * (EI[i] + EI[i + 1]) / E0
        j = 0.5 * (GJ[i] + GJ[i + 1]) / E0
        m.prop(i + 1, 1, 0.5 * (ea[i] + ea[i + 1]), k, CORDAL * k, j)
        m.barra(i + 1, i + 1, i + 1, i + 2, (0.0, 0.0, 1.0))
    m.engasta([1])
    w = np.zeros(n); dy = np.diff(y)
    w[:-1] += 0.5 * dy; w[1:] += 0.5 * dy
    for i in range(n):
        m.rigido(i + 1, i + 1, [1001 + i])
        mo = 0.0 if momento_por_m is None else float(momento_por_m[i]) * w[i]
        m.carga(1, 1001 + i, [0.0, 0.0, q[i] * w[i], 0.0, mo, 0.0])
    return m

def resolve(y, **kw):
    mod = modelo_asa(y, **kw)
    S = Sistema(mod)
    r = S.estatica(1)
    n = len(y)
    u = np.array([r["u"][i + 1] for i in range(n)])
    return {"w": u[:, 2], "theta": u[:, 4], "esforcos": r["esforcos"], "modelo": mod}
