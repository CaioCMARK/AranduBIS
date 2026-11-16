from __future__ import annotations

import numpy as np

_G2 = 1.0 / np.sqrt(3.0)
_PONTOS = [(-_G2, -_G2), (_G2, -_G2), (_G2, _G2), (-_G2, _G2)]
_XI = np.array([(-1, -1), (1, -1), (1, 1), (-1, 1)], float)

def eixos(P: np.ndarray) -> np.ndarray:
    d1, d2 = P[2] - P[0], P[3] - P[1]
    z = np.cross(d1, d2); nz = np.linalg.norm(z)
    if nz < 1e-18:
        raise ValueError("casca degenerada (area nula)")
    z /= nz
    x = P[1] - P[0]; x = x - z * (x @ z); x /= np.linalg.norm(x)
    return np.array([x, np.cross(z, x), z])

def _forma(xi, eta):
    N = 0.25 * (1 + _XI[:, 0] * xi) * (1 + _XI[:, 1] * eta)
    dxi = 0.25 * _XI[:, 0] * (1 + _XI[:, 1] * eta)
    deta = 0.25 * _XI[:, 1] * (1 + _XI[:, 0] * xi)
    return N, dxi, deta

def rigidez_local(xy: np.ndarray, E: float, nu: float, t: float, kd: float = 1e-2, E2: float | None = None, G12: float | None = None) -> np.ndarray:
    K = np.zeros((24, 24))
    if E2 is None:
        E2, G12 = E, E / (2 * (1 + nu))
    nu21 = nu * E2 / E
    den = 1.0 - nu * nu21
    Q = np.array([[E / den, nu * E2 / den, 0.0], [nu * E2 / den, E2 / den, 0.0], [0.0, 0.0, G12]])
    Dm, Db = Q * t, Q * t ** 3 / 12.0
    Gs = 5.0 / 6.0 * G12 * t
    area = 0.0
    im = np.array([[6 * i, 6 * i + 1] for i in range(4)]).ravel()
    ib = np.array([[6 * i + 2, 6 * i + 3, 6 * i + 4] for i in range(4)]).ravel()

    def jac(xi, eta):
        N, dxi, deta = _forma(xi, eta)
        J = np.array([[dxi @ xy[:, 0], dxi @ xy[:, 1]], [deta @ xy[:, 0], deta @ xy[:, 1]]])
        dN = np.linalg.solve(J, np.array([dxi, deta]))
        return N, dN, np.linalg.det(J)

    for xi, eta in _PONTOS:
        N, dN, dj = jac(xi, eta)
        area += dj
        Bm = np.zeros((3, 8))
        Bm[0, 0::2] = dN[0]; Bm[1, 1::2] = dN[1]; Bm[2, 0::2] = dN[1]; Bm[2, 1::2] = dN[0]
        K[np.ix_(im, im)] += Bm.T @ Dm @ Bm * dj
        bd = np.zeros(24)
        bd[0::6] = 0.5 * dN[1]; bd[1::6] = -0.5 * dN[0]; bd[5::6] = N
        K += kd * G12 * t * np.outer(bd, bd) * dj
        Bb = np.zeros((3, 12))
        Bb[0, 2::3] = dN[0]
        Bb[1, 1::3] = -dN[1]
        Bb[2, 2::3] = dN[1]; Bb[2, 1::3] = -dN[0]
        K[np.ix_(ib, ib)] += Bb.T @ Db @ Bb * dj
    N, dN, _ = jac(0.0, 0.0)
    _, _, dj0 = jac(0.0, 0.0)
    Bs = np.zeros((2, 12))
    Bs[0, 0::3] = dN[0]; Bs[0, 2::3] = N
    Bs[1, 0::3] = dN[1]; Bs[1, 1::3] = -N
    K[np.ix_(ib, ib)] += Bs.T @ (Gs * np.eye(2)) @ Bs * dj0 * 4.0
    return K

def rigidez_global(P: np.ndarray, E: float, nu: float, t: float, E2: float | None = None, G12: float | None = None):
    R = eixos(P)
    c = P.mean(0)
    xy = ((P - c) @ R.T)[:, :2]
    Kl = rigidez_local(xy, E, nu, t, E2=E2, G12=G12)
    T = np.kron(np.eye(8), R)
    return T.T @ Kl @ T, T
