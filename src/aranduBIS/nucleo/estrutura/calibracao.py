from __future__ import annotations

import numpy as np
import scipy.linalg as sl
from scipy.optimize import least_squares

from . import flutter as FL

LIM = (0.2, 5.0)
SIGMA_REL = 0.03

def _estatica(y, EI, GJ, no_carga, grau, valor, no_medida):
    n = len(y)
    K, _ = FL.matrizes(y, EI, GJ, np.ones(n), np.zeros(n), np.ones(n))
    livres = np.arange(3, 3 * n)
    f = np.zeros(3 * n)
    f[3 * no_carga + grau] = valor
    u = np.zeros(3 * n)
    u[livres] = np.linalg.solve(K[np.ix_(livres, livres)], f[livres])
    return u[3 * no_medida + grau]

def _modelo(d, f_EI, f_GJ, r_giro, observ, n_modos=12):
    y, c = d["y"], d["c"]
    EI, GJ = d["EI"] * f_EI, d["GJ"] * f_GJ
    m = d["m_lin"]
    x_a = d["x_alfa_c"] * c
    S, Ia = m * x_a, m * ((r_giro * c) ** 2 + x_a ** 2)
    vib = FL.modos_de_vibracao(y, EI, GJ, m, S, Ia, n_modos)
    res = []
    for o in observ["frequencias"]:
        cand = [f for f, t in zip(vib["f_hz"], vib["natureza"]) if o["tipo"] == "todos" or t == o["tipo"]]
        k = int(o.get("ordem", 1)) - 1
        res.append(cand[k] if k < len(cand) else np.nan)
    for o in observ["flecha"]:
        i, j = int(np.argmin(abs(y - o["y_carga_m"]))), int(np.argmin(abs(y - o["y_medida_m"])))
        res.append(abs(_estatica(y, EI, GJ, i, 0, float(o["P_N"]), j)))
    for o in observ["torcao"]:
        i, j = int(np.argmin(abs(y - o["y_carga_m"]))), int(np.argmin(abs(y - o["y_medida_m"])))
        res.append(abs(np.degrees(_estatica(y, EI, GJ, i, 2, float(o["T_Nm"]), j))))
    return np.array(res, float), vib

def _medidas(observ):
    return np.array([o["hz"] for o in observ["frequencias"]] + [o["w_m"] for o in observ["flecha"]] + [o["theta_graus"] for o in observ["torcao"]], float)

def _rotulos(observ):
    return ([f"{o['ordem']}o modo" + ("" if o["tipo"] == "todos" else f" de {o['tipo']}") for o in observ["frequencias"]] + [f"flecha {o['P_N']:g} N em {o['y_carga_m']:g} m" for o in observ["flecha"]]
            + [f"torcao {o['T_Nm']:g} N.m em {o['y_carga_m']:g} m" for o in observ["torcao"]])

