from __future__ import annotations

import numpy as np
import scipy.linalg as sl
from scipy.special import hankel2

from ..modelador import aeronave_geometria as AG
from .asa import _elemento
from .torcao import analisa

G_GAUSS = np.polynomial.legendre.leggauss(4)

def theodorsen(k):
    k = np.maximum(np.asarray(k, float), 1e-6)
    h1, h0 = hankel2(1, k), hankel2(0, k)
    return h1 / (h1 + 1j * h0)

def _hermite(xi, L):
    return np.array([1 - 3 * xi ** 2 + 2 * xi ** 3, L * (xi - 2 * xi ** 2 + xi ** 3), 3 * xi ** 2 - 2 * xi ** 3, L * (-xi ** 2 + xi ** 3)])

def matrizes(y, EI, GJ, m, S, Ia):
    n = len(y)
    K = np.zeros((3 * n, 3 * n))
    M = np.zeros((3 * n, 3 * n))
    xg, wg = G_GAUSS
    xg, wg = 0.5 * (xg + 1.0), 0.5 * wg
    for e in range(n - 1):
        L = float(y[e + 1] - y[e])
        ei = 2.0 / (1.0 / EI[e] + 1.0 / EI[e + 1])
        gj = 2.0 / (1.0 / GJ[e] + 1.0 / GJ[e + 1])
        idx = np.array([3 * e, 3 * e + 1, 3 * e + 3, 3 * e + 4])
        Kb = ei / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L ** 2, -6 * L, 2 * L ** 2],
                                     [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L ** 2, -6 * L, 4 * L ** 2]])
        K[np.ix_(idx, idx)] += Kb
        ia = np.array([3 * e + 2, 3 * e + 5])
        K[np.ix_(ia, ia)] += gj / L * np.array([[1.0, -1.0], [-1.0, 1.0]])
        Me = np.zeros((6, 6))
        for xi, w in zip(xg, wg):
            Nh = _hermite(xi, L)
            Na = np.array([1 - xi, xi])
            mi, si, ii = ((1 - xi) * a[e] + xi * a[e + 1] for a in (m, S, Ia))
            Nfull_h = np.array([Nh[0], Nh[1], 0, Nh[2], Nh[3], 0])
            Nfull_a = np.array([0, 0, Na[0], 0, 0, Na[1]])
            Me += w * L * (mi * np.outer(Nfull_h, Nfull_h) + si * (np.outer(Nfull_h, Nfull_a) + np.outer(Nfull_a, Nfull_h)) + ii * np.outer(Nfull_a, Nfull_a))
        gl = np.arange(3 * e, 3 * e + 6)
        M[np.ix_(gl, gl)] += Me
    return K, M

def modos_de_vibracao(y, EI, GJ, m, S, Ia, n_modos=8):
    n = len(y)
    K, M = matrizes(y, EI, GJ, m, S, Ia)
    livres = np.arange(3, 3 * n)
    w2, V = sl.eigh(K[np.ix_(livres, livres)], M[np.ix_(livres, livres)])
    n_modos = min(n_modos, len(w2))
    w2, V = w2[:n_modos], V[:, :n_modos]
    Phi = np.zeros((3 * n, n_modos))
    Phi[livres] = V
    energia = []
    for r in range(n_modos):
        u = Phi[:, r]
        eb = 0.0
        et = 0.0
        for e in range(n - 1):
            L = float(y[e + 1] - y[e])
            ei = 2.0 / (1.0 / EI[e] + 1.0 / EI[e + 1])
            gj = 2.0 / (1.0 / GJ[e] + 1.0 / GJ[e + 1])
            d = u[[3 * e, 3 * e + 1, 3 * e + 3, 3 * e + 4]]
            Kb = ei / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L ** 2, -6 * L, 2 * L ** 2], [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L ** 2, -6 * L, 4 * L ** 2]])
            eb += 0.5 * d @ Kb @ d
            et += 0.5 * gj / L * (u[3 * e + 5] - u[3 * e + 2]) ** 2
        energia.append((eb, et))
    return {"f_hz": (np.sqrt(np.clip(w2, 0, None)) / (2 * np.pi)).tolist(), "Phi": Phi, "w2": w2,
            "natureza": ["flexao" if eb >= et else "torcao" for eb, et in energia],
            "h": Phi[0::3].T.tolist(), "alfa": Phi[2::3].T.tolist()}

