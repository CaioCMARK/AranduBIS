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

def test_decolagem_com_solo_e_arrasto_que_cresce_com_cl():
    from aranduBIS.nucleo import decolagem as DC
    base = dict(S=1.5, CL_max=1.8, CL_corrida=0.6, CD_corrida=0.10, tracao_v=(0.0, 30.0), tracao_n=(40.0, 10.0))
    c = DC.Condicoes()
    sem = DC.simular(12.0, DC.Aeronave(**base), c, forcas=False)
    com = DC.simular(12.0, DC.Aeronave(**base, solo_h=(0.15, 0.6, 5.0), solo_K=(0.03, 0.05, 0.06), h0=0.15), c)
    assert sem.decolou and com.decolou
    assert com.altura_obstaculo != pytest.approx(sem.altura_obstaculo, abs=1e-6)
    assert com.forcas["D"][0] == pytest.approx(0.0)
    i = next(k for k, v in enumerate(com.v) if v > 5.0)
    q = 0.5 * c.rho * com.v[i] ** 2 * 1.5
    assert com.forcas["D"][i] == pytest.approx(q * 0.10, rel=1e-6)
    with pytest.raises(ValueError):
        DC.simular(12.0, DC.Aeronave(**base, solo_h=(0.15, 0.6), solo_K=(0.5, 0.5), h0=0.15), c)

def test_subir_perde_o_solo_e_aumenta_o_arrasto_induzido():
    from aranduBIS.nucleo import decolagem as DC
    base = dict(S=1.5, CL_max=1.8, CL_corrida=0.6, CD_corrida=0.10, tracao_v=(0.0, 30.0), tracao_n=(40.0, 10.0))
    forte = DC.Aeronave(**base, solo_h=(0.15, 5.0), solo_K=(0.01, 0.10), h0=0.15)
    fraco = DC.Aeronave(**base, solo_h=(0.15, 5.0), solo_K=(0.01, 0.01), h0=0.15)
    c = DC.Condicoes()
    assert DC.simular(12.0, forte, c, forcas=False).altura_obstaculo < DC.simular(12.0, fraco, c, forcas=False).altura_obstaculo
