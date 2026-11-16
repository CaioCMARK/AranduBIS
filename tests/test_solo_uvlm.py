import math
import warnings

import numpy as np
import pytest

from aranduBIS.nucleo.aero.planform import Estacao, Planform
from aranduBIS.nucleo.aero.uvlm import UVLM, Solo, UVLMParticulas
from aranduBIS.nucleo.aero.vlm import VLM, Superficie
from aranduBIS.nucleo.aero.vpm import Particulas

C, V, ALFA, XREF = 0.25, 12.0, 5.0, 0.0625


def _asa(b=1.5, c=C, ns=16, nc=4):
    pl = Planform(estacoes=(Estacao(y=0.0, corda=c), Estacao(y=b / 2, corda=c)), nome="ret")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Superficie(pl, n_span=ns, n_chord=nc)


@pytest.fixture(autouse=True)
def _sem_avisos():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


def _pontos_no_chao(solo, a_graus, xs=np.linspace(-0.5, 2.0, 11), ys=np.linspace(-1.2, 1.2, 9)):
    p0 = np.array(solo.plano()["p0"])
    e1 = np.array([math.cos(math.radians(a_graus)), 0.0, math.sin(math.radians(a_graus))])
    return np.array([p0 + x * e1 + y * np.array([0.0, 1.0, 0.0]) for x in xs for y in ys])


@pytest.mark.parametrize("h", [0.1, 0.25])
@pytest.mark.parametrize("livre", [False, True])
def test_altura_fixa_vai_ao_vlm_com_solo(h, livre):
    ref = VLM([_asa()], x_ref=XREF, altura_solo=h).resolver([ALFA], V=V)[0].CL
    u = UVLM([_asa()], V, alpha_graus=ALFA, dt=C / (4 * V), esteira_livre=livre, x_ref=XREF, solo=h,
             max_fileiras=None if livre else 120, fileiras_livres=24 if livre else None)
    u.roda(80 if livre else 120)
    assert u.h.CL[-1] == pytest.approx(ref, rel=0.012)
    livre_ar = VLM([_asa()], x_ref=XREF).resolver([ALFA], V=V)[0].CL
    assert u.h.CL[-1] > livre_ar


def test_chao_impermeavel_com_particulas():
    u = UVLMParticulas([_asa()], V, alpha_graus=ALFA, dt=C / (4 * V), x_ref=XREF, solo=0.15)
    u.roda(16)
    assert len(u.part) > 0
    Pg = _pontos_no_chao(u.solo, ALFA)
    v = u._induzida(Pg)
    assert np.abs(v @ u.solo.n).max() < 1e-10 * np.abs(v).max()
    assert np.all(u.solo.dist(u.part.X) >= 0)


def test_par_de_vortices_segue_a_trajetoria_de_lamb():
    b0, G, L, ds = 1.0, 1.0, 40.0, 0.05
    x = np.arange(-L / 2, L / 2, ds) + ds / 2
    n = len(x)
    P = Particulas("gaussiano")
    P.espelho = Solo(b0, 0.0)
    X = np.r_[np.c_[x, np.full(n, -b0 / 2), np.zeros(n)], np.c_[x, np.full(n, b0 / 2), np.zeros(n)]]
    A = np.r_[np.tile([-G * ds, 0, 0], (n, 1)), np.tile([G * ds, 0, 0], (n, 1))]
    P.adiciona(X, A, 0.1 * b0, 0, np.r_[np.zeros(n, int), np.ones(n, int)])
    dt = 0.1
    inv = []
    for k in range(200):
        u, _ = P.velocidade(P.X)
        X0 = P.X.copy(); P.X = X0 + 0.5 * dt * u
        u2, _ = P.velocidade(P.X); P.X = X0 + dt * u2
        if k % 20 == 19:
            m = (np.abs(P.X[:, 0]) < 1.0) & (P.fila == 1)
            y, z = P.X[m, 1].mean(), P.X[m, 2].mean() + b0
            inv.append(1 / y ** 2 + 1 / z ** 2)
    assert np.allclose(inv, 5.0, rtol=0.005)
    assert y > 2.5 and z < 0.47


