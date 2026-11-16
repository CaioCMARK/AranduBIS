from __future__ import annotations
from .polares import _MU_AR
from .polares import RHO_AR

import warnings
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "RE_MINIMO_TURBULENTO", "ESBELTEZ_MINIMA",
    "cf_laminar", "cf_turbulento", "cf_misto",
    "fator_forma_corpo", "fator_forma_perfil",
    "Componente", "CorpoRombudo", "PolarCompleta",
    "arrasto_parasita", "arrasto_de_perfil", "polar_completa",
    "CD_ROMBUDO",
]

def cf_laminar(re):
    re = np.asarray(re, dtype=float)
    return 1.328 / np.sqrt(np.maximum(re, 1.0))

RE_MINIMO_TURBULENTO = 1.211e4

def cf_turbulento(re):
    re = np.asarray(re, dtype=float)
    return 0.455 / (np.log10(np.maximum(re, 10.0)) ** 2.58)

def cf_misto(re, x_transicao: float = 0.0):
    if not 0.0 <= x_transicao <= 1.0:
        raise ValueError(f"x_transicao deve estar entre 0 e 1, veio {x_transicao}")
    re = np.asarray(re, dtype=float)
    if x_transicao == 0.0:
        return cf_turbulento(re)
    re_tr = re * x_transicao
    return cf_turbulento(re) - x_transicao * (cf_turbulento(re_tr) - cf_laminar(re_tr))

ESBELTEZ_MINIMA = 3.0

def fator_forma_corpo(esbeltez: float) -> float:
    if esbeltez <= 0:
        raise ValueError(f"esbeltez deve ser positiva, veio {esbeltez}")
    if esbeltez < ESBELTEZ_MINIMA:
        warnings.warn(
            f"esbeltez {esbeltez:.2f} abaixo de {ESBELTEZ_MINIMA:g}: a formula de "
            f"corpo esbelto devolve FF = {1.0 + 60.0/esbeltez**3 + esbeltez/400.0:.1f}, "
            f"que e extrapolacao, nao fator de forma. Um corpo tao rombudo separa "
            f"e escala com area FRONTAL — use CorpoRombudo com CD de Hoerner.",
            RuntimeWarning, stacklevel=2,
        )
    return 1.0 + 60.0 / esbeltez ** 3 + esbeltez / 400.0

def fator_forma_perfil(espessura_rel: float, x_espessura_max: float = 0.30,
                       enflechamento: float = 0.0) -> float:
    if not 0.0 < x_espessura_max <= 1.0:
        raise ValueError(f"x_espessura_max invalido: {x_espessura_max}")
    t = float(espessura_rel)
    base = 1.0 + (0.6 / x_espessura_max) * t + 100.0 * t ** 4
    return float(base * np.cos(np.radians(enflechamento)) ** 0.28)

CD_ROMBUDO: dict[str, float] = {
    "roda_exposta": 0.55,
    "roda_carenada": 0.20,
    "cilindro": 1.10,
    "estai_redondo": 1.10,
    "estai_perfilado": 0.10,
    "placa_normal": 1.17,
    "esfera": 0.47,
}

@dataclass
class CorpoRombudo:

    nome: str
    area_frontal: float
    cd_frontal: float
    quantidade: int = 1
    interferencia: float = 1.0

    def __post_init__(self) -> None:
        if self.area_frontal < 0:
            raise ValueError(f"{self.nome}: area frontal negativa")
        if self.quantidade < 0:
            raise ValueError(f"{self.nome}: quantidade negativa")

    def cd(self, S_ref: float, V: float = 0.0, rho: float = 0.0,
           mu: float = 0.0) -> float:
        if S_ref <= 0:
            raise ValueError("S_ref deve ser positiva")
        return (self.quantidade * self.cd_frontal * self.area_frontal
                * self.interferencia / S_ref)

@dataclass
class Componente:

    nome: str
    area_molhada: float
    comprimento: float
    fator_forma: float = 1.0
    interferencia: float = 1.0
    x_transicao: float = 0.0
    quantidade: int = 1

    def __post_init__(self) -> None:
        if self.area_molhada < 0:
            raise ValueError(f"{self.nome}: area molhada negativa")
        if self.comprimento <= 0:
            raise ValueError(f"{self.nome}: comprimento deve ser positivo")

    def cd(self, S_ref: float, V: float, rho: float = RHO_AR,
           mu: float = _MU_AR) -> float:
        if S_ref <= 0:
            raise ValueError("S_ref deve ser positiva")
        if V <= 0:
            raise ValueError("V deve ser positiva")
        re = rho * V * self.comprimento / mu
        if re < RE_MINIMO_TURBULENTO:
            warnings.warn(
                f"'{self.nome}': Re = {re:.3g} esta abaixo de "
                f"{RE_MINIMO_TURBULENTO:.3g}, onde a correlacao turbulenta cruza "
                f"a laminar e passa a devolver MENOS atrito que o laminar. "
                f"Um corpo tao curto provavelmente nao e dominado por atrito — "
                f"modele como CorpoRombudo, com area frontal e CD de Hoerner.",
                RuntimeWarning, stacklevel=2,
            )
        cf = float(cf_misto(re, self.x_transicao))
        return (self.quantidade * cf * self.fator_forma * self.interferencia
                * self.area_molhada / S_ref)

