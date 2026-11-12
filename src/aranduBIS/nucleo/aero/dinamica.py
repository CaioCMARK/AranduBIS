from __future__ import annotations

import math

import numpy as np
from scipy.linalg import expm

from ..modelador import aeronave_geometria as AG
from ..modelador import superficies_comando as SC
from .aeronave_vlm import avisos_de_ignoradas, superficies
from .equilibrio import longitudinal, monta
from .estabilidade import derivadas, derivadas_de_controle

G = 9.80665

def inercias(esq: dict) -> dict:
    A = AG.constroi(esq)
    r = AG.massa_e_cg(A)
    if not r["massa_kg"] or r["cg_m"] is None:
        raise ValueError("o modelo nao declara nenhuma massa: informe massa e inercias na tela")
    cg = np.asarray(r["cg_m"], float)
    semi = {}
    for el in esq.get("elementos", []):
        if el.get("tipo") == "asa":
            ys = [abs(float(s["y"])) for s in el.get("secoes", [])]
            if ys:
                semi[el.get("nome")] = max(ys)
    Ixx = Iyy = Izz = Ixz = 0.0
    for it in r["itens"]:
        m = float(it["massa"])
        dx, dy, dz = np.asarray(it["cg"], float) - cg
        Ixx += m * (dy * dy + dz * dz)
        Iyy += m * (dx * dx + dz * dz)
        Izz += m * (dx * dx + dy * dy)
        Ixz += m * dx * dz
        s = semi.get(str(it["nome"]).split(".")[0])
        if s and abs(float(it["cg"][1])) < 0.05 * s:
            Ixx += m * (2 * s) ** 2 / 12.0
            Izz += m * (2 * s) ** 2 / 12.0
    return {"m": float(r["massa_kg"]), "cg": cg.tolist(), "Ixx": Ixx, "Iyy": Iyy, "Izz": Izz, "Ixz": Ixz}

RAIOS_PADRAO = {"rx": 0.25, "ry": 0.38, "rz": 0.39}

def inercias_por_raio(esq: dict, m: float, raios: dict | None = None) -> dict:
    r = {**RAIOS_PADRAO, **(raios or {})}
    V = AG.constroi(esq).so_camada("aero").V
    b = float(V[:, 1].max() - V[:, 1].min())
    L = float(V[:, 0].max() - V[:, 0].min())
    e = 0.5 * (b + L)
    return {"Ixx": m * (r["rx"] * b) ** 2, "Iyy": m * (r["ry"] * L) ** 2, "Izz": m * (r["rz"] * e) ** 2, "Ixz": 0.0, "b": b, "L": L}

def _modos(A: np.ndarray) -> list[complex]:
    return list(np.linalg.eigvals(A))

