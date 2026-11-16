from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

MU_AR = 1.81e-5


@dataclass
class Pa:
    D: float
    B: int
    r_R: np.ndarray
    c_R: np.ndarray
    beta_graus: np.ndarray
    r_cubo_R: float = 0.12
    perfil: object = None
    nome: str = ""

    def __post_init__(self):
        self.r_R = np.asarray(self.r_R, float); self.c_R = np.asarray(self.c_R, float); self.beta_graus = np.asarray(self.beta_graus, float)

    @property
    def R(self) -> float:
        return 0.5 * self.D


def _coef(perfil, alpha_graus, Re):
    if perfil is None:
        a = np.radians(alpha_graus)
        return 2 * np.pi * a, np.full_like(a, 0.0)
    if callable(perfil) and not hasattr(perfil, "alpha"):
        return perfil(alpha_graus, Re)
    cl, cd, _ = perfil(alpha_graus, np.clip(Re, perfil.re[0], perfil.re[-1]), avisar=False)
    return cl, cd


@dataclass
class Resultado:
    J: float
    CT: float
    CP: float
    CQ: float
    eta: float
    T: float
    Q: float
    P: float
    rpm: float
    V: float
    r: np.ndarray = field(repr=False, default=None)
    dT: np.ndarray = field(repr=False, default=None)
    dQ: np.ndarray = field(repr=False, default=None)
    v_a: np.ndarray = field(repr=False, default=None)
    v_t: np.ndarray = field(repr=False, default=None)
    alpha: np.ndarray = field(repr=False, default=None)
    Re: np.ndarray = field(repr=False, default=None)
    F: np.ndarray = field(repr=False, default=None)
    dr: np.ndarray = field(repr=False, default=None)
    convergiu: bool = True


def _residuo(phi, x_ctx):
    sig, Vx, Vy, beta, B, r, R, rc, perfil, Re, perdas = x_ctx
    alpha = np.degrees(beta - phi)
    cl, cd = _coef(perfil, alpha, Re)
    s_, c_ = np.sin(phi), np.cos(phi)
    cn = cl * c_ - cd * s_
    ct = cl * s_ + cd * c_
    if perdas:
        sp = np.maximum(np.abs(s_), 1e-9)
        F = (2 / np.pi) ** 2 * np.arccos(np.clip(np.exp(-B / 2 * (R - r) / (r * sp)), 0, 1)) \
            * np.arccos(np.clip(np.exp(-B / 2 * (r - rc) / (rc * sp)), 0, 1))
        F = np.maximum(F, 1e-6)
    else:
        F = np.ones_like(r)
    k = sig * cn / (4 * F * s_ * s_)
    kp = sig * ct / (4 * F * s_ * c_)
    return s_ * (1 - k) - Vx / Vy * c_ * (1 + kp), k, kp, cl, cd, F


