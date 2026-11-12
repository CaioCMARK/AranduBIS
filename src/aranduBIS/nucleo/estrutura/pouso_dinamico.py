from __future__ import annotations

import math

import numpy as np

G0 = 9.80665

def _rodas_do_modelo(esq: dict, xcg: float, zcg: float) -> dict:
    rodas = [{"nome": e["nome"], "x": xcg - float(e.get("posicao", [0, 0, 0])[0]), "z": float(e.get("posicao", [0, 0, 0])[2]) - zcg,
              "R": 0.5 * float(e.get("diametro", 0.09))} for e in esq.get("elementos", []) if e.get("tipo") == "roda"]
    if len(rodas) < 3:
        raise ValueError("o modelo precisa de ao menos tres rodas (duas principais e a bequilha) para o pouso")
    nariz = max(rodas, key=lambda r: r["x"])
    principais = [r for r in rodas if r is not nariz]
    return {"principal": {"x": float(np.mean([r["x"] for r in principais])), "z": float(np.mean([r["z"] for r in principais])), "R": float(np.mean([r["R"] for r in principais])),
                          "n": len(principais), "nomes": [r["nome"] for r in principais]},
            "bequilha": {"x": nariz["x"], "z": nariz["z"], "R": nariz["R"], "n": 1, "nomes": [nariz["nome"]]}}

def atitude_de_tres_pontos(rodas: dict) -> tuple[float, float]:
    a, b = rodas["principal"], rodas["bequilha"]
    za, zb = a["z"] - a["R"], b["z"] - b["R"]
    th = 0.0
    for _ in range(50):
        f = (a["x"] * math.sin(th) + za * math.cos(th)) - (b["x"] * math.sin(th) + zb * math.cos(th))
        d = (a["x"] * math.cos(th) - za * math.sin(th)) - (b["x"] * math.cos(th) - zb * math.sin(th))
        if abs(d) < 1e-12:
            break
        th -= f / d
        if abs(f) < 1e-12:
            break
    h = -(a["x"] * math.sin(th) + za * math.cos(th))
    return float(h), float(th)

def perfil_de_pista(tipo: str, altura_m: float, comprimento_m: float, x0: float, semente: int = 1):
    if tipo == "plana" or altura_m <= 0:
        return (lambda x: 0.0), (lambda x: 0.0)
    if tipo == "lombada":
        def z(x):
            u = (x - x0) / comprimento_m
            return altura_m * math.sin(math.pi * u) if 0.0 < u < 1.0 else 0.0

        def dz(x):
            u = (x - x0) / comprimento_m
            return altura_m * math.pi / comprimento_m * math.cos(math.pi * u) if 0.0 < u < 1.0 else 0.0
        return z, dz
    if tipo == "degrau":
        def z(x):
            u = (x - x0) / comprimento_m
            return 0.0 if u <= 0 else altura_m if u >= 1 else altura_m * 0.5 * (1 - math.cos(math.pi * u))

        def dz(x):
            u = (x - x0) / comprimento_m
            return altura_m * 0.5 * math.pi / comprimento_m * math.sin(math.pi * u) if 0.0 < u < 1.0 else 0.0
        return z, dz
    if tipo == "irregular":
        rng = np.random.default_rng(semente)
        n = np.linspace(0.2, 10.0, 60)
        A = np.sqrt(2.0 * (n / 1.0) ** -2.0 * (n[1] - n[0]))
        A *= altura_m / math.sqrt(0.5 * float(np.sum(A ** 2)))
        ph = rng.uniform(0, 2 * np.pi, n.size)
        k = 2 * np.pi * n

        def z(x):
            if x < x0:
                return 0.0
            e = min(1.0, (x - x0) / 1.0)
            return float(e * np.sum(A * np.sin(k * (x - x0) + ph)))

        def dz(x):
            if x < x0:
                return 0.0
            e = min(1.0, (x - x0) / 1.0)
            return float(e * np.sum(A * k * np.cos(k * (x - x0) + ph)))
        return z, dz
    raise ValueError(f"perfil de pista desconhecido: {tipo!r} (plana, lombada, degrau, irregular)")

