from __future__ import annotations

import numpy as np

from ..fe.asa import resolve
from .torcao import analisa

def _acumula(y, f):
    return np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(y))])

def _do_fim(y, f):
    a = _acumula(y, f)
    return a[-1] - a

def carga_nas_estacoes(y, y_q, q_por_m):
    y_q, q = np.asarray(y_q, float), np.asarray(q_por_m, float)
    if y_q[-1] < y[-1] - 1e-9:
        y_q, q = np.append(y_q, y[-1]), np.append(q, 0.0)
    return np.interp(y, y_q, q)

def analitica(y, c, EI, GJ, ea_c, ca_c, q):
    M = _do_fim(y, _do_fim(y, q))
    w = _acumula(y, _acumula(y, M / EI))
    T = _do_fim(y, q * (ca_c - ea_c) * c)
    theta = -_acumula(y, T / GJ)
    return w, theta, M

def verifica(esq: dict, nome: str, caso: dict, mats: dict | None = None, **kw) -> dict:
    an = analisa(esq, nome, mats=mats, **kw)
    y, c = np.array(an["y"]), np.array(an["c"])
    EI, GJ, ea_c = np.array(an["EI"]), np.array(an["GJ"]), np.array(an["ea_c"])
    ca_c = float(an["ca_c"])
    q = carga_nas_estacoes(y, caso["y"], caso["liquida_por_m"])
    if not np.any(q):
        raise ValueError("carga liquida nula nesta asa no caso escolhido")
    x_ref = float(ea_c[0] * c[0])
    r = resolve(y, c=c, EI=EI, GJ=GJ, ea_c=np.full_like(y, x_ref) / c, ca_c=ca_c, q_por_m=q, momento_por_m=q * (ea_c * c - x_ref))
    w_a, th_a, M = analitica(y, c, EI, GJ, ea_c, ca_c, q)
    th_fe, w_fe = np.asarray(r["theta"]), np.asarray(r["w"])
    razao = lambda x, ref: float(x / ref) if abs(ref) > 1e-12 else None
    r_w, r_t = razao(w_fe[-1], w_a[-1]), razao(th_fe[-1], th_a[-1])
    avisos = []
    if r_w is not None and abs(r_w - 1.0) > 0.02:
        avisos.append(f"A flecha de elementos finitos difere {100 * (r_w - 1):+.1f} % da integracao analitica: confira a malha e a variacao de EI.")
    if r_t is not None and abs(r_t - 1.0) > 0.05:
        avisos.append(f"A torcao de elementos finitos difere {100 * (r_t - 1):+.1f} % da analitica: a rigidez cai de ordens de grandeza onde o chapeado "
                      "deixa de fechar a caixa e a malha de estacoes nao resolve esse degrau.")
    if abs(np.degrees(th_fe[-1])) > 15.0:
        avisos.append(f"{nome}: a torcao na ponta passa de 15 graus ({np.degrees(th_fe[-1]):.0f}), fora do regime da teoria linear. Leia como: "
                      "a parte externa, sem caixa fechada, nao resiste a torcao sob esta carga. Feche a caixa (chapeado ate a longarina) nessa regiao.")
    return {"nome": nome, "y": y.tolist(), "q_N_m": q.tolist(),
            "w_fe": w_fe.tolist(), "w_analitica": w_a.tolist(), "theta_fe_graus": np.degrees(th_fe).tolist(),
            "theta_analitica_graus": np.degrees(th_a).tolist(),
            "flecha_ponta_fe_m": float(w_fe[-1]), "flecha_ponta_analitica_m": float(w_a[-1]),
            "flecha_pct_fe": float(100 * w_fe[-1] / y[-1]), "torcao_ponta_fe_graus": float(np.degrees(th_fe[-1])),
            "torcao_ponta_analitica_graus": float(np.degrees(th_a[-1])), "razao_flecha": r_w, "razao_torcao": r_t,
            "fletor_raiz_Nm": float(M[0]), "n_nos": int(len(y)), "avisos": avisos}
