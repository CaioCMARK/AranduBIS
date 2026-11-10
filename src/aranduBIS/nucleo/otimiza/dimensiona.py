from __future__ import annotations

import copy

from .problema import ProblemaInvalido, _f, poe

PADRAO_CARGAS = {"Vc": 13.0, "Vd": 15.9, "n_max": 1.8, "n_min": 0.0, "U_c": 4.0, "U_d": 2.0, "fator_seguranca": 1.2}

def insere_massas(esq: dict, lista: list, ctx: dict) -> list[dict]:
    entrou = []
    for m in lista or []:
        kg = _f(m["formula"], ctx, f"massa {m['nome']}")
        if kg <= 0:
            continue
        pos = [_f(p, ctx, f"posicao de {m['nome']}") if isinstance(p, str) else float(p) for p in m.get("posicao", [0.0, 0.0, 0.0])]
        esq.setdefault("elementos", []).append({"nome": m["nome"], "tipo": "ponto", "massa": float(kg), "posicao": pos})
        entrou.append({"nome": m["nome"], "kg": float(kg)})
    return entrou

def _aplica(esq: dict, d: dict, t: float, ctx: dict) -> None:
    c = {**ctx, d.get("ajuste", {}).get("nome", "t"): t}
    for lg in d["ligacoes"]:
        v = _f(lg["formula"], c, "dimensionamento")
        for a in lg.get("alvos") or [lg["alvo"]]:
            poe(esq, a, v)

def margem(esq: dict, d: dict, casos: list, fator_seguranca: float) -> float:
    from ..estrutura.asa import verifica
    ms = [verifica(esq, nome, casos, fator_seguranca=fator_seguranca)["critico"]["margem"] for nome in d["elementos"]]
    return float(min(ms))

def dimensiona(esq: dict, dims: list, casos: list, ctx: dict, fator_seguranca: float = 1.2) -> list[dict]:
    saida = []
    for d in dims:
        a = d.get("ajuste", {}); lo, hi = float(a["minimo"]), float(a["maximo"]); alvo = float(d.get("margem_alvo", 0.0))
        def m(t):
            _aplica(esq, d, t, ctx)
            return margem(esq, d, casos, fator_seguranca)
        mh = m(hi)
        if mh < alvo:
            t, mg, ok = hi, mh, False
        else:
            ml = m(lo)
            if ml >= alvo:
                t, mg, ok = lo, ml, True
            else:
                for _ in range(int(d.get("iteracoes", 14))):
                    mid = 0.5 * (lo + hi)
                    if m(mid) >= alvo:
                        hi = mid
                    else:
                        lo = mid
                t = hi; mg = m(t); ok = True
        _aplica(esq, d, t, ctx)
        saida.append({"nome": d["nome"], "valor": float(t), "margem": float(mg), "alvo": alvo, "atingiu": bool(ok)})
    return saida
