import copy
import json
import warnings
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.nucleo.aero.equilibrio import comando_automatico, longitudinal, monta
from aranduBIS.nucleo.modelador import aeronave_geometria as AG

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def convencional():
    return json.loads((RAIZ / "cases/geometria/generico/generico.json").read_text(encoding="utf-8"))

def canard(d):
    c = copy.deepcopy(d)
    c["elementos"][1]["posicao"] = [-3.0, 0.0, 0.2]
    return c

def voadora(d):
    f = copy.deepcopy(d)
    f["elementos"] = [e for e in f["elementos"] if e["nome"] == "Asa"]
    f["elementos"][0]["secoes"] = [dict(s, xle=abs(s["y"]) * 0.5, ainc=2.0 if s["y"] == 0 else -1.0)
                                   for s in f["elementos"][0]["secoes"]]
    return f

def test_convencional_estavel_e_equilibra(convencional):
    r = longitudinal(convencional, 0.5, CL_alvo=0.8)
    assert r["estavel"] and r["margem_estatica"] > 0.1
    assert r["comando"] == "Profundor"
    assert r["trim"]["residuo"] < 1e-6 and r["trim"]["CL"] == pytest.approx(0.8, abs=1e-6)
    assert r["trim"]["contribuicao"]["Profundor"] < 0
    assert not r["avisos"]

def test_margem_e_a_distancia_ao_ponto_neutro_em_cordas(convencional):
    a, b = longitudinal(convencional, 0.5), longitudinal(convencional, 0.9)
    assert a["ponto_neutro"] == pytest.approx(b["ponto_neutro"], abs=0.01)
    assert a["margem_estatica"] - b["margem_estatica"] == pytest.approx(0.4 / a["c_ref"], rel=0.02)

def test_cg_atras_do_ponto_neutro_e_instavel_e_avisa(convencional):
    r = longitudinal(convencional, 1.2)
    assert not r["estavel"] and r["margem_estatica"] < 0
    assert any("Instavel" in a for a in r["avisos"])

def test_canard_usa_a_superficie_da_frente_como_comando(convencional):
    r = longitudinal(canard(convencional), 0.5, CL_alvo=0.8)
    assert r["comando"] == "Profundor"
    assert r["ponto_neutro"] < longitudinal(convencional, 0.5)["ponto_neutro"]
    assert r["trim"]["residuo"] < 1e-6

def test_asa_voadora_nao_tem_comando_e_acha_o_alpha_de_momento_nulo(convencional):
    r = longitudinal(voadora(convencional), 0.9, CL_alvo=0.5)
    assert r["comando"] is None and r["estavel"]
    assert abs(r["trim"]["Cm"]) < 1e-6 and r["trim"]["deflexao"] == 0.0

def test_biplano_conta_as_duas_asas_na_referencia():
    r = longitudinal(AG.exemplo_biplano_demo(), 0.3, V=20.0, CL_alvo=1.0)
    ref = {s["nome"] for s in r["superficies"] if s["referencia"]}
    assert ref == {"asa_inferior", "asa_superior"}
    assert r["comando"] == "empenagem_h"

def test_deriva_nao_entra_na_referencia_nem_vira_comando(convencional):
    vlm = monta(convencional, 0.5)
    deriva = next(s for s in vlm.superficies if s.nome == "Deriva")
    assert not deriva.de_referencia
    assert comando_automatico(vlm.superficies, 0.5) == "Profundor"

def test_asa_retangular_bate_com_a_teoria():
    esq = AG.exemplo_asa_ar3()
    r = longitudinal(esq, 0.25)
    AR = 3.0
    helmbold = 2 * np.pi * AR / (2 + np.sqrt(4 + AR ** 2))
    assert r["CL_alpha"] == pytest.approx(helmbold, rel=0.1)

def test_resultado_vai_para_json(convencional):
    json.dumps(longitudinal(convencional, 0.5, CL_alvo=0.8))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        longitudinal(convencional, 0.5)

def test_helice_desenhada_como_asa_fica_fora_do_calculo(convencional):
    d = copy.deepcopy(convencional)
    d["elementos"].append({"tipo": "asa", "nome": "helice", "rolagem": 90.0, "guinada": 90.0, "posicao": [0.0, 0.0, 0.1],
                           "secoes": convencional["elementos"][1]["secoes"]})
    r = longitudinal(d, 0.5)
    assert "helice" not in [s["nome"] for s in r["superficies"]]
    assert any("helice" in a for a in r["avisos"])
