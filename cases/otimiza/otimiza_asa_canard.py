import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from aranduBIS.nucleo.otimiza import busca as B
from aranduBIS.nucleo.otimiza import problema as P

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
YE, ENT = 0.31, 0.14
RETA = bool(int(os.environ.get("RETA", "0")))

def _c(y, ent=0.0):
    return f"(ct + (cr - ct) * (1 - {y} / (b / 2)) - {ent})"

def problema(esquema: str = "asa_canard.json") -> dict:
    pasta = RAIZ / "cases" / "geometria" / "generico"
    base = json.loads((pasta / esquema).read_text(encoding="utf8"))
    base["_pasta"] = str(pasta)
    sis = json.loads((AQUI / "massas_sistema_convencional.json").read_text(encoding="utf8"))
    sis_massas = [m for m in sis["massas"] if m["nome"] not in ("servo_do_leme",)]
    extras = [{"nome": "motopropulsor", "formula": "0.427 + 0.115 + 0.100 + 0.086", "posicao": [0.50, 0.0, 0.0]},
              {"nome": "servos_leme_e_elevon", "formula": "0.0294 * 2", "posicao": [0.35, 0.0, 0.0]},
              {"nome": "fuselagem_e_trem", "formula": "0.150 + 0.100 + 0.122 + 0.026 + 0.080 + 0.25", "posicao": [0.15, 0.0, 0.0]}]
    meio = len(base["elementos"][0]["secoes"]) == 9
    papeis = (["tip", "mid", "y1", "y2", "c", "y2", "y1", "mid", "tip"] if meio else ["tip", "y1", "y2", "c", "y2", "y1", "tip"])
    yexpr = {"tip": "b / 2", "mid": "ym * b / 2", "y1": f"{YE + 0.02}", "y2": f"{YE}", "c": "0"}
    lig = [{"escala_y": {"elementos": ["asa"], "fator": "b / 2.4"}}]
    for idx, p in enumerate(papeis):
        yv = yexpr[p]
        ent = "1" if p in ("y2", "c") else "0"
        corda = _c(yv, f"{ENT} * {ent}")
        corda = f"km * {corda}" if p == "mid" else corda
        xle = f"sw * ({yv}) / (b / 2)"
        xle = f"ks * {xle}" if p == "mid" else xle
        ainc = f"ai + wo * ({yv}) / (b / 2)"
        ainc = f"ai + fm * wo * ({yv}) / (b / 2)" if p == "mid" else ainc
        lig += [{"alvo": f"asa.secoes[{idx}].corda", "formula": corda}, {"alvo": f"asa.secoes[{idx}].xle", "formula": xle}, {"alvo": f"asa.secoes[{idx}].ainc", "formula": ainc}]
    n_ = len(papeis)
    if meio:
        lig += [{"alvo": "asa.secoes[1].y", "formula": "-ym * b / 2"}, {"alvo": f"asa.secoes[{n_ - 2}].y", "formula": "ym * b / 2"}]
    i1, i2 = (2, 3) if meio else (1, 2)
    lig += [{"alvo": f"asa.secoes[{i1}].y", "formula": f"-{YE + 0.02}"}, {"alvo": f"asa.secoes[{n_ - 1 - i1}].y", "formula": f"{YE + 0.02}"},
            {"alvo": f"asa.secoes[{i2}].y", "formula": f"-{YE}"}, {"alvo": f"asa.secoes[{n_ - 1 - i2}].y", "formula": f"{YE}"},
            {"alvos": ["canard.secoes[0].corda", "canard.secoes[1].corda"], "formula": "cc"},
            {"alvo": "canard.secoes[0].y", "formula": "-bc"}, {"alvo": "canard.secoes[1].y", "formula": "bc"},
            {"alvos": ["canard.secoes[0].ainc", "canard.secoes[1].ainc"], "formula": "ac"},
            {"alvo": "canard.controles[0].x", "formula": "0.6 * cc"},
            {"alvo": "canard.controles[0].y[1]", "formula": "bc"}]
    if meio and RETA:
        asa_el = next(e for e in base["elementos"] if e["nome"] == "asa")
        itens = [("longarinas", 0, asa_el["estrutura"]["longarinas"][0])] + \
                [("tubos", i, it) for i, it in enumerate(asa_el["estrutura"]["tubos"])]
        for grupo, i, item in itens:
            par = sorted((abs(float(y_)), float(xc_)) for y_, xc_ in item["xc_y"])
            xc_raiz = float(np.interp(0.0, [q[0] for q in par], [q[1] for q in par]))
            xc_ponta = float(np.interp(par[-1][0], [q[0] for q in par], [q[1] for q in par]))
            xc_novo = (f"({xc_raiz:.6f} * (cr - {ENT}) + ({xc_ponta:.6f} * ct - {xc_raiz:.6f} * (cr - {ENT})) * ym) "
                       f"/ (km * (ct + (cr - ct) * (1 - ym)))")
            caminho = f"asa.estrutura.{grupo}[{i}].xc_y"
            k_neg, k_pos = len(item["xc_y"]), len(item["xc_y"]) + 1
            item["xc_y"] = item["xc_y"] + [[-par[-1][0] * 0.5, xc_raiz], [par[-1][0] * 0.5, xc_raiz]]
            lig += [{"alvos": [f"{caminho}[{k_neg}][1]", f"{caminho}[{k_pos}][1]"], "formula": xc_novo},
                    {"alvo": f"{caminho}[{k_neg}][0]", "formula": "-ym * b / 2"},
                    {"alvo": f"{caminho}[{k_pos}][0]", "formula": "ym * b / 2"}]
    extra_var = [{"nome": "km", "minimo": 0.75, "maximo": 1.30, "padrao": 1.0}, {"nome": "ks", "minimo": 0.5, "maximo": 1.5, "padrao": 1.0},
                 {"nome": "fm", "minimo": 0.0, "maximo": 1.5, "padrao": 1.0}, {"nome": "ym", "minimo": 0.40, "maximo": 0.90, "padrao": 0.6}] if meio else []
    return {"base": base, "retira": ["carga_util"],
            "variaveis": [{"nome": "b", "minimo": 2.0, "maximo": 3.2, "padrao": 2.4}, {"nome": "cr", "minimo": 0.55, "maximo": 0.95, "padrao": 0.66},
                          {"nome": "ct", "minimo": 0.15, "maximo": 0.40, "padrao": 0.22}, {"nome": "sw", "minimo": 0.25, "maximo": 0.90, "padrao": 0.55},
                          {"nome": "wo", "minimo": -6.0, "maximo": 0.0, "padrao": -3.0}, {"nome": "ai", "minimo": 0.0, "maximo": 5.0, "padrao": 2.0},
                          {"nome": "cc", "minimo": 0.10, "maximo": 0.28, "padrao": 0.14}, {"nome": "bc", "minimo": 0.2, "maximo": 0.6, "padrao": 0.40},
                          {"nome": "ac", "minimo": 0.0, "maximo": 8.0, "padrao": 2.0}, {"nome": "xc", "minimo": 0.15, "maximo": 0.55, "padrao": 0.30}] + extra_var,
            "fator_massas": float(os.environ.get("FATOR_MASSAS", "1.0")), "grandezas": sis["grandezas"], "massas": sis_massas + extras, "ligacoes": lig,
            "dimensionamento": [{"nome": "parede", "elementos": ["asa"], "ajuste": {"nome": "t", "minimo": 0.0002, "maximo": 0.0030}, "margem_alvo": 0.1,
                                 "ligacoes": [{"alvos": [f"asa.estrutura.tubos[{i}].di" for i in range(4)], "formula": "0.012 - 2*t"}]}],
            "regra": json.loads((RAIZ / "cases" / "regras" / "sae2026_regular.json").read_text(encoding="utf8")), "cenario": {"NR": 185.0},
            "restricoes": [{"nome": "margem_estatica", "formula": "margem_estatica", "limite": 0.05, "tipo": "min"},
                           {"nome": "margem_estrutural", "formula": "margem_estrutural", "limite": 0.0, "tipo": "min"},
                           {"nome": "defl_canard", "formula": "defl_trim_decolagem", "limite": 20.0, "tipo": "max"},
                           {"nome": "trim_fecha", "formula": "trim_decolagem_fecha", "limite": 1.0, "tipo": "min"}],
            "analise": {"T0": 45.0, "V0": 28.0, "pista_m": 55.0, "obstaculo_m": 0.9, "massa_projeto": 18.0, "carga_ref_kg": 9.0, "carga_x": "xc",
                        "trim_decolagem": {"fator_v": 1.2},
                        "malha": {"n_span": 12, "n_chord": 2, "n_perfil": 24, "n_por_baia": 2}}}

