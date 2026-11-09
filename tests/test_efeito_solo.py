import json
import warnings
from pathlib import Path

import pytest

from aranduBIS.nucleo.aero import limites as L
from aranduBIS.nucleo.aero.aeronave_vlm import superficies
from aranduBIS.nucleo.aero.vlm import VLM

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def conv():
    d = json.loads((RAIZ / "cases/geometria/generico/generico.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/generico")
    return d

def test_solo_muito_longe_volta_ao_voo_livre_inclusive_o_momento(conv):
    livre = VLM(superficies(conv), x_ref=0.5).resolver([2.0], V=12, rho=1.1)[0]
    longe = VLM(superficies(conv), x_ref=0.5, altura_solo=1000.0).resolver([2.0], V=12, rho=1.1)[0]
    assert longe.CL == pytest.approx(livre.CL, rel=0.02)
    assert longe.CDi == pytest.approx(livre.CDi, rel=0.05)
    assert longe.Cm == pytest.approx(livre.Cm, abs=0.02)

def test_chao_perto_aumenta_cl_e_reduz_o_arrasto_induzido(conv):
    r = {h: VLM(superficies(conv), x_ref=0.5, altura_solo=h).resolver([3.0], V=12, rho=1.1)[0] for h in (0.5, 1.0, 5.0)}
    assert r[0.5].CL > r[1.0].CL > r[5.0].CL
    assert r[0.5].CDi < r[1.0].CDi < r[5.0].CDi

def test_reducao_do_arrasto_induzido_na_ordem_da_formula_de_mccormick():
    from aranduBIS.nucleo.aero.planform import Estacao, Planform
    from aranduBIS.nucleo.aero.vlm import Superficie
    b = 2.0
    pl = Planform(estacoes=(Estacao(y=0.0, corda=0.25), Estacao(y=b / 2, corda=0.25)), nome="ret")

    def cdi(h):
        s = Superficie(pl, incidencia=4.0, n_span=24, n_chord=4)
        return VLM([s], altura_solo=h).resolver([0.0], V=12, rho=1.1)[0].CDi

    razao = cdi(0.2 * b) / cdi(None)
    mc = (16 * 0.2) ** 2 / (1 + (16 * 0.2) ** 2)
    assert razao == pytest.approx(mc, abs=0.10)

def test_resolver_com_solo_aceita_delta_alpha_por_faixa(conv):
    import numpy as np
    v = VLM(superficies(conv), x_ref=0.5, altura_solo=0.3)
    ns = v._fatias["Asa"]["ns"]
    a = v.resolver([2.0], V=12, rho=1.1)[0]
    b = v.resolver([2.0], V=12, rho=1.1, delta_alpha={"Asa": np.full(ns, 0.02)})[0]
    assert b.CL > a.CL

def test_altura_do_solo_pelas_rodas():
    esq = {"elementos": [{"tipo": "roda", "posicao": [0.2, 0, -0.10], "diametro": 0.10},
                         {"tipo": "roda", "posicao": [-0.3, 0, -0.10], "diametro": 0.10}]}
    assert L.altura_do_solo(esq, 0.0, 0.0) == pytest.approx(0.15)
    assert L.altura_do_solo({"elementos": []}, 0.0, 0.0) is None

def test_corrida_com_solo_tem_menos_arrasto_que_em_voo_livre(conv):
    r = L.cl_max(conv, 0.5, altura=0.25)
    assert r["solo"]["usado"] and r["solo"]["origem"] == "voce"
    assert r["corrida"]["CD"] < r["solo"]["livre"]["CD"]
    assert not L.cl_max(conv, 0.5, com_solo=False)["solo"]["usado"]
