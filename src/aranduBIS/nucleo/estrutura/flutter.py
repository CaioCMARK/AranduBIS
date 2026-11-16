from __future__ import annotations

from .. import referencias as R

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
    n, d, N = P.shape
    return np.einsum("nia,njb->nijab", P, P).reshape(n * d * d, N * N)

def _aero_modal(G, peso, A, N):
    d = A.shape[-2]
    coef = (peso[:, None, None] * A.reshape(len(peso), d * d, 3)).transpose(2, 0, 1).reshape(3, -1)
    return (coef @ G).reshape(3, N, N)

def constantes_T(c, a):
    c = np.asarray(c, float); a = np.asarray(a, float)
    r, f = np.sqrt(np.clip(1 - c * c, 0, None)), np.arccos(np.clip(c, -1, 1))
    T = {1: -(2 + c * c) / 3 * r + c * f,
         3: -(1 - c * c) / 8 * (5 * c * c + 4) + c * (7 + 2 * c * c) * r * f / 4 - (1 / 8 + c * c) * f ** 2,
         4: c * r - f,
         5: -(1 - c * c) - f ** 2 + 2 * c * r * f,
         7: c * (7 + 2 * c * c) * r / 8 - (1 / 8 + c * c) * f,
         8: -(1 + 2 * c * c) * r / 3 + c * f,
         10: r + f,
         11: (2 - c) * r + (1 - 2 * c) * f,
         12: (2 + c) * r - (1 + 2 * c) * f}
    T[9] = 0.5 * (r ** 3 / 3 + a * T[4])
    T[13] = 0.5 * (-T[7] - (c - a) * T[1])
    return T

def _coeficientes3(rho, V, b, a, C, kappa, c_h):
    A2 = _coeficientes(rho, V, b, a, C, kappa)
    n = b.shape[0]
    A = np.zeros((n, 3, 3, 3), dtype=complex)
    A[:, :2, :2, :] = A2
    T = constantes_T(c_h, a)
    pi = np.pi
    Cc = kappa * C
    Lb = np.stack([2 * rho * V ** 2 * b * Cc * T[10], -rho * V * b ** 2 * T[4] + rho * V * b ** 2 * Cc * T[11], -rho * b ** 3 * T[1]], axis=-1)
    Mab = np.stack([-rho * V ** 2 * b ** 2 * (T[4] + T[10]) + 2 * rho * V ** 2 * b ** 2 * (a + 0.5) * Cc * T[10],
                    rho * V * b ** 3 * (-T[1] + T[8] + (c_h - a) * T[4] - 0.5 * T[11]) + rho * V * b ** 3 * (a + 0.5) * Cc * T[11],
                    rho * b ** 4 * (T[7] + (c_h - a) * T[1])], axis=-1)
    Mbh = np.stack([np.zeros_like(b, dtype=complex), -rho * V * b ** 2 * T[12] * Cc, rho * b ** 3 * T[1] + 0j], axis=-1)
    Mba = np.stack([-rho * V ** 2 * b ** 2 * T[12] * Cc,
                    rho * V * b ** 3 * (2 * T[9] + T[1] - (a - 0.5) * T[4]) - rho * V * b ** 3 * T[12] * Cc * (0.5 - a),
                    -2 * rho * b ** 4 * T[13] + 0j], axis=-1)
    Mbb = np.stack([-(rho * V ** 2 * b ** 2 / pi) * (T[5] - T[4] * T[10]) - (rho * V ** 2 * b ** 2 / pi) * T[12] * T[10] * Cc,
                    (rho * V * b ** 3 / (2 * pi)) * T[4] * T[11] - (rho * V * b ** 3 / (2 * pi)) * T[12] * T[11] * Cc,
                    rho * b ** 4 * T[3] / pi + 0j], axis=-1)
    A[:, 0, 2, :] = -Lb
    A[:, 1, 2, :] = Mab
    A[:, 2, 0, :], A[:, 2, 1, :], A[:, 2, 2, :] = Mbh, Mba, Mbb
    return A

