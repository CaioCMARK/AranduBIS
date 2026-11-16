from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numba import njit, prange
from scipy.linalg import lu_factor, lu_solve

from .vlm import VLM, Superficie, _velocidade_segmento


@njit(cache=True, inline="always", fastmath=True)
def _bs(px, py, pz, ax, ay, az, bx, by, bz, rc):
    r1x, r1y, r1z = px - ax, py - ay, pz - az
    r2x, r2y, r2z = px - bx, py - by, pz - bz
    cx = r1y * r2z - r1z * r2y; cy = r1z * r2x - r1x * r2z; cz = r1x * r2y - r1y * r2x
    n1 = math.sqrt(r1x * r1x + r1y * r1y + r1z * r1z); n2 = math.sqrt(r2x * r2x + r2y * r2y + r2z * r2z)
    if n1 < 1e-12 or n2 < 1e-12:
        return 0.0, 0.0, 0.0
    r0x, r0y, r0z = bx - ax, by - ay, bz - az
    d = cx * cx + cy * cy + cz * cz + rc * rc * (r0x * r0x + r0y * r0y + r0z * r0z)
    if d < 1e-30:
        return 0.0, 0.0, 0.0
    K = (r0x * (r1x / n1 - r2x / n2) + r0y * (r1y / n1 - r2y / n2) + r0z * (r1z / n1 - r2z / n2)) / (4.0 * math.pi * d)
    return cx * K, cy * K, cz * K


@njit(cache=True, parallel=True, fastmath=True)
def _soma_par(P, A, B, G, rc):
    n, m = P.shape[0], A.shape[0]
    out = np.zeros((n, 3))
    for i in prange(n):
        sx = 0.0; sy = 0.0; sz = 0.0
        for j in range(m):
            ux, uy, uz = _bs(P[i, 0], P[i, 1], P[i, 2], A[j, 0], A[j, 1], A[j, 2], B[j, 0], B[j, 1], B[j, 2], rc)
            sx += G[j] * ux; sy += G[j] * uy; sz += G[j] * uz
        out[i, 0] = sx; out[i, 1] = sy; out[i, 2] = sz
    return out


@njit(cache=True, fastmath=True)
def _soma_seq(P, A, B, G, rc):
    n, m = P.shape[0], A.shape[0]
    out = np.zeros((n, 3))
    for i in range(n):
        sx = 0.0; sy = 0.0; sz = 0.0
        for j in range(m):
            ux, uy, uz = _bs(P[i, 0], P[i, 1], P[i, 2], A[j, 0], A[j, 1], A[j, 2], B[j, 0], B[j, 1], B[j, 2], rc)
            sx += G[j] * ux; sy += G[j] * uy; sz += G[j] * uz
        out[i, 0] = sx; out[i, 1] = sy; out[i, 2] = sz
    return out


@njit(cache=True, parallel=True, fastmath=True)
def _por_segmento_par(P, A, B, rc):
    n, m = P.shape[0], A.shape[0]
    out = np.zeros((n, m, 3))
    for i in prange(n):
        for j in range(m):
            ux, uy, uz = _bs(P[i, 0], P[i, 1], P[i, 2], A[j, 0], A[j, 1], A[j, 2], B[j, 0], B[j, 1], B[j, 2], rc)
            out[i, j, 0] = ux; out[i, j, 1] = uy; out[i, j, 2] = uz
    return out


@njit(cache=True, fastmath=True)
def _por_segmento(P, A, B, rc):
    n, m = P.shape[0], A.shape[0]
    out = np.zeros((n, m, 3))
    for i in range(n):
        for j in range(m):
            ux, uy, uz = _bs(P[i, 0], P[i, 1], P[i, 2], A[j, 0], A[j, 1], A[j, 2], B[j, 0], B[j, 1], B[j, 2], rc)
            out[i, j, 0] = ux; out[i, j, 1] = uy; out[i, j, 2] = uz
    return out


