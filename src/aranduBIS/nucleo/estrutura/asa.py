from __future__ import annotations

from .. import referencias as R

import numpy as np

from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from .materiais import propriedades
from . import longarinas as LG

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

def _mat(mats: dict, nome: str) -> dict:
    from .materiais import ALIAS
    return mats[ALIAS.get(nome, nome)]

def _parte(tipo, mats, mat, A, z, meia, I):
    return (tipo, _mat(mats, mat)["E"], A, z, meia, I, mat)

def secao(cfg: dict, x: np.ndarray, zs: np.ndarray, zi: np.ndarray, c: float, y: float, mats: dict) -> dict:
    lgs = [lg for lg in cfg.get("longarinas", []) if LG.ativa(lg, y)]
    if not cfg.get("longarinas"):
        raise ValueError("a asa nao declara longarina (estrutura.longarinas)")
    partes, avisos, almas, tubos_lg, celulas = [], [], [], [], []
    for lg in lgs:
        p = LG.primitivas(lg, x, zs, zi, c, y)
        if p.get("aviso"):
            avisos.append(p["aviso"])
        for a in p["almas"]:
            h = a["zt"] - a["zb"]
            if h > 0:
                partes.append(_parte("alma", mats, a["mat"], a["tw"] * h, 0.5 * (a["zt"] + a["zb"]), 0.5 * h, a["tw"] * h ** 3 / 12.0))
                almas.append({**a, "h": h})
        for t in p["tubos"]:
            A = 0.25 * np.pi * (t["de"] ** 2 - t["di"] ** 2)
            partes.append(_parte("tubo_meio", mats, t["mat"], A, t["z"], 0.5 * t["de"], np.pi / 64 * (t["de"] ** 4 - t["di"] ** 4)))
            tubos_lg.append({**t, "A": A})
        for m in p["mesas"]:
            b = m["x1"] - m["x0"]
            partes.append(_parte("mesa_" + m["lado"], mats, m["mat"], b * m["t"], m["z"], 0.5 * m["t"], b * m["t"] ** 3 / 12.0))
        if p.get("celula"):
            celulas.append({**p["celula"], "GJ": LG.gj_celula(p["celula"], mats)})
        for t in p["tubos"]:
            celulas.append({"x": t["x"], "GJ": LG.gj_tubo(t["de"], t["di"], _mat(mats, t["mat"])["G"])})
    frente = min(almas, key=lambda a: a["x"]) if almas else None
    if frente is not None:
        xs, tw, h = frente["x"], frente["tw"], frente["h"]
    else:
        xs = ES.posicao_x(lgs[0], c, y) if lgs else ES.posicao_x(cfg["longarinas"][0], c, y)
        tw, h = 0.0, (float(np.interp(xs / c, x, zs)) - float(np.interp(xs / c, x, zi))) * c
    for tb in cfg.get("tubos", []):
        if not LG.ativa(tb, y):
            continue
        de, di = float(tb["de"]), float(tb.get("di", 0.0))
        xt = ES.posicao_x(tb, c, y)
        lado = tb.get("lado", "extradorso"); sup = lado == "extradorso"
        z = 0.5 * float(np.interp(xt / c, x, zs) + np.interp(xt / c, x, zi)) * c if lado == "meio" else float(np.interp(xt / c, x, zs if sup else zi)) * c + (-0.5 * de if sup else 0.5 * de)
        mat = tb.get("material", "tubo_carbono")
        partes.append(_parte("tubo_meio" if lado == "meio" else "tubo_sup" if sup else "tubo_inf", mats, mat if LG_mat_ok(mats, mat) else "tubo_carbono",
                             0.25 * np.pi * (de * de - di * di), z, 0.5 * de, np.pi / 64 * (de ** 4 - di ** 4)))
        if h > 0 and de > h:
            avisos.append(f"y = {y:.2f} m: o tubo de {1000 * de:.1f} mm nao cabe na altura da longarina ({1000 * h:.1f} mm)")
    ch = cfg.get("chapeado")
    if ch:
        xe, ts = _fim_do_chapeado(ch, y), float(ch.get("espessura", 0.001))
        mat_ch = ch.get("material", "balsa") if LG_mat_ok(mats, ch.get("material", "balsa")) else "balsa"
        if xe > 0:
            for lado, z_ in (("pele_sup", zs), ("pele_inf", zi)):
                m = x <= xe
                xx, zz = np.append(x[m], xe), np.append(z_[m], np.interp(xe, x, z_))
                ds = np.hypot(np.diff(xx), np.diff(zz)) * c
                for a, z in zip(ds, 0.5 * (zz[1:] + zz[:-1]) * c):
                    partes.append(_parte(lado, mats, mat_ch, ts * a, z, 0.0, 0.0))
    EA = sum(p[1] * p[2] for p in partes)
    if EA <= 0:
        raise ValueError(f"secao sem material em y = {y:.2f} m")
    zna = sum(p[1] * p[2] * p[3] for p in partes) / EA
    EI = sum(p[1] * (p[2] * (p[3] - zna) ** 2 + p[5]) for p in partes)
    return {"EI": EI, "zna": zna, "h": h, "c": c, "tw": tw, "partes": partes, "avisos": avisos, "xe": _fim_do_chapeado(ch, y) if ch else 0.0,
            "xs_c": xs / c, "almas": almas, "tubos_longarina": tubos_lg, "celulas": celulas}

