from __future__ import annotations

import numpy as np

G0 = 9.80665

def _cruz(v):
    return np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])

def alivio(pos, m, ref, externas, g=G0):
    pos, m, ref = np.asarray(pos, float), np.asarray(m, float), np.asarray(ref, float)
    r = pos - ref
    peso = np.zeros_like(pos); peso[:, 2] = -m * g
    F = peso.sum(axis=0) + sum(np.asarray(f, float) for _, f, _ in externas)
    M = np.cross(r, peso).sum(axis=0) + sum(np.cross(np.asarray(p, float) - ref, f) + np.asarray(mm, float) for p, f, mm in externas)
    mt = float(m.sum()); c = (m[:, None] * r).sum(axis=0)
    J = sum(mi * (ri @ ri * np.eye(3) - np.outer(ri, ri)) for mi, ri in zip(m, r))
    A = np.block([[mt * np.eye(3), -_cruz(c)], [_cruz(c), J]])
    x = np.linalg.solve(A, np.concatenate([F, M]))
    a, alfa = x[:3], x[3:]
    f = peso - m[:, None] * (a + np.cross(alfa, r))
    return f, a, alfa
