import math
import warnings

import numpy as np
import pytest

from aranduBIS.nucleo.aero.planform import Estacao, Planform
from aranduBIS.nucleo.aero.vlm import VLM, Superficie
from aranduBIS.nucleo.estrutura import flutter as FL
from aranduBIS.nucleo.estrutura import flutter_tempo as FT

from test_flutter import goland


@pytest.fixture(autouse=True)
def _sem_avisos():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


def _ret(c, semi, ns, nc, nome="w"):
    pl = Planform(estacoes=(Estacao(y=0.0, corda=c), Estacao(y=semi, corda=c)), nome=nome)
    return [Superficie(pl, n_span=ns, n_chord=nc)]


def test_lapis_de_matrizes_acha_polos_conhecidos():
    dt = 0.01
    t = np.arange(400) * dt
    s1, s2 = complex(-0.3, 2 * math.pi * 3.0), complex(0.2, 2 * math.pi * 7.5)
    y1 = np.exp(s1.real * t) * np.cos(s1.imag * t) + 0.5 * np.exp(s2.real * t) * np.sin(s2.imag * t)
    y2 = 0.3 * np.exp(s1.real * t) * np.sin(s1.imag * t) - np.exp(s2.real * t) * np.cos(s2.imag * t)
    ms = FT.lapis_de_matrizes(np.c_[y1, y2], dt, ordem=4)
    f = sorted((m["f_hz"], m["zeta"]) for m in ms)
    assert f[0][0] == pytest.approx(3.0, abs=1e-6) and f[0][1] == pytest.approx(-s1.real / abs(s1), abs=1e-6)
    assert f[1][0] == pytest.approx(7.5, abs=1e-6) and f[1][1] == pytest.approx(-s2.real / abs(s2), abs=1e-6)


def test_sem_ar_a_estrutura_vibra_nas_frequencias_naturais_sem_amortecer():
    y, c, EI, GJ, ea, m = goland(31)
    est = FL.estrutura_modal(y, c, EI, GJ, ea, m, 0.10, 0.25, n_modos=4)
    r = FT.marcha(_ret(1.8288, 6.096, 12, 4, "goland"), "goland", est, 0.33, 100.0, 1e-9, n_ciclos=10)
    f0 = est["vib"]["f_hz"]
    fs = sorted(x["f_hz"] for x in r["modos"])
    assert fs[0] == pytest.approx(f0[0], rel=0.01) and fs[1] == pytest.approx(f0[1], rel=0.03)
    assert all(abs(x["zeta"]) < 1e-4 for x in r["modos"])


def test_secao_tipica_de_asa_longa_bate_com_o_pk_de_theodorsen():
    rho, c, AR = 1.225, 0.1, 40.0
    b, span = c / 2, AR * c
    a, xth, mu, r2 = -0.2, 0.1, 20.0, 6 / 25
    wth = 2 * math.pi * 10; wh = 0.4 * wth
    m = mu * math.pi * rho * b * b; S = m * xth * b; Ia = m * r2 * b * b
    sup = _ret(c, span / 2, 20, 6, "tip")
    base = VLM(sup)
    kap = (base.resolver([1.0], V=10)[0].CL - base.resolver([0.0], V=10)[0].CL) * 180 / math.pi / (2 * math.pi)
    Ms2, Ks2 = np.array([[m, S], [S, Ia]]), np.diag([m * wh ** 2, Ia * wth ** 2])
    s, Vs, VF_pk = 1j * wth, np.linspace(5, 9, 81), None
    z_ant = V_ant = None
    for V in Vs:
        for _ in range(60):
            k = max(abs(s.imag), 1e-3) * b / V
            A = FL._coeficientes(rho, V, np.array([b]), np.array([a]), FL.theodorsen(k), kap)[0]
            Mi = np.linalg.inv(Ms2 - A[..., 2])
            ev = np.linalg.eigvals(np.block([[np.zeros((2, 2)), np.eye(2)], [-Mi @ (Ks2 - A[..., 0]), Mi @ A[..., 1]]]))
            ev = ev[ev.imag >= 0]; nv = ev[np.argmin(abs(ev - s))]
            if abs(nv - s) < 1e-8 * abs(s):
                s = nv; break
            s = nv
        z = -s.real / abs(s)
        if z_ant is not None and z_ant > 0 >= z:
            VF_pk = V_ant + (V - V_ant) * z_ant / (z_ant - z)
            break
        z_ant, V_ant = z, V
    est = {"N": 2, "Nw": 2, "y": np.array([0.0, span / 2]), "P": np.zeros((2, 3, 2)), "Ms": Ms2 * span / 2,
           "Ks": Ks2 * span / 2, "Cs": np.zeros((2, 2))}
    est["P"][:, 0, 0] = 1.0; est["P"][:, 1, 1] = 1.0
    r = FT.velocidade_de_flutter(sup, "tip", est, (a + 1) / 2, [0.88 * VF_pk, 1.08 * VF_pk], rho, refina=False, n_ciclos=10)
    assert r["VF"] == pytest.approx(VF_pk, rel=0.04)


