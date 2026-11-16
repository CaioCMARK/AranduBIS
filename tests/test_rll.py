import math
import warnings

import numpy as np
import pytest

from aranduBIS.nucleo.aero import bemt as BM
from aranduBIS.nucleo.aero import rll
from aranduBIS.nucleo.aero.planform import Estacao, Planform
from aranduBIS.nucleo.aero.vlm import VLM, Superficie
from aranduBIS.nucleo.aero.vpm import Particulas

V, RPM, RHO = 12.0, 7000.0, 1.225


@pytest.fixture(scope="module")
def pa():
    return BM.apc_tipica(12, 6)


@pytest.fixture(scope="module")
def isolada(pa):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return rll.simula_isolada(pa, V, RPM, RHO, voltas=8, dpsi_graus=10.0)


def _asa(b=1.6, c=0.3, ns=24, nc=4):
    pl = Planform(estacoes=(Estacao(y=0.0, corda=c), Estacao(y=b / 2, corda=c)), nome="ret")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Superficie(pl, n_span=ns, n_chord=nc)


def _media_azimutal(h, part, x, r, n=36):
    q = np.linspace(0, 2 * np.pi, n + 1)[:-1]
    P = np.array([[x, ri * math.cos(a), ri * math.sin(a)] for ri in np.atleast_1d(r) for a in q])
    u = part.velocidade(P)[0] + h.induzida(P, rc=0.05 * h.R)
    return u[:, 0].reshape(-1, n).mean(1)


def test_isolada_bate_com_bemt(pa, isolada):
    h, part, _ = isolada
    m = h.media(1)
    b = BM.analisa(pa, V, RPM, RHO, n_est=40)
    assert m["T"] == pytest.approx(b.T, rel=0.04)
    assert m["P"] == pytest.approx(b.P, rel=0.04)
    T = np.array(h.hist["T"])
    n = int(round(360 / 10))
    assert np.std(T[-n:]) < 0.01 * m["T"]
    assert np.isfinite(part.X).all()


def test_velocidade_no_disco_bate_com_bemt(pa, isolada):
    h, part, _ = isolada
    b = BM.analisa(pa, V, RPM, RHO, n_est=40)
    r = np.array([0.4, 0.55, 0.7]) * pa.R
    u = _media_azimutal(h, part, 0.0, r)
    ref = np.interp(r, b.r, b.v_a * b.F)
    assert np.allclose(u, ref, rtol=0.15)


def test_esteira_longe_e_teoria_de_momento(pa, isolada):
    h, part, _ = isolada
    R = pa.R
    re = np.linspace(0, 1.4 * R, 43)
    rm = 0.5 * (re[1:] + re[:-1]); dA = np.pi * np.diff(re ** 2)
    ux = _media_azimutal(h, part, 3.0 * R, rm)
    T_mom = RHO * np.sum((V + ux) * ux * dA)
    assert T_mom == pytest.approx(h.media(1)["T"], rel=0.10)
    dentro = rm < 0.8 * R
    u_disco = _media_azimutal(h, part, 0.0, rm[dentro])
    a = np.sum(u_disco * dA[dentro]) / np.sum(dA[dentro])
    b = np.sum(ux[dentro] * dA[dentro]) / np.sum(dA[dentro])
    assert 1.5 < b / a < 2.3


def test_rolagem_conserva_vorticidade_e_corta_particulas(pa):
    h = rll.HeliceLinha(pa, (0, 0, 0), RPM, dpsi_graus=15.0)
    part = Particulas()
    for k in range(30):
        h.avanca_linhas(lambda P: np.broadcast_to([V, 0, 0], P.shape))
        h.resolve_gamma(lambda P: np.broadcast_to([V, 0, 0], P.shape).copy())
        h.converte(part, k)
    w0, n0 = part.vorticidade_total(), len(part)
    sumiram = h.rola(part, 30, 10)
    assert sumiram > 0 and len(part) == n0 - sumiram
    assert np.allclose(part.vorticidade_total(), w0, atol=1e-12)
    velhas = part.nivel == 1
    assert velhas.sum() <= 3 * 2 * (30 - 2 - 10 + 1)


def test_fusao_em_arco_mantem_o_anel_no_raio():
    n, R = 72, 1.0
    ph = (np.arange(n) + 0.5) * 2 * np.pi / n
    X = np.c_[np.zeros(n), R * np.cos(ph), R * np.sin(ph)]
    t = np.c_[np.zeros(n), -np.sin(ph), np.cos(ph)]
    L = 2 * R * np.sin(np.pi / n)
    raios = {}
    for arco in (None, 60.0):
        P = Particulas()
        P.adiciona(X, L * t, 1.3 * L, 0, np.zeros(n, int))
        P.nasc = np.arange(n).astype(P.nasc.dtype)
        for _ in range(6):
            P.funde(200, 1, arco)
        raios[arco] = np.hypot(P.X[:, 1], P.X[:, 2])
    assert raios[None].min() < 0.5
    assert np.allclose(raios[60.0], R, atol=1e-9)


