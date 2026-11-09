from __future__ import annotations

import numpy as np

from .aeronave_vlm import superficies
from .estabilidade import derivadas
from .trim import trimar
from .vlm import VLM, Superficie

def comando_automatico(S: list[Superficie], x_cg: float) -> str | None:
    cand = [s for s in S if abs(s.diedro) <= 60.0 and not s.de_referencia]
    if not cand:
        return None
    braco = lambda s: abs(s.x_le + 0.25 * s.planform.corda_raiz - x_cg) * s.planform.area
    return max(cand, key=braco).nome

def monta(esq: dict, x_cg: float, z_cg: float = 0.0, n_chord: int = 4) -> VLM:
    return VLM(superficies(esq, n_chord=n_chord), x_ref=float(x_cg), z_ref=float(z_cg))

def _lista(a) -> list:
    return [float(v) for v in a]

def longitudinal(esq: dict, x_cg: float, V: float = 15.0, rho: float = 1.1, CL_alvo: float | None = None,
                 comando: str | None = None, alphas=None, z_cg: float = 0.0) -> dict:
    vlm = monta(esq, x_cg, z_cg)
    S = vlm.superficies
    avisos: list[str] = []
    d = derivadas(vlm, 3.0, V=V, rho=rho, laterais=False)
    alphas = np.linspace(-4.0, 12.0, 17) if alphas is None else np.asarray(alphas, float)
    r = vlm.resolver(alphas, V=V, rho=rho)
    comando = comando if comando is not None else comando_automatico(S, x_cg)
    sai = {
        "S_ref": float(vlm.S_ref), "c_ref": float(vlm.c_ref), "b_ref": float(vlm.b_ref), "x_cg": float(x_cg),
        "CL_alpha": float(d.CL_alpha), "Cm_alpha": float(d.Cm_alpha),
        "margem_estatica": float(d.margem_estatica), "ponto_neutro": float(d.ponto_neutro),
        "estavel": bool(d.estavel_longitudinal), "comando": comando,
        "superficies": [{"nome": s.nome, "referencia": bool(s.de_referencia), "vertical": abs(s.diedro) > 60.0} for s in S],
        "varredura": {"alpha": _lista(alphas), "CL": [float(x.CL) for x in r], "CDi": [float(x.CDi) for x in r],
                      "Cm": [float(x.Cm) for x in r]},
        "trim": None, "avisos": avisos,
    }
    if not d.estavel_longitudinal:
        avisos.append("Instavel em arfagem: Cm_alpha >= 0 (o CG esta atras do ponto neutro).")
    elif d.margem_estatica < 0.05:
        avisos.append("Margem estatica abaixo de 5% da corda media: pouca estabilidade.")
    if CL_alvo is not None:
        if comando is None:
            cm = np.array([x.Cm for x in r])
            if cm[0] * cm[-1] > 0:
                avisos.append("Sem comando de arfagem e sem alpha de Cm = 0 na faixa: nao ha equilibrio.")
            else:
                o = np.argsort(cm)
                al = float(np.interp(0.0, cm[o], alphas[o]))
                for _ in range(4):
                    h = 0.05
                    f0, f1 = vlm.resolver([al, al + h], V=V, rho=rho)
                    if abs(f0.Cm) < 1e-12 or f1.Cm == f0.Cm:
                        break
                    al -= f0.Cm * h / (f1.Cm - f0.Cm)
                x = vlm.resolver(al, V=V, rho=rho)[0]
                sai["trim"] = {"alpha": al, "deflexao": 0.0, "CL": float(x.CL), "CDi": float(x.CDi), "Cm": float(x.Cm),
                               "residuo": abs(float(x.Cm)), "atinge_CL_alvo": bool(x.CL >= CL_alvo)}
                if x.CL < CL_alvo:
                    avisos.append(f"Equilibra em CL = {x.CL:.2f}, abaixo dos {CL_alvo:.2f} pedidos.")
        else:
            try:
                t = trimar(vlm, CL_alvo, comando, x_cg=x_cg, V=V, rho=rho, tipo="inteira")
                sai["trim"] = {"alpha": t.alpha, "deflexao": t.deflexao, "CL": float(t.CL), "CDi": float(t.CDi),
                               "Cm": float(t.Cm), "residuo": t.residuo, "atinge_CL_alvo": bool(t.residuo < 1e-6),
                               "contribuicao": {k: float(v) for k, v in t.contribuicao.items()}}
            except ValueError as e:
                avisos.append(str(e).split("\n")[0])
    return sai
