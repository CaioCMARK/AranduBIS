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

def test_dobradica_entra_na_massa_e_valida():
    from aranduBIS.nucleo.modelador import aeronave_geometria as AG
    from aranduBIS.nucleo.modelador import superficies_comando as SC

    asa = {"nome": "e", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 20, "posicao": [0, 0, 0],
           "secoes": [{"y": -0.4, "xle": 0, "zle": 0, "corda": 0.2, "ainc": 0}, {"y": 0.4, "xle": 0, "zle": 0, "corda": 0.2, "ainc": 0}],
           "controles": [{"nome": "pr", "y": [0.0, 0.4], "xc": 0.7, "modo": "sim", "dobradica": "pino"}]}
    A = AG.constroi({"versao": 1, "nome": "t", "elementos": [asa]})
    it = [i for i in A.itens_massa if i["nome"] == "e.pr.dobradica"]
    assert len(it) == 1 and abs(it[0]["massa"] - 10e-3 * 0.4 * 2) < 1e-9
    assert SC.massa_dobradica({"y": [0.0, 0.4], "modo": "lado"}, 0.4) == 0.0
    asa["controles"][0]["dobradica"] = "inexistente"
    with pytest.raises(Exception):
        AG.constroi({"versao": 1, "nome": "t", "elementos": [asa]})
