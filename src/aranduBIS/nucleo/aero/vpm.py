from __future__ import annotations

import math

import numpy as np
from numba import njit, prange

GAUSS, WINCK = 0, 1
NUCLEOS = {"gaussiano": GAUSS, "winckelmans": WINCK}
_S2PI = math.sqrt(2.0 / math.pi)
_R2 = math.sqrt(2.0)


@njit(cache=True, inline="always", fastmath=True)
def _h(rho, tipo):
    if tipo == 1:
        q = rho * rho + 1.0
        h = (rho * rho + 2.5) / q ** 2.5
        dh_rho = -(3.0 * rho * rho + 10.5) / q ** 3.5
        return h, dh_rho
    if rho < 1e-2:
        r2 = rho * rho
        return _S2PI * (1.0 / 3.0 - r2 / 10.0), _S2PI * (-1.0 / 5.0 + r2 / 14.0)
    e = math.exp(-0.5 * rho * rho)
    g = math.erf(rho / _R2) - _S2PI * rho * e
    gp = _S2PI * rho * rho * e
    r3 = rho * rho * rho
    h = g / r3
    dh_rho = (gp / r3 - 3.0 * g / (r3 * rho)) / rho
    return h, dh_rho


@njit(cache=True, inline="always", fastmath=True)
def _contrib(px, py, pz, xq, yq, zq, ax, ay, az, s, tipo, out_u, out_g, i, com_grad):
    rx, ry, rz = px - xq, py - yq, pz - zq
    r2 = rx * rx + ry * ry + rz * rz
    if r2 < 1e-24:
        return
    r = math.sqrt(r2)
    rho = r / s
    h, dh_rho = _h(rho, tipo)
    s3 = s * s * s
    f = -h / (4.0 * math.pi * s3)
    cx = ry * az - rz * ay; cy = rz * ax - rx * az; cz = rx * ay - ry * ax
    out_u[i, 0] += f * cx; out_u[i, 1] += f * cy; out_u[i, 2] += f * cz
    if com_grad:
        fr = -dh_rho / (4.0 * math.pi * s3 * s * s)
        out_g[i, 0, 1] += f * az; out_g[i, 0, 2] -= f * ay
        out_g[i, 1, 0] -= f * az; out_g[i, 1, 2] += f * ax
        out_g[i, 2, 0] += f * ay; out_g[i, 2, 1] -= f * ax
        out_g[i, 0, 0] += fr * rx * cx; out_g[i, 0, 1] += fr * ry * cx; out_g[i, 0, 2] += fr * rz * cx
        out_g[i, 1, 0] += fr * rx * cy; out_g[i, 1, 1] += fr * ry * cy; out_g[i, 1, 2] += fr * rz * cy
        out_g[i, 2, 0] += fr * rx * cz; out_g[i, 2, 1] += fr * ry * cz; out_g[i, 2, 2] += fr * rz * cz


_RHO_LONGE = 6.0


@njit(cache=True, inline="always", fastmath=True)
def _h_rapido(rho, tipo):
    if tipo == 0 and rho > _RHO_LONGE:
        r3 = rho * rho * rho
        return 1.0 / r3, -3.0 / (r3 * rho * rho)
    return _h(rho, tipo)