def analisa(pa: Pa, V: float, rpm: float, rho: float = 1.225, n_est: int = 40, perdas: bool = True,
            n_re: int = 3) -> Resultado:
    R, B = pa.R, pa.B
    Om = 2 * math.pi * rpm / 60.0
    n = rpm / 60.0
    e = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n_est + 1)))
    xb = pa.r_cubo_R + (1 - pa.r_cubo_R) * e
    x = 0.5 * (xb[1:] + xb[:-1]); dx = np.diff(xb)
    r, dr = x * R, dx * R
    c = np.interp(x, pa.r_R, pa.c_R) * R
    beta = np.radians(np.interp(x, pa.r_R, pa.beta_graus))
    rc = pa.r_cubo_R * R
    sig = B * c / (2 * np.pi * r)
    Vx, Vy = max(float(V), 0.0), Om * r
    Re = rho * np.sqrt(Vx ** 2 + Vy ** 2) * c / MU_AR
    ok = np.ones_like(r, bool)
    for _ in range(max(1, n_re)):
        ctx = (sig, Vx, Vy, beta, B, r, R, rc, pa.perfil, Re, perdas)
        grade = np.r_[np.linspace(1e-6, np.pi / 2, 46), -np.linspace(1e-6, np.pi / 2, 46)]
        Rg = np.array([_residuo(np.full_like(r, g), ctx)[0] for g in grade])
        lo, hi = np.full_like(r, np.nan), np.full_like(r, np.nan)
        for j in range(len(r)):
            for i in range(len(grade) - 1):
                if i == 45:
                    continue
                if np.sign(Rg[i, j]) != np.sign(Rg[i + 1, j]) and np.isfinite(Rg[i, j]) and np.isfinite(Rg[i + 1, j]):
                    lo[j], hi[j] = grade[i], grade[i + 1]
                    break
        ok = np.isfinite(lo)
        lo = np.where(ok, lo, 1e-6); hi = np.where(ok, hi, np.pi / 2)
        flo = _residuo(lo, ctx)[0]
        for _ in range(60):
            m = 0.5 * (lo + hi)
            fm = _residuo(m, ctx)[0]
            mesmo = np.sign(fm) == np.sign(flo)
            lo = np.where(mesmo, m, lo); flo = np.where(mesmo, fm, flo)
            hi = np.where(mesmo, hi, m)
        phi = 0.5 * (lo + hi)
        _, k, kp, cl, cd, F = _residuo(phi, ctx)
        ut = Vy / (1 + kp)
        ua = ut * np.tan(phi)
        W2 = ua * ua + ut * ut
        Re = rho * np.sqrt(W2) * c / MU_AR
    alpha = np.degrees(beta - phi)
    cl, cd = _coef(pa.perfil, alpha, Re)
    dT = 0.5 * rho * W2 * B * c * (cl * np.cos(phi) - cd * np.sin(phi))
    dQ = 0.5 * rho * W2 * B * c * (cl * np.sin(phi) + cd * np.cos(phi)) * r
    dT = np.where(ok, dT, 0.0); dQ = np.where(ok, dQ, 0.0)
    T, Q = float(np.sum(dT * dr)), float(np.sum(dQ * dr))
    P = Q * Om
    D = pa.D
    CT = T / (rho * n * n * D ** 4) if n > 0 else 0.0
    CP = P / (rho * n ** 3 * D ** 5) if n > 0 else 0.0
    J = V / (n * D) if n > 0 else 0.0
    eta = J * CT / CP if CP > 1e-12 and CT > 0 else 0.0
    return Resultado(J=J, CT=CT, CP=CP, CQ=CP / (2 * np.pi), eta=eta, T=T, Q=Q, P=P, rpm=rpm, V=V, r=r, dT=dT, dQ=dQ,
                     v_a=ua - Vx, v_t=Vy - ut, alpha=alpha, Re=Re, F=F, dr=dr, convergiu=bool(ok.all()))


def curva(pa: Pa, rpm: float, Js, rho: float = 1.225, **kw) -> list[Resultado]:
    n = rpm / 60.0
    return [analisa(pa, float(J) * n * pa.D, rpm, rho, **kw) for J in np.atleast_1d(Js)]


def projeto_otimo(B: int, D: float, rpm: float, V: float, T: float, rho: float = 1.225, r_cubo_R: float = 0.12,
                  cl_projeto: float = 0.6, cd_cl=lambda cl, Re: 0.0, alpha_projeto=None, n_est: int = 40,
                  tol: float = 1e-10, max_iter: int = 200) -> dict:
    R = 0.5 * D
    Om = 2 * math.pi * rpm / 60.0
    lam = V / (Om * R)
    e = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n_est + 1)))
    xi_b = r_cubo_R + (1 - r_cubo_R) * e
    xi = 0.5 * (xi_b[1:] + xi_b[:-1]); dxi = np.diff(xi_b)
    Tc = 2 * T / (rho * V * V * np.pi * R * R)
    zeta = 0.0
    for _ in range(max_iter):
        tphi_t = lam * (1 + zeta / 2)
        phi_t = math.atan(tphi_t)
        phi = np.arctan(tphi_t / xi)
        f = B / 2 * (1 - xi) / math.sin(phi_t)
        F = (2 / np.pi) * np.arccos(np.exp(-f))
        xx = xi / lam
        G = F * xx * np.cos(phi) * np.sin(phi)
        Wc = 4 * np.pi * lam * G * V * R * zeta / (cl_projeto * B)
        a0 = zeta / 2 * np.cos(phi) ** 2
        W = V * (1 + a0) / np.sin(phi)
        c = np.where(W > 0, Wc / W, 0.0)
        Re = rho * W * c / MU_AR
        eps = np.asarray(cd_cl(cl_projeto, Re), float) * np.ones_like(xi)
        tphi = np.tan(phi)
        I1p = 4 * xi * G * (1 - eps * tphi)
        I2p = lam * (I1p / (2 * xi)) * (1 + eps / tphi) * np.sin(phi) * np.cos(phi)
        J1p = 4 * xi * G * (1 + eps / tphi)
        J2p = (J1p / 2) * (1 - eps * tphi) * np.cos(phi) ** 2
        I1, I2, J1, J2 = (float(np.sum(v * dxi)) for v in (I1p, I2p, J1p, J2p))
        disc = (I1 / (2 * I2)) ** 2 - Tc / I2
        if disc < 0:
            raise ValueError("tração pedida grande demais para esse diâmetro e rotação (sem solução de mínima perda)")
        zeta_n = I1 / (2 * I2) - math.sqrt(disc)
        if abs(zeta_n - zeta) < tol:
            zeta = zeta_n
            break
        zeta = zeta_n
    a = zeta / 2 * np.cos(phi) ** 2 * (1 - eps * tphi)
    W = V * (1 + a) / np.sin(phi)
    c = Wc / W
    Re = rho * W * c / MU_AR
    alpha = np.asarray(alpha_projeto(Re), float) * np.ones_like(xi) if alpha_projeto else np.degrees(cl_projeto / (2 * np.pi)) * np.ones_like(xi)
    beta = alpha + np.degrees(phi)
    Pc = J1 * zeta + J2 * zeta ** 2
    P = Pc * 0.5 * rho * V ** 3 * np.pi * R * R
    return {"r_R": xi, "c_R": c / R, "beta_graus": beta, "zeta": zeta, "Tc": Tc, "Pc": Pc, "eta": Tc / Pc, "P": P,
            "T": T, "Re": Re, "alpha": alpha, "F": F}


