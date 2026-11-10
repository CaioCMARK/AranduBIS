import pytest

from aranduBIS.nucleo.otimiza import busca as B, problema as P

def _prob():
    return {"variaveis": [{"nome": "x", "minimo": -5.0, "maximo": 5.0, "padrao": 4.0}, {"nome": "y", "minimo": -5.0, "maximo": 5.0, "padrao": 4.0},
                          {"nome": "k", "minimo": 0, "maximo": 2, "padrao": 0, "valores": ["a", "b", "c"]}]}

def _falso(prob, x):
    viol = max(0.0, x["x"] + x["y"] - 2.0) / 2.0
    obj = -(x["x"] - 1) ** 2 - (x["y"] - 2) ** 2 + x["k"]
    return {"x": dict(x), "objetivo": obj, "pontuacao": obj, "violacao": viol, "viavel": viol <= 0, "falha": None}

def test_deb_prefere_viavel_e_depois_menor_violacao():
    v = {"violacao": 0.0, "objetivo": 1.0}; w = {"violacao": 0.0, "objetivo": 2.0}
    i = {"violacao": 0.5, "objetivo": 99.0}; j = {"violacao": 0.1, "objetivo": -9.0}
    assert B.melhor_que(w, v) and not B.melhor_que(v, w) and B.melhor_que(v, i) and B.melhor_que(j, i) and not B.melhor_que(i, j)

def test_evolucao_acha_o_otimo_restrito_e_repete_pela_semente(monkeypatch):
    monkeypatch.setattr(B.P, "avalia", _falso)
    r = B.evolui(_prob(), populacao=20, geracoes=60, semente=3)
    m = r["melhor"]
    assert m["violacao"] <= 1e-9 and m["x"]["k"] == 2.0 and m["x"]["x"] == pytest.approx(0.5, abs=0.05) and m["x"]["y"] == pytest.approx(1.5, abs=0.05)
    h = [g["melhor_objetivo"] for g in r["historico"] if g["melhor_viavel"]]
    assert all(b >= a - 1e-12 for a, b in zip(h, h[1:])) and r["avaliacoes"] == 20 * 61
    r2 = B.evolui(_prob(), populacao=20, geracoes=60, semente=3)
    assert r2["melhor"]["x"] == m["x"]
    assert B.evolui(_prob(), populacao=20, geracoes=5, semente=4)["melhor"]["x"] != B.evolui(_prob(), populacao=20, geracoes=5, semente=5)["melhor"]["x"]
