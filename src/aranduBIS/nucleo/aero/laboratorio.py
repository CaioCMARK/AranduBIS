from __future__ import annotations

import copy
import functools
import math
import warnings
from pathlib import Path

import numpy as np

from .aeronave_vlm import superficies
from .comparativo import Elevon, acha_parametro, avalia, cl_maximo_equilibrado
from .vlm import VLM

PASTA = Path(__file__).resolve().parents[4] / "cases" / "geometria" / "laboratorio"
REFLEXO = "REFLEX-10.dat"
WASHOUT = 4.0
B = 2.4
V, RHO, CL_PROJ = 15.0, 1.1, 0.6
CF = 0.0065
Z_CANARD = 0.15
RHO_AREAL = 0.45


def _modelo(nome, elementos, **extra):
    return {"_pasta": str(PASTA), "versao": 1, "nome": nome, "unidade": "m", "referencia": {"fonte": "laboratorio de configuracoes"},
            "elementos": elementos, "marcas": [], **extra}


def asa_espelhada(nome, pts, pos=(0.0, 0.0, 0.0), arfagem=0.0, perfil=REFLEXO, controles=None, n_perfil=40):
    sec = []
    for k, (y, x, z, c, a) in enumerate(pts):
        sec.append({"y": y, "xle": x, "zle": z, "corda": c, "ainc": a, "perfil": perfil})
    esq = [{**s, "y": -s["y"]} for s in reversed(sec[1:])]
    el = {"nome": nome, "tipo": "asa", "n_perfil": n_perfil, "posicao": list(pos), "secoes": esq + sec}
    if arfagem:
        el["arfagem"] = arfagem
    if controles:
        el["controles"] = controles
    return el


def deriva(nome, x, y, z, h, cr, ct, xle_ponta=0.0, para_baixo=False):
    return {"nome": nome, "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 40, "rolagem": -90.0 if para_baixo else 90.0,
            "posicao": [x, y, z], "secoes": [{"y": 0.0, "xle": 0.0, "corda": cr}, {"y": h, "xle": xle_ponta, "corda": ct}]}


def area_deriva(h, cr, ct):
    return 0.5 * h * (cr + ct)



def asa_varrida(ainc_raiz=WASHOUT, extra=()):
    pts = [(0.0, 0.0, 0.0, 0.52, ainc_raiz), (B / 2, 0.55, 0.0, 0.22, 0.0)]
    return _modelo("asa_varrida", [asa_espelhada("asa", pts)] + list(extra))


def vertical_nas_pontas(h, ainc_raiz=WASHOUT):
    f = [deriva(f"deriva_{l}", 0.55, s * B / 2, 0.0, h, 0.22, 0.12, 0.08) for l, s in (("esq", -1), ("dir", 1))]
    e = asa_varrida(ainc_raiz, f); e["nome"] = "vertical_nas_pontas"
    return e


def vertical_central(h, ainc_raiz=WASHOUT):
    f = [deriva("deriva", 0.40, 0.0, 0.0, h, 0.26, 0.14, 0.12)]
    e = asa_varrida(ainc_raiz, f); e["nome"] = "vertical_central"
    return e


def vertical_nas_pontas_para_baixo(h, ainc_raiz=WASHOUT):
    f = [deriva(f"deriva_{l}", 0.55, s * B / 2, 0.0, h, 0.22, 0.12, 0.08, para_baixo=True) for l, s in (("esq", -1), ("dir", 1))]
    e = asa_varrida(ainc_raiz, f); e["nome"] = "vertical_nas_pontas_para_baixo"
    return e



