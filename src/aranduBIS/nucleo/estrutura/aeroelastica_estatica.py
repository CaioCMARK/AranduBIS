from __future__ import annotations

import copy

import numpy as np

from ..aero.equilibrio import comando_automatico, monta
from ..modelador import aeronave_geometria as AG
from .asa import _elemento
from .cargas import _equilibra
from .torcao import analisa

G = 9.80665
LIMITE_GRAUS = 45.0

def esquema_deformado(esq: dict, nome: str, y_theta, theta_graus, n_extra: int = 14) -> dict:
    e = copy.deepcopy(esq)
    el = _elemento(e, nome)
    sec = AG._secoes(el)
    originais = el.get("secoes") or []
    y_theta, theta_graus = np.asarray(y_theta, float), np.asarray(theta_graus, float)
    y_max = max(abs(s[1]) for s in sec)
    ys = {round(s[1], 9) for s in sec}
    for v in np.linspace(0.0, y_max, n_extra + 1):
        for sgn in (1.0, -1.0):
            y = sgn * float(v)
            if min(s[1] for s in sec) - 1e-9 <= y <= y_max + 1e-9:
                ys.add(round(y, 9))
    novas = []
    ys = sorted(ys)
    for i, y in enumerate(ys):
        xle, yy, zle, c, ainc = AG._secao_em(sec, y)
        d = {"y": float(y), "xle": float(xle), "zle": float(zle), "corda": float(c),
             "ainc": float(ainc + np.interp(abs(y), y_theta, theta_graus))}
        for ref, k in ((originais[0] if originais else {}, 0), (originais[-1] if originais else {}, len(ys) - 1)):
            if i == k:
                for chave in ("arquivo", "perfil"):
                    if chave in ref:
                        d[chave] = ref[chave]
        novas.append(d)
    el["secoes"] = novas
    el.pop("secoes_lineares", None)
    return e

def _torque_e_torcao(vlm, resultado, nome, an, V, rho):
    info = vlm._fatias[nome]
    y, c, dy = np.asarray(info["y"], float), np.asarray(info["c"], float), np.abs(np.asarray(info["dy"], float))
    lado = y > 0
    idx = np.flatnonzero(lado)
    idx = idx[np.argsort(y[idx])]
    ya, ca, dya = y[idx], c[idx], dy[idx]
    q = 0.5 * rho * V * V
    L = np.asarray(resultado.cl_faixa[nome], float)[idx] * q * ca
    m_c4 = np.asarray(resultado.cm_faixa[nome], float)[idx] * q * ca ** 2
    ea_c = np.interp(ya, an["y"], an["ea_c"])
    Tl = L * (ea_c - 0.25) * ca + m_c4
    T_ate_ponta = np.cumsum((Tl * dya)[::-1])[::-1]
    ys = np.array(an["y"])
    GJ = np.array(an["GJ"])
    T_est = np.interp(ys, ya, T_ate_ponta, left=T_ate_ponta[0], right=0.0)
    f = T_est / GJ
    theta = np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(ys))])
    fletor = np.array([np.sum(L[i:] * (ya[i:] - (ya[i] - dya[i] / 2))) for i in range(len(ya))])
    return {"y": ys, "theta": theta, "T_est": T_est, "y_faixa": ya, "L": L, "fletor_raiz": float(fletor[0]), "sustentacao": float(np.sum(L * dya))}

