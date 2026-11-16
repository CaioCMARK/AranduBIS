from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

from ..nucleo import referencias as R
from ..nucleo import discretizacao as D
from ..nucleo import decolagem as DC
from ..nucleo.modelador import aeronave_geometria as AG

_NAO_SUSTENTA = re.compile(r"empenagem|estab|deriva|leme|profund|helice|hélice|canard|winglet|endplate", re.I)

class ErroDeAnalise(ValueError):
    pass

def _secoes(el: dict) -> list[dict]:
    if isinstance(el.get("secoes"), list) and len(el["secoes"]) >= 2:
        return el["secoes"]
    s = el.get("secoes_lineares")
    if s:
        ys = np.linspace(s["y"][0], s["y"][1], int(s.get("n", 2)))
        return [{"y": float(y), "corda": float(s.get("corda", 1.0))} for y in ys]
    return []

def _sustenta(el: dict) -> bool:
    if "papel" in el:
        return el["papel"] == "sustentacao"
    return (el.get("tipo", "asa") == "asa" and el.get("camada", "aero") == "aero"
            and not _NAO_SUSTENTA.search(el.get("nome", "")) and not el.get("rolagem"))

def resumo_aero(esq: dict) -> dict:
    itens, S = [], 0.0
    for el in esq.get("elementos", []):
        if not _sustenta(el):
            continue
        sec = _secoes(el)
        if len(sec) < 2:
            continue
        y = np.array([float(s["y"]) for s in sec])
        c = np.array([float(s.get("corda", 0.0)) for s in sec])
        o = np.argsort(y)
        y, c = y[o], c[o]
        area = float(np.sum(0.5 * (c[1:] + c[:-1]) * np.diff(y)))
        mac = float(np.sum((2 / 3) * (c[1:] ** 2 + c[1:] * c[:-1] + c[:-1] ** 2) / (c[1:] + c[:-1] + 1e-12)
                           * 0.5 * (c[1:] + c[:-1]) * np.diff(y)) / area) if area > 0 else 0.0
        env = float(y[-1] - y[0])
        itens.append({"nome": el["nome"], "area_m2": area, "envergadura_m": env, "corda_media_m": mac})
        S += area
    if not itens:
        return {"area_m2": 0.0, "envergadura_m": 0.0, "alongamento": 0.0, "superficies": []}
    b = max(i["envergadura_m"] for i in itens)
    return {"area_m2": S, "envergadura_m": b, "alongamento": b * b / S if S > 0 else 0.0, "superficies": itens}

def _num(d: dict, chave: str, padrao=None, positivo=False):
    v = d.get(chave, padrao)
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ErroDeAnalise(f"“{chave}” precisa ser um número.")
    if positivo and v <= 0:
        raise ErroDeAnalise(f"“{chave}” precisa ser maior que zero.")
    return float(v)

def _vd(p: dict) -> float:
    if p.get("Vd") is not None:
        return _num(p, "Vd", positivo=True)
    if p.get("Vc") is not None:
        return R.velocidade_mergulho(_num(p, "Vc", positivo=True))
    raise ErroDeAnalise("Informe a velocidade de mergulho Vd (ou a de cruzeiro Vc).")

def _knockdown(p: dict):
    k = _num(p, "knockdown_pele", 0.0)
    if k < 0 or k > 1:
        raise ErroDeAnalise("“knockdown_pele” vai de 0 (automático) a 1.")
    return k or None

def _tracao(d: dict) -> tuple[tuple, tuple]:
    if d.get("v") and d.get("n"):
        v, n = list(map(float, d["v"])), list(map(float, d["n"]))
        if len(v) != len(n) or len(v) < 2 or any(b <= a for a, b in zip(v, v[1:])):
            raise ErroDeAnalise("Tabela de tração: velocidades crescentes, mesmo número de pontos.")
        return tuple(v), tuple(n)
    T0, V0 = _num(d, "T0", positivo=True), _num(d, "V0", positivo=True)
    return (0.0, V0), (T0, 0.0)

def _decimar(a, n=400):
    a = np.asarray(a, float)
    if len(a) <= n:
        return a.tolist()
    return a[np.linspace(0, len(a) - 1, n).astype(int)].tolist()

def _lim(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else x

def decolagem(p: dict) -> dict:
    a, c = p.get("aeronave") or {}, p.get("condicoes") or {}
    campos = {k: c[k] for k in ("pista_m", "obstaculo_m", "altitude_densidade_m", "mu",
                                "d_alpha_rotacao", "taxa_rotacao", "margem_rotacao") if k in c}
    for k, v in campos.items():
        _num(campos, k)
    cond = DC.Condicoes(**campos)
    vt, tt = _tracao(p.get("tracao") or {})
    solo = a.get("solo") or {}
    sh, sk = tuple(map(float, solo.get("h", ()))), tuple(map(float, solo.get("K", ())))
    ae = DC.Aeronave(S=_num(a, "S", positivo=True), CL_max=_num(a, "CL_max", positivo=True),
                     CL_corrida=_num(a, "CL_corrida"), CD_corrida=_num(a, "CD_corrida", positivo=True),
                     tracao_v=vt, tracao_n=tt, solo_h=sh, solo_K=sk, h0=float(solo.get("h0", 0.0)))
    massa = _num(p, "massa_kg", positivo=True)
    try:
        r = DC.simular(massa, ae, cond)
    except ValueError as e:
        raise ErroDeAnalise(str(e)) from None
    mm = DC.massa_maxima(ae, cond)
    lo = max(0.5, (mm["massa_kg"] or massa) * 0.6)
    hi = max(lo + 1.0, (mm["massa_kg"] or massa) * 1.5)
    varre = DC.varredura_de_massa(ae, cond, np.linspace(lo, hi, 25))
    f = r.forcas or {}
    return {
        "decolou": r.decolou, "transpos": r.transpos, "motivo": r.motivo,
        "altura_obstaculo_m": _lim(r.altura_obstaculo), "folga_m": _lim(r.folga_m),
        "distancia_rotacao_m": _lim(r.distancia_rotacao), "velocidade_rotacao_ms": _lim(r.velocidade_rotacao),
        "massa_kg": massa, "rho": cond.rho,
        "massa_maxima": {k: _lim(v) for k, v in mm.items()},
        "serie": {"x": _decimar(r.x), "h": _decimar(r.h), "v": _decimar(r.v),
                  "forcas": {k: _decimar(v) for k, v in f.items()}},
        "obstaculo": {"distancia_m": cond.pista_m, "altura_m": cond.obstaculo_m},
        "varredura": [{k: _lim(v) for k, v in q.items()} for q in varre],
        "numba": DC.COM_NUMBA,
    }

def _erro(e: Exception) -> str:
    if isinstance(e, FileNotFoundError):
        return "arquivo de perfil nao encontrado: " + Path(str(e.filename)).name
    return str(e).split(chr(10))[0]

def equilibrio(p: dict) -> dict:
    from ..nucleo.aero.equilibrio import longitudinal
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    V, rho = _num(p, "V", positivo=True), _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
    CL_alvo = _num(p, "CL_alvo", positivo=True) if p.get("CL_alvo") is not None else None
    x_cg, origem, z_cg = p.get("x_cg"), "voce", 0.0
    try:
        cg = None
        if x_cg is None or esq.get("elementos"):
            cg = AG.massa_e_cg(AG.constroi(esq))["cg_m"]
        if cg:
            z_cg = float(cg[2])
        if x_cg is None:
            x_cg, origem = (float(cg[0]), "massas do modelo") if cg else (None, "")
        if x_cg is None:
            base = longitudinal(esq, 0.0, V=V, rho=rho)
            x_cg, origem = base["ponto_neutro"] - 0.15 * base["c_ref"], "estimado"
        r = longitudinal(esq, float(x_cg), V=V, rho=rho, CL_alvo=CL_alvo, comando=p.get("comando"), z_cg=z_cg)
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}
    r["cg_origem"] = origem
    return r

_MEMO_LIMITES: dict = {}

def limites(p: dict) -> dict:
    import json
    chave = json.dumps(p, sort_keys=True, default=str)
    if chave not in _MEMO_LIMITES:
        if len(_MEMO_LIMITES) >= 6:
            _MEMO_LIMITES.pop(next(iter(_MEMO_LIMITES)))
        _MEMO_LIMITES[chave] = _limites(p)
    return _MEMO_LIMITES[chave]

def _limites(p: dict) -> dict:
    from ..nucleo.aero.limites import cl_max
    from ..nucleo.aero.equilibrio import longitudinal
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    V, rho = _num(p, "V", positivo=True), _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
    ncrit = int(_num(p, "ncrit", 4.0, positivo=True))
    if ncrit not in (4, 7):
        return {"erro": "Ncrit do banco: 4 (ar livre) ou 7."}
    x_cg = p.get("x_cg")
    try:
        if x_cg is None:
            cg = AG.massa_e_cg(AG.constroi(esq))["cg_m"]
            x_cg = float(cg[0]) if cg else None
        if x_cg is None:
            base = longitudinal(esq, 0.0, V=V, rho=rho)
            x_cg = base["ponto_neutro"] - 0.15 * base["c_ref"]
        a_solo = p.get("alpha_solo")
        cda = p.get("CdA")
        return cl_max(esq, float(x_cg), V=V, rho=rho, ncrit=ncrit,
                      alpha_solo=None if a_solo is None else _num(p, "alpha_solo"),
                      CdA_proprio=None if cda is None else _num(p, "CdA"),
                      altura=None if p.get("altura") is None else _num(p, "altura", positivo=True),
                      com_solo=bool(p.get("com_solo", True)))
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def propulsao(p: dict) -> dict:
    from ..nucleo.aero import propulsao as PR
    if p.get("lista"):
        return PR.lista()
    try:
        return PR.curva(str(p.get("motor", "")), str(p.get("helice", "")), P_w=_num(p, "P_w", 600.0, positivo=True),
                        rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), V_max=_num(p, "V_max", 30.0, positivo=True),
                        realista=bool(p.get("realista", True)),
                        celulas=int(_num(p, "celulas")) if p.get("celulas") else None,
                        v_celula=_num(p, "v_celula", 3.6, positivo=True),
                        capacidade_Ah=_num(p, "capacidade_Ah", positivo=True) if p.get("capacidade_Ah") else None,
                        taxa_C=_num(p, "taxa_C", positivo=True) if p.get("taxa_C") else None)
    except ValueError as e:
        return {"erro": _erro(e)}

def envelope_cg(p: dict) -> dict:
    from ..nucleo.aero.envelope import envelope_cg as env
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    try:
        return env(p.get("esquema") or {}, V=_num(p, "V", positivo=True), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                   massa_kg=None if p.get("massa_kg") is None else _num(p, "massa_kg", positivo=True),
                   CL_alvo=None if p.get("CL_alvo") is None else _num(p, "CL_alvo", positivo=True),
                   margem_minima=_num(p, "margem_minima", 0.05, positivo=True))
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

