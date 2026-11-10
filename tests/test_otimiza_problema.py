import json
from pathlib import Path

import pytest

from aranduBIS.nucleo.otimiza import problema as P

RAIZ = Path(__file__).resolve().parents[1]

def _base():
    sec = lambda y, c: {"y": y, "xle": 0.0, "zle": 0.0, "corda": c, "ainc": 0.0}
    asa = {"nome": "asa", "tipo": "asa", "perfil": "NACA 4412", "n_perfil": 20, "posicao": [0.0, 0.0, 0.0], "material": "isopor",
           "secoes": [sec(-1.2, 0.3), sec(0.0, 0.3), sec(1.2, 0.3)]}
    eh = {"nome": "eh", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 20, "posicao": [1.0, 0.0, 0.0], "material": "isopor",
          "secoes": [sec(-0.35, 0.16), sec(0.35, 0.16)]}
    fixo = {"nome": "fixos", "tipo": "ponto", "massa": 2.0, "posicao": [0.05, 0.0, 0.0]}
    return {"versao": 1, "nome": "t", "unidade": "m", "elementos": [asa, eh, fixo], "marcas": []}

def _prob():
    reg = json.loads((RAIZ / "cases" / "regras" / "sae2026_regular.json").read_text(encoding="utf8"))
    return {"base": _base(),
            "variaveis": [{"nome": "b", "minimo": 1.6, "maximo": 4.4, "padrao": 2.4}, {"nome": "afil", "minimo": 0.4, "maximo": 1.0, "padrao": 1.0},
                          {"nome": "perfil", "minimo": 0, "maximo": 1, "padrao": 0, "valores": ["NACA 4412", "NACA 2412"]}],
            "grandezas": [{"nome": "ct", "formula": "0.3 * afil"}],
            "ligacoes": [{"alvo": "asa.secoes[0].y", "formula": "-b / 2"}, {"alvo": "asa.secoes[2].y", "formula": "b / 2"},
                         {"alvos": ["asa.secoes[0].corda", "asa.secoes[2].corda"], "formula": "ct"},
                         {"alvo": "asa.perfil", "formula": "perfil", "valores": ["NACA 4412", "NACA 2412"]}],
            "regra": reg, "cenario": {"NR": 185.0},
            "restricoes": [{"nome": "margem_estatica", "formula": "margem_estatica", "limite": 0.05, "tipo": "min"}],
            "analise": {"T0": 45.0, "V0": 28.0, "pista_m": 55.0, "obstaculo_m": 0.9}}

def test_ligacoes_escrevem_em_qualquer_numero_do_modelo():
    prob = _prob()
    assert P.confere(prob) == []
    esq, ctx = P.monta(prob, {"b": 3.0, "afil": 0.5, "perfil": 1})
    asa = esq["elementos"][0]
    assert asa["secoes"][0]["y"] == -1.5 and asa["secoes"][2]["y"] == 1.5 and asa["secoes"][0]["corda"] == pytest.approx(0.15) and asa["perfil"] == "NACA 2412"
    assert prob["base"]["elementos"][0]["secoes"][0]["y"] == -1.2
    assert P.le(esq, "eh.posicao[0]") == 1.0
    assert P.monta(prob, {"b": 99.0})[1]["b"] == 4.4
    with pytest.raises(P.ProblemaInvalido):
        P.poe(esq, "nao_existe.corda", 1.0)
    ruim = dict(prob, ligacoes=[{"alvo": "asa.secoes[9].y", "formula": "b"}])
    assert any("nao existe" in m for m in P.confere(ruim))

def test_avaliacao_encadeada_mede_restricoes_e_nunca_levanta():
    prob = _prob()
    r = P.avalia(prob, {"b": 2.4, "afil": 1.0, "perfil": 0})
    q = r["resultados"]
    assert r["falha"] is None and r["pontuacao"] > 0 and r["objetivo"] == r["pontuacao"]
    assert q["envergadura"] == pytest.approx(2.4, abs=1e-6) and q["n_superficies"] == 2 and q["PV"] > 2.0 and q["CP_bruta"] > 0
    nomes = {c["nome"]: c for c in r["restricoes"]}
    assert {"envergadura", "potencia", "peso_total", "margem_estatica"} <= set(nomes) and nomes["envergadura"]["folga"] == pytest.approx(1.6, abs=1e-6)
    g = P.avalia(prob, {"b": 4.4, "afil": 1.0, "perfil": 0})
    c = {c["nome"]: c for c in g["restricoes"]}["envergadura"]
    assert not g["viavel"] and c["violacao"] == pytest.approx(0.1, abs=1e-6) and g["violacao"] >= 0.1 and g["pontuacao"] is not None
    quebrado = dict(prob, base={"versao": 1, "nome": "x", "elementos": [dict(_base()["elementos"][0], material=None)]}, ligacoes=[], restricoes=[])
    f = P.avalia(quebrado, {})
    assert f["falha"]["etapa"] == "geometria e massa" and f["violacao"] > 10 and f["objetivo"] is None