@njit(cache=True, inline="always", fastmath=True)
def _linha(P, X, A, S, tipo, com_grad, i, u, g):
    px, py, pz = P[i, 0], P[i, 1], P[i, 2]
    ux = 0.0; uy = 0.0; uz = 0.0
    g00 = 0.0; g01 = 0.0; g02 = 0.0; g10 = 0.0; g11 = 0.0; g12 = 0.0; g20 = 0.0; g21 = 0.0; g22 = 0.0
    q4 = 1.0 / (4.0 * math.pi)
    for q in range(X.shape[0]):
        rx, ry, rz = px - X[q, 0], py - X[q, 1], pz - X[q, 2]
        r2 = rx * rx + ry * ry + rz * rz
        if r2 < 1e-24:
            continue
        s = S[q]
        rho = math.sqrt(r2) / s
        h, dh_rho = _h_rapido(rho, tipo)
        s3 = s * s * s
        f = -h * q4 / s3
        ax, ay, az = A[q, 0], A[q, 1], A[q, 2]
        cx = ry * az - rz * ay; cy = rz * ax - rx * az; cz = rx * ay - ry * ax
        ux += f * cx; uy += f * cy; uz += f * cz
        if com_grad:
            fr = -dh_rho * q4 / (s3 * s * s)
            g01 += f * az; g02 -= f * ay; g10 -= f * az; g12 += f * ax; g20 += f * ay; g21 -= f * ax
            a0 = fr * cx; a1 = fr * cy; a2 = fr * cz
            g00 += a0 * rx; g01 += a0 * ry; g02 += a0 * rz
            g10 += a1 * rx; g11 += a1 * ry; g12 += a1 * rz
            g20 += a2 * rx; g21 += a2 * ry; g22 += a2 * rz
    u[i, 0] = ux; u[i, 1] = uy; u[i, 2] = uz
    if com_grad:
        g[i, 0, 0] = g00; g[i, 0, 1] = g01; g[i, 0, 2] = g02
        g[i, 1, 0] = g10; g[i, 1, 1] = g11; g[i, 1, 2] = g12
        g[i, 2, 0] = g20; g[i, 2, 1] = g21; g[i, 2, 2] = g22


@njit(cache=True, parallel=True, fastmath=True)
def _campo_par(P, X, A, S, tipo, com_grad):
    n = P.shape[0]
    u = np.zeros((n, 3)); g = np.zeros((n if com_grad else 1, 3, 3))
    for i in prange(n):
        _linha(P, X, A, S, tipo, com_grad, i, u, g)
    return u, g


@njit(cache=True, fastmath=True)
def _campo_seq(P, X, A, S, tipo, com_grad):
    n = P.shape[0]
    u = np.zeros((n, 3)); g = np.zeros((n if com_grad else 1, 3, 3))
    for i in range(n):
        _linha(P, X, A, S, tipo, com_grad, i, u, g)
    return u, g


@njit(cache=True, inline="always", fastmath=True)
def _zeta(rho, tipo):
    if tipo == 1:
        return 15.0 / (8.0 * math.pi) / (rho * rho + 1.0) ** 3.5
    return math.exp(-0.5 * rho * rho) / (2.0 * math.pi) ** 1.5


@njit(cache=True, parallel=True, fastmath=True)
def _vort_par(P, X, A, S, tipo):
    n = P.shape[0]
    w = np.zeros((n, 3))
    for i in prange(n):
        for q in range(X.shape[0]):
            rx, ry, rz = P[i, 0] - X[q, 0], P[i, 1] - X[q, 1], P[i, 2] - X[q, 2]
            s = S[q]
            z = _zeta(math.sqrt(rx * rx + ry * ry + rz * rz) / s, tipo) / (s * s * s)
            w[i, 0] += z * A[q, 0]; w[i, 1] += z * A[q, 1]; w[i, 2] += z * A[q, 2]
    return w


_MIN_PARALELO = 200_000


def campo(P, X, A, S, nucleo: str = "gaussiano", gradiente: bool = False):
    P = np.ascontiguousarray(P, dtype=np.float64)
    if len(X) == 0 or len(P) == 0:
        return np.zeros((len(P), 3)), (np.zeros((len(P), 3, 3)) if gradiente else None)
    f = _campo_par if len(P) * len(X) >= _MIN_PARALELO else _campo_seq
    u, g = f(P, np.ascontiguousarray(X, dtype=np.float64), np.ascontiguousarray(A, dtype=np.float64),
             np.ascontiguousarray(S, dtype=np.float64), NUCLEOS[nucleo], bool(gradiente))
    return u, (g if gradiente else None)


