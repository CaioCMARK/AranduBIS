from __future__ import annotations

import math

import numpy as np

from ..modelador import superficies_comando as SC
from .aeronave_vlm import avisos_de_ignoradas
from .dinamica import dinamica
from .equilibrio import monta
from .estabilidade import momento_charneira
from .limites import polares_da_aeronave
from .polares import reynolds

OPCOES = ("sobe_desce", "so_sobe")

def comandos_de_rolagem(esq: dict) -> list[tuple[str, dict]]:
    sai = []
    for el in esq.get("elementos", []):
        if el.get("tipo") != "asa":
            continue
        for c in el.get("controles") or []:
            if c.get("modo") == "anti":
                sai.append((el.get("nome"), SC.resolve(c, el.get("secoes") or [])))
    return sai

def _faixas(info: dict, c: dict) -> tuple[np.ndarray, float]:
    y = np.asarray(info["y"], float)
    y0, y1 = (float(v) for v in c["y"])
    m = (np.abs(y) >= y0) & (np.abs(y) <= y1)
    if not m.any():
        raise ValueError(f"o aileron {c.get('nome')!r} nao cobre nenhuma faixa do VLM (y = {y0}..{y1})")
    if "xc" in c:
        xc = float(c["xc"])
    elif "corda" in c:
        xc = 1.0 - float(c["corda"]) / float(np.mean(np.asarray(info["c"], float)[m]))
    else:
        xc = 0.75
    return m, min(max(xc, 0.3), 0.95)

def _deflexoes(vlm, ailerons, opcao: str, sobe: float, desce: float, lado: int = +1) -> tuple[dict, float]:
    saida, xcs = {}, []
    for nome, c in ailerons:
        info = vlm._fatias.get(nome)
        if info is None:
            continue
        m, xc = _faixas(info, c)
        xcs.append(xc)
        s = np.sign(np.asarray(info["y"], float))
        d = np.zeros(len(s))
        if opcao == "sobe_desce":
            d = np.where(m, np.where(s * lado > 0, desce, -sobe), 0.0)
        else:
            d = np.where(m & (s * lado < 0), -sobe, 0.0)
        saida[nome] = np.radians(d)
    return saida, float(np.mean(xcs)) if xcs else 0.75

def margem_de_estol(vlm, polares: dict, ailerons, alpha: float, dflap: dict, xc: float, V: float, rho: float,
                    passo: float = 1.0, ate: float = 20.0) -> dict:
    alfas = alpha + np.arange(0.0, ate + 1e-9, passo)
    rs = vlm.resolver(alfas, V=V, rho=rho, delta_flap=dflap or None, x_charneira=xc)
    melhor = None
    for nome, c in ailerons:
        info, pol = vlm._fatias[nome], polares.get(nome)
        if pol is None:
            continue
        y = np.asarray(info["y"], float)
        ext = np.abs(y) >= float(c["y"][0])
        idx = np.flatnonzero(ext)
        cmax = np.array([pol.cl_max(float(reynolds(V, float(info["c"][i]), rho)))[0] for i in idx])
        margem = np.array([cmax - np.asarray(r.cl_faixa[nome], float)[idx] for r in rs])
        pior = margem.min(axis=1)
        k = int(np.argmax(pior <= 0)) if (pior <= 0).any() else None
        if k is None:
            da = float(ate)
        elif k == 0:
            da = 0.0
        else:
            da = float(passo * (k - 1) + passo * pior[k - 1] / (pior[k - 1] - pior[k]))
        i_crit = int(np.argmin(margem[0]))
        cand = {"delta_alpha_graus": da, "ilimitado": k is None, "superficie": nome, "y_critico": float(y[idx][i_crit]),
                "cl_demanda": float(np.asarray(rs[0].cl_faixa[nome], float)[idx][i_crit]), "cl_max_perfil": float(cmax[i_crit])}
        if melhor is None or da < melhor["delta_alpha_graus"]:
            melhor = cand
    return melhor or {"delta_alpha_graus": float("nan"), "ilimitado": False, "superficie": None, "y_critico": None,
                      "cl_demanda": None, "cl_max_perfil": None}

def momentos_de_charneira(vlm, ailerons, alpha: float, V: float, rho: float, sobe: float, desce: float) -> list[dict]:
    sai = []
    for nome, c in ailerons:
        info = vlm._fatias.get(nome)
        if info is None:
            continue
        m, xc = _faixas(info, c)
        lado = m & (np.asarray(info["y"], float) > 0)
        for sentido, graus in (("para baixo", desce), ("para cima", -sobe)):
            h = momento_charneira(vlm, nome, graus, alpha, V, faixas=lado, x_charneira=xc, rho=rho)
            sai.append({"aileron": c.get("nome"), "elemento": nome, "sentido": sentido, "deflexao": abs(graus),
                        "momento_Nm": float(h.momento_Nm), "torque_kgfcm": float(h.torque_kgfcm), "Ch": float(h.Ch),
                        "area_m2": float(h.area_m2), "corda_m": float(h.corda_m)})
    return sai

def _tempo_ate(phi_graus: float, p_ss: float, tau: float) -> float | None:
    alvo = math.radians(phi_graus)
    if p_ss <= 0 or alvo <= 0:
        return None
    f = lambda t: p_ss * (t - tau * (1.0 - math.exp(-t / tau))) - alvo
    lo, hi = 0.0, 1.0
    while f(hi) < 0 and hi < 600:
        hi *= 2.0
    if f(hi) < 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return 0.5 * (lo + hi)

