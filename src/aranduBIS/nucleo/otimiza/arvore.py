from __future__ import annotations

from . import problema as P

def monta(sub: dict[str, dict]) -> dict:
    if len(sub) < 2:
        raise ValueError("arvore de topologias precisa de pelo menos 2 topologias")
    ordem = list(sub.keys())
    variaveis = [{"nome": "topologia", "minimo": 0, "maximo": len(ordem) - 1, "valores": list(range(len(ordem))), "padrao": 0}]
    for nome in ordem:
        variaveis += [{**v, "nome": f"{nome}_{v['nome']}"} for v in sub[nome]["variaveis"]]
    return {"_ordem": ordem, "_sub": sub, "variaveis": variaveis}

def avalia(prob_arvore: dict, x: dict) -> dict:
    nome = prob_arvore["_ordem"][int(round(x["topologia"]))]
    sub = prob_arvore["_sub"][nome]
    pref = f"{nome}_"
    x_sub = {k[len(pref):]: v for k, v in x.items() if k.startswith(pref)}
    r = P.avalia(sub, x_sub)
    r["x"] = dict(x)
    if r.get("resultados") is not None:
        r["resultados"] = {**r["resultados"], "topologia": nome}
    return r

def tira_malha(prob_arvore: dict) -> None:
    for sub in prob_arvore["_sub"].values():
        sub.setdefault("analise", {}).pop("malha", None)

def top_por_topologia(prob_arvore: dict, populacao: list[dict], k: int) -> list[dict]:
    por_topo: dict[str, list[dict]] = {}
    for ind in populacao:
        nome = prob_arvore["_ordem"][int(round(ind["x"]["topologia"]))]
        por_topo.setdefault(nome, []).append(ind)
    candidatos = []
    for inds in por_topo.values():
        inds.sort(key=lambda z: (z["violacao"] > 0, z["violacao"] if z["violacao"] > 0 else -(z["objetivo"] or 0)))
        candidatos += inds[:k]
    return candidatos

def semeia(prob_arvore: dict, nome_topologia: str, x_sub: dict) -> dict:
    idx = float(prob_arvore["_ordem"].index(nome_topologia))
    return {"topologia": idx, **{f"{nome_topologia}_{k}": v for k, v in x_sub.items()}}
