import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import vibracao as VB
from aranduBIS.nucleo.estrutura.materiais import propriedades

L, DE, DI = 1.0, 0.01, 0.008

def balanco(n=8):
    nos = [[L * i / n, 0.0, 0.0] for i in range(n + 1)]
    return {"versao": 1, "nome": "t", "elementos": [
        {"nome": "boom", "tipo": "trelica", "tubos": {"T": {"de": DE, "di": DI, "material": "tubo_carbono"}}, "nos": nos,
         "barras": [[i, i + 1, "T"] for i in range(n)]},
        {"nome": "empenagem_h", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 40, "posicao": [L - 0.0475, 0.0, 0.0],
         "secoes": [{"y": -0.2, "corda": 0.19}, {"y": 0.2, "corda": 0.19}]}]}

@pytest.fixture(scope="module")
def r():
    return VB.analisa(balanco(), massa_empenagem_h_kg=0.15, x_apoio=0.0, rpm_min=3000, rpm_max=9000)

def _modo(r, nome):
    return next(m for m in r["modos"] if m["natureza"] == nome)

def test_flexao_vertical_confere_com_o_balanco_analitico(r):
    esq = balanco()
    p = propriedades("tubo_carbono", esq, None, qualidade_carbono=1.0)
    I = np.pi / 64 * (DE ** 4 - DI ** 4)
    rho_lin = r["massa_trelica_kg"] / L
    f = VB.balanco_com_massa(p["E"], I, L, rho_lin, 0.15)
    assert _modo(r, "flexao vertical")["f_hz"] == pytest.approx(f, rel=0.02)

def test_massa_na_ponta_baixa_a_frequencia(r):
    for m in r["modos"][:3]:
        assert m["f_hz"] < 0.5 * m["f_sem_massas_hz"]

def test_torcao_do_boom_usa_a_inercia_de_rolagem_da_empenagem(r):
    esq = balanco()
    p = propriedades("tubo_carbono", esq, None, qualidade_carbono=1.0)
    J = 2 * np.pi / 64 * (DE ** 4 - DI ** 4)
    b = 0.4
    I_rol = sum(0.15 / 5 * (f * b / 2) ** 2 for f in (-0.8, -0.4, 0.0, 0.4, 0.8))
    f_t = np.sqrt(p["G"] * J / L / I_rol) / (2 * np.pi)
    assert _modo(r, "torcao do boom")["f_hz"] == pytest.approx(f_t, rel=0.04)

def test_sem_massas_avisa_e_da_as_frequencias_do_tubo_vazio():
    r = VB.analisa(balanco(), x_apoio=0.0)
    assert any("Nenhuma massa" in a for a in r["avisos"])
    assert r["modos"][0]["f_hz"] == pytest.approx(r["modos"][0]["f_sem_massas_hz"], rel=1e-6)

def test_massa_adicional_na_ponta_do_boom():
    a = VB.analisa(balanco(), massa_empenagem_h_kg=0.1, x_apoio=0.0)
    b = VB.analisa(balanco(), massa_empenagem_h_kg=0.1, x_apoio=0.0, adicionais=[{"nome": "camera", "massa_kg": 0.1, "x": 1.0, "y": 0.0, "z": 0.0}])
    assert b["modos"][0]["f_hz"] < a["modos"][0]["f_hz"]
    assert any("camera" in n for n in b["notas"])

def test_motor_longe_da_trelica_nao_entra_nos_modos_da_cauda():
    a = VB.analisa(balanco(), massa_empenagem_h_kg=0.1, x_apoio=0.0)
    b = VB.analisa(balanco(), massa_empenagem_h_kg=0.1, x_apoio=0.0, massa_motor_kg=0.3, pos_motor=[-0.5, 0.0, 0.0])
    assert b["modos"][0]["f_hz"] == pytest.approx(a["modos"][0]["f_hz"], rel=1e-9)
    assert any("motor" in n and "apoio" in n for n in b["notas"])

def test_suporte_do_motor_como_balanco_com_massa_na_ponta():
    esq = balanco()
    s = VB.suporte_do_motor(esq, {"comprimento_m": 0.1, "de_m": 0.02, "di_m": 0.018}, 0.25, None, 1.0)
    p = propriedades("tubo_carbono", esq, None, qualidade_carbono=1.0)
    I = np.pi / 64 * (0.02 ** 4 - 0.018 ** 4)
    assert s["f_hz"] == pytest.approx(np.sqrt(3 * p["E"] * I / 0.1 ** 3 / (0.25 + 33 / 140 * s["massa_tubo_kg"])) / (2 * np.pi), rel=1e-9)
    mais_longo = VB.suporte_do_motor(esq, {"comprimento_m": 0.2, "de_m": 0.02, "di_m": 0.018}, 0.25, None, 1.0)
    assert mais_longo["f_hz"] < s["f_hz"] / 2
    with pytest.raises(ValueError):
        VB.suporte_do_motor(esq, {"comprimento_m": 0.1, "de_m": 0.02, "di_m": 0.03}, 0.25)