def burgess_dunne(ainc_raiz=WASHOUT, gap=0.36, stagger=0.12, com_derivas=True, nome="burgess_dunne"):
    pts = lambda: [(0.0, 0.0, 0.0, 0.30, ainc_raiz), (B / 2, 0.50, 0.0, 0.12, 0.0)]
    inf = asa_espelhada("asa_inferior", pts(), pos=(0.0, 0.0, 0.0))
    sup = asa_espelhada("asa_superior", pts(), pos=(-stagger, 0.0, gap))
    el = [inf, sup]
    if com_derivas:
        el += [deriva(f"deriva_{l}", 0.50, s * B / 2, 0.0, 0.20, 0.12, 0.08, 0.05) for l, s in (("esq", -1), ("dir", 1))]
    return _modelo(nome, el)


def monoplano_equivalente(ainc_raiz=WASHOUT):
    pts = [(0.0, 0.0, 0.0, 0.60, ainc_raiz), (B / 2, 0.50, 0.0, 0.24, 0.0)]
    return _modelo("monoplano_equivalente", [asa_espelhada("asa", pts)])



def bwb(ainc_raiz=WASHOUT, com_canard=False, S_canard=0.10, nome="bwb", com_derivas=True):
    pts = [(0.0, 0.0, 0.0, 0.90, ainc_raiz), (0.35, 0.50, 0.0, 0.50, ainc_raiz * 0.6), (B / 2, 0.50 + 0.577 * (B / 2 - 0.35), 0.0, 0.20, 0.0)]
    elv = [{"nome": "elevon", "y": [0.5, B / 2 - 0.02], "x": 0.7, "deflexao": 0.0, "modo": "sim", "charneira": "meio",
            "dobradica": "chanfro", "limite": 25.0}]
    el = [asa_espelhada("asa", pts, controles=elv)]
    xt, ct = pts[-1][1], pts[-1][3]
    if com_derivas:
        el += [deriva(f"deriva_{l}", xt, s * B / 2, 0.0, 0.18, ct, 0.10, 0.07) for l, s in (("esq", -1), ("dir", 1))]
    if com_canard:
        bc = S_canard / 0.14
        el.append(asa_espelhada("canard", [(0.0, 0.0, 0.0, 0.14, 2.0), (bc / 2, 0.0, 0.0, 0.14, 2.0)], pos=(-0.55, 0.0, Z_CANARD)))
    return _modelo(nome, el)



def duto_anel(R=0.15, comp=0.30, n=8, x=0.95, z=0.0, esp=0.0, nome_pref="duto"):
    els = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        y0, z0 = R * math.cos(a0), R * math.sin(a0)
        y1, z1 = R * math.cos(a1), R * math.sin(a1)
        L = math.hypot(y1 - y0, z1 - z0)
        diedro = math.degrees(math.atan2(z1 - z0, y1 - y0))
        els.append({"nome": f"{nome_pref}_{k}", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 40,
                    "rolagem": diedro, "posicao": [x, y0, z + z0], "secoes": [{"y": 0.0, "xle": 0.0, "corda": comp},
                                                                              {"y": L, "xle": 0.0, "corda": comp}]})
    return els


def asa_com_duto_na_cauda(R=0.15, comp=0.30, n=8, x_duto=0.95):
    pts = [(0.0, 0.0, 0.0, 0.30, 2.0), (B / 2, 0.0, 0.0, 0.24, 0.0)]
    el = [asa_espelhada("asa", pts)] + duto_anel(R, comp, n, x_duto)
    return _modelo("asa_com_duto_na_cauda", el)


def asa_sem_cauda_reta():
    pts = [(0.0, 0.0, 0.0, 0.30, 2.0), (B / 2, 0.0, 0.0, 0.24, 0.0)]
    return _modelo("asa_reta", [asa_espelhada("asa", pts)])


def asa_com_cauda_convencional(S_h=0.10, S_v=0.04, x_cauda=0.95):
    pts = [(0.0, 0.0, 0.0, 0.30, 2.0), (B / 2, 0.0, 0.0, 0.24, 0.0)]
    bh = math.sqrt(S_h * 6.0)
    ch = S_h / bh
    h = S_v / 0.18
    el = [asa_espelhada("asa", pts),
          asa_espelhada("empenagem_h", [(0.0, 0.0, 0.0, ch, 0.0), (bh / 2, 0.0, 0.0, ch, 0.0)], pos=(x_cauda, 0.0, 0.0)),
          deriva("deriva", x_cauda, 0.0, 0.0, h, 0.22, 0.14, 0.06)]
    return _modelo("asa_cauda_convencional", el)