@njit(cache=True, inline="always", fastmath=True)
def _bs_grad(px, py, pz, ax, ay, az, bx, by, bz, rc, out):
    for q in range(12):
        out[q] = 0.0
    r1x, r1y, r1z = px - ax, py - ay, pz - az
    r2x, r2y, r2z = px - bx, py - by, pz - bz
    n1 = math.sqrt(r1x * r1x + r1y * r1y + r1z * r1z); n2 = math.sqrt(r2x * r2x + r2y * r2y + r2z * r2z)
    if n1 < 1e-12 or n2 < 1e-12:
        return
    cx = r1y * r2z - r1z * r2y; cy = r1z * r2x - r1x * r2z; cz = r1x * r2y - r1y * r2x
    r0x, r0y, r0z = bx - ax, by - ay, bz - az
    d = cx * cx + cy * cy + cz * cz + rc * rc * (r0x * r0x + r0y * r0y + r0z * r0z)
    if d < 1e-30:
        return
    u1x, u1y, u1z = r1x / n1, r1y / n1, r1z / n1
    u2x, u2y, u2z = r2x / n2, r2y / n2, r2z / n2
    N = r0x * (u1x - u2x) + r0y * (u1y - u2y) + r0z * (u1z - u2z)
    q4 = 4.0 * math.pi * d
    K = N / q4
    out[0] = cx * K; out[1] = cy * K; out[2] = cz * K
    p1 = r0x * u1x + r0y * u1y + r0z * u1z
    p2 = r0x * u2x + r0y * u2y + r0z * u2z
    gNx = (r0x - p1 * u1x) / n1 - (r0x - p2 * u2x) / n2
    gNy = (r0y - p1 * u1y) / n1 - (r0y - p2 * u2y) / n2
    gNz = (r0z - p1 * u1z) / n1 - (r0z - p2 * u2z) / n2
    gdx = 2.0 * (cy * r0z - cz * r0y); gdy = 2.0 * (cz * r0x - cx * r0z); gdz = 2.0 * (cx * r0y - cy * r0x)
    gKx = gNx / q4 - K * gdx / d; gKy = gNy / q4 - K * gdy / d; gKz = gNz / q4 - K * gdz / d
    out[3] = cx * gKx;              out[4] = -K * r0z + cx * gKy;   out[5] = K * r0y + cx * gKz
    out[6] = K * r0z + cy * gKx;    out[7] = cy * gKy;              out[8] = -K * r0x + cy * gKz
    out[9] = -K * r0y + cz * gKx;   out[10] = K * r0x + cz * gKy;   out[11] = cz * gKz


@njit(cache=True, parallel=True, fastmath=True)
def _soma_grad_par(P, A, B, G, rc):
    n, m = P.shape[0], A.shape[0]
    u = np.zeros((n, 3))
    g = np.zeros((n, 3, 3))
    for i in prange(n):
        o = np.empty(12)
        acc = np.zeros(12)
        for j in range(m):
            _bs_grad(P[i, 0], P[i, 1], P[i, 2], A[j, 0], A[j, 1], A[j, 2], B[j, 0], B[j, 1], B[j, 2], rc, o)
            for q in range(12):
                acc[q] += G[j] * o[q]
        u[i, 0] = acc[0]; u[i, 1] = acc[1]; u[i, 2] = acc[2]
        for k in range(3):
            for l in range(3):
                g[i, k, l] = acc[3 + 3 * k + l]
    return u, g


@njit(cache=True, fastmath=True)
def _soma_grad_seq(P, A, B, G, rc):
    n, m = P.shape[0], A.shape[0]
    u = np.zeros((n, 3))
    g = np.zeros((n, 3, 3))
    o = np.empty(12)
    acc = np.zeros(12)
    for i in range(n):
        for q in range(12):
            acc[q] = 0.0
        for j in range(m):
            _bs_grad(P[i, 0], P[i, 1], P[i, 2], A[j, 0], A[j, 1], A[j, 2], B[j, 0], B[j, 1], B[j, 2], rc, o)
            for q in range(12):
                acc[q] += G[j] * o[q]
        u[i, 0] = acc[0]; u[i, 1] = acc[1]; u[i, 2] = acc[2]
        for k in range(3):
            for l in range(3):
                g[i, k, l] = acc[3 + 3 * k + l]
    return u, g


def _vel_grad_segmentos(P, A, B, G, rc):
    P = np.ascontiguousarray(P, dtype=np.float64)
    if not len(A) or not len(P):
        return np.zeros((len(P), 3)), np.zeros((len(P), 3, 3))
    f = _soma_grad_par if P.shape[0] * A.shape[0] >= _MIN_PARALELO // 4 else _soma_grad_seq
    return f(P, np.ascontiguousarray(A, dtype=np.float64), np.ascontiguousarray(B, dtype=np.float64),
             np.ascontiguousarray(G, dtype=np.float64), float(rc))


_MIN_PARALELO = 400_000


def _vel_segmentos(P, A, B, G, rc):
    P = np.ascontiguousarray(P, dtype=np.float64)
    f = _soma_par if P.shape[0] * A.shape[0] >= _MIN_PARALELO else _soma_seq
    return f(P, np.ascontiguousarray(A, dtype=np.float64), np.ascontiguousarray(B, dtype=np.float64),
             np.ascontiguousarray(G, dtype=np.float64), float(rc))


def _malha(nos, G):
    r, c = G.shape
    Gp = np.zeros((r + 2, c + 2))
    Gp[1:-1, 1:-1] = G
    gv = Gp[1:, 1:-1] - Gp[:-1, 1:-1]
    gc = Gp[1:-1, :-1] - Gp[1:-1, 1:]
    A = np.concatenate([nos[:, :-1].reshape(-1, 3), nos[:-1, :].reshape(-1, 3)])
    B = np.concatenate([nos[:, 1:].reshape(-1, 3), nos[1:, :].reshape(-1, 3)])
    return A, B, np.concatenate([gv.ravel(), gc.ravel()])


