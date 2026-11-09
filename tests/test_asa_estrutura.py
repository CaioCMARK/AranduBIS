import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import asa as AS
from aranduBIS.nucleo.estrutura.materiais import propriedades

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def cargas(biplano):
    return AN.cargas({"esquema": biplano, "Vc": 13.0, "Vd": 15.9, "CL_max": 1.97})

def mats():
    return {k: propriedades(k) for k in ("balsa", "tubo_carbono")}

def secao_teste(**kw):
    x = np.linspace(0, 1, 41)
    zs, zi = 0.06 * np.sin(np.pi * x), -0.0 * x
    cfg = {"longarinas": [{"x": 0.07, "largura": 0.00238}],
           "tubos": [{"x": 0.07, "lado": "extradorso", "de": 0.004, "di": 0.003}, {"x": 0.07, "lado": "intradorso", "de": 0.004, "di": 0.003}]}
    cfg.update(kw)
    return AS.secao(cfg, x, zs, zi, 0.36, 0.1, mats()), cfg

def test_flexao_de_viga_composta_bate_com_a_conta_a_mao():
    s, _ = secao_teste()
    m = mats()
    h = s["h"]
    A = 0.25 * np.pi * (0.004 ** 2 - 0.003 ** 2)
    d = h - 0.004
    EI_tubos = 2 * m["tubo_carbono"]["E"] * A * (d / 2) ** 2
    EI_alma = m["balsa"]["E"] * 0.00238 * h ** 3 / 12
    assert s["EI"] == pytest.approx(EI_tubos + EI_alma, rel=0.02)
    assert s["zna"] == pytest.approx(0.5 * h, rel=1e-6)

def test_tensao_no_tubo_e_momento_sobre_modulo(cargas, biplano):
    s, _ = secao_teste()
    t = AS._tensoes(s, 10.0, 0.0, mats())
    E = mats()["tubo_carbono"]["E"]
    assert t["tubo_comp"] == pytest.approx(10.0 * E * (s["h"] - 0.002 - s["zna"]) / s["EI"], rel=1e-6)
    assert t["tubo_comp"] == pytest.approx(t["tubo_tr"], rel=0.02)
    assert AS._tensoes(s, -10.0, 0.0, mats())["tubo_comp"] == pytest.approx(t["tubo_tr"], rel=0.02)

def test_chapeado_mais_curto_deixa_a_secao_mais_flexivel():
    cheio, _ = secao_teste(chapeado={"ate_xc": 0.22, "espessura": 0.001})
    curto, _ = secao_teste(chapeado={"ate_xc": 0.22, "espessura": 0.001, "ate_xc_y": [[0.0, 0.22], [0.1, 0.05]]})
    sem, _ = secao_teste()
    assert sem["EI"] < curto["EI"] < cheio["EI"]
    assert curto["xe"] == pytest.approx(0.05)

def test_qualidade_do_material_reduz_o_admissivel_e_a_margem(biplano, cargas):
    a = AS.verifica(biplano, "asa_inferior", cargas["casos"])
    b = AS.verifica(biplano, "asa_inferior", cargas["casos"], qualidade_balsa=0.5)
    assert b["admissiveis_MPa"]["alma_cis"] == pytest.approx(0.5 * a["admissiveis_MPa"]["alma_cis"])
    assert b["critico"]["margem"] < a["critico"]["margem"]
    assert a["admissiveis_MPa"]["tubo_comp"] == pytest.approx(1200.0)

def test_biplano_tem_margens_positivas_e_flecha_dentro_do_limite(biplano, cargas):
    r = AS.verifica(biplano, "asa_inferior", cargas["casos"])
    assert r["critico"]["margem"] > 0 and r["flecha_max_pct"] < 6.0
    assert r["estacoes"]["EI"][0] > r["estacoes"]["EI"][-1] > 0
    assert len(r["casos"]) == len(cargas["casos"])

def test_mais_carga_menos_margem(biplano, cargas):
    base = AS.verifica(biplano, "asa_inferior", cargas["casos"], fator_seguranca=1.2)
    mais = AS.verifica(biplano, "asa_inferior", cargas["casos"], fator_seguranca=2.4)
    assert mais["critico"]["margem"] < base["critico"]["margem"]

def test_modelo_sem_estrutura_diz_o_que_falta(biplano, cargas):
    d = copy.deepcopy(biplano)
    next(e for e in d["elementos"] if e["nome"] == "asa_inferior")["estrutura"] = {}
    with pytest.raises(ValueError, match="estrutura"):
        AS.verifica(d, "asa_inferior", cargas["casos"])
    with pytest.raises(ValueError, match="material"):
        propriedades("unobtainium")

def test_fronteira_asa(biplano):
    r = AN.asa({"esquema": biplano, "Vc": 13.0, "Vd": 15.9, "CL_max": 1.97})
    assert "erro" not in r and {a["nome"] for a in r["asas"]} == {"asa_inferior", "asa_superior"}
    assert r["critico"]["asa"] in ("asa_inferior", "asa_superior")
    assert "erro" in AN.asa({"esquema": {"elementos": []}})