def test_malha_grossa_da_triagem_ordena_como_a_completa():
    prob = _prob()
    grossa = dict(prob, analise=dict(prob["analise"], malha={"n_span": 12, "n_chord": 2, "n_perfil": 16, "n_por_baia": 2}))
    bs = (1.8, 2.4, 3.2)
    cheia = [P.avalia(prob, {"b": b, "afil": 1.0, "perfil": 0}) for b in bs]
    rapida = [P.avalia(grossa, {"b": b, "afil": 1.0, "perfil": 0}) for b in bs]
    assert all(r["falha"] is None for r in cheia + rapida)
    for a, c in zip(cheia, rapida):
        assert c["resultados"]["PV"] == pytest.approx(a["resultados"]["PV"], rel=0.02)
        assert c["resultados"]["CL_max"] == pytest.approx(a["resultados"]["CL_max"], rel=0.06)
    ordem = lambda L: sorted(range(len(L)), key=lambda i: L[i]["pontuacao"])
    assert ordem(cheia) == ordem(rapida)

def test_massas_de_sistema_entram_por_formula_e_pesam_no_vazio():
    prob = _prob()
    sistema = json.loads((RAIZ / "cases" / "otimiza" / "massas_sistema_convencional.json").read_text(encoding="utf8"))
    com = dict(prob, grandezas=prob["grandezas"] + sistema["grandezas"], massas=sistema["massas"])
    a = P.avalia(prob, {"b": 2.4, "afil": 1.0, "perfil": 0})["resultados"]
    b = P.avalia(com, {"b": 2.4, "afil": 1.0, "perfil": 0})["resultados"]
    assert b["massas_sistema_kg"] > 0.7 and b["PV"] == pytest.approx(a["PV"] + b["massas_sistema_kg"], rel=1e-6)
    grande = P.avalia(com, {"b": 3.4, "afil": 1.0, "perfil": 0})["resultados"]
    assert grande["massas_sistema_kg"] > b["massas_sistema_kg"] + 0.05

def test_dimensionamento_reforca_ate_a_margem_alvo_e_pesa_mais():
    base = json.loads((RAIZ / "cases" / "geometria" / "biplano" / "biplano_2025.json").read_text(encoding="utf8"))
    base["_pasta"] = str(RAIZ / "cases" / "geometria" / "biplano")
    A = ["asa_inferior", "asa_superior"]; nt = len(base["elementos"][0]["estrutura"]["tubos"])
    prob = _prob()
    prob.update(base=base, grandezas=[], restricoes=[], variaveis=[{"nome": "b", "minimo": 2.4, "maximo": 4.0, "padrao": 3.6}],
                ligacoes=[{"alvos": [f"{a}.secoes[0].y" for a in A], "formula": "-b / 2"}, {"alvos": [f"{a}.secoes[4].y" for a in A], "formula": "b / 2"}])
    prob["analise"] = {"T0": 45.0, "V0": 28.0, "pista_m": 55.0, "obstaculo_m": 0.9, "massa_projeto": 17.0, "malha": {"n_span": 12, "n_chord": 2, "n_perfil": 16, "n_por_baia": 1}}
    dim = lambda alvo: [{"nome": "parede", "elementos": A, "ajuste": {"nome": "t", "minimo": 0.0001, "maximo": 0.0018}, "margem_alvo": alvo,
                         "ligacoes": [{"alvos": [f"{a}.estrutura.tubos[{i}].di" for a in A for i in range(nt)], "formula": "0.004 - 2*t"}]}]
    leve = P.avalia(dict(prob, dimensionamento=dim(0.0)), {"b": 3.6})
    forte = P.avalia(dict(prob, dimensionamento=dim(0.5)), {"b": 3.6})
    assert leve["falha"] is None and forte["falha"] is None
    dl, df = leve["resultados"]["dimensionamento"][0], forte["resultados"]["dimensionamento"][0]
    assert dl["atingiu"] and df["atingiu"] and dl["margem"] >= -1e-3 and df["margem"] >= 0.5 - 1e-3
    assert df["valor"] > dl["valor"] and forte["resultados"]["PV"] > leve["resultados"]["PV"]
    assert forte["resultados"]["margem_estrutural"] == pytest.approx(df["margem"])

