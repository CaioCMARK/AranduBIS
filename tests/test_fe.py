import numpy as np
import pytest

from aranduBIS.nucleo.fe import Modelo, Sistema, escreve, le

E, G, RHO = 70e9, 26e9, 2700.0
A, I1, I2, J, L = 4e-4, 8e-8, 3e-8, 5e-8, 1.0

def balanco(n=10, v=(0, 0, 1)):
    m = Modelo()
    m.material(1, E, G, rho=RHO); m.prop(1, 1, A, I1, I2, J)
    for i in range(n + 1):
        m.no(i + 1, 0, L * i / n, 0)
    for i in range(n):
        m.barra(i + 1, 1, i + 1, i + 2, v)
    m.engasta([1])
    return m

def test_flexao_nos_dois_planos():
    m = balanco()
    m.carga(1, 11, [0, 0, 100.0, 0, 0, 0]); m.carga(2, 11, [100.0, 0, 0, 0, 0, 0])
    S = Sistema(m)
    assert S.estatica(1)["u"][11][2] == pytest.approx(100 * L ** 3 / (3 * E * I1), rel=1e-9)
    assert S.estatica(2)["u"][11][0] == pytest.approx(100 * L ** 3 / (3 * E * I2), rel=1e-9)

def test_axial_e_torcao():
    m = balanco()
    m.carga(1, 11, [0, 1e4, 0, 0, 0, 0]); m.carga(2, 11, [0, 0, 0, 0, 50.0, 0])
    S = Sistema(m)
    assert S.estatica(1)["u"][11][1] == pytest.approx(1e4 * L / (E * A), rel=1e-9)
    assert S.estatica(2)["u"][11][4] == pytest.approx(50 * L / (G * J), rel=1e-9)

def test_esforcos_da_viga():
    m = balanco()
    m.carga(1, 11, [0, 0, 100.0, 0, 0, 0])
    ef = Sistema(m).estatica(1)["esforcos"]
    assert abs(ef[1][1]) == pytest.approx(100.0, rel=1e-9)
    assert abs(ef[1][5]) == pytest.approx(100.0 * L, rel=1e-9)

def test_primeiro_modo_do_balanco():
    f = Sistema(balanco(n=20)).modos(3)["f_hz"]
    esperado = 1.8751 ** 2 / (2 * np.pi) * np.sqrt(E * min(I1, I2) / (RHO * A * L ** 4))
    assert f[0] == pytest.approx(esperado, rel=2e-3)
    assert f[1] > f[0]

def test_massa_concentrada_na_ponta():
    m = balanco(n=20); m.props[1]["A"] = 1e-6; m.materiais[1]["rho"] = RHO
    m.massa(100, 21, 2.0)
    f = Sistema(m).modos(1)["f_hz"][0]
    k = 3 * E * min(I1, I2) / L ** 3
    assert f == pytest.approx(np.sqrt(k / 2.0) / (2 * np.pi), rel=2e-3)

def test_ligacao_rigida_gera_torcao():
    m = balanco()
    m.no(50, 0.2, L, 0); m.rigido(1, 11, [50])
    m.carga(1, 50, [0, 0, 100.0, 0, 0, 0])
    u = Sistema(m).estatica(1)["u"]
    assert abs(u[11][4]) == pytest.approx(100 * 0.2 * L / (G * J), rel=1e-6)
    assert u[50][2] == pytest.approx(u[11][2] + 0.2 * u[11][4], abs=1e-12) or u[50][2] == pytest.approx(u[11][2] - 0.2 * u[11][4], abs=1e-12)

def test_modelo_sem_engaste_e_detectado():
    m = balanco(); m.spc.clear(); m.carga(1, 11, [0, 0, 1.0, 0, 0, 0])
    with pytest.raises(Exception):
        Sistema(m).estatica(1)

def test_bdf_ida_e_volta():
    m = balanco(); m.no(50, 0.2, L, 0); m.rigido(1, 11, [50]); m.massa(100, 11, 0.5)
    m.carga(1, 50, [0, 0, 100.0, 0, 3.0, 0])
    txt = escreve(m)
    for cartao in ("GRID,", "MAT1,", "PBAR,", "CBAR,", "CONM2,", "RBE2,", "SPC1,", "FORCE,", "MOMENT,", "SOL 101"):
        assert cartao in txt
    m2 = le(txt)
    a, b = Sistema(m).estatica(1)["u"][50], Sistema(m2).estatica(1)["u"][50]
    assert np.allclose(a, b, rtol=1e-9, atol=1e-15)
    assert Sistema(m).modos(2)["f_hz"] == pytest.approx(Sistema(m2).modos(2)["f_hz"], rel=1e-9)

def test_semi_asa_contra_integracao_analitica():
    from aranduBIS.nucleo.fe.asa import resolve
    y = np.linspace(0.0, 1.2, 41)
    c = 0.36 - 0.14 * y / 1.2
    EI = 200.0 * (1 - 0.7 * y / 1.2)
    GJ = 25.0 * (1 - 0.5 * y / 1.2)
    ea_c, ca_c = 0.054 / c, 0.25
    q = 80.0 * np.sqrt(np.clip(1 - (y / 1.2) ** 2, 0, None))
    r = resolve(y, c=c, EI=EI, GJ=GJ, ea_c=ea_c, ca_c=ca_c, q_por_m=q)
    def cumint(f):
        return np.concatenate([[0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(y))])
    def do_fim(f):
        a = cumint(f); return a[-1] - a
    V = do_fim(q); M = do_fim(V)
    w = cumint(cumint(M / EI))
    T = do_fim(q * (ca_c - ea_c) * c)
    th = cumint(T / GJ)
    assert r["w"][-1] == pytest.approx(w[-1], rel=2e-3)
    assert abs(r["theta"][-1]) == pytest.approx(th[-1], rel=2e-3)

def test_linha_elastica_torta_acopla_flexao_e_torcao():
    from aranduBIS.nucleo.fe.asa import resolve
    y = np.linspace(0.0, 1.2, 41); c = 0.36 - 0.14 * y / 1.2
    kw = dict(c=c, EI=np.full(41, 200.0), GJ=np.full(41, 25.0), ca_c=0.25, q_por_m=np.full(41, 80.0))
    reto = resolve(y, ea_c=0.054 / c, **kw)["theta"][-1]
    torto = resolve(y, ea_c=np.full(41, 0.15), **kw)["theta"][-1]
    assert abs(torto - reto) > 0.01 * abs(reto)
