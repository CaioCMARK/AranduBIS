from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

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
    V, rho = _num(p, "V", 15.0, positivo=True), _num(p, "rho", 1.1, positivo=True)
    CL_alvo = _num(p, "CL_alvo", positivo=True) if p.get("CL_alvo") is not None else None
    x_cg, origem = p.get("x_cg"), "voce"
    try:
        if x_cg is None:
            cg = AG.massa_e_cg(AG.constroi(esq))["cg_m"]
            x_cg, origem = (float(cg[0]), "massas do modelo") if cg else (None, "")
        if x_cg is None:
            base = longitudinal(esq, 0.0, V=V, rho=rho)
            x_cg, origem = base["ponto_neutro"] - 0.15 * base["c_ref"], "estimado"
        r = longitudinal(esq, float(x_cg), V=V, rho=rho, CL_alvo=CL_alvo, comando=p.get("comando"))
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
    V, rho = _num(p, "V", 12.0, positivo=True), _num(p, "rho", 1.1, positivo=True)
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
                        rho=_num(p, "rho", 1.1, positivo=True), V_max=_num(p, "V_max", 30.0, positivo=True),
                        realista=bool(p.get("realista", True)),
                        celulas=int(_num(p, "celulas")) if p.get("celulas") else None,
                        v_celula=_num(p, "v_celula", 3.6, positivo=True),
                        capacidade_Ah=_num(p, "capacidade_Ah", positivo=True) if p.get("capacidade_Ah") else None,
                        taxa_C=_num(p, "taxa_C", positivo=True) if p.get("taxa_C") else None)
    except ValueError as e:
        return {"erro": _erro(e)}

def _args_dinamica(p: dict) -> dict:
    I = {k: _num(p["inercias"], k) for k in ("Ixx", "Iyy", "Izz", "Ixz") if (p.get("inercias") or {}).get(k) is not None}
    if I and len(I) < 4 and not all(k in I for k in ("Ixx", "Iyy", "Izz")):
        raise ValueError("Informe Ixx, Iyy e Izz (e Ixz, ou zero), ou deixe todas vazias para usar as do modelo.")
    I = ({"Ixz": 0.0, **I} if I else None)
    raios = ({k: _num(p["raios"], k, positivo=True) for k in ("rx", "ry", "rz") if (p.get("raios") or {}).get(k) is not None}
             if p.get("raios") is not None else None)
    return dict(x_cg=None if p.get("x_cg") is None else _num(p, "x_cg"), V=_num(p, "V", 15.0, positivo=True),
                rho=_num(p, "rho", 1.1, positivo=True),
                massa_kg=None if p.get("massa_kg") is None else _num(p, "massa_kg", positivo=True), I=I,
                raios=raios, modo_inercia=str(p.get("modo_inercia") or "auto"))

def dinamica(p: dict) -> dict:
    from ..nucleo.aero.dinamica import dinamica as din
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    try:
        return din(p.get("esquema") or {}, **_args_dinamica(p))
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
                                  ncrit=int(_num(p, "ncrit", 4.0, positivo=True)))
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}