@dataclass
class Historico:
    t: list = field(default_factory=list)
    CL: list = field(default_factory=list)
    CD: list = field(default_factory=list)
    Cm: list = field(default_factory=list)
    F: list = field(default_factory=list)


class Solo:

    def __init__(self, altura, alpha_rad: float, x_ref: float = 0.0, z_ref: float = 0.0):
        self.altura = altura
        self.n = np.array([-math.sin(alpha_rad), 0.0, math.cos(alpha_rad)])
        self.P0 = np.array([x_ref, 0.0, z_ref])
        self.z_ref = float(z_ref)
        self.t = 0.0
        self.variavel = callable(altura)

    def h(self, t: float | None = None) -> float:
        t = self.t if t is None else t
        return float(self.altura(t)) if self.variavel else float(self.altura)

    def hdot(self, t: float) -> float:
        if not self.variavel:
            return 0.0
        e = 1e-6
        return (float(self.altura(t + e)) - float(self.altura(t - e))) / (2 * e)

    def dist(self, P, t: float | None = None):
        return (np.asarray(P) - self.P0) @ self.n + self.h(t) + self.z_ref

    def reflete(self, P, t: float | None = None):
        P = np.asarray(P, float)
        return P - 2.0 * self.dist(P, t)[..., None] * self.n

    def vetor(self, V):
        V = np.asarray(V, float)
        return V - 2.0 * (V @ self.n)[..., None] * self.n

    def segmentos(self, seg, t: float | None = None):
        A, B, G = seg
        return np.ascontiguousarray(self.reflete(A, t)), np.ascontiguousarray(self.reflete(B, t)), -np.asarray(G)

    def afasta(self, P, d_min: float, t: float | None = None):
        d = self.dist(P, t)
        k = d < d_min
        if np.any(k):
            P = P.copy()
            P[k] += (d_min - d[k])[:, None] * self.n
        return P

    def plano(self, t: float | None = None) -> dict:
        return {"p0": (self.P0 - (self.h(t) + self.z_ref) * self.n).tolist(), "n": self.n.tolist()}


