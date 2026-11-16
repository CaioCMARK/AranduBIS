import math

import numpy as np
import pytest

from aranduBIS.nucleo.estrutura import asa as AS
from aranduBIS.nucleo.estrutura import longarinas as LG
from aranduBIS.nucleo.estrutura import torcao as TO
from aranduBIS.nucleo.estrutura.materiais import propriedades

C = 0.36
X = np.linspace(0, 1, 201)
ZS, ZI = 0.06 * np.sin(np.pi * X), -0.06 * np.sin(np.pi * X)

def mats():
    return {k: propriedades(k) for k in ("balsa", "tubo_carbono", "spruce")}

def sec(lg, **kw):
    cfg = {"longarinas": [lg], **kw}
    return AS.secao(cfg, X, ZS, ZI, C, 0.1, mats())

def test_tubo_longarina_tem_ei_do_tubo_e_cisalhamento_2V_sobre_A():
    de, di = 0.012, 0.010
    s = sec({"tipo": "tubo", "xc": 0.3, "de": de, "di": di})
    E = mats()["tubo_carbono"]["E"]
    I = math.pi / 64 * (de ** 4 - di ** 4)
    assert s["EI"] == pytest.approx(E * I, rel=1e-9)
    assert s["zna"] == pytest.approx(0.0, abs=1e-12)
    A = math.pi / 4 * (de ** 2 - di ** 2)
    t, mg = AS._tensoes(s, 10.0, 7.0, mats())
    assert t["tubo_comp"] == pytest.approx(10.0 * 0.5 * de / I, rel=1e-9)
    assert t["tubo_cis"] == pytest.approx(2 * 7.0 / A, rel=1e-9)
    assert "alma_cis" not in t

def test_viga_caixao_bate_com_a_conta_a_mao():
    lg = {"tipo": "caixao", "xc": 0.3, "largura_caixa": 0.02, "espessura_alma": 0.0016, "material_alma": "balsa",
          "espessura_mesa": 0.003, "material_mesa": "spruce"}
    s = sec(lg)
    m = mats()
    H = 2 * 0.06 * C * 0.5 * (np.sin(np.pi * (0.3 - 0.01 / C)) + np.sin(np.pi * (0.3 + 0.01 / C)))
    tm, b, tw = 0.003, 0.02, 0.0016
    d = 0.5 * H - 0.5 * tm
    EI_mesas = 2 * m["spruce"]["E"] * (b * tm * d ** 2 + b * tm ** 3 / 12)
    hw = [2 * 0.06 * C * np.sin(np.pi * xx / C) - 2 * tm for xx in (0.3 * C - 0.01 + 0.0008, 0.3 * C + 0.01 - 0.0008)]
    EI_almas = sum(m["balsa"]["E"] * tw * h ** 3 / 12 for h in hw)
    assert s["EI"] == pytest.approx(EI_mesas + EI_almas, rel=1e-3)
    t, _ = AS._tensoes(s, 0.0, 10.0, m)
    assert t["alma_cis"] == pytest.approx(10.0 / (sum(hw) * tw), rel=1e-4)
    assert "mesa_comp" in AS._tensoes(s, 5.0, 0.0, m)[0]

def test_celula_da_viga_caixao_segue_bredt():
    cel = {"b": 0.0184, "h": 0.018, "tw": 0.0016, "tm": 0.003, "mat_alma": "balsa", "mat_mesa": "spruce"}
    m = mats()
    A = 0.0184 * 0.018
    esperado = 4 * A ** 2 / (2 * 0.018 / (m["balsa"]["G"] * 0.0016) + 2 * 0.0184 / (m["spruce"]["G"] * 0.003))
    assert LG.gj_celula(cel, m) == pytest.approx(esperado, rel=1e-12)