def test_subida_lenta_e_quase_estatica():
    dt, h0, vs = C / (4 * V), 0.08, 0.3
    t0 = 40 * dt

    def alt(t):
        return h0 + vs * max(0.0, t - t0)
    u = UVLM([_asa()], V, alpha_graus=ALFA, dt=dt, esteira_livre=True, x_ref=XREF, solo=alt, fileiras_livres=24)
    u.roda(int(t0 / dt) + 160)
    g = math.degrees(math.atan2(vs, V))
    for k in (-100, -1):
        t = u.h.t[k]
        qs = VLM([_asa()], x_ref=XREF, altura_solo=alt(t)).resolver([ALFA - g], V=V)[0].CL
        assert u.h.CL[k] == pytest.approx(qs, rel=0.006)
    assert u.h.CL[int(t0 / dt) - 1] > u.h.CL[-1]


def test_erros_claros():
    with pytest.raises(ValueError, match="esteira livre"):
        UVLM([_asa()], V, alpha_graus=ALFA, esteira_livre=False, solo=lambda t: 0.2 + t)
    with pytest.raises(ValueError, match="abaixo do chão"):
        UVLM([_asa()], V, alpha_graus=ALFA, x_ref=XREF, solo=0.001)
    u = UVLM([_asa()], V, alpha_graus=ALFA, dt=C / (4 * V), x_ref=XREF, solo=lambda t: 0.05 - 2.0 * t)
    with pytest.raises(ValueError, match="encostou no chão"):
        u.roda(40)


def test_helice_girante_enxerga_o_chao():
    from aranduBIS.nucleo.aero import bemt as BM
    from aranduBIS.nucleo.aero import rll
    pa = BM.apc_tipica(12, 6)
    u = rll.UVLMHelice([_asa(ns=12, nc=2)], V, [{"pa": pa, "centro": (-0.2, 0.0, 0.0), "rpm": 7000}], alpha_graus=ALFA,
                       dt=C / (4 * V), x_ref=XREF, dpsi_graus=30.0, solo=0.25)
    assert u.helices[0].solo is u.solo and u.part.espelho is u.solo
    u.roda(3)
    Pg = _pontos_no_chao(u.solo, ALFA)
    v = u._induzida(Pg)
    assert np.abs(v @ u.solo.n).max() < 1e-10 * np.abs(v).max()
    assert u.hist_helice[0]["T"][-1] > 0
    assert "solo" in u.instantaneo()


def test_fronteira_uvlm_com_solo():
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("generico/asa_canard.json")
    r = AN.uvlm({"esquema": esq, "V": 15, "alpha": 4, "caso": "degrau", "rho": 1.1, "solo": True, "esteira": "rigida",
                 "discretizacao": "manual", "n_span": 8, "n_chord": 2, "cordas": 4, "instantaneos": True, "forcar": True})
    assert "erro" not in r, r.get("erro")
    s = r["solo"]
    assert s["origem"] == "pelas rodas" and s["h0"] > 0 and s["CL_solo"] > s["CL_livre"]
    assert r["CL_estacionario"] == pytest.approx(s["CL_solo"])
    assert r["quadros"]["quadros"][-1]["solo"]["n"][2] > 0.99
    r2 = AN.uvlm({"esquema": esq, "V": 15, "alpha": 4, "caso": "degrau", "rho": 1.1, "solo": True, "subida": 1.0,
                  "esteira": "rigida", "discretizacao": "manual", "n_span": 8, "n_chord": 2, "cordas": 3, "espera_cordas": 1,
                  "forcar": True})
    assert "erro" not in r2, r2.get("erro")
    assert r2["esteira"] == "livre" and any("rígida" in a for a in r2["avisos"])
    assert r2["solo"]["h"][-1] > r2["solo"]["h"][0] and "quase estático" in r2["ref"]["nome"]