_CL_MAX: dict = {}
_CARGAS: dict = {}

def cargas(p: dict) -> dict:
    chave = json.dumps(p, sort_keys=True, default=str)
    if chave not in _CARGAS:
        r = _cargas(p)
        if "erro" in r:
            return r
        if len(_CARGAS) > 4:
            _CARGAS.clear()
        _CARGAS[chave] = r
    return _CARGAS[chave]

def _aileron_par(p: dict):
    a = p.get("aileron")
    if not isinstance(a, dict) or a.get("ativo") is False:
        return None
    out = {}
    for k in ("massa_kg", "x_cg", "r_giro", "f_b", "zeta"):
        if a.get(k) not in (None, ""):
            v = float(a[k])
            if k in ("massa_kg", "r_giro") and v <= 0:
                raise ErroDeAnalise(f"aileron.{k} precisa ser positivo")
            if k == "f_b" and v < 0:
                raise ErroDeAnalise("aileron.f_b nao pode ser negativa")
            out[k] = v
    return out

def _com_longarina(e: dict) -> bool:
    return e.get("tipo") == "asa" and bool((e.get("estrutura") or {}).get("longarinas"))

def _sem_longarina(esq: dict) -> list[str]:
    n = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa" and e.get("estrutura") and not _com_longarina(e)]
    return [f"Sem longarina declarada, fora desta analise: {', '.join(n)}."] if n else []

def asa(p: dict) -> dict:
    from ..nucleo.estrutura.asa import verifica
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    c = cargas(p)
    if "erro" in c:
        return c
    esq = p.get("esquema") or {}
    try:
        saidas, avisos = [], []
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            if not any(s["nome"] == e["nome"] for s in c["casos"][0]["superficies"]):
                continue
            saidas.append(verifica(esq, e["nome"], c["casos"], mats=p.get("materiais"), fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True),
                                   qualidade_balsa=_num(p, "qualidade_balsa", 1.0, positivo=True),
                                   qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True)))
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        pior = min(saidas, key=lambda s: s["critico"]["margem"])
        return {"asas": saidas, "critico": dict(pior["critico"], asa=pior["nome"]), "vn": c["vn"], "massa_kg": c["massa_kg"],
                "avisos": avisos + c["avisos"] + [a for s in saidas for a in s["avisos"]] + _sem_longarina(esq)}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def massa_estrutural(p: dict) -> dict:
    from ..nucleo.estrutura.massa import balanco
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    try:
        return balanco(p.get("esquema") or {}, _num(p, "mtow_kg", positivo=True) if p.get("mtow_kg") is not None else None)
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def trem(p: dict) -> dict:
    from ..nucleo.estrutura.trem import analisa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        r = analisa(esq, massa_kg=_num(p, "massa_kg", positivo=True) if p.get("massa_kg") is not None else None,
                    x_cg=_num(p, "x_cg") if p.get("x_cg") is not None else None, fator_pouso=_num(p, "fator_pouso", R.FATOR_POUSO, positivo=True),
                    atrito_pouso=_num(p, "atrito_pouso", 0.3), fator_taxi_y=_num(p, "fator_taxi_y", R.FATOR_TAXI_Y), fator_taxi_z=_num(p, "fator_taxi_z", R.FATOR_TAXI_Z, positivo=True),
                    fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True), K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True),
                    raio_inercia=_num(p, "raio_inercia", 0.25, positivo=True), raio_solda=_num(p, "raio_solda", 0.0), mats=p.get("materiais"), qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True))
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, StopIteration) as e:
        return {"erro": _erro(e)}

_REF_AERO: dict = {}
_FE_TREM: dict = {}

def pouso_dinamico(p: dict) -> dict:
    from ..nucleo.aero.equilibrio import monta
    from ..nucleo.aero.estabilidade import derivadas
    from ..nucleo.estrutura import pouso_dinamico as PD
    from ..nucleo.estrutura import trem as TR
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        c = cargas({k: v for k, v in p.items() if k in ("esquema", "rho", "Vc", "Vd", "massa_kg", "x_cg", "CL_max", "ncrit", "n_max", "n_min", "U_c", "U_d", "fator_seguranca", "cl_min_rel")})
        if "erro" in c:
            return c
        massa = float(c["massa_kg"])
        mc = AG.massa_e_cg(AG.constroi(esq))
        cg = mc["cg_m"]
        x_cg = float(p["x_cg"]) if p.get("x_cg") is not None else (float(cg[0]) if cg else None)
        if x_cg is None:
            return {"erro": "Sem CG: declare as pecas no modelo ou informe x_cg."}
        z_cg = float(cg[2]) if cg else 0.0
        rho, Vc = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), _num(p, "Vc", positivo=True)
        chave = (json.dumps(esq, sort_keys=True, default=str), round(x_cg, 6), round(Vc, 3), round(rho, 4))
        if chave not in _REF_AERO:
            if len(_REF_AERO) > 6:
                _REF_AERO.clear()
            vlm = monta(esq, x_cg, z_cg)
            d = derivadas(vlm, 3.0, V=Vc, rho=rho, laterais=False)
            _REF_AERO[chave] = {"S": float(vlm.S_ref), "c": float(vlm.c_ref), "CLa": float(d.CL_alpha), "Cma": float(d.Cm_alpha)}
        ref = _REF_AERO[chave]
        fator_pouso, atrito = _num(p, "fator_pouso", R.FATOR_POUSO, positivo=True), _num(p, "atrito_pouso", 0.3)
        kw = dict(fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True), K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True),
                  raio_inercia=_num(p, "raio_inercia", 0.25, positivo=True), raio_solda=_num(p, "raio_solda", 0.0), mats=p.get("materiais"),
                  qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True))
        chave_fe = (chave[0], round(massa, 4), fator_pouso, atrito, json.dumps({k: v for k, v in kw.items() if k != "mats"}, sort_keys=True), json.dumps(kw["mats"], sort_keys=True, default=str))
        if chave_fe not in _FE_TREM:
            if len(_FE_TREM) > 4:
                _FE_TREM.clear()
            _FE_TREM[chave_fe] = TR.analisa(esq, massa_kg=massa, x_cg=x_cg, fator_pouso=fator_pouso, atrito_pouso=atrito, **kw)
        opc = lambda k, pad=None, pos=False: _num(p, k, pad, positivo=pos) if p.get(k) is not None else pad
        r = PD.analisa(esq, massa_kg=massa, x_cg=x_cg, Iyy=opc("Iyy", None, True), S=ref["S"], c_med=ref["c"], CL_alpha=ref["CLa"], Cm_alpha=ref["Cma"],
                       CL_max=float(c["vn"]["CL_max"]), Vs=float(c["vn"]["Vs"]), rho=rho, V_toque_rel=_num(p, "V_toque_rel", 1.15, positivo=True),
                       vel_descida=_num(p, "vel_descida", 1.0, positivo=True), atitude_2p_extra=_num(p, "atitude_2p_extra", 6.0),
                       sustentacao_toque_rel=_num(p, "sustentacao_toque_rel", 1.0), Cm_q=_num(p, "Cm_q", -8.0), CD=_num(p, "CD", 0.12),
                       mu_rolamento=_num(p, "mu_rolamento", R.MU_ROLAGEM), k_pneu_principal=_num(p, "k_pneu_principal", 30000.0, positivo=True),
                       k_pneu_bequilha=_num(p, "k_pneu_bequilha", 30000.0, positivo=True), k_perna_principal=opc("k_perna_principal", None, True),
                       k_perna_bequilha=opc("k_perna_bequilha", None, True), zeta=_num(p, "zeta", 0.15), curso_trem_mm=_num(p, "curso_trem_mm", 0.0),
                       perfil_pista=str(p.get("perfil_pista") or "irregular"), altura_pista_mm=_num(p, "altura_pista_mm", 5.0), comprimento_pista_m=_num(p, "comprimento_pista_m", 0.3, positivo=True),
                       V_taxi_rel=_num(p, "V_taxi_rel", 0.8, positivo=True), sustentacao_taxi_rel=_num(p, "sustentacao_taxi_rel", 0.0), fator_pouso_projeto=fator_pouso,
                       aplica_fe=bool(p.get("aplica_fe")), atrito_pouso=atrito, fe_estatico=_FE_TREM[chave_fe], **kw)
        r["ref_aero"] = ref
        r["origem_massa"] = c["origem_massa"]
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, StopIteration) as e:
        return {"erro": _erro(e)}