def asa_em_caixa(gap=0.40, stagger=0.35, nome="asa_em_caixa"):
    pts = lambda inc: [(0.0, 0.0, 0.0, 0.18, inc), (B / 2, 0.0, 0.0, 0.18, inc)]
    return _modelo(nome, [asa_espelhada("asa_frente", pts(3.0), perfil="NACA 4412"),
                          asa_espelhada("asa_tras", pts(1.0), pos=(stagger, 0.0, gap), perfil="NACA 4412")])


def tandem(x_tras=0.70, area_tras=0.5, nome="tandem"):
    f = [(0.0, 0.0, 0.0, 0.24, 3.0), (1.0, 0.0, 0.0, 0.24, 3.0)]
    cb = 0.28
    t = [(0.0, 0.0, 0.0, cb, 1.0), (1.2, 0.0, 0.0, cb, 1.0)]
    return _modelo(nome, [asa_espelhada("asa_frente", f, perfil="NACA 4412"),
                          asa_espelhada("asa_tras", t, pos=(x_tras, 0.0, 0.0), perfil="NACA 4412")])



def referencia_de(esq: dict) -> dict:
    d = copy.deepcopy(esq)
    v = VLM(superficies(d, 24, 8))
    d.pop("_pasta", None)
    d["referencia"] = {**d.get("referencia", {}), "Sref": round(float(v.S_ref), 4), "Cref": round(float(v.c_ref), 4),
                       "Bref": round(float(v.b_ref), 4)}
    return d



PESO_N = 66.8
N_CHORD, N_SPAN = 8, 24
_KW = dict(V=V, rho=RHO, peso_N=PESO_N, n_span=N_SPAN, n_chord=N_CHORD)


def _sem_aviso(f):
    @functools.wraps(f)
    def g(*a, **k):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*pede n_span.*")
            return f(*a, **k)
    return g


def _q():
    return 0.5 * RHO * V * V


@_sem_aviso
def exemplos() -> dict:
    ex = {}
    for nome, f in (("asa_varrida", asa_varrida), ("burgess_dunne", burgess_dunne), ("monoplano_equivalente", monoplano_equivalente),
                    ("bwb", bwb), ("bwb_canard", lambda a: bwb(a, com_canard=True))):
        ex[f"{nome}.json"] = _trima_washout(f)[1]
    w = _trima_washout(asa_varrida)[0]
    for rot, fab in (("vertical_nas_pontas", vertical_nas_pontas), ("vertical_nas_pontas_para_baixo", vertical_nas_pontas_para_baixo),
                     ("vertical_central", vertical_central)):
        ex[f"{rot}.json"] = fab(_h_para_cn(lambda h_: fab(h_, w), 0.03)[0], w)
    ex["asa_com_duto_na_cauda.json"] = asa_com_duto_na_cauda()
    ex["asa_cauda_convencional.json"] = asa_com_cauda_convencional()
    ex["asa_em_caixa.json"] = asa_em_caixa()
    ex["tandem.json"] = tandem()
    return ex


def _medida_cm(e):
    return avalia(e, comando=None, laterais=False, **_KW)["trim"]["Cm"]


def _trima_washout(construtor, comando=None):
    def med(e):
        return avalia(e, comando=None, laterais=False, **_KW)["trim"]["Cm"]
    a, e, _ = acha_parametro(construtor, 0.0, med, 2.0, 6.0, tol=1e-4, n=14)
    return float(a), e


def _h_para_cn(fabrica, Cn_alvo=0.03, h0=0.12, h1=0.30):
    return acha_parametro(fabrica, Cn_alvo, lambda e: avalia(e, comando=None, **_KW)["Cn_beta"], h0, h1, tol=1e-3, n=16)


