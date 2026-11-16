from __future__ import annotations

import math

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from ..aero.uvlm import UVLM, _malha
from .flutter import estrutura_modal


class Acoplamento:

    def __init__(self, u: UVLM, nome: str, est: dict, ea_c, simetria: str = "simetrico", dobradica_c=None):
        self.u, self.est = u, est
        self.N = int(est["N"]); self.Nw = int(est["Nw"])
        self.yb = np.asarray(est["y"], float)
        self.P = np.asarray(est["P"], float)
        self.ea_c = np.broadcast_to(np.asarray(ea_c, float), self.yb.shape)
        self.dob = None if dobradica_c is None else np.broadcast_to(np.asarray(dobradica_c, float), self.yb.shape)
        self.anti = simetria == "anti"
        try:
            self.s = next(s for s in u.te if s["nome"] == nome)
        except StopIteration:
            raise ValueError(f"superfície {nome!r} não está no UVLM") from None
        fa = u.vlm._fatias[nome]
        o = np.argsort(fa["y"])
        self._y_le = np.asarray(fa["y"])[o]
        cf = np.asarray(fa["c"])[o]
        self._x_le = (np.asarray(fa["x_quarto"]) - 0.25 * np.asarray(fa["c"]))[o]
        self._x_te = self._x_le + cf
        n_cp = len(u.cp)
        self.m_cp = np.zeros(n_cp, bool); self.m_cp[self.s["fatia"]] = True
        cont = [len(_malha(t["grade"], np.zeros((t["nc"], t["ns"])))[0]) for t in u.te]
        k = [i for i, t in enumerate(u.te) if t is self.s][0]
        self.m_mid = np.zeros(len(u._mid), bool); self.m_mid[sum(cont[:k]):sum(cont[:k + 1])] = True
        self.W_cp, self.S_cp = self.campo(u.cp, self.m_cp)
        self.W_mid, self.S_mid = self.campo(u._mid, self.m_mid)
        self.W_cen, _ = self.campo(u._centro, self.m_cp)
        ys = u.cp[self.m_cp, 1]
        self.fator = 0.5 if (ys.min() < -1e-9 and ys.max() > 1e-9) else 1.0
        self.q = np.zeros(self.N); self.qd = np.zeros(self.N)

    def campo(self, P, mascara=None):
        P = np.asarray(P, float)
        n = len(P)
        W = np.zeros((n, self.N)); S = np.zeros((n, self.N))
        m = np.ones(n, bool) if mascara is None else mascara
        if not m.any():
            return W, S
        x, y = P[m, 0], P[m, 1]
        ya = np.abs(y)
        sinal = np.sign(y) if self.anti else np.ones_like(y)
        x_le = np.interp(y, self._y_le, self._x_le); c = np.interp(y, self._y_le, self._x_te) - x_le
        x_ea = x_le + np.interp(ya, self.yb, self.ea_c) * c
        Wm = np.zeros((len(x), self.N)); Sm = np.zeros((len(x), self.N))
        for r in range(self.Nw):
            h = np.interp(ya, self.yb, self.P[:, 0, r]); al = np.interp(ya, self.yb, self.P[:, 1, r])
            Wm[:, r] = -(h + (x - x_ea) * al) * sinal
            Sm[:, r] = -al * sinal
        if self.N > self.Nw:
            mk = np.interp(ya, self.yb, self.P[:, 2, self.Nw])
            xh = x_le + np.interp(ya, self.yb, self.dob) * c
            atras = (x > xh) * mk
            Wm[:, self.Nw] = -(x - xh) * atras * sinal
            Sm[:, self.Nw] = -atras * sinal
        W[m], S[m] = Wm, Sm
        return W, S

    def movimento(self, t, P):
        u = self.u
        if P is u.cp:
            W, S = self.W_cp, self.S_cp
        elif P is u._mid:
            W, S = self.W_mid, self.S_mid
        else:
            W, S = self.campo(P)
        v = np.zeros((len(P), 3))
        v[:, 2] = W @ self.qd + u.V * (S @ self.q)
        return v

    def forca(self, t) -> np.ndarray:
        meio, Fseg, centro, Fn = self.u.forcas_distribuidas(t)
        return self.fator * (self.W_mid.T @ Fseg[:, 2] + self.W_cen.T @ Fn[:, 2])


