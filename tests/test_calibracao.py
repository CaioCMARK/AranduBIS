import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import calibracao as CA
from aranduBIS.nucleo.estrutura import flutter as FL

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def dados(biplano):
    return FL.dados_de_vibracao(biplano, "asa_inferior")

def _medidas(d, f_EI, f_GJ, r=0.28):
    obs = {"frequencias": [{"tipo": "flexao", "ordem": 1}, {"tipo": "torcao", "ordem": 1}],
           "flecha": [{"P_N": 10.0, "y_carga_m": float(d["y"][-1]), "y_medida_m": float(d["y"][-1])}],
           "torcao": [{"T_Nm": 0.5, "y_carga_m": float(d["y"][-1]), "y_medida_m": float(d["y"][-1])}]}
    mod, _ = CA._modelo(d, f_EI, f_GJ, r, obs)
    obs["frequencias"][0]["hz"], obs["frequencias"][1]["hz"] = float(mod[0]), float(mod[1])
    obs["flecha"][0]["w_m"] = float(mod[2])
    obs["torcao"][0]["theta_graus"] = float(mod[3])
    return obs

def test_frequencia_escala_com_a_raiz_da_rigidez(dados):
    b, _ = CA._modelo(dados, 1.0, 4.0, 0.28, {"frequencias": [{"tipo": "torcao", "ordem": 1}], "flecha": [], "torcao": []})
    c, _ = CA._modelo(dados, 1.0, 1.0, 0.28, {"frequencias": [{"tipo": "torcao", "ordem": 1}], "flecha": [], "torcao": []})
    assert b[0] == pytest.approx(2 * c[0], rel=0.02)

def test_flecha_estatica_fecha_com_a_formula_de_balanco(dados):
    y = dados["y"]
    EI = np.full(len(y), 150.0)
    L = y[-1]
    w = abs(CA._estatica(y, EI, np.full(len(y), 20.0), len(y) - 1, 0, 8.0, len(y) - 1))
    assert w == pytest.approx(8.0 * L ** 3 / (3 * 150.0), rel=1e-6)

def test_recupera_ei_e_gj_conhecidos(biplano, dados):
    obs = _medidas(dados, 1.30, 0.70)
    r = CA.calibra(biplano, "asa_inferior", obs)
    assert r["parametros"]["EI"] == pytest.approx(1.30, rel=0.02)
    assert r["parametros"]["GJ"] == pytest.approx(0.70, rel=0.02)
    assert r["rms_depois_pct"] < 0.5 < r["rms_antes_pct"]

def test_so_frequencias_nao_separam_tres_parametros(biplano, dados):
    obs = _medidas(dados, 1.2, 0.8)
    obs["flecha"], obs["torcao"] = [], []
    r = CA.calibra(biplano, "asa_inferior", obs, ajusta=("EI", "GJ", "r_giro"))
    assert any("subdeterminado" in a or "nao separam" in a for a in r["avisos"])

def test_sem_medidas_da_erro(biplano):
    with pytest.raises(ValueError):
        CA.calibra(biplano, "asa_inferior", {})

def test_fronteira_calibracao(biplano, dados):
    obs = _medidas(dados, 1.1, 0.9)
    r = AN.calibracao({"esquema": biplano, "observacoes": obs, "ajusta": ["EI", "GJ"]})
    assert "erro" not in r and r["parametros"]["EI"] == pytest.approx(1.1, rel=0.03)
    assert "erro" in AN.calibracao({"esquema": {"elementos": []}})
    assert "erro" in AN.calibracao({"esquema": biplano, "observacoes": {}})

def test_modo_de_qualquer_tipo_e_modo_ausente_nao_entra_na_media_antes(biplano, dados):
    obs = {"frequencias": [{"tipo": "todos", "ordem": 1, "hz": 7.0}, {"tipo": "flexao", "ordem": 1, "hz": 50.0}], "flecha": [], "torcao": []}
    r = CA.calibra(biplano, "asa_inferior", obs, ajusta=("GJ",))
    assert r["modelo_antes"][1] is None and r["erro_antes_pct"][1] is None
    assert r["rms_antes_pct"] < 100
    assert r["rotulos"][0] == "1o modo"
