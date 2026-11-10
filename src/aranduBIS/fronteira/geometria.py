from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..nucleo.modelador import aeronave_estrutura as ES
from ..nucleo.modelador import aeronave_geometria as AG

RAIZ = Path(__file__).resolve().parents[3]
PASTA_EXEMPLOS = RAIZ / "cases" / "geometria"

class ErroDeGeometria(ValueError):
    pass

def constroi(esquema: dict) -> dict:
    esq = dict(esquema)
    esq.setdefault("_pasta", str(PASTA_EXEMPLOS / "biplano"))
    try:
        A = AG.constroi(esq)
    except AG.GeometriaInvalida as e:
        raise ErroDeGeometria(str(e)) from None
    m = AG.massa_e_cg(A)
    lo, hi = A.V.min(axis=0), A.V.max(axis=0)
    camadas = A.camadas or ["aero"] * len(A.zonas)
    return {
        "nome": A.nome,
        "V": np.round(A.V, 6).ravel().tolist(),
        "T": A.T.ravel().tolist(),
        "zona": A.zona.tolist(),
        "zonas": A.zonas,
        "camadas": camadas,
        "bbox": [lo.tolist(), hi.tolist()],
        "massa_kg": m["massa_kg"],
        "cg_m": m["cg_m"],
        "itens_massa": m["itens"],
        "n_vertices": int(len(A.V)),
        "n_triangulos": int(len(A.T)),
    }

def exemplos() -> list[str]:
    out = []
    for p in sorted(PASTA_EXEMPLOS.rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and "elementos" in d and "versao" in d:
            out.append(p.relative_to(PASTA_EXEMPLOS).as_posix())
    return out

def abre_exemplo(nome: str) -> dict:
    p = (PASTA_EXEMPLOS / nome).resolve()
    if PASTA_EXEMPLOS.resolve() not in p.parents or p.suffix != ".json":
        raise ErroDeGeometria("exemplo fora da pasta de exemplos")
    if not p.is_file():
        raise ErroDeGeometria(f"exemplo não encontrado: {nome}")
    d = json.loads(p.read_text(encoding="utf8"))
    d["_pasta"] = str(p.parent)
    return d

def grava(esquema: dict, pasta, nome: str | None = None) -> str:
    nome = nome or esquema.get("nome", "aeronave")
    if not nome.replace("_", "").replace("-", "").isalnum():
        raise ErroDeGeometria("nome do arquivo: só letras, números, _ e -")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    limpo = {k: v for k, v in esquema.items() if not k.startswith("_")}
    alvo = pasta / f"{nome}.json"
    alvo.write_text(json.dumps(limpo, indent=2, ensure_ascii=False), encoding="utf8")
    return str(alvo)

def materiais() -> list[dict]:
    return [{"nome": n, "densidade": d, "origem": o} for n, (d, o) in ES.MATERIAIS.items()]

def medidas(p: dict) -> dict:
    from ..nucleo.medidas import medidas as _med
    esq = dict(p.get("esquema") or {})
    esq.setdefault("_pasta", str(PASTA_EXEMPLOS / "biplano"))
    try:
        ca = p.get("cone_altura")
        return _med(esq, excluir=tuple(p.get("excluir") or ()), cone_altura=float(ca) if ca else None)
    except (AG.GeometriaInvalida, ValueError, FileNotFoundError) as e:
        raise ErroDeGeometria(str(e))
