from __future__ import annotations

import numpy as np

from ..fe import Sistema
from ..modelador import aeronave_geometria as AG
from . import cauda as CA
from .materiais import propriedades

G0 = 9.80665

def _liga_massas(m, pos, ligados, apoio, ponto, raio, novo):
    d = np.linalg.norm(pos - ponto, axis=1)
    perto = [i + 1 for i in np.argsort(d)[:8] if d[i] <= raio and (i + 1) in ligados and (i + 1) not in apoio] or \
            [i + 1 for i in np.argsort(d) if (i + 1) in ligados and (i + 1) not in apoio][:4]
    m.no(novo, *ponto)
    m.rigido(novo, novo, perto)
    return novo, perto

def _pontos_de_massa(m, mestre, base, deslocamentos, massa, novo, eid):
    nos = []
    for d in deslocamentos:
        m.no(novo, *(np.asarray(base, float) + np.asarray(d, float)))
        m.massa(eid, novo, massa / len(deslocamentos))
        nos.append(novo); novo += 1; eid += 1
    m.rigido(eid, mestre, nos)
    return novo, eid + 1

def _constroi(esq, mats, qualidade_carbono, x_apoio, raio_ligacao, raio_motor, massas, com_massas):
    m, pos, info, avisos = CA.monta(esq, mats, qualidade_carbono)
    grupos = CA._grupos(m)
    apoio, _explicito = CA.aplica_apoios(m, x_apoio, avisos)
    ligados = {n for g in grupos if any(a in g for a in apoio) for n in g}
    nota = []
    if not com_massas:
        return m, pos, ligados, apoio, nota, {"nos": [], "ref": 0.1}
    novo = max(m.nos) + 1
    eid = 100000
    nos_massa = []
    ref = 0.1
    h = CA._ponto_empenagem(esq, "empenagem_h")
    v = CA._ponto_empenagem(esq, "deriva")
    mestre = None
    if h and massas.get("empenagem_h", 0) > 0:
        mestre, _ = _liga_massas(m, pos, ligados, apoio, h["ponto"], raio_ligacao, novo); novo += 1
        b = h["b"]; ref = max(ref, b / 2)
        desl = [[0.0, f * b / 2, 0.0] for f in (-0.8, -0.4, 0.0, 0.4, 0.8)]
        n0 = novo
        novo, eid = _pontos_de_massa(m, mestre, h["ponto"], desl, massas["empenagem_h"], novo, eid)
        nos_massa += list(range(n0, novo))
        nota.append(f"empenagem horizontal: {massas['empenagem_h'] * 1000:.0f} g espalhados em {b:.2f} m de envergadura")
    if v and massas.get("deriva", 0) > 0:
        if mestre is None:
            mestre, _ = _liga_massas(m, pos, ligados, apoio, v["ponto"], raio_ligacao, novo); novo += 1
        alt = v["b"]; ref = max(ref, alt)
        desl = [[0.0, 0.0, f * alt] for f in (-0.33, 0.0, 0.33)]
        n0 = novo
        novo, eid = _pontos_de_massa(m, mestre, v["ponto"], desl, massas["deriva"], novo, eid)
        nos_massa += list(range(n0, novo))
        nota.append(f"deriva: {massas['deriva'] * 1000:.0f} g espalhados em {alt:.2f} m de altura")
    for q in massas.get("pontuais", []):
        p = np.asarray(q["pos"], float)
        cand = [i + 1 for i in np.argsort(np.linalg.norm(pos - p, axis=1)) if (i + 1) in ligados and (i + 1) not in apoio]
        if not cand:
            nota.append(f"{q['nome']}: sem no livre da trelica por perto; tratada como presa no apoio (nao entra)")
            continue
        no = cand[0]
        d = float(np.linalg.norm(pos[no - 1] - p))
        if q.get("so_perto") and d > raio_motor:
            nota.append(f"{q['nome']}: a {d * 1000:.0f} mm da trelica (limite {raio_motor * 1000:.0f} mm): esta no apoio (fuselagem), nao entra nos modos da cauda")
            continue
        m.massa(eid, no, q["massa"]); eid += 1
        nota.append(f"{q['nome']}: {q['massa'] * 1000:.0f} g no no mais proximo da trelica (a {d * 1000:.0f} mm)")
    return m, pos, ligados, apoio, nota, {"nos": nos_massa, "ref": ref}

def _natureza(forma, m, x_apoio, ref):
    s = np.zeros(4)
    for no, u in forma.items():
        if m.nos[no][0] <= x_apoio + 1e-6:
            continue
        s += np.array([u[0] ** 2, u[1] ** 2, u[2] ** 2, (u[3] * ref) ** 2])
    t = s.sum()
    if t <= 0:
        return "indefinido", {}
    p = s / t
    nome = ["axial", "flexao lateral", "flexao vertical", "torcao do boom"][int(np.argmax(p))]
    return nome, {"x": float(p[0]), "y": float(p[1]), "z": float(p[2]), "torcao": float(p[3])}

