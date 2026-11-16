from __future__ import annotations

from ..nucleo.modelador import aeronave_geometria as AG
from .analise_comum import _erro, _num

def nervuras_posicoes(p: dict) -> dict:
    from ..nucleo.estrutura import nervuras as NV
    from ..nucleo.modelador import aeronave_geometria as AG
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        nome = p.get("asa")
        if not nome:
            asas = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa"]
            if not asas:
                return {"erro": "Nenhuma asa no modelo."}
            nome = asas[0]
        if p.get("y") is not None:
            el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome and e.get("tipo") == "asa"), None)
            if el is None:
                return {"erro": f"asa {nome!r} nao existe no modelo"}
            ys = [q[1] for q in AG._secoes(el)]
            valores = [_num({"v": v}, "v") for v in p["y"]]
            completa = AG._nervuras_y(valores, ys)
            simetrica = ys[0] < -1e-9 and ys[-1] > 1e-9 and abs(ys[0] + ys[-1]) < 1e-6 * max(abs(ys[0]), abs(ys[-1]))
            r = {"y": valores, "simetrica": bool(simetrica), "completa": [float(v) for v in completa], "passos_mm": [1000.0 * float(b - a) for a, b in zip(completa, completa[1:])]}
        else:
            r = NV.posicoes(esq, str(nome), int(_num(p, "n", 8.0, positivo=True)), str(p.get("lei", "uniforme")), _num(p, "expoente", 1.6, positivo=True))
        r["asa"] = nome
        r["passo_max_mm"] = max(r["passos_mm"], default=0.0)
        r["passo_min_mm"] = min(r["passos_mm"], default=0.0)
        r["n_total"] = len(r["completa"])
        return r
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def _alivio(p: dict, esq: dict, conj: dict) -> dict:
    from ..nucleo.estrutura import alivio as AL
    from ..nucleo.estrutura import materiais as MT
    from .analise_voo import resumo_aero

    mat = MT.propriedades(conj["material"], esq, p.get("materiais"))
    n, fs = _num(p, "alivio_n", 3.8, positivo=True), _num(p, "alivio_fs", 1.5, positivo=True)
    massa = _num(p, "alivio_massa_kg", 0.0)
    if not massa > 0:
        massa = float(AG.massa_e_cg(AG.constroi(esq))["massa_kg"])
    S = float(resumo_aero(esq).get("area_m2") or 0.0)
    if not (massa > 0 and S > 0):
        raise ValueError("furos de alívio: informe a massa da aeronave (o modelo não tem massa ou área de asa)")
    pressao = n * massa * 9.80665 / S
    kerf = _num(p, "kerf_mm", 0.0)
    ys = [q["y_m"] for q in conj["nervuras"]]
    total, removida, margens, n_furos, apoios = 0.0, 0.0, [], 0, set()
    for k, nv in enumerate(conj["nervuras"]):
        viz = [abs(ys[j] - ys[k]) for j in (k - 1, k + 1) if 0 <= j < len(ys)]
        passo = 0.5 * sum(viz) if len(viz) == 2 else (viz[0] if viz else 0.1)
        carga = pressao * passo * nv["corda_mm"] / 1000.0
        comp = sum(q["x1"] - q["x0"] for q in nv["pecas"]) or 1.0
        for q in nv["pecas"]:
            r = AL.propoe(q["contorno"], q["furos"], conj["espessura_mm"], carga_N=carga * (q["x1"] - q["x0"]) / comp, tau_adm_MPa=mat["S"] / 1e6,
                          sigma_adm_MPa=min(mat["X"], mat["XC"]) / 1e6, fs=fs, borda_mm=_num(p, "alivio_borda_mm", 6.0, positivo=True),
                          ponte_mm=_num(p, "alivio_ponte_mm", 6.0, positivo=True), d_min_mm=_num(p, "alivio_d_min_mm", 8.0, positivo=True),
                          d_max_mm=_num(p, "alivio_d_max_mm", 60.0, positivo=True))
            total += r["area_mm2"]
            apoios.add(r["apoio"])
            for f in r["furos"]:
                removida += 0.25 * 3.141592653589793 * f["d"] ** 2
                if f["margem"] is not None:
                    margens.append(f["margem"])
                n_furos += 1
                g = dict(f)
                if kerf:
                    g["d"] = g["dx"] = max(f["d"] - kerf, 0.1)
                q["furos"].append(g)
                q["area_mm2"] -= 0.25 * 3.141592653589793 * f["d"] ** 2
    fr = removida / total if total > 0 else 0.0
    return {"n_furos": n_furos, "fracao_removida": fr, "fator_massa": 1.0 - fr, "margem_min": min(margens) if margens else None, "pressao_Pa": pressao,
            "massa_kg": massa, "n": n, "fs": fs, "tau_adm_MPa": mat["S"] / 1e6, "sigma_adm_MPa": min(mat["X"], mat["XC"]) / 1e6, "apoios": sorted(a for a in apoios if a),
            "hipoteses": "Nervura tratada como viga ao longo da corda, com a carga de sustentação da faixa (n × peso / área × passo × corda) distribuída por igual e apoiada nos furos de tubo. "
                         "Em cada furo confere o cisalhamento e a flexão da seção líquida. Não cobre esmagamento local, flambagem da alma nem cargas de manuseio."}

