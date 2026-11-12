import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import asa_fe as AF

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def r(biplano):
    return AN.torcao_fe({"esquema": biplano, "Vc": 13.0, "Vd": 15.9, "CL_max": 1.97})

def test_carga_nas_estacoes_fecha_em_zero_na_ponta():
    y = np.linspace(0, 1.0, 11)
    q = AF.carga_nas_estacoes(y, [0.1, 0.5, 0.9], [30.0, 20.0, 10.0])
    assert q[0] == pytest.approx(30.0) and q[-1] == pytest.approx(0.0)

def test_analitica_de_viga_uniforme_fecha_com_qL4_sobre_8EI():
    y = np.linspace(0, 1.2, 241)
    q = np.full_like(y, 50.0)
    w, th, M = AF.analitica(y, np.full_like(y, 0.3), np.full_like(y, 200.0), np.full_like(y, 25.0), np.full_like(y, 0.3), 0.25, q)
    assert w[-1] == pytest.approx(50.0 * 1.2 ** 4 / (8 * 200.0), rel=1e-3)
    assert M[0] == pytest.approx(50.0 * 1.2 ** 2 / 2, rel=1e-3)

def test_fronteira_devolve_as_duas_asas(r):
    assert "erro" not in r and {a["nome"] for a in r["asas"]} == {"asa_inferior", "asa_superior"}
    assert r["massa_kg"] > 0

def test_flecha_de_elementos_finitos_fecha_com_a_analitica(r):
    for a in r["asas"]:
        assert a["flecha_ponta_fe_m"] > 0
        assert a["razao_flecha"] == pytest.approx(1.0, abs=0.02)
        assert len(a["y"]) == len(a["w_fe"]) == len(a["theta_fe_graus"]) == a["n_nos"]
        assert a["caso"]

def test_torcao_tem_o_sinal_da_linha_elastica_e_ordem_da_analitica(r):
    for a in r["asas"]:
        assert np.isfinite(a["torcao_ponta_fe_graus"])
        assert np.sign(a["torcao_ponta_fe_graus"]) == np.sign(a["torcao_ponta_analitica_graus"])
        assert a["razao_torcao"] == pytest.approx(1.0, abs=0.05)

def test_sem_estrutura_da_erro_claro():
    out = AN.torcao_fe({"esquema": {"elementos": []}})
    assert "erro" in out

def test_torcao_enorme_gera_aviso(r):
    for a in r["asas"]:
        if abs(a["torcao_ponta_fe_graus"]) > 15.0:
            assert any("15 graus" in x for x in a["avisos"])
