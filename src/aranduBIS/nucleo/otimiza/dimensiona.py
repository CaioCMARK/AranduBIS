from __future__ import annotations

import copy

from .problema import ProblemaInvalido, _f, poe

PADRAO_CARGAS = {"Vc": 13.0, "Vd": 15.9, "n_max": 1.8, "n_min": 0.0, "U_c": 4.0, "U_d": 2.0, "fator_seguranca": 1.2}

def insere_massas(esq: dict, lista: list, ctx: dict, fator: float = 1.0) -> list[dict]:
    entrou = []
    for m in lista or []:
        onde = f"peca {m['nome']}"
        custo, opcao = 0.0, None
        if m.get("opcoes"):
            i = int(round(_f(m.get("escolha", 0), ctx, onde + " (escolha)"))) if not isinstance(m.get("escolha", 0), (int, float)) else int(m.get("escolha", 0))
            if not 0 <= i < len(m["opcoes"]):
                raise ProblemaInvalido(f"{onde}: opcao {i} fora do catalogo de {len(m['opcoes'])}")
            o = m["opcoes"][i]; qtd = _f(m.get("quantidade", 1), ctx, onde + " (quantidade)") if isinstance(m.get("quantidade", 1), str) else float(m.get("quantidade", 1))
            kg, custo, opcao = float(o["kg"]) * qtd, float(o.get("custo", 0.0)) * qtd, o.get("nome")
        else:
            kg = _f(m["formula"], ctx, onde)
            custo = _f(m["custo"], ctx, onde + " (custo)") if isinstance(m.get("custo"), str) else float(m.get("custo", 0.0))
        kg *= float(fator)
        if kg <= 0:
            continue
        pos = [_f(p, ctx, f"posicao de {m['nome']}") if isinstance(p, str) else float(p) for p in m.get("posicao", [0.0, 0.0, 0.0])]
        esq.setdefault("elementos", []).append({"nome": m["nome"], "tipo": "ponto", "massa": float(kg), "posicao": pos})
        entrou.append({"nome": m["nome"], "kg": float(kg), "custo": float(custo), "opcao": opcao})
    return entrou

def _aplica(esq: dict, d: dict, t: float, ctx: dict) -> None:
    c = {**ctx, d.get("ajuste", {}).get("nome", "t"): t}
    for lg in d["ligacoes"]:
        v = _f(lg["formula"], c, "dimensionamento")
        for a in lg.get("alvos") or [lg["alvo"]]:
            poe(esq, a, v)

def margem(esq: dict, d: dict, casos: list, fator_seguranca: float, aero: dict | None = None) -> float:
    tipo = d.get("tipo", "flexao")
    if tipo == "flexao":
        from ..estrutura.asa import verifica
        ms = [verifica(esq, nome, casos, fator_seguranca=fator_seguranca)["critico"]["margem"] for nome in d["elementos"]]
        return float(min(ms))
    if tipo == "reversao":
        from ..estrutura import torcao as TO
        a = {"rho": 1.1, "Vd": 15.9, **(aero or {})}
        ms = []
        for nome in d["elementos"]:
            calib = 1.0
            if d.get("fe"):
                from ..fe import asa_casca as FC
                k_an = TO.analisa(esq, nome, rho=a["rho"], Vd=a["Vd"], fator=fator_seguranca)["K_theta"]
                calib = FC.torcao_fe(esq, nome, **(d.get("malha_fe") or {}))["K_theta"] / k_an
            r = TO.analisa(esq, nome, rho=a["rho"], Vd=a["Vd"], fator=fator_seguranca, calib_GJ=calib)
            if r["margem_VR"] is not None:
                ms.append(r["margem_VR"])
        return float(min(ms)) if ms else 9.99
    raise ProblemaInvalido(f"dimensionamento {d.get('nome')!r}: tipo {tipo!r} desconhecido (use flexao ou reversao)")

def dimensiona(esq: dict, dims: list, casos: list, ctx: dict, fator_seguranca: float = 1.2, aero: dict | None = None) -> list[dict]:
    saida = []
    for d in dims:
        a = d.get("ajuste", {}); lo, hi = float(a["minimo"]), float(a["maximo"]); alvo = float(d.get("margem_alvo", 0.0))
        def m(t):
            _aplica(esq, d, t, ctx)
            return margem(esq, d, casos, fator_seguranca, aero)
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