def test_retira_e_estica_alongam_o_boom_e_pesam_mais():
    from aranduBIS.nucleo.modelador import aeronave_geometria as AG
    base = json.loads((RAIZ / "cases" / "geometria" / "biplano" / "biplano_2025.json").read_text(encoding="utf8"))
    base["_pasta"] = str(RAIZ / "cases" / "geometria" / "biplano")
    prob = {"base": base, "retira": ["massa_equivalente"], "variaveis": [{"nome": "lb", "minimo": 0.8, "maximo": 2.0, "padrao": 1.3}], "grandezas": [],
            "ligacoes": [{"estica": {"elementos": ["boom_tubos"], "de": 0.30, "fim": "lb"}}, {"alvos": ["empenagem_h.posicao[0]", "deriva.posicao[0]"], "formula": "lb"}]}
    def boom(lb):
        esq, _ = P.monta(prob, {"lb": lb})
        assert all(e["nome"] != "massa_equivalente" for e in esq["elementos"])
        mc = AG.massa_e_cg(AG.constroi(esq))
        return sum(q["massa"] for q in mc["itens"] if str(q["nome"]).startswith("boom")), max(n[0] for e in esq["elementos"] if e["nome"] == "boom_tubos" for n in e["nos"])
    (m1, x1), (m2, x2) = boom(1.0), boom(1.8)
    assert x1 == pytest.approx(1.0) and x2 == pytest.approx(1.8) and m2 > 1.5 * m1

def test_pecas_com_catalogo_trocam_massa_e_custo_pela_escolha():
    prob = _prob()
    prob["variaveis"].append({"nome": "servo", "minimo": 0, "maximo": 1, "padrao": 0, "valores": ["padrao", "leve"]})
    sistema = json.loads((RAIZ / "cases" / "otimiza" / "massas_sistema_convencional.json").read_text(encoding="utf8"))
    sistema["massas"][0]["escolha"] = "servo"
    prob.update(grandezas=prob["grandezas"] + sistema["grandezas"], massas=sistema["massas"])
    a = P.avalia(prob, {"b": 2.4, "afil": 1.0, "perfil": 0, "servo": 0})["resultados"]
    b = P.avalia(prob, {"b": 2.4, "afil": 1.0, "perfil": 0, "servo": 1})["resultados"]
    assert b["massas_sistema_kg"] < a["massas_sistema_kg"] and b["custo_pecas"] > a["custo_pecas"]
    assert {p["opcao"] for p in a["pecas"] if p["opcao"]} == {"servo padrao"} and b["pecas"][0]["opcao"] == "servo leve"

def test_dimensionamento_de_reversao_com_fe_reforca_a_secao_aberta_com_x():
    import copy
    base = json.loads((RAIZ / "cases" / "geometria" / "biplano" / "biplano_2025.json").read_text(encoding="utf8"))
    base["_pasta"] = str(RAIZ / "cases" / "geometria" / "biplano")
    el = next(e for e in base["elementos"] if e["nome"] == "asa_inferior")
    ch = el["estrutura"]["chapeado"]; ch["ate_xc_y"] = [[p[0], 0.12] for p in ch["ate_xc_y"]]; ch["ate_xc"] = 0.12
    esq = copy.deepcopy(base)
    d = {"nome": "x", "tipo": "reversao", "fe": True, "elementos": ["asa_inferior"], "ajuste": {"nome": "a", "minimo": 0.0005, "maximo": 0.02}, "margem_alvo": -0.4,
         "iteracoes": 6, "ligacoes": [{"alvos": [f"asa_inferior.estrutura.cruzadas[{i}].area_m2" for i in range(2)], "formula": "a"}]}
    from aranduBIS.nucleo.otimiza import dimensiona as DM
    sem = DM.margem(esq, dict(d, fe=False), [], 1.2)
    com = DM.margem(esq, d, [], 1.2)
    assert com > sem
    r = DM.dimensiona(esq, [d], [], {}, 1.2)[0]
    assert r["atingiu"] and r["margem"] >= -0.4 - 1e-3 and 0.0005 < r["valor"] < 0.02
    assert DM.dimensiona(copy.deepcopy(base), [dict(d, margem_alvo=0.5)], [], {}, 1.2)[0]["atingiu"] is False