def test_ponto_fixo_nao_serrilha_com_muitos_elementos(pa):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        h, part, _ = rll.simula_isolada(pa, V, RPM, RHO, voltas=1.5, dpsi_graus=15.0, n_el=20)
    G = h.ultimo["Gamma"][0]
    d2 = np.diff(G, 2)
    assert np.abs(d2).max() < 0.2 * np.abs(G).max()
    assert h.media(0.5)["T"] == pytest.approx(BM.analisa(pa, V, RPM, RHO, n_est=40).T, rel=0.08)


def test_guarda_de_instabilidade():
    P = Particulas()
    P.adiciona(np.zeros((2, 3)), np.ones((2, 3)), 0.01, 0, np.arange(2))
    with pytest.raises(ValueError, match="instável"):
        P.avanca(np.full((2, 3), 1e4), np.zeros((2, 3, 3)), 1e-3, v_ref=10.0)
    P.X[0, 0] = np.nan
    with pytest.raises(ValueError, match="divergiu"):
        P.confere(10.0)


@pytest.fixture(scope="module")
def acoplada(pa):
    from aranduBIS.nucleo.aero.uvlm import UVLMParticulas
    dt = 0.3 / (4 * V)
    out = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for sentido in (1, -1):
            u = rll.UVLMHelice([_asa()], V, [{"pa": pa, "centro": (-0.2, 0.0, 0.0), "rpm": RPM, "sentido": sentido}],
                               alpha_graus=4, dt=dt, dpsi_graus=15.0)
            u.roda(16)
            out[sentido] = u
        u0 = UVLMParticulas([_asa()], V, alpha_graus=4, dt=dt)
        u0.roda(16)
    out[0] = u0
    return out


def test_acoplada_sopro_aumenta_cl_como_o_bemt_com_sopro(pa, acoplada):
    u, u0 = acoplada[1], acoplada[0]
    b = BM.analisa(pa, V, RPM, RHO, n_est=40)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        v = VLM([_asa()])
        s = BM.sopro_de(b, (-0.2, 0, 0), (1, 0, 0), 1)
        sem = v.resolver([4.0], V=V)[0]
        com = v.resolver([4.0], V=V, v_local=s.velocidade(v.cps))[0]
    d_ref = com.CL - sem.CL
    d = np.mean(u.h.CL[-4:]) - np.mean(u0.h.CL[-4:])
    assert d > 0
    assert d == pytest.approx(d_ref, rel=0.3)
    T = np.mean(u.hist_helice[0]["T"][-4:])
    assert T == pytest.approx(b.T, rel=0.06)
    assert u.n_sub == round(u.dt * 2 * math.pi * RPM / 60 / math.radians(15.0))


def test_acoplada_giro_trocado_espelha_a_carga(acoplada):
    a, b = acoplada[1], acoplada[-1]
    ya = a.cp[:, 1]
    na, nb = a.G, b.G
    f = a.te[0]
    ns = f["ns"]
    ga, gb = na[f["fatia"]].reshape(-1, ns)[0], nb[f["fatia"]].reshape(-1, ns)[0]
    assert np.allclose(ga, gb[::-1], rtol=0.15, atol=0.02 * np.abs(ga).max())
    assert not np.allclose(ga, ga[::-1], rtol=0.02)
    assert ya.shape == b.cp[:, 1].shape


def test_instantaneo_tem_aneis_da_helice(acoplada):
    d = acoplada[1].instantaneo()
    assert len(d["aneis"]) == 1 + 2
    assert d["aneis"][1].shape[1] == 13
    assert len(d["X"]) == len(acoplada[1].part)


def test_fronteira_uvlm_com_helice_girante():
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("monoplano/monoplano_a.json")
    p = {"esquema": esq, "V": 12, "alpha": 4, "caso": "degrau", "helice_girante": True, "helice": "22x10E", "rpm": 4500,
         "rho": 1.1, "discretizacao": "manual", "n_span": 8, "n_chord": 2, "passos_por_corda": 2, "cordas": 2,
         "dpsi": 20, "instantaneos": True, "forcar": True}
    r = AN.uvlm(p)
    assert "erro" not in r, r.get("erro")
    h = r["helice"]
    assert h["n_sub"] >= 1 and len(h["T"]) == r["passos"] and h["T_media"] > 0
    assert h["T_media"] == pytest.approx(h["T_bemt"], rel=0.25)
    assert any(e["campo"] == "dpsi" and e["origem"] == "manual" for e in r["discretizacao"])
    assert any("antes do sopro" in a for a in r["avisos"])
    assert r["quadros"]["quadros"][-1]["pas"]
    assert r["esteira"] == "particulas"
