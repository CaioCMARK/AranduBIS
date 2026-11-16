from __future__ import annotations

import math
import re
from pathlib import Path
import numpy as np
from ..nucleo import referencias as R

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

def _erro(e: Exception) -> str:
    if isinstance(e, FileNotFoundError):
        return "arquivo de perfil nao encontrado: " + Path(str(e.filename)).name
    return str(e).split(chr(10))[0]
