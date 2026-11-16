import pytest

from aranduBIS.nucleo import variaveis as V

CONV = {"n_secoes_asa": 2, "n_asas": 1, "cauda": 1, "canard": 0}

def test_comandos_e_estrutura_nascem_travados_e_o_resto_livre():
    c = V.monta()
    assert not any(x.livre for x in c.v.values() if x.grupo == "comandos")
    assert all(x.livre for x in c.v.values() if x.grupo in ("asa", "empenagem", "fuselagem", "perfil", "trem", "massa"))

def test_asa_composta_ganha_variaveis_com_mais_secoes():
    c = V.monta()
    n2 = c.contagem(dict(CONV, n_secoes_asa=2))["total"]
    n3 = c.contagem(dict(CONV, n_secoes_asa=3))["total"]
    n5 = c.contagem(dict(CONV, n_secoes_asa=5))["total"]
    assert n3 - n2 == 6 and n5 - n2 == 18
    assert "asa_corda4" in [x.nome for x in c.livres(dict(CONV, n_secoes_asa=5))]
    assert "asa_corda4" not in [x.nome for x in c.livres(dict(CONV, n_secoes_asa=3))]

def test_genes_ligam_e_desligam_superficies():
    c = V.monta()
    sem = {x.nome for x in c.livres(CONV)}
    com = {x.nome for x in c.livres(dict(CONV, canard=1, n_asas=2, n_secoes_asa2=2))}
    assert "canard_area" not in sem and "canard_area" in com
    assert "asa2_b" not in sem and "asa2_b" in com
    assert "cauda_area" in sem and "cauda_area" not in {x.nome for x in c.livres(dict(CONV, cauda=0))}

def test_liberar_um_grupo_e_travar_uma_variavel():
    c = V.monta()
    antes = c.contagem(CONV)["total"]
    c.liberar("comandos")
    assert c.contagem(CONV)["total"] == antes + 4 and c.contagem(CONV)["comandos"] == 4
    c.travar("aileron_corda_rel", 0.3)
    assert c.projeto({"aileron_corda_rel": 0.1}, CONV)["aileron_corda_rel"] == 0.3
    c.travar("asa")
    assert "asa" not in c.contagem(CONV)

def test_projeto_usa_vetor_nas_livres_padrao_nas_travadas_e_omite_inativas():
    c = V.monta()
    p = c.projeto({"asa_b": 2.0, "aileron_corda_rel": 0.99}, CONV)
    assert p["asa_b"] == 2.0 and p["aileron_corda_rel"] == 0.25
    assert "canard_area" not in p and "asa_corda3" not in p

def test_erros_claros():
    c = V.monta()
    with pytest.raises(KeyError):
        c.liberar("naoexiste")
    with pytest.raises(ValueError):
        c.travar("asa_b", 99.0)
    with pytest.raises(ValueError):
        c.travar("asa", 1.0)
    with pytest.raises(ValueError):
        V.Variavel("x", "asa", 1.0, 2.0, 5.0)
