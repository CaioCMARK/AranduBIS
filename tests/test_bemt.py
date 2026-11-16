import warnings

import numpy as np
import pytest

from aranduBIS.nucleo.aero import bemt as BM

warnings.simplefilter("ignore")


def _polar():
    from pathlib import Path
    from aranduBIS.nucleo.aero.polares import BancoPolares
    return BancoPolares.carregar_npz(Path(__file__).resolve().parents[1] / "data/polares.npz")["CLARK_Y_AIRFOIL@n7"]


def test_bemt_reproduz_o_projeto_otimo_sem_arrasto():
    B, D, rpm, V, T, rho = 2, 0.5, 4000, 15.0, 30.0, 1.225
    d = BM.projeto_otimo(B, D, rpm, V, T, rho, cl_projeto=0.6)
    pa = BM.Pa(D=D, B=B, r_R=d["r_R"], c_R=d["c_R"], beta_graus=d["beta_graus"], r_cubo_R=0.12, perfil=None)
    r = BM.analisa(pa, V, rpm, rho)
    assert r.convergiu
    assert r.T == pytest.approx(T, rel=0.01)
    assert r.P == pytest.approx(d["P"], rel=0.01)
    assert r.eta == pytest.approx(d["eta"], rel=0.002)
    assert d["eta"] < BM.eficiencia_ideal(T, V, D, rho)


def test_bemt_reproduz_o_projeto_otimo_com_perfil_real():
    pol = _polar()
    al = np.linspace(-4, 10, 281)

    def alpha_de(cl0, Re):
        out = []
        for re in np.atleast_1d(Re):
            cl, _, _ = pol(al, np.full_like(al, np.clip(re, pol.re[0], pol.re[-1])), avisar=False)
            out.append(np.interp(cl0, cl, al))
        return np.array(out)

    def eps(cl0, Re):
        a = alpha_de(cl0, Re)
        cl, cd, _ = pol(a, np.clip(np.atleast_1d(Re), pol.re[0], pol.re[-1]), avisar=False)
        return cd / cl

    B, D, rpm, V, T, rho = 2, 0.5, 4000, 15.0, 30.0, 1.225
    d = BM.projeto_otimo(B, D, rpm, V, T, rho, cl_projeto=0.7, cd_cl=eps, alpha_projeto=lambda Re: alpha_de(0.7, Re))
    pa = BM.Pa(D=D, B=B, r_R=d["r_R"], c_R=d["c_R"], beta_graus=d["beta_graus"], r_cubo_R=0.12, perfil=pol)
    r = BM.analisa(pa, V, rpm, rho)
    assert r.T == pytest.approx(T, rel=0.01) and r.P == pytest.approx(d["P"], rel=0.01)
    assert r.eta == pytest.approx(d["eta"], rel=0.003)


def test_parada_e_teoria_de_momento():
    pa = BM.apc_tipica(16, 8, None)
    r = BM.analisa(pa, 0.0, 5000, 1.225, perdas=False)
    assert r.convergiu and r.T > 0
    A = np.pi * pa.R ** 2
    P_ideal = r.T ** 1.5 / np.sqrt(2 * 1.225 * A)
    assert P_ideal < r.P < 1.6 * P_ideal
    assert np.allclose(r.v_a, np.sqrt(r.dT / (4 * np.pi * r.r * 1.225)), rtol=1e-6)


@pytest.mark.parametrize("nome", ["16x8E", "18x10E", "22x10E"])
def test_forma_tipica_apc_fica_perto_do_catalogo(nome):
    from aranduBIS.nucleo.aero.apc import catalogo
    from aranduBIS.nucleo.aero.polares import estender_viterna
    h = catalogo()[nome]
    pa = BM.apc_tipica(h.D_pol, h.passo_pol, estender_viterna(_polar()))
    rpm = 5000 if h.D_pol < 20 else 4000
    Js = np.array([0.0, 0.2, 0.4])
    ct, cp = h.coeficientes(Js, rpm)
    res = BM.curva(pa, rpm, Js, 1.225)
    assert all(x.convergiu for x in res)
    assert np.allclose([x.CT for x in res], ct, rtol=0.15)
    assert np.allclose([x.CP for x in res], cp, rtol=0.15)


def test_sopro_conserva_massa_e_dobra_longe():
    pa = BM.apc_tipica(16, 8, None)
    r = BM.analisa(pa, 12.0, 5000, 1.225, perdas=True)
    s = BM.sopro_de(r, centro=(0, 0, 0))
    j = len(r.r) // 2
    assert s.velocidade(np.array([[0.0, r.r[j], 0.0]]))[0][0] == pytest.approx(r.v_a[j], rel=1e-9)
    rb, k = s.bordas(50 * pa.R)
    assert k > 1.99
    rm = 0.5 * (rb[j] + rb[j + 1])
    assert s.velocidade(np.array([[50 * pa.R, rm, 0.0]]))[0][0] == pytest.approx(k * r.v_a[j], rel=1e-9)

    def vazao(x):
        rb, _ = s.bordas(x)
        rr = np.linspace(rb[0], rb[-1], 20001)
        rm = 0.5 * (rr[1:] + rr[:-1])
        u = 12 + s.velocidade(np.c_[np.full(len(rm), x), rm, np.zeros(len(rm))])[:, 0]
        return np.sum(u * 2 * np.pi * rm * np.diff(rr))
    assert vazao(10 * pa.R) == pytest.approx(vazao(0.0), rel=1e-3)
    assert rb[-1] < s.bordas(0.0)[0][-1]
    assert np.allclose(s.velocidade(np.array([[0.5, 2 * pa.R, 0.0]])), 0)
    vt = s.velocidade(np.array([[0.1, 0.0, r.r[j]]]))[0]
    assert vt[1] > 0


def test_fronteira_helice_e_sopro_na_asa():
    import copy
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("monoplano/monoplano_a.json")
    r = AN.helice({"esquema": esq, "helice": "22x10E", "rpm": 4500, "V": 12, "rho": 1.1, "alpha": 4})
    assert "erro" not in r, r.get("erro")
    assert r["ponto"]["T"] > 0 and 0 < r["ponto"]["eta"] < r["ponto"]["eta_ideal"]
    assert len(r["curva"]["CT"]) == len(r["curva"]["CT_apc"]) == len(r["curva"]["J"])
    e2 = copy.deepcopy(esq)
    next(el for el in e2["elementos"] if el["nome"] == "helice")["posicao"] = [-0.25, 0.0, 0.5]
    a = AN.helice({"esquema": e2, "helice": "22x10E", "rpm": 4500, "V": 12, "rho": 1.1, "alpha": 4, "sentido": 1})["sopro"]
    b = AN.helice({"esquema": e2, "helice": "22x10E", "rpm": 4500, "V": 12, "rho": 1.1, "alpha": 4, "sentido": -1})["sopro"]
    assert a["CL_com"] > 1.03 * a["CL_sem"] and "asa" in a["afetadas"]
    qa = next(q for q in a["superficies"] if q["nome"] == "asa")
    qb = next(q for q in b["superficies"] if q["nome"] == "asa")
    ya, da = np.array(qa["y"]), np.array(qa["cl_com"]) - np.array(qa["cl_sem"])
    db = np.array(qb["cl_com"]) - np.array(qb["cl_sem"])
    assert np.allclose(np.interp(ya, -ya[::-1], da[::-1]), db, atol=1e-3)
    assert "erro" in AN.helice({"helice": "99x99E"})
