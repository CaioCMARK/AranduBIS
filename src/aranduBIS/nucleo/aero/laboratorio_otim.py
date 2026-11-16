from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

from ..otimiza import problema as P
from ..otimiza.problema import _escala_no
from . import laboratorio as L

RAIZ = Path(__file__).resolve().parents[4]
GENERICO = RAIZ / "cases" / "geometria" / "generico"
SIS = RAIZ / "cases" / "otimiza" / "massas_sistema_convencional.json"
REGRA = RAIZ / "cases" / "regras" / "sae2026_regular.json"
DENS_CASCA = 0.45
Cn_MIN = 0.03
VARRE_EXT_MAX = 30.0
VARRE_INT_MAX = 50.0
COMP_SUP_MAX = 1.6



def _spec(nome, fabrica, principais, comando, tipo, extras, motor_x, secundarias=(), prende=None, duto=False, T0=45.0, V0=28.0, ai0=0.0):
    return dict(nome=nome, fabrica=fabrica, principais=principais, secundarias=secundarias, comando=comando, tipo=tipo, extras=extras,
                motor_x=motor_x, prende=prende or {}, duto=duto, T0=T0, V0=V0, ai0=ai0)


def _com_deriva_central(fabrica, x_deriva: float, z: float = 0.0):
    def f():
        e = fabrica()
        d = copy.deepcopy(next(el for el in L.asa_com_cauda_convencional()["elementos"] if el["nome"] == "deriva"))
        d["posicao"] = [x_deriva, 0.0, z]
        e["elementos"].append(d)
        return e
    return f


def _especificacoes() -> dict:
    sw = ("sw", 0.4, 1.6, 1.0)
    kh = ("kh", 0.5, 2.5, 1.0)
    return {
        "monoplano_cauda": _spec("monoplano_cauda", L.asa_com_cauda_convencional, ["asa"], "empenagem_h", "inteira",
                                 [("kt", 0.5, 1.8, 1.0), ("lt", 0.6, 1.6, 1.0), kh], -0.25, secundarias=("empenagem_h",)),
        "asa_voadora_pontas": _spec("asa_voadora_pontas", lambda: L.vertical_nas_pontas(0.30, L.WASHOUT), ["asa"], "asa", "flape",
                                    [sw, kh], 1.0, prende={"deriva_esq": "asa", "deriva_dir": "asa"}),
        "asa_voadora_central": _spec("asa_voadora_central", lambda: L.vertical_central(0.40, L.WASHOUT), ["asa"], "asa", "flape",
                                     [sw, kh, ("lt", 0.6, 2.2, 1.0)], 1.0),
        "burgess_dunne": _spec("burgess_dunne", lambda: L.burgess_dunne(L.WASHOUT), ["asa_inferior", "asa_superior"], "asa_inferior", "flape",
                               [sw, ("st", 0.0, 2.0, 1.0), ("gp", 0.6, 1.6, 1.0), kh], 1.0, prende={"deriva_esq": "asa_inferior", "deriva_dir": "asa_inferior"}),
        "bwb": _spec("bwb", lambda: L.bwb(L.WASHOUT), ["asa"], "asa", "flape", [sw, kh], 1.0, prende={"deriva_esq": "asa", "deriva_dir": "asa"}),
        "bwb_canard": _spec("bwb_canard", lambda: L.bwb(1.0, com_canard=True), ["asa"], "canard", "inteira",
                            [sw, kh, ("kt", 0.5, 2.0, 1.0), ("lt", 0.6, 1.6, 1.0)], 1.0, secundarias=("canard",), prende={"deriva_esq": "asa", "deriva_dir": "asa"}),
        "asa_em_caixa": _spec("asa_em_caixa", _com_deriva_central(L.asa_em_caixa, 0.50), ["asa_frente", "asa_tras"], "asa_tras", "inteira",
                              [("st", 0.0, 2.0, 1.0), ("gp", 0.6, 1.6, 1.0), ("kt", 0.6, 1.5, 1.0), kh], -0.25, secundarias=("asa_tras",)),
        "tandem": _spec("tandem", _com_deriva_central(L.tandem, 0.85), ["asa_frente", "asa_tras"], "asa_tras", "inteira",
                        [("lt", 0.6, 1.8, 1.0), ("kt", 0.6, 1.5, 1.0), kh], -0.25, secundarias=("asa_tras",)),
        "duto_na_cauda": _spec("duto_na_cauda", _com_deriva_central(L.asa_com_duto_na_cauda, 0.65), ["asa"], "asa", "flape", [("lt", 0.6, 1.6, 1.0), kh], 1.0, duto=True,
                               T0=26.8, V0=25.0),
    }


