from __future__ import annotations

import numpy as np

EPS = 1e-12


def _dist(P, C):
    A, B = P, np.roll(P, -1, axis=0)
    AB = B - A
    L2 = np.maximum(np.einsum("ij,ij->i", AB, AB), EPS)
    t = np.clip(np.einsum("cij,ij->ci", C[:, None, :] - A[None, :, :], AB) / L2, 0.0, 1.0)
    Q = A[None, :, :] + t[:, :, None] * AB[None, :, :]
    return np.min(np.linalg.norm(Q - C[:, None, :], axis=2), axis=1)


def _dentro(P, C):
    x, z = C[:, 0][:, None], C[:, 1][:, None]
    A, B = P[None, :, :], np.roll(P, -1, axis=0)[None, :, :]
    cruza = (A[..., 1] > z) != (B[..., 1] > z)
    dz = np.where(np.abs(B[..., 1] - A[..., 1]) < EPS, EPS, B[..., 1] - A[..., 1])
    xc = A[..., 0] + (z - A[..., 1]) / dz * (B[..., 0] - A[..., 0])
    return (np.sum(cruza & (x < xc), axis=1) % 2) == 1


def _envelope(P, xs):
    zs, zi = np.full(len(xs), -np.inf), np.full(len(xs), np.inf)
    for a, b in zip(P, np.roll(P, -1, axis=0)):
        if abs(b[0] - a[0]) < 1e-9:
            continue
        m = (xs >= min(a[0], b[0])) & (xs <= max(a[0], b[0]))
        z = a[1] + (xs[m] - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
        zs[m] = np.maximum(zs[m], z)
        zi[m] = np.minimum(zi[m], z)
    return zs, zi


def esforcos(x0: float, x1: float, carga_N: float, apoios) -> tuple:
    L = max(x1 - x0, EPS)
    q = carga_N / L
    ap = sorted(float(a) for a in apoios if x0 <= a <= x1)
    if len(ap) >= 2 and ap[-1] - ap[0] > 1e-6:
        a, b = ap[0], ap[-1]
        Rb = carga_N * (0.5 * (x0 + x1) - a) / (b - a)
        Ra = carga_N - Rb

        def VM(x):
            x = np.asarray(x, float)
            V = -q * (x - x0) + Ra * (x > a) + Rb * (x > b)
            M = -0.5 * q * (x - x0) ** 2 + Ra * np.maximum(x - a, 0.0) + Rb * np.maximum(x - b, 0.0)
            return V, M
        return VM, "biapoiada nos furos de tubo extremos"
    a = ap[0] if ap else x0 + 0.3 * L

    def VM(x):
        x = np.asarray(x, float)
        esq = x < a
        V = np.where(esq, -q * (x - x0), q * (x1 - x))
        M = np.where(esq, -0.5 * q * (x - x0) ** 2, -0.5 * q * (x1 - x) ** 2)
        return V, M
    return VM, "engastada no tubo" if ap else "engastada a 30 % da corda (sem furo de tubo na peça)"


def propoe(contorno, furos, espessura_mm: float, carga_N: float = 0.0, tau_adm_MPa: float = 1.0, sigma_adm_MPa: float = 5.0, fs: float = 1.5,
           borda_mm: float = 6.0, ponte_mm: float = 6.0, d_min_mm: float = 8.0, d_max_mm: float = 60.0, passo_mm: float = 1.0, max_furos: int = 24) -> dict:
    P = np.asarray(contorno, float)
    if len(P) < 3 or not espessura_mm > 0:
        return {"furos": [], "fracao": 0.0, "margem_min": None, "apoio": "", "area_mm2": 0.0}
    x0, x1 = float(P[:, 0].min()), float(P[:, 0].max())
    xs = np.arange(x0 + borda_mm, x1 - borda_mm + 1e-9, passo_mm)
    area = 0.5 * abs(float(P[:, 0] @ np.roll(P[:, 1], -1) - P[:, 1] @ np.roll(P[:, 0], -1)))
    VM, apoio = esforcos(x0, x1, carga_N, [f["c"][0] for f in furos])
    vazio = {"furos": [], "fracao": 0.0, "margem_min": None, "apoio": apoio, "area_mm2": area}
    if not len(xs):
        return vazio
    zs, zi = _envelope(P, xs)
    ok = np.isfinite(zs) & np.isfinite(zi)
    C = np.c_[xs[ok], 0.5 * (zs[ok] + zi[ok])]
    if not len(C):
        return vazio
    d = _dist(P, C)
    dentro = _dentro(P, C)
    raio = np.where(dentro, np.minimum(d - borda_mm, 0.5 * d_max_mm), -1.0)
    fixos = [(np.array(f["c"], float), 0.5 * max(f["d"], f.get("dx", f["d"]))) for f in furos]
    for c, r in fixos:
        raio = np.minimum(raio, np.linalg.norm(C - c, axis=1) - r - ponte_mm)
    aceitos = []
    while len(aceitos) < max_furos:
        k = int(np.argmax(raio))
        r = float(raio[k])
        if 2.0 * r < d_min_mm:
            break
        c, h = C[k].copy(), 2.0 * float(d[k])
        V, M = (abs(float(v)) for v in VM(c[0]))
        dd, margem = 2.0 * r, None
        while dd >= d_min_mm:
            tau = 1.5 * V / (espessura_mm * (h - dd))
            sig = M * 0.5 * h / (espessura_mm * (h ** 3 - dd ** 3) / 12.0)
            m_tau = tau_adm_MPa / (fs * tau) - 1.0 if tau > EPS else np.inf
            m_sig = sigma_adm_MPa / (fs * sig) - 1.0 if sig > EPS else np.inf
            margem = min(m_tau, m_sig)
            if margem >= 0.0:
                break
            dd *= 0.9
        if dd >= d_min_mm and margem is not None and margem >= 0.0:
            aceitos.append({"c": [float(c[0]), float(c[1])], "d": float(dd), "dx": float(dd), "tipo": "alivio", "altura_mm": h,
                            "margem": None if not np.isfinite(margem) else float(margem), "V_N": V, "M_Nmm": M})
            raio = np.minimum(raio, np.linalg.norm(C - c, axis=1) - 0.5 * dd - ponte_mm)
        else:
            raio[np.abs(C[:, 0] - c[0]) < max(0.5 * d_min_mm, passo_mm)] = -1.0
    aceitos.sort(key=lambda f: f["c"][0])
    removida = sum(0.25 * np.pi * f["d"] ** 2 for f in aceitos)
    margens = [f["margem"] for f in aceitos if f["margem"] is not None]
    return {"furos": aceitos, "fracao": float(removida / area) if area > 0 else 0.0, "margem_min": min(margens) if margens else None, "apoio": apoio, "area_mm2": area}
