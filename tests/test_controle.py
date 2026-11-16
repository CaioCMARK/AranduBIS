import copy
import json
from pathlib import Path

import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.aero.controle import autoridade_rolagem, comandos_de_rolagem

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def monoplano():
    d = json.loads((RAIZ / "cases/geometria/monoplano/monoplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/monoplano")
    return d

@pytest.fixture(scope="module")
def r(monoplano):
    return autoridade_rolagem(monoplano, massa_kg=11.0, raios={})

def test_acha_os_dois_ailerons(monoplano):
    nomes = {c["nome"] for _, c in comandos_de_rolagem(monoplano)}
    assert nomes == {"aileron"}

def test_so_sobe_tem_menos_autoridade_que_sobe_e_desce(r):
    a, b = r["opcoes"]["sobe_desce"], r["opcoes"]["so_sobe"]
    assert a["pb2V"] > b["pb2V"] > 0
    assert 1.3 < a["pb2V"] / b["pb2V"] < 3.0
    assert a["Cl_comando"] * b["Cl_comando"] > 0
    assert a["tempo_inclinacao_s"] < b["tempo_inclinacao_s"]

def test_curva_cresce_com_a_deflexao(r):
    for k in ("sobe_desce", "so_sobe"):
        y = r["curva"][k]
        assert all(y[i + 1] > y[i] for i in range(len(y) - 1))

def test_sem_aileron_avisa(monoplano):
    d = copy.deepcopy(monoplano)
    for e in d["elementos"]:
        e["controles"] = [c for c in e.get("controles", []) if c.get("modo") != "anti"]
    with pytest.raises(ValueError, match="ailerons"):
        autoridade_rolagem(d, massa_kg=15.0, raios={})
    assert "erro" in AN.controle({"esquema": d, "massa_kg": 15.0, "raios": {}})

def test_fronteira_devolve_as_opcoes(monoplano):
    out = AN.controle({"esquema": monoplano, "V": 15, "massa_kg": 15.0, "raios": {}, "sobe_max": 20, "desce_max": 20})
    assert set(out["opcoes"]) == {"sobe_desce", "so_sobe"} and out["opcoes"]["sobe_desce"]["sobe"] == 20

def test_margem_de_estol_local(r):
    sem = r["estol_sem_comando"]["delta_alpha_graus"]
    a, b = r["opcoes"]["sobe_desce"]["estol_local"], r["opcoes"]["so_sobe"]["estol_local"]
    assert 0 <= a["delta_alpha_graus"] < sem
    assert b["delta_alpha_graus"] > a["delta_alpha_graus"]
    assert a["cl_demanda"] > b["cl_demanda"] > 0 and a["cl_max_perfil"] > 0

def test_momento_de_charneira_cresce_com_v2(monoplano):
    from aranduBIS.fronteira import analise as AN
    a = AN.controle({"esquema": monoplano, "V": 15, "massa_kg": 15.0, "raios": {}, "V_servo": 12})["servo"]["itens"]
    b = AN.controle({"esquema": monoplano, "V": 15, "massa_kg": 15.0, "raios": {}, "V_servo": 24})["servo"]["itens"]
    assert len(a) == 2 and all(i["momento_Nm"] > 0 and i["torque_kgfcm"] > 0 for i in a)
    for x, y in zip(a, b):
        assert 2.5 < y["momento_Nm"] / x["momento_Nm"] < 5.5