def _monta_estado(esq: dict, x_cg: float | None = None, V: float = 12.0, rho: float = 1.1, massa_kg: float | None = None,
                  I: dict | None = None, z_cg: float | None = None,
                  raios: dict | None = None, modo_inercia: str = "auto") -> dict:
    avisos = avisos_de_ignoradas(esq)
    try:
        prop = inercias(esq)
        com_modelo = True
    except ValueError:
        if massa_kg is None or x_cg is None or not (I or raios is not None):
            raise
        prop, com_modelo = {"m": massa_kg, "cg": [x_cg, 0.0, 0.0], "Ixx": 0, "Iyy": 0, "Izz": 0, "Ixz": 0, **(I or {})}, False
    m = float(massa_kg) if massa_kg else prop["m"]
    origem_m = "voce" if massa_kg else "modelo"
    cg = prop["cg"] if x_cg is None else [float(x_cg), prop["cg"][1], prop["cg"][2]]
    z = float(z_cg) if z_cg is not None else float(cg[2])
    decl = esq.get("inercias") or {}
    declarada = False
    if not I and all(decl.get(k) is not None for k in ("Ixx", "Iyy", "Izz")):
        I, declarada = {k: float(decl.get(k, 0.0)) for k in ("Ixx", "Iyy", "Izz", "Ixz")}, True
    usa_raio = (not I and raios is not None and
                (modo_inercia == "raio" or (modo_inercia == "auto" and (not com_modelo or prop["m"] < 0.5 * m))))
    if usa_raio:
        est = inercias_por_raio(esq, m, raios)
        Ixx, Iyy, Izz, Ixz = est["Ixx"], est["Iyy"], est["Izz"], 0.0
        origem_I = "estimada por raio de giro"
        avisos.append(f"Inércias estimadas por raio de giro (b = {est['b']:.2f} m, L = {est['L']:.2f} m): são hipótese de projeto, não medida.")
    else:
        Ixx, Iyy, Izz, Ixz = (float((I or {}).get(k, prop[k])) for k in ("Ixx", "Iyy", "Izz", "Ixz"))
        origem_I = "declarada no modelo" if declarada else ("voce" if I else "modelo")
    if min(Ixx, Iyy, Izz) <= 0 or Iyy > Ixx + Izz or Ixx > Iyy + Izz or Izz > Ixx + Iyy:
        avisos.append("As inércias violam a desigualdade triangular (cada uma deve ser ≤ soma das outras duas): "
                      "não descrevem um corpo rígido real; confira os valores e os eixos.")
    if com_modelo and prop["m"] < 0.5 * m and not (raios is not None and not I and modo_inercia != "modelo"):
        avisos.append(f"O modelo declara so {prop['m']:.2f} kg de {m:.2f} kg: faltam bateria, motor e carga no modelo "
                      "(use elementos de massa) ou informe as inercias; CG e inercias do modelo NAO valem.")
    vlm = monta(esq, cg[0], z)
    q = 0.5 * rho * V * V
    CL_req = m * G / (q * vlm.S_ref)
    lg = longitudinal(esq, cg[0], V=V, rho=rho, CL_alvo=CL_req, z_cg=z)
    if lg["trim"] is None:
        raise ValueError("sem equilibrio nessa condicao: " + ("; ".join(lg["avisos"]) or "CL fora da faixa"))
    avisos += [a for a in lg["avisos"] if a not in avisos]
    alpha = lg["trim"]["alpha"]
    d = derivadas(vlm, alpha, V=V, rho=rho)
    S, b, c = vlm.S_ref, vlm.b_ref, vlm.c_ref
    qS = q * S
    Za = -qS * d.CL_alpha / (m * V)
    Ma = qS * c * d.Cm_alpha / Iyy
    Mq = qS * c * c * d.Cm_q / (2.0 * V * Iyy)
    As = np.array([[Za, 1.0], [Ma, Mq]])
    ev = _modos(As)
    sp = _par(ev)
    CD = lg["trim"]["CDi"] + 0.03
    LD = CL_req / CD
    fug = {"omega": math.sqrt(2) * G / V, "zeta": 1.0 / (math.sqrt(2) * LD),
           "nota": "aproximacao de Lanchester com CD = CDi + 0,03 (arrasto parasita nao entra)"}
    Yv = qS * d.CY_beta / (m * V)
    Lv, Lp, Lr = qS * b * d.Cl_beta / (Ixx * V), qS * b * b * d.Cl_p / (2 * Ixx * V), qS * b * b * d.Cl_r / (2 * Ixx * V)
    Nv, Np, Nr = qS * b * d.Cn_beta / (Izz * V), qS * b * b * d.Cn_p / (2 * Izz * V), qS * b * b * d.Cn_r / (2 * Izz * V)
    den = 1.0 - Ixz * Ixz / (Ixx * Izz)
    Lv_, Lp_, Lr_ = ((Lv + Ixz / Ixx * Nv) / den, (Lp + Ixz / Ixx * Np) / den, (Lr + Ixz / Ixx * Nr) / den)
    Nv_, Np_, Nr_ = ((Nv + Ixz / Izz * Lv) / den, (Np + Ixz / Izz * Lp) / den, (Nr + Ixz / Izz * Lr) / den)
    Al = np.array([[Yv, 0.0, -V, G], [Lv_, Lp_, Lr_, 0.0], [Nv_, Np_, Nr_, 0.0], [0.0, 1.0, 0.0, 0.0]])
    return {
        "avisos": avisos, "m": m, "origem_m": origem_m, "cg": cg, "z": z,
        "Ixx": Ixx, "Iyy": Iyy, "Izz": Izz, "Ixz": Ixz, "origem_I": origem_I,
        "vlm": vlm, "q": q, "CL_req": CL_req, "CDi": lg["trim"]["CDi"], "alpha": alpha, "d": d,
        "S": S, "b": b, "c": c, "As": As, "Al": Al, "V": V, "rho": rho,
    }

