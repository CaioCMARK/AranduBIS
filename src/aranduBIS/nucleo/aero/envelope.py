from __future__ import annotations

import numpy as np

from .dinamica import G, inercias
from .equilibrio import longitudinal, monta

def envelope_cg(esq: dict, V: float = 15.0, rho: float = 1.1, massa_kg: float | None = None,
                CL_alvo: float | None = None, margem_minima: float = 0.05) -> dict:
    env = esq.get("envelope_cg")
    if not env or "x_m" not in env or "z_m" not in env:
        raise ValueError('o modelo nao declara "envelope_cg" ({"x_m": [min, max], "z_m": [min, max]})')
    x0, x1 = (float(v) for v in env["x_m"])
    z0, z1 = (float(v) for v in env["z_m"])
    if x1 < x0 or z1 < z0:
        raise ValueError("envelope_cg: os limites precisam estar em ordem crescente")
    avisos = []
    if CL_alvo is None:
        try:
            m = float(massa_kg) if massa_kg else inercias(esq)["m"]
        except ValueError:
            m = None
        vlm = monta(esq, 0.5 * (x0 + x1), 0.5 * (z0 + z1))
        if m:
            CL_alvo = m * G / (0.5 * rho * V * V * vlm.S_ref)
        else:
            avisos.append("Sem massa no modelo: o equilibrio nao foi calculado (informe a massa ou o CL).")
    ref = (esq.get("referencia") or {}).get("Cref")
    pontos = [("dianteiro-baixo", x0, z0), ("traseiro-baixo", x1, z0), ("traseiro-alto", x1, z1),
              ("dianteiro-alto", x0, z1), ("centro", 0.5 * (x0 + x1), 0.5 * (z0 + z1))]
    itens = []
    for nome, x, z in pontos:
        r = longitudinal(esq, x, V=V, rho=rho, CL_alvo=CL_alvo, z_cg=z, alphas=np.array([0.0, 6.0]))
        t = r["trim"]
        itens.append({"nome": nome, "x": x, "z": z, "x_mac": (x / float(ref)) if ref else None,
                      "margem_estatica": r["margem_estatica"], "ponto_neutro": r["ponto_neutro"], "estavel": r["estavel"],
                      "alpha": t["alpha"] if t else None, "deflexao": t["deflexao"] if t else None,
                      "atinge_CL": bool(t["atinge_CL_alvo"]) if t else None, "comando": r["comando"]})
        for a in r["avisos"]:
            if a not in avisos and not a.startswith("Margem estatica abaixo"):
                avisos.append(a)
    pior = min(itens, key=lambda i: i["margem_estatica"])
    melhor = max(itens, key=lambda i: i["margem_estatica"])
    ok = all(i["estavel"] and i["margem_estatica"] >= margem_minima for i in itens)
    return {"V": V, "rho": rho, "CL": CL_alvo, "limites": {"x_m": [x0, x1], "z_m": [z0, z1]}, "fonte": env.get("fonte"),
            "c_ref": float(r["c_ref"]), "Cref_modelo": float(ref) if ref else None, "itens": itens, "pior": pior["nome"],
            "margem_min": pior["margem_estatica"], "margem_max": melhor["margem_estatica"], "margem_minima_exigida": margem_minima,
            "ok": bool(ok), "avisos": avisos}