def flambagem(p: dict) -> dict:
    from ..nucleo.estrutura.flambagem import verifica as fl

    a = asa(p)
    if "erro" in a:
        return a
    esq = p.get("esquema") or {}
    try:
        saidas = [dict(fl(esq, x["nome"], x, mats=p.get("materiais"), qualidade_balsa=_num(p, "qualidade_balsa", 1.0, positivo=True),
                          E_transv_GPa=_num(p, "balsa_E_transv", R.BALSA["ET_sobre_EL"] * R.BALSA["E"] / R.GPA, positivo=True), knockdown=_knockdown(p),
                          margem_alvo=_num(p, "margem_alvo_flambagem", 0.0)), fontes=x["fontes"]) for x in a["asas"]]
        pior = min(saidas, key=lambda s: s["pior_pele"]["margem_pele"] if s["pior_pele"] else 1e9)
        return {"asas": saidas, "pior": pior["nome"], "critico": pior["pior_pele"], "vn": a["vn"], "avisos": a["avisos"]}
    except (ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def _succao_media(xe_c: float) -> float:
    import math
    xe = min(max(xe_c, 1e-4), 1.0)
    return 2.0 / (math.pi * xe) * (math.sqrt(xe * (1 - xe)) + math.asin(math.sqrt(xe)))

def chapeado_fe(p: dict) -> dict:
    from ..nucleo.estrutura import asa as AS
    from ..nucleo.estrutura.flambagem import verifica as fl, _fator_imperfeicao, _geom, sigma_cr_curvo, sigma_cr_ortotropica
    from ..nucleo.estrutura.materiais import propriedades
    from ..nucleo.fe import chapeado_ccx as CC

    try:
        CC.executavel()
    except CC.SemCalculix as e:
        return {"erro": str(e)}
    a = asa(p)
    if "erro" in a:
        return a
    esq = p.get("esquema") or {}
    try:
        com = [x for x in a["asas"] if ((AS._elemento(esq, x["nome"]).get("estrutura") or {}).get("chapeado"))]
        if not com:
            return {"erro": "Nenhuma asa com chapeado declarado."}
        nome = p.get("asa") if p.get("asa") in [x["nome"] for x in com] else None
        E_tr = _num(p, "balsa_E_transv", R.BALSA["ET_sobre_EL"] * R.BALSA["E"] / R.GPA, positivo=True) * 1e9
        qb = _num(p, "qualidade_balsa", 1.0, positivo=True)
        cand = []
        for x in com:
            if nome and x["nome"] != nome:
                continue
            f = fl(esq, x["nome"], x, mats=p.get("materiais"), qualidade_balsa=qb, E_transv_GPa=E_tr / 1e9, knockdown=_knockdown(p))
            for pn in f["paineis"]:
                if "margem_pele" in pn and pn["sigma_pele_MPa"] > 0:
                    cand.append((x, pn))
        if not cand:
            return {"erro": "Nenhuma baia de chapeado em compressao."}
        if p.get("baia"):
            y0, y1 = (float(v) for v in p["baia"])
            x, pn = min(cand, key=lambda c: abs(c[1]["y0"] - y0) + abs(c[1]["y1"] - y1))
        else:
            x, pn = min(cand, key=lambda c: c[1]["margem_pele"])
        y0, y1, ym = pn["y0"], pn["y1"], 0.5 * (pn["y0"] + pn["y1"])
        el = AS._elemento(esq, x["nome"])
        yy = np.array(x["y"])
        k_caso = max(range(len(x["casos"])), key=lambda k: float(np.interp(ym, yy, x["casos"][k]["tensao_MPa"]["pele_comp"])))
        sigma = float(np.interp(ym, yy, x["casos"][k_caso]["tensao_MPa"]["pele_comp"])) * 1e6
        c = cargas(p)
        caso = next(k for k in c["casos"] if k["nome"] == x["casos"][k_caso]["caso"])
        sup = next(s for s in caso["superficies"] if s["nome"] == x["nome"])
        L = sup["lados"].get("dir") or sup["lados"].get("esq")
        l_m = abs(float(np.interp(ym, np.abs(L["y"]), L["sustentacao_por_m"])))
        sec_el, xs, Z = AS._perfis(el, esq)
        q = AG._secao_em(sec_el, ym); corda = float(q[3])
        xe = AS._fim_do_chapeado(el["estrutura"]["chapeado"], ym)
        sf = float(a["asas"][0]["fator_seguranca"])
        dp = _num(p, "dp_Pa", None) if p.get("dp_Pa") is not None else sf * 0.5 * _succao_media(xe) * l_m / corda
        m = {k: propriedades(k, esq, p.get("materiais")) for k in sorted({"balsa", "tubo_carbono", "spruce"})}
        i, t = AG._no_vao(sec_el, ym)
        zs, zi = (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]
        zln = AS.secao(el["estrutura"], xs, zs, zi, corda, ym, m)["zna"]
        r = CC.analisa_baia(esq, x["nome"], y0, y1, sigma, dp, imperf_t=_num(p, "imperfeicao_t", 0.5), z_LN=zln, E_transv=E_tr,
                            mats=p.get("materiais"), qualidade_balsa=qb)
        mb = propriedades("balsa", esq, p.get("materiais"), qb)
        cc, arco, area, Rr = _geom(sec_el, xs, Z, el, el["estrutura"], ym)
        ts = float(el["estrutura"]["chapeado"].get("espessura", 0.001))
        an_curvo = sigma_cr_curvo(mb["E"], E_tr, mb["G"], mb["nu"], ts, y1 - y0, arco, Rr, 1.0)
        r.update({"asa": x["nome"], "caso": caso["nome"], "corda": corda, "sustentacao_por_m": l_m, "fator_seguranca": sf, "z_LN": zln,
                  "analitico": {"sigma_cr_curvo_MPa": an_curvo / 1e6, "sigma_cr_plano_MPa": sigma_cr_ortotropica(mb["E"], E_tr, mb["G"], mb["nu"], ts, y1 - y0, arco) / 1e6,
                                "knockdown_sp8007": _fator_imperfeicao(None, Rr, ts), "margem_estimada": pn["margem_pele"]},
                  "margem_fe": (r["sigma_flambagem_MPa"] / (sigma / 1e6) - 1.0) if r.get("sigma_flambagem_MPa") else None})
        r["avisos"] = ["Baia isolada entre duas nervuras tidas como rigidas no proprio plano; a tensao de flexao vem da analise de viga e a "
                       "pressao e a da placa plana na regiao do chapeado, metade no extradorso (hipotese). Flambagem com imperfeicao: "
                       "o criterio e a pele sair uma espessura do lugar."]
        return r
    except (ValueError, FileNotFoundError, KeyError, StopIteration, RuntimeError) as e:
        return {"erro": _erro(e)}

def torcao(p: dict) -> dict:
    from ..nucleo.estrutura.torcao import analisa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        saidas = []
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            saidas.append(analisa(esq, e["nome"], mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                                  Vd=_vd(p), fator=_num(p, "margem_aeroelastica", 1.2, positivo=True),
                                  x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                  eficiencia=_num(p, "eficiencia_comando", 0.85, positivo=True), calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True),
                                  ea_desloc_c=_num(p, "ea_desloc_c", 0.0), calib_EI=_num(p, "calib_EI", 1.0, positivo=True)))
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        com_vr = [s for s in saidas if s["VR"] is not None]
        pior = min(com_vr, key=lambda s: s["VR"]) if com_vr else saidas[0]
        return {"asas": saidas, "pior": pior["nome"], "VR": pior["VR"], "V_requerida": pior["V_requerida"], "margem_VR": pior["margem_VR"],
                "avisos": sorted({a for s in saidas for a in s["avisos"]}) + _sem_longarina(esq)}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def torcao_fe(p: dict) -> dict:
    from ..nucleo.estrutura.asa_fe import verifica
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    c = cargas(p)
    if "erro" in c:
        return c
    esq = p.get("esquema") or {}
    try:
        saidas, avisos = [], []
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            achados = [(k, next((s for s in caso["superficies"] if s["nome"] == e["nome"]), None)) for k, caso in enumerate(c["casos"])]
            achados = [(k, s) for k, s in achados if s is not None]
            if not achados:
                continue
            k, sup = max(achados, key=lambda t: abs(t[1]["fletor_raiz"]))
            lado = sup["lados"].get("dir") or sup["lados"].get("esq")
            r = verifica(esq, e["nome"], lado, mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                         Vd=_vd(p), x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True),
                         cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True), calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True),
                         ea_desloc_c=_num(p, "ea_desloc_c", 0.0), calib_EI=_num(p, "calib_EI", 1.0, positivo=True))
            r["caso"] = c["casos"][k]["nome"]
            saidas.append(r)
            avisos += r["avisos"]
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        return {"asas": saidas, "vn": c["vn"], "massa_kg": c["massa_kg"], "avisos": sorted(set(avisos + c["avisos"]))}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def juncao(p: dict) -> dict:
    from ..nucleo.estrutura import juncao as JN
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    c = cargas(p)
    if "erro" in c:
        return c
    esq = p.get("esquema") or {}
    try:
        saidas, avisos = [], []
        tipos = tuple(p.get("tipos") or ("solda", "parafuso:x", "rotula"))
        for e in esq.get("elementos", []):
            if not _com_longarina(e) or (p.get("asa") and e["nome"] != p["asa"]):
                continue
            achados = [(k, next((s for s in caso["superficies"] if s["nome"] == e["nome"]), None)) for k, caso in enumerate(c["casos"])]
            achados = [(k, s) for k, s in achados if s is not None]
            if not achados:
                continue
            k, sup = max(achados, key=lambda t: abs(t[1]["fletor_raiz"]))
            lado = sup["lados"].get("dir") or sup["lados"].get("esq")
            try:
                r = JN.analisa(esq, e["nome"], lado, mats=p.get("materiais"), tipos=tipos, x_apoio=_num(p, "x_apoio", 0.30),
                               raio_ligacao=_num(p, "raio_ligacao", 0.06, positivo=True), fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True),
                               K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True), Vd=_vd(p), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                               calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True))
            except ValueError as x:
                avisos.append(f"{e['nome']}: {_erro(x)}")
                continue
            r["caso"] = c["casos"][k]["nome"]
            saidas.append(r)
            avisos += r["avisos"]
        if not saidas:
            return {"erro": "Nenhuma asa com longarina pôde ser ligada à treliça. " + " ".join(avisos)} if avisos else {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        return {"asas": saidas, "avisos": list(dict.fromkeys(avisos))}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def _massa_real(p: dict) -> dict | None:
    m = p.get("massa_real")
    if not m or not m.get("usar"):
        return None
    adic = []
    for a in m.get("adicionais") or []:
        b = {"nome": str(a.get("nome") or "adicional")}
        if a.get("asa"):
            b["asa"] = str(a["asa"])
        for k in ("massa_kg", "y_m", "y_fim_m", "x_c", "largura_c", "gramatura_g_m2", "de_xc", "ate_xc"):
            if a.get(k) not in (None, ""):
                b[k] = _num(a, k)
        if "massa_kg" not in b and "gramatura_g_m2" not in b:
            continue
        adic.append(b)
    med = {}
    for asa, d in (m.get("medidas") or {}).items():
        med[asa] = {k: _num(d, k, positivo=True) for k in ("massa_medida_kg", "x_cg_medido_c", "y_cg_medido_m") if d.get(k) not in (None, "")}
    return {"usar": True, "adicionais": adic, "medidas": med}

def massa_asa(p: dict) -> dict:
    from ..nucleo.estrutura.flutter import dados_de_vibracao, itens_de_massa, modos_de_vibracao
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        mr = _massa_real(p) or {"usar": True, "adicionais": []}
        asas = [e["nome"] for e in esq.get("elementos", []) if _com_longarina(e)]
        if not asas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        itens = itens_de_massa(esq)
        saidas = []
        decl = {e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "ponto"}
        pontos = [q for q in itens if q["nome"] in decl and abs(q["cg"][1]) > 0.05]
        for nome in asas:
            d = dados_de_vibracao(esq, nome, mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p),
                                  x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                  calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                  ea_desloc_c=_num(p, "ea_desloc_c", 0.0), itens=itens,
                                  massa_real=mr)
            ref = dados_de_vibracao(esq, nome, mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p),
                                    x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                    calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                    ea_desloc_c=_num(p, "ea_desloc_c", 0.0), itens=itens)
            pf = d["perfil_massa"]

            def freq(dd):
                c = dd["c"]
                xa = dd["x_alfa_c"] * c
                m = dd["m_lin"]
                return modos_de_vibracao(dd["y"], dd["EI"], dd["GJ"], m, m * xa, m * ((dd["r_giro_c"] * c) ** 2 + xa ** 2), 6)
            fr, f0 = freq(d), freq(ref)
            pf.update({"nome": nome, "f_hz": fr["f_hz"], "natureza": fr["natureza"], "f_hz_hipotese_antiga": f0["f_hz"], "natureza_hipotese_antiga": f0["natureza"],
                       "massa_hipotese_antiga_kg": ref["M"], "x_cg_c_hipotese_antiga": ref["xcg"]})
            saidas.append(pf)
        aviso = []
        if pontos:
            aviso.append("Massas pontuais do modelo fora do eixo (servo, motor na asa?): " + ", ".join(f"{q['nome']} ({q['massa']:.3f} kg em y = {q['cg'][1]:+.2f} m)" for q in pontos)
                         + ". Nao entram sozinhas: declare-as como adicionais da asa certa.")
        return {"asas": saidas, "avisos": aviso}
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def flutter(p: dict) -> dict:
    from ..nucleo.estrutura.flutter import analisa_flutter, itens_de_massa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        saidas = []
        itens = itens_de_massa(esq) if any(e.get("tipo") == "asa" and e.get("estrutura") for e in esq.get("elementos", [])) else None
        for e in esq.get("elementos", []):
            if not _com_longarina(e):
                continue
            saidas.append(analisa_flutter(esq, e["nome"], mats=p.get("materiais"), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                                          Vd=_vd(p), fator=_num(p, "margem_aeroelastica", 1.2, positivo=True),
                                          x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                          calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), ea_desloc_c=_num(p, "ea_desloc_c", 0.0),
                                          massa_asa_kg=_num(p, "massa_asa_kg", None, positivo=True) if p.get("massa_asa_kg") else None,
                                          x_cg_c=_num(p, "x_cg_c", None, positivo=True) if p.get("x_cg_c") else None,
                                          r_giro_c=_num(p, "r_giro_c", 0.28, positivo=True), zeta_s=_num(p, "zeta_s", 0.0),
                                          calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                          V_max_rel=_num(p, "V_max_rel", 3.0, positivo=True), n_modos=int(_num(p, "n_modos", positivo=True)) if p.get("n_modos") else None, itens=itens,
                                          massa_real=_massa_real(p), aileron=_aileron_par(p), varre=bool(p.get("varre_aileron")) and p.get("asa_varredura") in (None, e["nome"])))
        if not saidas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        com = [s for s in saidas if s["VF"] is not None]
        pior = min(com, key=lambda s: s["VF"]) if com else saidas[0]
        return {"asas": saidas, "pior": pior["nome"], "VF": pior["VF"], "V_requerida": pior["V_requerida"], "margem_VF": pior["margem_VF"],
                "avisos": sorted({a for s in saidas for a in s["avisos"]})}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def flutter_tempo(p: dict) -> dict:
    import time
    from ..nucleo.estrutura.flutter import itens_de_massa
    from ..nucleo.estrutura.flutter_tempo import analisa_no_tempo
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida
    esq = p.get("esquema") or {}
    try:
        asas = [e["nome"] for e in esq.get("elementos", []) if _com_longarina(e)]
        if not asas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        nome = p.get("asa") if p.get("asa") in asas else asas[0]
        itens = itens_de_massa(esq)
        t0 = time.time()
        extra = {}
        if p.get("fatores"):
            extra["fatores"] = tuple(float(x) for x in p["fatores"])
        if p.get("n_ciclos"):
            extra["n_ciclos"] = _num(p, "n_ciclos", positivo=True)
        r = analisa_no_tempo(esq, nome, rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p), **extra,
                             aileron=_aileron_par(p), zeta_s=_num(p, "zeta_s", 0.0),
                             n_modos=int(_num(p, "n_modos", positivo=True)) if p.get("n_modos") else None,
                             forcar=bool(p.get("forcar")), mats=p.get("materiais"),
                             fator=_num(p, "margem_aeroelastica", 1.2, positivo=True),
                             x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                             calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                             ea_desloc_c=_num(p, "ea_desloc_c", 0.0),
                             massa_asa_kg=_num(p, "massa_asa_kg", None, positivo=True) if p.get("massa_asa_kg") else None,
                             x_cg_c=_num(p, "x_cg_c", None, positivo=True) if p.get("x_cg_c") else None,
                             r_giro_c=_num(p, "r_giro_c", 0.28, positivo=True), itens=itens, massa_real=_massa_real(p))
        r["tempo_s"] = time.time() - t0
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}