NOMES = tuple(_especificacoes())



def _elementos(esq, nomes):
    return [e for e in esq["elementos"] if e.get("nome") in nomes]


def _semi(el) -> float:
    return max(abs(float(s["y"])) for s in el["secoes"])


def estrutura_de_referencia() -> tuple[dict, dict]:
    ref = json.loads((GENERICO / "asa_canard.json").read_text(encoding="utf8"))
    asa = next(e for e in ref["elementos"] if e["nome"] == "asa")
    return copy.deepcopy(asa["estrutura"]), copy.deepcopy(asa["entelagem"])


def com_estrutura(esq: dict, nomes) -> dict:
    est0, ent0 = estrutura_de_referencia()
    e = copy.deepcopy(esq)
    for el in _elementos(e, nomes):
        k = _semi(el) / 1.2
        est = copy.deepcopy(est0)
        _escala_no(est, k)
        el["estrutura"], el["entelagem"] = est, copy.deepcopy(ent0)
        el.pop("controles", None)
    return e


def _fins_e_duto(esq):
    return [el for el in esq["elementos"] if el.get("tipo") == "asa" and (el["nome"].startswith("deriva") or el["nome"].startswith("duto"))]


def _area(el) -> float:
    s = el["secoes"]
    return sum(0.5 * (s[i]["corda"] + s[i + 1]["corda"]) * abs(s[i + 1]["y"] - s[i]["y"]) for i in range(len(s) - 1))


def _prende_derivas(esq, mapa: dict):
    for nome, asa_nome in mapa.items():
        f = next((e for e in esq["elementos"] if e["nome"] == nome), None)
        a = next((e for e in esq["elementos"] if e["nome"] == asa_nome), None)
        if f is None or a is None:
            continue
        pontas = sorted(a["secoes"], key=lambda s: abs(s["y"]))[-1]
        pontas = {**{"xle": 0.0, "zle": 0.0}, **pontas}
        lado = 1.0 if f["posicao"][1] >= 0 else -1.0
        razao = f["secoes"][1]["corda"] / f["secoes"][0]["corda"]
        f["posicao"] = [a["posicao"][0] + pontas["xle"], lado * abs(pontas["y"]) + a["posicao"][1], a["posicao"][2] + pontas["zle"]]
        f["secoes"][0].update(xle=0.0, corda=pontas["corda"])
        f["secoes"][1]["corda"] = pontas["corda"] * razao


