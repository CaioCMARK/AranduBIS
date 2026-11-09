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

def test_atitude_de_solo_vem_das_rodas():
    esq = {"elementos": [{"tipo": "roda", "posicao": [0.2, 0, -0.10], "diametro": 0.10},
                         {"tipo": "roda", "posicao": [-0.3, 0, -0.10], "diametro": 0.04}]}
    a = L.atitude_de_solo(esq)
    assert a == pytest.approx(-__import__("math").degrees(__import__("math").atan2(-0.03, 0.5)))
    assert L.atitude_de_solo({"elementos": []}) is None

def test_corrida_tem_cl_cd_e_parasita(modelo):
    r = L.cl_max(modelo, 0.5)
    c = r["corrida"]
    assert 0 < c["CL"] < r["CL_max"] and c["CD"] == pytest.approx(c["CDi"] + c["CDp"] + c["CD_parasita"])
    r2 = L.cl_max(modelo, 0.5, CdA_proprio=0.5, alpha_solo=3.0)
    assert r2["corrida"]["alpha"] == 3.0 and r2["corrida"]["origem"] == "voce"
    assert r2["corrida"]["CD_parasita"] == pytest.approx(0.5 / r2["corrida"]["S_ref"])
    assert r2["corrida"]["CL"] > c["CL"]

def test_parasita_ignora_camada_de_estrutura_e_tubos_dentro_de_placa():
    from aranduBIS.nucleo.aero.parasita import parasita
    caixa = [[0, 0], [0.5, 0], [0.5, 0.2], [0, 0.2]]
    esq = {"elementos": [
        {"tipo": "placa", "nome": "fus", "espessura": 0.1, "contorno": [[0, 0], [1.0, 0], [1.0, 0.05], [0, 0.05]]},
        {"tipo": "placa", "nome": "carga", "camada": "estrutura", "espessura": 0.1, "contorno": caixa},
        {"tipo": "trelica", "nome": "dentro", "tubos": {"a": {"de": 0.005}}, "nos": [[0.1, 0, 0.02], [0.5, 0, 0.02]], "barras": [[0, 1, "a"]]},
        {"tipo": "trelica", "nome": "fora", "tubos": {"a": {"de": 0.005}}, "nos": [[0.1, 0.5, 0.02], [0.1, 0.9, 0.02]], "barras": [[0, 1, "a"]]}]}
    p = parasita(esq, 1.0, 12.0)
    nomes = {x["nome"] for x in p["partes"]}
    assert "fus" in nomes and "fora" in nomes and "carga" not in nomes and "dentro" not in nomes
    assert next(x for x in p["partes"] if x["nome"] == "fora")["CdA"] == pytest.approx(1.1 * 0.005 * 0.4)