def aeroelastica(p: dict) -> dict:
    from ..nucleo.estrutura.aeroelastica_estatica import estatica
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        A = AG.constroi(esq)
        mc = AG.massa_e_cg(A)
        massa = _num(p, "massa_kg", positivo=True) if p.get("massa_kg") is not None else mc["massa_kg"]
        if not massa or massa <= 0:
            return {"erro": "Sem massa: este modelo ainda nao tem pecas com massa. Abra o exemplo de biplano (botao Primeiros passos), declare a estrutura das asas na etapa 1 (aba Estrutura) ou informe a massa."}
        cg = mc["cg_m"]
        x_cg = float(p["x_cg"]) if p.get("x_cg") is not None else (float(cg[0]) if cg else None)
        if x_cg is None:
            return {"erro": "Sem CG: declare as pecas no modelo ou informe x_cg."}
        r = estatica(esq, V=_num(p, "V", positivo=True), n=_num(p, "n", 1.0, positivo=True), massa_kg=massa, x_cg=x_cg,
                     z_cg=float(cg[2]) if cg else 0.0, rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), mats=p.get("materiais"),
                     calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                     ea_desloc_c=_num(p, "ea_desloc_c", 0.0), x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True),
                     cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True))
        r["origem_massa"] = "informada" if p.get("massa_kg") is not None else "massas do modelo"
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def calibracao(p: dict) -> dict:
    from ..nucleo.estrutura.calibracao import calibra
    from ..nucleo.estrutura.flutter import itens_de_massa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        asas = [e["nome"] for e in esq.get("elementos", []) if _com_longarina(e)]
        if not asas:
            return {"erro": "Nenhuma asa com longarina declarada no modelo (aba Estrutura da asa, na etapa 1)."}
        nome = p.get("asa") or asas[0]
        if nome not in asas:
            return {"erro": f"A asa {nome!r} nao tem estrutura declarada."}
        r = calibra(esq, nome, p.get("observacoes") or {}, ajusta=tuple(p.get("ajusta") or ("EI", "GJ")), mats=p.get("materiais"),
                    rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vd=_vd(p), x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True),
                    cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True), ea_desloc_c=_num(p, "ea_desloc_c", 0.0),
                    massa_asa_kg=_num(p, "massa_asa_kg", None, positivo=True) if p.get("massa_asa_kg") else None,
                    x_cg_c=_num(p, "x_cg_c", None, positivo=True) if p.get("x_cg_c") else None,
                    r_giro_c=_num(p, "r_giro_c", 0.28, positivo=True), itens=itens_de_massa(esq), massa_real=_massa_real(p))
        r["asas"] = asas
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def cauda(p: dict) -> dict:
    from ..nucleo.estrutura.cauda import analisa
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        aviso = []
        c = cargas(p) if p.get("com_cargas", True) else {"erro": "nao pedidas"}
        if "erro" in c:
            casos, peso = None, _num(p, "peso_N", 0.0)
            aviso.append("Sem as cargas do V-n (" + str(c["erro"]) + "): o caso de trim da empenagem ficou em zero.")
        else:
            casos, peso = c["casos"], c["massa_kg"] * 9.80665
        r = analisa(esq, casos, peso_N=peso, rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True), Vc=_num(p, "Vc", positivo=True),
                    Vd=_vd(p), U_c=_num(p, "U_c", R.RAJADA_VC_MS, positivo=True),
                    fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True), x_apoio=_num(p, "x_apoio", 0.30),
                    CL_max_h=_num(p, "CL_max_h", 0.8, positivo=True), K_flambagem=_num(p, "K_flambagem", 1.0, positivo=True),
                    tailstrike_peso=_num(p, "tailstrike_peso", 0.0), mats=p.get("materiais"),
                    qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True),
                    juntas={k: _num(p, "junta_" + k, None) for k in ("tau_cola_MPa", "comprimento_cola_de", "Kt", "d_parafuso_mm", "tau_parafuso_MPa", "esmagamento_MPa") if p.get("junta_" + k) is not None})
        r["avisos"] = aviso + r["avisos"]
        r["peso_N"] = peso
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError) as e:
        return {"erro": _erro(e)}

def vibracao(p: dict) -> dict:
    from ..nucleo.aero import propulsao as PR
    from ..nucleo.estrutura import vibracao as VB
    from ..nucleo.estrutura.flutter import dados_de_vibracao, itens_de_massa, modos_de_vibracao
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        aviso = []
        rpm_v = None
        rpm_min, rpm_max = _num(p, "rpm_min", 3000.0, positivo=True), _num(p, "rpm_max", 9000.0, positivo=True)
        if p.get("motor") and p.get("helice"):
            try:
                cur = PR.curva(str(p["motor"]), str(p["helice"]), P_w=_num(p, "P_w", 600.0, positivo=True), rho=_num(p, "rho", 1.1, positivo=True),
                               V_max=_num(p, "V_max", 30.0, positivo=True), realista=bool(p.get("realista", True)))
            except ValueError as e:
                return {"erro": _erro(e)}
            if "erro" in cur:
                return cur
            rpm_v = {"V": cur["V"], "rpm": cur["rpm"]}
            rpm_min, rpm_max = float(min(cur["rpm"])), float(max(cur["rpm"]))
            aviso.append(f"Faixa de rotacao da curva do motor com a helice: {rpm_min:.0f} a {rpm_max:.0f} rpm (de parado ate {_num(p, 'V_max', 30.0):g} m/s).")
        externos = []
        if p.get("incluir_asas", True):
            mr = _massa_real(p) or {"usar": True, "adicionais": []}
            itens = itens_de_massa(esq)
            for e in esq.get("elementos", []):
                if e.get("tipo") != "asa" or not e.get("estrutura"):
                    continue
                try:
                    d = dados_de_vibracao(esq, e["nome"], mats=p.get("materiais"), rho=_num(p, "rho", 1.1, positivo=True), Vd=_num(p, "Vd", 15.9, positivo=True),
                                          x_ca_c=_num(p, "x_ca_c", 0.25, positivo=True), cl_alpha_2d=_num(p, "cl_alpha_2d", 6.2832, positivo=True),
                                          calib_GJ=_num(p, "calib_GJ", 1.0, positivo=True), calib_EI=_num(p, "calib_EI", 1.0, positivo=True),
                                          ea_desloc_c=_num(p, "ea_desloc_c", 0.0), itens=itens, massa_real=mr)
                except ValueError as ex:
                    aviso.append(f"“{e['nome']}” ficou fora dos modos externos: {_erro(ex)}.")
                    continue
                c = d["c"]; xa = d["x_alfa_c"] * c; m_ = d["m_lin"]
                fr = modos_de_vibracao(d["y"], d["EI"], d["GJ"], m_, m_ * xa, m_ * ((d["r_giro_c"] * c) ** 2 + xa ** 2), 3)
                for k, (f, nat) in enumerate(zip(fr["f_hz"], fr["natureza"])):
                    externos.append({"nome": f"{e['nome']} {k + 1} ({'flexao' if nat == 'flexao' else 'torcao'})", "f_hz": float(f), "natureza": nat})
        pos_motor = p.get("pos_motor")
        if pos_motor is not None and (not isinstance(pos_motor, (list, tuple)) or len(pos_motor) != 3):
            return {"erro": "“pos_motor” precisa ser [x, y, z] em metros."}
        adic = [a for a in (p.get("adicionais") or []) if isinstance(a, dict)]
        r = VB.analisa(esq, massa_empenagem_h_kg=_num(p, "massa_empenagem_h_kg", 0.0), massa_deriva_kg=_num(p, "massa_deriva_kg", 0.0),
                       massa_motor_kg=_num(p, "massa_motor_kg", 0.0), pos_motor=pos_motor, adicionais=adic, rpm_min=rpm_min, rpm_max=rpm_max,
                       n_pas=int(_num(p, "n_pas", 2.0, positivo=True)), ordens_extra=[_num({"k": k}, "k", positivo=True) for k in (p.get("ordens_extra") or [])],
                       margem_min=_num(p, "margem_min", 0.20, positivo=True), x_apoio=_num(p, "x_apoio", 0.30), mats=p.get("materiais"),
                       qualidade_carbono=_num(p, "qualidade_carbono", 1.0, positivo=True), raio_motor=_num(p, "raio_motor", 0.15, positivo=True),
                       n_modos=int(_num(p, "n_modos", 8.0, positivo=True)), suporte_motor=p.get("suporte_motor") or None, modos_externos=externos, rpm_v=rpm_v)
        r["avisos"] = aviso + r["avisos"]
        r["rpm_v"] = rpm_v
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def nervuras_posicoes(p: dict) -> dict:
    from ..nucleo.estrutura import nervuras as NV
    from ..nucleo.modelador import aeronave_geometria as AG
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        nome = p.get("asa")
        if not nome:
            asas = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa"]
            if not asas:
                return {"erro": "Nenhuma asa no modelo."}
            nome = asas[0]
        if p.get("y") is not None:
            el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome and e.get("tipo") == "asa"), None)
            if el is None:
                return {"erro": f"asa {nome!r} nao existe no modelo"}
            ys = [q[1] for q in AG._secoes(el)]
            valores = [_num({"v": v}, "v") for v in p["y"]]
            completa = AG._nervuras_y(valores, ys)
            simetrica = ys[0] < -1e-9 and ys[-1] > 1e-9 and abs(ys[0] + ys[-1]) < 1e-6 * max(abs(ys[0]), abs(ys[-1]))
            r = {"y": valores, "simetrica": bool(simetrica), "completa": [float(v) for v in completa], "passos_mm": [1000.0 * float(b - a) for a, b in zip(completa, completa[1:])]}
        else:
            r = NV.posicoes(esq, str(nome), int(_num(p, "n", 8.0, positivo=True)), str(p.get("lei", "uniforme")), _num(p, "expoente", 1.6, positivo=True))
        r["asa"] = nome
        r["passo_max_mm"] = max(r["passos_mm"], default=0.0)
        r["passo_min_mm"] = min(r["passos_mm"], default=0.0)
        r["n_total"] = len(r["completa"])
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}


