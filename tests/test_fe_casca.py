import numpy as np
import pytest

from aranduBIS.nucleo.fe.modelo import Modelo
from aranduBIS.nucleo.fe.solver import Sistema

def _tubo(L=1.0, a=0.10, h=0.05, t=0.002, nx=20, na=4, nh=2, E=70e9, nu=0.3):
    m = Modelo(); m.material(1, E, nu=nu)
    perfil = []
    for p, q, n in (((-a / 2, -h / 2), (a / 2, -h / 2), na), ((a / 2, -h / 2), (a / 2, h / 2), nh), ((a / 2, h / 2), (-a / 2, h / 2), na), ((-a / 2, h / 2), (-a / 2, -h / 2), nh)):
        for k in range(n):
            perfil.append((p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n))
    nc = len(perfil); idn = lambda i, j: 1 + i * nc + (j % nc)
    for i in range(nx + 1):
        for j, (y, z) in enumerate(perfil):
            m.no(idn(i, j), L * i / nx, y, z)
    e = 1
    for i in range(nx):
        for j in range(nc):
            m.casca(e, 1, t, (idn(i, j), idn(i + 1, j), idn(i + 1, j + 1), idn(i, j + 1))); e += 1
    mestre = 10 ** 6
    m.no(mestre, L, 0.0, 0.0)
    m.rigido(1, mestre, [idn(nx, j) for j in range(nc)])
    m.engasta([idn(0, j) for j in range(nc)])
    return m, mestre, nc

def test_torcao_de_tubo_retangular_fecha_com_bredt_batho():
    L, a, h, t, E, nu = 1.0, 0.10, 0.05, 0.002, 70e9, 0.3
    m, mestre, _ = _tubo(L, a, h, t, E=E, nu=nu)
    T = 10.0
    m.carga(1, mestre, [0, 0, 0, T, 0, 0])
    u = Sistema(m).estatica(1)["u"][mestre]
    G = E / (2 * (1 + nu))
    J = 4 * (a * h) ** 2 / (2 * (a + h) / t)
    giro_fechado = T * L / (G * J)
    assert u[3] == pytest.approx(giro_fechado, rel=0.06)

def test_placa_engastada_em_flexao_fecha_com_viga():
    E, nu, L, b, t, nx, ny = 70e9, 0.3, 1.0, 0.1, 0.01, 20, 2
    m = Modelo(); m.material(1, E, nu=nu)
    idn = lambda i, j: 1 + i * (ny + 1) + j
    for i in range(nx + 1):
        for j in range(ny + 1):
            m.no(idn(i, j), L * i / nx, b * j / ny, 0.0)
    e = 1
    for i in range(nx):
        for j in range(ny):
            m.casca(e, 1, t, (idn(i, j), idn(i + 1, j), idn(i + 1, j + 1), idn(i, j + 1))); e += 1
    m.engasta([idn(0, j) for j in range(ny + 1)])
    P = 100.0
    for j in range(ny + 1):
        m.carga(1, idn(nx, j), [0, 0, P / (ny + 1), 0, 0, 0])
    u = Sistema(m).estatica(1)["u"]
    w = np.mean([u[idn(nx, j)][2] for j in range(ny + 1)])
    I = b * t ** 3 / 12
    assert w == pytest.approx(P * L ** 3 / (3 * E * I), rel=0.06)