def _fins(esq):
    return [e for e in esq["elementos"] if e["nome"].startswith("deriva")]


def _resumo(a):
    t = a["trim"]
    return {"Di_N": a["Di_N"], "e_b": a["e_b"], "Cn_beta": a.get("Cn_beta"), "Cl_beta": a.get("Cl_beta"), "SM": a["SM"],
            "alpha": t["alpha"], "delta": t["delta"], "CL": t["CL"], "Cm": t["Cm"]}


def _mass_fin_N(esq):
    return 9.81 * RHO_AREAL * sum(area_deriva(f["secoes"][1]["y"], f["secoes"][0]["corda"], f["secoes"][1]["corda"]) for f in _fins(esq))


def _arrasto_deriva_N(esq):
    return CF * _q() * 2.2 * sum(area_deriva(f["secoes"][1]["y"], f["secoes"][0]["corda"], f["secoes"][1]["corda"]) for f in _fins(esq))


@_sem_aviso
def estudo_vertical(Cn_alvo=0.03):
    w = _trima_washout(asa_varrida)[0]
    sem = avalia(asa_varrida(w), comando=None, **_KW)
    saida = {"washout_graus": w, "sem_vertical": _resumo(sem)}
    for rot, fab in (("pontas_cima", vertical_nas_pontas), ("pontas_baixo", vertical_nas_pontas_para_baixo), ("central", vertical_central)):
        h, e, cn = _h_para_cn(lambda h_: fab(h_, w), Cn_alvo)
        a = avalia(e, comando=None, **_KW)
        r = _resumo(a)
        r.update({"h_m": h, "area_total_m2": sum(area_deriva(f["secoes"][1]["y"], f["secoes"][0]["corda"], f["secoes"][1]["corda"]) for f in _fins(e)),
                  "Dp_deriva_N": _arrasto_deriva_N(e), "peso_deriva_N": _mass_fin_N(e),
                  "saldo_arrasto_N": a["Di_N"] + _arrasto_deriva_N(e) - sem["Di_N"]})
        saida[rot] = r
    return saida


def _com_washout(fabrica, h, ainc):
    return fabrica(h, ainc) if h is not None else fabrica(ainc)


@_sem_aviso
def estudo_burgess_dunne():
    wm, mono = _trima_washout(monoplano_equivalente)
    wb, bd = _trima_washout(burgess_dunne)
    wbs, bds = _trima_washout(lambda a: burgess_dunne(a, com_derivas=False))
    res = {}
    for rot, e, w in (("monoplano", mono, wm), ("burgess_dunne", bd, wb), ("burgess_dunne_sem_derivas", bds, wbs)):
        r = _resumo(avalia(e, comando=None, **_KW))
        r["washout_graus"] = w
        res[rot] = r
    res["ganho_Di_pct"] = 100 * (1 - res["burgess_dunne"]["Di_N"] / res["monoplano"]["Di_N"])
    d_m = avalia(monoplano_equivalente(4.0), comando=None, laterais=False, **_KW)["Di_N"]
    d_b = avalia(burgess_dunne(4.0), comando=None, laterais=False, **_KW)["Di_N"]
    res["ganho_Di_pct_mesmo_washout_4graus"] = 100 * (1 - d_b / d_m)
    return res


