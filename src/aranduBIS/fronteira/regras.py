from __future__ import annotations

import json
from pathlib import Path

from ..nucleo import regra as R

RAIZ = Path(__file__).resolve().parents[3]
PASTA_FABRICA = RAIZ / "cases" / "regras"

class ErroDeRegra(ValueError):
    pass

def _pastas(pasta_dados: Path):
    return (("fabrica", PASTA_FABRICA), ("equipe", Path(pasta_dados) / "regras"))

def lista(pasta_dados: Path) -> list[dict]:
    out = []
    for origem, p in _pastas(pasta_dados):
        if p.is_dir():
            for f in sorted(p.glob("*.json")):
                out.append({"nome": f.stem, "origem": origem})
    return out

def abre(pasta_dados: Path, nome: str, origem: str) -> dict:
    for o, p in _pastas(pasta_dados):
        if o == origem:
            f = (p / f"{nome}.json").resolve()
            if p.resolve() not in f.parents or not f.is_file():
                raise ErroDeRegra(f"regra não encontrada: {nome}")
            return R.normaliza(json.loads(f.read_text(encoding="utf8")))
    raise ErroDeRegra("origem desconhecida")

def grava(pasta_dados: Path, regra: dict, nome: str) -> str:
    if not nome or not nome.replace("_", "").replace("-", "").isalnum():
        raise ErroDeRegra("Nome do arquivo: só letras, números, _ e -.")
    p = Path(pasta_dados) / "regras"
    p.mkdir(parents=True, exist_ok=True)
    f = p / f"{nome}.json"
    f.write_text(json.dumps(R.normaliza(regra), indent=2, ensure_ascii=False), encoding="utf8")
    return str(f)

def avalia(regra: dict, valores: dict) -> dict:
    if not isinstance(regra, dict):
        raise ErroDeRegra("regra inválida")
    return R.avaliar(R.normaliza(regra), valores or {})
