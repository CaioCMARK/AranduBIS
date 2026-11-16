import warnings

import numpy as np
import pytest

from aranduBIS.nucleo.aero import vpm as P


@pytest.mark.parametrize("nucleo", ["gaussiano", "winckelmans"])
def test_gradiente_analitico_bate_com_diferencas_finitas(nucleo):
    rng = np.random.default_rng(0)
    X, A, S, Q = rng.normal(size=(40, 3)), rng.normal(size=(40, 3)), np.full(40, 0.3), rng.normal(size=(6, 3))
    u, g = P.campo(Q, X, A, S, nucleo, True)
    h, gf = 1e-6, np.zeros_like(g)
    for l in range(3):
        e = np.zeros(3); e[l] = h
        gf[:, :, l] = (P.campo(Q + e, X, A, S, nucleo)[0] - P.campo(Q - e, X, A, S, nucleo)[0]) / (2 * h)
    assert np.abs(g - gf).max() < 1e-7 * np.abs(gf).max()


def test_longe_das_particulas_e_biot_savart_classico():
    X, A, S = P.anel(1.0, 2.0, 600, 0.05)
    z = np.array([0.5, 1.0, 2.0])
    for nuc in ("gaussiano", "winckelmans"):
        u, _ = P.campo(np.c_[np.zeros(3), np.zeros(3), z], X, A, S, nuc)
        assert np.allclose(u[:, 2], 2.0 / (2 * (1 + z ** 2) ** 1.5), rtol=1e-4)
        assert np.abs(u[:, :2]).max() < 1e-10


@pytest.mark.parametrize("sigma", [0.1, 0.05, 0.025])
def test_anel_fino_anda_na_velocidade_da_teoria(sigma):
    X, A, S = P.anel(1.0, 1.0, int(2 * np.pi / (sigma / 4)), sigma)
    u, _ = P.campo(X, X, A, S)
    assert u[:, 2].mean() == pytest.approx(P.velocidade_anel_filamento(1.0, 1.0, sigma), rel=1e-3)
    assert np.abs(u[:, :2]).max() < 1e-9 * abs(u[:, 2].mean()) + 1e-12


def test_anel_marchando_conserva_raio_impulso_e_intensidade():
    sigma = 0.08
    X, A, S = P.anel(1.0, 1.0, 160, sigma)
    nuvem = P.Particulas("gaussiano")
    nuvem.adiciona(X, A, S)
    I0, a0 = nuvem.impulso(), np.linalg.norm(nuvem.A, axis=1).mean()
    U = P.velocidade_anel_filamento(1.0, 1.0, sigma)
    dt = 0.05
    for _ in range(40):
        u, g = nuvem.velocidade(nuvem.X, gradiente=True)
        nuvem.avanca(u, g, dt)
    R = np.hypot(nuvem.X[:, 0], nuvem.X[:, 1])
    assert R.mean() == pytest.approx(1.0, abs=2e-3) and R.std() < 1e-6
    assert nuvem.X[:, 2].mean() == pytest.approx(U * 40 * dt, rel=1e-3)
    assert np.allclose(nuvem.impulso(), I0, rtol=0, atol=1e-3 * np.linalg.norm(I0))
    assert np.linalg.norm(nuvem.A, axis=1).mean() == pytest.approx(a0, rel=2e-3)


def test_difusao_espalha_o_nucleo():
    nuvem = P.Particulas("gaussiano", nu=1e-3)
    nuvem.adiciona(np.zeros((1, 3)), np.ones((1, 3)), 0.01)
    nuvem.avanca(np.zeros((1, 3)), None, 10.0)
    assert nuvem.S[0] == pytest.approx(np.sqrt(0.01 ** 2 + 2e-3 * 10), rel=1e-12)


def test_fusao_conserva_a_vorticidade_e_reduz_as_particulas():
    nuvem = P.Particulas()
    rng = np.random.default_rng(1)
    for passo in range(64):
        nuvem.adiciona(np.c_[np.full(5, passo * 0.1), np.arange(5), np.zeros(5)], rng.normal(size=(5, 3)), 0.13, passo, fila=np.arange(5))
        tot = nuvem.vorticidade_total()
        nuvem.funde(passo, 8)
        assert np.allclose(nuvem.vorticidade_total(), tot)
    assert len(nuvem) < 0.4 * 64 * 5
    assert set(np.unique(nuvem.fila)) == set(range(5))


def _asa(AR, c, ns):
    from aranduBIS.nucleo.aero.planform import Estacao, Planform
    from aranduBIS.nucleo.aero.vlm import Superficie
    pl = Planform(estacoes=(Estacao(y=0.0, corda=c), Estacao(y=AR * c / 2, corda=c)), nome="ret")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Superficie(pl, n_span=ns, n_chord=4)


def test_esteira_de_particulas_reproduz_a_de_aneis():
    from aranduBIS.nucleo.aero.uvlm import UVLM, UVLMParticulas
    from aranduBIS.nucleo.aero.vlm import VLM
    warnings.simplefilter("ignore")
    c, s = 0.25, _asa(8, 0.25, 12)
    dt = c / 40
    r = UVLM([s], V=10, alpha_graus=5, esteira_livre=True, dt=dt, fileiras_livres=None); r.roda(100)
    p = UVLMParticulas([s], V=10, alpha_graus=5, dt=dt); p.roda(100)
    assert np.abs(np.array(p.h.CL) / np.array(r.h.CL) - 1).max() < 0.005
    assert p.h.CL[-1] == pytest.approx(VLM([s]).resolver([5.0], V=10, rho=1.225)[0].CL, rel=0.01)
    assert len(p.part) < 0.5 * 100 * (2 * 12 + 1)


def test_vortice_de_ponta_enrola_para_dentro():
    from aranduBIS.nucleo.aero.uvlm import UVLMParticulas
    warnings.simplefilter("ignore")
    c, s = 0.25, _asa(6, 0.25, 12)
    p = UVLMParticulas([s], V=10, alpha_graus=10, dt=c / 40); p.roda(60)
    semi = 6 * c / 2
    longe = p.part.X[:, 0] > p.part.X[:, 0].max() - 0.3
    ax = np.abs(p.part.A[:, 0])
    m = longe & (ax > np.percentile(ax[longe], 90))
    y_vort = np.average(np.abs(p.part.X[m, 1]), weights=ax[m])
    assert 0.7 * semi < y_vort < semi


def test_fronteira_esteira_de_particulas_e_video():
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("biplano/biplano_a.json")
    p = dict(esquema=esq, V=15, caso="degrau", alpha=3, esteira="particulas", discretizacao="manual", n_span=6, n_chord=2, cordas=4)
    r = AN.uvlm(p)
    assert "erro" not in r, r.get("erro")
    assert r["esteira"] == "particulas" and r["particulas"]["n"] > 0
    assert {e["campo"] for e in r["discretizacao"]} >= {"fileiras_aneis", "idade_fusao", "sobreposicao"}
    assert "erro" in AN.uvlm(dict(p, esteira="xyz"))
    dados, tipo = AN.uvlm_video(dict(p, cordas=2, largura=480))
    assert tipo == "video/mp4" and dados[4:8] == b"ftyp" and len(dados) > 5000