def _massa_efetiva(S, forma):
    n = S.n
    phi = np.zeros(n)
    for no, i in S.idx.items():
        phi[6 * i:6 * i + 6] = forma[no]
    liv = np.zeros(n)
    for no, i in S.idx.items():
        if no not in S.mod.spc:
            liv[6 * i:6 * i + 3] = 1.0
    out = []
    den = float(phi @ (S.M @ phi))
    for d in range(3):
        r = np.zeros(n)
        r[d::6] = liv[d::6]
        Mt = float(r @ (S.M @ r))
        g = float(phi @ (S.M @ r))
        out.append(g * g / (den * Mt) if den > 0 and Mt > 0 else 0.0)
    return out

def balanco_com_massa(E, I, L, rho_lin, m_ponta):
    meq = m_ponta + 33.0 / 140.0 * rho_lin * L
    k = 3.0 * E * I / L ** 3
    return float(np.sqrt(k / meq) / (2 * np.pi))

def suporte_do_motor(esq, s, massa_motor_kg, mats=None, qualidade_carbono=1.0):
    de, L = float(s["de_m"]), float(s["comprimento_m"])
    di = float(s.get("di_m", 0.0))
    if L <= 0 or de <= 0 or di < 0 or di >= de:
        raise ValueError("suporte do motor: comprimento e diametros precisam ser positivos, com di menor que de")
    nome = s.get("material", "tubo_carbono")
    p = propriedades(nome, esq, mats, qualidade_carbono=qualidade_carbono)
    from ..modelador import aeronave_estrutura as ES
    I = np.pi / 64 * (de ** 4 - di ** 4)
    A = 0.25 * np.pi * (de ** 2 - di ** 2)
    rho = float(ES.densidade(nome, esq))
    m_conj = float(massa_motor_kg) + float(s.get("massa_helice_kg", 0.0)) + float(s.get("massa_extra_kg", 0.0))
    if m_conj <= 0:
        raise ValueError("suporte do motor: informe a massa do motor (e da helice) para o balanco")
    f = balanco_com_massa(p["E"], I, L, rho * A, m_conj)
    return {"f_hz": f, "L_m": L, "de_m": de, "di_m": di, "material": nome, "massa_conjunto_kg": m_conj, "EI": float(p["E"] * I), "massa_tubo_kg": rho * A * L}

def campbell(rpm_min, rpm_max, n_pas, modos, ordens_extra=(), n=60):
    rpm = np.linspace(rpm_min, rpm_max, n)
    ordens = [("1P", 1.0)]
    if n_pas > 1:
        ordens.append((f"{n_pas}P", float(n_pas)))
    for k in ordens_extra:
        if float(k) > 0 and all(abs(float(k) - o) > 1e-9 for _, o in ordens):
            ordens.append((f"{float(k):g}P", float(k)))
    return {"rpm": rpm.tolist(), "ordens": [{"nome": nm, "ordem": o, "f_hz": (o * rpm / 60.0).tolist()} for nm, o in ordens], "modos": modos}

def ressonancias(rpm_min, rpm_max, n_pas, modos, ordens_extra=(), margem_min=0.20, rpm_v=None):
    ordens = [("1P", 1.0)]
    if n_pas > 1:
        ordens.append((f"{n_pas}P", float(n_pas)))
    for k in ordens_extra:
        if float(k) > 0 and all(abs(float(k) - o) > 1e-9 for _, o in ordens):
            ordens.append((f"{float(k):g}P", float(k)))
    out = []
    for md in modos:
        f = md["f_hz"]
        if f is None or f <= 0:
            continue
        for nm, o in ordens:
            lo, hi = o * rpm_min / 60.0, o * rpm_max / 60.0
            rpm_res = 60.0 * f / o
            dentro = lo <= f <= hi
            sep = 0.0 if dentro else (lo / f - 1.0 if f < lo else 1.0 - hi / f)
            sep = float(abs(sep))
            sev = "dentro" if dentro else ("perto" if sep < margem_min else "ok")
            r = {"modo": md["nome"], "natureza": md.get("natureza", ""), "f_modo_hz": float(f), "ordem": nm, "rpm_ressonancia": float(rpm_res),
                 "separacao": sep, "situacao": sev}
            if rpm_v is not None and dentro:
                V, R = np.asarray(rpm_v["V"], float), np.asarray(rpm_v["rpm"], float)
                if len(V) > 1 and np.all(np.diff(R) > 0):
                    r["V_ms"] = float(np.interp(rpm_res, R, V))
            out.append(r)
    ordem = {"dentro": 0, "perto": 1, "ok": 2}
    out.sort(key=lambda r: (ordem[r["situacao"]], r["separacao"]))
    return out