class UVLM:

    def __init__(self, superficies: list[Superficie], V: float, alpha_graus: float = 0.0, rho: float = 1.225,
                 dt: float | None = None, esteira_livre: bool = True, nucleo: float = 0.002, x_ref: float = 0.0, z_ref: float = 0.0,
                 movimento=None, rajada=None, fracao_esteira: float = 0.3,
                 max_fileiras: int | None = None, fileiras_livres: int | None = 40,
                 teto_cache_mb: float = 250.0, solo=None):
        self.vlm = VLM(superficies, x_ref=x_ref, z_ref=z_ref)
        v = self.vlm
        self.V, self.rho, self.alpha = float(V), float(rho), math.radians(alpha_graus)
        self.Vinf = self.V * np.array([math.cos(self.alpha), 0.0, math.sin(self.alpha)])
        self.dt = float(dt) if dt else v.c_ref / (4.0 * self.V)
        self.livre, self.rc = esteira_livre, float(nucleo) * v.c_ref
        self.movimento, self.rajada = movimento, rajada
        self.max_fileiras = int(max_fileiras) if max_fileiras else None
        self.fileiras_livres = int(fileiras_livres) if fileiras_livres else None
        self.R, self.cp, self.n = v.aneis.copy(), v.cps.copy(), v.normais.copy()
        self.N = v.N
        self.te = []
        for nome, f in v._fatias.items():
            i0 = f["inicio"] + (f["nc"] - 1) * f["ns"]
            idx = np.arange(i0, i0 + f["ns"])
            linha = np.vstack([self.R[idx, 3], self.R[idx[-1], 2][None]])
            linha1 = linha + float(fracao_esteira) * self.Vinf * self.dt
            Rs = self.R[f["inicio"]:f["inicio"] + f["nc"] * f["ns"]].reshape(f["nc"], f["ns"], 4, 3)
            grade = np.empty((f["nc"] + 1, f["ns"] + 1, 3))
            grade[:-1, :-1] = Rs[:, :, 0]; grade[:-1, -1] = Rs[:, -1, 1]; grade[-1, :-1] = Rs[-1, :, 3]; grade[-1, -1] = Rs[-1, -1, 2]
            self.te.append({"nome": nome, "idx": idx, "linha": linha, "linha1": linha1, "ns": f["ns"], "nc": f["nc"],
                            "fatia": slice(f["inicio"], f["inicio"] + f["nc"] * f["ns"]), "grade": grade,
                            "nos": [linha.copy()], "G": []})
        self.solo = Solo(solo, self.alpha, x_ref, z_ref) if solo is not None else None
        if self.solo is not None:
            if np.any(self.solo.dist(self.R.reshape(-1, 3)) <= 0):
                raise ValueError("Efeito solo: parte da aeronave fica abaixo do chão nessa altura e ângulo.")
            if self.solo.variavel and not esteira_livre:
                raise ValueError("Efeito solo com altura variando pede esteira livre ou de partículas.")
        self._h_lu = None
        self._monta_lu()
        self.G = np.zeros(self.N)
        self.G_ant = np.zeros(self.N)
        self.t = 0.0
        self.h = Historico()
        self.x_ref, self.z_ref = float(x_ref), float(z_ref)
        self._area = 0.5 * np.linalg.norm(np.cross(self.R[:, 2] - self.R[:, 0], self.R[:, 3] - self.R[:, 1]), axis=1)
        self._centro = self.R.mean(axis=1)
        A, B, bf = [], [], []
        for s in self.te:
            a, b, _ = _malha(s["grade"], np.zeros((s["nc"], s["ns"])))
            m = np.zeros(len(a), bool); nv = (s["nc"] + 1) * s["ns"]; m[nv - s["ns"]:nv] = True
            A.append(a); B.append(b); bf.append(m)
        A, B = np.concatenate(A), np.concatenate(B)
        self._mid, self._dlb, self._bf = 0.5 * (A + B), B - A, np.concatenate(bf)
        self._cauda = 20.0 * v.b_ref * self.Vinf / self.V
        por_fileira = 8.0 * (self.N + 3 * len(self._mid)) * sum(t["ns"] for t in self.te)
        teto = float(teto_cache_mb) * 1e6
        self._k_cache = int(max(4, teto // max(por_fileira, 1.0)))
        self._cache = {}

    def _monta_lu(self):
        def aneis():
            yield self.R, None
            for s in self.te:
                a, b = s["linha"], s["linha1"]
                yield np.stack([a[:-1], a[1:], b[1:], b[:-1]], axis=1), s["idx"]
        Avec = np.zeros((self.N, self.N, 3))
        for R, idx in aneis():
            for sinal, RR in [(1.0, R)] + ([(-1.0, self.solo.reflete(R))] if self.solo is not None else []):
                for k in range(4):
                    v = sinal * _por_segmento_par(self.cp, np.ascontiguousarray(RR[:, k]), np.ascontiguousarray(RR[:, (k + 1) % 4]), self.rc)
                    if idx is None:
                        Avec += v
                    else:
                        Avec[:, idx] += v
        self._lu = lu_factor(np.einsum("ijk,ik->ij", Avec, self.n))
        self._h_lu = self.solo.h() if self.solo is not None else None

    def _vseg(self, P, seg, rc):
        if seg is None:
            return np.zeros_like(P)
        v = _vel_segmentos(P, *seg, rc)
        if self.solo is not None:
            v = v + _vel_segmentos(P, *self.solo.segmentos(seg), rc)
        return v

    def _vgseg(self, P, seg, rc):
        if seg is None:
            return np.zeros_like(P), np.zeros((len(P), 3, 3))
        u, g = _vel_grad_segmentos(P, *seg, rc)
        if self.solo is not None:
            ui, gi = _vel_grad_segmentos(P, *self.solo.segmentos(seg), rc)
            u, g = u + ui, g + gi
        return u, g

    def aneis_da_esteira(self, sem_primeira: bool = False):
        R, G = [], []
        for s in self.te:
            nos = s["nos"]
            for k in range(1 if sem_primeira else 0, len(s["G"])):
                a, b = nos[k], nos[k + 1]
                r = np.stack([a[:-1], a[1:], b[1:], b[:-1]], axis=1)
                R.append(r); G.append(s["G"][k])
        if not R:
            return np.zeros((0, 4, 3)), np.zeros(0)
        return np.concatenate(R), np.concatenate(G)

    def _segmentos(self, corpo: bool = True, esteira: bool = True, sem_primeira: bool = False):
        A, B, G = [], [], []
        for s in self.te:
            partes_n, partes_g = [], []
            if corpo:
                partes_n.append(s["grade"]); partes_g.append(self.G[s["fatia"]].reshape(s["nc"], s["ns"]))
            if esteira and s["G"]:
                k0 = 1 if sem_primeira else 0
                if len(s["G"]) > k0:
                    nos = np.array(s["nos"][k0:])
                    if corpo:
                        nos = nos[1:]
                    partes_n.append(nos); partes_g.append(np.array(s["G"][k0:]))
            if not partes_g:
                continue
            a, b, g = _malha(np.concatenate(partes_n), np.concatenate(partes_g))
            A.append(a); B.append(b); G.append(g)
        if not G:
            return None
        A, B, G = np.concatenate(A), np.concatenate(B), np.concatenate(G)
        k = G != 0.0
        return np.ascontiguousarray(A[k]), np.ascontiguousarray(B[k]), np.ascontiguousarray(G[k])

    def _induzida(self, P, **kw):
        return self._vseg(P, self._segmentos(**kw), self.rc)

    def _vel_esteira(self, P, sem_primeira: bool = False):
        return self._induzida(P, corpo=False, sem_primeira=sem_primeira)

    def _fileira(self, si, k):
        s = self.te[si]
        ch = (si, k, bool(s.get("cortada")) and k == len(s["G"]) - 1)
        if ch not in self._cache:
            a, b = s["nos"][k], s["nos"][k + 1]
            r = np.stack([a[:-1], a[1:], b[1:], b[:-1]], axis=1)
            vc = sum(_por_segmento(self.cp, np.ascontiguousarray(r[:, e]), np.ascontiguousarray(r[:, (e + 1) % 4]), self.rc) for e in range(4))
            vm = sum(_por_segmento(self._mid, np.ascontiguousarray(r[:, e]), np.ascontiguousarray(r[:, (e + 1) % 4]), self.rc) for e in range(4))
            if self.solo is not None:
                ri = self.solo.reflete(r)
                vc = vc - sum(_por_segmento(self.cp, np.ascontiguousarray(ri[:, e]), np.ascontiguousarray(ri[:, (e + 1) % 4]), self.rc) for e in range(4))
                vm = vm - sum(_por_segmento(self._mid, np.ascontiguousarray(ri[:, e]), np.ascontiguousarray(ri[:, (e + 1) % 4]), self.rc) for e in range(4))
            self._cache[ch] = (np.einsum("ijk,ik->ij", vc, self.n), vm)
        return self._cache[ch]

    def _esteira_rigida(self, onde: str, k0: int = 0):
        out = np.zeros(self.N) if onde == "cp" else np.zeros_like(self._mid)
        j = 0 if onde == "cp" else 1
        A, B, G = [], [], []
        for si, s in enumerate(self.te):
            K = max(k0, min(len(s["G"]), self._k_cache))
            for k in range(k0, K):
                M = self._fileira(si, k)[j]
                out += M @ s["G"][k] if j == 0 else np.einsum("ijk,j->ik", M, s["G"][k])
            if len(s["G"]) > K:
                a, b, g = _malha(np.array(s["nos"][K:]), np.array(s["G"][K:]))
                A.append(a); B.append(b); G.append(g)
        if G:
            P = self.cp if j == 0 else self._mid
            v = self._vseg(P, (np.concatenate(A), np.concatenate(B), np.concatenate(G)), self.rc)
            out += np.einsum("ij,ij->i", v, self.n) if j == 0 else v
        return out

    def _ar(self, P, t):
        v = np.broadcast_to(self.Vinf, P.shape).copy()
        if self.rajada is not None:
            v += self.rajada(t, P)
        if self.solo is not None and self.solo.variavel:
            v -= self.solo.hdot(t) * self.solo.n
        return v

    def _convecta(self, t):
        velhos = [np.array(s["nos"][1:]) for s in self.te]
        tam = [v.shape[0] * v.shape[1] if v.size else 0 for v in velhos]
        if sum(tam):
            Pw = np.concatenate([v.reshape(-1, 3) for v in velhos if v.size])
            vel = self._ar(Pw, t) if self.livre else np.broadcast_to(self.Vinf, Pw.shape)
            if self.livre:
                if self.fileiras_livres:
                    m = np.concatenate([np.repeat(np.arange(v.shape[0]) < self.fileiras_livres, v.shape[1]) for v in velhos if v.size])
                    vel[m] += self._induzida(Pw[m])
                else:
                    vel = vel + self._induzida(Pw)
            Pn = Pw + vel * self.dt
            if self.solo is not None:
                Pn = self.solo.afasta(Pn, 0.01 * self.vlm.c_ref, t + self.dt)
        j = 0
        for s, v, n in zip(self.te, velhos, tam):
            novos = []
            if n:
                novos = list(Pn[j:j + n].reshape(v.shape)); j += n
            s["nos"] = [s["linha"].copy(), s["linha1"].copy()] + novos
            s["G"] = [np.zeros(s["ns"])] + s["G"]
            if self.max_fileiras and len(s["G"]) > self.max_fileiras:
                s["G"] = s["G"][:self.max_fileiras]
                s["nos"] = s["nos"][:self.max_fileiras + 1]
                s["nos"][-1] = s["nos"][-2] + self._cauda
                s["cortada"] = True

    def passo(self):
        t = self._prepara_passo()
        self._resolve_G(t)
        return self._registra(t)

    def _prepara_passo(self) -> float:
        t = self.t + self.dt
        if self.solo is not None:
            self.solo.t = self.t
        self._convecta(self.t)
        if self.solo is not None:
            self.solo.t = t
            if self.solo.variavel and self.solo.h() != self._h_lu:
                if np.any(self.solo.dist(self.R.reshape(-1, 3)) <= 0):
                    raise ValueError(f"Efeito solo: em t = {t:.3f} s a aeronave encostou no chão (h = {self.solo.h():.3f} m).")
                self._monta_lu()
        self.G_ant = self.G.copy()
        return t

    def _resolve_G(self, t: float) -> None:
        P = self.cp
        v_rel = self._ar(P, t)
        if getattr(self, "so_perturbacao", False):
            v_rel = v_rel - self.Vinf
        if self.livre:
            v_rel = v_rel + self._vel_esteira(P, sem_primeira=True)
        if self.movimento is not None:
            v_rel -= self.movimento(t, P)
        vn = np.einsum("ij,ij->i", v_rel, self.n)
        if not self.livre:
            vn = vn + self._esteira_rigida("cp", 1)
        self.G = lu_solve(self._lu, -vn)
        for s in self.te:
            s["G"][0] = self.G[s["idx"]].copy()

    def _registra(self, t: float):
        F, M = self._forcas(t)
        self.t = t
        v = self.vlm
        q = 0.5 * self.rho * self.V ** 2
        ed = self.Vinf / self.V
        el = np.array([-math.sin(self.alpha), 0.0, math.cos(self.alpha)])
        L, D = float(F @ el), float(F @ ed)
        h = self.h
        h.t.append(t); h.F.append(F)
        h.CL.append(L / (q * v.S_ref)); h.CD.append(D / (q * v.S_ref)); h.Cm.append(float(M[1]) / (q * v.S_ref * v.c_ref))
        return h.CL[-1]

    def forcas_distribuidas(self, t: float):
        G = np.concatenate([_malha(s["grade"], self.G[s["fatia"]].reshape(s["nc"], s["ns"]))[2] for s in self.te])
        G[self._bf] = 0.0
        meio, dl = self._mid, self._dlb
        if getattr(self, "so_perturbacao", False):
            vloc = self._ar(meio, t)
        elif self.livre:
            vloc = self._ar(meio, t) + self._induzida(meio)
        else:
            vloc = self._ar(meio, t) + self._induzida(meio, esteira=False) + self._esteira_rigida("mid", 0)
        if self.movimento is not None and not getattr(self, "so_perturbacao", False):
            vloc -= self.movimento(t, meio)
        Fseg = self.rho * G[:, None] * np.cross(vloc, dl)
        dG = (self.G - self.G_ant) / self.dt
        Fn = self.rho * (dG * self._area)[:, None] * self.n
        return meio, Fseg, self._centro, Fn

    def _forcas(self, t):
        meio, Fseg, centro, Fn = self.forcas_distribuidas(t)
        ref = np.array([self.x_ref, 0.0, self.z_ref])
        F = Fseg.sum(axis=0) + Fn.sum(axis=0)
        M = np.cross(meio - ref, Fseg).sum(axis=0) + np.cross(centro - ref, Fn).sum(axis=0)
        return F, M

    def roda(self, n_passos: int, a_cada: int | None = None, guarda: list | None = None):
        for k in range(int(n_passos)):
            self.passo()
            if a_cada and guarda is not None and (k % a_cada == 0 or k == n_passos - 1):
                guarda.append(self.instantaneo())
        return self.h

    def instantaneo(self) -> dict:
        d = {"t": self.t, "CL": self.h.CL[-1] if self.h.CL else 0.0,
             "aneis": [np.array(s["nos"][:-1] if s.get("cortada") else s["nos"]) for s in self.te]}
        if getattr(self, "part", None) is not None and len(self.part):
            d["X"] = self.part.X.copy(); d["w"] = np.linalg.norm(self.part.A, axis=1)
        if self.solo is not None:
            d["solo"] = self.solo.plano()
        return d


class UVLMParticulas(UVLM):

    def __init__(self, superficies, V, *a, fileiras_aneis: int = 3, nucleo_particula: str = "gaussiano",
                 nu: float = 1.5e-5, sobreposicao: float = 1.3, max_idade: int | None = None,
                 idade_fusao: int | None = 8, **kw):
        from .vpm import Particulas
        kw["esteira_livre"] = True
        kw["max_fileiras"] = None
        kw["fileiras_livres"] = None
        super().__init__(superficies, V, *a, **kw)
        self.K = max(2, int(fileiras_aneis))
        self.part = Particulas(nucleo_particula, nu)
        self.part.espelho = self.solo
        self.sobre = float(sobreposicao)
        self.max_idade = int(max_idade) if max_idade else None
        self.idade_fusao = int(idade_fusao) if idade_fusao else None
        self._passo = 0

    def _induzida(self, P, corpo: bool = True, esteira: bool = True, sem_primeira: bool = False):
        v = super()._induzida(P, corpo=corpo, esteira=esteira, sem_primeira=sem_primeira)
        if esteira and len(self.part):
            v = v + self.part.velocidade(P)[0]
        return v

    def _aneis(self, P, rc=None):
        return self._vseg(P, self._segmentos(), self.rc if rc is None else rc)

    def _aneis_grad(self, P, rc):
        return self._vgseg(P, self._segmentos(), rc)

    def _segmentos(self, corpo: bool = True, esteira: bool = True, sem_primeira: bool = False):
        seg = super()._segmentos(corpo=corpo, esteira=esteira, sem_primeira=sem_primeira)
        if not esteira:
            return seg
        A, B, G = [], [], []
        for s in self.te:
            if s.get("Gb") is not None and len(s["G"]) > (1 if sem_primeira else 0):
                L = s["nos"][len(s["G"])]
                A.append(L[:-1]); B.append(L[1:]); G.append(s["Gb"])
        if not G:
            return seg
        A, B, G = np.concatenate(A), np.concatenate(B), np.concatenate(G)
        if seg is not None:
            A, B, G = np.concatenate([seg[0], A]), np.concatenate([seg[1], B]), np.concatenate([seg[2], G])
        return np.ascontiguousarray(A), np.ascontiguousarray(B), np.ascontiguousarray(G)

    def _converte(self, si, s):
        k = len(s["G"]) - 1
        a, b, Gk = s["nos"][k], s["nos"][k + 1], np.asarray(s["G"][k], float)
        A, B, g = _malha(np.array([a, b]), Gk[None, :])
        ns = s["ns"]
        Gb = s.get("Gb")
        g = g.copy()
        g[ns:2 * ns] += (Gb if Gb is not None else 0.0)
        sel = np.r_[np.arange(ns, 2 * ns), np.arange(2 * ns, len(g))]
        meio, alpha = 0.5 * (A[sel] + B[sel]), g[sel, None] * (B[sel] - A[sel])
        ok = np.linalg.norm(alpha, axis=1) > 1e-14
        sigma = self.sobre * float(np.linalg.norm(self.Vinf)) * self.dt
        fila = si * 100000 + np.r_[np.arange(ns), 50000 + np.arange(len(g) - 2 * ns)]
        if ok.any():
            self.part.adiciona(meio[ok], alpha[ok], sigma, self._passo, fila[ok])
        s["Gb"] = Gk.copy()
        s["G"] = s["G"][:k]
        s["nos"] = s["nos"][:k + 1]

    def _convecta(self, t):
        n = len(self.part)
        if n:
            X = self.part.X
            rc = float(np.median(self.part.S))
            ua, ga = self._aneis_grad(X, rc)
            up, gp = self.part.velocidade(X, gradiente=True)
            u = self._ar(X, t) + ua + up
            g = gp + ga
        super()._convecta(t)
        if n:
            self.part.avanca(u, g, self.dt)
            if self.solo is not None:
                self.part.X = self.solo.afasta(self.part.X, 0.0, t + self.dt)
        self._passo += 1
        for si, s in enumerate(self.te):
            while len(s["G"]) > self.K:
                self._converte(si, s)
        if self.idade_fusao:
            self.part.funde(self._passo, self.idade_fusao)
        if self.max_idade and len(self.part):
            self.part.remove(self.part.nasc < self._passo - self.max_idade)

    def particulas(self):
        return {"X": self.part.X.copy(), "A": self.part.A.copy(), "S": self.part.S.copy()}


def wagner(s):
    s = np.asarray(s, float)
    return 1.0 - 0.165 * np.exp(-0.0455 * s) - 0.335 * np.exp(-0.3 * s)


def kussner(s):
    s = np.asarray(s, float)
    return 1.0 - 0.5 * np.exp(-0.13 * s) - 0.5 * np.exp(-s)


def theodorsen(k):
    from scipy.special import hankel2
    k = np.asarray(k, float)
    return hankel2(1, k) / (hankel2(1, k) + 1j * hankel2(0, k))


def movimento_mergulho(h0: float, f: float):
    w = 2 * math.pi * f

    def mov(t, P):
        v = np.zeros_like(P)
        v[:, 2] = h0 * w * math.cos(w * t)
        return v
    return mov


def movimento_arfagem(theta0_graus: float, f: float, x_eixo: float, V: float):
    th0, w = math.radians(theta0_graus), 2 * math.pi * f

    def mov(t, P):
        v = np.zeros_like(P)
        v[:, 2] = th0 * w * math.cos(w * t) * (x_eixo - P[:, 0]) - V * th0 * math.sin(w * t)
        return v
    return mov


def rajada_1_cos(w0: float, H: float, V: float, x0: float = 0.0):
    def raj(t, P):
        xg = V * t - (P[:, 0] - x0)
        v = np.zeros_like(P)
        dentro = (xg >= 0) & (xg <= H)
        v[dentro, 2] = 0.5 * w0 * (1.0 - np.cos(2 * math.pi * xg[dentro] / H))
        return v
    return raj


def rajada_degrau(w0: float, V: float, x0: float = 0.0):
    def raj(t, P):
        v = np.zeros_like(P)
        v[:, 2] = np.where(P[:, 0] - x0 < V * t, w0, 0.0)
        return v
    return raj


LIMITE_PASSOS = 600


def discretizacao_auto(caso: str, k: float | None = None, H_cordas: float | None = None, esteira_livre: bool = False,
                       tolerancia: float = 0.05, limite_passos: int = LIMITE_PASSOS, esteira: str | None = None) -> dict:
    d = {"n_span": (None, "recomendado pelo alongamento de cada superfície (24 se AR ≥ 4, 48 se AR ≥ 1)")}
    if caso in ("mergulho", "arfagem"):
        k = float(k or 0.0)
        nc = int(min(16, max(4, math.ceil(1.2 * k / tolerancia))))
        d["n_chord"] = (nc, f"massa aparente: erro ≈ 1,2 k / n_chord ≤ {100 * tolerancia:g} % com k = {k:.2f}"
                            + (" (limitado a 16)" if nc == 16 and 1.2 * k / 16 > tolerancia else ""))
        ppc = max(4, math.ceil(40 * k / math.pi))
        d["passos_por_corda"] = (ppc, "≥ 40 passos por ciclo (no mínimo 4 por corda)")
        d["ciclos"] = (3.0, "o 1º ciclo leva o transitório da partida; os 2 seguintes já são periódicos")
        passos_por_ciclo = ppc * math.pi / max(k, 1e-9)
        n = 3.0 * passos_por_ciclo
    elif caso == "rajada_degrau":
        d["n_chord"] = (8, "a frente da rajada passa ponto de controle por ponto de controle (4 painéis dão degraus de 20 %)")
        d["passos_por_corda"] = (16, "2 passos por painel na corda, para a frente da rajada")
        d["cordas"] = (20.0, "Küssner chega a 99 % em ~20 cordas")
        n = 20.0 * 16
    elif caso == "rajada_1cos":
        H = float(H_cordas or 25.0)
        d["n_chord"] = (4, "rajada longa e suave: o ΔCL converge com 4 painéis (o CL absoluto de perfil arqueado sai ~14 % baixo; a referência estacionária usa a mesma malha)")
        ppc = max(4, math.ceil(40 / H))
        d["passos_por_corda"] = (ppc, "≥ 40 passos ao longo da rajada (no mínimo 4 por corda)")
        d["cordas"] = (H + 10.0, "a rajada inteira mais 10 cordas para a esteira levar a resposta embora")
        n = (H + 10.0) * ppc
    else:
        d["n_chord"] = (4, "partida impulsiva: a resposta relativa (Wagner) converge com 4 painéis (o CL absoluto de perfil arqueado sai ~14 % baixo; a referência estacionária usa a mesma malha)")
        d["passos_por_corda"] = (4, "Wagner quase não depende do passo (dt = c/4V)")
        d["cordas"] = (20.0, "Wagner passa de 98 % em ~20 cordas")
        n = 20.0 * 4
    ppc = d["passos_por_corda"][0]
    if n > limite_passos:
        f = n / limite_passos
        novo = max(2, int(ppc / f))
        d["passos_por_corda"] = (novo, d["passos_por_corda"][1] + f"; reduzido de {ppc} para caber em {limite_passos} passos")
        ppc = novo
    esteira = esteira or ("livre" if esteira_livre else "rigida")
    if esteira == "particulas":
        d["fileiras_aneis"] = (3, "3 fileiras de anéis atrás do bordo de fuga (a 1ª é o Kutta); dali para trás, partículas. "
                                  "Com 2 a 3 fileiras o CL bate com a esteira de anéis a 0,1 %")
        d["idade_fusao"] = (8, "partículas da mesma linha de vórtice se juntam aos pares a cada 8·2ⁿ passos: o número cresce "
                               "com log₂ dos passos; o CL muda < 0,1 % (com 4: 1 %)")
        d["sobreposicao"] = (1.3, "núcleo σ = 1,3 V·dt: as filas de partículas de cada perna se sobrepõem e viram tubos de vorticidade")
        d["nucleo"] = (0.002, "núcleo dos anéis de 0,2 % da corda (nas partículas vale o σ delas)")
        return d
    if esteira_livre or esteira == "livre":
        d["max_fileiras"] = (int(min(80, 15 * ppc)), "15 cordas de esteira livre; o resto vira a cauda longa (custo ~ quadrado dos nós)")
        d["fileiras_livres"] = (int(min(40, 6 * ppc)), "6 cordas enrolando com a velocidade local; atrás disso a forma congela")
    else:
        d["max_fileiras"] = (int(min(300, 30 * ppc)), "30 cordas de esteira; depois disso a cauda longa fecha as pernas (erro < 1 %)")
        d["fileiras_livres"] = (None, "esteira rígida")
    d["nucleo"] = (0.002, "núcleo de 0,2 % da corda: casa com o VLM estacionário em 0,1 %")
    return d