def estrutura_modal(y, c, EI, GJ, ea_c, m, x_alfa_c, r_cg_c, n_modos=8, zeta_s=0.0, aileron: dict | None = None,
                    cl_alpha_2d=2 * np.pi, rho=1.1) -> dict:
    y, c, EI, GJ, ea_c, m = (np.asarray(v, float) for v in (y, c, EI, GJ, ea_c, m))
    x_alfa_c = np.broadcast_to(np.asarray(x_alfa_c, float), y.shape)
    r_cg_c = np.broadcast_to(np.asarray(r_cg_c, float), y.shape)
    x_a = x_alfa_c * c
    b = 0.5 * c
    a = 2.0 * ea_c - 1.0
    if aileron is None:
        S = m * x_a
        Ia = m * ((r_cg_c * c) ** 2 + x_a ** 2)
    else:
        mk0 = np.asarray(aileron["mascara"], float)
        mb = mk0 * np.asarray(aileron["m"], float)
        fora = mb > 0.9 * m
        if np.any(fora):
            m = np.where(fora, m + mb, m)
            aileron["_aviso"] = (f"Em {int(fora.sum())} estacoes a massa do aileron passa de 90 % da massa da faixa da asa: ali ele foi somado "
                                 "a asa (a massa do modelo nao o contem). Confira a massa da asa e a do aileron.")
        ch0 = np.broadcast_to(np.asarray(aileron["c"], float), y.shape)
        dh = (ch0 - a) * b
        xb = np.asarray(aileron["x_b"], float)
        mr = m - mb
        S = mr * x_a + mb * (dh + xb)
        Ia = mr * ((r_cg_c * c) ** 2 + x_a ** 2) + mk0 * np.asarray(aileron["I_b"], float) + mb * (dh ** 2 + 2 * dh * xb)
    vib = modos_de_vibracao(y, EI, GJ, m, S, Ia, n_modos)
    Phi = vib["Phi"]
    Nw = Phi.shape[1]
    peso = _pesos(y)
    kappa = cl_alpha_2d / (2 * np.pi)
    w0 = np.sqrt(vib["w2"])
    if aileron is None:
        P = np.stack([Phi[0::3], Phi[2::3]], axis=1)
        Ms, Ks, Cs = np.eye(Nw), np.diag(w0 ** 2), 2 * zeta_s * np.diag(w0)
        coef = lambda V, C: _coeficientes(rho, V, b, a, C, kappa)
    else:
        mk = np.asarray(aileron["mascara"], float)
        ch = np.broadcast_to(np.asarray(aileron["c"], float), y.shape)
        Sb = mk * np.asarray(aileron["m"], float) * np.asarray(aileron["x_b"], float)
        Ib = mk * np.asarray(aileron["I_b"], float)
        P = np.zeros((len(y), 3, Nw + 1))
        P[:, 0, :Nw], P[:, 1, :Nw], P[:, 2, Nw] = Phi[0::3], Phi[2::3], mk
        Ms = np.eye(Nw + 1)
        Ms[:Nw, Nw] = Ms[Nw, :Nw] = np.sum(peso[:, None] * (Phi[0::3] * Sb[:, None] + Phi[2::3] * (Ib + (ch - a) * b * Sb)[:, None]), axis=0)
        Mbb = float(np.sum(peso * Ib))
        if Mbb <= 0:
            raise ValueError("aileron sem inercia: informe a massa do aileron")
        Ms[Nw, Nw] = Mbb
        wb = 2 * np.pi * float(aileron.get("f_b", 0.0))
        Ks = np.diag(np.append(w0 ** 2, wb ** 2 * Mbb))
        Cs = np.diag(np.append(2 * zeta_s * w0, 2 * float(aileron.get("zeta", zeta_s)) * wb * Mbb))
        coef = lambda V, C: _coeficientes3(rho, V, b, a, C, kappa, ch)
    return {"y": y, "c": c, "a": a, "b": b, "vib": vib, "P": P, "Ms": Ms, "Ks": Ks, "Cs": Cs, "coef": coef,
            "kappa": kappa, "peso": peso, "w0": w0, "Nw": Nw, "N": P.shape[2], "aileron": aileron, "Phi": Phi}


