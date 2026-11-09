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
    ae = DC.Aeronave(S=_num(a, "S", positivo=True), CL_max=_num(a, "CL_max", positivo=True),
                     CL_corrida=_num(a, "CL_corrida"), CD_corrida=_num(a, "CD_corrida", positivo=True),
                     tracao_v=vt, tracao_n=tt)
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

def limites(p: dict) -> dict:
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
        return cl_max(esq, float(x_cg), V=V, rho=rho, ncrit=ncrit)
    except (GeometriaInvalida, ValueError, FileNotFoundError) as e:
        return {"erro": _erro(e)}

def propulsao(p: dict) -> dict:
    from ..nucleo.aero import propulsao as PR
    if p.get("lista"):
        return PR.lista()
    try:
        return PR.curva(str(p.get("motor", "")), str(p.get("helice", "")), P_w=_num(p, "P_w", 600.0, positivo=True),
                        rho=_num(p, "rho", 1.1, positivo=True), V_max=_num(p, "V_max", 30.0, positivo=True),
                        realista=bool(p.get("realista", True)))
    except ValueError as e:
        return {"erro": _erro(e)}
