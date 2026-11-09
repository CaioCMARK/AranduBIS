import copy
import json
from pathlib import Path

import pytest

from aranduBIS.nucleo.aero import limites as L

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def modelo():
    return json.loads((RAIZ / "cases/geometria/generico/generico.json").read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def res(modelo):
    return L.cl_max(modelo, 0.5)

def test_perfil_fora_do_banco_e_marcado_aproximado(res):
    asa = next(p for p in res["polares"] if p["superficie"] == "Asa")
    assert asa["origem"] == "aproximado" and "nao esta no banco" in asa["nota"]

def test_perfil_do_banco_nao_e_marcado(res):
    prof = next(p for p in res["polares"] if p["superficie"] == "Profundor")
    assert prof["origem"] == "banco" and prof["polar"] == "NACA0012@n4" and not prof["nota"]

def test_ncrit_escolhe_a_variante(modelo):
    m = copy.deepcopy(modelo)
    for e in m["elementos"]:
        if e["nome"] == "Profundor":
            e["perfil"] = "NACA 6412"
            for s in e.get("secoes", []):
                s.pop("perfil", None)
    b = L.banco()
    from aranduBIS.nucleo.aero.aeronave_vlm import superficies
    from aranduBIS.nucleo.aero.vlm import VLM
    pol, info = L.polares_da_aeronave(VLM(superficies(m), x_ref=0.5), ncrit=7)
    assert pol["Profundor"].nome.replace("_", "") == "NACA6412@n7" and info[1]["origem"] == "banco"

def test_cl_max_da_asa_e_menor_que_o_2d_e_plausivel(res):
    assert 1.0 < res["CL_max"] < 2.0
    assert 8.0 < res["alpha_estol"] < 22.0
    assert res["convergiu"]

def test_avisa_que_nao_foi_conferido_com_ensaio(res):
    assert any("ensaio" in a for a in res["avisos"])