class MarchaAeroelastica:

    def __init__(self, u: UVLM, ac: Acoplamento, tol: float = 1e-6, max_iter: int = 30):
        self.u, self.ac = u, ac
        e = ac.est
        self.M, self.C, self.K = (np.asarray(e[k], float) for k in ("Ms", "Cs", "Ks"))
        dt = u.dt
        self._lu = lu_factor(self.M + 0.5 * dt * self.C + 0.25 * dt * dt * self.K)
        u.movimento = ac.movimento
        self.tol, self.max_iter = float(tol), int(max_iter)
        self.hist = {"t": [], "q": [], "iter": []}

    def roda(self, n_passos: int, q0=None, qd0=None):
        u, ac, M, C, K = self.u, self.ac, self.M, self.C, self.K
        N = ac.N
        dt = u.dt
        q = np.zeros(N) if q0 is None else np.asarray(q0, float).copy()
        v = np.zeros(N) if qd0 is None else np.asarray(qd0, float).copy()
        a = np.linalg.solve(M, -C @ v - K @ q)
        escala = max(1e-12, float(np.abs(np.r_[q, v * dt]).max()))
        for _ in range(int(n_passos)):
            t = u._prepara_passo()
            xk = np.r_[q + dt * v + 0.5 * dt * dt * a, v + dt * a]
            omega, r_ant = 0.5, None
            for it in range(self.max_iter):
                ac.q, ac.qd = xk[:N], xk[N:]
                u._resolve_G(t)
                Q = ac.forca(t)
                an = lu_solve(self._lu, Q - C @ (v + 0.5 * dt * a) - K @ (q + dt * v + 0.25 * dt * dt * a))
                xt = np.r_[q + dt * v + 0.25 * dt * dt * (a + an), v + 0.5 * dt * (a + an)]
                r = xt - xk
                escala = max(escala, float(np.abs(np.r_[xt[:N], xt[N:] * dt]).max()))
                if float(np.abs(np.r_[r[:N], r[N:] * dt]).max()) <= self.tol * escala:
                    xk = xt
                    break
                if r_ant is not None:
                    dr = r - r_ant
                    den = float(dr @ dr)
                    if den > 0:
                        omega = float(np.clip(-omega * (r_ant @ dr) / den, 0.05, 1.5))
                xk = xk + omega * r
                r_ant = r
            ac.q, ac.qd = xk[:N], xk[N:]
            q, v, a = xk[:N].copy(), xk[N:].copy(), an
            u._registra(t)
            self.hist["t"].append(t); self.hist["q"].append(q.copy()); self.hist["iter"].append(it + 1)
        return self.hist


def lapis_de_matrizes(Y, dt: float, ordem: int | None = None, f_min: float = 0.1, tol_sv: float = 1e-7) -> list[dict]:
    Y = np.atleast_2d(np.asarray(Y, float))
    if Y.shape[0] < Y.shape[1]:
        Y = Y.T
    n, nc = Y.shape
    L = n // 2
    H = np.vstack([np.lib.stride_tricks.sliding_window_view(Y[:, c], L + 1) for c in range(nc)])
    _, sv, Vt = np.linalg.svd(H, full_matrices=False)
    Mo = int(np.sum(sv > tol_sv * sv[0])) if ordem is None else int(ordem)
    Mo = max(1, min(Mo, L))
    Vp = Vt[:Mo].T
    z = np.linalg.eigvals(np.linalg.pinv(Vp[:-1]) @ Vp[1:])
    s = np.log(z.astype(complex)) / dt
    Z = z[None, :] ** np.arange(n)[:, None]
    B = np.linalg.lstsq(Z, Y.astype(complex), rcond=None)[0]
    ener = np.sum(np.abs(B) ** 2, axis=1)
    out = []
    for si, ei in zip(s, ener):
        f = si.imag / (2 * math.pi)
        if f > f_min:
            out.append({"s": si, "f_hz": float(f), "zeta": float(-si.real / abs(si)), "energia": float(ei)})
    out.sort(key=lambda d: -d["energia"])
    return out