def nervuras_dxf(p: dict) -> dict:
    from ..nucleo.estrutura import nervuras as NV
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        com = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa" and (e.get("estrutura") or {}).get("nervuras")]
        if not com:
            return {"erro": "Nenhuma asa com nervuras declaradas (estrutura.nervuras.y) no modelo."}
        nome = p.get("asa") or com[0]
        conj = NV.pecas(esq, str(nome), kerf_mm=_num(p, "kerf_mm", 0.0), folga_tubo_mm=_num(p, "folga_tubo_mm", 0.1), folga_longarina_mm=_num(p, "folga_longarina_mm", 0.1),
                        bf_min_mm=_num(p, "bf_min_mm", 1.0), recesso_chapeado=bool(p.get("recesso_chapeado", True)), parede_min_mm=_num(p, "parede_min_mm", 1.2))
        org = NV.organiza(conj, (_num(p, "folha_largura_mm", 600.0, positivo=True), _num(p, "folha_altura_mm", 300.0, positivo=True)), espaco_mm=_num(p, "espaco_mm", 4.0))
        texto = NV.dxf(conj, org, folha=bool(p.get("moldura", True)), rotulos=bool(p.get("rotulos", True)))
        W = org["folha_mm"][0]
        pecas = []
        for n in conj["nervuras"]:
            for q in n["pecas"]:
                ox, oy = q["pos"]
                pecas.append({"nome": q["nome"], "i": n["i"], "y_m": n["y_m"], "angulo": n.get("angulo", 0.0), "folha": q["folha"], "contorno": [[x + ox, z + oy] for x, z in q["contorno"]],
                              "furos": [{"c": [f["c"][0] + ox, f["c"][1] + oy], "d": f["d"], "dx": f.get("dx", f["d"])} for f in q["furos"]], "largura_mm": q["x1"] - q["x0"], "altura_mm": q["z1"] - q["z0"],
                              "area_mm2": q["area_mm2"]})
        return {"asa": conj["asa"], "asas": com, "dxf": texto, "espessura_mm": conj["espessura_mm"], "material": conj["material"], "n_nervuras": len(conj["nervuras"]),
                "n_pecas": len(pecas), "pecas": pecas, "folhas": org["folhas"], "folha_mm": org["folha_mm"], "avisos": conj["avisos"] + org["avisos"],
                "area_total_cm2": sum(q["area_mm2"] for q in pecas) / 100.0}
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def planificacao(p: dict) -> dict:
    from ..nucleo.estrutura import planifica as PL
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        com = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa" and (e.get("estrutura") or {}).get("chapeado")]
        if not com:
            return {"erro": "Nenhuma asa com chapeado declarado (estrutura.chapeado) no modelo. Declare na aba Estrutura da asa até onde a pele vai."}
        nome = str(p.get("asa") or com[0])
        modo = str(p.get("modo") or "auto")
        lim = p.get("limite_pct")
        conj = PL.faixas(esq, nome, modo=modo, n_vao=int(_num(p, "n_vao", 6.0, positivo=True)), limite_pct=(None if lim in (None, "", 0) else float(lim)), margem_cola_mm=_num(p, "margem_cola_mm", 5.0),
                        cortes_y=[float(c) / 1000.0 for c in (p.get("cortes_y_mm") or [])], modos={str(k): str(m) for k, m in (p.get("modos") or {}).items() if m})
        org = PL.organiza(conj, (_num(p, "folha_largura_mm", 1000.0, positivo=True), _num(p, "folha_altura_mm", 300.0, positivo=True)), espaco_mm=_num(p, "espaco_mm", 6.0))
        texto = PL.dxf(conj, org, folha=bool(p.get("moldura", True)), rotulos=bool(p.get("rotulos", True)))
        W = org["folha_mm"][0]
        chapas = []
        for c in org["colocados"]:
            it, q = c["item"], c["item"]["p"]
            origem = [min(a[0] for a in q["contorno"]), min(a[1] for a in q["contorno"])]
            cont = [[(it["w"] - (a[0] - origem[0]) if c["espelho"] else a[0] - origem[0]) + c["pos"][0], a[1] - origem[1] + c["pos"][1]] for a in q["contorno"]]
            f = conj["faixas"][it["faixa"] - 1]
            chapas.append({"rot": it["rot"], "faixa": it["faixa"], "folha": c["folha"], "espelho": c["espelho"], "status": f["status"], "contorno": cont,
                           "largura_mm": it["w"], "altura_mm": it["h"], "deformacao_max_pct": q["deformacao_max_pct"]})
        faixas = []
        for i, f in enumerate(conj["faixas"], 1):
            faixas.append({"i": i, "y0_m": f["y0_m"], "y1_m": f["y1_m"], "quantidade": f["quantidade"], "modo": f["modo"], "modo_pedido": f["modo_pedido"], "chave": f["chave"], "status": f["status"], "deformacao_max_pct": f["deformacao_max_pct"],
                           "pecas": [{k: q[k] for k in ("nome", "largura_mm", "altura_mm", "area_mm2", "area3d_mm2", "deformacao_max_pct", "deformacao_media_pct", "defeito_angular_max_graus",
                                                     "curvatura_total_rad", "var_area_max_pct", "v", "estr", "contorno", "m1", "nk", "linha_bordo_ataque")} for q in f["pecas"]]})
        resumo = {s: sum(1 for f in conj["faixas"] if f["status"] == s) for s in ("ok", "atencao", "nao")}
        return {"asa": nome, "asas": com, "material": conj["material"], "limite_pct": conj["limite_pct"], "ate_xc": conj["ate_xc"], "n_vao": conj["n_vao"], "faixas": faixas, "chapas": chapas, "mapa": conj["mapa"],
                "folhas": org["folhas"], "folha_mm": org["folha_mm"], "resumo": resumo, "dxf": texto, "avisos": conj["avisos"] + org["avisos"]}
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def secoes(p: dict) -> dict:
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida
    from ..nucleo.modelador.secoes import secoes_da_asa

    esq = p.get("esquema") or {}
    try:
        nome = p.get("asa")
        if not nome:
            return {"erro": "Informe a asa."}
        return secoes_da_asa(esq, str(nome))
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def _cargas(p: dict) -> dict:
    from ..nucleo.aero.equilibrio import monta
    from ..nucleo.aero.estabilidade import derivadas
    from ..nucleo.aero.limites import cl_max as cl_max_aeronave
    from ..nucleo.estrutura.cargas import casos_de_carga
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        rho = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
        Vc = _num(p, "Vc", positivo=True)
        Vd = _vd(p)
        if Vd <= Vc:
            return {"erro": "Vd precisa ser maior que Vc."}
        A = AG.constroi(esq)
        mc = AG.massa_e_cg(A)
        massa = _num(p, "massa_kg", positivo=True) if p.get("massa_kg") is not None else mc["massa_kg"]
        if not massa or massa <= 0:
            return {"erro": "Sem massa: este modelo ainda nao tem pecas com massa. Abra o exemplo de biplano (botao Primeiros passos), declare a estrutura das asas na etapa 1 (aba Estrutura) ou informe a massa."}
        cg = mc["cg_m"]
        x_cg = float(p["x_cg"]) if p.get("x_cg") is not None else (float(cg[0]) if cg else None)
        z_cg = float(cg[2]) if cg else 0.0
        if x_cg is None:
            return {"erro": "Sem CG: declare as pecas no modelo ou informe x_cg."}
        vlm = monta(esq, x_cg, z_cg)
        d = derivadas(vlm, 3.0, V=Vc, rho=rho, laterais=False)
        avisos = []
        if p.get("CL_max") is not None:
            clm, origem = _num(p, "CL_max", positivo=True), "voce"
        else:
            ncrit = int(_num(p, "ncrit", 4.0, positivo=True))
            chave = (json.dumps(esq, sort_keys=True, default=str), round(x_cg, 6), round(Vc, 3), round(rho, 4), ncrit)
            if chave not in _CL_MAX:
                if len(_CL_MAX) > 8:
                    _CL_MAX.clear()
                _CL_MAX[chave] = float(cl_max_aeronave(esq, x_cg, V=Vc, rho=rho, ncrit=ncrit, com_solo=False)["CL_max"])
            clm, origem = _CL_MAX[chave], "teoria de faixas (polares do banco)"
        sai = casos_de_carga(esq, x_cg, z_cg, massa, rho, clm, float(d.CL_alpha), float(vlm.c_ref), float(vlm.S_ref), Vc, Vd,
                             n_max=None if p.get("n_max") is None else _num(p, "n_max", positivo=True),
                             n_min=None if p.get("n_min") is None else _num(p, "n_min"),
                             U_c=_num(p, "U_c", R.RAJADA_VC_MS, positivo=True), U_d=_num(p, "U_d", R.RAJADA_VD_MS, positivo=True),
                             fator_seguranca=_num(p, "fator_seguranca", R.FATOR_SEGURANCA, positivo=True),
                             cl_min_rel=_num(p, "cl_min_rel", 0.5, positivo=True))
        for c in sai["casos"]:
            if c["CL"] > clm * 1.001:
                avisos.append(f"{c['nome']}: o CL pedido ({c['CL']:.2f}) passa do CL maximo ({clm:.2f}): a aeronave estola antes; "
                              "a carga real e menor que a calculada.")
        sai["avisos"] = avisos + sai["avisos"]
        sai.update(massa_kg=massa, origem_CL_max=origem, origem_massa="informada" if p.get("massa_kg") is not None else "massas do modelo")
        return sai
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def _args_dinamica(p: dict) -> dict:
    I = {k: _num(p["inercias"], k) for k in ("Ixx", "Iyy", "Izz", "Ixz") if (p.get("inercias") or {}).get(k) is not None}
    if I and len(I) < 4 and not all(k in I for k in ("Ixx", "Iyy", "Izz")):
        raise ValueError("Informe Ixx, Iyy e Izz (e Ixz, ou zero), ou deixe todas vazias para usar as do modelo.")
    I = ({"Ixz": 0.0, **I} if I else None)
    raios = ({k: _num(p["raios"], k, positivo=True) for k in ("rx", "ry", "rz") if (p.get("raios") or {}).get(k) is not None}
             if p.get("raios") is not None else None)
    return dict(x_cg=None if p.get("x_cg") is None else _num(p, "x_cg"), V=_num(p, "V", positivo=True),
                rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True),
                massa_kg=None if p.get("massa_kg") is None else _num(p, "massa_kg", positivo=True), I=I,
                raios=raios, modo_inercia=str(p.get("modo_inercia") or "auto"))

