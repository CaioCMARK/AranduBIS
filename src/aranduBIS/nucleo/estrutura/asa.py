from __future__ import annotations

import numpy as np

from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from .materiais import propriedades

INF = 999.0

def _elemento(esq: dict, nome: str) -> dict:
    for e in esq.get("elementos", []):
        if e.get("nome") == nome and e.get("tipo") == "asa":
            return e
    raise ValueError(f"asa {nome!r} nao esta no modelo")

def _perfis(el: dict, esq: dict):
    sec = AG._secoes(el)
    if AG._quer_aneis(el):
        x, Z = AG._perfis_secoes(el, esq)
    else:
        x, zs, zi = ES.perfil_xy(el.get("perfil", "NACA 0012"), int(el.get("n_perfil", 40)), esq.get("_pasta", "."))
        Z = [(zs, zi)] * len(sec)
    return sec, x, Z

def _fim_do_chapeado(ch: dict, y: float) -> float:
    pares = ch.get("ate_xc_y")
    if pares:
        pares = sorted((abs(float(a)), float(b)) for a, b in pares)
        return float(np.interp(abs(y), [p[0] for p in pares], [p[1] for p in pares]))
    return float(ch.get("ate_xc", 0.25))

def secao(cfg: dict, x: np.ndarray, zs: np.ndarray, zi: np.ndarray, c: float, y: float, mats: dict) -> dict:
    lg = (cfg.get("longarinas") or [None])[0]
    if lg is None:
        raise ValueError("a asa nao declara longarina (estrutura.longarinas)")
    xs = ES.posicao_x(lg, c, y)
    tw = float(lg.get("largura", 0.00238))
    zu, zl = float(np.interp(xs / c, x, zs)) * c, float(np.interp(xs / c, x, zi)) * c
    h = zu - zl
    E_b = mats["balsa"]["E"]
    partes = []
    I0 = 0.0
    if h > 0:
        partes.append(("alma", E_b, tw * h, 0.5 * (zu + zl)))
        I0 += E_b * tw * h ** 3 / 12.0
    avisos = []
    for tb in cfg.get("tubos", []):
        y0, y1 = tb.get("y") or (-1e9, 1e9)
        if not (min(y0, y1) - 1e-9 <= y <= max(y0, y1) + 1e-9):
            continue
        de, di = float(tb["de"]), float(tb.get("di", 0.0))
        xt = ES.posicao_x(tb, c, y)
        lado = tb.get("lado", "extradorso"); sup = lado == "extradorso"
        z = 0.5 * float(np.interp(xt / c, x, zs) + np.interp(xt / c, x, zi)) * c if lado == "meio" else float(np.interp(xt / c, x, zs if sup else zi)) * c + (-0.5 * de if sup else 0.5 * de)
        mt = mats[tb.get("material", "tubo_carbono")] if tb.get("material", "tubo_carbono") in mats else mats["tubo_carbono"]
        partes.append(("tubo_sup" if sup else "tubo_inf", mt["E"], 0.25 * np.pi * (de * de - di * di), z))
        if h > 0 and de > h:
            avisos.append(f"y = {y:.2f} m: o tubo de {1000 * de:.1f} mm nao cabe na altura da longarina ({1000 * h:.1f} mm)")
    ch = cfg.get("chapeado")
    if ch:
        xe, ts = _fim_do_chapeado(ch, y), float(ch.get("espessura", 0.001))
        if xe > 0:
            for lado, z_ in (("pele_sup", zs), ("pele_inf", zi)):
                m = x <= xe
                xx, zz = np.append(x[m], xe), np.append(z_[m], np.interp(xe, x, z_))
                ds = np.hypot(np.diff(xx), np.diff(zz)) * c
                for a, z in zip(ds, 0.5 * (zz[1:] + zz[:-1]) * c):
                    partes.append((lado, E_b, ts * a, z))
    EA = sum(p[1] * p[2] for p in partes)
    if EA <= 0:
        raise ValueError(f"secao sem material em y = {y:.2f} m")
    zna = sum(p[1] * p[2] * p[3] for p in partes) / EA
    EI = sum(p[1] * p[2] * (p[3] - zna) ** 2 for p in partes) + I0
    return {"EI": EI, "zna": zna, "h": h, "c": c, "tw": tw, "partes": partes, "avisos": avisos, "xe": _fim_do_chapeado(ch, y) if ch else 0.0,
            "xs_c": xs / c}

