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

def rigidez_local(xy: np.ndarray, E: float, nu: float, t: float, kd: float = 1e-3) -> np.ndarray:
    K = np.zeros((24, 24))
    Dm = E * t / (1 - nu ** 2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    Db = E * t ** 3 / (12 * (1 - nu ** 2)) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    G = E / (2 * (1 + nu)); Gs = 5.0 / 6.0 * G * t
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
    for i in range(4):
        K[6 * i + 5, 6 * i + 5] += kd * E * t * area / 4.0
    return K

def rigidez_global(P: np.ndarray, E: float, nu: float, t: float):
    R = eixos(P)
    c = P.mean(0)
    xy = ((P - c) @ R.T)[:, :2]
    Kl = rigidez_local(xy, E, nu, t)
    T = np.kron(np.eye(8), R)
    return T.T @ Kl @ T, T