def eficiencia_ideal(T: float, V: float, D: float, rho: float = 1.225) -> float:
    Tc = T / (0.5 * rho * V * V * np.pi * D * D / 4)
    return 2.0 / (1.0 + math.sqrt(1.0 + Tc))


_APC_E_x = np.array([0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.75, 0.80, 0.90, 0.95, 1.00])
_APC_E_c = np.array([0.110, 0.132, 0.169, 0.186, 0.183, 0.167, 0.146, 0.135, 0.121, 0.088, 0.066, 0.040])


def apc_tipica(D_pol: float, passo_pol: float, perfil=None, B: int = 2) -> Pa:
    D = D_pol * 0.0254
    x = _APC_E_x
    beta = np.degrees(np.arctan(passo_pol / (np.pi * D_pol * x)))
    return Pa(D=D, B=B, r_R=x, c_R=_APC_E_c, beta_graus=beta, r_cubo_R=0.15, perfil=perfil, nome=f"{D_pol:g}x{passo_pol:g} (forma típica APC E)")


@dataclass
class Sopro:
    centro: np.ndarray
    eixo: np.ndarray
    R: float
    V: float
    r_b: np.ndarray
    v_a: np.ndarray
    v_t: np.ndarray
    sentido: int = 1

    def bordas(self, x: float):
        k = 1 + x / math.sqrt(x * x + self.R ** 2)
        V = max(self.V, 1e-6)
        vaz = (V + self.v_a) * np.diff(self.r_b ** 2)
        r2 = self.r_b[0] ** 2 + np.r_[0.0, np.cumsum(vaz / np.maximum(V + k * self.v_a, 1e-9))]
        return np.sqrt(r2), k

    def velocidade(self, P: np.ndarray) -> np.ndarray:
        P = np.atleast_2d(np.asarray(P, float))
        e = self.eixo / np.linalg.norm(self.eixo)
        d = P - self.centro
        x = d @ e
        radial = d - x[:, None] * e
        rho = np.linalg.norm(radial, axis=1)
        out = np.zeros_like(P)
        rm0 = 0.5 * (self.r_b[1:] + self.r_b[:-1])
        for i in range(len(P)):
            rb, k = self.bordas(float(x[i]))
            if not (rb[0] <= rho[i] < rb[-1]):
                continue
            j = min(int(np.searchsorted(rb, rho[i], side="right")) - 1, len(self.v_a) - 1)
            rm = 0.5 * (rb[j] + rb[j + 1])
            vtan = k * self.v_t[j] * rm0[j] / max(rho[i], 1e-9)
            er = radial[i] / max(rho[i], 1e-12)
            out[i] = k * self.v_a[j] * e + vtan * np.cross(er, e) * self.sentido
        return out


def sopro_de(res: Resultado, centro, eixo=(1.0, 0.0, 0.0), sentido: int = 1) -> Sopro:
    r_b = np.r_[res.r[0] - 0.5 * res.dr[0], res.r + 0.5 * res.dr]
    return Sopro(centro=np.asarray(centro, float), eixo=np.asarray(eixo, float), R=float(r_b[-1]), V=res.V, r_b=r_b,
                 v_a=res.v_a.copy(), v_t=res.v_t.copy(), sentido=sentido)