def arrasto_parasita(componentes, S_ref: float, V: float, rho: float = RHO_AR,
                     mu: float = _MU_AR, detalhar: bool = False):
    if S_ref <= 0:
        raise ValueError("S_ref deve ser positiva")
    parcelas: dict[str, float] = {}
    for c in componentes:
        parcelas[c.nome] = parcelas.get(c.nome, 0.0) + float(c.cd(S_ref, V, rho, mu))
    total = float(sum(parcelas.values()))
    return (total, parcelas) if detalhar else total

def _cd_de_cl(polar, cl_alvo, re):
    cl_alvo = np.atleast_1d(np.asarray(cl_alvo, dtype=float))
    re = np.broadcast_to(np.asarray(re, dtype=float), cl_alvo.shape)
    cd = np.empty_like(cl_alvo)
    estolada = np.zeros(cl_alvo.shape, dtype=bool)

    achatado_cl = cl_alvo.ravel()
    achatado_re = re.ravel()
    cd_plano = cd.ravel()
    est_plano = estolada.ravel()

    for rev in np.unique(achatado_re):
        sel = achatado_re == rev
        a = polar.alpha
        cl_v, cd_v, _ = polar(a, np.full_like(a, rev))
        i_max = int(np.argmax(cl_v))
        cl_r, cd_r = cl_v[:i_max + 1], cd_v[:i_max + 1]
        ordem = np.argsort(cl_r)
        cl_r, cd_r = cl_r[ordem], cd_r[ordem]

        alvo = achatado_cl[sel]
        acima = alvo > cl_r[-1]
        est_plano[sel] = acima
        cd_plano[sel] = np.where(acima, cd_r[-1], np.interp(alvo, cl_r, cd_r))

    return cd, estolada

def arrasto_de_perfil(vlm, resultado, banco, V: float, rho: float = RHO_AR,
                      mu: float = _MU_AR, detalhar: bool = False):
    if V <= 0:
        raise ValueError("V deve ser positiva")
    S_ref = vlm.S_ref
    total = 0.0
    detalhes: dict[str, dict] = {}

    for s in vlm.superficies:
        nome = s.planform.nome
        if nome not in banco:
            raise KeyError(
                f"nao ha polar para a superficie '{nome}'. O arrasto de perfil "
                f"nao pode ser inventado: registre a polar no banco, com "
                f"Origem e Confianca, ou remova a superficie da conta."
            )
        polar = banco[nome]
        polar.exigir_usavel()

        info = vlm._fatias[nome]
        c = np.asarray(info["c"], dtype=float)
        dy = np.abs(np.asarray(info["dy"], dtype=float))
        cl = np.asarray(resultado.cl_faixa[nome], dtype=float)

        re = rho * V * c / mu
        r0, r1 = polar.faixa_re
        fora = (re < r0) | (re > r1)

        cd, estolada = _cd_de_cl(polar, cl, re)
        cd_sup = float(np.sum(cd * c * dy) / S_ref)
        total += cd_sup
        detalhes[nome] = dict(
            CD=cd_sup, cd_faixa=cd, re_faixa=re,
            estoladas=int(estolada.sum()), fora_da_faixa_re=int(fora.sum()),
        )

    return (total, detalhes) if detalhar else total

@dataclass
class PolarCompleta:

    alpha: float
    CL: float
    CD: float
    CD_induzido: float
    CD_perfil: float
    CD_parasita: float
    parcelas_parasitas: dict[str, float] = field(default_factory=dict)
    detalhes_perfil: dict = field(default_factory=dict)

    @property
    def eficiencia(self) -> float:
        return self.CL / self.CD if self.CD else float("nan")

    def __repr__(self) -> str:
        return (f"<PolarCompleta a={self.alpha:.2f} CL={self.CL:.3f} "
                f"CD={self.CD:.4f} (i={self.CD_induzido:.4f} "
                f"p={self.CD_perfil:.4f} 0={self.CD_parasita:.4f}) "
                f"L/D={self.eficiencia:.2f}>")

    def fracoes(self) -> dict[str, float]:
        if not self.CD:
            return {}
        return {"induzido": self.CD_induzido / self.CD,
                "perfil": self.CD_perfil / self.CD,
                "parasita": self.CD_parasita / self.CD}

def polar_completa(vlm, alphas, banco, componentes, V: float,
                   rho: float = RHO_AR, mu: float = _MU_AR):
    alphas = np.atleast_1d(np.asarray(alphas, dtype=float))
    resultados = vlm.resolver(alphas)
    cd0, parcelas = arrasto_parasita(componentes, vlm.S_ref, V, rho, mu, detalhar=True)

    saida = []
    for a, r in zip(alphas, resultados):
        cdp, det = arrasto_de_perfil(vlm, r, banco, V, rho, mu, detalhar=True)
        saida.append(PolarCompleta(
            alpha=float(a), CL=float(r.CL),
            CD=float(r.CDi) + cdp + cd0,
            CD_induzido=float(r.CDi), CD_perfil=cdp, CD_parasita=cd0,
            parcelas_parasitas=parcelas, detalhes_perfil=det,
        ))
    return saida
