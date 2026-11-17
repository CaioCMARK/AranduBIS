"""Gera tres_superficies_livre2.json a partir de tres_superficies_livre.json: acrescenta segunda asa opcional
(biplano/tandem), cauda V central ou dupla e flecha/diedro em canard, empenagem e deriva."""
import copy
import json
from pathlib import Path

D = Path(__file__).parent
pr = json.loads((D / "tres_superficies_livre.json").read_text(encoding="utf8"))
PERF = pr["variaveis"][[v["nome"] for v in pr["variaveis"]].index("p_raiz")]["valores"]


def var(n, a, b, p, **k):
    d = {"nome": n, "minimo": a, "maximo": b, "padrao": p}
    d.update(k)
    return d


def vp(n, p):
    return var(n, 0, len(PERF) - 1, p, valores=PERF)


el = {e["nome"]: e for e in pr["base"]["elementos"]}
a2 = copy.deepcopy(el["canard"]); a2["nome"] = "asa2"; a2["posicao"] = [0.0, 0.0, 0.5]
dd = copy.deepcopy(el["deriva"]); dd["nome"] = "deriva_d"; dd["posicao"] = [1.95, 0.4, 0.22]
de = copy.deepcopy(el["deriva"]); de["nome"] = "deriva_e"; de["posicao"] = [1.95, -0.4, 0.22]
mont = {"nome": "montantes", "tipo": "ponto", "massa": 0.05, "posicao": [0.0, 0.0, 0.3], "nota": "Montantes e cabos da segunda asa (estimativa)."}
pr["base"]["elementos"] += [a2, dd, de, mont]
pr["grandezas"] = [{"nome": "yv", "formula": "min(y_v2, b_h * 0.5)"}]
pr["variaveis"] += [
    var("fl_can", 0.0, 0.15, 0.0), var("dz_can", -0.05, 0.15, 0.0), var("z_can", 0.05, 0.4, 0.17),
    var("fl_h", 0.0, 0.15, 0.0), var("dz_h", -0.05, 0.15, 0.0), var("z_h", 0.1, 0.5, 0.22),
    var("af_v", 0.4, 1.0, 0.8), var("fl_v", 0.0, 0.15, 0.0), vp("p_v", 0),
    var("tem_twin", 0, 1, 0, valores=[0, 1]), var("y_v2", 0.2, 0.7, 0.4),
    var("tem_asa2", 0, 1, 0, valores=[0, 1]), var("b_2", 0.6, 2.2, 1.4), var("c_2", 0.15, 0.5, 0.3),
    var("x_2", -0.3, 0.7, 0.1), var("z_2", 0.12, 0.7, 0.4), var("ainc_2", -1, 6, 2), var("fl_2", 0.0, 0.15, 0.0), var("dz_2", -0.05, 0.15, 0.0), vp("p_2", 5),
]
L = pr["ligacoes"]
L[:] = [l for l in L if not l.get("retira_se")]
L += [
    {"alvos": ["canard.secoes[0].xle", "canard.secoes[1].xle"], "formula": "fl_can"},
    {"alvos": ["canard.secoes[0].zle", "canard.secoes[1].zle"], "formula": "dz_can"},
    {"alvos": ["canard.posicao[2]"], "formula": "z_can"},
    {"alvos": ["empenagem_h.secoes[0].xle", "empenagem_h.secoes[1].xle"], "formula": "fl_h"},
    {"alvos": ["empenagem_h.secoes[0].zle", "empenagem_h.secoes[1].zle"], "formula": "dz_h"},
    {"alvos": ["empenagem_h.posicao[2]", "deriva.posicao[2]", "deriva_d.posicao[2]", "deriva_e.posicao[2]"], "formula": "z_h"},
    {"alvos": ["deriva.secoes[1].corda", "deriva_d.secoes[1].corda", "deriva_e.secoes[1].corda"], "formula": "c_v * af_v"},
    {"alvos": ["deriva.secoes[1].xle", "deriva_d.secoes[1].xle", "deriva_e.secoes[1].xle"], "formula": "fl_v"},
    {"alvos": ["deriva.secoes[0].perfil", "deriva.secoes[1].perfil", "deriva_d.secoes[0].perfil", "deriva_d.secoes[1].perfil", "deriva_e.secoes[0].perfil", "deriva_e.secoes[1].perfil"], "formula": "p_v", "valores": PERF},
    {"escala_y": {"elementos": ["deriva_d", "deriva_e"], "fator": "h_v / 0.4"}},
    {"alvos": ["deriva_d.secoes[0].corda", "deriva_e.secoes[0].corda"], "formula": "c_v"},
    {"alvos": ["deriva_d.posicao[0]", "deriva_e.posicao[0]"], "formula": "x_cauda"},
    {"alvos": ["deriva_d.posicao[1]"], "formula": "yv"},
    {"alvos": ["deriva_e.posicao[1]"], "formula": "-yv"},
    {"escala_y": {"elementos": ["asa2"], "fator": "b_2 / 0.9"}},
    {"alvos": ["asa2.secoes[0].corda", "asa2.secoes[1].corda"], "formula": "c_2"},
    {"alvos": ["asa2.secoes[0].ainc", "asa2.secoes[1].ainc"], "formula": "ainc_2"},
    {"alvos": ["asa2.secoes[0].xle", "asa2.secoes[1].xle"], "formula": "fl_2"},
    {"alvos": ["asa2.secoes[0].zle", "asa2.secoes[1].zle"], "formula": "dz_2"},
    {"alvos": ["asa2.secoes[0].perfil", "asa2.secoes[1].perfil"], "formula": "p_2", "valores": PERF},
    {"alvos": ["asa2.posicao[0]"], "formula": "x_2"},
    {"alvos": ["asa2.posicao[2]"], "formula": "z_2"},
    {"alvos": ["montantes.massa"], "formula": "0.03 + 0.04 * b_2"},
    {"alvos": ["montantes.posicao[0]"], "formula": "x_2 + 0.5 * c_2"},
    {"alvos": ["montantes.posicao[2]"], "formula": "0.5 * (z_2 + 0.2)"},
    {"retira_se": ["canard"], "formula": "1 - tem_can"},
    {"retira_se": ["deriva"], "formula": "tem_twin"},
    {"retira_se": ["deriva_d", "deriva_e"], "formula": "1 - tem_twin"},
    {"retira_se": ["asa2", "montantes"], "formula": "1 - tem_asa2"},
]
pr["descricao"] = "Gerador livre 2: asa em 3 estacoes com perfis independentes, canard opcional, segunda asa opcional (biplano/tandem), cauda central ou dupla, flecha e diedro nas superficies. Maximizar EE."
(D / "tres_superficies_livre2.json").write_text(json.dumps(pr, indent=1), encoding="utf8")
print(len(pr["variaveis"]), "variaveis")
