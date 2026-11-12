import numpy as np
import pytest

from aranduBIS.nucleo.estrutura import flutter as FL

FT, SLUG, LBF = 0.3048, 14.5939, 4.44822

def goland(n=41):
    L, c = 20 * FT, 6 * FT
    y = np.linspace(0, L, n)
    m = np.full(n, 0.746 * SLUG / FT)
    EI = np.full(n, 23.65e6 * LBF * FT ** 2)
    GJ = np.full(n, 2.39e6 * LBF * FT ** 2)
    return y, np.full(n, c), EI, GJ, np.full(n, 0.33), m

def test_frequencia_de_flexao_do_balanco_uniforme():
    y = np.linspace(0, 1.2, 41)
    EI, m = 200.0, 0.8
    v = FL.modos_de_vibracao(y, np.full(41, EI), np.full(41, 1e6), np.full(41, m), np.zeros(41), np.full(41, 1e-6), 3)
    assert v["f_hz"][0] == pytest.approx(1.8751 ** 2 / (2 * np.pi) * np.sqrt(EI / (m * 1.2 ** 4)), rel=2e-3)
    assert v["natureza"][0] == "flexao"

def test_frequencia_de_torcao_do_balanco_uniforme():
    y = np.linspace(0, 1.2, 41)
    GJ, Ia = 30.0, 0.02
    v = FL.modos_de_vibracao(y, np.full(41, 1e6), np.full(41, GJ), np.full(41, 0.8), np.zeros(41), np.full(41, Ia), 4)
    f_t = 1 / (4 * 1.2) * np.sqrt(GJ / Ia)
    assert min(abs(f - f_t) for f in v["f_hz"]) / f_t < 2e-3
    assert "torcao" in v["natureza"]

def test_desbalanceamento_acopla_flexao_e_torcao():
    y = np.linspace(0, 1.2, 31)
    kw = dict(EI=np.full(31, 200.0), GJ=np.full(31, 30.0), m=np.full(31, 0.8), Ia=np.full(31, 0.02))
    a = FL.modos_de_vibracao(y, kw["EI"], kw["GJ"], kw["m"], np.zeros(31), kw["Ia"], 2)["f_hz"]
    b = FL.modos_de_vibracao(y, kw["EI"], kw["GJ"], kw["m"], np.full(31, 0.8 * 0.05), kw["Ia"] + 0.8 * 0.05 ** 2, 2)["f_hz"]
    assert b[0] < a[0] < a[1] < b[1]

def test_asa_de_goland_flutter_perto_de_135_m_s():
    y, c, EI, GJ, ea, _ = goland()
    m = np.full(len(y), 0.746 * SLUG / FT)
    r = FL.flutter(y, c, EI, GJ, ea, m, 0.10, 0.25, rho=1.225, Vmax=200.0, n_V=50, n_modos=6)
    assert r["VF"] == pytest.approx(135.6, rel=0.06)
    assert r["f_flutter_hz"] == pytest.approx(11.25, rel=0.15)

def test_escala_exata_rigidez_x4_dobra_a_velocidade_de_flutter():
    y, c, EI, GJ, ea, _ = goland(21)
    m = np.full(len(y), 0.746 * SLUG / FT)
    a = FL.flutter(y, c, EI, GJ, ea, m, 0.10, 0.25, rho=1.225, Vmax=200.0, n_V=50, n_modos=4)["VF"]
    b = FL.flutter(y, c, 4 * EI, 4 * GJ, ea, m, 0.10, 0.25, rho=1.225, Vmax=400.0, n_V=100, n_modos=4)["VF"]
    assert b == pytest.approx(2 * a, rel=0.02)

def test_cg_a_frente_da_linha_elastica_nao_flutua():
    y, c, EI, GJ, ea, _ = goland(21)
    m = np.full(len(y), 0.746 * SLUG / FT)
    r = FL.flutter(y, c, EI, GJ, ea, m, -0.05, 0.25, rho=1.225, Vmax=250.0, n_V=40, n_modos=4)
    assert r["VF"] is None

def test_cg_mais_atras_baixa_a_velocidade_de_flutter():
    y, c, EI, GJ, ea, _ = goland(21)
    m = np.full(len(y), 0.746 * SLUG / FT)
    v1 = FL.flutter(y, c, EI, GJ, ea, m, 0.08, 0.25, rho=1.225, Vmax=250.0, n_V=50, n_modos=4)["VF"]
    v2 = FL.flutter(y, c, EI, GJ, ea, m, 0.14, 0.25, rho=1.225, Vmax=250.0, n_V=50, n_modos=4)["VF"]
    assert v1 is not None and v2 is not None and v2 < v1

def _aeronave():
    import json
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1]
    d = json.loads((raiz / "cases/geometria/biplano/biplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(raiz / "cases/geometria/biplano")
    return d

def test_fronteira_devolve_as_duas_asas_com_frequencias():
    from aranduBIS.fronteira import analise as AN
    r = AN.flutter({"esquema": _aeronave(), "Vd": 15.9})
    assert "erro" not in r and {a["nome"] for a in r["asas"]} == {"asa_inferior", "asa_superior"}
    for a in r["asas"]:
        assert len(a["f_vacuo_hz"]) == 8 and a["f_vacuo_hz"][0] > 0 and a["massa_semi_asa_kg"] > 0
        assert len(a["V"]) == len(a["amortecimento"][0]) == len(a["freq_hz"][0])
        assert 0.0 < a["x_cg_c"] < 1.0

def test_massa_e_cg_informados_prevalecem():
    from aranduBIS.fronteira import analise as AN
    r = AN.flutter({"esquema": _aeronave(), "Vd": 15.9, "massa_asa_kg": 0.5, "x_cg_c": 0.3})
    a = r["asas"][0]
    assert a["massa_semi_asa_kg"] == 0.5 and a["x_cg_c"] == 0.3 and a["origem_massa"] == "informada"

def test_sem_estrutura_da_erro_claro_no_flutter():
    from aranduBIS.fronteira import analise as AN
    assert "erro" in AN.flutter({"esquema": {"elementos": []}})