def LG_mat_ok(mats: dict, nome: str) -> bool:
    from .materiais import ALIAS
    return ALIAS.get(nome, nome) in mats

def _grupo(parte) -> str:
    tipo, mat = parte[0], parte[6]
    if tipo.startswith("pele"):
        return "pele"
    if mat in LG.CARBONO:
        return "tubo"
    return "mesa"

def _tensoes(sec: dict, M: float, V: float, mats: dict) -> tuple[dict, dict]:
    s, mg = {}, {}

    def poe(k, sig, adm):
        s[k] = max(s.get(k, 0.0), sig)
        mg[k] = min(mg.get(k, INF), _margem(adm, sig))
    for p in sec["partes"]:
        if p[0] == "alma":
            continue
        g, mp = _grupo(p), _mat(mats, p[6])
        for zf in {p[3] - p[4], p[3] + p[4]}:
            v = M * p[1] * (zf - sec["zna"]) / sec["EI"]
            if v > 0:
                poe(g + "_comp", v, mp["XC"])
            else:
                poe(g + "_tr", -v, mp["X"])
    k = [(_mat(mats, a["mat"])["G"] * a["h"] * a["tw"], "alma", a) for a in sec["almas"]]
    k += [(_mat(mats, t["mat"])["G"] * 0.5 * t["A"], "tubo", t) for t in sec["tubos_longarina"]]
    tot = sum(v[0] for v in k)
    for ki, qual, d in k:
        Vi = abs(V) * ki / tot if tot > 0 else 0.0
        if qual == "alma":
            poe("alma_cis", Vi / (d["h"] * d["tw"]), _mat(mats, d["mat"])["S"])
        else:
            poe("tubo_cis", 2.0 * Vi / d["A"], _mat(mats, d["mat"])["S"])
    return s, mg

def _margem(adm: float, atua: float) -> float:
    return INF if atua <= 1e-9 else min(INF, adm / atua - 1.0)

ITENS = ("tubo_comp", "tubo_tr", "mesa_comp", "mesa_tr", "pele_comp", "pele_tr", "alma_cis", "tubo_cis")