def simula(p: dict, rodas: dict, h0: float, th0: float, vz0: float, V0: float, t_fim: float, solo=None, dsolo=None, dt: float = 5e-4,
           velocidade_constante: bool = False, X0: float = 0.0, passo_saida: int = 20) -> dict:
    m, I, S, cb, rho = p["m"], p["Iyy"], p["S"], p["c"], p["rho"]
    CLa, CLmax, CL0, a0, Cma, Cmq, CD, mu = p["CLa"], p["CLmax"], p["CL0"], p["alfa0"], p["Cma"], p["Cmq"], p["CD"], p["mu"]
    solo = solo or (lambda x: 0.0)
    dsolo = dsolo or (lambda x: 0.0)
    W = m * G0
    trens = []
    for nome in ("principal", "bequilha"):
        r, g = rodas[nome], p["trens"][nome]
        k = 1.0 / (1.0 / g["k_pneu"] + 1.0 / g["k_perna"])
        m_ap = m * (0.5 if nome == "principal" else 0.25)
        trens.append((nome, r["x"], r["z"], r["R"], k, 2.0 * g["zeta"] * math.sqrt(k * m_ap), g["curso"]))

    def forcas(s):
        h, vz, th, w, X, V = s
        c_, s_ = math.cos(th), math.sin(th)
        FN, FX, MY, info = 0.0, 0.0, 0.0, []
        for nome, xb, zb, R, k, cd, curso in trens:
            rx, rz = xb * c_ - zb * s_, xb * s_ + zb * c_
            hc = h + rz
            d = solo(X + rx) - (hc - R)
            if d <= 0.0:
                info.append((0.0, d))
                continue
            dd = dsolo(X + rx) * V - (vz + w * rx)
            N = k * d + cd * dd + (10.0 * k * (d - curso) if 0.0 < curso < d else 0.0)
            N = max(N, 0.0)
            fx = -mu * N if V > 0.1 else 0.0
            FN += N; FX += fx; MY += rx * N - rz * fx
            info.append((N, d))
        al = th - math.atan2(vz, max(V, 1.0))
        q = 0.5 * rho * V * V
        CL = min(max(CL0 + CLa * (al - a0), -CLmax), CLmax)
        L, D = q * S * CL, q * S * CD
        MY += q * S * cb * (Cma * (al - a0) + Cmq * w * cb / (2.0 * max(V, 1.0)))
        return FN, FX, MY, L, D, info

    def deriv(s):
        FN, FX, MY, L, D, info = forcas(s)
        dV = 0.0 if velocidade_constante else (FX - D) / m
        return np.array([s[1], (FN + L) / m - G0, s[3], MY / I, s[5], dV])

    s = np.array([h0, vz0, th0, 0.0, X0, V0], float)
    n_pas = int(round(t_fim / dt))
    T, H, TH, VZ, V_, NP, NB, ACG, LL, DP, DB = ([] for _ in range(11))
    for i in range(n_pas + 1):
        if i % passo_saida == 0 or i == n_pas:
            FN, FX, MY, L, D, info = forcas(s)
            T.append(i * dt); H.append(s[0]); TH.append(s[2]); VZ.append(s[1]); V_.append(s[5])
            NP.append(info[0][0]); NB.append(info[1][0]); ACG.append((FN + L) / W - 1.0); LL.append(L)
            DP.append(max(info[0][1], 0.0)); DB.append(max(info[1][1], 0.0))
        if i == n_pas:
            break
        k1 = deriv(s); k2 = deriv(s + 0.5 * dt * k1); k3 = deriv(s + 0.5 * dt * k2); k4 = deriv(s + dt * k3)
        s = s + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        if not np.all(np.isfinite(s)):
            raise ValueError("a simulacao divergiu: reduza a razao de descida ou confira as rigidezes")
    NP, NB = np.array(NP), np.array(NB)
    return {"t": T, "h": H, "theta_graus": np.degrees(TH).tolist(), "vz": VZ, "V": V_, "N_principal": NP.tolist(), "N_bequilha": NB.tolist(),
            "n_cg": ACG, "sustentacao": LL, "delta_principal_mm": (1000 * np.array(DP)).tolist(), "delta_bequilha_mm": (1000 * np.array(DB)).tolist(),
            "pico": {"N_principal": float(NP.max()), "t_N_principal": float(T[int(np.argmax(NP))]), "N_bequilha": float(NB.max()), "t_N_bequilha": float(T[int(np.argmax(NB))],),
                     "N_bequilha_no_pico_principal": float(NB[int(np.argmax(NP))]), "N_principal_no_pico_bequilha": float(NP[int(np.argmax(NB))]),
                     "N_total": float((NP + NB).max()), "fator_principal": float(NP.max() / W), "fator_bequilha": float(NB.max() / W), "fator_total": float((NP + NB).max() / W),
                     "delta_principal_mm": float(max(DP) * 1000), "delta_bequilha_mm": float(max(DB) * 1000), "theta_max_graus": float(np.degrees(max(TH))), "theta_min_graus": float(np.degrees(min(TH))),
                     "n_cg_max": float(max(ACG))}}

