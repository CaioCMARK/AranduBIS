import numpy as np
import pytest

from aranduBIS.nucleo.estrutura import flutter as FL

N = 21
Y = np.linspace(0, 1.0, N); C = np.full(N, 0.25)
MK = ((Y >= 0.55) & (Y <= 0.95)).astype(float)
CF = 0.25 * 0.25

def _asa(GJ=150.0, x_alfa_c=0.0, **kw):
    return dict(y=Y, c=C, EI=np.full(N, 60.0), GJ=np.full(N, GJ), ea_c=np.full(N, 0.35), m=np.full(N, 0.45), x_alfa_c=x_alfa_c, r_cg_c=0.28,
                rho=1.225, Vmax=100, n_V=60, n_modos=4, **kw)

def _ail(m=0.05, xg=1 / 3, fb=0.0):
    return {"mascara": MK, "c": 0.5, "m": m, "x_b": xg * CF, "I_b": m * CF ** 2 / 6, "f_b": fb, "zeta": 0.0}

def test_constantes_classicas():
    T = FL.constantes_T(np.array([0.5]), np.array([-0.3]))
    assert 2 * T[10][0] == pytest.approx(2 * (np.sqrt(0.75) + np.arccos(0.5)))
    T1 = FL.constantes_T(np.array([1.0]), np.array([0.0]))
    assert all(abs(T1[k][0]) < 1e-12 for k in (1, 3, 4, 5, 7, 8, 10, 11, 12))

def test_massa_aparente_e_simetrica():
    A = FL._coeficientes3(1.225, 12.0, np.array([0.1]), np.array([-0.2]), np.array([0.8 - 0.1j]), 1.0, np.array([0.6]))
    Mac = A[0, :, :, 2].real
    assert np.allclose(Mac, Mac.T, rtol=1e-12, atol=1e-15)

def test_aileron_desbalanceado_e_frouxo_flutua_e_balanceado_nao():
    sem = FL.flutter(**_asa())
    assert sem["VF"] is None
    frouxo = FL.flutter(**_asa(aileron=_ail(xg=1 / 3, fb=0.0)))
    rigido = FL.flutter(**_asa(aileron=_ail(xg=1 / 3, fb=20.0)))
    balanceado = FL.flutter(**_asa(aileron=_ail(xg=0.0, fb=0.0)))
    assert frouxo["VF"] is not None and frouxo["VF"] < 10
    assert rigido["VF"] > 4 * frouxo["VF"]
    assert balanceado["VF"] is None or balanceado["VF"] > 70
    assert "aileron" in frouxo["natureza"]

def test_comando_muito_rigido_volta_a_asa_sem_aileron():
    base = FL.flutter(**_asa(GJ=25.0, x_alfa_c=0.10))
    trav = FL.flutter(**_asa(GJ=25.0, x_alfa_c=0.10, aileron=_ail(m=1e-4, fb=1e4)))
    assert trav["VF"] == pytest.approx(base["VF"], rel=0.01)

def test_analise_da_aeronave_com_aileron():
    from aranduBIS.fronteira import geometria as G
    esq = G.abre_exemplo("biplano/biplano_a.json")
    r = FL.analisa_flutter(esq, "asa_inferior", Vd=18.75, aileron={"f_b": 0.0}, n_V=25)
    assert r["aileron"]["nome"] == "aileron_inferior" and r["aileron"]["massa_kg"] > 0
    assert "estimada" in r["aileron"]["origem_massa"]
    assert len(r["f_vacuo_hz"]) == len(r["formas"]["h"]) == len(r["natureza"])
