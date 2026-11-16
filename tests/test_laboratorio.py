import warnings

import numpy as np
import pytest

from aranduBIS.nucleo.aero import laboratorio as L
from aranduBIS.nucleo.aero.comparativo import avalia

KW = dict(V=15.0, rho=1.1, peso_N=66.8, laterais=False, n_span=24, n_chord=8)


@pytest.fixture(autouse=True)
def _sem_aviso_de_malha():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*pede n_span.*")
        yield


def _k_trefftz(h_b, n=4000):
    y = (np.arange(n) + 0.5) / n - 0.5
    dy = 1.0 / n
    G = np.sqrt(np.clip(1 - (2 * y) ** 2, 0, None))
    dG = np.gradient(G, dy)

    def w(zoff):
        Y = y[:, None] - y[None, :]
        return (dG[None, :] * Y / (Y ** 2 + zoff ** 2 + 1e-12)).sum(1) * dy / (2 * np.pi)

    D = 0.5 * (G * (w(0.0) + w(h_b))).sum() * dy * 2
    D1 = 0.5 * (G * w(0.0)).sum() * dy
    return D / (4 * D1)


def _mono_reto():
    return L._modelo("m", [L.asa_espelhada("a", [(0, 0, 0, 0.30, 0), (L.B / 2, 0, 0, 0.30, 0)], perfil="NACA 0012")])


def _biplano_reto(h):
    p = [(0, 0, 0, 0.15, 0), (L.B / 2, 0, 0, 0.15, 0)]
    return L._modelo("b", [L.asa_espelhada("a1", p, perfil="NACA 0012"), L.asa_espelhada("a2", p, pos=(0, 0, h), perfil="NACA 0012")])


def test_biplano_do_vlm_confere_com_prandtl_munk_no_plano_de_trefftz():
    dm = avalia(_mono_reto(), comando=None, **KW)["Di_N"]
    for h in (0.24, 0.36):
        razao = avalia(_biplano_reto(h), comando=None, **KW)["Di_N"] / dm
        assert razao == pytest.approx(_k_trefftz(h / L.B), rel=0.03)


def test_regua_de_comparacao_poe_o_cg_na_margem_e_trima():
    a = avalia(L.asa_com_cauda_convencional(), **KW)
    assert a["SM"] == pytest.approx(0.10, abs=0.01)
    assert abs(a["trim"]["Cm"]) < 1e-5 and a["trim"]["convergiu"] and not a["trim"]["saturou"]
    assert a["L_N"] == pytest.approx(66.8, rel=1e-4)
    assert a["trim"]["comando"] == "empenagem_h"


def test_derivas_de_ponta_para_cima_reduzem_o_arrasto_induzido_como_nas_winglets():
    sem = avalia(L.asa_varrida(4.0), comando=None, **KW)["Di_N"]
    cima = avalia(L.vertical_nas_pontas(0.30, 4.0), comando=None, **dict(KW, laterais=True))
    baixo = avalia(L.vertical_nas_pontas_para_baixo(0.30, 4.0), comando=None, **KW)
    assert 0.10 < 1 - cima["Di_N"] / sem < 0.25
    assert cima["Di_N"] < baixo["Di_N"] < sem
    assert cima["Cn_beta"] > 0.02 and abs(L._fins(L.vertical_nas_pontas(0.3))[0]["rolagem"]) == 90.0


def test_vertical_central_da_asa_voadora_estabiliza_mas_nao_reduz_induzido():
    sem = avalia(L.asa_varrida(4.0), comando=None, **KW)["Di_N"]
    c = avalia(L.vertical_central(0.40, 4.0), comando=None, **dict(KW, laterais=True))
    assert c["Di_N"] == pytest.approx(sem, rel=0.01)
    assert c["Cn_beta"] > 0.0


def test_burgess_dunne_perde_menos_induzido_que_o_monoplano_de_mesma_area_e_envergadura():
    mono = avalia(L.monoplano_equivalente(4.0), comando=None, **KW)["Di_N"]
    bd = avalia(L.burgess_dunne(4.0, com_derivas=False), comando=None, **KW)["Di_N"]
    assert 1 - bd / mono == pytest.approx(1 - _k_trefftz(0.36 / L.B), abs=0.05)


def test_esteira_do_canard_rente_a_asa_da_induzido_impossivel():
    def e_b(z):
        m = L.bwb(0.0, com_canard=True)
        next(x for x in m["elementos"] if x["nome"] == "canard")["posicao"][2] = z
        return avalia(m, comando="canard", **KW)["e_b"]
    assert e_b(L.Z_CANARD) < 1.35
    assert e_b(0.03) > 1.5


def test_bwb_rotaciona_no_efeito_solo_e_o_canard_ajuda():
    r = L.estudo_bwb()
    assert r["bwb"]["pode_rotacionar"] and r["bwb_canard"]["pode_rotacionar"]
    assert r["bwb_canard"]["CL_max_equilibrado"] > r["bwb"]["CL_max_equilibrado"]
    assert r["bwb"]["no_limite"]["alpha"] <= 14.0 + 1e-6


def test_asa_em_caixa_perde_menos_induzido_que_monoplano_com_cauda_e_tandem_nao():
    r = L.estudo_caixa_tandem()
    assert r["caixa"]["e_b"] > r["monoplano_com_cauda"]["e_b"] + 0.15
    assert r["tandem"]["Di_N"] > r["caixa"]["Di_N"]
    for k in r:
        assert abs(r[k]["Cm"]) < 1e-5


def test_duto_na_cauda_estabiliza_a_guinada_mais_que_a_cauda_convencional():
    r = L.estudo_duto()
    assert r["duto_na_cauda"]["Cn_beta"] > 2 * r["cauda_convencional"]["Cn_beta"]
    assert r["duto_na_cauda"]["Cm_alpha"] > r["cauda_convencional"]["Cm_alpha"]


def test_empuxo_estatico_do_duto_pela_teoria_do_disco():
    T = L.empuxo_duto(P_W=400.0, D_m=0.30, sigma=1.0, rho=1.1, FM=1.0)
    assert T == pytest.approx((2 * 1.1 * np.pi * 0.15 ** 2 * 400.0 ** 2) ** (1 / 3), rel=1e-12)
    assert L.empuxo_duto(sigma=1.2) == pytest.approx(L.empuxo_duto(sigma=1.0) * 1.2 ** (1 / 3), rel=1e-12)


def test_massa_de_ponta_atras_do_eixo_cria_flutter_e_na_frente_nao():
    esq = L._trima_washout(L.asa_varrida)[1]
    r = L.flutter_massa_de_ponta(esq, "asa", Vd=25.0, massas_g=(0, 25), x_c=(0.3, 0.8))
    VF = {(c["massa_g"], c["x_c"]): c["VF"] for c in r["casos"]}
    assert VF[(0, 0.3)] is None and VF[(25, 0.3)] is None and VF[(0, 0.8)] is None
    assert VF[(25, 0.8)] is not None and VF[(25, 0.8)] > r["V_requerida"]