def transforma(esq: dict, spec: dict, x: dict) -> dict:
    e = copy.deepcopy(esq)
    sy, kc = x["b"] / 2.4, x["kc"]
    sw, kh, lt, kt, st, gp = (x.get(k, 1.0) for k in ("sw", "kh", "lt", "kt", "st", "gp"))
    for el in e["elementos"]:
        nome = el["nome"]
        if el.get("tipo") != "asa":
            continue
        ehduto = nome.startswith("duto")
        efin = nome.startswith("deriva")
        sec = el["secoes"]
        if nome in spec["principais"] and sw != 1.0:
            for s in sec:
                s["xle"] *= sw
        if efin and kh != 1.0:
            for s in sec:
                s["y"] *= kh
        if nome in spec["principais"]:
            semi = _semi(el)
            for s in sec:
                s["ainc"] = spec["ai0"] + x["ai"] + x["wo"] * (1.0 - abs(s["y"]) / semi) if spec["tipo"] == "flape" or nome == "asa" else s["ainc"] + x["ai"]
        if nome in spec["secundarias"] and kt != 1.0:
            f = math.sqrt(kt)
            for s in sec:
                s["y"] *= f
                s["corda"] *= f
        if ehduto:
            pass
        else:
            for s in sec:
                s["y"] *= sy
                s["xle"] *= kc
                if "zle" in s:
                    s["zle"] *= sy
                s["corda"] *= kc
            p = el["posicao"]
            el["posicao"] = [p[0] * (kc if nome in spec["principais"] else 1.0), p[1] * sy, p[2] * sy]
            for parte in ("estrutura", "controles"):
                if el.get(parte):
                    _escala_no(el[parte], sy * (math.sqrt(kt) if nome in spec["secundarias"] else 1.0) * (kh if efin else 1.0))
    por_nome = {el["nome"]: el for el in e["elementos"]}
    if lt != 1.0:
        for n in spec["secundarias"] + (("deriva",) if "deriva" in por_nome and "empenagem_h" in por_nome else ()):
            if n in por_nome:
                por_nome[n]["posicao"][0] *= lt
        if spec["duto"]:
            for el in e["elementos"]:
                if el["nome"].startswith("duto"):
                    el["posicao"][0] *= lt
        if "deriva" in por_nome and spec["nome"] in ("asa_voadora_central", "asa_em_caixa", "tandem", "duto_na_cauda"):
            por_nome["deriva"]["posicao"][0] *= lt
    if st != 1.0 or gp != 1.0:
        tras = por_nome.get("asa_superior") or por_nome.get("asa_tras")
        if tras is not None:
            tras["posicao"][0] *= st
            tras["posicao"][2] *= gp
            if spec["nome"] == "asa_em_caixa" and "deriva" in por_nome:
                por_nome["deriva"]["posicao"][0] = tras["posicao"][0] + 0.15 * kc
    _prende_derivas(e, spec["prende"])
    for el in e["elementos"]:
        if el.get("estrutura"):
            _gruda_pontas(el)
    return e


def _gruda_pontas(el) -> None:
    semi = _semi(el)
    for tb in el["estrutura"].get("tubos", []):
        if tb.get("y"):
            tb["y"] = [math.copysign(semi, v) if abs(abs(v) - semi) < 1e-6 * semi else v for v in tb["y"]]


def _extremos_x(esq) -> tuple[float, float]:
    lo, hi = math.inf, -math.inf
    for el in esq["elementos"]:
        if el.get("tipo") != "asa":
            continue
        for s in el["secoes"]:
            lo = min(lo, el["posicao"][0] + s["xle"]) if not el["nome"].startswith("duto") else lo
            hi = max(hi, el["posicao"][0] + s["xle"] + s["corda"])
    return lo, hi



def _massas(esq, spec, x_lo, L_x):
    sis = json.loads(SIS.read_text(encoding="utf8"))
    massas = [m for m in sis["massas"] if m["nome"] != "servo_do_leme"]
    massas += [{"nome": "motopropulsor", "formula": "0.427 + 0.115 + 0.100 + 0.086", "_f": spec["motor_x"]},
               {"nome": "servos_leme_e_elevon", "formula": "0.0294 * 2", "_f": 0.5},
               {"nome": "fuselagem_e_trem", "formula": "0.150 + 0.100 + 0.122 + 0.026 + 0.080 + 0.25", "_f": 0.3}]
    for m in massas:
        f = m.pop("_f", 0.3)
        m["posicao"] = [x_lo + f * L_x, 0.0, 0.0]
    for el in _fins_e_duto(esq):
        kg = DENS_CASCA * _area(el) * (2.0 if el["nome"].startswith("duto") else 1.0)
        sec = el["secoes"]
        m = {"nome": "casca_" + el["nome"], "formula": f"{kg:.6f}",
             "posicao": [el["posicao"][0] + sec[0]["xle"] + 0.5 * sec[0]["corda"], el["posicao"][1], el["posicao"][2]]}
        massas.append(m)
    return sis["grandezas"], massas