def flutter(y, c, EI, GJ, ea_c, m, x_alfa_c, r_cg_c, rho=1.1, Vmax=60.0, n_V=60, n_modos=8, zeta_s=0.0, cl_alpha_2d=2 * np.pi, V_min=2.0,
            aileron: dict | None = None):
    e = estrutura_modal(y, c, EI, GJ, ea_c, m, x_alfa_c, r_cg_c, n_modos, zeta_s, aileron, cl_alpha_2d, rho)
    y, b, a, vib, Phi, P, Ms, Ks, Cs, coef, peso, w0, Nw = (e[k] for k in ("y", "b", "a", "vib", "Phi", "P", "Ms", "Ks", "Cs", "coef", "peso", "w0", "Nw"))
    N = P.shape[2]
    G = _produtos(P)
    w2v, Vv = sl.eigh(Ks, Ms)
    w_ini = np.sqrt(np.clip(w2v, 0, None))
    if aileron is None:
        nat_c, formas_h, formas_a, formas_b = vib["natureza"], vib["h"], vib["alfa"], None
    else:
        nat_c, formas_h, formas_a, formas_b = [], [], [], []
        for r in range(N):
            v_ = Vv[:, r]
            parte_b = v_[Nw] ** 2 * Ms[Nw, Nw] / max(float(v_ @ Ms @ v_), 1e-30)
            nat_c.append("aileron" if parte_b > 0.5 else vib["natureza"][int(np.argmax(np.abs(v_[:Nw])))])
            formas_h.append((Phi[0::3] @ v_[:Nw]).tolist()); formas_a.append((Phi[2::3] @ v_[:Nw]).tolist()); formas_b.append(float(v_[Nw]))
    Vs = np.linspace(V_min, Vmax, n_V)
    s_hist = np.zeros((n_V, N), dtype=complex)
    s_prev = 1j * np.maximum(w_ini, 1e-2)
    for iv, V in enumerate(Vs):
        for r in range(N):
            s = s_prev[r]
            for _ in range(40):
                k = np.maximum(abs(s.imag), 1e-3) * b / V
                C = theodorsen(k)
                Q0, Q1, Q2 = _aero_modal(G, peso, coef(V, C), N)
                Minv = np.linalg.inv(Ms - Q2)
                Mat = np.block([[np.zeros((N, N)), np.eye(N)], [-Minv @ (Ks - Q0), Minv @ (Q1 - Cs)]])
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
    sai = {"V": Vs.tolist(), "freq_hz": freq.T.tolist(), "amortecimento": amort.T.tolist(),
           "f_vacuo_hz": (w_ini / (2 * np.pi)).tolist() if aileron is not None else vib["f_hz"],
           "natureza": nat_c,
           "VF": None, "f_flutter_hz": None, "modo_flutter": None, "VD": None, "formas": {"y": y.tolist(), "h": formas_h, "alfa": formas_a, **({"beta": formas_b} if formas_b is not None else {})}}
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

