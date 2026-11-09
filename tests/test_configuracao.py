import pytest

from aranduBIS.nucleo import configuracao as C

def test_fabrica_funciona_sem_instalar_nada():
    c = C.Configuracao()
    assert c.valor("polares.fonte") == "banco" and c.problemas() == []

def test_ncrit_fixo_so_vale_quando_escolhido():
    c = C.Configuracao()
    assert not c.ativa("polares.ncrit")
    c.definir("polares.ncrit_modo", "fixo")
    c.definir("polares.ncrit", 6)
    assert c.ativa("polares.ncrit") and c.valor("polares.ncrit") == 6.0

def test_faixa_e_escolha_sao_recusadas():
    c = C.Configuracao()
    with pytest.raises(C.ConfiguracaoInvalida):
        c.definir("polares.ncrit", 40)
    with pytest.raises(C.ConfiguracaoInvalida):
        c.definir("polares.fonte", "magia")
    with pytest.raises(C.ConfiguracaoInvalida):
        c.definir("nao.existe", 1)

def test_avl_sem_caminho_diz_o_que_falta(tmp_path):
    c = C.Configuracao({"polares.fonte": "avl"})
    assert "informe o caminho do AVL" in c.problemas()[0]
    c.definir("polares.avl_caminho", str(tmp_path / "avl.exe"))
    assert "não encontrado" in c.problemas()[0]
    (tmp_path / "avl.exe").write_text("x")
    assert c.problemas() == []

def test_grava_so_o_que_mudou_e_volta_igual(tmp_path):
    c = C.Configuracao({"polares.ncrit_modo": "fixo", "polares.ncrit": 7})
    c.definir("polares.ncrit", 9)
    c.gravar(tmp_path / "cfg.json")
    d = C.Configuracao.ler(tmp_path / "cfg.json")
    assert d.mudancas() == {"polares.ncrit_modo": "fixo"}
    assert C.Configuracao.ler(tmp_path / "nao_existe.json").mudancas() == {}