def dinamica(esq: dict, x_cg: float | None = None, V: float = 12.0, rho: float = 1.1, massa_kg: float | None = None,
             I: dict | None = None, z_cg: float | None = None,
             raios: dict | None = None, modo_inercia: str = "auto") -> dict:
    base = _monta_estado(esq, x_cg=x_cg, V=V, rho=rho, massa_kg=massa_kg, I=I, z_cg=z_cg, raios=raios, modo_inercia=modo_inercia)
    As, Al, d, avisos = base["As"], base["Al"], base["d"], base["avisos"]
    ev = _modos(As)
    sp = _par(ev)
    CD = base["CDi"] + 0.03
    LD = base["CL_req"] / CD
    fug = {"omega": math.sqrt(2) * G / V, "zeta": 1.0 / (math.sqrt(2) * LD),
           "nota": "aproximacao de Lanchester com CD = CDi + 0,03 (arrasto parasita nao entra)"}
    el = _modos(Al)
    dr = next((l for l in el if abs(l.imag) > 1e-9 and l.imag > 0), None)
    reais = sorted([l.real for l in el if abs(l.imag) <= 1e-9])
    roll = min(reais) if reais else None
    espiral = max(reais) if reais else None
    if dr is None:
        avisos.append("Sem par complexo na dinamica lateral: o dutch roll e superamortecido ou o modelo esta fora da faixa.")
    modos = {
        "curto_periodo": sp, "fugoide": fug,
        "rolagem": None if roll is None else {"lambda": roll, "tau": -1.0 / roll if roll < 0 else None},
        "espiral": None if espiral is None else {"lambda": espiral, "estavel": bool(espiral < 0),
                                                 "t_metade_ou_dobro": math.log(2) / abs(espiral) if abs(espiral) > 1e-12 else None},
        "dutch_roll": None if dr is None else {"omega": abs(dr), "zeta": -dr.real / abs(dr), "periodo": 2 * math.pi / dr.imag,
                                               "sigma": dr.real},
    }
    t = np.linspace(0.0, 10.0, 101)
    x0 = np.array([V * math.radians(5.0), 0.0, 0.0, 0.0])
    lat = np.array([expm(Al * ti) @ x0 for ti in t])
    y0 = np.array([math.radians(5.0), 0.0])
    lon = np.array([expm(As * ti) @ y0 for ti in t])
    resposta = {"t": t.tolist(), "beta": np.degrees(lat[:, 0] / V).tolist(), "phi": np.degrees(lat[:, 3]).tolist(),
                "r": np.degrees(lat[:, 2]).tolist(), "alpha": np.degrees(lon[:, 0]).tolist(), "q": np.degrees(lon[:, 1]).tolist()}
    return {
        "V": V, "rho": rho, "alpha": base["alpha"], "CL": base["CL_req"], "m": base["m"], "origem_massa": base["origem_m"],
        "origem_inercia": base["origem_I"],
        "inercias": {"Ixx": base["Ixx"], "Iyy": base["Iyy"], "Izz": base["Izz"], "Ixz": base["Ixz"]},
        "cg": base["cg"], "S_ref": base["S"], "b_ref": base["b"], "c_ref": base["c"],
        "derivadas": {k: float(getattr(d, k)) for k in ("CL_alpha", "Cm_alpha", "Cm_q", "CY_beta", "Cl_beta", "Cn_beta",
                                                          "Cl_p", "Cl_r", "Cn_p", "Cn_r")},
        "margem_estatica": float(d.margem_estatica), "ponto_neutro": float(d.ponto_neutro),
        "resposta": resposta, "modos": modos, "avaliacao": avaliar(modos, d), "avisos": avisos,
    }

def _resposta_forcada(A: np.ndarray, B: np.ndarray, u0: float, duracao: float, t: np.ndarray) -> np.ndarray:
    B = np.asarray(B, float).reshape(-1, 1)
    n = A.shape[0]
    xp = -np.linalg.pinv(A) @ (B * u0)
    Ident = np.eye(n)
    x_fim_degrau = None
    x = np.zeros((len(t), n))
    for i, ti in enumerate(t):
        if ti <= duracao:
            x[i] = ((Ident - expm(A * ti)) @ xp).ravel()
            x_fim_degrau = x[i]
        else:
            if x_fim_degrau is None:
                x_fim_degrau = ((Ident - expm(A * duracao)) @ xp).ravel()
            x[i] = (expm(A * (ti - duracao)) @ x_fim_degrau.reshape(-1, 1)).ravel()
    return x

def comandos_disponiveis(esq: dict) -> list[dict]:
    return [{"nome": c["nome"], "elemento": c["elemento"], "modo": c.get("modo", "sim"), "y": c["y"]}
            for c in SC.lista(esq)]

