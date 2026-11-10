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
