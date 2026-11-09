from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

try:
    from numba import njit
    COM_NUMBA = True
except Exception:
    COM_NUMBA = False

    def njit(*a, **k):
        if a and callable(a[0]) and not k:
            return a[0]
        return lambda f: f

G = 9.80665

def densidade_do_ar(altitude_densidade_m: float) -> float:
    return 1.225 * (1.0 - 2.25577e-5 * altitude_densidade_m) ** 4.25588

@dataclass(frozen=True)
class Condicoes:

    pista_m: float = 55.0
    obstaculo_m: float = 0.90
    altitude_densidade_m: float = 1330.0
    mu: float = 0.062
    d_alpha_rotacao: float = 6.0
    taxa_rotacao: float = 20.0
    margem_rotacao: float = 1.02
    dt: float = 0.005
    t_max: float = 30.0

    @property
    def rho(self) -> float:
        return densidade_do_ar(self.altitude_densidade_m)

@dataclass(frozen=True)
class Aeronave:

    S: float
    CL_max: float
    CL_corrida: float
    CD_corrida: float
    tracao_v: tuple = (0.0, 30.0)
    tracao_n: tuple = (60.0, 20.0)

@dataclass
class Resultado:
    decolou: bool
    transpos: bool
    altura_obstaculo: float
    folga_m: float
    distancia_rotacao: float
    velocidade_rotacao: float
    motivo: str = ""
    x: np.ndarray = field(default_factory=lambda: np.zeros(0), repr=False)
    v: np.ndarray = field(default_factory=lambda: np.zeros(0), repr=False)
    h: np.ndarray = field(default_factory=lambda: np.zeros(0), repr=False)
    t: np.ndarray = field(default_factory=lambda: np.zeros(0), repr=False)
    forcas: dict | None = field(default=None, repr=False)

_OK, _SEM_TRACAO, _NAO_ATINGIU_VLO, _NAO_SAIU_DO_SOLO = 0, 1, 2, 3

@njit(cache=True)
def _laco(m, S, CLmax, CLc, CDc, vt, tt, rho, mu, pista, dalpha, taxa, margem, dt, tmax, saida, forcas):
    W = m * G
    v_lo = margem * math.sqrt(2.0 * W / (rho * S * CLmax))
    t = 0.0
    x = 0.0
    v = 0.0
    h = 0.0
    n = 0
    cap = saida.shape[0]
    estado = _OK

    while v < v_lo and t < tmax and x < pista and n < cap - 1:
        q = 0.5 * rho * v * v
        L = q * S * CLc
        D = q * S * CDc
        N = max(W - L, 0.0)
        T = np.interp(v, vt, tt)
        a = (T - D - mu * N) / m
        if a <= 0.0 and v < 1e-6:
            return _SEM_TRACAO, n, 0.0, 0.0, 0.0
        saida[n, 0] = t; saida[n, 1] = x; saida[n, 2] = v; saida[n, 3] = 0.0
        forcas[n, 0] = T; forcas[n, 1] = D; forcas[n, 2] = mu * N; forcas[n, 3] = L; forcas[n, 4] = W
        n += 1
        v += a * dt
        x += v * dt
        t += dt
    if v < v_lo:
        saida[n, 0] = t; saida[n, 1] = x; saida[n, 2] = v; saida[n, 3] = 0.0
        forcas[n, :] = forcas[max(n - 1, 0), :]
        return _NAO_ATINGIU_VLO, n + 1, x, v, 0.0

    x_lo = x
    v_ini = v

    dur = max(dalpha, 0.0) / max(taxa, 1e-9)
    t_rot = 0.0
    no_solo = True
    while no_solo and t < tmax and x < pista and n < cap - 1:
        f = min(1.0, t_rot / dur) if dur > 0.0 else 1.0
        cl = CLc + f * (CLmax - CLc)
        q = 0.5 * rho * v * v
        L = q * S * cl
        if L >= W:
            no_solo = False
            break
        D = q * S * CDc
        T = np.interp(v, vt, tt)
        F = mu * max(W - L, 0.0)
        a = (T - D - F) / m
        saida[n, 0] = t; saida[n, 1] = x; saida[n, 2] = v; saida[n, 3] = 0.0
        forcas[n, 0] = T; forcas[n, 1] = D; forcas[n, 2] = F; forcas[n, 3] = L; forcas[n, 4] = W
        n += 1
        v = max(0.0, v + a * dt)
        x += v * dt
        t += dt
        t_rot += dt
    if no_solo:
        return _NAO_SAIU_DO_SOLO, n, x_lo, v_ini, 0.0

    while x < pista and t < tmax and n < cap - 1:
        q = 0.5 * rho * v * v
        cl = min(CLmax, W / max(q * S, 1e-9))
        D = q * S * CDc
        T = np.interp(v, vt, tt)
        exc = T - D
        sg = min(1.0, max(-1.0, exc / W))
        cg = math.sqrt(max(0.0, 1.0 - sg * sg))
        a = (exc - W * sg) / m
        saida[n, 0] = t; saida[n, 1] = x; saida[n, 2] = v; saida[n, 3] = h
        forcas[n, 0] = T; forcas[n, 1] = D; forcas[n, 2] = 0.0; forcas[n, 3] = q * S * cl; forcas[n, 4] = W
        n += 1
        v = max(0.1, v + a * dt)
        x += v * cg * dt
        h += v * sg * dt
        t += dt
    return _OK, n, x_lo, v_ini, h