if __name__ == "__main__":
    import os
    prob = problema(os.environ.get("ESQUEMA", "asa_canard.json"))
    if sys.argv[1:] == ["avalia"]:
        r = P.avalia(prob, {})
        print(json.dumps({k: v for k, v in r.items() if k != "resultados"}, ensure_ascii=False, default=str)[:1500])
        print(json.dumps(r.get("resultados"), ensure_ascii=False, default=str)[:3500])
        raise SystemExit
    pop, ger, sem, proc = (int(v) for v in (sys.argv[1:] + ["12", "20", "1", "4"][len(sys.argv) - 1:])[:4])
    t0 = time.time()
    ini = []
    for arq in filter(None, os.environ.get("INICIAIS", "").split(",")):
        d_ = json.loads((AQUI / "saida" / arq).read_text(encoding="utf8"))
        ini += [a["x"] for a in d_["refino"] if a.get("viavel")] + [d_["historico"][-1]["melhor_x"]]
    r = B.evolui(prob, populacao=pop, geracoes=ger, semente=sem, processos=proc, inicial=ini or None,
                 ao_gerar=lambda g: print(g["geracao"], "melhor %.2f" % (g["melhor_objetivo"] or 0), g["melhor_viavel"], "viav", g["n_viaveis"], "div %.2f" % g["diversidade"],
                                          "%.0fs" % g["tempo_s"], {k: round(v, 3) for k, v in g["melhor_x"].items()}, flush=True))
    fin = B.refina(prob, r, quantos=3, processos=min(proc, 3))
    saida = AQUI / "saida"
    saida.mkdir(exist_ok=True)
    (saida / os.environ.get("SAIDA", "asa_canard.json")).write_text(json.dumps({"historico": r["historico"], "refino": fin}, ensure_ascii=False, default=str, indent=1), encoding="utf8")
    print("total %.0fs" % (time.time() - t0))
