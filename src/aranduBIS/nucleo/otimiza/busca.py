from __future__ import annotations

import copy
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from . import problema as P

def _limites(prob):
    vs = prob["variaveis"]
    lo = np.array([float(v["minimo"]) for v in vs]); hi = np.array([float(v["maximo"]) for v in vs])
    return [v["nome"] for v in vs], lo, hi, [bool(v.get("valores")) for v in vs]

def _x(nomes, vetor, discreta):
    return {n: (float(round(u)) if d else float(u)) for n, u, d in zip(nomes, vetor, discreta)}

def melhor_que(a: dict, b: dict) -> bool:
    va, vb = a["violacao"], b["violacao"]
    if va <= 0.0 and vb <= 0.0:
        return (a["objetivo"] or -np.inf) > (b["objetivo"] or -np.inf)
    if va <= 0.0 or vb <= 0.0:
        return va <= 0.0
    return va < vb

def _aval(args):
    prob, x = args
    return P.avalia(prob, x)

def evolui(prob: dict, populacao: int = 24, geracoes: int = 40, F: float = 0.7, CR: float = 0.8, estrategia: str = "melhor",
           semente: int = 0, processos: int = 1, inicial: list[dict] | None = None, ao_gerar=None) -> dict:
    nomes, lo, hi, disc = _limites(prob)
    n = len(nomes); rng = np.random.default_rng(semente); t0 = time.perf_counter()
    pop = lo + rng.random((populacao, n)) * (hi - lo)
    pop[0] = [float(v.get("padrao", 0.5 * (v["minimo"] + v["maximo"]))) for v in prob["variaveis"]]
    for i, x in enumerate(inicial or [], start=1):
        if i < populacao:
            pop[i] = np.clip([x.get(nm, pop[i][k]) for k, nm in enumerate(nomes)], lo, hi)
    pool = ProcessPoolExecutor(processos) if processos > 1 else None
    mapa = (lambda L: list(pool.map(_aval, L))) if pool else (lambda L: [_aval(a) for a in L])
    try:
        res = mapa([(prob, _x(nomes, v, disc)) for v in pop]); n_aval = populacao; hist = []
        for g in range(geracoes + 1):
            ib = 0
            for i in range(1, populacao):
                if melhor_que(res[i], res[ib]):
                    ib = i
            viaveis = [r for r in res if r["violacao"] <= 0.0]
            reg = {"geracao": g, "melhor_objetivo": res[ib]["objetivo"], "melhor_viavel": res[ib]["violacao"] <= 0.0, "melhor_violacao": res[ib]["violacao"],
                   "media_objetivo": float(np.mean([r["objetivo"] for r in viaveis])) if viaveis else None, "n_viaveis": len(viaveis),
                   "diversidade": float(np.mean(np.std((pop - lo) / (hi - lo), axis=0))), "avaliacoes": n_aval, "tempo_s": time.perf_counter() - t0,
                   "melhor_x": dict(res[ib]["x"])}
            hist.append(reg)
            if ao_gerar:
                ao_gerar(reg)
            if g == geracoes:
                break
            tentativas = np.empty_like(pop)
            for i in range(populacao):
                outros = [j for j in range(populacao) if j != i]
                r1, r2, r3 = rng.choice(outros, 3, replace=False)
                mut = (pop[i] + F * (pop[ib] - pop[i]) + F * (pop[r2] - pop[r3])) if estrategia == "melhor" else (pop[r1] + F * (pop[r2] - pop[r3]))
                v = np.where(rng.random(n) < CR, mut, pop[i])
                k = rng.integers(n); v[k] = mut[k]
                fora = (v < lo) | (v > hi)
                v = np.where(fora, np.where(rng.random(n) < 0.5, lo + (pop[i] - lo) * rng.random(n), hi - (hi - pop[i]) * rng.random(n)), v)
                tentativas[i] = np.clip(v, lo, hi)
            filhos = mapa([(prob, _x(nomes, v, disc)) for v in tentativas]); n_aval += populacao
            for i in range(populacao):
                if melhor_que(filhos[i], res[i]) or (filhos[i]["violacao"] == res[i]["violacao"] and filhos[i]["objetivo"] == res[i]["objetivo"]):
                    pop[i], res[i] = tentativas[i], filhos[i]
    finally:
        if pool:
            pool.shutdown()
    ib = 0
    for i in range(1, populacao):
        if melhor_que(res[i], res[ib]):
            ib = i
    return {"melhor": res[ib], "populacao": res, "historico": hist, "semente": semente, "avaliacoes": n_aval, "variaveis": nomes,
            "parametros": {"populacao": populacao, "geracoes": geracoes, "F": F, "CR": CR, "estrategia": estrategia}}

def refina(prob: dict, resultado: dict, quantos: int = 5, processos: int = 1) -> list[dict]:
    cheia = copy.deepcopy(prob)
    cheia.setdefault("analise", {}).pop("malha", None)
    ordem = sorted(resultado["populacao"], key=lambda r: (r["violacao"] > 0, r["violacao"] if r["violacao"] > 0 else -(r["objetivo"] or 0)))[:quantos]
    pool = ProcessPoolExecutor(processos) if processos > 1 else None
    try:
        novos = list(pool.map(_aval, [(cheia, r["x"]) for r in ordem])) if pool else [_aval((cheia, r["x"])) for r in ordem]
    finally:
        if pool:
            pool.shutdown()
    return sorted(novos, key=lambda r: (r["violacao"] > 0, r["violacao"] if r["violacao"] > 0 else -(r["objetivo"] or 0)))
