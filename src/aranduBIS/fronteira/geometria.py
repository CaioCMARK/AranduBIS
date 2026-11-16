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

def perfil_pontos(spec: str, pasta, n: int = 81) -> list:
    try:
        x, zs, zi = ES.perfil_xy(spec, int(n), pasta or ".")
    except (ValueError, OSError) as e:
        raise ErroDeGeometria(str(e))
    return [[float(a), float(b)] for a, b in np.vstack([np.c_[x, zs][::-1], np.c_[x, zi][1:]])]

def grava_perfil(nome: str, pontos, pasta_aeronave, pasta_aeronaves) -> dict:
    if not nome or not nome.replace("_", "").replace("-", "").isalnum():
        raise ErroDeGeometria("nome do perfil: só letras, números, _ e -")
    try:
        P = np.array(pontos, float)
    except (ValueError, TypeError):
        raise ErroDeGeometria("pontos inválidos")
    if P.ndim != 2 or P.shape[1] != 2 or len(P) < 10 or not np.isfinite(P).all():
        raise ErroDeGeometria("o perfil precisa de pelo menos 10 pontos (x, z)")
    pa = Path(pasta_aeronaves).resolve()
    ap = Path(pasta_aeronave).resolve() if pasta_aeronave else None
    propria = ap is not None and (ap == pa or pa in ap.parents)
    pasta = ap if propria else pa / "perfis"
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / f"{nome}.dat"
    alvo.write_text(nome + chr(10) + chr(10).join(f"{a:.6f} {b:.6f}" for a, b in P) + chr(10), encoding="utf8")
    return {"perfil": alvo.name if propria else str(alvo), "caminho": str(alvo)}

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

def exporta_fabricacao(p: dict, pasta_dados=None) -> dict:
    from ..nucleo.modelador import exporta_fabricacao as EF
    esq = dict(p.get("esquema") or {})
    esq.setdefault("_pasta", str(PASTA_EXEMPLOS / "biplano"))
    formatos = tuple(p.get("formatos") or ("dat", "dxf", "csv"))
    if not set(formatos) <= {"dat", "dxf", "csv", "avl", "stl_fechado", "stl_esqueleto", "montagem"}:
        raise ErroDeGeometria("formatos: use dat, dxf, csv, avl, stl_fechado, stl_esqueleto e montagem")
    raizes = [PASTA_EXEMPLOS] + ([Path(pasta_dados)] if pasta_dados else [])
    try:
        return EF.exporta(esq, formatos, p.get("asas") or None, raizes=raizes)
    except (AG.GeometriaInvalida, ValueError, FileNotFoundError) as e:
        raise ErroDeGeometria(str(e))
