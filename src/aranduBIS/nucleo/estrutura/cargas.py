from __future__ import annotations

import numpy as np

from ..aero.aeronave_vlm import avisos_de_ignoradas
from ..aero.equilibrio import comando_automatico, monta
from ..aero.trim import trimar

G = 9.80665

def envelope_vn(massa_kg: float, S: float, CL_max: float, CL_alpha: float, c_med: float, rho: float, Vc: float, Vd: float,
                n_max: float = 1.8, n_min: float = 0.0, U_c: float = 4.0, U_d: float = 2.0, cl_min_rel: float = 0.5) -> dict:
    W = massa_kg * G
    cs = W / S
    Vs = float(np.sqrt(2 * cs / (rho * CL_max)))
    Va = Vs * float(np.sqrt(n_max))
    avisos = []
    mu = 2 * cs / (rho * c_med * CL_alpha * G)
    Kg = 0.88 * mu / (5.3 + mu)
    dn = lambda U, V: rho * Kg * U * V * CL_alpha / (2 * cs)
    dn_c, dn_d = dn(U_c, Vc), dn(U_d, Vd)
    V = np.linspace(0.0, Vd, 120)
    pos = np.minimum((V / Vs) ** 2, n_max)
    if n_min < 0:
        Vsn = float(np.sqrt(2 * cs / (rho * cl_min_rel * CL_max)))
        Vg = Vsn * float(np.sqrt(abs(n_min)))
        neg = np.maximum(-(V / Vsn) ** 2, n_min)
    else:
        Vsn = Vg = None
        neg = np.zeros_like(V)
    vg = np.array([0.0, Vc, Vd])
    rajada_pos = [1.0, 1.0 + dn_c, 1.0 + dn_d]
    rajada_neg = [1.0, 1.0 - dn_c, 1.0 - dn_d]
    pontos = [{"nome": "manobra_Va", "V": Va, "n": n_max, "origem": "manobra"},
              {"nome": "manobra_Vd", "V": Vd, "n": n_max, "origem": "manobra"},
              {"nome": "rajada_Vc", "V": Vc, "n": rajada_pos[1], "origem": "rajada"},
              {"nome": "rajada_Vd", "V": Vd, "n": rajada_pos[2], "origem": "rajada"}]
    if n_min < 0:
        pontos += [{"nome": "negativo_Vg", "V": Vg, "n": n_min, "origem": "manobra"},
                   {"nome": "rajada_neg_Vc", "V": Vc, "n": rajada_neg[1], "origem": "rajada"}]
    n_proj = max(n_max, rajada_pos[1], rajada_pos[2])
    if rajada_pos[1] > n_max + 1e-9 or rajada_pos[2] > n_max + 1e-9:
        avisos.append(f"A rajada leva o fator de carga a {max(rajada_pos[1], rajada_pos[2]):.2f}, acima do limite de manobra {n_max:.2f}: "
                      "a rajada dimensiona (use o maior, ou revise a rajada de projeto).")
    if Vc < Va:
        avisos.append(f"Vc ({Vc:.1f} m/s) abaixo de Va ({Va:.1f} m/s): confira as velocidades.")
    return {"massa_kg": massa_kg, "S": S, "CL_max": CL_max, "CL_alpha": CL_alpha, "rho": rho, "Vs": Vs, "Va": Va, "Vc": Vc, "Vd": Vd,
            "n_max": n_max, "n_min": n_min, "n_projeto": n_proj, "mu": mu, "Kg": Kg, "dn_Vc": dn_c, "dn_Vd": dn_d,
            "Vs_negativo": Vsn, "Vg": Vg,
            "curvas": {"V": V.tolist(), "manobra_pos": pos.tolist(), "manobra_neg": neg.tolist(), "rajada_V": vg.tolist(),
                       "rajada_pos": rajada_pos, "rajada_neg": rajada_neg},
            "pontos": pontos, "avisos": avisos}

def _equilibra(vlm, CL_alvo: float, V: float, rho: float, comando: str | None):
    if comando is not None:
        t = trimar(vlm, CL_alvo, comando, V=V, rho=rho, tipo="inteira")
        return t.resultado, t.alpha, t.deflexao, bool(t.residuo < 1e-6)
    a0, a1 = vlm.resolver([0.0, 6.0], V=V, rho=rho)
    al = 6.0 * (CL_alvo - a0.CL) / (a1.CL - a0.CL)
    return vlm.resolver(al, V=V, rho=rho)[0], float(al), 0.0, True

def massa_da_superficie(esq: dict, nome: str) -> float:
    from ..modelador import aeronave_geometria as AG
    return float(sum(q["massa"] for q in AG.massa_e_cg(AG.constroi(esq))["itens"] if str(q["nome"]).startswith(nome + ".")))

