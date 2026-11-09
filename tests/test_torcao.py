import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import torcao as TO

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

def com_chapeado(esq, **kw):
    e = copy.deepcopy(esq)
    for el in e["elementos"]:
        if el.get("estrutura"):
            el["estrutura"]["chapeado"].update(kw)
    return e

def test_caixa_fechada_tem_gj_muito_maior_que_a_aberta(biplano):
    r = TO.analisa(biplano, "asa_inferior")
    GJ, fech = np.array(r["GJ"]), np.array(r["fechada"])
    assert fech[0] and not fech[-1]
    assert GJ[fech].min() > 50 * GJ[~fech].max()
    assert any("fechar a caixa" in a for a in r["avisos"])

def test_gj_proporcional_a_espessura_do_chapeado(biplano):
    a = TO.analisa(com_chapeado(biplano, ate_xc=0.30, espessura=0.001), "asa_inferior")["GJ"][0]
    b = TO.analisa(com_chapeado(biplano, ate_xc=0.30, espessura=0.002), "asa_inferior")["GJ"][0]
    assert b / a == pytest.approx(2.0, rel=0.1)

def test_linha_elastica_entre_o_bordo_de_ataque_e_a_longarina(biplano):
    r = TO.analisa(com_chapeado(biplano, ate_xc=0.30), "asa_inferior")
    for ea, xs in zip(r["ea_c"][:5], [0.071 / c for c in r["c"][:5]]):
        assert 0.0 < ea <= xs + 1e-6

def test_reversao_escala_com_raiz_do_gj(biplano):
    e = com_chapeado(biplano, ate_xc=0.30)
    a = TO.analisa(e, "asa_inferior")
    b = TO.analisa(e, "asa_inferior", calib_GJ=2.0)
    assert a["VR"] is not None and b["VR"] == pytest.approx(a["VR"] * np.sqrt(2.0), rel=0.01)
    assert a["GJ_minimo"] == pytest.approx((a["V_requerida"] / a["VR"]) ** 2, rel=1e-6)

def test_sem_divergencia_com_a_linha_elastica_a_frente_do_ca(biplano):
    r = TO.analisa(com_chapeado(biplano, ate_xc=0.30), "asa_inferior")
    assert r["VD"] is None and r["folga_ea_ca_c"]["max"] < 0

def test_divergencia_aparece_com_a_linha_elastica_atras(biplano):
    r = TO.analisa(com_chapeado(biplano, ate_xc=0.30), "asa_inferior", ea_desloc_c=0.25)
    assert r["VD"] is not None and r["VD"] > 0
    r2 = TO.analisa(com_chapeado(biplano, ate_xc=0.30), "asa_inferior", ea_desloc_c=0.25, calib_GJ=4.0)
    assert r2["VD"] == pytest.approx(2 * r["VD"], rel=0.02)

def test_asa_rigida_nao_reverte_e_efetividade_vai_a_um(biplano):
    r = TO.analisa(com_chapeado(biplano, ate_xc=0.30), "asa_inferior", calib_GJ=1e4)
    assert r["VR"] is None and min(r["curva"]["razao"]) > 0.99

def test_aberta_em_todo_o_vao_reverte_cedo(biplano):
    a = TO.analisa(biplano, "asa_inferior")
    b = TO.analisa(com_chapeado(biplano, ate_xc=0.30), "asa_inferior")
    assert a["VR"] < b["VR"] and a["margem_VR"] < 0

def test_fronteira_torcao(biplano):
    r = AN.torcao({"esquema": biplano, "Vd": 15.9})
    assert "erro" not in r and {a["nome"] for a in r["asas"]} == {"asa_inferior", "asa_superior"}
    assert r["V_requerida"] == pytest.approx(1.2 * 15.9)
    assert AN.torcao({"esquema": biplano, "Vd": -1})["erro"]
    sem = copy.deepcopy(biplano)
    for el in sem["elementos"]:
        el.pop("estrutura", None)
    assert "Nenhuma asa" in AN.torcao({"esquema": sem})["erro"]