class Particulas:

    def __init__(self, nucleo: str = "gaussiano", nu: float = 0.0):
        if nucleo not in NUCLEOS:
            raise ValueError(f"núcleo desconhecido: {nucleo} (use {', '.join(NUCLEOS)})")
        self.nucleo, self.nu = nucleo, float(nu)
        self.X = np.zeros((0, 3)); self.A = np.zeros((0, 3)); self.S = np.zeros(0); self.nasc = np.zeros(0, int)
        self.ids = np.zeros(0, int); self._prox = 0
        self.fila = np.zeros(0, int); self.nivel = np.zeros(0, int)
        self.espelho = None

    def __len__(self):
        return len(self.S)

    def adiciona(self, X, A, S, passo: int = 0, fila=None) -> np.ndarray:
        n = len(X)
        ids = np.arange(self._prox, self._prox + n); self._prox += n
        self.X = np.vstack([self.X, X]); self.A = np.vstack([self.A, A])
        self.S = np.concatenate([self.S, np.broadcast_to(S, (n,))]); self.nasc = np.concatenate([self.nasc, np.full(n, passo)])
        self.ids = np.concatenate([self.ids, ids])
        self.fila = np.concatenate([self.fila, np.full(n, -1) if fila is None else np.asarray(fila, int)])
        self.nivel = np.concatenate([self.nivel, np.zeros(n, int)])
        return ids

    def indices(self, ids) -> np.ndarray:
        k = np.searchsorted(self.ids, ids)
        ok = (k < len(self.ids)) & (self.ids[np.minimum(k, len(self.ids) - 1)] == ids)
        return np.where(ok, k, -1)

    def remove(self, m) -> None:
        manter = ~np.asarray(m, bool)
        for k in ("X", "A", "S", "nasc", "ids", "fila", "nivel"):
            setattr(self, k, getattr(self, k)[manter])

    def funde(self, passo: int, idade0, arco_max=None) -> int:
        tot = 0
        if len(self) < 2:
            return 0
        def idades():
            v = np.asarray(idade0(self.fila) if callable(idade0) else np.full(len(self), float(idade0)), float)
            return np.where(v > 0, v, np.inf)
        idd = idades()
        if not np.isfinite(idd).any():
            return 0
        for m in range(int(np.log2(max(2, passo / max(1.0, idd.min())))) + 2):
            idd = idades()
            sel = np.nonzero((self.nivel == m) & (self.fila >= 0) & (passo - self.nasc >= idd * 2 ** m))[0]
            if len(sel) < 2:
                continue
            sel = sel[np.lexsort((self.nasc[sel], self.fila[sel]))]
            f = self.fila[sel]
            inicio = np.r_[0, np.nonzero(np.diff(f))[0] + 1]
            pos = np.arange(len(sel)) - np.repeat(inicio, np.diff(np.r_[inicio, len(sel)]))
            par = np.nonzero((pos % 2 == 0) & (np.r_[f[1:] == f[:-1], False]))[0]
            if not len(par):
                continue
            i0, i1 = sel[par], sel[par + 1]
            w0, w1 = np.linalg.norm(self.A[i0], axis=1), np.linalg.norm(self.A[i1], axis=1)
            curva = np.zeros(len(i0), bool)
            if arco_max is not None:
                arc = np.asarray(arco_max(self.fila[i0]) if callable(arco_max) else np.full(len(i0), float(arco_max)), float)
                curva = arc > 0
                if curva.any():
                    t0 = self.A[i0] / np.maximum(w0, 1e-300)[:, None]
                    t1 = self.A[i1] / np.maximum(w1, 1e-300)[:, None]
                    cth = np.clip(np.einsum("ij,ij->i", t0, t1), -1.0, 1.0)
                    ok = ~curva | (cth >= np.cos(np.radians(0.5 * np.where(curva, arc, 0.0))))
                    if not ok.all():
                        i0, i1, w0, w1, curva = i0[ok], i1[ok], w0[ok], w1[ok], curva[ok]
                        t0, t1, cth = t0[ok], t1[ok], cth[ok]
                        if not len(i0):
                            continue
            ws = w0 + w1
            peso = np.where(ws > 1e-300, w0 / np.where(ws > 0, ws, 1.0), 0.5)[:, None]
            Xn = peso * self.X[i0] + (1 - peso) * self.X[i1]
            An = self.A[i0] + self.A[i1]
            if curva.any():
                c = self.X[i1] - self.X[i0]
                L = np.linalg.norm(c, axis=1)
                sg = np.sign(np.einsum("ij,ij->i", c, t0 + t1)); sg[sg == 0] = 1.0
                d = -(t1 - t0) * sg[:, None]
                cu = c / np.maximum(L, 1e-300)[:, None]
                d -= np.einsum("ij,ij->i", d, cu)[:, None] * cu
                nd = np.linalg.norm(d, axis=1)
                th = np.arccos(cth)
                fl = 0.5 * L * np.tan(0.25 * th)
                k = curva & (nd > 1e-12)
                Xn[k] += (fl[k] / nd[k])[:, None] * d[k]
                nA = np.linalg.norm(An, axis=1)
                k = curva & (nA > 1e-300)
                An[k] *= (ws[k] / nA[k])[:, None]
            self.X[i0] = Xn
            self.A[i0] = An
            self.S[i0] = 2.0 * np.maximum(self.S[i0], self.S[i1])
            self.nasc[i0] = np.minimum(self.nasc[i0], self.nasc[i1])
            self.nivel[i0] = m + 1
            m1 = np.zeros(len(self), bool); m1[i1] = True
            self.remove(m1)
            tot += len(i1)
        return tot

    def velocidade(self, P, gradiente: bool = False):
        u, g = campo(P, self.X, self.A, self.S, self.nucleo, gradiente)
        if self.espelho is not None and len(self):
            ui, gi = campo(P, self.espelho.reflete(self.X), -self.espelho.vetor(self.A), self.S, self.nucleo, gradiente)
            u = u + ui
            if gradiente:
                g = g + gi
        return u, g

    def vorticidade(self, P):
        if not len(self):
            return np.zeros((len(P), 3))
        return _vort_par(np.ascontiguousarray(P, dtype=np.float64), self.X, self.A, self.S, NUCLEOS[self.nucleo])

    def relaxa(self, f: float) -> None:
        if f <= 0 or not len(self):
            return
        w = self.vorticidade(self.X)
        nw = np.linalg.norm(w, axis=1, keepdims=True)
        na = np.linalg.norm(self.A, axis=1, keepdims=True)
        ok = (nw[:, 0] > 1e-300) & (na[:, 0] > 0)
        alvo = np.where(ok[:, None], na * w / np.where(nw > 0, nw, 1.0), self.A)
        self.A = (1 - f) * self.A + f * alvo

    def confere(self, v_ref: float, o_que: str = "esteira de partículas") -> None:
        if not len(self):
            return
        if not np.isfinite(self.X).all() or not np.isfinite(self.A).all():
            raise ValueError(f"{o_que}: a nuvem divergiu (NaN). Diminua o passo ou aumente o núcleo das partículas.")

    def avanca(self, u, grad, dt: float, v_ref: float | None = None) -> None:
        if not len(self):
            return
        if v_ref is not None and (not np.isfinite(u).all() or np.abs(u).max() > 50 * v_ref):
            raise ValueError("esteira de partículas instável: velocidade induzida absurda numa partícula (encontro de "
                             "núcleos). Aumente a sobreposição dos núcleos ou diminua o passo.")
        self.X = self.X + u * dt
        if grad is not None:
            self.A = self.A + np.einsum("pil,pl->pi", grad, self.A) * dt
        if self.nu > 0:
            self.S = np.sqrt(self.S ** 2 + 2.0 * self.nu * dt)

    def vorticidade_total(self) -> np.ndarray:
        return self.A.sum(axis=0)

    def impulso(self) -> np.ndarray:
        return 0.5 * np.cross(self.X, self.A).sum(axis=0)


def anel(R: float, Gamma: float, n: int, sigma: float, centro=(0.0, 0.0, 0.0)) -> tuple:
    th = (np.arange(n) + 0.5) * 2 * np.pi / n
    X = np.c_[R * np.cos(th), R * np.sin(th), np.zeros(n)] + np.asarray(centro, float)
    t = np.c_[-np.sin(th), np.cos(th), np.zeros(n)]
    A = Gamma * t * (2 * np.pi * R / n)
    return X, A, np.full(n, float(sigma))


def velocidade_anel_filamento(R: float, Gamma: float, sigma: float) -> float:
    return Gamma / (4 * np.pi * R) * (np.log(8 * R / sigma) - 1.0 - 0.5 * (np.log(2.0) - np.euler_gamma))


def velocidade_anel_saffman(R: float, Gamma: float, delta: float) -> float:
    return Gamma / (4 * np.pi * R) * (np.log(8 * R / delta) - 0.558)