def calibra(esq: dict, nome: str, observ: dict, ajusta=("EI", "GJ"), mats: dict | None = None, rho: float = 1.1, Vd: float = 15.9, x_ca_c: float = 0.25,
            cl_alpha_2d: float = 2 * np.pi, ea_desloc_c: float = 0.0, massa_asa_kg: float | None = None, x_cg_c: float | None = None,
            r_giro_c: float = 0.28, itens=None, massa_real: dict | None = None) -> dict:
    obs = {k: list(observ.get(k) or []) for k in ("frequencias", "flecha", "torcao")}
    medidas = _medidas(obs)
    if len(medidas) == 0:
        raise ValueError("Informe ao menos uma medida (frequencia, flecha ou torcao).")
    if np.any(medidas <= 0):
        raise ValueError("As medidas precisam ser maiores que zero.")
    ajusta = [a for a in ("EI", "GJ", "r_giro") if a in ajusta]
    if not ajusta:
        raise ValueError("Escolha ao menos um parametro para ajustar (EI, GJ ou raio de giracao).")
    d = FL.dados_de_vibracao(esq, nome, mats=mats, rho=rho, Vd=Vd, x_ca_c=x_ca_c, cl_alpha_2d=cl_alpha_2d, ea_desloc_c=ea_desloc_c,
                             massa_asa_kg=massa_asa_kg, x_cg_c=x_cg_c, r_giro_c=r_giro_c, itens=itens, massa_real=massa_real)
    r0 = d["r_giro_c"]

    def parametros(p):
        v = dict(zip(ajusta, np.exp(p)))
        return v.get("EI", 1.0), v.get("GJ", 1.0), r0 * v.get("r_giro", 1.0)

    def residuo(p):
        mod, _ = _modelo(d, *parametros(p), obs)
        return np.where(np.isfinite(mod), mod / medidas - 1.0, 10.0)

    p0 = np.zeros(len(ajusta))
    antes = residuo(p0)
    mod_antes0, _ = _modelo(d, *parametros(p0), obs)
    existe = np.isfinite(mod_antes0)
    sol = least_squares(residuo, p0, bounds=(np.log(LIM[0]), np.log(LIM[1])), x_scale=0.3)
    depois = sol.fun
    J = sol.jac
    avisos = []
    sv = np.linalg.svd(J, compute_uv=False) if J.size else np.array([])
    incerteza = [None] * len(ajusta)
    if len(sv) == len(ajusta) and sv.min() > 1e-8 * sv.max() and len(medidas) >= len(ajusta):
        cov = SIGMA_REL ** 2 * np.linalg.inv(J.T @ J)
        incerteza = [float(100 * np.sqrt(cov[i, i])) for i in range(len(ajusta))]
    else:
        avisos.append("As medidas nao separam todos os parametros escolhidos (ha mais parametros que informacao independente): "
                      "escolha menos parametros ou acrescente ensaios (flexao e torcao em separado).")
    if len(medidas) < len(ajusta):
        avisos.append(f"Ha {len(ajusta)} parametros e so {len(medidas)} medida(s): o ajuste e subdeterminado.")
    for nm, v, lo in zip(ajusta, np.exp(sol.x), sol.active_mask):
        if lo != 0:
            avisos.append(f"{nm} bateu no limite ({LIM[0]:g} a {LIM[1]:g} x): confira as medidas, as unidades e a massa.")
    mod_depois, vib = _modelo(d, *parametros(sol.x), obs)
    mod_antes, _ = _modelo(d, *parametros(p0), obs)
    if np.any(~np.isfinite(mod_antes)):
        avisos.append("Algum modo pedido nao existe no modelo (tipo e ordem): aumente a ordem ou troque o tipo.")
    rms = lambda r: float(np.sqrt(np.mean(np.square(r)))) if len(r) else 0.0
    v = dict(zip(ajusta, np.exp(sol.x)))
    if massa_real is not None:
        avisos += d["perfil_massa"]["avisos"]
    avisos.append(f"Massa da semi-asa fixa em {d['M']:.3f} kg ({d['origem_massa']}) e centro de massa em x/c = {d['xcg']:.3f}: erro de massa vira erro "
                  "proporcional nas rigidezes ajustadas.")
    return {"nome": nome, "parametros": {k: float(val) for k, val in v.items()}, "incerteza_pct": dict(zip(ajusta, incerteza)),
            "rotulos": _rotulos(obs), "medido": medidas.tolist(), "modelo_antes": [float(x) if np.isfinite(x) else None for x in mod_antes],
            "modelo_depois": mod_depois.tolist(), "erro_antes_pct": [float(100 * a) if e else None for a, e in zip(antes, existe)], "erro_depois_pct": (100 * depois).tolist(),
            "rms_antes_pct": 100 * rms(antes[existe]), "rms_depois_pct": 100 * rms(depois), "massa_semi_asa_kg": d["M"], "x_cg_c": d["xcg"],
            "r_giro_c": float(np.mean(r0 * v.get("r_giro", 1.0))), "f_vacuo_hz": vib["f_hz"], "natureza": vib["natureza"], "avisos": avisos}
