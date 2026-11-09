import pytest

def test_charneira_em_x_fixo_fica_paralela_a_longarina():
    from aranduBIS.nucleo.modelador import superficies_comando as SC
    c = {"nome": "a", "y": [0.75, 1.3], "x": 0.172}
    xc_raiz = SC.charneira_em(c, 0.2955, 0.0169); xc_ponta = SC.charneira_em(c, 0.2029, 0.0293)
    assert xc_raiz * 0.2955 + 0.0169 == pytest.approx(0.172, abs=1e-9)
    assert xc_ponta * 0.2029 + 0.0293 == pytest.approx(0.172, abs=1e-9)
    assert xc_ponta > xc_raiz
    sec = [{"y": 0.0, "xle": 0.0, "corda": 0.4}, {"y": 0.153, "xle": 0.0, "corda": 0.396}, {"y": 1.55, "xle": 0.035, "corda": 0.16}]
    r = SC.resolve(c, sec)
    assert 0.05 < r["corda"] < 0.14
    assert SC.resolve({"y": [0, 1], "corda": 0.1}, sec)["corda"] == 0.1