def dados_de_vibracao(esq: dict, nome: str, mats: dict | None = None, rho: float = R.RHO_NIVEL_MAR, Vd: float | None = None, fator: float = 1.2, x_ca_c: float = 0.25,
                      cl_alpha_2d: float = 2 * np.pi, calib_GJ: float = 1.0, calib_EI: float = 1.0, ea_desloc_c: float = 0.0,
                      massa_asa_kg: float | None = None, x_cg_c: float | None = None, r_giro_c: float = 0.28, itens=None,
                      massa_real: dict | None = None) -> dict:
    if Vd is None:
        raise ValueError("informe Vd: velocidade de mergulho, em m/s")
    if massa_real is None and massa_asa_kg is None and x_cg_c is None:
        massa_real = {"usar": True, "adicionais": []}
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
    if massa_real is not None:
        from .massa_asa import perfil_de_massa
        med = (massa_real.get("medidas") or {}).get(nome) or {}
        pf = perfil_de_massa(esq, nome, y, ea, itens if itens is not None else itens_de_massa(esq),
                             [a for a in massa_real.get("adicionais") or [] if a.get("asa") in (None, "", nome)],
                             med.get("massa_medida_kg") or None, med.get("x_cg_medido_c") or None, med.get("y_cg_medido_m") or None)
        return {"an": an, "y": y, "c": c, "EI": np.array(an["EI"]), "GJ": np.array(an["GJ"]), "ea_c": ea, "m_lin": np.array(pf["m_lin"]),
                "x_alfa_c": np.array(pf["x_alfa_c"]), "M": pf["massa_kg"], "xcg": pf["x_cg_c"], "r_giro_c": np.array(pf["r_cg_c"]), "perfil_massa": pf,
                "origem_massa": "distribuicao por estacao (estrutura do modelo + massas adicionais" + (" + massa medida)" if med.get("massa_medida_kg") else ")"),
                "origem_x_cg": "distribuicao por estacao"}
    return {"an": an, "y": y, "c": c, "EI": np.array(an["EI"]), "GJ": np.array(an["GJ"]), "ea_c": ea, "m_lin": M * c / np.trapezoid(c, y),
            "x_alfa_c": xcg - ea, "M": float(M), "xcg": float(xcg), "r_giro_c": r_giro_c,
            "origem_massa": "informada" if massa_asa_kg is not None else "itens de massa do modelo (semi-asa)",
            "origem_x_cg": "informado" if x_cg_c is not None else ("itens de massa do modelo" if mm else "hipotese 0,35")}

def _aileron(esq, nome, d, par, zeta_s):
    from .asa import _elemento
    from ..modelador.superficies_comando import charneira_em, resolve
    el = _elemento(esq, nome)
    ct = next((c for c in el.get("controles", []) if c.get("modo") == "anti"), None)
    if ct is None:
        return None, "Sem aileron declarado nesta asa: o flutter de aileron nao foi calculado."
    ct = resolve(ct, el.get("secoes") or [])
    y0, y1 = sorted(abs(float(v)) for v in ct["y"])
    sec = AG._secoes(el)
    ys = np.array([q[1] for q in sec]); xl = np.array([q[0] for q in sec])
    y, c = np.asarray(d["y"], float), np.asarray(d["c"], float)
    mk = ((y >= y0 - 1e-9) & (y <= y1 + 1e-9)).astype(float)
    if mk.sum() < 2:
        return None, "Aileron curto demais para as estacoes da analise."
    xh = np.array([charneira_em(ct, ci, float(np.interp(yi, np.abs(ys), xl))) for yi, ci in zip(y, c)])
    cf = (1.0 - xh) * c
    L = y1 - y0
    massa = par.get("massa_kg")
    origem = "informada"
    if massa in (None, ""):
        area_a = float(np.trapezoid(cf * mk, y)); area = float(np.trapezoid(c, y))
        massa = float(d["M"]) * area_a / max(area, 1e-9)
        origem = f"estimada: {100 * area_a / area:.0f} % da area da semi-asa x a massa dela; pese o aileron e informe"
    massa = float(massa)
    xg = float(par.get("x_cg", 1.0 / 3.0)); rg = float(par.get("r_giro", np.sqrt(1.0 / 6.0)))
    mb = massa / L
    ail = {"mascara": mk, "c": 2 * xh - 1, "m": mb, "x_b": xg * cf, "I_b": mb * (rg * cf) ** 2,
           "f_b": float(par.get("f_b", 0.0)), "zeta": float(par.get("zeta", zeta_s))}
    info = {"nome": ct.get("nome"), "y": [y0, y1], "massa_kg": massa, "origem_massa": origem, "x_cg": xg, "r_giro": rg,
            "f_b": ail["f_b"], "corda_m": [float(cf[mk > 0].min()), float(cf[mk > 0].max())], "dobradica_xc": float(np.mean(xh[mk > 0]))}
    return ail, info