def resposta_a_comando(esq: dict, nome_controle: str, deflexao_graus: float = 10.0, duracao_s: float = 0.3,
                       x_cg: float | None = None, V: float = 12.0, rho: float = 1.1, massa_kg: float | None = None,
                       I: dict | None = None, z_cg: float | None = None, raios: dict | None = None,
                       modo_inercia: str = "auto", t_total: float | None = None) -> dict:
    base = _monta_estado(esq, x_cg=x_cg, V=V, rho=rho, massa_kg=massa_kg, I=I, z_cg=z_cg, raios=raios, modo_inercia=modo_inercia)
    controles = {c["nome"]: c for c in SC.lista(esq)}
    c = controles.get(nome_controle)
    if c is None:
        raise ValueError(f"comando {nome_controle!r} não existe no modelo; disponíveis: {sorted(controles)}")
    dc = derivadas_de_controle(base["vlm"], c["elemento"], c, base["alpha"], V=V, rho=rho)
    if dc is None:
        raise ValueError(f"comando {nome_controle!r} não cobre nenhuma faixa do VLM (y = {c['y']})")
    S, b, c_ref, q = base["S"], base["b"], base["c"], base["q"]
    m, Ixx, Iyy, Izz, Ixz = base["m"], base["Ixx"], base["Iyy"], base["Izz"], base["Ixz"]
    den = 1.0 - Ixz * Ixz / (Ixx * Izz)
    B_long = np.array([-q * S * dc["CL_delta"] / (m * V), q * S * c_ref * dc["Cm_delta"] / Iyy])
    L_delta, N_delta = q * S * b * dc["Cl_delta"] / Ixx, q * S * b * dc["Cn_delta"] / Izz
    B_lat = np.array([q * S * dc["CY_delta"] / m, (L_delta + Ixz / Ixx * N_delta) / den,
                      (N_delta + Ixz / Izz * L_delta) / den, 0.0])
    delta = math.radians(deflexao_graus)
    t_total = float(t_total) if t_total else max(10.0, duracao_s * 8.0)
    t = np.linspace(0.0, t_total, 161)
    lon = _resposta_forcada(base["As"], B_long, delta, duracao_s, t)
    lat = _resposta_forcada(base["Al"], B_lat, delta, duracao_s, t)
    resposta = {"t": t.tolist(), "alpha": np.degrees(lon[:, 0]).tolist(), "q": np.degrees(lon[:, 1]).tolist(),
                "beta": np.degrees(lat[:, 0] / V).tolist(), "phi": np.degrees(lat[:, 3]).tolist(),
                "r": np.degrees(lat[:, 2]).tolist()}

    def pico(serie):
        a = np.abs(serie)
        return float(a.max()) if len(a) else 0.0

    return {
        "controle": nome_controle, "elemento": c["elemento"], "modo": c.get("modo", "sim"),
        "deflexao_graus": deflexao_graus, "duracao_s": duracao_s, "t_total": t_total, "V": V, "alpha": base["alpha"],
        "derivadas": dc, "resposta": resposta,
        "picos": {"alpha_graus": pico(resposta["alpha"]), "q_graus_s": pico(resposta["q"]),
                 "beta_graus": pico(resposta["beta"]), "phi_graus": pico(resposta["phi"])},
        "avisos": base["avisos"],
    }

def _par(ev) -> dict:
    ev = sorted(ev, key=lambda l: -l.imag)
    l = ev[0]
    if abs(l.imag) > 1e-9:
        return {"omega": abs(l), "zeta": -l.real / abs(l), "periodo": 2 * math.pi / l.imag, "oscilatorio": True}
    return {"raizes": sorted(float(x.real) for x in ev), "oscilatorio": False, "omega": None, "zeta": None}

def avaliar(m: dict, d) -> list[dict]:
    sai = []

    def ok(nome, valor, texto, bom, lim):
        sai.append({"nome": nome, "valor": valor, "limite": lim, "ok": bool(bom), "texto": texto})

    ok("Estabilidade de arfagem (Cmα < 0)", float(d.Cm_alpha), "Cmα negativo: o nariz volta ao ângulo de equilíbrio.", d.Cm_alpha < 0, "< 0")
    ok("Efeito diedro (Clβ < 0)", float(d.Cl_beta), "Clβ negativo: a asa levanta ao derrapar para o lado oposto.", d.Cl_beta < 0, "< 0")
    ok("Estabilidade direcional (Cnβ > 0)", float(d.Cn_beta), "Cnβ positivo: o nariz aponta para o vento relativo.", d.Cn_beta > 0, "> 0")
    sp = m["curto_periodo"]
    if sp.get("oscilatorio"):
        ok("Curto período, amortecimento", sp["zeta"], "Referência: entre 0,3 e 2.", 0.3 <= sp["zeta"] <= 2.0, "0,3 a 2")
    dr = m["dutch_roll"]
    if dr:
        ok("Dutch roll, amortecimento", dr["zeta"], "Referência MIL-F-8785C classe I: ≥ 0,19 (nível 1), ≥ 0,02 (nível 3). Aqui exijo 0,1.",
           dr["zeta"] >= 0.1, "≥ 0,1")
    r = m["rolagem"]
    if r and r["tau"] is not None:
        ok("Rolagem, constante de tempo (s)", r["tau"], "Referência MIL-F-8785C classe I: ≤ 1,0 s.", r["tau"] <= 1.0, "≤ 1,0 s")
    e = m["espiral"]
    if e:
        t2 = None if e["estavel"] else e["t_metade_ou_dobro"]
        ok("Espiral", float("inf") if e["estavel"] else t2,
           "Estável, ou tempo para dobrar ≥ 12 s (MIL-F-8785C classe I, nível 1).", e["estavel"] or (t2 is not None and t2 >= 12.0), "estável ou ≥ 12 s")
    return sai