def test_viga_i_nao_fecha_celula_e_caixao_fecha():
    base = {"tipo": "caixao", "xc": 0.3, "largura_caixa": 0.02}
    cx = TO.estacao({"longarinas": [base]}, X, ZS, ZI, C, 0.1, mats())
    vi = TO.estacao({"longarinas": [{**base, "n_almas": 1}]}, X, ZS, ZI, C, 0.1, mats())
    assert cx["fechada"] and not vi["fechada"]
    assert cx["GJ"] > 10 * vi["GJ"]
    assert cx["ea_c"] == pytest.approx(0.3, abs=1e-9)

def test_tubo_longarina_resiste_a_torcao_como_tubo():
    de, di = 0.012, 0.010
    e = TO.estacao({"longarinas": [{"tipo": "tubo", "xc": 0.3, "de": de, "di": di}]}, X, ZS, ZI, C, 0.1, mats())
    assert e["fechada"]
    assert e["GJ"] == pytest.approx(mats()["tubo_carbono"]["G"] * math.pi / 32 * (de ** 4 - di ** 4), rel=1e-9)

def test_alma_antiga_continua_igual():
    lg = {"x": 0.07, "largura": 0.00238}
    assert LG.tipo(lg) == "alma"
    s = sec(lg)
    h = 2 * 0.06 * C * np.sin(np.pi * 0.07 / C)
    assert s["h"] == pytest.approx(h, rel=1e-3)
    assert s["EI"] == pytest.approx(mats()["balsa"]["E"] * 0.00238 * s["h"] ** 3 / 12, rel=1e-9)

def test_tipo_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="tipo"):
        LG.tipo({"tipo": "trelica"})

def test_recortes_da_nervura():
    cfg = {"longarinas": [{"tipo": "tubo", "xc": 0.3, "de": 0.012, "di": 0.01}],
           "tubos": [{"xc": 0.6, "lado": "extradorso", "de": 0.004, "di": 0.003}]}
    r = LG.recortes(cfg, X, ZS, ZI, C, 0.1)
    furos = sorted((round(f["x"] / C, 3), f["d"]) for f in r if f["forma"] == "furo")
    assert furos == [(0.3, 0.012), (0.6, 0.004)]

def _asa(lg):
    return {"versao": 1, "nome": "t", "elementos": [{"nome": "asa", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 30,
            "secoes": [{"y": 0.0, "xle": 0.0, "z": 0.0, "corda": 0.3, "ainc": 0.0}, {"y": 1.0, "xle": 0.0, "z": 0.0, "corda": 0.3, "ainc": 0.0}],
            "simetrica": True, "estrutura": {"longarinas": [lg]}}]}

def test_massa_do_tubo_longarina_e_area_vezes_comprimento():
    from aranduBIS.nucleo.modelador import aeronave_geometria as AG
    from aranduBIS.nucleo.modelador import aeronave_estrutura as ES
    esq = _asa({"tipo": "tubo", "xc": 0.25, "de": 0.012, "di": 0.010})
    mc = AG.massa_e_cg(AG.constroi(esq))
    esperado = math.pi / 4 * (0.012 ** 2 - 0.010 ** 2) * 1.0 * ES.densidade("tubo_carbono")
    assert mc["massa_kg"] == pytest.approx(esperado, rel=0.03)

def test_massa_da_viga_caixao():
    from aranduBIS.nucleo.modelador import aeronave_geometria as AG
    from aranduBIS.nucleo.modelador import aeronave_estrutura as ES
    lg = {"tipo": "caixao", "xc": 0.25, "largura_caixa": 0.02, "espessura_alma": 0.0016, "espessura_mesa": 0.003}
    esq = _asa(lg)
    mc = AG.massa_e_cg(AG.constroi(esq))
    t = 0.12 * 0.3
    mesas = 2 * 0.02 * 0.003 * 1.0 * ES.densidade("spruce")
    almas = 2 * 0.0016 * (t - 0.006) * 1.0 * ES.densidade("balsa")
    assert mc["massa_kg"] == pytest.approx(mesas + almas, rel=0.08)
