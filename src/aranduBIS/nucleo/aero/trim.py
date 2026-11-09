from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .vlm import VLM

@dataclass
class Trim:

    alpha: float
    deflexao: float
    CL: float
    CDi: float
    Cm: float
    contribuicao: dict[str, float] = field(default_factory=dict)
    residuo: float = 0.0
    resultado: object = None

    @property
    def carga_da_cauda(self) -> float:
        return self.contribuicao.get(self._comando, float("nan"))

    _comando: str = ""

    def __repr__(self) -> str:
        return (f"<Trim α={self.alpha:.2f}° δ={self.deflexao:+.2f}° "
                f"CL={self.CL:.4f} Cm={self.Cm:+.2e} res={self.residuo:.1e}>")

def _deflexao(vlm: VLM, comando: str, graus: float, tipo: str):
    ns = vlm._fatias[comando]["ns"]
    d = np.full(ns, np.radians(graus))
    if tipo == "flape":
        return {"delta_flap": {comando: d}}
    if tipo == "inteira":
        return {"delta_alpha": {comando: d}}
    raise ValueError("tipo deve ser 'flape' ou 'inteira'")

def _contribuicoes(vlm: VLM, r) -> dict[str, float]:
    saida = {}
    for nome, info in vlm._fatias.items():
        cl = np.asarray(r.cl_faixa.get(nome, []))
        if cl.size == 0:
            continue
        largura = info.get("d_env")
        if largura is None:
            largura = np.abs(info["dy"])
        saida[nome] = float(np.sum(cl * info["c"] * largura)) / vlm.S_ref
    return saida

def trimar(vlm: VLM, CL_alvo: float, comando: str, x_cg: float | None = None,
           V: float = 1.0, rho: float = 1.0, tipo: str = "flape",
           x_charneira: float = 0.7, **kw) -> Trim:
    if comando not in vlm._fatias:
        raise ValueError(f"superficie '{comando}' nao existe; "
                         f"ha {sorted(vlm._fatias)}")
    x0 = vlm.x_ref
    if x_cg is not None:
        vlm.x_ref = float(x_cg)
    try:
        def avaliar(al, de):
            return vlm.resolver(al, V=V, rho=rho, x_charneira=x_charneira,
                                **_deflexao(vlm, comando, de, tipo), **kw)[0]

        al, de = 0.0, 0.0
        h = 0.5
        r = avaliar(al, de)
        for _ in range(12):
            f = np.array([r.CL - CL_alvo, r.Cm])
            res = float(np.linalg.norm(f))
            if res < 1e-11:
                break
            ra, rd = avaliar(al + h, de), avaliar(al, de + h)
            J = np.array([[(ra.CL - r.CL) / h, (rd.CL - r.CL) / h],
                          [(ra.Cm - r.Cm) / h, (rd.Cm - r.Cm) / h]])
            det = np.linalg.det(J)
            if abs(det) < 1e-12:
                raise ValueError(
                    "jacobiano singular: o comando nao tem autoridade sobre o "
                    f"momento (dCm/ddelta = {J[1,1]:.2e}). Confira o braco da "
                    "cauda e se a superficie de comando e a certa.")
            passo = np.linalg.solve(J, -f)
            passo = np.clip(passo, -10.0, 10.0)
            al, de = al + passo[0], de + passo[1]
            r = avaliar(al, de)

        res = float(np.linalg.norm([r.CL - CL_alvo, r.Cm]))
        return Trim(alpha=float(al), deflexao=float(de), CL=r.CL,
                    CDi=r.CDi, Cm=r.Cm, contribuicao=_contribuicoes(vlm, r),
                    residuo=res, resultado=r, _comando=comando)
    finally:
        vlm.x_ref = x0

def penalidade_de_trim(vlm: VLM, CL_alvo: float, comando: str,
                       x_cg: float | None = None, **kw) -> float:
    t = trimar(vlm, CL_alvo, comando, x_cg=x_cg, **kw)
    asa = sum(v for k, v in t.contribuicao.items() if k != comando)
    return float(asa - CL_alvo)

def varrer_cg(vlm: VLM, CL_alvo: float, comando: str,
              x_cg: np.ndarray, **kw) -> list[Trim]:
    return [trimar(vlm, CL_alvo, comando, x_cg=float(x), **kw) for x in x_cg]