def test_ressonancia_dentro_perto_e_ok():
    modos = [{"nome": "a", "f_hz": 100.0}, {"nome": "b", "f_hz": 75.0}, {"nome": "c", "f_hz": 20.0}]
    rs = VB.ressonancias(5000, 8000, 2, modos)
    d = {(x["modo"], x["ordem"]): x for x in rs}
    assert d[("a", "1P")]["situacao"] == "dentro" and d[("a", "1P")]["rpm_ressonancia"] == pytest.approx(6000)
    assert d[("b", "1P")]["situacao"] == "perto" and d[("b", "1P")]["separacao"] == pytest.approx(5000 / 60 / 75 - 1)
    assert d[("c", "1P")]["situacao"] == "ok" and d[("c", "2P")]["situacao"] == "ok"
    assert rs[0]["situacao"] == "dentro"
    assert [x["situacao"] for x in rs] == sorted((x["situacao"] for x in rs), key=["dentro", "perto", "ok"].index)

def test_ressonancia_indica_a_velocidade_de_voo():
    rpm_v = {"V": [0, 10, 20, 30], "rpm": [5000, 6000, 7000, 8000]}
    rs = VB.ressonancias(5000, 8000, 2, [{"nome": "a", "f_hz": 100.0}], rpm_v=rpm_v)
    assert next(x for x in rs if x["ordem"] == "1P")["V_ms"] == pytest.approx(10.0)

def test_campbell_tem_as_ordens_e_os_modos():
    c = VB.campbell(3000, 9000, 3, [{"nome": "a", "f_hz": 80.0}], ordens_extra=[4])
    assert [o["ordem"] for o in c["ordens"]] == [1.0, 3.0, 4.0]
    assert c["ordens"][1]["f_hz"][-1] == pytest.approx(3 * 9000 / 60)
    assert len(c["rpm"]) == len(c["ordens"][0]["f_hz"])

def test_faixa_de_rpm_invalida():
    with pytest.raises(ValueError):
        VB.analisa(balanco(), x_apoio=0.0, rpm_min=9000, rpm_max=3000)
    with pytest.raises(ValueError):
        VB.analisa(balanco(), x_apoio=0.0, n_pas=0)

def test_fronteira_devolve_modos_campbell_e_ressonancias():
    q = AN.vibracao({"esquema": balanco(), "massa_empenagem_h_kg": 0.15, "x_apoio": 0.0, "rpm_min": 3000, "rpm_max": 9000, "n_pas": 2,
                     "incluir_asas": False, "suporte_motor": {"comprimento_m": 0.1, "de_m": 0.02, "di_m": 0.018}, "massa_motor_kg": 0.25})
    assert "erro" not in q
    assert q["modos"][0]["f_hz"] > 0 and q["suporte_motor"]["f_hz"] > 0
    assert any(m["nome"].startswith("suporte do motor") for m in q["campbell"]["modos"])
    assert q["ressonancias"] and q["faixa_rpm"] == [3000.0, 9000.0]

def test_fronteira_recusa_entrada_ruim():
    assert "erro" in AN.vibracao({"esquema": balanco(), "x_apoio": 0.0, "incluir_asas": False, "pos_motor": [1, 2]})
    assert "erro" in AN.vibracao({"esquema": balanco(), "x_apoio": 0.0, "incluir_asas": False, "rpm_min": 9000, "rpm_max": 3000})
    assert "erro" in AN.vibracao({"esquema": {"versao": 1, "nome": "v", "elementos": []}, "incluir_asas": False})

def test_asa_sem_longarina_fica_fora_dos_modos_externos_sem_derrubar_a_analise():
    esq = balanco()
    esq["elementos"][1]["estrutura"] = {"nervuras": {"y": [0.1], "espessura": 0.003}}
    q = AN.vibracao({"esquema": esq, "massa_empenagem_h_kg": 0.15, "x_apoio": 0.0})
    assert "erro" not in q and q["modos"]
    assert any("empenagem_h" in a and "fora dos modos externos" in a for a in q["avisos"])
