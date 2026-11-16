from __future__ import annotations

import numpy as np

from .. import referencias as R
from ..fe import Sistema
from ..modelador import aeronave_geometria as AG
from . import cauda as CA
from . import torcao as TO
from .asa import INF

E0 = 1e9
CORDAL = 100.0
X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
GRAUS = {"solda": (), "rotula": (X, Y, Z), "parafuso:x": (X,), "parafuso:y": (Y,), "parafuso:z": (Z,)}
ROTULO = {"solda": "solda (engaste)", "rotula": "rotula", "parafuso:x": "parafuso no eixo x", "parafuso:y": "parafuso no eixo y", "parafuso:z": "parafuso no eixo z"}
NO_ASA = 500000

def _eixo_da_asa(esq, nome, an):
    from .asa import _elemento
    el = _elemento(esq, nome)
    if abs(float(el.get("rolagem", 0.0) or 0.0)) > 1e-6 or abs(float(el.get("arfagem", 0.0) or 0.0)) > 1e-6 or abs(float(el.get("guinada", 0.0) or 0.0)) > 1e-6:
        raise ValueError(f"a asa {nome!r} tem rotacao (rolagem, arfagem ou guinada): a comparacao de juncoes so trata asas sem rotacao")
    sec = AG._secoes(el); pos = np.asarray(el.get("posicao", [0, 0, 0]), float)
    y_min = min(s[1] for s in sec)
    simetrica = y_min < -1e-9
    y, c, ea = np.array(an["y"]), np.array(an["c"]), np.array(an["ea_c"])
    def ponto(yy, k):
        q = AG._secao_em(sec, float(yy))
        return np.array([pos[0] + q[0] + ea[k] * c[k], pos[1] + yy, pos[2] + q[2]])
    return el, y, simetrica, ponto

def _ligacoes(m, pos, nome, P_eixo, raio):
    decl = [l for l in m.ligacoes if l["tipo"] == "ligacao" and l.get("alvo") == nome]
    if decl:
        return sorted({l["no"] for l in decl}), True
    d = np.array([[np.linalg.norm(p - q) for q in P_eixo] for p in pos])
    dmin = d.min(axis=1)
    cand = [i + 1 for i in np.argsort(dmin) if dmin[i] <= raio]
    return sorted(cand[:8]), False

def _estacoes(y, simetrica, y_lig):
    base = set(np.round(y, 9))
    if simetrica:
        base |= {-v for v in base}
    lim = max(base)
    for v in y_lig:
        base.add(round(float(np.clip(v, -lim if simetrica else min(base), lim)), 9))
    return np.array(sorted(base))