def quicadas(r: dict, t_toque: float = 0.0, minimo_s: float = 0.03) -> dict:
    t = np.array(r["t"]); fora = (np.array(r["N_principal"]) + np.array(r["N_bequilha"])) <= 0.0
    ja = np.flatnonzero(~fora)
    if len(ja) == 0:
        return {"n": 0, "tempo_s": 0.0}
    inicio = ja[0]
    n, dur, tempo = 0, 0.0, 0.0
    for i in range(inicio, len(t)):
        if fora[i]:
            dur += t[1] - t[0]
        else:
            if dur >= minimo_s:
                n += 1; tempo += dur
            dur = 0.0
    return {"n": n, "tempo_s": float(tempo)}

def _h0_pouso(rodas, th0):
    a, b = rodas["principal"], rodas["bequilha"]
    fundo = lambda r: r["x"] * math.sin(th0) + (r["z"]) * math.cos(th0) - r["R"]
    return -min(fundo(a), fundo(b))

def analisa(esq: dict, massa_kg: float | None = None, x_cg: float | None = None, Iyy: float | None = None, S: float = 1.0, c_med: float = 0.3, CL_alpha: float = 4.5,
            Cm_alpha: float = -0.5, CL_max: float = 1.4, Vs: float = 10.0, rho: float = 1.1, V_toque_rel: float = 1.15, vel_descida: float = 1.0, atitude_2p_extra: float = 6.0,
            sustentacao_toque_rel: float = 1.0, Cm_q: float = -8.0, CD: float = 0.12, mu_rolamento: float = 0.05, k_pneu_principal: float = 30000.0,
            k_pneu_bequilha: float = 30000.0, k_perna_principal: float | None = None, k_perna_bequilha: float | None = None, zeta: float = 0.15,
            curso_trem_mm: float = 0.0, perfil_pista: str = "irregular", altura_pista_mm: float = 5.0, comprimento_pista_m: float = 0.3, V_taxi_rel: float = 0.8,
            sustentacao_taxi_rel: float = 0.0, fator_pouso_projeto: float = 5.4, razoes: tuple = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0), aplica_fe: bool = False,
            atrito_pouso: float = 0.3, fator_seguranca: float = 1.2, K_flambagem: float = 0.8, raio_inercia: float = 0.25, raio_solda: float = 0.0, mats: dict | None = None,
            qualidade_carbono: float = 1.0, fe_estatico: dict | None = None) -> dict:
    from ..modelador import aeronave_geometria as AG
    from . import trem as TR

    mc = AG.massa_e_cg(AG.constroi(esq))
    cg = mc["cg_m"]
    massa = float(massa_kg) if massa_kg else float(mc["massa_kg"])
    if not massa or massa <= 0:
        raise ValueError("sem massa: declare as pecas no modelo ou informe a massa")
    xcg = float(x_cg) if x_cg is not None else float(cg[0])
    zcg = float(cg[2])
    rodas = _rodas_do_modelo(esq, xcg, zcg)
    if not (rodas["principal"]["x"] < 0.0 < rodas["bequilha"]["x"]):
        raise ValueError(f"o CG (x = {xcg:.3f} m) precisa ficar entre a bequilha e as principais para o pouso")
    if Iyy is None:
        Iyy = float((esq.get("inercias") or {}).get("Iyy") or 0.0)
        if not Iyy:
            from .massa import balanco
            Iyy = float(balanco(esq)["inercias_calculadas"]["Iyy"])
    avisos = []
    fe_k = fe_estatico or TR.analisa(esq, massa_kg=massa, x_cg=xcg, fator_pouso=fator_pouso_projeto, atrito_pouso=atrito_pouso, fator_seguranca=fator_seguranca,
                                     K_flambagem=K_flambagem, raio_inercia=raio_inercia, raio_solda=raio_solda, mats=mats, qualidade_carbono=qualidade_carbono)
    c0 = fe_k["casos"][0]
    rig = {}
    for nome in ("principal", "bequilha"):
        ks = []
        for n in rodas[nome]["nomes"]:
            dz = abs(c0["deslocamento_rodas_mm"][n][2]) * 1e-3
            if dz > 1e-9:
                ks.append(c0["rodas"][n]["R"] / dz)
        rig[nome] = float(np.sum(ks)) if ks else 1e9
    k_pm = float(k_perna_principal) if k_perna_principal else rig["principal"]
    k_pb = float(k_perna_bequilha) if k_perna_bequilha else rig["bequilha"]
    W = massa * G0
    V_td = V_toque_rel * Vs
    h3, th3 = atitude_de_tres_pontos(rodas)
    CL_td = sustentacao_toque_rel * W / (0.5 * rho * V_td ** 2 * S)
    if CL_td > CL_max:
        avisos.append(f"A sustentação pedida no toque (L/W = {sustentacao_toque_rel:g}) pede CL = {CL_td:.2f}, acima do máximo {CL_max:.2f}: o CL foi limitado.")
    base = {"m": massa, "Iyy": Iyy, "S": S, "c": c_med, "rho": rho, "CLa": CL_alpha, "CLmax": CL_max, "CL0": min(CL_td, CL_max), "alfa0": th3, "Cma": Cm_alpha, "Cmq": Cm_q,
            "CD": CD, "mu": mu_rolamento,
            "trens": {"principal": {"k_pneu": k_pneu_principal * rodas["principal"]["n"], "k_perna": k_pm, "zeta": zeta, "curso": 1e-3 * curso_trem_mm},
                      "bequilha": {"k_pneu": k_pneu_bequilha, "k_perna": k_pb, "zeta": zeta, "curso": 1e-3 * curso_trem_mm}}}

    def pouso(th0, vs, t_fim=0.8, dt=5e-4):
        p = dict(base, alfa0=th0)
        return simula(p, rodas, _h0_pouso(rodas, th0), th0, -vs, V_td, t_fim, dt=dt, passo_saida=int(round(0.01 / dt)))

    casos = {}
    for chave, th0, rot in (("pouso_3_pontos", th3, "três pontos (as três rodas tocam juntas)"),
                            ("pouso_2_pontos", th3 + math.radians(atitude_2p_extra), f"dois pontos (principais primeiro, {atitude_2p_extra:g}° a mais de atitude)")):
        r = pouso(th0, vel_descida)
        r["descricao"] = f"{rot}, razão de descida {vel_descida:g} m/s, V = {V_td:.1f} m/s"
        r["quicadas"] = quicadas(r)
        casos[chave] = r
    varredura = {"razao": list(razoes)}
    for chave, th0 in (("pouso_3_pontos", th3), ("pouso_2_pontos", th3 + math.radians(atitude_2p_extra))):
        pr = [pouso(th0, v, 0.6, 1e-3)["pico"] for v in razoes]
        varredura[chave] = {"fator_principal": [x["fator_principal"] for x in pr], "fator_bequilha": [x["fator_bequilha"] for x in pr], "fator_total": [x["fator_total"] for x in pr]}
        lim = None
        for i in range(1, len(razoes)):
            f0, f1 = pr[i - 1]["fator_total"], pr[i]["fator_total"]
            if f0 < fator_pouso_projeto <= f1:
                lim = razoes[i - 1] + (fator_pouso_projeto - f0) / (f1 - f0) * (razoes[i] - razoes[i - 1])
                break
        varredura[chave]["razao_limite"] = lim
    V_t = V_taxi_rel * Vs
    x_ini = V_t * 1.2
    zf, dzf = perfil_de_pista(perfil_pista, altura_pista_mm * 1e-3, comprimento_pista_m, x_ini)
    CL_tx = min(sustentacao_taxi_rel * W / (0.5 * rho * V_t ** 2 * S), CL_max)
    p_tx = dict(base, CL0=CL_tx, alfa0=th3)
    taxi = simula(p_tx, rodas, h3, th3, 0.0, V_t, 1.2 + (25.0 if perfil_pista == "irregular" else 6.0) / V_t, solo=zf, dsolo=dzf, velocidade_constante=True, dt=1e-3, passo_saida=20)
    taxi["descricao"] = f"taxi a {V_t:.1f} m/s sobre pista {perfil_pista} ({altura_pista_mm:g} mm" + (f" rms)" if perfil_pista == "irregular" else f", {comprimento_pista_m:g} m)")
    i0 = int(np.searchsorted(taxi["t"], 1.0))
    N_p, N_b = np.array(taxi["N_principal"][i0:]), np.array(taxi["N_bequilha"][i0:])
    taxi["pico"].update({"fator_principal": float(N_p.max() / W), "fator_bequilha": float(N_b.max() / W), "fator_total": float((N_p + N_b).max() / W),
                         "N_principal": float(N_p.max()), "N_bequilha": float(N_b.max())})
    taxi["perda_de_contato_principal_pct"] = float(100 * np.mean(N_p <= 0.0))
    taxi["perda_de_contato_bequilha_pct"] = float(100 * np.mean(N_b <= 0.0))
    casos["taxi"] = taxi
    pico_2p = casos["pouso_2_pontos"]["pico"]
    if pico_2p["fator_total"] > fator_pouso_projeto:
        avisos.append(f"O pouso em dois pontos a {vel_descida:g} m/s passa de {fator_pouso_projeto:g} x o peso ({pico_2p['fator_total']:.1f}): acima do fator de projeto do trem.")
    for k, r in casos.items():
        if curso_trem_mm > 0 and (r["pico"]["delta_principal_mm"] > curso_trem_mm * 1.001 or r["pico"]["delta_bequilha_mm"] > curso_trem_mm * 1.001):
            avisos.append(f"{k.replace('_', ' ')}: o trem chega ao batente ({curso_trem_mm:g} mm): a carga passa a ser a do batente, bem mais rígida.")
        dp = 1000 * r["pico"]["N_principal"] / (k_pneu_principal * rodas["principal"]["n"])
        db = 1000 * r["pico"]["N_bequilha"] / k_pneu_bequilha
        r["pico"]["pneu_principal_mm"], r["pico"]["pneu_bequilha_mm"] = dp, db
        lim = 0.25 * 2000 * max(rodas["principal"]["R"], 1e-3)
        if dp > lim or db > 0.25 * 2000 * max(rodas["bequilha"]["R"], 1e-3):
            avisos.append(f"{k.replace('_', ' ')}: o pneu comprime {max(dp, db):.0f} mm (mais de 25 % do diâmetro): ele chega ao aro e a carga real passa da calculada.")
        if k != "taxi" and r["quicadas"]["n"]:
            avisos.append(f"{k.replace('_', ' ')}: a aeronave quica {r['quicadas']['n']} vez(es) (perde o contato por {r['quicadas']['tempo_s']:.2f} s).")
    avisos.append("Estimativas que mandam no resultado: rigidez e amortecimento do pneu (meça num ensaio de queda), a razão de descida e a atitude no toque. A rigidez da perna vem da treliça. "
                  "Sem massa de roda, sem efeito solo, sem atrito lateral; o motor e a hélice não entram.")
    saida = {"casos": {}, "varredura": varredura, "massa_kg": massa, "peso_N": W, "Iyy": Iyy, "cg_x": xcg, "V_toque": V_td, "Vs": Vs, "atitude_3_pontos_graus": math.degrees(th3),
             "altura_cg_3_pontos": h3, "rigidez_perna_N_m": {"principal": k_pm, "bequilha": k_pb, "origem": "informada" if k_perna_principal else "treliça (elementos finitos)"},
             "rigidez_pneu_N_m": {"principal": base["trens"]["principal"]["k_pneu"], "bequilha": k_pneu_bequilha}, "fator_pouso_projeto": fator_pouso_projeto, "avisos": avisos,
             "rodas": {k: {kk: vv for kk, vv in v.items()} for k, v in rodas.items()}}
    for k, r in casos.items():
        saida["casos"][k] = {kk: vv for kk, vv in r.items()}
    if aplica_fe:
        extra = []
        for k, r in casos.items():
            pk = r["pico"]
            mu_ = 0.0 if k == "taxi" else atrito_pouso
            extra.append({"nome": f"{k}_dinamico_pico_principal", "descricao": f"{r['descricao']}: instante do pico da principal ({pk['N_principal']:.0f} N)",
                          "Rm": pk["N_principal"], "Rn": pk["N_bequilha_no_pico_principal"], "mu": mu_})
            extra.append({"nome": f"{k}_dinamico_pico_bequilha", "descricao": f"{r['descricao']}: instante do pico da bequilha ({pk['N_bequilha']:.0f} N)",
                          "Rm": pk["N_principal_no_pico_bequilha"], "Rn": pk["N_bequilha"], "mu": mu_})
        fe = TR.analisa(esq, massa_kg=massa, x_cg=xcg, fator_pouso=fator_pouso_projeto, atrito_pouso=atrito_pouso, fator_seguranca=fator_seguranca, K_flambagem=K_flambagem,
                        raio_inercia=raio_inercia, raio_solda=raio_solda, mats=mats, qualidade_carbono=qualidade_carbono, casos_extra=extra)
        din = [c for c in fe["casos"] if "_dinamico_" in c["caso"]]
        est = min((c for c in fe["casos"] if "_dinamico_" not in c["caso"]), key=lambda c: c["margem"])
        pior = min(din, key=lambda c: c["margem"])
        saida["fe"] = {"casos": din, "critico": {"caso": pior["caso"], "margem": float(pior["margem"]), "barra": pior["piores"][0]["id"], "modo": pior["piores"][0]["modo"],
                                                   "elemento": pior["piores"][0]["elemento"], "tubo": pior["piores"][0]["tubo"]},
                       "margem_estatica": float(est["margem"]), "caso_estatico": est["caso"], "avisos": fe["avisos"]}
    return saida
