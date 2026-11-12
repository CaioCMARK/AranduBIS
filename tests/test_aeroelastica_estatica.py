import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.aero.equilibrio import monta
from aranduBIS.nucleo.estrutura import aeroelastica_estatica as AE
from aranduBIS.nucleo.modelador import aeronave_geometria as AG

RAIZ = Path(__file__).resolve().parents[1]

def _carrega():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def aberta():
    return _carrega()

@pytest.fixture(scope="module")
def fechada(aberta):
    d = copy.deepcopy(aberta)
    for el in d["elementos"]:
        if el.get("estrutura") and el["estrutura"].get("chapeado"):
            el["estrutura"]["chapeado"].pop("ate_xc_y", None)
            el["estrutura"]["chapeado"]["ate_xc"] = 0.45
    return d

@pytest.fixture(scope="module")
def cg(aberta):
    return AG.massa_e_cg(AG.constroi(aberta))["cg_m"]

def _roda(esq, cg, **kw):
    args = dict(V=13.0, n=1.0, massa_kg=14.0, x_cg=cg[0], z_cg=cg[2], rho=1.1)
    args.update(kw)
    return AE.estatica(esq, **args)

@pytest.fixture(scope="module")
def base(fechada, cg):
    return _roda(fechada, cg)

def test_torcao_zero_nao_muda_o_vlm(aberta, cg):
    e = AE.esquema_deformado(aberta, "asa_inferior", [0.0, 1.2], [0.0, 0.0])
    a = monta(aberta, cg[0], cg[2]).resolver(3.0, V=13.0, rho=1.1)[0]
    b = monta(e, cg[0], cg[2]).resolver(3.0, V=13.0, rho=1.1)[0]
    assert b.CL == pytest.approx(a.CL, rel=1e-3)

def test_torcao_de_incidencia_positiva_aumenta_a_sustentacao(aberta, cg):
    a = monta(aberta, cg[0], cg[2]).resolver(3.0, V=13.0, rho=1.1)[0].CL
    e = AE.esquema_deformado(aberta, "asa_inferior", [0.0, 1.2], [0.0, 3.0])
    assert monta(e, cg[0], cg[2]).resolver(3.0, V=13.0, rho=1.1)[0].CL > a

def test_converge_e_o_trim_fecha_o_cl_alvo(base):
    assert base["convergiu"] and base["motivo"] is None
    m = [h["mudanca_graus"] for h in base["iteracoes"]]
    assert m[-1] < 0.01 and all(b < a for a, b in zip(m, m[1:]))
    assert base["flexivel"]["CL"] == pytest.approx(base["CL_alvo"], rel=1e-4)

def test_washout_pede_mais_alpha_e_alivia_a_raiz(base):
    assert base["variacao_alpha_graus"] > 0
    for a in base["asas"]:
        assert a["torcao_ponta_graus"] < 0
        assert a["razao_fletor"] < 1.0

def test_rigidez_enorme_volta_a_asa_rigida(fechada, cg):
    r = _roda(fechada, cg, calib_GJ=1e4)
    assert r["convergiu"]
    assert abs(r["variacao_alpha_graus"]) < 0.02
    assert all(abs(a["torcao_ponta_graus"]) < 0.02 and a["razao_fletor"] == pytest.approx(1.0, abs=2e-3) for a in r["asas"])

def test_linha_elastica_mais_atras_empurra_para_washin(fechada, cg, base):
    r = _roda(fechada, cg, ea_desloc_c=0.1)
    for a, b in zip(r["asas"], base["asas"]):
        assert a["torcao_ponta_graus"] > b["torcao_ponta_graus"]

def test_ponta_aberta_diverge_e_diz_isso(aberta, cg):
    r = _roda(aberta, cg)
    assert not r["convergiu"] and "diverg" in r["motivo"]
    assert r["flexivel"] is None

def test_fronteira_devolve_o_resultado_e_erro_claro(fechada):
    r = AN.aeroelastica({"esquema": fechada, "V": 13.0, "n": 1.0, "massa_kg": 14.0})
    assert "erro" not in r and r["convergiu"] and {a["nome"] for a in r["asas"]} == {"asa_inferior", "asa_superior"}
    assert "erro" in AN.aeroelastica({"esquema": {"elementos": []}})