def _monta(esq, nome, an, caso, tipo, mats, qualidade_carbono, x_apoio, raio):
    m, pos, info, avisos = CA.monta(esq, mats, qualidade_carbono)
    apoio, explicito = CA.aplica_apoios(m, x_apoio, avisos)
    el, y, simetrica, ponto = _eixo_da_asa(esq, nome, an)
    EI, GJ = np.array(an["EI"]), np.array(an["GJ"])
    P0 = [ponto(v, k) for k, v in enumerate(y)] + ([ponto(-v, k) for k, v in enumerate(y)] if simetrica else [])
    nos_lig, declaradas = _ligacoes(m, pos, nome, P0, raio)
    if not nos_lig:
        raise ValueError(f"nenhum no da trelica a menos de {1000 * raio:.0f} mm da longarina de {nome!r}: declare a ligacao num no da trelica (aba de nos, coluna 'liga a')")
    pos_asa = float(np.asarray(el.get("posicao", [0, 0, 0]), float)[1])
    ys = _estacoes(y, simetrica, [pos[n - 1][1] - pos_asa for n in nos_lig])
    interp = lambda arr, yy: float(np.interp(abs(yy), y, arr))
    k_de = lambda yy: int(np.argmin(np.abs(y - abs(yy))))
    P = np.array([[*ponto(v, k_de(v))] for v in ys])
    P[:, 0] = [float(np.interp(abs(v), y, [ponto(q, k)[0] for k, q in enumerate(y)])) for v in ys]
    P[:, 2] = [float(np.interp(abs(v), y, [ponto(q, k)[2] for k, q in enumerate(y)])) for v in ys]
    m.material(900, E0, E0, rho=0.0)
    for i, p in enumerate(P):
        m.no(NO_ASA + i, *p)
    eid_asa = []
    for i in range(len(ys) - 1):
        ym = 0.5 * (ys[i] + ys[i + 1])
        k, j = interp(EI, ym) / E0, interp(GJ, ym) / E0
        m.prop(9000 + i, 900, 1e-3, k, CORDAL * k, j)
        m.barra(900000 + i, 9000 + i, NO_ASA + i, NO_ASA + i + 1, (0.0, 0.0, 1.0))
        eid_asa.append(900000 + i)
    pares = []
    for n in nos_lig:
        i = int(np.argmin(np.abs(ys - (pos[n - 1][1] - pos_asa))))
        pares.append((n, i))
        d = P[i] - pos[n - 1]; L = float(np.linalg.norm(d))
        if L < 1e-3:
            m.rigido(800000 + len(pares), NO_ASA + i, [n])
            continue
        ki = 50.0 * float(EI.max()) / E0
        m.prop(8000 + len(pares), 900, 1e-3, ki, ki, ki)
        m.barra(800000 + len(pares), 8000 + len(pares), n, NO_ASA + i, CA._orienta(d))
        if GRAUS[tipo]:
            m.libera(800000 + len(pares), 0, GRAUS[tipo])
    yq, q = np.asarray(caso["y"], float), np.asarray(caso["liquida_por_m"], float)
    if yq[-1] < y[-1] - 1e-9:
        yq, q = np.append(yq, y[-1]), np.append(q, 0.0)
    qs = np.interp(np.abs(ys), yq, q)
    w = np.zeros(len(ys)); dy = np.diff(ys)
    w[:-1] += 0.5 * dy; w[1:] += 0.5 * dy
    for i in range(len(ys)):
        m.carga(1, NO_ASA + i, [0.0, 0.0, qs[i] * w[i], 0.0, 0.0, 0.0])
    return m, pos, info, avisos, ys, P, pares, eid_asa, apoio, explicito, declaradas, float((qs * w).sum())

def _variante(esq, nome, an, caso, tipo, mats, qualidade_carbono, x_apoio, raio, fator_seguranca, K_flambagem):
    m, pos, info, avisos, ys, P, pares, eid_asa, apoio, explicito, declaradas, forca = _monta(esq, nome, an, caso, tipo, mats, qualidade_carbono, x_apoio, raio)
    S = Sistema(m)
    r = S.estatica(1)
    u = np.array([r["u"][NO_ASA + i] for i in range(len(ys))])
    ref = float(np.mean([u[i][2] for _, i in pares]))
    wz = u[:, 2] - ref
    M = np.zeros(len(ys))
    for i, eid in enumerate(eid_asa):
        f = r["esforcos"][eid]
        ma, mb = float(abs(f[5])), float(abs(f[11]))
        M[i] = max(M[i], ma); M[i + 1] = max(M[i + 1], mb)
    ligs = []
    for i in sorted({q[1] for q in pares}):
        n = [q[0] for q in pares if q[1] == i]
        tot = np.zeros(3)
        for k, eid in enumerate(eid_asa):
            f = r["esforcos"][eid]
            loc = next(t for t in S.locais if t[0] == eid)
            Rm = loc[2][:3, :3]
            if k == i:
                tot += Rm.T @ f[3:6]
            if k + 1 == i:
                tot += Rm.T @ f[9:12]
        ligs.append({"nos": [int(q) for q in n], "y": float(ys[i]), "momento_Nm": float(np.linalg.norm(tot)), "momento_xyz": [float(v) for v in tot],
                     "flexao_Nm": float(abs(tot[0])), "engastado": all(q in set(apoio) for q in n)})
    grupos = CA._grupos(m)
    ligados = {n for g in grupos if any(a in g for a in apoio) for n in g}
    barras = [(eid, pid, ga, gb) for eid, pid, ga, gb, _ in m.barras if eid in info]
    lista = CA.margens_barras({e: r["esforcos"][e] for e, *_ in barras}, barras, info, pos, ligados, esq, mats, qualidade_carbono, fator_seguranca, K_flambagem, {})
    uteis = [b for b in lista if not b["curta"]] or lista
    pior = min(uteis, key=lambda b: b["margem"]) if uteis else None
    return {"tipo": tipo, "rotulo": ROTULO[tipo], "y": ys.tolist(), "w_mm": (1000 * wz).tolist(), "fletor_Nm": M.tolist(),
            "flecha_ponta_mm": float(1000 * max(abs(wz[0]), abs(wz[-1]))), "fletor_max_Nm": float(M.max()),
            "fletor_na_ligacao_Nm": float(max(M[i] for _, i in pares)), "ligacoes": ligs,
            "momento_transmitido_Nm": float(max(l["momento_Nm"] for l in ligs)),
            "margem_trelica": None if pior is None else float(min(pior["margem"], 99.0)),
            "barra_critica": None if pior is None else {"id": pior["id"], "elemento": pior["elemento"], "modo": pior["modo"]},
            "flexao_transmitida_Nm": float(max(l["flexao_Nm"] for l in ligs)), "forca_N": forca,
            "_meta": {"avisos": avisos, "explicito": explicito, "declaradas": declaradas, "n_lig": len(pares), "todos_engastados": all(l["engastado"] for l in ligs)}}