def problema(nome: str, pop_malha: dict | None = None, seguro: bool = False) -> dict:
    spec = _especificacoes()[nome]
    base0 = spec["fabrica"]()
    base0.pop("_pasta", None)
    base0["_pasta"] = str(L.PASTA)
    todas = [e["nome"] for e in base0["elementos"] if e.get("tipo") == "asa" and not e["nome"].startswith(("deriva", "duto"))]
    base0 = com_estrutura(base0, todas)
    if spec["duto"]:
        for el in base0["elementos"]:
            if el["nome"].startswith("duto"):
                el["sustenta"] = el["nome"] == "duto_1"
    ai_def = 0.0
    wo_def = max(s["ainc"] for e in base0["elementos"] if e["nome"] == spec["principais"][0] for s in e["secoes"])
    var = [{"nome": "b", "minimo": 2.0, "maximo": 3.8, "padrao": 2.8}, {"nome": "kc", "minimo": 0.8, "maximo": 3.0, "padrao": 1.8},
           {"nome": "xf", "minimo": -0.40, "maximo": 0.95, "padrao": 0.10}, {"nome": "ai", "minimo": -2.0, "maximo": 6.0, "padrao": ai_def},
           {"nome": "wo", "minimo": 0.0, "maximo": 12.0, "padrao": min(12.0, wo_def)}]
    sec = [n for n in spec["secundarias"] if n not in spec["principais"]]
    var += [{"nome": "de", "minimo": 0.012, "maximo": 0.024, "padrao": 0.014}]
    if sec:
        var += [{"nome": "dt", "minimo": 0.012, "maximo": 0.020, "padrao": 0.012}]
    var += [{"nome": n, "minimo": lo, "maximo": hi, "padrao": p} for n, lo, hi, p in spec["extras"]]
    regra = json.loads(REGRA.read_text(encoding="utf8"))
    sis = json.loads(SIS.read_text(encoding="utf8"))
    return {"modelo": nome, "base0": base0, "base": base0, "variaveis": var, "grandezas": sis["grandezas"], "massas": [],
            "regra": regra, "cenario": {"NR": 185.0},
            "dimensionamento": [{"nome": "parede", "elementos": spec["principais"], "ajuste": {"nome": "t", "minimo": 0.0002, "maximo": 0.0030}, "margem_alvo": 0.1,
                                 "ligacoes": [{"alvos": [f"{n}.estrutura.tubos[{i}].di" for n in spec["principais"] for i in range(4)], "formula": "de - 2*t"}]}]
                               + ([{"nome": "parede_sec", "elementos": sec, "ajuste": {"nome": "ts", "minimo": 0.0002, "maximo": 0.0030}, "margem_alvo": 0.1,
                                    "ligacoes": [{"alvos": [f"{n}.estrutura.tubos[{i}].di" for n in sec for i in range(4)], "formula": "dt - 2*ts"}]}] if sec else []),
            "ligacoes": [{"alvos": [f"{n}.estrutura.tubos[{i}].de" for n in spec["principais"] for i in range(4)], "formula": "de"}]
                        + ([{"alvos": [f"{n}.estrutura.tubos[{i}].de" for n in sec for i in range(4)], "formula": "dt"}] if sec else []),
            "cn_min": 0.04 if seguro else Cn_MIN,
            "restricoes": [{"nome": "margem_estatica", "formula": "margem_estatica", "limite": 0.06 if seguro else 0.05, "tipo": "min"},
                           {"nome": "margem_estrutural", "formula": "margem_estrutural", "limite": 0.03 if seguro else 0.0, "tipo": "min"},
                           {"nome": "defl_comando", "formula": "defl_trim_decolagem", "limite": 20.0, "tipo": "max"},
                           {"nome": "trim_fecha", "formula": "trim_decolagem_fecha", "limite": 1.0, "tipo": "min"}],
            "analise": {"T0": spec["T0"], "V0": spec["V0"], "pista_m": 55.0, "obstaculo_m": 0.9, "massa_projeto": 18.0, "cargas": {"Vc": 15.0},
                        "carga_ref_kg": 9.0, "trim_decolagem": {"fator_v": 1.2, "tipo": spec["tipo"], "comando": spec["comando"], "x_charneira": 0.7, "y_min": 0.0},
                        "malha": pop_malha or {"n_span": 12, "n_chord": 2, "n_perfil": 24, "n_por_baia": 2}}}