def nervuras_dxf(p: dict) -> dict:
    from ..nucleo.estrutura import nervuras as NV
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        com = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa" and (e.get("estrutura") or {}).get("nervuras")]
        if not com:
            return {"erro": "Nenhuma asa com nervuras declaradas (estrutura.nervuras.y) no modelo."}
        nome = p.get("asa") or com[0]
        conj = NV.pecas(esq, str(nome), kerf_mm=_num(p, "kerf_mm", 0.0), folga_tubo_mm=_num(p, "folga_tubo_mm", 0.1), folga_longarina_mm=_num(p, "folga_longarina_mm", 0.1),
                        bf_min_mm=_num(p, "bf_min_mm", 1.0), recesso_chapeado=bool(p.get("recesso_chapeado", True)), parede_min_mm=_num(p, "parede_min_mm", 1.2))
        alivio = _alivio(p, esq, conj) if p.get("alivio") else None
        org = NV.organiza(conj, (_num(p, "folha_largura_mm", 600.0, positivo=True), _num(p, "folha_altura_mm", 300.0, positivo=True)), espaco_mm=_num(p, "espaco_mm", 4.0))
        texto = NV.dxf(conj, org, folha=bool(p.get("moldura", True)), rotulos=bool(p.get("rotulos", True)))
        W = org["folha_mm"][0]
        pecas = []
        for n in conj["nervuras"]:
            for q in n["pecas"]:
                ox, oy = q["pos"]
                pecas.append({"nome": q["nome"], "i": n["i"], "y_m": n["y_m"], "angulo": n.get("angulo", 0.0), "folha": q["folha"], "contorno": [[x + ox, z + oy] for x, z in q["contorno"]],
                              "furos": [{"c": [f["c"][0] + ox, f["c"][1] + oy], "d": f["d"], "dx": f.get("dx", f["d"]), "tipo": f.get("tipo", "tubo"), "margem": f.get("margem")} for f in q["furos"]], "largura_mm": q["x1"] - q["x0"], "altura_mm": q["z1"] - q["z0"],
                              "area_mm2": q["area_mm2"]})
        return {"asa": conj["asa"], "asas": com, "dxf": texto, "espessura_mm": conj["espessura_mm"], "material": conj["material"], "n_nervuras": len(conj["nervuras"]),
                "n_pecas": len(pecas), "pecas": pecas, "folhas": org["folhas"], "folha_mm": org["folha_mm"], "avisos": conj["avisos"] + org["avisos"],
                "area_total_cm2": sum(q["area_mm2"] for q in pecas) / 100.0, "alivio": alivio}
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def planificacao(p: dict) -> dict:
    from ..nucleo.estrutura import planifica as PL
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida

    esq = p.get("esquema") or {}
    try:
        com = [e["nome"] for e in esq.get("elementos", []) if e.get("tipo") == "asa" and (e.get("estrutura") or {}).get("chapeado")]
        if not com:
            return {"erro": "Nenhuma asa com chapeado declarado (estrutura.chapeado) no modelo. Declare na aba Estrutura da asa até onde a pele vai."}
        nome = str(p.get("asa") or com[0])
        modo = str(p.get("modo") or "auto")
        lim = p.get("limite_pct")
        conj = PL.faixas(esq, nome, modo=modo, n_vao=int(_num(p, "n_vao", 6.0, positivo=True)), limite_pct=(None if lim in (None, "", 0) else float(lim)), margem_cola_mm=_num(p, "margem_cola_mm", 5.0),
                        cortes_y=[float(c) / 1000.0 for c in (p.get("cortes_y_mm") or [])], modos={str(k): str(m) for k, m in (p.get("modos") or {}).items() if m})
        org = PL.organiza(conj, (_num(p, "folha_largura_mm", 1000.0, positivo=True), _num(p, "folha_altura_mm", 300.0, positivo=True)), espaco_mm=_num(p, "espaco_mm", 6.0))
        texto = PL.dxf(conj, org, folha=bool(p.get("moldura", True)), rotulos=bool(p.get("rotulos", True)))
        W = org["folha_mm"][0]
        chapas = []
        for c in org["colocados"]:
            it, q = c["item"], c["item"]["p"]
            origem = [min(a[0] for a in q["contorno"]), min(a[1] for a in q["contorno"])]
            cont = [[(it["w"] - (a[0] - origem[0]) if c["espelho"] else a[0] - origem[0]) + c["pos"][0], a[1] - origem[1] + c["pos"][1]] for a in q["contorno"]]
            f = conj["faixas"][it["faixa"] - 1]
            chapas.append({"rot": it["rot"], "faixa": it["faixa"], "folha": c["folha"], "espelho": c["espelho"], "status": f["status"], "contorno": cont,
                           "largura_mm": it["w"], "altura_mm": it["h"], "deformacao_max_pct": q["deformacao_max_pct"]})
        faixas = []
        for i, f in enumerate(conj["faixas"], 1):
            faixas.append({"i": i, "y0_m": f["y0_m"], "y1_m": f["y1_m"], "quantidade": f["quantidade"], "modo": f["modo"], "modo_pedido": f["modo_pedido"], "chave": f["chave"], "status": f["status"], "deformacao_max_pct": f["deformacao_max_pct"],
                           "pecas": [{k: q[k] for k in ("nome", "largura_mm", "altura_mm", "area_mm2", "area3d_mm2", "deformacao_max_pct", "deformacao_media_pct", "defeito_angular_max_graus",
                                                     "curvatura_total_rad", "var_area_max_pct", "v", "estr", "contorno", "m1", "nk", "linha_bordo_ataque")} for q in f["pecas"]]})
        resumo = {s: sum(1 for f in conj["faixas"] if f["status"] == s) for s in ("ok", "atencao", "nao")}
        return {"asa": nome, "asas": com, "material": conj["material"], "limite_pct": conj["limite_pct"], "ate_xc": conj["ate_xc"], "n_vao": conj["n_vao"], "faixas": faixas, "chapas": chapas, "mapa": conj["mapa"],
                "folhas": org["folhas"], "folha_mm": org["folha_mm"], "resumo": resumo, "dxf": texto, "avisos": conj["avisos"] + org["avisos"]}
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}

def secoes(p: dict) -> dict:
    from ..nucleo.modelador.aeronave_geometria import GeometriaInvalida
    from ..nucleo.modelador.secoes import secoes_da_asa

    esq = p.get("esquema") or {}
    try:
        nome = p.get("asa")
        if not nome:
            return {"erro": "Informe a asa."}
        return secoes_da_asa(esq, str(nome))
    except (GeometriaInvalida, ValueError, FileNotFoundError, KeyError, TypeError) as e:
        return {"erro": _erro(e)}