def autoridade_rolagem(esq: dict, x_cg: float | None = None, V: float = 15.0, rho: float = 1.1,
                       massa_kg: float | None = None, I: dict | None = None, raios: dict | None = None,
                       modo_inercia: str = "auto", sobe_max: float = 30.0, desce_max: float = 25.0,
                       pb2V_min: float = 0.05, t_inclinacao_max: float = 1.5, inclinacao: float = 30.0,
                       beta: float = 0.0, ncrit: int = 4, V_servo: float = 18.0) -> dict:
    ailerons = comandos_de_rolagem(esq)
    if not ailerons:
        raise ValueError("o modelo nao tem ailerons: declare um comando com \"modo\": \"anti\" em uma asa")
    din = dinamica(esq, x_cg=x_cg, V=V, rho=rho, massa_kg=massa_kg, I=I, raios=raios, modo_inercia=modo_inercia)
    cg, alpha = din["cg"], din["alpha"]
    vlm = monta(esq, cg[0], cg[2])
    S, b = vlm.S_ref, vlm.b_ref
    q = 0.5 * rho * V * V
    Cl_p, Ixx = din["derivadas"]["Cl_p"], din["inercias"]["Ixx"]
    tau = -2.0 * V * Ixx / (q * S * b * b * Cl_p) if Cl_p < 0 else float("inf")
    base = vlm.resolver(alpha, V=V, rho=rho, beta=beta)[0]
    avisos = list(dict.fromkeys(list(din["avisos"]) + avisos_de_ignoradas(esq)))
    if Cl_p >= 0:
        avisos.append("Clp >= 0: sem amortecimento em rolagem no modelo; a taxa de regime nao existe.")

    polares, info_pol = polares_da_aeronave(vlm, ncrit)
    for i in info_pol:
        if i["origem"] == "aproximado" and any(i["superficie"] == n for n, _ in ailerons):
            avisos.append(f"Perfil de {i['superficie']} aproximado para o estol local: {i['nota']}")
    xc0 = _deflexoes(vlm, ailerons, "sobe_desce", 0.0, 0.0)[1]
    sem = margem_de_estol(vlm, polares, ailerons, alpha, {}, xc0, V, rho)

    def um(opcao, sobe, desce, com_estol=False):
        piores, pior_estol = None, None
        for lado in (+1, -1):
            dflap, xc = _deflexoes(vlm, ailerons, opcao, sobe, desce, lado)
            r = vlm.resolver(alpha, V=V, rho=rho, beta=beta, delta_flap=dflap, x_charneira=xc)[0]
            cl, cn = float(r.Cl - base.Cl), float(r.Cn - base.Cn)
            est = margem_de_estol(vlm, polares, ailerons, alpha, dflap, xc, V, rho) if com_estol else None
            if piores is None or abs(cl) < abs(piores["Cl"]):
                piores = {"Cl": cl, "Cn": cn, "xc": xc, "lado": lado}
            if com_estol and (pior_estol is None or est["delta_alpha_graus"] < pior_estol["delta_alpha_graus"]):
                pior_estol = est
        pb2V = abs(piores["Cl"] / Cl_p) if Cl_p < 0 else float("nan")
        p_ss = pb2V * 2.0 * V / b if math.isfinite(pb2V) else float("nan")
        t_inc = _tempo_ate(inclinacao, p_ss, tau) if math.isfinite(p_ss) and math.isfinite(tau) else None
        return {"opcao": opcao, "sobe": sobe, "desce": desce if opcao == "sobe_desce" else 0.0, "Cl_comando": piores["Cl"],
                "Cn_comando": piores["Cn"], "pb2V": pb2V, "p_regime_graus_s": math.degrees(p_ss) if math.isfinite(p_ss) else None,
                "tempo_inclinacao_s": t_inc, "guinada_adversa": piores["Cn"] / piores["Cl"] if abs(piores["Cl"]) > 1e-9 else None,
                "xc": piores["xc"], "estol_local": pior_estol, "ok_pb2V": bool(math.isfinite(pb2V) and pb2V >= pb2V_min),
                "ok_tempo": bool(t_inc is not None and t_inc <= t_inclinacao_max)}

    opcoes = {"sobe_desce": um("sobe_desce", sobe_max, desce_max, True), "so_sobe": um("so_sobe", sobe_max, 0.0, True)}
    graus = list(np.linspace(2.0, max(sobe_max, desce_max), 8))
    curva = {"deflexao": [float(g) for g in graus],
             "sobe_desce": [um("sobe_desce", g, g)["pb2V"] for g in graus],
             "so_sobe": [um("so_sobe", g, 0.0)["pb2V"] for g in graus]}
    for nome, o in opcoes.items():
        if o["Cl_comando"] == 0.0 or abs(o["Cl_comando"]) < 1e-9:
            avisos.append(f"A opcao {nome} nao gera momento de rolagem: confira o trecho em y e a charneira do aileron.")
    return {"V": V, "rho": rho, "alpha": alpha, "m": din["m"], "origem_inercia": din["origem_inercia"], "Ixx": Ixx,
            "tau_rolagem_s": tau, "Cl_p": Cl_p, "S_ref": S, "b_ref": b, "criterios": {"pb2V_min": pb2V_min, "t_inclinacao_max": t_inclinacao_max, "inclinacao": inclinacao},
            "ailerons": [{"elemento": n, "nome": c.get("nome"), "y": c["y"], "corda": c.get("corda"), "xc": c.get("xc")} for n, c in ailerons],
            "servo": {"V": V_servo, "itens": momentos_de_charneira(vlm, ailerons, alpha, V_servo, rho, sobe_max, desce_max)},
            "estol_sem_comando": sem, "opcoes": opcoes, "curva": curva, "avisos": avisos}
