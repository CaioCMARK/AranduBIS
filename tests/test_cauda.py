import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import cauda as CA
from aranduBIS.nucleo.fe import le, Sistema

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def r(biplano):
    return CA.analisa(biplano)

def viga_simples(L=1.0, de=0.01, di=0.008):
    n = 8
    nos = [[L * i / n, 0.0, 0.0] for i in range(n + 1)]
    return {"versao": 1, "nome": "t", "elementos": [
        {"nome": "boom", "tipo": "trelica", "tubos": {"T": {"de": de, "di": di, "material": "tubo_carbono"}}, "nos": nos,
         "barras": [[i, i + 1, "T"] for i in range(n)]},
        {"nome": "empenagem_h", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 40, "posicao": [L - 0.0475, 0.0, 0.0],
         "secoes": [{"y": -0.2, "corda": 0.19}, {"y": 0.2, "corda": 0.19}]}]}

def test_modelo_tem_as_barras_do_esquema(biplano, r):
    n_barras = sum(len(e["barras"]) for e in biplano["elementos"] if e["tipo"] == "trelica")
    assert r["n_barras"] <= n_barras and r["n_barras"] > 0.9 * n_barras
    assert r["massa_kg"] == pytest.approx(0.57, abs=0.1)

def test_balanco_simples_confere_com_a_mao():
    esq = viga_simples()
    r = CA.analisa(esq, x_apoio=0.0, tailstrike_peso=1.0, peso_N=100.0)
    c = next(c for c in r["casos"] if c["caso"] == "tailstrike")
    I = np.pi / 64 * (0.01 ** 4 - 0.008 ** 4)
    E = 112e9
    assert c["deslocamento_ponta_mm"][2] == pytest.approx(1000 * 100.0 * 1.0 ** 3 / (3 * E * I), rel=1e-6)
    b = c["piores"][0]
    sigma = 1.2 * 100.0 * 1.0 * 0.005 / I
    assert b["margens"]["compressao"] == pytest.approx(1200e6 / sigma - 1, rel=2e-3)

def test_carga_maior_reduz_a_margem(biplano):
    a = CA.analisa(biplano, tailstrike_peso=0.5)
    b = CA.analisa(biplano, tailstrike_peso=3.0)
    ma = next(c["margem"] for c in a["casos"] if c["caso"] == "tailstrike")
    mb = next(c["margem"] for c in b["casos"] if c["caso"] == "tailstrike")
    assert mb < ma

def test_rajada_lateral_torce_o_boom(r):
    c = next(c for c in r["casos"] if c["caso"] == "rajada_lateral_Vc")
    assert abs(c["rotacao_h_graus"][0]) > 0

def test_deck_bdf_reproduz_a_deformada(biplano, r):
    m = le(r["bdf"])
    assert len(m.barras) == r["n_barras"] and "SOL 101" in r["bdf"]
    ref = next(c for c in r["casos"] if c["caso"] == "tailstrike")
    u = Sistema(m).estatica(next(i for i, c in enumerate(r["casos"], 1) if c["caso"] == "tailstrike"))["u"]
    assert max(abs(v[2]) for v in u.values()) * 1000 >= ref["flecha_ponta_mm"] - 1e-6

def test_fronteira_cauda(biplano):
    r2 = AN.cauda({"esquema": biplano, "com_cargas": False})
    assert "erro" not in r2 and r2["casos"][0]["caso"] == "trim" and r2["casos"][0]["descricao"].endswith("0.0 N")
    sem = copy.deepcopy(biplano)
    sem["elementos"] = [e for e in sem["elementos"] if e["tipo"] != "trelica"]
    assert "trelica" in AN.cauda({"esquema": sem, "com_cargas": False})["erro"]