def _varre_aileron(esq, nome, d, par, zeta_s, r_giro_c, rho, Vmax, n_modos, cl_alpha_2d, f_ref=10.0):
    f_t = max(1.0, float(f_ref))
    out = {"f_b": [], "VF_f_b": [], "x_cg": [], "VF_x_cg": []}
    for fb in np.linspace(0.0, 1.5 * f_t, 6):
        a, _ = _aileron(esq, nome, d, {**par, "f_b": float(fb)}, zeta_s)
        r = flutter(d["y"], d["c"], d["EI"], d["GJ"], d["ea_c"], d["m_lin"], d["x_alfa_c"], r_giro_c, rho=rho, Vmax=Vmax, n_V=25, n_modos=min(n_modos, 4),
                    cl_alpha_2d=cl_alpha_2d, aileron=a)
        out["f_b"].append(float(fb)); out["VF_f_b"].append(r["VF"])
    for xg in (-0.2, 0.0, 0.15, 1 / 3, 0.5):
        a, _ = _aileron(esq, nome, d, {**par, "x_cg": xg}, zeta_s)
        r = flutter(d["y"], d["c"], d["EI"], d["GJ"], d["ea_c"], d["m_lin"], d["x_alfa_c"], r_giro_c, rho=rho, Vmax=Vmax, n_V=25, n_modos=min(n_modos, 4),
                    cl_alpha_2d=cl_alpha_2d, aileron=a)
        out["x_cg"].append(float(xg)); out["VF_x_cg"].append(r["VF"])
    return out

