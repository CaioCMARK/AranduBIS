import copy
import json
import math
from pathlib import Path

import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import flambagem as FL

RAIZ = Path(__file__).resolve().parents[1]
E, NU = 2.85e9, 0.3
G = E / (2 * (1 + NU))

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def pedido(biplano):
    return {"esquema": biplano, "Vc": 13.0, "Vd": 15.9, "CL_max": 1.97}

def test_placa_isotropica_quadrada_reproduz_k4():
    t, b = 1e-3, 0.1
    esperado = 4 * math.pi ** 2 * E / (12 * (1 - NU ** 2)) * (t / b) ** 2
    assert FL.sigma_cr_ortotropica(E, E, G, NU, t, b, b) == pytest.approx(esperado, rel=1e-9)

def test_casca_com_raio_infinito_vira_placa():
    t, a, b = 1e-3, 0.15, 0.1
    assert FL.sigma_cr_curvo(E, E, G, NU, t, a, b, float("inf")) == pytest.approx(FL.sigma_cr_ortotropica(E, E, G, NU, t, a, b), rel=1e-6)

def test_cilindro_longo_reproduz_a_formula_classica():
    t, R = 1e-3, 0.05
    classico = E * t / (R * math.sqrt(3 * (1 - NU ** 2)))
    assert FL.sigma_cr_curvo(E, E, G, NU, t, 2.0, 0.6, R, nm=400, nn=100) == pytest.approx(classico, rel=0.03)

def test_alma_longa_reproduz_k_de_cisalhamento():
    t, h = 2e-3, 0.04
    esperado = 5.34 * math.pi ** 2 * E / (12 * (1 - NU ** 2)) * (t / h) ** 2
    assert FL.tau_cr_alma(E, NU, t, h, 100 * h) == pytest.approx(esperado, rel=1e-3)

def test_painel_curvo_aguenta_mais_que_o_plano_e_curvatura_forte_mais_ainda():
    t, a, b = 1e-3, 0.1, 0.1
    plano = FL.sigma_cr_ortotropica(E, 0.12e9, 0.148e9, 0.01, t, a, b)
    assert FL.sigma_cr_curvo(E, 0.12e9, 0.148e9, 0.01, t, a, b, 0.09) > plano
    assert FL.sigma_cr_curvo(E, 0.12e9, 0.148e9, 0.01, t, a, b, 0.03) > FL.sigma_cr_curvo(E, 0.12e9, 0.148e9, 0.01, t, a, b, 0.09)

def test_paineis_do_modelo(biplano, pedido):
    a = AN.asa(pedido)["asas"][0]
    r = FL.verifica(biplano, "asa_inferior", a)
    assert len(r["paineis"]) >= 10 and r["nervuras"][0] == pytest.approx(0.0558)
    p = r["pior_pele"]
    assert p["margem_pele"] == pytest.approx(p["sigma_cr_MPa"] / p["sigma_pele_MPa"] - 1, rel=1e-6)
    assert p["knockdown_para_margem_zero"] == pytest.approx(0.5 * p["sigma_pele_MPa"] / p["sigma_cr_MPa"], rel=1e-6)
    r2 = FL.verifica(biplano, "asa_inferior", a, knockdown=1.0)
    assert r2["pior_pele"]["margem_pele"] > p["margem_pele"]

def test_chapeado_mais_grosso_ganha_margem(biplano, pedido):
    e2 = copy.deepcopy(biplano)
    for el in e2["elementos"]:
        if el.get("estrutura"):
            el["estrutura"]["chapeado"]["espessura"] = 0.002
    a1 = FL.verifica(biplano, "asa_inferior", AN.asa(pedido)["asas"][0])["pior_pele"]["sigma_cr_MPa"]
    a2 = FL.verifica(e2, "asa_inferior", AN.asa(dict(pedido, esquema=e2))["asas"][0])["pior_pele"]["sigma_cr_MPa"]
    assert a2 > 2 * a1

def test_fronteira_flambagem(pedido):
    r = AN.flambagem(pedido)
    assert "erro" not in r and r["critico"] and {a["nome"] for a in r["asas"]} == {"asa_inferior", "asa_superior"}
    assert AN.flambagem(dict(pedido, knockdown_pele=-1))["erro"]
