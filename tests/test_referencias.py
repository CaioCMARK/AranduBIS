import pytest

from aranduBIS.nucleo import configuracao as C
from aranduBIS.nucleo import referencias as R
from aranduBIS.fronteira import analise as AN

def test_fator_de_manobra_far23_confere_com_a_formula_e_o_teto():
    assert R.fator_manobra_positivo(5000 * R.LB) == pytest.approx(2.1 + 24000 / 15000)
    assert R.fator_manobra_positivo(15.0) == 3.8 and R.fator_manobra_positivo(None) == 3.8
    assert R.fator_manobra_positivo(10000 * R.LB) == pytest.approx(2.1 + 24000 / 20000)
    assert R.fator_manobra_negativo(3.8) == pytest.approx(-1.52)

def test_rajadas_e_velocidades_do_far23():
    assert R.RAJADA_VC_MS == pytest.approx(15.24) and R.RAJADA_VD_MS == pytest.approx(7.62)
    assert R.velocidade_mergulho(20.0) == 25.0 and R.FATOR_SEGURANCA == 1.5

def test_atmosfera_padrao():
    assert R.densidade_isa(0.0) == pytest.approx(1.225)
    assert R.densidade_isa(1000.0) == pytest.approx(1.1117, abs=2e-3)

def test_knockdown_sp8007_cai_com_r_sobre_t_e_fica_entre_0_e_1():
    k = [R.knockdown_sp8007(x) for x in (10, 100, 300, 1000)]
    assert all(0 < v < 1 for v in k) and k == sorted(k, reverse=True)
    assert R.knockdown_sp8007(100) == pytest.approx(0.581, abs=2e-3)

def test_opcoes_automaticas_seguem_as_outras_e_voltam_ao_automatico():
    c = C.Configuracao()
    assert (c.valor("estrutura.V_c"), c.valor("estrutura.V_d")) == (15.0, pytest.approx(18.75))
    c.definir("analise.velocidade_cruzeiro", 20.0)
    assert c.valor("estrutura.V_c") == 20.0 and c.valor("estrutura.V_d") == pytest.approx(25.0)
    c.definir("estrutura.V_d", 30.0)
    assert c.valor("estrutura.V_d") == 30.0 and c.manual("estrutura.V_d")
    c.definir("estrutura.V_d", None)
    assert c.valor("estrutura.V_d") == pytest.approx(25.0) and not c.manual("estrutura.V_d")
    c.definir("decolagem.altitude_densidade_m", 1330.0)
    assert c.valor("analise.rho") == pytest.approx(R.densidade_isa(1330.0))
    c.definir("dinamica.massa_kg", 100.0)
    assert c.valor("estrutura.n_max") == 3.8
    assert c.valor("estrutura.n_min") == pytest.approx(-1.52)
    c.definir("estrutura.n_max", 2.5)
    assert c.valor("estrutura.n_min") == pytest.approx(-1.0)

def test_valor_igual_ao_automatico_continua_fixado():
    c = C.Configuracao()
    c.definir("estrutura.V_c", 15.0)
    c.definir("analise.velocidade_cruzeiro", 22.0)
    assert c.valor("estrutura.V_c") == 15.0

def test_so_opcao_automatica_aceita_voltar_ao_automatico():
    c = C.Configuracao()
    with pytest.raises(C.ConfiguracaoInvalida):
        c.definir("estrutura.n_max_inexistente", None)
    with pytest.raises(C.ConfiguracaoInvalida):
        c.definir("analise.CL_alvo", None)
    c.definir("estrutura.fator_seguranca", 2.0)
    assert c.valor("estrutura.fator_seguranca") == 2.0 and c.manual("estrutura.fator_seguranca")
    c.definir("estrutura.fator_seguranca", None)
    assert c.valor("estrutura.fator_seguranca") == 1.5 and not c.manual("estrutura.fator_seguranca")

def test_opcoes_de_referencia_dizem_a_fonte():
    for k in ("estrutura.fator_seguranca", "estrutura.rajada_Vc", "estrutura.fator_pouso", "estrutura.balsa_E", "decolagem.mu"):
        assert C.opcao(k).fonte and C.opcao(k).referencia

def test_nenhum_padrao_vem_de_uma_aeronave_especifica():
    c = C.Configuracao()
    assert c.valor("decolagem.altitude_densidade_m") == 0.0 and c.valor("dinamica.massa_kg") == 0.0
    for o in C.OPCOES:
        txt = (o.ajuda + o.rotulo).lower()
        assert "ipt" not in txt.split() and "referência do projeto" not in txt and "calibrado" not in txt

def test_api_sem_velocidade_pede_a_velocidade_em_vez_de_assumir_uma():
    import json
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    d = json.loads((raiz / "cases/geometria/monoplano/monoplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(raiz / "cases/geometria/monoplano")
    r = AN.torcao({"esquema": d})
    assert "Vd" in r["erro"] or "Vc" in r["erro"]
    assert "erro" not in AN.torcao({"esquema": d, "Vc": 12.0})
    assert "erro" not in AN.torcao({"esquema": d, "Vd": 15.0})