def _pesos(y):
    w = np.zeros(len(y))
    dy = np.diff(y)
    w[:-1] += 0.5 * dy
    w[1:] += 0.5 * dy
    return w

def _coeficientes(rho, V, b, a, C, kappa):
    pi = np.pi
    Ccirc = kappa * C
    Lh = np.stack([np.zeros_like(b), 2 * pi * rho * V * b * Ccirc, pi * rho * b ** 2], axis=-1)
    La = np.stack([2 * pi * rho * V ** 2 * b * Ccirc,
                   pi * rho * b ** 2 * V + 2 * pi * rho * V * b * Ccirc * b * (0.5 - a), -pi * rho * b ** 3 * a], axis=-1)
    Mh = np.stack([np.zeros_like(b), 2 * pi * rho * V * b ** 2 * (a + 0.5) * Ccirc, pi * rho * b ** 3 * a], axis=-1)
    Ma = np.stack([2 * pi * rho * V ** 2 * b ** 2 * (a + 0.5) * Ccirc,
                   -pi * rho * b ** 3 * V * (0.5 - a) + 2 * pi * rho * V * b ** 2 * (a + 0.5) * Ccirc * b * (0.5 - a),
                   -pi * rho * b ** 4 * (0.125 + a ** 2)], axis=-1)
    A = np.zeros(b.shape + (2, 2, 3), dtype=complex)
    A[..., 0, 0, :], A[..., 0, 1, :] = -Lh, -La
    A[..., 1, 0, :], A[..., 1, 1, :] = Mh, Ma
    return A

def _produtos(P):
    n, _, N = P.shape
    return np.einsum("nia,njb->nijab", P, P).reshape(n * 4, N * N)

def _aero_modal(G, peso, A, N):
    coef = (peso[:, None, None] * A.reshape(len(peso), 4, 3)).transpose(2, 0, 1).reshape(3, -1)
    return (coef @ G).reshape(3, N, N)

def flutter(y, c, EI, GJ, ea_c, m, x_alfa_c, r_cg_c, rho=1.1, Vmax=60.0, n_V=60, n_modos=8, zeta_s=0.0, cl_alpha_2d=2 * np.pi, V_min=2.0):
    y, c, EI, GJ, ea_c, m = (np.asarray(v, float) for v in (y, c, EI, GJ, ea_c, m))
    x_alfa_c = np.broadcast_to(np.asarray(x_alfa_c, float), y.shape)
    r_cg_c = np.broadcast_to(np.asarray(r_cg_c, float), y.shape)
    x_a = x_alfa_c * c
    S = m * x_a
    Ia = m * ((r_cg_c * c) ** 2 + x_a ** 2)
    vib = modos_de_vibracao(y, EI, GJ, m, S, Ia, n_modos)
    Phi = vib["Phi"]
    N = Phi.shape[1]
    P = np.stack([Phi[0::3], Phi[2::3]], axis=1)
    G = _produtos(P)
    b = 0.5 * c
    a = 2.0 * ea_c - 1.0
    peso = _pesos(y)
    kappa = cl_alpha_2d / (2 * np.pi)
    w0 = np.sqrt(vib["w2"])
    Vs = np.linspace(V_min, Vmax, n_V)
    s_hist = np.zeros((n_V, N), dtype=complex)
    s_prev = 1j * w0
    Cs = 2 * zeta_s * np.diag(w0)
    for iv, V in enumerate(Vs):
        for r in range(N):
            s = s_prev[r]
            for _ in range(40):
                k = np.maximum(abs(s.imag), 1e-3) * b / V
                C = theodorsen(k)
                Q0, Q1, Q2 = _aero_modal(G, peso, _coeficientes(rho, V, b, a, C, kappa), N)
                Minv = np.linalg.inv(np.eye(N) - Q2)
                Mat = np.block([[np.zeros((N, N)), np.eye(N)], [-Minv @ (np.diag(w0 ** 2) - Q0), Minv @ (Q1 - Cs)]])
                ev = np.linalg.eigvals(Mat)
                ev = ev[ev.imag >= -1e-9]
                novo = ev[np.argmin(np.abs(ev - s))]
                if abs(novo - s) < 1e-5 * max(abs(s), 1.0):
                    s = novo
                    break
                s = novo
            s_hist[iv, r] = s
        s_prev = s_hist[iv].copy()
    amort = -s_hist.real / np.maximum(np.abs(s_hist), 1e-12)
    freq = s_hist.imag / (2 * np.pi)
    sai = {"V": Vs.tolist(), "freq_hz": freq.T.tolist(), "amortecimento": amort.T.tolist(), "f_vacuo_hz": vib["f_hz"], "natureza": vib["natureza"],
           "VF": None, "f_flutter_hz": None, "modo_flutter": None, "VD": None, "formas": {"y": y.tolist(), "h": vib["h"], "alfa": vib["alfa"]}}
    for iv in range(1, n_V):
        for r in range(N):
            if s_hist[iv, r].imag < 0.5 * 2 * np.pi * 0.1:
                if s_hist[iv, r].real > 0 >= s_hist[iv - 1, r].real and sai["VD"] is None:
                    t = -s_hist[iv - 1, r].real / (s_hist[iv, r].real - s_hist[iv - 1, r].real)
                    sai["VD"] = float(Vs[iv - 1] + t * (Vs[iv] - Vs[iv - 1]))
                continue
            if amort[iv, r] <= 0 < amort[iv - 1, r] and sai["VF"] is None:
                t = amort[iv - 1, r] / (amort[iv - 1, r] - amort[iv, r])
                sai["VF"] = float(Vs[iv - 1] + t * (Vs[iv] - Vs[iv - 1]))
                sai["f_flutter_hz"] = float(freq[iv - 1, r] + t * (freq[iv, r] - freq[iv - 1, r]))
                sai["modo_flutter"] = int(r)
    return sai