@pytest.fixture(scope="module")
def goland_tempo():
    y, c, EI, GJ, ea, m = goland(31)
    est = FL.estrutura_modal(y, c, EI, GJ, ea, m, 0.10, 0.25, n_modos=4)
    return FT.velocidade_de_flutter(_ret(1.8288, 6.096, 24, 8, "goland"), "goland", est, 0.33, [150.0, 170.0], 1.225,
                                    refina=False, n_ciclos=10)


def test_asa_de_goland_no_tempo(goland_tempo):
    r = goland_tempo
    assert r["VF"] == pytest.approx(162.0, rel=0.03)
    assert 2 * math.pi * r["f_flutter_hz"] == pytest.approx(67.5, rel=0.05)
    assert all(max(m["iter"]) <= 10 for m in r["marchas"])


def test_polo_real_acha_o_crescimento_sem_oscilar():
    dt = 1e-3
    t = np.arange(0, 0.6, dt)
    for taxa in (-3.0, 2.0):
        q = np.c_[np.exp(taxa * t) + 0.5 * np.exp(-4 * t) * np.cos(2 * np.pi * 30 * t), 0.3 * np.exp(taxa * t)]
        r = FT.polo_real({"t": t, "q": q}, dt, 0.02, 10.0)
        assert r["s_real"] == pytest.approx(taxa, abs=0.05) and r["diverge"] == (taxa > 0)


def test_fronteira_flutter_no_tempo():
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("generico/asa_canard.json")
    p = {"esquema": esq, "Vd": 25, "rho": 1.1, "asa": "canard"}
    r = AN.flutter_tempo(dict(p, forcar=True, fatores=[1.0], n_ciclos=5))
    assert "erro" not in r, r.get("erro")
    assert r["VF_pk"] == pytest.approx(19.5, rel=0.05)
    assert r["VD_faixas"] == pytest.approx(26.5, rel=0.02)
    ds = r["VD_3d_simetrias"]
    assert ds["simetrico"] == pytest.approx(16.0, rel=0.05) and ds["anti"] < ds["simetrico"]
    assert r["VD_3d"] == ds["anti"]
    assert r["VD_marcha"] == pytest.approx(ds["simetrico"], rel=0.02)
    m = max(r["marchas"], key=lambda x: x["V"])
    assert m["zeta"] > 0 and 40 < m["f_hz"] < 70
    assert m["divergencia"]["diverge"]
    assert len(m["t"]) == len(m["alfa_ponta_rel"]) and r["discretizacao"]["superficies"] == ["canard"]


def test_canard_com_eixo_elastico_a_frente_nao_diverge_e_o_flutter_passa_da_exigencia():
    from aranduBIS.fronteira import analise as AN, geometria as G
    from aranduBIS.nucleo.estrutura import flutter as FL
    base = G.abre_exemplo("generico/asa_canard.json")
    var = G.abre_exemplo("generico/asa_canard_eixo_a_frente.json")
    assert FL.dados_de_vibracao(base, "canard", Vd=25.0, rho=1.1)["ea_c"][0] == pytest.approx(0.256, abs=0.003)
    assert FL.dados_de_vibracao(var, "canard", Vd=25.0, rho=1.1)["ea_c"][0] == pytest.approx(0.113, abs=0.003)
    r = AN.flutter_tempo({"esquema": var, "Vd": 25, "rho": 1.1, "asa": "canard", "forcar": True, "fatores": [1.0], "n_ciclos": 5})
    assert "erro" not in r, r.get("erro")
    assert r["VF_pk"] > 1.2 * 25.0
    assert r["VD_faixas"] is None
    assert r["VD_3d"] is None or r["VD_3d"] > 100.0