def dinamica(p: dict) -> dict:
    from ..nucleo.aero.dinamica import dinamica as din
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    try:
        return din(p.get("esquema") or {}, **_args_dinamica(p))
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def comandos(p: dict) -> dict:
    from ..nucleo.aero.dinamica import comandos_disponiveis

    return {"comandos": comandos_disponiveis(p.get("esquema") or {})}

def resposta_comando(p: dict) -> dict:
    from ..nucleo.aero.dinamica import resposta_a_comando
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    try:
        return resposta_a_comando(p.get("esquema") or {}, str(p.get("controle") or ""),
                                  deflexao_graus=_num(p, "deflexao_graus", 10.0),
                                  duracao_s=_num(p, "duracao_s", 0.3, positivo=True),
                                  **_args_dinamica(p))
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def controle(p: dict) -> dict:
    from ..nucleo.aero.controle import autoridade_rolagem
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    try:
        return autoridade_rolagem(p.get("esquema") or {}, **_args_dinamica(p),
                                  sobe_max=_num(p, "sobe_max", 30.0, positivo=True), desce_max=_num(p, "desce_max", 25.0, positivo=True),
                                  pb2V_min=_num(p, "pb2V_min", 0.05, positivo=True),
                                  t_inclinacao_max=_num(p, "t_inclinacao_max", 1.5, positivo=True),
                                  inclinacao=_num(p, "inclinacao", 30.0, positivo=True), beta=_num(p, "beta", 0.0),
                                  ncrit=int(_num(p, "ncrit", 4.0, positivo=True)), V_servo=_num(p, "V_servo", 18.0, positivo=True))
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}


