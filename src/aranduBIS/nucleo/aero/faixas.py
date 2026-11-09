from __future__ import annotations
from .polares import _MU_AR
from .polares import RHO_AR

import warnings
from dataclasses import dataclass, field

import numpy as np

from .polares import Polar, estender_viterna, reynolds
from .vlm import VLM

CL_ALPHA_2D = 2.0 * np.pi

LIMITE_ALPHA_EFETIVO = 30.0

QUEDA_DE_ESTOL = 0.05

def estacoes_sem_estol(pol: Polar, queda: float = QUEDA_DE_ESTOL) -> list[str]:
    ruins = []
    for i in range(len(pol.re)):
        m = pol.alpha >= 0.0
        cl = pol.cl[i][m]
        pico, achou = -np.inf, False
        for c in cl:
            pico = max(pico, c)
            if pico > 0 and c < pico * (1.0 - queda):
                achou = True
                break
        if not achou:
            ruins.append(f"Re={pol.re[i] / 1000:.0f}k")
    return ruins

def estender_polares(vlm: VLM, polares: dict[str, Polar],
                     alpha_max: float = 90.0,
                     passo: float = 2.0) -> dict[str, Polar]:
    ar = {s.nome: s.planform.alongamento for s in vlm.superficies}
    saida: dict[str, Polar] = {}
    for nome, pol in polares.items():
        if pol is None or "viterna" in pol.meta:
            saida[nome] = pol
            continue
        sem_estol = estacoes_sem_estol(pol)
        if sem_estol:
            warnings.warn(
                f"polar '{pol.nome}' NAO ALCANCA O ESTOL em "
                f"{len(sem_estol)}/{len(pol.re)} estacoes "
                f"({', '.join(sem_estol)}), com a tabela indo ate "
                f"{pol.alpha[-1]:.1f} graus: nessas Viterna nao tem onde "
                f"ancorar, entao a superficie '{nome}' fica com extrapolacao "
                f"linear. Acima de {pol.alpha[-1]:.1f} graus nao existe dado — "
                f"o conserto e rodar o XFOIL mais alto NESSAS estacoes, nao "
                f"escolher entre duas ficcoes.",
                RuntimeWarning, stacklevel=2)
            saida[nome] = pol
            continue
        saida[nome] = estender_viterna(pol, alpha_max=alpha_max,
                                       passo=passo, AR=ar.get(nome, 6.0))
    return saida

@dataclass
class ResultadoFaixas:

    alpha: float
    CL: float
    CDi: float
    CDp: float
    convergiu: bool
    iteracoes: int
    residuo: float
    motivo: str = ""

    y: dict[str, np.ndarray] = field(default_factory=dict)
    cl: dict[str, np.ndarray] = field(default_factory=dict)
    cd: dict[str, np.ndarray] = field(default_factory=dict)
    re: dict[str, np.ndarray] = field(default_factory=dict)
    alpha_efetivo: dict[str, np.ndarray] = field(default_factory=dict)
    estolada: dict[str, np.ndarray] = field(default_factory=dict)
    delta: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def CD(self) -> float:
        return self.CDi + self.CDp

    @property
    def eficiencia(self) -> float:
        return self.CL / self.CD if self.CD > 0 else float("nan")

    def fracao_estolada(self, superficie: str = "asa") -> float:
        est = self.estolada.get(superficie)
        return float(np.mean(est)) if est is not None and len(est) else 0.0

    def inicio_do_estol(self, superficie: str = "asa") -> float | None:
        est, y = self.estolada.get(superficie), self.y.get(superficie)
        if est is None or not np.any(est):
            return None
        return float(np.min(np.abs(np.asarray(y)[est])))

    def __repr__(self) -> str:
        marca = "" if self.convergiu else f" NAO-CONVERGIU ({self.motivo})"
        return (f"<Faixas alpha={self.alpha:.2f}° CL={self.CL:.4f} "
                f"CD={self.CD:.5f} (i={self.CDi:.5f} p={self.CDp:.5f}) "
                f"L/D={self.eficiencia:.2f}{marca}>")