def modos_identificados(hist: dict, dt: float, t_descarta: float, f_lim: tuple[float, float], frac: float = 0.02) -> list[dict]:
    t = np.asarray(hist["t"]); Q = np.asarray(hist["q"])
    k = t > t_descarta
    if k.sum() < 20:
        raise ValueError("histórico curto demais para identificar os modos")
    Y = Q[k] - Q[k].mean(axis=0)
    ordem = min(2 * Q.shape[1] + 4, Y.shape[0] // 3)
    ms = [m for m in lapis_de_matrizes(Y, dt, ordem=ordem) if f_lim[0] <= m["f_hz"] <= f_lim[1] and abs(m["zeta"]) < 0.6]
    if not ms:
        return []
    e0 = max(m["energia"] for m in ms)
    return [m for m in ms if m["energia"] >= frac * e0]


def marcha(superficies, nome: str, est: dict, ea_c, V: float, rho: float, n_ciclos: float = 8.0, passos_por_corda: int = 4,
           alpha_graus: float = 0.0, simetria: str = "simetrico", dobradica_c=None, perturbacao: float = 1e-4,
           fileiras_esteira: int | None = None, x_ref: float = 0.0, f_alvo: float | None = None) -> dict:
    import warnings
    from ..aero.vlm import VLM
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = VLM(superficies).c_ref
    f = np.sqrt(np.clip(np.diag(est["Ks"]) / np.diag(est["Ms"]), 0, None)) / (2 * math.pi)
    f_min = max(0.05, float(f[f > 0].min()) if np.any(f > 0) else 1.0)
    f_max = float(f.max())
    if f_alvo:
        f_ref = float(f_alvo)
    else:
        f_ref = float(np.sort(f[f > 0])[:2][-1]) if np.any(f > 0) else 1.0
    dt = min(c / (passos_por_corda * V), 1.0 / (24.0 * f_ref))
    T = max(n_ciclos / f_alvo, 2.0 / f_min) if f_alvo else n_ciclos / f_min
    n = int(math.ceil(T / dt))
    fil = int(fileiras_esteira or min(n + 2, math.ceil(30 * c / (V * dt))))
    u = UVLM(superficies, V, alpha_graus=alpha_graus, rho=rho, dt=dt, esteira_livre=False, x_ref=x_ref, max_fileiras=fil)
    u.so_perturbacao = True
    ac = Acoplamento(u, nome, est, ea_c, simetria, dobradica_c)
    m = MarchaAeroelastica(u, ac)
    Pm = np.abs(np.asarray(est["P"], float))
    amp = np.array([perturbacao / max(Pm[:, 1, r].max() if r < ac.Nw else Pm[:, 2, r].max(), Pm[:, 0, r].max() / c, 1e-30)
                    for r in range(ac.N)])
    w = 2 * math.pi * np.maximum(f, f_min)
    qd0 = amp * np.r_[w, np.full(ac.N - len(w), w[-1])][:ac.N]
    h = m.roda(n, qd0=qd0)
    t_desc = min(2.0 / (f_alvo or f_min), 0.35 * T)
    modos = modos_identificados(h, u.dt, t_desc, (0.3 * f_min, min(1.5 * f_max, 0.4 / u.dt)))
    pior = min(modos, key=lambda d: d["zeta"]) if modos else None
    div = polo_real(h, u.dt, t_desc, f_min)
    return {"V": V, "t": h["t"], "q": np.asarray(h["q"]), "iter": h["iter"], "modos": modos, "pior": pior,
            "dt": u.dt, "CL": u.h.CL, "n_passos": n, "divergencia": div}


def polo_real(hist: dict, dt: float, t_descarta: float, f_min: float, frac: float = 0.02) -> dict | None:
    t = np.asarray(hist["t"]); Q = np.asarray(hist["q"])
    k = t > t_descarta
    n = int(k.sum())
    if n < 20:
        return None
    ms = lapis_de_matrizes(Q[k], dt, ordem=min(2 * Q.shape[1] + 4, n // 3), f_min=-math.inf)
    janela = float(t[k][-1] - t[k][0])
    f_real = 0.25 * f_min
    ms = [m for m in ms if m["s"].real * janela < 8.0 and (abs(m["f_hz"]) < f_real or abs(m["zeta"]) < 0.6)]
    e0 = max((m["energia"] for m in ms), default=0.0)
    reais = [m for m in ms if abs(m["f_hz"]) < f_real and m["energia"] >= frac * e0]
    if not reais:
        return None
    r = max(reais, key=lambda m: m["s"].real)
    return {"s_real": float(r["s"].real), "energia_rel": float(r["energia"] / e0), "diverge": bool(r["s"].real > 0)}


def divergencia_estatica(superficies, nome: str, est: dict, ea_c, rho: float, V_ref: float = 10.0,
                         simetria: str = "simetrico", dobradica_c=None, x_ref: float = 0.0, cordas: float = 40.0,
                         passos: int = 40) -> dict:
    import warnings
    from ..aero.vlm import VLM
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = VLM(superficies).c_ref
    N = int(est["N"])
    dt = cordas * c / (passos * V_ref)
    Q0 = np.zeros((N, N))
    for r in range(N):
        u = UVLM(superficies, V_ref, rho=rho, dt=dt, esteira_livre=False, x_ref=x_ref, max_fileiras=passos + 2)
        u.so_perturbacao = True
        ac = Acoplamento(u, nome, est, ea_c, simetria, dobradica_c)
        u.movimento = ac.movimento
        ac.q = np.eye(N)[r]; ac.qd = np.zeros(N)
        u.roda(passos)
        Q0[:, r] = ac.forca(u.t)
    K = np.asarray(est["Ks"], float)
    mu = np.linalg.eigvals(np.linalg.solve(K, Q0))
    esc = np.abs(mu).max() or 1.0
    reais = mu.real[(np.abs(mu.imag) < 1e-6 * esc) & (mu.real > 1e-9 * esc)]
    VD = float(V_ref / math.sqrt(reais.max())) if len(reais) else None
    return {"VD": VD, "Q0": Q0, "V_ref": V_ref, "simetria": simetria}


def velocidade_de_flutter(superficies, nome: str, est: dict, ea_c, Vs, rho: float, refina: bool = True, **kw) -> dict:
    res = []
    for V in sorted(Vs):
        r = marcha(superficies, nome, est, ea_c, float(V), rho, **kw)
        res.append(r)
    VF = fF = VD = None
    sr = [r["divergencia"]["s_real"] if r.get("divergencia") else np.nan for r in res]
    for i in range(1, len(res)):
        if np.isfinite(sr[i - 1]) and np.isfinite(sr[i]) and sr[i - 1] <= 0 < sr[i]:
            V0, V1 = res[i - 1]["V"], res[i]["V"]
            VD = V0 - sr[i - 1] / (sr[i] - sr[i - 1]) * (V1 - V0)
            break

    def perto(r, f):
        ms = r["modos"] or ([r["pior"]] if r["pior"] else [])
        if not ms:
            return None
        m = min(ms, key=lambda x: abs(x["f_hz"] - f))
        return m if abs(m["f_hz"] - f) < 0.3 * f else None

    for i in range(1, len(res)):
        m1 = res[i]["pior"]
        if not m1 or m1["zeta"] > 0 or not all(x["zeta"] > 0 for x in res[i - 1]["modos"]):
            continue
        m0 = perto(res[i - 1], m1["f_hz"])
        if m0 is None:
            continue
        V0, V1 = res[i - 1]["V"], res[i]["V"]
        z0, z1, f0, f1 = m0["zeta"], m1["zeta"], m0["f_hz"], m1["f_hz"]
        VF = V0 + z0 / (z0 - z1) * (V1 - V0)
        fF = f0 + (VF - V0) / (V1 - V0) * (f1 - f0)
        if refina and V1 - V0 > 0.02 * VF:
            rm = marcha(superficies, nome, est, ea_c, float(VF), rho, **kw)
            res.append(rm); res.sort(key=lambda r_: r_["V"])
            mm = perto(rm, fF)
            if mm is not None:
                zm, fm = mm["zeta"], mm["f_hz"]
                Va, za, fa, Vb, zb, fb = (VF, zm, fm, V1, z1, f1) if zm > 0 else (V0, z0, f0, VF, zm, fm)
                VF = Va + za / (za - zb) * (Vb - Va)
                fF = fa + (VF - Va) / (Vb - Va) * (fb - fa)
        break
    return {"VF": VF, "f_flutter_hz": fF, "VD": VD, "marchas": res}


FATOR_ITERACOES = 1.2


def analisa_no_tempo(esq: dict, nome: str, rho: float, Vd: float, fatores=(0.75, 0.95, 1.15, 1.4), n_span=None,
                     n_chord: int | None = None, passos_por_corda: int = 4, n_ciclos: float = 8.0, aileron: dict | None = None,
                     zeta_s: float = 0.0, n_modos: int | None = None, forcar: bool = False, so_a_asa: bool = True,
                     **kw_dados) -> dict:
    import warnings
    from .. import discretizacao as DS
    from ..aero.aeronave_vlm import superficies
    from ..aero.vlm import VLM
    from .flutter import _aileron, dados_de_vibracao, flutter
    n_modos = DS.flutter_n_modos() if n_modos is None else int(n_modos)
    d = dados_de_vibracao(esq, nome, rho=rho, Vd=Vd, **kw_dados)
    ail = info_ail = None
    if aileron is not None:
        ail, info_ail = _aileron(esq, nome, d, aileron, zeta_s)
    cl2d = kw_dados.get("cl_alpha_2d", 2 * math.pi)
    pk = flutter(d["y"], d["c"], d["EI"], d["GJ"], d["ea_c"], d["m_lin"], d["x_alfa_c"], d["r_giro_c"], rho=rho,
                 Vmax=3.0 * Vd, n_V=DS.flutter_n_V(), n_modos=n_modos, zeta_s=zeta_s, cl_alpha_2d=cl2d, aileron=ail)
    est = estrutura_modal(d["y"], d["c"], d["EI"], d["GJ"], d["ea_c"], d["m_lin"], d["x_alfa_c"], d["r_giro_c"], n_modos,
                          zeta_s, ail, cl2d, rho)
    V0 = pk["VF"] if pk["VF"] else Vd
    Vs = [f * V0 for f in fatores]
    simetria = "anti" if ail is not None else "simetrico"
    dob = None if ail is None else (np.asarray(ail["c"], float) + 1.0) / 2.0
    f_t = float(pk["f_flutter_hz"] or max(pk["f_vacuo_hz"][:2]))
    b_med = 0.25 * float(np.mean(d["c"])) * 2
    k = 2 * math.pi * f_t * b_med / V0
    motivo_nc = f"frequência reduzida do flutter k ≈ {k:.2f}: erro da massa aparente ≈ 1,2 k / n_chord ≤ 5 %"
    nc = n_chord or int(min(12, max(4, math.ceil(1.2 * k / 0.05))))
    with warnings.catch_warnings(), DS.silencio():
        warnings.simplefilter("ignore")
        sup = superficies(esq, n_span, nc)
        if so_a_asa:
            sup = [x for x in sup if x.planform.nome == nome] or sup
        vb = VLM(sup)
        div3 = {sm: divergencia_estatica(sup, nome, est, d["ea_c"], rho, V_ref=V0, simetria=sm, dobradica_c=dob)["VD"]
                for sm in ("simetrico", "anti")}
    VD3 = min((v for v in div3.values() if v), default=None)
    from .torcao import aeroelastica as _torcao_faixas
    VD_faixas = _torcao_faixas(d["y"], d["c"], d["GJ"], d["ea_c"], kw_dados.get("x_ca_c", 0.25), None, cl2d, rho, Vd,
                               kw_dados.get("fator", 1.2))["VD"]
    VD_sim = div3[simetria]
    if VD_sim and VD_sim < max(Vs):
        for fv in (0.95, 1.05):
            if all(abs(fv * VD_sim - v) > 0.025 * VD_sim for v in Vs):
                Vs.append(fv * VD_sim)
    Vs = sorted(Vs)
    c_ref = vb.c_ref
    f_min = float(min(f for f in pk["f_vacuo_hz"] if f > 0))
    faixas = sum(f["ns"] for f in vb._fatias.values())
    custo = {"segundos": 0.0, "interacoes": 0.0, "memoria_bytes": 0.0}
    for V in Vs + [V0]:
        dt_ = min(c_ref / (passos_por_corda * V), 1.0 / (24.0 * f_t))
        n = int(math.ceil(max(n_ciclos / f_t, 2.0 / f_min) / dt_))
        cc = DS.custo_uvlm(vb.N, faixas, n, min(n + 2, math.ceil(30 * c_ref / (V * dt_))), False, None)
        custo["segundos"] += FATOR_ITERACOES * cc["segundos"]; custo["interacoes"] += FATOR_ITERACOES * cc["interacoes"]
        custo["memoria_bytes"] = max(custo["memoria_bytes"], cc["memoria_bytes"])
    cd = DS.custo_uvlm(vb.N, faixas, 40, 42, False, None)
    custo["segundos"] += 2 * est["N"] * cd["segundos"]; custo["interacoes"] += 2 * est["N"] * cd["interacoes"]
    DS.confere_orcamento(custo, f"Flutter no tempo de {nome}", forcar=forcar)
    r = velocidade_de_flutter(sup, nome, est, d["ea_c"], Vs, rho, n_ciclos=n_ciclos, passos_por_corda=passos_por_corda,
                              simetria=simetria, dobradica_c=dob, f_alvo=f_t)
    P = est["P"]
    h_tip, a_tip = P[-1, 0, :], P[-1, 1, :]
    marchas = []
    for m in r["marchas"]:
        q = m["q"]
        dec = max(1, len(q) // 300)
        al = q @ a_tip; hh = -(q @ h_tip)
        ra = float(np.abs(al[: max(2, len(al) // 4)]).max()) or 1.0
        rh = float(np.abs(hh[: max(2, len(hh) // 4)]).max()) or 1.0
        marchas.append({"V": m["V"], "zeta": m["pior"]["zeta"] if m["pior"] else None, "f_hz": m["pior"]["f_hz"] if m["pior"] else None,
                        "divergencia": m.get("divergencia"),
                        "modos": [{"f_hz": x["f_hz"], "zeta": x["zeta"]} for x in m["modos"]],
                        "t": list(map(float, m["t"][::dec])), "h_ponta_rel": (hh / rh)[::dec].tolist(),
                        "alfa_ponta_rel": (al / ra)[::dec].tolist(), "iter_max": int(max(m["iter"]))})
    V_com = next((m["V"] for m in marchas if m["divergencia"] and m["divergencia"]["diverge"]), None)
    return {"nome": nome, "VF": r["VF"], "f_flutter_hz": r["f_flutter_hz"], "VF_pk": pk["VF"], "f_flutter_pk_hz": pk["f_flutter_hz"],
            "VD_3d": VD3, "VD_3d_simetrias": div3, "VD_faixas": VD_faixas, "VD_pk": pk.get("VD"),
            "VD_marcha": r["VD"], "V_cresce_sem_oscilar": V_com,
            "pk": {"V": pk["V"], "amortecimento": pk["amortecimento"], "natureza": pk["natureza"]},
            "V_requerida": kw_dados.get("fator", 1.2) * Vd, "marchas": marchas, "simetria": simetria, "aileron": info_ail,
            "discretizacao": {"n_chord": nc, "motivo_n_chord": motivo_nc, "passos_por_corda": passos_por_corda,
                              "n_ciclos": n_ciclos, "paineis": vb.N, "superficies": [x.planform.nome for x in sup]},
            "estimativa_s": custo["segundos"], "f_vacuo_hz": pk["f_vacuo_hz"]}
