from __future__ import annotations

import numpy as np

from ..modelador import aeronave_geometria as AG

GRUPOS = {"asa": "asas", "trelica": "treliças de tubos", "placa": "placas (fuselagem, boom, carga)", "roda": "rodas", "corpo": "corpos", "ponto": "massas pontuais declaradas"}

def _tipo_de(esq):
    return {e["nome"]: e.get("tipo", "asa") for e in esq.get("elementos", [])}

def _inercias(P, m, cg):
    r = P - cg
    Ixx = float(np.sum(m * (r[:, 1] ** 2 + r[:, 2] ** 2))); Iyy = float(np.sum(m * (r[:, 0] ** 2 + r[:, 2] ** 2))); Izz = float(np.sum(m * (r[:, 0] ** 2 + r[:, 1] ** 2)))
    Ixz = float(-np.sum(m * r[:, 0] * r[:, 2]))
    return {"Ixx": Ixx, "Iyy": Iyy, "Izz": Izz, "Ixz": Ixz}

def balanco(esq: dict, mtow_kg: float | None = None, nao_modelada: str = "massa_equivalente") -> dict:
    mc = AG.massa_e_cg(AG.constroi(esq))
    itens = mc["itens"]
    if not itens:
        raise ValueError("o modelo nao declara nenhuma massa")
    tipo = _tipo_de(esq)
    for q in itens:
        q["grupo"] = tipo.get(str(q["nome"]).split(".")[0], "asa")
    por = {}
    for q in itens:
        g = por.setdefault(q["grupo"], {"massa": 0.0, "mx": np.zeros(3), "itens": []})
        g["massa"] += q["massa"]; g["mx"] += q["massa"] * np.array(q["cg"], float)
        g["itens"].append({"nome": q["nome"], "massa": float(q["massa"]), "cg": [float(x) for x in q["cg"]]})
    grupos = [{"grupo": k, "rotulo": GRUPOS.get(k, k), "massa_kg": g["massa"], "cg": (g["mx"] / g["massa"]).tolist(), "itens": sorted(g["itens"], key=lambda i: -i["massa"])}
              for k, g in por.items()]
    grupos.sort(key=lambda g: -g["massa_kg"])
    total = float(mc["massa_kg"])
    nm = next((q for q in itens if q["nome"] == nao_modelada), None)
    m_nm = float(nm["massa"]) if nm else 0.0
    desenhada = total - m_nm
    P = np.array([q["cg"] for q in itens], float); m = np.array([q["massa"] for q in itens], float)
    cg = (m[:, None] * P).sum(0) / m.sum()
    mtow = float(mtow_kg) if mtow_kg else total
    saida = {"grupos": grupos, "total_kg": total, "desenhada_kg": desenhada, "nao_modelada_kg": m_nm, "nao_modelada_nome": nao_modelada if nm else None,
             "estrutural_kg": float(sum(g["massa_kg"] for g in grupos if g["grupo"] in ("asa", "trelica", "placa", "roda", "corpo"))),
             "cg": cg.tolist(), "inercias_calculadas": _inercias(P, m, cg), "inercias_declaradas": {k: v for k, v in (esq.get("inercias") or {}).items() if k != "fonte"},
             "mtow_kg": mtow}
    env = esq.get("envelope_cg") or {}
    if env.get("x_m"):
        saida["envelope"] = {"x": env["x_m"], "z": env.get("z_m"), "x_dentro": bool(env["x_m"][0] - 1e-9 <= cg[0] <= env["x_m"][1] + 1e-9),
                             "z_dentro": None if not env.get("z_m") else bool(env["z_m"][0] - 1e-9 <= cg[2] <= env["z_m"][1] + 1e-9)}
    if nm:
        nova = mtow - desenhada
        saida["nao_modelada_sugerida_kg"] = float(nova)
        P2 = P.copy(); m2 = m.copy()
        i = next(j for j, q in enumerate(itens) if q["nome"] == nao_modelada)
        m2[i] = max(nova, 0.0)
        cg2 = (m2[:, None] * P2).sum(0) / m2.sum()
        saida["cg_mtow_fixo"] = cg2.tolist()
    sens = []
    for f in (0.8, 1.0, 1.2, 1.5):
        est = np.array([q["grupo"] in ("asa", "trelica", "placa", "roda", "corpo") for q in itens])
        m3 = m.copy(); m3[est] *= f
        if nm:
            i = next(j for j, q in enumerate(itens) if q["nome"] == nao_modelada)
            m4 = m3.copy(); m4[i] = max(mtow - (m3.sum() - m3[i]), 0.0)
            cgf = (m4[:, None] * P).sum(0) / m4.sum()
        else:
            m4 = m3; cgf = (m3[:, None] * P).sum(0) / m3.sum()
        sens.append({"fator_estrutura": f, "massa_estrutural_kg": float(m3[est].sum()), "massa_total_livre_kg": float(m3.sum()),
                     "nao_modelada_mtow_fixo_kg": float(m4[i] if nm else 0.0), "cg_x_mtow_fixo": float(cgf[0]),
                     "cg_x_mtow_livre": float((m3[:, None] * P).sum(0)[0] / m3.sum())})
    saida["sensibilidade"] = sens
    aviso = []
    if nm and m_nm > 0.7 * total:
        aviso.append(f"{100 * m_nm / total:.0f} % da massa ({m_nm:.2f} kg) e o item {nao_modelada!r}, uma hipotese: o CG e as inercias dependem de onde ele esta. Declare bateria, motor, ESC, carga e demais componentes no modelo para trocar a hipotese por massa real.")
    if saida["inercias_declaradas"]:
        for k in ("Ixx", "Iyy", "Izz"):
            d, c = saida["inercias_declaradas"].get(k), saida["inercias_calculadas"][k]
            if d and abs(c / d - 1) > 0.3:
                aviso.append(f"{k} calculado ({c:.3f} kg.m2) difere de {100 * abs(c / d - 1):.0f} % do declarado ({d:.3f}): massas pontuais nao tem inercia propria e o item de massa nao modelada esta concentrado.")
    saida["avisos"] = aviso
    return saida