def estatica(esq: dict, V: float, n: float, massa_kg: float, x_cg: float, z_cg: float = 0.0, rho: float = 1.1, mats: dict | None = None,
             calib_GJ: float = 1.0, ea_desloc_c: float = 0.0, x_ca_c: float = 0.25, cl_alpha_2d: float = 2 * np.pi,
             n_iter: int = 12, relax: float = 0.7, tol_graus: float = 0.01, comando: str | None = None, n_span: int | None = None, n_chord: int = 4,
             calib_EI: float = 1.0) -> dict:
    vlm0 = monta(esq, x_cg, z_cg, n_chord=n_chord, n_span=n_span)
    q = 0.5 * rho * V * V
    CL_alvo = n * massa_kg * G / (q * vlm0.S_ref)
    comando = comando if comando is not None else comando_automatico(vlm0.superficies, x_cg)
    r0, alfa0, defl0, ok0 = _equilibra(vlm0, CL_alvo, V, rho, comando)
    asas = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa" and e.get("estrutura")
            and any(s.nome == e["nome"] and abs(s.diedro) < 60.0 for s in vlm0.superficies)]
    if not asas:
        raise ValueError("Nenhuma asa sustentadora com estrutura declarada no modelo.")
    ans = {a: analisa(esq, a, mats=mats, rho=rho, Vd=V, x_ca_c=x_ca_c, cl_alpha_2d=cl_alpha_2d, calib_GJ=calib_GJ, ea_desloc_c=ea_desloc_c,
                      calib_EI=calib_EI) for a in asas}
    rig = {a: _torque_e_torcao(vlm0, r0, a, ans[a], V, rho) for a in asas}
    theta = {a: np.zeros(len(ans[a]["y"])) for a in asas}
    hist, convergiu, motivo = [], False, None
    r, alfa, defl, ok = r0, alfa0, defl0, ok0
    vlm = vlm0
    for it in range(n_iter):
        flex = {a: _torque_e_torcao(vlm, r, a, ans[a], V, rho) for a in asas}
        novo = {a: relax * np.degrees(flex[a]["theta"]) + (1 - relax) * theta[a] for a in asas}
        dif = max(float(np.max(np.abs(novo[a] - theta[a]))) for a in asas)
        theta = novo
        hist.append({"iteracao": it + 1, "mudanca_graus": dif, "torcao_ponta_graus": {a: float(theta[a][-1]) for a in asas}})
        if max(abs(float(theta[a][-1])) for a in asas) > LIMITE_GRAUS:
            motivo = f"a torcao passou de {LIMITE_GRAUS:.0f} graus: divergencia estatica neste ponto (V, n)."
            break
        e = esq
        for a in asas:
            e = esquema_deformado(e, a, ans[a]["y"], theta[a])
        vlm = monta(e, x_cg, z_cg, n_chord=n_chord, n_span=n_span)
        r, alfa, defl, ok = _equilibra(vlm, CL_alvo, V, rho, comando)
        if dif < tol_graus:
            convergiu = True
            break
    if not convergiu and motivo is None:
        motivo = f"nao convergiu em {n_iter} iteracoes (ultima mudanca {hist[-1]['mudanca_graus']:.3f} graus)."
    fin = {a: _torque_e_torcao(vlm, r, a, ans[a], V, rho) for a in asas} if motivo is None or convergiu else None
    sai = {"V": V, "n": n, "massa_kg": massa_kg, "CL_alvo": float(CL_alvo), "comando": comando, "convergiu": bool(convergiu), "motivo": motivo,
           "iteracoes": hist, "rigida": {"alpha": float(alfa0), "deflexao": float(defl0), "CL": float(r0.CL), "Cm": float(r0.Cm)},
           "flexivel": None if fin is None else {"alpha": float(alfa), "deflexao": float(defl), "CL": float(r.CL), "Cm": float(r.Cm)}, "asas": []}
    for a in asas:
        d = {"nome": a, "y": ans[a]["y"], "theta_graus": theta[a].tolist(), "torcao_ponta_graus": float(theta[a][-1]),
             "GJ": ans[a]["GJ"], "ea_c": ans[a]["ea_c"],
             "y_faixa": rig[a]["y_faixa"].tolist(), "L_rigida": rig[a]["L"].tolist(), "fletor_raiz_rigida": rig[a]["fletor_raiz"],
             "sustentacao_rigida": rig[a]["sustentacao"]}
        if fin is not None:
            d.update(L_flexivel=fin[a]["L"].tolist(), fletor_raiz_flexivel=fin[a]["fletor_raiz"], sustentacao_flexivel=fin[a]["sustentacao"],
                     razao_fletor=fin[a]["fletor_raiz"] / rig[a]["fletor_raiz"] if rig[a]["fletor_raiz"] else None)
        sai["asas"].append(d)
    if fin is not None:
        sai["variacao_alpha_graus"] = float(alfa - alfa0)
        sai["variacao_deflexao_graus"] = float(defl - defl0)
    return sai
