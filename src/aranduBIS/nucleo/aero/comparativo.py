from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .aeronave_vlm import superficies
from .estabilidade import derivadas
from .vlm import VLM


@dataclass
class Elevon:
    superficie: str
    y_min: float = 0.0
    x_charneira: float = 0.75
    limite: float = 25.0


def _flape(vlm: VLM, el: Elevon, graus: float) -> dict:
    info = vlm._fatias[el.superficie]
    d = np.where(np.abs(info["y"]) >= el.y_min, np.radians(graus), 0.0)
    return {"delta_flap": {el.superficie: d}}


def _inteira(vlm: VLM, nome: str, graus: float) -> dict:
    return {"delta_alpha": {nome: np.full(vlm._fatias[nome]["ns"], np.radians(graus))}}


def _newton(f, x0, h=1.0, n=12, lim=None):
    x = np.array(x0, float)
    r = f(*x)
    for _ in range(n):
        F = np.array(r[0])
        if np.linalg.norm(F) < 1e-6:
            break
        J = np.empty((2, 2))
        for k in range(2):
            xp = x.copy(); xp[k] += h
            J[:, k] = (np.array(f(*xp)[0]) - F) / h
        if abs(np.linalg.det(J)) < 1e-14:
            return x, r, False
        x = x + np.clip(np.linalg.solve(J, -F), -4.0, 4.0)
        r = f(*x)
        if lim is not None and abs(x[1]) > 3.0 * lim:
            return x, r, False
    return x, r, bool(np.linalg.norm(r[0]) < 6e-3)


def _comando_inteiro(S: list, x_cg: float) -> str | None:
    cand = [s for s in S if abs(s.diedro) <= 60.0 and not s.de_referencia]
    if not cand:
        return None
    return max(cand, key=lambda s: abs(s.x_le + 0.25 * s.planform.corda_raiz - x_cg) * s.planform.area).nome


def trima(vlm: VLM, CL_alvo: float, V: float, rho: float, elevon: Elevon | None, inteira: str | None,
          altura_solo: float | None = None):
    if elevon is None and inteira is None:
        def g(al, _de):
            r = vlm.resolver(al, V=V, rho=rho)[0]
            return (r.CL - CL_alvo, r.Cm), r
        al = 3.0
        for _ in range(10):
            (f, r) = g(al, 0.0)
            ra = vlm.resolver(al + 0.5, V=V, rho=rho)[0]
            al -= f[0] * 0.5 / (ra.CL - r.CL)
        r = vlm.resolver(al, V=V, rho=rho)[0]
        return al, 0.0, r, abs(r.Cm) < 1e-4, False

    def aval(al, de):
        kw = _flape(vlm, elevon, de) if elevon else _inteira(vlm, inteira, de)
        kw["x_charneira"] = elevon.x_charneira if elevon else 0.8
        r = vlm.resolver(al, V=V, rho=rho, **kw)[0]
        return (r.CL - CL_alvo, r.Cm), r

    lim = elevon.limite if elevon else 30.0
    x, (F, r), ok = _newton(aval, (3.0, 0.0), lim=lim)
    return float(x[0]), float(x[1]), r, ok, bool(abs(x[1]) > lim)


def avalia(esq: dict, V: float = 15.0, rho: float = 1.1, CL: float = 0.6, SM: float = 0.10,
           elevon: Elevon | None = None, comando: str | None = "auto", n_span=None, n_chord=None,
           altura_solo: float | None = None, laterais: bool = True, alpha0: float = 3.0,
           peso_N: float | None = None, x_cg: float | None = None) -> dict:
    S = superficies(esq, n_span=n_span, n_chord=n_chord)
    ref = [s for s in S if s.de_referencia] or S
    z_cg = float(np.mean([s.z for s in ref]))
    v0 = VLM(S, x_ref=0.0, z_ref=z_cg)
    d0 = derivadas(v0, alpha0, V=V, rho=rho, laterais=False)
    x_np = float(d0.ponto_neutro)
    c = float(v0.c_ref)
    x_cg = x_np - SM * c if x_cg is None else float(x_cg)
    if peso_N is not None:
        CL = peso_N / (0.5 * rho * V * V * float(v0.S_ref))
    vlm = VLM(S, x_ref=x_cg, z_ref=z_cg, altura_solo=altura_solo)
    d = derivadas(vlm, alpha0, V=V, rho=rho, laterais=laterais)
    cmd = _comando_inteiro(S, x_cg) if comando == "auto" else comando
    if elevon is not None:
        cmd = None
    al, de, r, ok, sat = trima(vlm, CL, V, rho, elevon, cmd, altura_solo)
    S_ref, b = float(vlm.S_ref), float(vlm.b_ref)
    q = 0.5 * rho * V * V
    L = float(r.CL) * q * S_ref
    saida = {
        "L_N": L, "Di_N": float(r.CDi) * q * S_ref,
        "e_b": float(L * L / (np.pi * q * b * b * float(r.CDi) * q * S_ref)) if r.CDi > 1e-12 else float("nan"),
        "S_ref": S_ref, "b_ref": b, "c_ref": c, "AR": b * b / S_ref, "x_np": x_np, "x_cg": x_cg,
        "SM": float(d.margem_estatica), "CL_alpha": float(d.CL_alpha), "Cm_alpha": float(d.Cm_alpha),
        "trim": {"alpha": al, "delta": de, "CL": float(r.CL), "CDi": float(r.CDi), "e": float(r.e_oswald),
                 "Cm": float(r.Cm), "convergiu": ok, "saturou": sat, "comando": (elevon.superficie + " (elevon)") if elevon else cmd},
        "CL_por_superficie": {k: float(v) for k, v in r.CL_superficie.items()},
        "superficies": [s.nome for s in S],
    }
    if laterais:
        saida["Cn_beta"] = float(d.Cn_beta); saida["Cl_beta"] = float(d.Cl_beta); saida["CY_beta"] = float(d.CY_beta)
        saida["Cl_p"] = float(d.Cl_p); saida["Cn_r"] = float(d.Cn_r)
    return saida


def cl_maximo_equilibrado(esq: dict, V: float, rho: float, SM: float = 0.10, elevon: Elevon | None = None,
                          comando: str | None = "auto", altura_solo: float | None = None, CL_max: float = 1.6,
                          n_span=None, n_chord=None, alpha_max: float = 14.0) -> dict:
    lo, hi = 0.1, CL_max
    ultimo = None
    for _ in range(10):
        mid = 0.5 * (lo + hi)
        a = avalia(esq, V=V, rho=rho, CL=mid, SM=SM, elevon=elevon, comando=comando, laterais=False,
                   altura_solo=altura_solo, n_span=n_span, n_chord=n_chord)
        t = a["trim"]
        bom = t["convergiu"] and not t["saturou"] and t["alpha"] <= alpha_max
        if bom:
            lo, ultimo = mid, a
        else:
            hi = mid
    return {"CL_max_equilibrado": lo, "avaliacao": ultimo}


def acha_parametro(construtor, alvo: float, medida, x0: float, x1: float, tol: float = 1e-3, n: int = 12) -> tuple:
    f0 = medida(construtor(x0)) - alvo
    f1 = medida(construtor(x1)) - alvo
    for _ in range(n):
        if abs(f1) < tol * max(1.0, abs(alvo)) or f1 == f0:
            break
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
        x0, f0, x1 = x1, f1, x2
        f1 = medida(construtor(x1)) - alvo
    e = construtor(x1)
    return x1, e, f1 + alvo