def _tensoes(sec: dict, M: float, V: float, mats: dict) -> dict:
    s = {"tubo_comp": 0.0, "tubo_tr": 0.0, "pele_comp": 0.0, "pele_tr": 0.0}
    for tipo, E, A, z in sec["partes"]:
        if tipo == "alma":
            continue
        v = M * E * (z - sec["zna"]) / sec["EI"]
        grupo = "tubo" if tipo.startswith("tubo") else "pele"
        k = grupo + ("_comp" if v > 0 else "_tr")
        s[k] = max(s[k], abs(v))
    s["alma_cis"] = abs(V) / (sec["h"] * sec["tw"]) if sec["h"] > 0 else 0.0
    return s

def _margem(adm: float, atua: float) -> float:
    return INF if atua <= 1e-9 else min(INF, adm / atua - 1.0)

def verifica(esq: dict, nome: str, casos: list, mats: dict | None = None, fator_seguranca: float = 1.2,
             qualidade_balsa: float = 1.0, qualidade_carbono: float = 1.0) -> dict:
    el = _elemento(esq, nome)
    cfg = el.get("estrutura") or {}
    if not cfg:
        raise ValueError(f"a asa {nome!r} nao declara estrutura")
    m = {k: propriedades(k, esq, mats, qualidade_balsa, qualidade_carbono) for k in ("balsa", "tubo_carbono")}
    sec_el, x, Z = _perfis(el, esq)
    lados = [next(s for s in c["superficies"] if s["nome"] == nome)["lados"] for c in casos]
    y = np.array(lados[0].get("dir", lados[0].get("esq"))["y"])
    estacoes = []
    for yy in y:
        q = AG._secao_em(sec_el, float(yy)); i, t = AG._no_vao(sec_el, float(yy))
        zs, zi = (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]
        estacoes.append(secao(cfg, x, zs, zi, float(q[3]), float(yy), m))
    avisos = sorted({a for e in estacoes for a in e["avisos"]})
    itens = ("tubo_comp", "tubo_tr", "pele_comp", "pele_tr", "alma_cis")
    adm = {"tubo_comp": m["tubo_carbono"]["XC"], "tubo_tr": m["tubo_carbono"]["X"], "pele_comp": m["balsa"]["XC"],
           "pele_tr": m["balsa"]["X"], "alma_cis": m["balsa"]["S"]}
    EI = np.array([e["EI"] for e in estacoes])
    saida_casos, pior = [], None
    for c, lado in zip(casos, lados):
        L = lado.get("dir") or lado.get("esq")
        M, V = np.array(L["fletor"]), np.array(L["cortante"])
        tens = [_tensoes(e, fator_seguranca * mj, fator_seguranca * vj, m) for e, mj, vj in zip(estacoes, M, V)]
        marg = {k: [_margem(adm[k], t[k]) for t in tens] for k in itens}
        minimos = {k: {"margem": float(min(v)), "y": float(y[int(np.argmin(v))])} for k, v in marg.items()}
        yy = np.concatenate([[0.0], y]); kap = np.concatenate([[M[0] / EI[0]], M / EI])
        theta = np.concatenate([[0.0], np.cumsum(0.5 * (kap[1:] + kap[:-1]) * np.diff(yy))])
        w = np.concatenate([[0.0], np.cumsum(0.5 * (theta[1:] + theta[:-1]) * np.diff(yy))])
        d = {"caso": c["nome"], "margens": marg, "minimos": minimos, "tensao_MPa": {k: [t[k] / 1e6 for t in tens] for k in itens},
             "flecha": w[1:].tolist(), "flecha_ponta_m": float(w[-1]), "flecha_pct": float(100 * w[-1] / y[-1])}
        saida_casos.append(d)
        k_pior = min(minimos, key=lambda k: minimos[k]["margem"])
        if pior is None or minimos[k_pior]["margem"] < pior["margem"]:
            pior = {"caso": c["nome"], "item": k_pior, "margem": minimos[k_pior]["margem"], "y": minimos[k_pior]["y"]}
    flecha_max = max(saida_casos, key=lambda d: d["flecha_ponta_m"])
    return {"nome": nome, "y": y.tolist(), "admissiveis_MPa": {k: v / 1e6 for k, v in adm.items()},
            "materiais": {k: {kk: vv for kk, vv in v.items() if kk != "fonte"} for k, v in m.items()},
            "fontes": {k: PADRAO_FONTE(k) for k in m},
            "estacoes": {"EI": EI.tolist(), "h": [e["h"] for e in estacoes], "c": [e["c"] for e in estacoes],
                         "x_longarina_c": [e["xs_c"] for e in estacoes], "x_chapeado_c": [e["xe"] for e in estacoes]},
            "casos": saida_casos, "critico": pior, "flecha_max_pct": flecha_max["flecha_pct"], "flecha_max_caso": flecha_max["caso"],
            "fator_seguranca": fator_seguranca, "avisos": avisos}

def PADRAO_FONTE(nome: str) -> str:
    from .materiais import PADRAO
    return PADRAO[nome]["fonte"]