def prepara(prob: dict, x: dict) -> dict:
    spec = _especificacoes()[prob["modelo"]]
    xx = {v["nome"]: float(min(max(x.get(v["nome"], v["padrao"]), v["minimo"]), v["maximo"])) for v in prob["variaveis"]}
    esq = transforma(prob["base0"], spec, xx)
    lo, hi = _extremos_x(esq)
    grandezas, massas = _massas(esq, spec, lo, hi - lo)
    p = dict(prob)
    p["base"], p["grandezas"], p["massas"] = esq, grandezas, massas
    a = copy.deepcopy(prob["analise"])
    a["carga_x"] = float(lo + xx["xf"] * (hi - lo))
    comando = next(e for e in esq["elementos"] if e["nome"] == spec["comando"])
    a["trim_decolagem"]["y_min"] = 0.4 * _semi(comando) if spec["tipo"] == "flape" else 0.0
    p["analise"] = a
    return p


def avalia(prob: dict, x: dict) -> dict:
    from .equilibrio import monta
    p = prepara(prob, x)
    r = P.avalia(p, x)
    if r["falha"] is None:
        try:
            q = r["resultados"]
            malha = p["analise"].get("malha") or {}
            ns, nc = malha.get("n_span"), malha.get("n_chord")
            v = monta(p["base"], q["x_cg"], q["z_cg"], n_chord=nc, n_span=ns)
            Vv, rr = float(p["analise"].get("V", 12.0)), float(p["analise"].get("rho", 1.1))
            h = 0.5
            bp = v.resolver(3.0, V=Vv, rho=rr, beta=+h)[0]
            bm = v.resolver(3.0, V=Vv, rho=rr, beta=-h)[0]
            cn = float((bp.Cn - bm.Cn) / math.radians(2 * h))
        except Exception as e:
            cn = float("nan")
        q["Cn_beta"] = cn if math.isfinite(cn) else None
        lim_cn = float(prob.get("cn_min", Cn_MIN))
        ok = math.isfinite(cn) and cn >= lim_cn
        folga = (cn - lim_cn) if math.isfinite(cn) else -1.0
        vi = 0.0 if ok else max(0.0, -folga) / lim_cn
        r["restricoes"].append({"nome": "Cn_beta", "valor": q["Cn_beta"], "limite": lim_cn, "tipo": "min", "folga": folga, "violacao": vi, "ok": ok, "erro": None, "origem": "projeto"})
        r["viavel"] = all(c["ok"] for c in r["restricoes"])
    if r["falha"] is None:
        spec = _especificacoes()[prob["modelo"]]
        ext, intr, comp = _geometria(p["base"], spec)
        q = r["resultados"]
        q.update(varredura_externa=ext, varredura_interna=intr, comprimento_sup=comp)
        for nome, v, lim in (("varredura_externa", ext, VARRE_EXT_MAX), ("varredura_interna", intr, VARRE_INT_MAX), ("comprimento_sup", comp, COMP_SUP_MAX)):
            ok = v <= lim
            r["restricoes"].append({"nome": nome, "valor": v, "limite": lim, "tipo": "max", "folga": lim - v, "violacao": 0.0 if ok else (v - lim) / lim, "ok": ok, "erro": None, "origem": "projeto"})
        r["viavel"] = all(c["ok"] for c in r["restricoes"])
        r["violacao"] = _violacao(r["restricoes"])
    return r


def _geometria(esq: dict, spec: dict) -> tuple[float, float, float]:
    ext = intr = 0.0
    for el in esq["elementos"]:
        if el.get("nome") not in spec["principais"]:
            continue
        sec = sorted(el["secoes"], key=lambda t: t["y"])
        sec = [t for t in sec if t["y"] >= -1e-9] or sec
        semi = max(abs(t["y"]) for t in el["secoes"])
        for a, b in zip(sec[:-1], sec[1:]):
            dy = b["y"] - a["y"]
            if dy < 1e-6:
                continue
            ang = abs(math.degrees(math.atan((b["xle"] - a["xle"]) / dy)))
            if 0.5 * (a["y"] + b["y"]) > 0.30 * semi:
                ext = max(ext, ang)
            else:
                intr = max(intr, ang)
    lo, hi = _extremos_x(esq)
    return float(ext), float(intr), float(hi - lo)


def _violacao(restricoes: list) -> float:
    v = 0.0
    for c in restricoes:
        if c.get("ok"):
            continue
        if c.get("folga") is None:
            v += 1.0
        else:
            v += max(0.0, -float(c["folga"])) / max(abs(float(c["limite"] or 0.0)), 0.1)
    return v