class TeoriaDeFaixas:

    def _alpha_zero(self, nome: str) -> float:
        for s in self.vlm.superficies:
            if s.nome == nome and s.perfil is not None:
                return s.perfil.alpha_sustentacao_nula()
        return 0.0

    def __init__(self, vlm: VLM, polares: dict[str, Polar],
                 rho: float = RHO_AR, mu: float = _MU_AR,
                 estender: bool = True):
        self.vlm = vlm
        self.polares = estender_polares(vlm, polares) if estender else polares
        self.rho, self.mu = rho, mu

    def _matriz_resposta(self, alpha: float, V: float, nome: str) -> tuple:
        ns = self.vlm._fatias[nome]["ns"]
        zero = np.zeros(ns)
        cl0 = self.vlm.resolver(alpha, V=V, rho=self.rho,
                                delta_alpha={nome: zero})[0].cl_faixa[nome]
        B = np.empty((ns, ns))
        for j in range(ns):
            e = np.zeros(ns); e[j] = 1.0
            B[:, j] = self.vlm.resolver(alpha, V=V, rho=self.rho,
                                        delta_alpha={nome: e})[0].cl_faixa[nome] - cl0
        return cl0, B

    def resolver(self, alpha: float, V: float, max_iter: int = 30,
                 tol: float = 1e-5, amortecimento: float = 1.0,
                 paciencia: int = 5,
                 delta0: dict[str, np.ndarray] | None = None,
                 continuacao: float = 2.0) -> ResultadoFaixas:
        fatias = self.vlm._fatias
        nomes = [n for n in fatias if self.polares.get(n) is not None]
        delta = {n: np.zeros(fatias[n]["ns"]) for n in fatias}
        if delta0 is not None:
            for n, v0 in delta0.items():
                if n in delta and len(v0) == len(delta[n]):
                    delta[n] = np.asarray(v0, dtype=float).copy()
        resposta = {n: self._matriz_resposta(alpha, V, n) for n in nomes}
        re_loc = {n: reynolds(V, fatias[n]["c"], rho=self.rho, mu=self.mu) for n in fatias}

        convergiu, res, it = False, np.inf, 0
        motivo = f"orçamento de {max_iter} iterações esgotado"
        melhor_res, melhor_delta, parado = np.inf, dict(delta), 0
        sem_saida: dict[str, np.ndarray] = {}
        for it in range(1, max_iter + 1):
            res = 0.0
            travou = False
            entrada = {n: v.copy() for n, v in delta.items()}
            for nome in nomes:
                pol = self.polares[nome]
                cl0, B = resposta[nome]
                d = delta[nome]
                cl_vlm = cl0 + B @ d
                a_ef = cl_vlm / CL_ALPHA_2D - d
                a_deg = np.degrees(a_ef)
                cl_2d, _, _ = pol(a_deg, re_loc[nome])
                F = cl_2d - cl_vlm
                res = max(res, float(np.max(np.abs(F))))

                h = 0.25
                clp, _, _ = pol(a_deg + h, re_loc[nome])
                clm, _, _ = pol(a_deg - h, re_loc[nome])
                slope = np.degrees((clp - clm) / (2 * h))

                J = slope[:, None] * (B / CL_ALPHA_2D - np.eye(len(d))) - B
                try:
                    passo = np.linalg.solve(J, -F)
                except np.linalg.LinAlgError:
                    passo = -F / CL_ALPHA_2D

                norma0 = float(np.sqrt(np.mean(F ** 2)))
                fator, aceitou = amortecimento, False
                for _ in range(12):
                    tentativa = d + fator * passo
                    cl_t = cl0 + B @ tentativa
                    a_t = np.degrees(cl_t / CL_ALPHA_2D - tentativa)
                    cl2_t, _, _ = pol(a_t, re_loc[nome])
                    if np.max(np.abs(a_t - alpha)) > LIMITE_ALPHA_EFETIVO:
                        fator *= 0.5
                        continue
                    if float(np.sqrt(np.mean((cl2_t - cl_t) ** 2))) < norma0:
                        aceitou = True
                        break
                    fator *= 0.5
                if aceitou:
                    delta[nome] = d + fator * passo
                else:
                    travou = True
                    delta[nome] = d - 0.5 * F / CL_ALPHA_2D
                    sem_saida[nome] = (F < -tol) & (slope < 0.0)

            if res < melhor_res - tol:
                melhor_res, melhor_delta, parado = res, entrada, 0
            else:
                parado += 1
            if res < tol:
                convergiu, motivo = True, "resíduo abaixo da tolerância"
                break
            if travou and parado >= paciencia:
                delta, res = melhor_delta, melhor_res
                culpadas = sum(int(np.sum(v)) for v in sem_saida.values())
                motivo = (f"Newton empacou com {culpadas} faixa(s) no ramo "
                          f"pós-estol pedindo mais cl do que a seção entrega")
                break

        if not convergiu and amortecimento > 0.5 and max_iter > 1:
            r2 = self.resolver(alpha, V, max_iter=max_iter, tol=tol,
                               amortecimento=0.5, paciencia=paciencia,
                               delta0=delta0, continuacao=0.0)
            if r2.convergiu:
                r2.iteracoes += it
                r2.motivo += f" [resgatado com meio passo apos {it} iteracoes]"
                return r2

            if continuacao > 0.0 and alpha > continuacao:
                anterior = self.resolver(alpha - continuacao, V,
                                         max_iter=max_iter, tol=tol,
                                         amortecimento=amortecimento,
                                         paciencia=paciencia, delta0=delta0,
                                         continuacao=continuacao)
                r3 = self.resolver(alpha, V, max_iter=max_iter, tol=tol,
                                   amortecimento=amortecimento,
                                   paciencia=paciencia,
                                   delta0=anterior.delta, continuacao=0.0)
                if r3.convergiu:
                    r3.iteracoes += it + anterior.iteracoes
                    r3.motivo += (f" [resgatado por continuacao desde "
                                  f"{alpha - continuacao:.1f} graus]")
                    return r3
                if r3.residuo < min(res, r2.residuo):
                    r3.motivo = motivo + " [nem a continuacao fechou]"
                    return r3
            if r2.residuo < res:
                r2.iteracoes += it
                r2.motivo = motivo + " [nem o meio passo fechou]"
                return r2

        r = self.vlm.resolver(alpha, V=V, rho=self.rho, delta_alpha=delta)[0]
        y, cl, cd, re_d, aef, est = {}, {}, {}, {}, {}, {}
        CDp = 0.0
        for nome, info in fatias.items():
            cl_i = r.cl_faixa[nome]
            a_ef = np.degrees(cl_i / CL_ALPHA_2D + self._alpha_zero(nome)
                              - delta.get(nome, 0.0))
            pol = self.polares.get(nome)
            if pol is not None:
                _, cd_i, _ = pol(a_ef, re_loc[nome])
                a_estol = np.array([pol.cl_max(float(rr))[1] for rr in re_loc[nome]])
                estolada = a_ef > a_estol
            else:
                cd_i = np.zeros_like(cl_i)
                estolada = np.zeros_like(cl_i, dtype=bool)
            CDp += float(np.sum(cd_i * info["c"] * np.abs(info["dy"]))) / self.vlm.S_ref
            y[nome], cl[nome], cd[nome] = info["y"], cl_i, cd_i
            re_d[nome], aef[nome], est[nome] = re_loc[nome], a_ef, estolada

        return ResultadoFaixas(
            alpha=alpha, CL=r.CL, CDi=r.CDi, CDp=CDp,
            convergiu=convergiu, iteracoes=it, residuo=float(res),
            motivo=motivo,
            y=y, cl=cl, cd=cd, re=re_d, alpha_efetivo=aef, estolada=est,
            delta=delta,
        )

    def curva_cl(self, alphas, V: float, **kw) -> list[ResultadoFaixas]:
        return [self.resolver(float(a), V, **kw) for a in np.atleast_1d(alphas)]

    def cl_max(self, V: float, a_min: float = 0.0, a_max: float = 20.0,
               passo: float = 0.5, **kw) -> tuple[float, float, ResultadoFaixas]:
        melhor, a_melhor, quedas = None, a_min, 0
        for a in np.arange(a_min, a_max + passo / 2, passo):
            r = self.resolver(float(a), V, **kw)
            if melhor is None or r.CL > melhor.CL:
                melhor, a_melhor, quedas = r, float(a), 0
            elif r.CL < melhor.CL * 0.98:
                quedas += 1
                if quedas >= 2:
                    break
            else:
                quedas = 0
        return melhor.CL, a_melhor, melhor
