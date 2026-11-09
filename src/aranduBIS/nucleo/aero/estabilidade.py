from __future__ import annotations
_G = 9.80665
RHO_AR = 1.225

from dataclasses import dataclass, field

import numpy as np

from .vlm import VLM

@dataclass
class Derivadas:

    alpha: float
    CL: float
    CDi: float
    Cm: float

    CL_alpha: float
    Cm_alpha: float
    CY_beta: float = 0.0
    Cl_beta: float = 0.0
    Cn_beta: float = 0.0
    Cl_p: float = 0.0
    Cn_p: float = 0.0
    Cm_q: float = 0.0
    Cl_r: float = 0.0
    Cn_r: float = 0.0
    controles: dict[str, dict[str, float]] = field(default_factory=dict)
    x_ref: float = 0.0
    c_ref: float = 1.0

    @property
    def margem_estatica(self) -> float:
        if abs(self.CL_alpha) < 1e-12:
            return float("nan")
        return -self.Cm_alpha / self.CL_alpha

    @property
    def ponto_neutro(self) -> float:
        if abs(self.CL_alpha) < 1e-12:
            return float("nan")
        return self.x_ref + self.margem_estatica * self.c_ref

    @property
    def estavel_longitudinal(self) -> bool:
        return self.Cm_alpha < 0.0

    @property
    def estavel_direcional(self) -> bool:
        return self.Cn_beta > 0.0

    def __repr__(self) -> str:
        return (f"<Derivadas α={self.alpha:.1f}° CL={self.CL:.3f} "
                f"Cmα={self.Cm_alpha:+.4f} Cnβ={self.Cn_beta:+.4f} "
                f"Clp={self.Cl_p:+.4f} MS={100*self.margem_estatica:+.1f}% MAC>")

def derivadas(vlm: VLM, alpha: float, V: float = 1.0, rho: float = 1.0,
              h: float = 0.5, h_taxa: float = 0.01,
              laterais: bool = True) -> Derivadas:
    b, c = vlm.b_ref, vlm.c_ref
    base = vlm.resolver(alpha, V=V, rho=rho)[0]

    ap = vlm.resolver(alpha + h, V=V, rho=rho)[0]
    am = vlm.resolver(alpha - h, V=V, rho=rho)[0]
    d_a = np.radians(2 * h)
    CLa = (ap.CL - am.CL) / d_a
    Cma = (ap.Cm - am.Cm) / d_a

    d = Derivadas(alpha=alpha, CL=base.CL, CDi=base.CDi, Cm=base.Cm,
                  x_ref=vlm.x_ref, c_ref=c,
                  CL_alpha=CLa, Cm_alpha=Cma)
    if not laterais:
        return d

    bp = vlm.resolver(alpha, V=V, rho=rho, beta=+h)[0]
    bm = vlm.resolver(alpha, V=V, rho=rho, beta=-h)[0]
    d.CY_beta = (bp.CY - bm.CY) / d_a
    d.Cl_beta = (bp.Cl - bm.Cl) / d_a
    d.Cn_beta = (bp.Cn - bm.Cn) / d_a

    pp = vlm.resolver(alpha, V=V, rho=rho, p=+h_taxa * 2 * V / b)[0]
    pm = vlm.resolver(alpha, V=V, rho=rho, p=-h_taxa * 2 * V / b)[0]
    d.Cl_p = (pp.Cl - pm.Cl) / (2 * h_taxa)
    d.Cn_p = (pp.Cn - pm.Cn) / (2 * h_taxa)

    qp = vlm.resolver(alpha, V=V, rho=rho, q_taxa=+h_taxa * 2 * V / c)[0]
    qm = vlm.resolver(alpha, V=V, rho=rho, q_taxa=-h_taxa * 2 * V / c)[0]
    d.Cm_q = (qp.Cm - qm.Cm) / (2 * h_taxa)

    rp = vlm.resolver(alpha, V=V, rho=rho, r_taxa=+h_taxa * 2 * V / b)[0]
    rm = vlm.resolver(alpha, V=V, rho=rho, r_taxa=-h_taxa * 2 * V / b)[0]
    d.Cl_r = (rp.Cl - rm.Cl) / (2 * h_taxa)
    d.Cn_r = (rp.Cn - rm.Cn) / (2 * h_taxa)
    return d

@dataclass
class MomentoCharneira:

    superficie: str
    deflexao: float
    velocidade: float
    Ch: float
    momento_Nm: float
    area_m2: float
    corda_m: float

    @property
    def torque_kgfcm(self) -> float:
        return self.momento_Nm * 100.0 / _G

    def __repr__(self) -> str:
        return (f"<Charneira {self.superficie} δ={self.deflexao:+.0f}° "
                f"V={self.velocidade:.0f} m/s: {self.momento_Nm:.3f} N·m "
                f"= {self.torque_kgfcm:.2f} kgf·cm>")

def momento_charneira(vlm: VLM, superficie: str, deflexao: float, alpha: float,
                      V: float, faixas: slice | None = None,
                      x_charneira: float = 0.75, rho: float = RHO_AR
                      ) -> MomentoCharneira:
    info = vlm._fatias[superficie]
    ns, nc = info["ns"], info["nc"]
    sel = faixas if faixas is not None else slice(None)

    d = np.zeros(ns)
    d[sel] = np.radians(deflexao)
    r = vlm.resolver(alpha, V=V, rho=rho, delta_flap={superficie: d},
                     x_charneira=x_charneira)[0]
    r0 = vlm.resolver(alpha, V=V, rho=rho)[0]

    i0, n = info["inicio"], info["n"]
    g = r.gamma[i0:i0 + n].reshape(nc, ns)
    g0 = r0.gamma[i0:i0 + n].reshape(nc, ns)
    gnet = np.vstack([g[:1], np.diff(g, axis=0)]) - np.vstack([g0[:1], np.diff(g0, axis=0)])

    x_seg = info["x_segmento"]
    c_f = info["c"]
    x_le = info["x_quarto"] - 0.25 * c_f
    x_h = x_le + x_charneira * c_f
    atras = x_seg >= x_h[None, :]

    dy = np.abs(info["d_env"])
    braco = x_seg - x_h[None, :]
    M = float(np.sum(np.where(atras, gnet * braco, 0.0) * dy[None, :]) * rho * V)

    corda_f = float(np.mean(c_f[sel] * (1.0 - x_charneira)))
    area_f = float(np.sum((c_f * (1.0 - x_charneira) * dy)[sel]))
    q = 0.5 * rho * V * V
    Ch = M / (q * area_f * corda_f) if area_f > 0 and corda_f > 0 else float("nan")

    return MomentoCharneira(superficie=superficie, deflexao=deflexao, velocidade=V,
                            Ch=Ch, momento_Nm=abs(M), area_m2=area_f, corda_m=corda_f)