def analisa_flutter(esq: dict, nome: str, mats: dict | None = None, rho: float = R.RHO_NIVEL_MAR, Vd: float | None = None, fator: float = 1.2, x_ca_c: float = 0.25,
                    cl_alpha_2d: float = 2 * np.pi, calib_GJ: float = 1.0, ea_desloc_c: float = 0.0, massa_asa_kg: float | None = None,
                    x_cg_c: float | None = None, r_giro_c: float = 0.28, zeta_s: float = 0.0, V_max_rel: float = 3.0, n_V: int | None = None, n_modos: int | None = None,
                    itens=None, calib_EI: float = 1.0, massa_real: dict | None = None, aileron: dict | None = None, varre: bool = False) -> dict:
    from .. import discretizacao as DS
    n_modos = DS.flutter_n_modos() if n_modos is None else int(n_modos)
    n_V = DS.flutter_n_V() if n_V is None else int(n_V)
    if Vd is None:
        raise ValueError("informe Vd: velocidade de mergulho, em m/s")
    d = dados_de_vibracao(esq, nome, mats=mats, rho=rho, Vd=Vd, fator=fator, x_ca_c=x_ca_c, cl_alpha_2d=cl_alpha_2d, calib_GJ=calib_GJ, calib_EI=calib_EI,
                          ea_desloc_c=ea_desloc_c, massa_asa_kg=massa_asa_kg, x_cg_c=x_cg_c, r_giro_c=r_giro_c, itens=itens, massa_real=massa_real)
    r_giro_c = d["r_giro_c"]
    an, M, xcg = d["an"], d["M"], d["xcg"]
    avisos = []
    ail = None
    if aileron is not None:
        ail, info_ail = _aileron(esq, nome, d, aileron, zeta_s)
        if ail is None:
            avisos.append(info_ail)
    r = flutter(d["y"], d["c"], d["EI"], d["GJ"], d["ea_c"], d["m_lin"], d["x_alfa_c"], r_giro_c, rho=rho, Vmax=V_max_rel * Vd, n_V=n_V, n_modos=n_modos,
                zeta_s=zeta_s, cl_alpha_2d=cl_alpha_2d, aileron=ail)
    if ail is not None:
        r["aileron"] = info_ail
        if ail.get("_aviso"):
            avisos.append(ail["_aviso"])
        if varre:
            r["varredura"] = _varre_aileron(esq, nome, d, aileron, zeta_s, r_giro_c, rho, V_max_rel * Vd, n_modos, cl_alpha_2d,
                                            f_ref=max(r["f_vacuo_hz"][:4]))
    V_req = fator * Vd
    if r["VF"] is None and r["VD"] is None:
        avisos.append(f"Sem flutter nem divergencia ate {V_max_rel:g} x Vd ({V_max_rel * Vd:.1f} m/s) com estes dados.")
    if r["VF"] is not None:
        avisos.append(f"Flutter a {r['VF']:.1f} m/s, a {r['f_flutter_hz']:.1f} Hz.")
        f_max = max(r["f_vacuo_hz"]) if r["f_vacuo_hz"] else 0.0
        if r["f_flutter_hz"] and f_max < 3.0 * r["f_flutter_hz"]:
            DS.avisa(f"Flutter de {nome} a {r['f_flutter_hz']:.1f} Hz, mas o modo mais alto incluído vibra a {f_max:.1f} Hz "
                     f"(< 3× a do flutter): aumente os modos de vibração em Configurações → Discretização e confira se o VF muda.")
    dV = V_max_rel * Vd / max(1, n_V - 1)
    if r["VF"] is not None and abs(r["VF"] - V_req) < 2 * dV:
        DS.avisa(f"Flutter de {nome} a {r['VF']:.1f} m/s, a menos de dois passos da varredura (ΔV = {dV:.1f} m/s) do requisito "
                 f"({V_req:.1f} m/s): aumente as velocidades na varredura para o veredito não depender da interpolação.")
    if r["VD"] is not None:
        avisos.append(f"Divergencia (autovalor real cruza zero) a {r['VD']:.1f} m/s.")
    pm = d.get("perfil_massa")
    if pm is None:
        avisos.append("A massa da asa vem so dos itens estruturais do modelo (nervuras, longarina, tubos, chapeado), espalhada na proporcao da corda; servo, aileron, "
                      "entelagem e lastro nao entram se nao estiverem no modelo. Use a vista Massa da asa (real) para declara-los. A posicao do centro de massa e "
                      "o raio de giracao decidem o flutter: calibre com o ensaio de vibracao (GVT).")
    else:
        avisos += pm["avisos"]
        n = len(d["y"])
        c0 = d["c"]
        m0 = pm["massa_kg"] * c0 / np.trapezoid(c0, d["y"])
        xa0 = np.full(n, pm["x_cg_c"]) - d["ea_c"]
        S0, I0 = m0 * xa0 * c0, m0 * ((0.28 * c0) ** 2 + (xa0 * c0) ** 2)
        f_unif = modos_de_vibracao(d["y"], d["EI"], d["GJ"], m0, S0, I0, n_modos)["f_hz"]
    if any(not f for f in an["fechada"]):
        avisos.append("Parte da asa tem caixa aberta (GJ muito baixo): as frequencias de torcao e o flutter ficam dominados por essa regiao mole.")
    sai = {"nome": nome, "V_requerida": V_req, "fator": fator, "massa_semi_asa_kg": float(M), "origem_massa": d["origem_massa"], "x_cg_c": float(xcg),
           "origem_x_cg": d["origem_x_cg"], "r_giro_c": float(np.mean(r_giro_c)), "zeta_s": zeta_s, "rho": rho, "avisos": avisos, **r}
    if pm is not None:
        sai["perfil_massa"] = pm
        sai["f_vacuo_hz_massa_uniforme"] = f_unif
    sai["margem_VF"] = None if r["VF"] is None else r["VF"] / V_req - 1.0
    sai["margem_VD"] = None if r["VD"] is None else r["VD"] / V_req - 1.0
    return sai