def itens_de_massa(esq: dict) -> list:
    return AG.massa_e_cg(AG.constroi(esq))["itens"]

def massa_do_modelo(esq: dict, nome: str, y, c, xle, pos_x: float, itens: list | None = None) -> dict:
    itens = [q for q in (itens if itens is not None else itens_de_massa(esq)) if str(q["nome"]).startswith(nome + ".")]
    if not itens:
        raise ValueError(f"a asa {nome!r} nao tem itens de massa no modelo")
    M = float(sum(q["massa"] for q in itens))
    fr = []
    for q in itens:
        yy = float(np.clip(abs(q["cg"][1]), y[0], y[-1]))
        fr.append((q["massa"], (q["cg"][0] - pos_x - np.interp(yy, y, xle)) / np.interp(yy, y, c)))
    x_cg_c = float(sum(w * f for w, f in fr) / M)
    return {"massa_kg": M, "x_cg_c": x_cg_c}

def dados_de_vibracao(esq: dict, nome: str, mats: dict | None = None, rho: float = 1.1, Vd: float = 15.9, fator: float = 1.2, x_ca_c: float = 0.25,
                      cl_alpha_2d: float = 2 * np.pi, calib_GJ: float = 1.0, calib_EI: float = 1.0, ea_desloc_c: float = 0.0,
                      massa_asa_kg: float | None = None, x_cg_c: float | None = None, r_giro_c: float = 0.28, itens=None) -> dict:
    an = analisa(esq, nome, mats=mats, rho=rho, Vd=Vd, fator=fator, x_ca_c=x_ca_c, cl_alpha_2d=cl_alpha_2d, calib_GJ=calib_GJ,
                 ea_desloc_c=ea_desloc_c, calib_EI=calib_EI)
    el = _elemento(esq, nome)
    y, c = np.array(an["y"]), np.array(an["c"])
    sec = AG._secoes(el)
    xle = np.array([AG._secao_em(sec, float(v))[0] for v in y])
    pos_x = float((el.get("posicao") or [0.0, 0.0, 0.0])[0])
    try:
        mm = massa_do_modelo(esq, nome, y, c, xle, pos_x, itens)
    except ValueError:
        mm = None
    M = massa_asa_kg if massa_asa_kg is not None else (mm["massa_kg"] / 2.0 if mm else None)
    if M is None:
        raise ValueError(f"sem massa da asa {nome!r}: informe a massa da semi-asa")
    xcg = x_cg_c if x_cg_c is not None else (mm["x_cg_c"] if mm else 0.35)
    ea = np.array(an["ea_c"])
    return {"an": an, "y": y, "c": c, "EI": np.array(an["EI"]), "GJ": np.array(an["GJ"]), "ea_c": ea, "m_lin": M * c / np.trapezoid(c, y),
            "x_alfa_c": xcg - ea, "M": float(M), "xcg": float(xcg), "r_giro_c": r_giro_c,
            "origem_massa": "informada" if massa_asa_kg is not None else "itens de massa do modelo (semi-asa)",
            "origem_x_cg": "informado" if x_cg_c is not None else ("itens de massa do modelo" if mm else "hipotese 0,35")}

