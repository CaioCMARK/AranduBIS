import warnings

import numpy as np
import pytest

from aranduBIS.nucleo.aero.planform import Estacao, Planform
from aranduBIS.nucleo.aero.uvlm import UVLM, kussner, wagner
from aranduBIS.nucleo.aero.vlm import VLM, Superficie


def _asa(AR, c=0.1, ns=24, nc=4):
    pl = Planform(estacoes=(Estacao(y=0.0, corda=c), Estacao(y=AR * c / 2, corda=c)), nome="ret")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Superficie(pl, n_span=ns, n_chord=nc)


@pytest.fixture(autouse=True)
def _sem_aviso_de_malha():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        yield


def test_limite_estacionario_igual_ao_vlm():
    s = _asa(8, c=0.25)
    ref = VLM([s]).resolver([5.0], V=10, rho=1.225)[0].CL
    u = UVLM([s], V=10, alpha_graus=5.0, esteira_livre=False, dt=0.25 / 10)
    u.roda(150)
    assert u.h.CL[-1] == pytest.approx(ref, rel=0.01)


def test_esteira_livre_desce_e_nao_muda_o_cl_em_angulo_pequeno():
    s = _asa(8, c=0.25, ns=16)
    r = UVLM([s], V=10, alpha_graus=5.0, esteira_livre=False, dt=0.25 / 10); r.roda(40)
    l = UVLM([s], V=10, alpha_graus=5.0, esteira_livre=True, dt=0.25 / 10); l.roda(40)
    Rw, _ = l.aneis_da_esteira()
    Rr, _ = r.aneis_da_esteira()
    assert Rw[..., 2].mean() < Rr[..., 2].mean()
    assert l.h.CL[-1] == pytest.approx(r.h.CL[-1], rel=0.02)


def test_wagner_em_asa_muito_alongada():
    c, V, a = 0.1, 10.0, 2.0
    u = UVLM([_asa(60, c=c, ns=40)], V=V, alpha_graus=a, esteira_livre=False, dt=c / (8 * V))
    h = u.roda(40)
    s = 2 * V * np.array(h.t) / c
    phi = np.array(h.CL) / (2 * np.pi * np.radians(a))
    k = (s >= 4) & (s <= 10)
    assert np.all(np.abs(phi[k] - wagner(s[k])) < 0.04)
    assert np.all(np.diff(phi[s >= 1]) > 0)


def test_kussner_rajada_degrau():
    c, V, w0 = 0.1, 10.0, 0.2

    def rajada(t, P):
        v = np.zeros_like(P)
        v[:, 2] = np.where(P[:, 0] < V * t, w0, 0.0)
        return v

    u = UVLM([_asa(60, c=c, ns=40, nc=8)], V=V, alpha_graus=0.0, esteira_livre=False, dt=c / (16 * V), rajada=rajada)
    h = u.roda(80)
    s = 2 * V * np.array(h.t) / c
    psi = np.array(h.CL) / (2 * np.pi * w0 / V)
    k = (s >= 3) & (s <= 10)
    assert np.all(np.abs(psi[k] - kussner(s[k])) < 0.03)


def test_max_fileiras_corta_a_esteira():
    u = UVLM([_asa(8, ns=8)], V=10, alpha_graus=3.0, esteira_livre=False, max_fileiras=10)
    u.roda(25)
    assert all(len(s["G"]) == 10 and len(s["nos"]) == 11 for s in u.te)


def test_theodorsen_mergulho_harmonico():
    from aranduBIS.nucleo.aero.uvlm import movimento_mergulho, theodorsen
    c, V, k = 0.1, 10.0, 0.4
    w = 2 * k * V / c; f = w / (2 * np.pi); h0 = 0.01 * c / k; per = 1 / f
    dt = c / (8 * V)
    u = UVLM([_asa(40, c=c, ns=24, nc=8)], V=V, esteira_livre=False, dt=dt, movimento=movimento_mergulho(h0, f), max_fileiras=150)
    h = u.roda(int(2.5 * per / dt))
    t, CL = np.array(h.t), np.array(h.CL)
    m = t > 1.25 * per
    X = np.c_[np.cos(w * t[m]), np.sin(w * t[m]), np.ones(m.sum())]
    a, b, _ = np.linalg.lstsq(X, CL[m], rcond=None)[0]
    uv = complex(a, -b)
    th = -2 * np.pi * complex(theodorsen(k)) * h0 * w / V - np.pi * (c / 2) * 1j * h0 * w * w / V ** 2
    assert abs(uv) == pytest.approx(abs(th), rel=0.08)
    assert abs(np.degrees(np.angle(uv / th))) < 6.0


def test_esteira_cortada_com_cauda_mantem_o_limite_estacionario():
    s = _asa(8, c=0.25)
    ref = VLM([s]).resolver([5.0], V=10, rho=1.225)[0].CL
    for livre in (False, True):
        u = UVLM([s], V=10, alpha_graus=5.0, esteira_livre=livre, dt=0.25 / 10, max_fileiras=20, fileiras_livres=10)
        u.roda(60)
        assert u.h.CL[-1] == pytest.approx(ref, rel=0.015)