def distribuicao(esq: dict, x_cg: float, z_cg: float, V: float, n: float, massa_kg: float, rho: float = 1.1,
                 comando: str | None = None, massas_sup: dict | None = None, vlm=None) -> dict:
    vlm = vlm or monta(esq, x_cg, z_cg)
    q = 0.5 * rho * V * V
    CL_alvo = n * massa_kg * G / (q * vlm.S_ref)
    comando = comando if comando is not None else comando_automatico(vlm.superficies, x_cg)
    r, alfa, defl, ok = _equilibra(vlm, CL_alvo, V, rho, comando)
    avisos = avisos_de_ignoradas(esq)
    if not ok:
        avisos.append("O equilibrio (trim) nao fechou neste ponto: cargas com incerteza maior.")
    sup, total = [], 0.0
    for s in vlm.superficies:
        if abs(s.diedro) > 60.0:
            continue
        info = vlm._fatias[s.nome]
        y, c, dy = np.asarray(info["y"], float), np.asarray(info["c"], float), np.abs(np.asarray(info["dy"], float))
        area = c * np.asarray(info["d_env"], float)
        L = np.asarray(r.cl_faixa[s.nome], float) * q * area
        m = massas_sup.get(s.nome) if massas_sup else None
        if m is None:
            m = massa_da_superficie(esq, s.nome)
        peso = n * m * G * area / area.sum()
        liq = L - peso
        total += float(L.sum())
        lados = {}
        for nome_lado, sel in (("dir", y > 0), ("esq", y < 0)):
            idx = np.flatnonzero(sel)
            if idx.size == 0:
                continue
            idx = idx[np.argsort(np.abs(y[idx]))]
            ya, w = np.abs(y[idx]), dy[idx]
            borda = ya - w / 2
            cort = np.cumsum(liq[idx][::-1])[::-1]
            fl = np.array([np.sum(liq[idx][i:] * (ya[i:] - borda[i])) for i in range(len(idx))])
            lados[nome_lado] = {"y": ya.tolist(), "sustentacao_por_m": (L[idx] / w).tolist(), "liquida_por_m": (liq[idx] / w).tolist(),
                                "cortante": cort.tolist(), "fletor": fl.tolist(), "borda_raiz": float(borda[0]),
                                "cortante_raiz": float(cort[0]), "fletor_raiz": float(fl[0])}
        ref = lados.get("dir") or lados.get("esq")
        sup.append({"nome": s.nome, "referencia": bool(s.de_referencia), "massa_kg": m, "sustentacao_N": float(L.sum()),
                    "lados": lados, "y": ref["y"], "sustentacao_por_m": ref["sustentacao_por_m"], "liquida_por_m": ref["liquida_por_m"],
                    "cortante": ref["cortante"], "fletor": ref["fletor"],
                    "cortante_raiz": max(l["cortante_raiz"] for l in lados.values()),
                    "fletor_raiz": max(l["fletor_raiz"] for l in lados.values())})
    return {"V": V, "n": n, "CL": float(CL_alvo), "alpha": alfa, "deflexao": defl, "comando": comando, "convergiu": ok,
            "peso_N": float(n * massa_kg * G), "sustentacao_total_N": total, "superficies": sup, "avisos": avisos}

def casos_de_carga(esq: dict, x_cg: float, z_cg: float, massa_kg: float, rho: float, CL_max: float, CL_alpha: float,
                   c_med: float, S: float, Vc: float, Vd: float, n_max: float = 1.8, n_min: float = 0.0, U_c: float = 4.0,
                   U_d: float = 2.0, fator_seguranca: float = 1.2, cl_min_rel: float = 0.5, comando: str | None = None, n_span: int | None = None, n_chord: int = 4) -> dict:
    vn = envelope_vn(massa_kg, S, CL_max, CL_alpha, c_med, rho, Vc, Vd, n_max, n_min, U_c, U_d, cl_min_rel)
    massas = {}
    vlm = monta(esq, x_cg, z_cg, n_chord=n_chord, n_span=n_span)
    casos, avisos = [], list(vn["avisos"])
    for p in vn["pontos"]:
        d = distribuicao(esq, x_cg, z_cg, p["V"], p["n"], massa_kg, rho, comando, massas, vlm)
        for sp in d["superficies"]:
            massas[sp["nome"]] = sp["massa_kg"]
        d.update(nome=p["nome"], origem=p["origem"])
        casos.append(d)
        avisos += [a for a in d["avisos"] if a not in avisos]
    criticos = {}
    for nome in {s["nome"] for c in casos for s in c["superficies"]}:
        pior = max(((abs(s["fletor_raiz"]), c["nome"], s) for c in casos for s in c["superficies"] if s["nome"] == nome),
                   key=lambda t: t[0])
        criticos[nome] = {"caso": pior[1], "fletor_raiz": pior[2]["fletor_raiz"], "cortante_raiz": pior[2]["cortante_raiz"],
                          "fletor_ultimo": fator_seguranca * pior[2]["fletor_raiz"], "cortante_ultimo": fator_seguranca * pior[2]["cortante_raiz"]}
    return {"vn": vn, "casos": casos, "criticos": criticos, "fator_seguranca": fator_seguranca, "x_cg": x_cg, "z_cg": z_cg, "avisos": avisos}