def verifica(esq: dict, nome: str, casos: list, mats: dict | None = None, fator_seguranca: float = R.FATOR_SEGURANCA,
             qualidade_balsa: float = 1.0, qualidade_carbono: float = 1.0, calib_EI: float = 1.0) -> dict:
    el = _elemento(esq, nome)
    cfg = el.get("estrutura") or {}
    if not cfg:
        raise ValueError(f"a asa {nome!r} nao declara estrutura")
    from .materiais import ALIAS
    nomes = {ALIAS.get(k, k) for k in LG.materiais(cfg) | {"balsa", "tubo_carbono"}}
    m = {k: propriedades(k, esq, mats, qualidade_balsa, qualidade_carbono) for k in sorted(nomes)}
    sec_el, x, Z = _perfis(el, esq)
    lados = [next(s for s in c["superficies"] if s["nome"] == nome)["lados"] for c in casos]
    y = np.array(lados[0].get("dir", lados[0].get("esq"))["y"])
    estacoes = []
    for yy in y:
        q = AG._secao_em(sec_el, float(yy)); i, t = AG._no_vao(sec_el, float(yy))
        zs, zi = (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]
        estacoes.append(secao(cfg, x, zs, zi, float(q[3]), float(yy), m))
    avisos = sorted({a for e in estacoes for a in e["avisos"]})
    EI = calib_EI * np.array([e["EI"] for e in estacoes])
    saida_casos, pior, presentes, adm = [], None, set(), {}
    for c, lado in zip(casos, lados):
        L = lado.get("dir") or lado.get("esq")
        M, V = np.array(L["fletor"]), np.array(L["cortante"])
        res = [_tensoes(e, fator_seguranca * mj, fator_seguranca * vj, m) for e, mj, vj in zip(estacoes, M, V)]
        for t_, mg_ in res:
            presentes |= set(mg_)
            for k_, v_ in t_.items():
                if v_ > 1e-9 and mg_[k_] < INF:
                    adm[k_] = min(adm.get(k_, float("inf")), v_ * (1.0 + mg_[k_]))
        marg = {k: [r[1].get(k, INF) for r in res] for k in ITENS}
        minimos = {k: {"margem": float(min(v)), "y": float(y[int(np.argmin(v))])} for k, v in marg.items()}
        yy = np.concatenate([[0.0], y]); kap = np.concatenate([[M[0] / EI[0]], M / EI])
        theta = np.concatenate([[0.0], np.cumsum(0.5 * (kap[1:] + kap[:-1]) * np.diff(yy))])
        w = np.concatenate([[0.0], np.cumsum(0.5 * (theta[1:] + theta[:-1]) * np.diff(yy))])
        d = {"caso": c["nome"], "margens": marg, "minimos": minimos, "tensao_MPa": {k: [r[0].get(k, 0.0) / 1e6 for r in res] for k in ITENS},
             "flecha": w[1:].tolist(), "flecha_ponta_m": float(w[-1]), "flecha_pct": float(100 * w[-1] / y[-1])}
        saida_casos.append(d)
        k_pior = min(minimos, key=lambda k: minimos[k]["margem"])
        if pior is None or minimos[k_pior]["margem"] < pior["margem"]:
            pior = {"caso": c["nome"], "item": k_pior, "margem": minimos[k_pior]["margem"], "y": minimos[k_pior]["y"]}
    itens = [k for k in ITENS if k in presentes]
    adm_ref = _admissiveis_ref(cfg, m)
    flecha_max = max(saida_casos, key=lambda d: d["flecha_ponta_m"])
    return {"nome": nome, "y": y.tolist(), "itens": itens, "admissiveis_MPa": {k: adm.get(k, adm_ref.get(k, 0.0)) / 1e6 for k in ITENS},
            "materiais": {k: {kk: vv for kk, vv in v.items() if kk != "fonte"} for k, v in m.items()},
            "fontes": {k: v["fonte"] for k, v in m.items()},
            "longarinas": [LG.tipo(lg) for lg in cfg.get("longarinas", [])],
            "estacoes": {"EI": EI.tolist(), "h": [e["h"] for e in estacoes], "tw": [e["tw"] for e in estacoes], "c": [e["c"] for e in estacoes],
                         "x_longarina_c": [e["xs_c"] for e in estacoes], "x_chapeado_c": [e["xe"] for e in estacoes]},
            "casos": saida_casos, "critico": pior, "flecha_max_pct": flecha_max["flecha_pct"], "flecha_max_caso": flecha_max["caso"],
            "fator_seguranca": fator_seguranca, "avisos": avisos}

def _admissiveis_ref(cfg: dict, m: dict) -> dict:
    c, b = m["tubo_carbono"], m["balsa"]
    mesa = next((LG._p(lg, "material_mesa", LG.PADRAO_CAIXAO) for lg in cfg.get("longarinas", []) if LG.tipo(lg) == "caixao"), "balsa")
    mm = _mat(m, mesa) if LG_mat_ok(m, mesa) else b
    alma = next((a for lg in cfg.get("longarinas", []) for a in [lg.get("material") if LG.tipo(lg) == "alma" else
                 LG._p(lg, "material_alma", LG.PADRAO_CAIXAO) if LG.tipo(lg) == "caixao" else None] if a), "balsa")
    ma = _mat(m, alma) if LG_mat_ok(m, alma) else b
    return {"tubo_comp": c["XC"], "tubo_tr": c["X"], "mesa_comp": mm["XC"], "mesa_tr": mm["X"], "pele_comp": b["XC"], "pele_tr": b["X"],
            "alma_cis": ma["S"], "tubo_cis": c["S"]}

def PADRAO_FONTE(nome: str) -> str:
    from .materiais import PADRAO
    return PADRAO[nome]["fonte"]