def simular(massa_kg: float, ae: Aeronave, c: Condicoes = Condicoes(), forcas: bool = True) -> Resultado:
    if massa_kg <= 0 or ae.S <= 0 or ae.CL_max <= 0:
        raise ValueError("massa, área e CL máximo precisam ser positivos")
    if ae.CL_corrida >= ae.CL_max:
        raise ValueError("CL de corrida precisa ser menor que o CL máximo")
    cap = int(c.t_max / c.dt) + 4
    saida = np.zeros((cap, 4))
    fz = np.zeros((cap, 5))
    vt = np.asarray(ae.tracao_v, float)
    tt = np.asarray(ae.tracao_n, float)
    est, n, x_lo, v_lo, h = _laco(float(massa_kg), ae.S, ae.CL_max, ae.CL_corrida, ae.CD_corrida, vt, tt,
                                  c.rho, c.mu, c.pista_m, c.d_alpha_rotacao, c.taxa_rotacao,
                                  c.margem_rotacao, c.dt, c.t_max, saida, fz)
    s = saida[:n]
    nan = float("nan")
    base = dict(t=s[:, 0].copy(), x=s[:, 1].copy(), v=s[:, 2].copy(), h=s[:, 3].copy(),
                forcas={k: fz[:n, i].copy() for i, k in enumerate(("T", "D", "atrito", "L", "W"))} if forcas else None)
    if est == _SEM_TRACAO:
        return Resultado(False, False, nan, nan, nan, nan, "Tração insuficiente para iniciar a corrida.", **base)
    if est == _NAO_ATINGIU_VLO:
        return Resultado(False, False, nan, nan, x_lo, v_lo,
                         f"Não atingiu a velocidade de rotação em {c.pista_m:.0f} m (chegou a {v_lo:.1f} m/s).", **base)
    if est == _NAO_SAIU_DO_SOLO:
        return Resultado(False, False, nan, nan, x_lo, v_lo,
                         f"Começou a girar em {x_lo:.1f} m mas não saiu do solo em {c.pista_m:.0f} m: "
                         f"precisa de mais sustentação ou de rotação mais rápida.", **base)
    h, x_lo, v_lo = float(h), float(x_lo), float(v_lo)
    folga = h - c.obstaculo_m
    ok = bool(folga >= 0)
    msg = "" if ok else f"Saiu do solo em {x_lo:.1f} m mas só chegou a {h:.2f} m no obstáculo (faltaram {-folga:.2f} m)."
    return Resultado(True, ok, h, folga, x_lo, v_lo, msg, **base)

def massa_maxima(ae: Aeronave, c: Condicoes = Condicoes(), m_min: float = 0.5, m_max: float = 60.0,
                 tol_kg: float = 0.005) -> dict:
    def passa(m):
        return simular(m, ae, c, forcas=False).transpos

    if not passa(m_min):
        return {"massa_kg": None, "folga_m": None, "limitada_por": "nem a menor massa passa"}
    if passa(m_max):
        return {"massa_kg": m_max, "folga_m": simular(m_max, ae, c, forcas=False).folga_m,
                "limitada_por": "teto da busca"}
    lo, hi = m_min, m_max
    while hi - lo > tol_kg:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if passa(mid) else (lo, mid)
    return {"massa_kg": lo, "folga_m": simular(lo, ae, c, forcas=False).folga_m, "limitada_por": "obstáculo"}

def varredura_de_massa(ae: Aeronave, c: Condicoes, massas) -> list[dict]:
    out = []
    for m in massas:
        r = simular(float(m), ae, c, forcas=False)
        out.append({"massa_kg": float(m), "decolou": r.decolou, "transpos": r.transpos,
                    "altura_m": None if not r.decolou else r.altura_obstaculo,
                    "distancia_rotacao_m": None if not r.decolou else r.distancia_rotacao})
    return out
