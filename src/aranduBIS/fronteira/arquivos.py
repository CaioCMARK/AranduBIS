from __future__ import annotations

from pathlib import Path

PASTAS = ("base", "relatorios", "desenhos")

class ErroDeArquivo(ValueError):
    pass

def raiz(cfg, pasta: str) -> Path:
    if pasta not in PASTAS:
        raise ErroDeArquivo(f"pasta desconhecida: {pasta}")
    c = cfg.valor(f"pastas.{pasta}")
    if not c:
        raise ErroDeArquivo(f"A pasta “{pasta}” não foi configurada (Configurações > Pastas da equipe).")
    r = Path(c)
    if not r.is_dir():
        raise ErroDeArquivo(f"A pasta configurada não existe: {c}")
    return r.resolve()

def _dentro(r: Path, sub: str) -> Path:
    p = (r / sub).resolve()
    if p != r and r not in p.parents:
        raise ErroDeArquivo("caminho fora da pasta configurada")
    return p

def lista(cfg, pasta: str, sub: str = "") -> dict:
    r = raiz(cfg, pasta)
    d = _dentro(r, sub)
    if not d.is_dir():
        raise ErroDeArquivo("não é uma pasta")
    itens = []
    for e in sorted(d.iterdir(), key=lambda q: (not q.is_dir(), q.name.lower())):
        if e.name.startswith("."):
            continue
        try:
            tam = e.stat().st_size if e.is_file() else None
        except OSError:
            continue
        itens.append({"nome": e.name, "pasta": e.is_dir(), "tamanho": tam,
                      "caminho": e.relative_to(r).as_posix()})
    return {"raiz": str(r), "sub": "" if d == r else d.relative_to(r).as_posix(), "itens": itens[:2000]}

def caminho_do_arquivo(cfg, pasta: str, caminho: str) -> Path:
    p = _dentro(raiz(cfg, pasta), caminho)
    if not p.is_file():
        raise ErroDeArquivo("arquivo não encontrado")
    return p