def analisa(esq: dict, nome: str, caso: dict, mats: dict | None = None, tipos=("solda", "parafuso:x", "rotula"), x_apoio: float = 0.30,
            raio_ligacao: float = 0.06, qualidade_carbono: float = 1.0, fator_seguranca: float = R.FATOR_SEGURANCA, K_flambagem: float = 1.0,
            Vd: float | None = None, **kw) -> dict:
    an = TO.analisa(esq, nome, mats=mats, Vd=Vd, **kw)
    variantes, avisos = [], []
    for tipo in tipos:
        if tipo not in GRAUS:
            raise ValueError(f"tipo de juncao desconhecido: {tipo!r}")
        try:
            v = _variante(esq, nome, an, caso, tipo, mats, qualidade_carbono, x_apoio, raio_ligacao, fator_seguranca, K_flambagem)
        except ValueError as x:
            if "mecanismo" in str(x) or "singular" in str(x):
                variantes.append({"tipo": tipo, "rotulo": ROTULO[tipo], "mecanismo": True})
                avisos.append(f"Com {ROTULO[tipo]} a asa vira mecanismo: os pontos de ligacao nao bastam para segura-la (falta um segundo ponto ou uma junta rigida).")
                continue
            raise
        meta = v.pop("_meta")
        variantes.append(v)
    validas = [v for v in variantes if not v.get("mecanismo")]
    if not validas:
        raise ValueError("nenhuma das juncoes testadas segura a asa: declare mais pontos de ligacao")
    avisos += [a for a in meta["avisos"] if a not in avisos]
    if not meta["declaradas"]:
        avisos.append(f"Nenhuma ligacao declarada com {nome}: foram usados os {meta['n_lig']} nos da trelica a menos de {1000 * raio_ligacao:.0f} mm da longarina. Declare as ligacoes para controlar isso.")
    if meta["todos_engastados"]:
        avisos.append("Todos os nos de ligacao estao no apoio da trelica (engastados): a comparacao mostra o efeito na asa, mas a trelica nao se deforma. Declare os apoios em outros nos para ver o efeito nela.")
    avisos.append("A carga entra na linha elastica (sem momento de torcao) e a asa e uma viga com o EI e o GJ da aba Asa; a ligacao e pontual.")
    base = next((v for v in validas if v["tipo"] == "solda"), validas[0])
    for v in validas:
        v["delta"] = {k: (None if not base[k] else float(v[k] / base[k] - 1.0)) for k in ("flecha_ponta_mm", "fletor_na_ligacao_Nm", "momento_transmitido_Nm", "flexao_transmitida_Nm")}
    return {"asa": nome, "variantes": variantes, "referencia": base["tipo"], "avisos": avisos, "n_ligacoes": meta["n_lig"], "declaradas": meta["declaradas"]}