@_sem_aviso
def estudo_bwb(altura_solo=0.20, CL_rot=0.9):
    el = Elevon("asa", y_min=0.5, x_charneira=0.7, limite=25.0)
    res = {}
    for rot, fab in (("bwb", bwb), ("bwb_canard", lambda a, **k: bwb(a, com_canard=True, **k))):
        com_canard = rot == "bwb_canard"
        kw = dict(elevon=None, comando="canard") if com_canard else dict(elevon=el, comando=None)
        w, e = _trima_washout(fab)
        r = _resumo(avalia(e, **kw, **_KW))
        _, e0 = _trima_washout(lambda a: fab(a, com_derivas=False))
        rot_ = cl_maximo_equilibrado(e0, V=V, rho=RHO, altura_solo=altura_solo, n_span=14, n_chord=6, **kw)
        r.update({"washout_graus": w, "CL_max_equilibrado": rot_["CL_max_equilibrado"], "pode_rotacionar": rot_["CL_max_equilibrado"] >= CL_rot,
                  "altura_solo_m": altura_solo, "CL_rot": CL_rot,
                  "no_limite": {"alpha": rot_["avaliacao"]["trim"]["alpha"], "delta": rot_["avaliacao"]["trim"]["delta"]},
                  "CL_max_vs_altura": {f"{h:g}": cl_maximo_equilibrado(e0, V=V, rho=RHO, altura_solo=h, n_span=14, n_chord=6, **kw)["CL_max_equilibrado"]
                                       for h in (0.15, 0.30)}})
        res[rot] = r
    return res


@_sem_aviso
def estudo_duto():
    x_cg = 0.12
    res = {}
    for rot, e in (("asa_reta", asa_sem_cauda_reta()), ("duto_na_cauda", asa_com_duto_na_cauda()), ("cauda_convencional", asa_com_cauda_convencional())):
        a = avalia(e, comando=None, x_cg=x_cg, **_KW)
        res[rot] = _resumo(a) | {"Cm_alpha": a["Cm_alpha"]}
    return res


def empuxo_duto(P_W=400.0, D_m=0.30, sigma=1.0, rho=RHO, FM=0.7):
    A = math.pi * D_m * D_m / 4
    return FM * (2 * rho * A * sigma * P_W ** 2) ** (1 / 3)


@_sem_aviso
def estudo_caixa_tandem():
    res = {}
    for rot, e, cmd in (("monoplano_com_cauda", asa_com_cauda_convencional(), "auto"), ("caixa", asa_em_caixa(), "asa_tras"), ("tandem", tandem(), "asa_tras")):
        a = avalia(e, comando=cmd, **_KW)
        res[rot] = _resumo(a)
    return res


def flutter_massa_de_ponta(esq, asa="asa", Vd=25.0, massas_g=(0, 25, 50), x_c=(0.3, 0.55, 0.8)):
    import json
    from ..estrutura import flutter as FL
    esq = copy.deepcopy(esq)
    el_asa = next(e for e in esq["elementos"] if e["nome"] == asa)
    if "estrutura" not in el_asa:
        ref = json.loads((PASTA.parent / "generico" / "asa_canard.json").read_text(encoding="utf8"))
        base = next(e for e in ref["elementos"] if e["nome"] == "asa")
        el_asa["estrutura"], el_asa["entelagem"] = copy.deepcopy(base["estrutura"]), copy.deepcopy(base["entelagem"])
    ponta = max(abs(s["y"]) for s in el_asa["secoes"])
    out = {"asa": asa, "Vd": Vd, "V_requerida": 1.2 * Vd, "casos": []}
    for xc in x_c:
        for m in massas_g:
            mr = {"usar": True, "adicionais": [{"nome": "deriva", "asa": asa, "massa_kg": m / 1000.0, "y_m": ponta * 0.96, "x_c": xc}] if m else [],
                  "medidas": {}}
            r = FL.analisa_flutter(esq, asa, Vd=Vd, massa_real=mr)
            out["casos"].append({"massa_g": m, "x_c": xc, "VF": r["VF"]})
    return out


@_sem_aviso
def roda_estudos():
    w = _trima_washout(asa_varrida)[1]
    return {"vertical": estudo_vertical(), "burgess_dunne": estudo_burgess_dunne(), "bwb": estudo_bwb(), "duto": estudo_duto(),
            "duto_empuxo_N": {"cilindrico_sigma1": empuxo_duto(sigma=1.0), "difusor_sigma1.2": empuxo_duto(sigma=1.2)},
            "caixa_tandem": estudo_caixa_tandem(), "flutter_massa_de_ponta": flutter_massa_de_ponta(w)}