def uvlm(p: dict) -> dict:
    import time
    import warnings
    from ..nucleo.aero import rll as RL
    from ..nucleo.aero import uvlm as U
    from ..nucleo.aero.aeronave_vlm import superficies
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        if p.get("V") is None:
            raise ErroDeAnalise("Informe a velocidade (ou a Vc na vista Cargas).")
        V = _num(p, "V", positivo=True)
        rho = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
        alpha = _num(p, "alpha", 0.0)
        caso = p.get("caso", "degrau")
        if caso not in ("degrau", "rajada_degrau", "rajada_1cos", "mergulho", "arfagem"):
            raise ErroDeAnalise("Caso desconhecido: use degrau, rajada_degrau, rajada_1cos, mergulho ou arfagem.")
        esteira = p.get("esteira") or ("livre" if p.get("esteira_livre") else "rigida")
        if esteira not in ("rigida", "livre", "particulas"):
            raise ErroDeAnalise("Esteira: use rigida, livre ou particulas.")
        gira = bool(p.get("helice_girante"))
        avisos_pre = []
        solo_on = bool(p.get("solo"))
        subida = _num(p, "subida", 0.0) if solo_on else 0.0
        if solo_on and subida != 0 and esteira == "rigida":
            avisos_pre.append("Efeito solo com a altura mudando: a esteira rígida não acompanha o chão se movendo, então virou livre.")
            esteira = "livre"
        if gira and esteira != "particulas":
            avisos_pre.append("Hélice girante: a esteira dela é de partículas, então a da asa também virou partículas.")
            esteira = "particulas"
        livre = esteira != "rigida"
        manual = p.get("discretizacao") == "manual"
        H_cordas = _num(p, "H_cordas", 25.0, positivo=True) if caso == "rajada_1cos" else None
        f = _num(p, "f", 5.0, positivo=True) if caso in ("mergulho", "arfagem") else None
        with warnings.catch_warnings(), D.silencio():
            warnings.simplefilter("ignore")
            pre = U.VLM(superficies(esq, n_span=8, n_chord=2))
        c_pre = pre.c_ref
        auto = U.discretizacao_auto(caso, k=(math.pi * f * c_pre / V) if f else None, H_cordas=H_cordas, esteira_livre=livre, esteira=esteira)
        if solo_on and subida != 0:
            auto["espera_cordas"] = (8.0, "a partida impulsiva assenta (Wagner ≈ 95 %) antes de a altura começar a mudar")
        if gira:
            auto.update(RL.discretizacao_auto())
            centro_h = _centro_helice(esq)
            x_fim = float(pre.aneis[..., 0].max())
            if caso == "degrau":
                n_c = int(max(8, math.ceil(max(0.0, x_fim - float(centro_h[0])) / c_pre + 3)))
                auto["cordas"] = (n_c, f"hélice girante: o sopro leva {max(0.0, x_fim - float(centro_h[0])) / c_pre:.1f} cordas "
                                       "para passar pela última superfície; + 3 cordas, no mínimo 8 (Wagner a ~90 %)")
        escolha = []

        def campo(chave, rotulo, inteiro=True):
            va, motivo = auto.get(chave, (None, ""))
            if manual and p.get(chave) is not None:
                x = _num(p, chave, positivo=True)
                x = int(round(x)) if inteiro else x
                escolha.append({"campo": chave, "rotulo": rotulo, "valor": x, "origem": "manual", "auto": va, "motivo": motivo})
                return x
            escolha.append({"campo": chave, "rotulo": rotulo, "valor": va, "origem": "auto", "auto": va, "motivo": motivo})
            return va

        ns = campo("n_span", "Painéis na envergadura")
        nc = campo("n_chord", "Painéis na corda")
        nc_auto = escolha[-1]["origem"] == "auto"
        with warnings.catch_warnings(), D.silencio():
            warnings.simplefilter("ignore")
            faixas = U.VLM(superficies(esq, n_span=ns, n_chord=1)).N
        por_corda = campo("passos_por_corda", "Passos por corda")
        if caso in ("mergulho", "arfagem"):
            ciclos = campo("ciclos", "Ciclos", inteiro=False)
            cordas = None
        else:
            cordas = campo("cordas", "Duração (cordas)", inteiro=False)
        if esteira == "particulas":
            fil_aneis = campo("fileiras_aneis", "Fileiras de anéis antes das partículas")
            idade_fusao = campo("idade_fusao", "Idade da 1ª fusão de partículas (passos)")
            sobre = campo("sobreposicao", "Núcleo das partículas (× V·dt)", inteiro=False)
            max_fil, fil_livres = None, None
        else:
            max_fil = campo("max_fileiras", "Fileiras de esteira (antes da cauda)")
            fil_livres = campo("fileiras_livres", "Fileiras que enrolam") if livre else None
        nucleo = campo("nucleo", "Núcleo dos vórtices (× corda)", inteiro=False)
        if gira:
            nome_h, cat_h, pa_h, perfil_h, _ = _helice_catalogo(p)
            rpm = _num(p, "rpm", 4000.0, positivo=True)
            sentido = -1 if p.get("sentido") in (-1, "-1", "anti") else 1
            dpsi = campo("dpsi", "Giro da hélice por subpasso (graus)", inteiro=False)
            n_el = campo("n_el", "Elementos por pá")
            rolagem = campo("voltas_rolagem", "Enrolamento da esteira da hélice (voltas)", inteiro=False)
            Om = 2 * math.pi * rpm / 60.0
            comp_h = max(x_fim + 0.5 * pre.b_ref - float(centro_h[0]), 4 * pa_h.R)
        nuc_part = p.get("nucleo_particula") if (manual and p.get("nucleo_particula") in ("gaussiano", "winckelmans")) else "gaussiano"

        def passos_de(ppc):
            return int(math.ceil(ciclos * math.pi / (math.pi * f * c_pre / V) * ppc)) if cordas is None else int(math.ceil(cordas * ppc))

        def custo(nc_):
            if gira:
                dt_ = c_pre / (por_corda * V)
                n_sub = max(1, int(round(dt_ * Om / math.radians(dpsi))))
                dts = dt_ / n_sub
                return D.custo_rll(nc_ * faixas, faixas, passos_de(por_corda), n_sub, pa_h.B, n_el,
                                   rolagem * 2 * math.pi / (Om * dts), int(math.ceil(comp_h / (V * dts))), fil_aneis, idade_fusao)
            if esteira == "particulas":
                return D.custo_vpm(nc_ * faixas, faixas, passos_de(por_corda), fil_aneis, idade_fusao)
            return D.custo_uvlm(nc_ * faixas, faixas, passos_de(por_corda), max_fil, livre, fil_livres)
        if solo_on:
            custo_sem_solo = custo

            def custo(nc_):
                c_ = dict(custo_sem_solo(nc_))
                c_["segundos"] *= 2.0; c_["interacoes"] *= 2.0
                return c_
        est = custo(nc)
        if nc_auto and est["segundos"] > D.orcamento_s() and nc > 4:
            nc0 = nc
            while nc > 4 and custo(nc)["segundos"] > D.orcamento_s():
                nc -= 1
            escolha[1]["valor"] = nc
            escolha[1]["motivo"] += f"; reduzido de {nc0} para {nc} para caber no orçamento de {D.orcamento_s():.0f} s"
            est = custo(nc)
        try:
            D.confere_orcamento(est, "Marcha do UVLM" + (" com a hélice girante" if gira else ""), forcar=bool(p.get("forcar")))
        except ValueError as e:
            if not gira:
                raise
            raise ErroDeAnalise(f"{e} Com a hélice girante o custo vem do tempo físico × rpm / giro por subpasso, com "
                                f"~{est['particulas']} partículas no fim: duração mais curta ou giro de 20° (modo manual; o "
                                "sopro sai ~14 % fraco) cortam o tempo.") from None
        with warnings.catch_warnings(record=True) as avisos_malha:
            warnings.simplefilter("always")
            sup = superficies(esq, n_span=ns, n_chord=nc)
            base = U.VLM(sup)
        c = base.c_ref
        dt = c / (por_corda * V)
        n_passos = int(math.ceil(cordas * por_corda)) if cordas else 0
        x_le = float(base.aneis[..., 0].min())
        x_ref = _num(p, "x_ref", x_le + 0.25 * c) if p.get("x_ref") is not None else x_le + 0.25 * c
        altura_fn = None
        if solo_on:
            from ..nucleo.aero import limites as LI
            if p.get("altura_solo") is not None:
                h0 = _num(p, "altura_solo", positivo=True); origem_h = "informada"
            else:
                h0 = LI.altura_do_solo(esq, alpha, x_ref)
                if h0 is None or h0 <= 0:
                    raise ErroDeAnalise("Efeito solo: informe a altura do solo (o modelo não tem rodas para medir).")
                origem_h = "pelas rodas"
            esp = campo("espera_cordas", "Espera antes de mudar a altura (cordas)", inteiro=False) if subida != 0 else 0.0
            t_esp = esp * c / V

            def altura_fn(t, h0=h0, vs=subida, t_esp=t_esp):
                return h0 + vs * max(0.0, t - t_esp)
            if subida == 0:
                altura_fn = h0
        mov = raj = None
        alpha_corrida = alpha
        ref = {}
        CLa = (base.resolver([1.0], V=V, rho=rho)[0].CL - base.resolver([0.0], V=V, rho=rho)[0].CL) * 180 / math.pi
        if caso == "degrau":
            pass
        elif caso in ("rajada_degrau", "rajada_1cos"):
            w0 = _num(p, "w0", 2.0)
            if caso == "rajada_degrau":
                raj = U.rajada_degrau(w0, V, x_le)
            else:
                H = H_cordas * c
                raj = U.rajada_1_cos(w0, H, V, x_le)
                if cordas < H_cordas:
                    avisos_pre.append(f"A duração ({cordas:g} cordas) acaba antes da rajada passar ({H_cordas:g} cordas).")
        else:
            amp = _num(p, "amplitude", 0.02 if caso == "mergulho" else 2.0, positivo=True)
            n_passos = int(math.ceil(ciclos / (f * dt)))
            mov = U.movimento_mergulho(amp, f) if caso == "mergulho" else U.movimento_arfagem(amp, f, x_ref, V)
        avisos = list(avisos_pre)
        if solo_on and subida != 0 and n_passos * dt <= t_esp:
            avisos.append(f"A duração ({n_passos * dt:.3f} s) acaba antes de a altura começar a mudar ({t_esp:.3f} s de espera).")
        if gira:
            t_sopro = (x_fim - float(centro_h[0])) / V
            dur = n_passos * dt
            if dur < t_sopro:
                avisos.append(f"A duração ({dur:.3f} s) acaba antes do sopro da hélice passar pela última superfície "
                              f"(~{t_sopro:.3f} s): aumente a duração para ver o regime.")
        if caso in ("mergulho", "arfagem"):
            k_red = math.pi * f * c / V
            err = 1.2 * k_red / nc
            if err > 0.05:
                avisos.append(f"Frequência reduzida k = {k_red:.2f} com {nc} painéis na corda: a amplitude do CL deve sair "
                              f"uns {100 * err:.0f} % acima da teoria (erro ≈ 1,2 k / n_chord). {math.ceil(24 * k_red)} painéis dão 5 %.")
        t0 = time.time()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if gira:
                u = RL.UVLMHelice(sup, V, [{"pa": pa_h, "centro": centro_h, "rpm": rpm, "sentido": sentido, "n_el": n_el}],
                                  alpha_graus=alpha_corrida, rho=rho, dt=dt, x_ref=x_ref, movimento=mov, rajada=raj,
                                  nucleo=nucleo, fileiras_aneis=fil_aneis, idade_fusao=idade_fusao, sobreposicao=sobre,
                                  nucleo_particula=nuc_part, dpsi_graus=dpsi, voltas_rolagem=rolagem,
                                  comprimento_esteira=comp_h, solo=altura_fn)
            elif esteira == "particulas":
                u = U.UVLMParticulas(sup, V=V, alpha_graus=alpha_corrida, rho=rho, dt=dt, x_ref=x_ref, movimento=mov, rajada=raj,
                                     nucleo=nucleo, fileiras_aneis=fil_aneis, idade_fusao=idade_fusao, sobreposicao=sobre,
                                     nucleo_particula=nuc_part, solo=altura_fn)
            else:
                u = U.UVLM(sup, V=V, alpha_graus=alpha_corrida, rho=rho, dt=dt, esteira_livre=livre, x_ref=x_ref,
                           movimento=mov, rajada=raj,
                           max_fileiras=max_fil, fileiras_livres=fil_livres, nucleo=nucleo, solo=altura_fn)
            inst = p.get("_instantaneos")
            if inst is None and p.get("instantaneos"):
                inst = []
            alvo = 150 if p.get("_instantaneos") is not None else 60
            h = u.roda(n_passos, a_cada=(n_passos / alvo if gira else max(1, math.ceil(n_passos / alvo))) if inst is not None else None,
                       guarda=inst)
            if inst is not None:
                p["_aneis_corpo"] = u.R.copy()
        t = np.array(h.t); s = 2 * V * t / c
        CL0 = base.resolver([alpha], V=V, rho=rho)[0].CL
        CL_livre = CL0
        if solo_on:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                def cl_solo(h, a):
                    return U.VLM(sup, x_ref=x_ref, altura_solo=h).resolver([a], V=V, rho=rho)[0].CL
                CL0 = cl_solo(h0, alpha)
                if subida != 0:
                    ts = np.linspace(t[0], t[-1], 13)
                    qs = [cl_solo(altura_fn(ti), alpha - math.degrees(math.atan2(subida if ti > t_esp else 0.0, V))) for ti in ts]
                    qs_t = np.interp(t, ts, qs)
        if caso == "degrau" and solo_on and subida != 0:
            ref = {"nome": "quase estático: VLM com solo em h(t) e α − γ, × Wagner", "y": (qs_t * U.wagner(s)).tolist()}
        elif caso == "degrau":
            ref = {"nome": "Wagner × CL estacionário" + (" com solo" if solo_on else ""), "y": (CL0 * U.wagner(s)).tolist()}
        elif caso == "rajada_degrau":
            ref = {"nome": "Küssner × CLα w0/V", "y": (CL0 + CLa * (w0 / V) * U.kussner(s)).tolist()}
        elif caso == "mergulho":
            w = 2 * math.pi * f; k = w * c / (2 * V); C = complex(U.theodorsen(k))
            hd = amp * w * np.cos(w * t); hdd = -amp * w * w * np.sin(w * t)
            circ = -(C.real * hd - C.imag * amp * w * np.sin(w * t)) / V
            ref = {"nome": "Theodorsen (faixa 2D × CLα 3D/2π)", "y": (CL0 + CLa * circ + CLa / (2 * math.pi) * math.pi * (c / 2) * (-hdd) / V ** 2).tolist(), "k": k}
        Rw, Gw = u.aneis_da_esteira()
        lado = []
        for si in u.te:
            nos = np.array(si["nos"])
            if si.get("cortada"):
                nos = nos[:-1]
            j = [0, nos.shape[1] // 2, nos.shape[1] - 1]
            lado.append({"nome": si["nome"], "x": nos[:, j, 0].T.tolist(), "z": nos[:, j, 2].T.tolist(), "y": nos[0, j, 1].tolist()})
        dec = max(1, len(t) // 400)
        extra = {"V": V, "esteira": esteira}
        if p.get("instantaneos") and p.get("_instantaneos") is None and inst:
            extra["quadros"] = _compacta_quadros(inst, u.R)
        if esteira == "particulas":
            X, A = u.part.X, u.part.A
            w = np.linalg.norm(A, axis=1)
            k = np.argsort(-w)[:4000] if len(w) > 4000 else np.arange(len(w))
            extra["particulas"] = {"x": X[k, 0].tolist(), "y": X[k, 1].tolist(), "z": X[k, 2].tolist(), "w": w[k].tolist(),
                                   "n": int(len(w)), "vorticidade_total": u.part.vorticidade_total().tolist(),
                                   "sigma_medio": float(u.part.S.mean()) if len(w) else None}
        if gira:
            from ..nucleo.aero import bemt as BM
            hh = u.hist_helice[0]
            hl = u.helices[0]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ref_h = BM.analisa(pa_h, V, rpm, rho, n_est=D.helice_n_est())
            dec_h = max(1, len(hh["t"]) // 400)
            n_ult = max(1, int(round(2 * math.pi / (Om * dt))))
            extra["helice"] = {"nome": nome_h, "perfil": perfil_h, "rpm": rpm, "sentido": sentido, "D": pa_h.D,
                               "centro": centro_h.tolist(), "n_sub": u.n_sub, "dpsi": math.degrees(Om * u.dt_sub),
                               "t": hh["t"][::dec_h], "T": hh["T"][::dec_h], "P": hh["P"][::dec_h],
                               "T_media": float(np.mean(hl.hist["T"][-n_ult * u.n_sub:])),
                               "P_media": float(np.mean(hl.hist["P"][-n_ult * u.n_sub:])),
                               "T_bemt": ref_h.T, "P_bemt": ref_h.P, "J": ref_h.J,
                               "particulas": int(np.sum(u.part.fila >= RL.ID_HELICE)),
                               "comprimento_esteira": u.comprimento_esteira}
        if caso.startswith("rajada"):
            extra["w0"] = w0
        if caso in ("mergulho", "arfagem"):
            extra["k"] = math.pi * f * c / V
        for e in escolha:
            if e["campo"] == "n_span" and e["valor"] is None:
                e["valor"] = ", ".join(f"{q.nome} {q.n_span}" for q in sup)
        extra["estimativa_s"] = est["segundos"]
        if solo_on:
            hs = [altura_fn(ti) for ti in t] if callable(altura_fn) else [h0] * len(t)
            extra["solo"] = {"h0": h0, "origem": origem_h, "subida": subida, "espera_s": t_esp, "CL_livre": CL_livre,
                             "CL_solo": CL0, "h": hs[::dec], "b": float(base.b_ref)}
        return {**extra, "discretizacao": escolha, "modo_discretizacao": "manual" if manual else "auto", "caso": caso, "t": t[::dec].tolist(), "s": s[::dec].tolist(), "CL": h.CL[::dec], "CD": h.CD[::dec], "Cm": h.Cm[::dec],
                "ref": ({k: (v[::dec] if isinstance(v, list) else v) for k, v in ref.items()} if ref else None),
                "CL_estacionario": CL0, "CL_alpha": CLa, "c_ref": c, "S_ref": base.S_ref, "dt": dt, "passos": n_passos,
                "paineis": base.N, "aneis_esteira": int(len(Gw)), "esteira_lado": lado, "esteira_livre": livre, "x_ref": x_ref,
                "tempo_s": time.time() - t0,
                "avisos": sorted({str(a.message) for a in avisos_malha}) + avisos}
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}


def convergencia_vlm(p: dict) -> dict:
    from ..nucleo.aero import convergencia as CV
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida
    try:
        return CV.vlm(p.get("esquema") or {}, V=_num(p, "V", 15.0, positivo=True), rho=_num(p, "rho", R.RHO_NIVEL_MAR, positivo=True))
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}


def _compacta_quadros(inst: list, R_corpo, max_part: int = 3000, max_fileiras: int = 30) -> dict:
    wtodos = [q["w"] for q in inst if "w" in q and len(q["w"])]
    wref = float(np.percentile(np.concatenate(wtodos), 99)) if wtodos else 1.0
    quadros = []
    for q in inst:
        d = {"t": round(float(q["t"]), 5), "CL": round(float(q["CL"]), 5), "aneis": []}
        for a in q["aneis"]:
            a = np.asarray(a)
            if a.shape[0] > max_fileiras + 1:
                a = a[np.unique(np.r_[np.linspace(0, a.shape[0] - 1, max_fileiras + 1).round().astype(int)])]
            d["aneis"].append({"n": [int(a.shape[0]), int(a.shape[1])], "p": np.round(a.reshape(-1), 3).tolist()})
        if q.get("pas"):
            d["pas"] = [np.round(np.asarray(a).reshape(-1), 4).tolist() for a in q["pas"]]
        if q.get("solo"):
            d["solo"] = {k: np.round(v, 4).tolist() for k, v in q["solo"].items()}
        if "X" in q and len(q["X"]):
            k = np.unique(np.linspace(0, len(q["X"]) - 1, min(len(q["X"]), max_part)).round().astype(int))
            w = np.clip(np.log10(np.maximum(q["w"][k] / wref, 1e-3)) / 3 + 1, 0, 1)
            d["X"] = np.round(q["X"][k].reshape(-1), 3).tolist()
            d["w"] = (w * 255).round().astype(int).tolist()
            d["n_part"] = int(len(q["X"]))
        quadros.append(d)
    return {"corpo": np.round(np.asarray(R_corpo).reshape(-1), 4).tolist(), "quadros": quadros}


def uvlm_video(p: dict) -> tuple[bytes, str]:
    from ..nucleo import anima
    q = dict(p)
    q["_instantaneos"] = []
    r = uvlm(q)
    if "erro" in r:
        raise ErroDeAnalise(r["erro"])
    nomes = {"degrau": "partida impulsiva", "rajada_degrau": "rajada degrau", "rajada_1cos": "rajada 1-cos",
             "mergulho": "mergulho harmônico", "arfagem": "arfagem harmônica"}
    est = {"rigida": "esteira rígida", "livre": "esteira livre de anéis", "particulas": "esteira de partículas de vórtice"}
    nome = (p.get("esquema") or {}).get("nome", "")
    titulo = f"{nome} · {nomes.get(r['caso'], r['caso'])} · {est.get(r['esteira'], '')} · V = {r['V']:.1f} m/s"
    if r.get("helice"):
        hh = r["helice"]
        titulo += f" · hélice {hh['nome']} a {hh['rpm']:.0f} rpm"
    if r.get("solo"):
        ss = r["solo"]
        titulo += f" · solo a {ss['h0']:.2f} m" + (f", subindo {ss['subida']:.1f} m/s" if ss["subida"] > 0 else
                                                     f", descendo {-ss['subida']:.1f} m/s" if ss["subida"] < 0 else "")
    return anima.esteira(q["_instantaneos"], q["_aneis_corpo"], titulo=titulo, codec=p.get("codec", "h264"),
                         largura=int(p.get("largura", 1280)))


def _helice_catalogo(p: dict):
    from ..nucleo.aero import bemt as BM
    from ..nucleo.aero.apc import catalogo
    from ..nucleo.aero.polares import BancoPolares, estender_viterna
    nome = str(p.get("helice") or "22x10E")
    h = catalogo().get(nome)
    if h is None:
        raise ErroDeAnalise(f"Hélice {nome} fora do catálogo APC Thin Electric.")
    banco = BancoPolares.carregar_npz(Path(__file__).resolve().parents[3] / "data" / "polares.npz")
    chave = str(p.get("perfil") or "CLARK_Y_AIRFOIL@n7")
    if chave not in banco:
        raise ErroDeAnalise(f"Perfil {chave} não está no banco de polares.")
    pol = estender_viterna(banco[chave])
    return nome, h, BM.apc_tipica(h.D_pol, h.passo_pol, pol), chave, pol


def _centro_helice(esq: dict):
    el = next((e for e in esq.get("elementos", []) if "helic" in str(e.get("nome", "")).lower()), None)
    if el is not None:
        return np.asarray(el.get("posicao", [0, 0, 0]), float)
    xs = [e.get("posicao", [0, 0, 0])[0] for e in esq.get("elementos", []) if e.get("tipo") == "asa"]
    return np.array([min(xs) - 0.15 if xs else -0.3, 0.0, 0.0])


def helice(p: dict) -> dict:
    import warnings
    from ..nucleo.aero import bemt as BM
    from ..nucleo.aero.aeronave_vlm import superficies
    from ..nucleo.aero.vlm import VLM
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida
    try:
        nome, h, pa, chave, pol = _helice_catalogo(p)
        rho = _num(p, "rho", R.RHO_NIVEL_MAR, positivo=True)
        rpm = _num(p, "rpm", 4000.0, positivo=True)
        V = _num(p, "V", 12.0)
        alpha = _num(p, "alpha", 4.0)
        sentido = -1 if p.get("sentido") in (-1, "-1", "anti") else 1
        n_est = D.helice_n_est()
        n = rpm / 60.0
        J_max = 1.2 * h.passo_pol / h.D_pol
        Js = np.linspace(0.0, J_max, 31)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            curva = BM.curva(pa, rpm, Js, rho, n_est=n_est)
            ct_apc, cp_apc = h.coeficientes(Js, rpm)
            op = BM.analisa(pa, V, rpm, rho, n_est=n_est)
        avisos = ["Geometria da pá: forma média das APC Thin Electric (corda típica, passo constante pelo nome). "
                  "Com a geometria medida (UIUC) a previsão melhora; a curva da APC é cálculo do fabricante, não ensaio."]
        if np.any(op.Re < pol.re[0]) or np.any(op.Re > pol.re[-1]):
            avisos.append(f"Reynolds na pá de {op.Re.min():.0f} a {op.Re.max():.0f}; as polares de {chave} vão de "
                          f"{pol.re[0]:.0f} a {pol.re[-1]:.0f}: fora disso usa a borda da grade.")
        if not all(c.convergiu for c in curva):
            avisos.append("Em algum J a solução não achou o ângulo de entrada em parte da pá (freio ou moinho): essas faixas ficaram fora.")
        out = {"helice": nome, "D": pa.D, "passo_pol": h.passo_pol, "perfil": chave, "rpm": rpm, "V": V, "rho": rho,
               "curva": {"J": Js.tolist(), "CT": [c.CT for c in curva], "CP": [c.CP for c in curva], "eta": [c.eta for c in curva],
                         "CT_apc": np.asarray(ct_apc).tolist(), "CP_apc": np.asarray(cp_apc).tolist(),
                         "eta_apc": [float(j * t / q) if q > 1e-9 and t > 0 else 0.0 for j, t, q in zip(Js, ct_apc, cp_apc)]},
               "ponto": {"J": op.J, "T": op.T, "Q": op.Q, "P": op.P, "eta": op.eta, "CT": op.CT, "CP": op.CP,
                         "r_R": (op.r / pa.R).tolist(), "dT": op.dT.tolist(), "alpha": op.alpha.tolist(), "Re": op.Re.tolist(),
                         "v_a": op.v_a.tolist(), "v_t": op.v_t.tolist(), "F": op.F.tolist(),
                         "eta_ideal": BM.eficiencia_ideal(op.T, V, pa.D, rho) if V > 0 and op.T > 0 else None},
               "geometria": {"r_R": pa.r_R.tolist(), "c_R": pa.c_R.tolist(), "beta": pa.beta_graus.tolist()}, "avisos": avisos}
        esq = p.get("esquema") or {}
        if esq.get("elementos") and V > 0:
            centro = _centro_helice(esq)
            sopro = BM.sopro_de(op, centro, (1.0, 0.0, 0.0), sentido)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                v = VLM(superficies(esq))
                vl = sopro.velocidade(v.cps)
                sem = v.resolver([alpha], V=V, rho=rho, guardar_campos=True)[0]
                com = v.resolver([alpha], V=V, rho=rho, v_local=vl, guardar_campos=True)[0]
            afetadas = [nm for nm, f in v._fatias.items()
                        if np.abs(vl[f["inicio"]:f["inicio"] + f["n"]]).max() > 0.01 * V]
            out["sopro"] = {"centro": centro.tolist(),
                            "CL_sem": sem.CL, "CL_com": com.CL, "CDi_sem": sem.CDi, "CDi_com": com.CDi, "Cm_sem": sem.Cm, "Cm_com": com.Cm,
                            "superficies": [{"nome": nm, "y": sem.y_faixa[nm].tolist(), "cl_sem": sem.cl_faixa[nm].tolist(),
                                             "cl_com": com.cl_faixa[nm].tolist()} for nm in v._fatias if nm in sem.cl_faixa],
                            "afetadas": afetadas, "v_max": float(np.abs(vl).max())}
            if not afetadas:
                avisos.append("O sopro não alcança nenhuma superfície sustentadora (hélice atrás delas ou fora do alinhamento): "
                              "só a indução de montante, pequena.")
        return out
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}