def test_fronteira_uvlm_no_biplano():
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("biplano/biplano_a.json")
    r = AN.uvlm(dict(esquema=esq, V=15, caso="rajada_1cos", w0=3, H_cordas=6, cordas=4, n_span=8, n_chord=2, esteira_livre=False))
    assert "erro" not in r, r.get("erro")
    assert max(r["CL"][1:]) > r["CL_estacionario"] + 0.3 * r["CL_alpha"] * 3 / 15
    assert r["CL"][-1] == pytest.approx(r["CL_estacionario"], abs=0.05)
    assert len(r["esteira_lado"]) == len({e["nome"] for e in r["esteira_lado"]}) >= 2
    assert "erro" in AN.uvlm(dict(esquema=esq, caso="rajada_1cos"))
    assert "erro" in AN.uvlm(dict(esquema=esq, V=15, caso="xyz"))


def test_discretizacao_automatica_segue_as_regras_medidas():
    from aranduBIS.nucleo.aero.uvlm import LIMITE_PASSOS, discretizacao_auto
    a = discretizacao_auto("mergulho", k=0.4)
    assert a["n_chord"][0] == 10
    assert a["passos_por_corda"][0] >= 4
    assert discretizacao_auto("mergulho", k=2.0)["n_chord"][0] == 16
    assert discretizacao_auto("mergulho", k=0.05)["n_chord"][0] == 4
    assert discretizacao_auto("rajada_degrau")["n_chord"][0] == 8
    r = discretizacao_auto("rajada_1cos", H_cordas=25)
    assert r["cordas"][0] == 35 and r["passos_por_corda"][0] == 4
    longa = discretizacao_auto("rajada_1cos", H_cordas=200)
    assert longa["cordas"][0] * longa["passos_por_corda"][0] <= LIMITE_PASSOS
    assert discretizacao_auto("degrau", esteira_livre=True)["fileiras_livres"][0] is not None
    assert all(isinstance(m, str) and m for _, m in discretizacao_auto("degrau").values())


def test_fronteira_manual_sobrepoe_so_o_que_foi_preenchido():
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("biplano/biplano_a.json")
    base = dict(esquema=esq, V=15, caso="degrau", alpha=3)
    r = AN.uvlm(dict(base, discretizacao="manual", n_span=8, n_chord=2, cordas=3))
    d = {e["campo"]: e for e in r["discretizacao"]}
    assert d["n_chord"]["valor"] == 2 and d["n_chord"]["origem"] == "manual" and d["n_chord"]["auto"] == 4
    assert d["passos_por_corda"]["origem"] == "auto" and r["passos"] == 3 * d["passos_por_corda"]["valor"]
    assert r["paineis"] == 2 * 8 * len(r["esteira_lado"])
    r2 = AN.uvlm(dict(base, discretizacao="auto", n_chord=2, cordas=3, n_span=8, esteira_livre=False))
    assert {e["campo"]: e["origem"] for e in r2["discretizacao"]}["n_chord"] == "auto"


def test_regime_nao_depende_do_passo():
    sup = [_asa(6.0, c=0.14, ns=24, nc=12)]
    cl = []
    for por_corda in (1, 4, 12):
        dt = 0.14 / (por_corda * 10.0); n = 30 * por_corda
        u = UVLM(sup, 10.0, alpha_graus=5.0, dt=dt, esteira_livre=False, max_fileiras=n + 2)
        u.roda(n)
        cl.append(u.h.CL[-1])
    assert max(cl) - min(cl) < 2e-4 * max(cl)


def test_arfagem_harmonica_adianta_a_fase_como_theodorsen():
    from aranduBIS.nucleo.aero import uvlm as U
    c, AR, V, k = 0.1, 30.0, 10.0, 0.3
    sup = [_asa(AR, c=c, ns=30, nc=12)]
    base = VLM(sup)
    CLa = (base.resolver([1.0], V=V)[0].CL - base.resolver([0.0], V=V)[0].CL) * 180 / np.pi
    b = c / 2; w = k * V / b; f = w / (2 * np.pi)
    dt = c / (12 * V)
    u = UVLM(sup, V, dt=dt, esteira_livre=False, movimento=U.movimento_arfagem(1.0, f, 0.25 * c, V), max_fileiras=300)
    u.roda(int(3 / (f * dt)))
    t = np.array(u.h.t); CL = np.array(u.h.CL); m = t > t[-1] - 1 / f
    A, B, _ = np.linalg.lstsq(np.c_[np.sin(w * t[m]), np.cos(w * t[m]), np.ones(m.sum())], CL[m], rcond=None)[0]
    th, C = np.radians(1.0), complex(U.theodorsen(k))
    Z = CLa * C * (th + (b / V) * 1j * w * th) + CLa / (2 * np.pi) * (np.pi * (b / V) * 1j * w * th + 0.5 * np.pi * (b / V) ** 2 * (-w * w * th))
    fase = np.degrees(np.arctan2(B, A))
    assert fase > 0
    assert fase == pytest.approx(np.degrees(np.angle(Z)), abs=5.0)
    assert np.hypot(A, B) == pytest.approx(abs(Z), rel=0.12)