def analisa(esq: dict, massa_empenagem_h_kg: float = 0.0, massa_deriva_kg: float = 0.0, massa_motor_kg: float = 0.0, pos_motor=None,
            adicionais=None, rpm_min: float = 3000.0, rpm_max: float = 9000.0, n_pas: int = 2, ordens_extra=(), margem_min: float = 0.20,
            x_apoio: float = 0.30, mats: dict | None = None, qualidade_carbono: float = 1.0, raio_ligacao: float = 0.10, raio_motor: float = 0.15,
            n_modos: int = 8, suporte_motor: dict | None = None, modos_externos=None, rpm_v: dict | None = None) -> dict:
    if rpm_min <= 0 or rpm_max < rpm_min:
        raise ValueError("faixa de rotacao invalida: rpm_min deve ser positiva e menor ou igual a rpm_max")
    if int(n_pas) < 1:
        raise ValueError("numero de pas deve ser pelo menos 1")
    massas = {"empenagem_h": float(massa_empenagem_h_kg), "deriva": float(massa_deriva_kg), "pontuais": []}
    avisos = []
    if massa_motor_kg > 0 and pos_motor is not None:
        massas["pontuais"].append({"nome": "motor", "massa": float(massa_motor_kg), "pos": [float(x) for x in pos_motor], "so_perto": True})
    for a in adicionais or []:
        if float(a.get("massa_kg", 0)) > 0:
            massas["pontuais"].append({"nome": a.get("nome", "massa"), "massa": float(a["massa_kg"]), "pos": [float(a.get(k, 0.0)) for k in ("x", "y", "z")]})
    m, pos, ligados, apoio, nota, extra = _constroi(esq, mats, qualidade_carbono, x_apoio, raio_ligacao, raio_motor, massas, True)
    s = Sistema(m)
    r = s.modos(n_modos)
    m0, _, _, _, _, _ = _constroi(esq, mats, qualidade_carbono, x_apoio, raio_ligacao, raio_motor, massas, False)
    r0 = Sistema(m0).modos(n_modos)
    modos = []
    for k, f in enumerate(r["f_hz"]):
        nat, part = _natureza(r["formas"][k], m, x_apoio, extra["ref"])
        me = _massa_efetiva(s, r["formas"][k])
        local = max(me) < 0.05 and nat != "torcao do boom"
        if local:
            nat = "local (tubo solto)"
        modos.append({"i": k + 1, "f_hz": float(f), "f_sem_massas_hz": float(r0["f_hz"][k]) if k < len(r0["f_hz"]) else None, "natureza": nat, "participacao": part,
                      "massa_efetiva": {"x": me[0], "y": me[1], "z": me[2]}, "local": bool(local)})
    total_pontos = sum(massas[k] for k in ("empenagem_h", "deriva")) + sum(q["massa"] for q in massas["pontuais"])
    if total_pontos <= 0:
        avisos.append("Nenhuma massa de empenagem, deriva ou adicional informada: so os tubos entram e as frequencias sao as do boom vazio (muito acima das reais).")
    saida = {"modos": modos, "massa_trelica_kg": float(m0.massa_total()), "massa_somada_kg": float(total_pontos), "massa_modelo_kg": float(m.massa_total()),
             "notas": nota, "x_apoio": x_apoio, "n_nos": len(m.nos), "n_barras": len(m.barras)}
    todos = [{"nome": f"cauda {md['i']} ({md['natureza']})", "f_hz": md["f_hz"], "natureza": md["natureza"]} for md in modos[:n_modos] if not md["local"]]
    if suporte_motor:
        sup = suporte_do_motor(esq, suporte_motor, massa_motor_kg, mats, qualidade_carbono)
        saida["suporte_motor"] = sup
        todos.append({"nome": "suporte do motor (balanco)", "f_hz": sup["f_hz"], "natureza": "flexao"})
        if massa_motor_kg <= 0:
            avisos.append("Suporte do motor sem massa do motor: informe a massa do conjunto.")
    elif massa_motor_kg > 0 and not any(q["nome"] == "motor" for q in massas["pontuais"]):
        avisos.append("Massa do motor informada sem a posicao e sem o suporte: ela nao entra em nenhum modo. Informe a posicao do motor ou o balanco do suporte.")
    for q in modos_externos or []:
        todos.append({"nome": q["nome"], "f_hz": float(q["f_hz"]), "natureza": q.get("natureza", "")})
    saida["campbell"] = campbell(rpm_min, rpm_max, int(n_pas), todos, ordens_extra)
    saida["ressonancias"] = ressonancias(rpm_min, rpm_max, int(n_pas), todos, ordens_extra, margem_min, rpm_v)
    saida["faixa_rpm"] = [float(rpm_min), float(rpm_max)]
    saida["n_pas"] = int(n_pas)
    saida["margem_min"] = float(margem_min)
    saida["avisos"] = avisos
    return saida
