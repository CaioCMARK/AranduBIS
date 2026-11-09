from __future__ import annotations

import math

import numpy as np

from .aeronave_vlm import avisos_de_ignoradas
from .dinamica import dinamica
from .equilibrio import monta

OPCOES = ("sobe_desce", "so_sobe")

def comandos_de_rolagem(esq: dict) -> list[tuple[str, dict]]:
    sai = []
    for el in esq.get("elementos", []):
        if el.get("tipo") != "asa":
            continue
        for c in el.get("controles") or []:
            if c.get("modo") == "anti":
                sai.append((el.get("nome"), c))
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
                       beta: float = 0.0) -> dict:
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

    def um(opcao, sobe, desce):
        piores = None
        for lado in (+1, -1):
            dflap, xc = _deflexoes(vlm, ailerons, opcao, sobe, desce, lado)
            r = vlm.resolver(alpha, V=V, rho=rho, beta=beta, delta_flap=dflap, x_charneira=xc)[0]
            cl, cn = float(r.Cl - base.Cl), float(r.Cn - base.Cn)
            if piores is None or abs(cl) < abs(piores["Cl"]):
                piores = {"Cl": cl, "Cn": cn, "xc": xc, "lado": lado}
        pb2V = abs(piores["Cl"] / Cl_p) if Cl_p < 0 else float("nan")
        p_ss = pb2V * 2.0 * V / b if math.isfinite(pb2V) else float("nan")
        t_inc = _tempo_ate(inclinacao, p_ss, tau) if math.isfinite(p_ss) and math.isfinite(tau) else None
        return {"opcao": opcao, "sobe": sobe, "desce": desce if opcao == "sobe_desce" else 0.0, "Cl_comando": piores["Cl"],
                "Cn_comando": piores["Cn"], "pb2V": pb2V, "p_regime_graus_s": math.degrees(p_ss) if math.isfinite(p_ss) else None,
                "tempo_inclinacao_s": t_inc, "guinada_adversa": piores["Cn"] / piores["Cl"] if abs(piores["Cl"]) > 1e-9 else None,
                "xc": piores["xc"], "ok_pb2V": bool(math.isfinite(pb2V) and pb2V >= pb2V_min),
                "ok_tempo": bool(t_inc is not None and t_inc <= t_inclinacao_max)}

    opcoes = {"sobe_desce": um("sobe_desce", sobe_max, desce_max), "so_sobe": um("so_sobe", sobe_max, 0.0)}
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
            "opcoes": opcoes, "curva": curva, "avisos": avisos}