def analisa_flutter(esq: dict, nome: str, mats: dict | None = None, rho: float = 1.1, Vd: float = 15.9, fator: float = 1.2, x_ca_c: float = 0.25,
                    cl_alpha_2d: float = 2 * np.pi, calib_GJ: float = 1.0, ea_desloc_c: float = 0.0, massa_asa_kg: float | None = None,
                    x_cg_c: float | None = None, r_giro_c: float = 0.28, zeta_s: float = 0.0, V_max_rel: float = 3.0, n_V: int = 45, n_modos: int = 8,
                    itens=None, calib_EI: float = 1.0) -> dict:
    d = dados_de_vibracao(esq, nome, mats=mats, rho=rho, Vd=Vd, fator=fator, x_ca_c=x_ca_c, cl_alpha_2d=cl_alpha_2d, calib_GJ=calib_GJ, calib_EI=calib_EI,
                          ea_desloc_c=ea_desloc_c, massa_asa_kg=massa_asa_kg, x_cg_c=x_cg_c, r_giro_c=r_giro_c, itens=itens)
    an, M, xcg = d["an"], d["M"], d["xcg"]
    avisos = []
    r = flutter(d["y"], d["c"], d["EI"], d["GJ"], d["ea_c"], d["m_lin"], d["x_alfa_c"], r_giro_c, rho=rho, Vmax=V_max_rel * Vd, n_V=n_V, n_modos=n_modos,
                zeta_s=zeta_s, cl_alpha_2d=cl_alpha_2d)
    V_req = fator * Vd
    if r["VF"] is None and r["VD"] is None:
        avisos.append(f"Sem flutter nem divergencia ate {V_max_rel:g} x Vd ({V_max_rel * Vd:.1f} m/s) com estes dados.")
    if r["VF"] is not None:
        avisos.append(f"Flutter a {r['VF']:.1f} m/s, a {r['f_flutter_hz']:.1f} Hz.")
    if r["VD"] is not None:
        avisos.append(f"Divergencia (autovalor real cruza zero) a {r['VD']:.1f} m/s.")
    avisos.append("A massa da asa vem so dos itens estruturais do modelo (nervuras, longarina, tubos, chapeado); servo, aileron, entelagem e lastro nao entram "
                  "se nao estiverem no modelo. A posicao do centro de massa e o raio de giracao decidem o flutter: calibre com o ensaio de vibracao (GVT).")
    if any(not f for f in an["fechada"]):
        avisos.append("Parte da asa tem caixa aberta (GJ muito baixo): as frequencias de torcao e o flutter ficam dominados por essa regiao mole.")
    sai = {"nome": nome, "V_requerida": V_req, "fator": fator, "massa_semi_asa_kg": float(M), "origem_massa": d["origem_massa"], "x_cg_c": float(xcg),
           "origem_x_cg": d["origem_x_cg"], "r_giro_c": r_giro_c, "zeta_s": zeta_s, "rho": rho, "avisos": avisos, **r}
    sai["margem_VF"] = None if r["VF"] is None else r["VF"] / V_req - 1.0
    sai["margem_VD"] = None if r["VD"] is None else r["VD"] / V_req - 1.0
    return sai
