from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

try:
    import numba as _nb
    _NUMBA = True
except Exception:
    _nb = None; _NUMBA = False

if _NUMBA:
    @_nb.njit(cache=True)
    def _ptri_s(px, py, pz, ax, ay, az, bx, by, bz, cx, cy, cz):
        abx = bx - ax; aby = by - ay; abz = bz - az; acx = cx - ax; acy = cy - ay; acz = cz - az; apx = px - ax; apy = py - ay; apz = pz - az
        d1 = abx * apx + aby * apy + abz * apz; d2 = acx * apx + acy * apy + acz * apz
        if d1 <= 0.0 and d2 <= 0.0: return apx * apx + apy * apy + apz * apz, 1.0, 0.0, 0.0, 1
        bpx = px - bx; bpy = py - by; bpz = pz - bz; d3 = abx * bpx + aby * bpy + abz * bpz; d4 = acx * bpx + acy * bpy + acz * bpz
        if d3 >= 0.0 and d4 <= d3: return bpx * bpx + bpy * bpy + bpz * bpz, 0.0, 1.0, 0.0, 2
        vc = d1 * d4 - d3 * d2
        if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
            t = d1 / (d1 - d3); qx = apx - t * abx; qy = apy - t * aby; qz = apz - t * abz; return qx * qx + qy * qy + qz * qz, 1.0 - t, t, 0.0, 4
        cpx = px - cx; cpy = py - cy; cpz = pz - cz; d5 = abx * cpx + aby * cpy + abz * cpz; d6 = acx * cpx + acy * cpy + acz * cpz
        if d6 >= 0.0 and d5 <= d6: return cpx * cpx + cpy * cpy + cpz * cpz, 0.0, 0.0, 1.0, 3
        vb = d5 * d2 - d1 * d6
        if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
            t = d2 / (d2 - d6); qx = apx - t * acx; qy = apy - t * acy; qz = apz - t * acz; return qx * qx + qy * qy + qz * qz, 1.0 - t, 0.0, t, 5
        va = d3 * d6 - d5 * d4
        if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
            t = (d4 - d3) / ((d4 - d3) + (d5 - d6)); qx = bpx - t * (cx - bx); qy = bpy - t * (cy - by); qz = bpz - t * (cz - bz); return qx * qx + qy * qy + qz * qz, 0.0, 1.0 - t, t, 6
        den = 1.0 / (va + vb + vc); v = vb * den; w = vc * den; qx = apx - abx * v - acx * w; qy = apy - aby * v - acy * w; qz = apz - abz * v - acz * w
        return qx * qx + qy * qy + qz * qz, 1.0 - v - w, v, w, 0

    @_nb.njit(cache=True)
    def _constroi_bvh(tmin, tmax, cen, folha):
        T = len(cen); ordem = np.arange(T); nmax_nos = 4 * (T // max(folha, 1)) + 16; nmin = np.empty((nmax_nos, 3)); nmx = np.empty((nmax_nos, 3)); esq = -np.ones(nmax_nos, np.int64); ini = np.zeros(nmax_nos, np.int64); cnt = np.zeros(nmax_nos, np.int64)
        pilha = np.empty((256, 3), np.int64); pilha[0, 0] = 0; pilha[0, 1] = 0; pilha[0, 2] = T; sp = 1; nn = 1
        while sp > 0:
            sp -= 1; no = pilha[sp, 0]; i0 = pilha[sp, 1]; i1 = pilha[sp, 2]
            lo = np.full(3, np.inf); hi = np.full(3, -np.inf); clo = np.full(3, np.inf); chi = np.full(3, -np.inf)
            for j in range(i0, i1):
                t = ordem[j]
                for a in range(3):
                    lo[a] = min(lo[a], tmin[t, a]); hi[a] = max(hi[a], tmax[t, a]); clo[a] = min(clo[a], cen[t, a]); chi[a] = max(chi[a], cen[t, a])
            nmin[no] = lo; nmx[no] = hi; n = i1 - i0; eixo = 0; ext = chi[0] - clo[0]
            for a in range(1, 3):
                if chi[a] - clo[a] > ext: ext = chi[a] - clo[a]; eixo = a
            if n <= folha or ext <= 0.0:
                ini[no] = i0; cnt[no] = n; continue
            sub = ordem[i0:i1].copy(); chave = np.empty(n)
            for j in range(n): chave[j] = cen[sub[j], eixo]
            idx = np.argsort(chave)
            for j in range(n): ordem[i0 + j] = sub[idx[j]]
            meio = (i0 + i1) // 2; esq[no] = nn; l = nn; nn += 2
            pilha[sp, 0] = l + 1; pilha[sp, 1] = meio; pilha[sp, 2] = i1; sp += 1
            pilha[sp, 0] = l; pilha[sp, 1] = i0; pilha[sp, 2] = meio; sp += 1
        return nmin[:nn], nmx[:nn], esq[:nn], ini[:nn], cnt[:nn], ordem

    @_nb.njit(parallel=True, cache=True)
    def _consulta_bvh(P, A, B, C, nmin, nmax, esq, ini, cnt, ordem):
        N = len(P); d2 = np.empty(N); tri = np.empty(N, np.int64); U = np.empty(N); V = np.empty(N); W = np.empty(N); reg = np.empty(N, np.int64)
        for i in _nb.prange(N):
            px = P[i, 0]; py = P[i, 1]; pz = P[i, 2]; melhor = np.inf; bt = 0; bu = 0.0; bv = 0.0; bw = 0.0; br = 0; pilha = np.empty(128, np.int64); sp = 1; pilha[0] = 0
            while sp > 0:
                sp -= 1; no = pilha[sp]
                dx = max(nmin[no, 0] - px, 0.0, px - nmax[no, 0]); dy = max(nmin[no, 1] - py, 0.0, py - nmax[no, 1]); dz = max(nmin[no, 2] - pz, 0.0, pz - nmax[no, 2])
                if dx * dx + dy * dy + dz * dz >= melhor: continue
                if esq[no] < 0:
                    for j in range(ini[no], ini[no] + cnt[no]):
                        t = ordem[j]; dd, uu, vv, ww, rr = _ptri_s(px, py, pz, A[t, 0], A[t, 1], A[t, 2], B[t, 0], B[t, 1], B[t, 2], C[t, 0], C[t, 1], C[t, 2])
                        if dd < melhor: melhor = dd; bt = t; bu = uu; bv = vv; bw = ww; br = rr
                else:
                    l = esq[no]; r = l + 1
                    dxl = max(nmin[l, 0] - px, 0.0, px - nmax[l, 0]); dyl = max(nmin[l, 1] - py, 0.0, py - nmax[l, 1]); dzl = max(nmin[l, 2] - pz, 0.0, pz - nmax[l, 2])
                    dxr = max(nmin[r, 0] - px, 0.0, px - nmax[r, 0]); dyr = max(nmin[r, 1] - py, 0.0, py - nmax[r, 1]); dzr = max(nmin[r, 2] - pz, 0.0, pz - nmax[r, 2])
                    if dxl * dxl + dyl * dyl + dzl * dzl < dxr * dxr + dyr * dyr + dzr * dzr:
                        pilha[sp] = r; pilha[sp + 1] = l
                    else:
                        pilha[sp] = l; pilha[sp + 1] = r
                    sp += 2
            d2[i] = melhor; tri[i] = bt; U[i] = bu; V[i] = bv; W[i] = bw; reg[i] = br
        return d2, tri, U, V, W, reg

if _NUMBA:
    @_nb.njit(cache=True)
    def _agrega_dipolos(A, B, C, nmin, nmax, esq, ini, cnt, ordem):
        nn = len(esq); av = np.zeros((nn, 3)); cm = np.zeros((nn, 3)); ar = np.zeros(nn); rad = np.zeros(nn)
        for no in range(nn - 1, -1, -1):
            if esq[no] < 0:
                for j in range(ini[no], ini[no] + cnt[no]):
                    t = ordem[j]; ux = B[t, 0] - A[t, 0]; uy = B[t, 1] - A[t, 1]; uz = B[t, 2] - A[t, 2]; vx = C[t, 0] - A[t, 0]; vy = C[t, 1] - A[t, 1]; vz = C[t, 2] - A[t, 2]
                    nx = 0.5 * (uy * vz - uz * vy); ny = 0.5 * (uz * vx - ux * vz); nz = 0.5 * (ux * vy - uy * vx); a = np.sqrt(nx * nx + ny * ny + nz * nz)
                    av[no, 0] += nx; av[no, 1] += ny; av[no, 2] += nz; ar[no] += a
                    for k in range(3): cm[no, k] += a * (A[t, k] + B[t, k] + C[t, k]) / 3.0
            else:
                l = esq[no]; r = l + 1
                for k in range(3): av[no, k] = av[l, k] + av[r, k]; cm[no, k] = ar[l] * cm[l, k] + ar[r] * cm[r, k]
                ar[no] = ar[l] + ar[r]
            if ar[no] > 0.0:
                for k in range(3): cm[no, k] /= ar[no]
            else:
                for k in range(3): cm[no, k] = 0.5 * (nmin[no, k] + nmax[no, k])
        for no in range(nn):
            r2 = 0.0
            for cx in (nmin[no, 0], nmax[no, 0]):
                for cy in (nmin[no, 1], nmax[no, 1]):
                    for cz in (nmin[no, 2], nmax[no, 2]):
                        d2 = (cx - cm[no, 0]) ** 2 + (cy - cm[no, 1]) ** 2 + (cz - cm[no, 2]) ** 2; r2 = max(r2, d2)
            rad[no] = np.sqrt(r2)
        return av, cm, ar, rad

    @_nb.njit(parallel=True, cache=True)
    def _enrolamento_bvh(P, A, B, C, nmin, nmax, esq, ini, cnt, ordem, av, cm, rad, beta):
        N = len(P); w = np.zeros(N)
        for i in _nb.prange(N):
            px = P[i, 0]; py = P[i, 1]; pz = P[i, 2]; acc = 0.0; pilha = np.empty(128, np.int64); sp = 1; pilha[0] = 0
            while sp > 0:
                sp -= 1; no = pilha[sp]; rx = cm[no, 0] - px; ry = cm[no, 1] - py; rz = cm[no, 2] - pz; d2 = rx * rx + ry * ry + rz * rz
                if d2 > beta * beta * rad[no] * rad[no]:
                    acc += (av[no, 0] * rx + av[no, 1] * ry + av[no, 2] * rz) / (d2 * np.sqrt(d2)); continue
                if esq[no] < 0:
                    for j in range(ini[no], ini[no] + cnt[no]):
                        t = ordem[j]; ax = A[t, 0] - px; ay = A[t, 1] - py; az = A[t, 2] - pz; bx = B[t, 0] - px; by = B[t, 1] - py; bz = B[t, 2] - pz; cx = C[t, 0] - px; cy = C[t, 1] - py; cz = C[t, 2] - pz
                        la = np.sqrt(ax * ax + ay * ay + az * az); lb = np.sqrt(bx * bx + by * by + bz * bz); lc = np.sqrt(cx * cx + cy * cy + cz * cz)
                        det = ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
                        den = la * lb * lc + (ax * bx + ay * by + az * bz) * lc + (bx * cx + by * cy + bz * cz) * la + (cx * ax + cy * ay + cz * az) * lb
                        acc += 2.0 * np.arctan2(det, den)
                else:
                    pilha[sp] = esq[no]; pilha[sp + 1] = esq[no] + 1; sp += 2
            w[i] = acc / (4.0 * np.pi)
        return w

_BLOCO_AMOSTRA = 8_000_000

def _ptri(P, A, B, C):
    ab = B - A; ac = C - A; ap = P - A; d1 = np.einsum("ij,ij->i", ab, ap); d2 = np.einsum("ij,ij->i", ac, ap)
    bp = P - B; d3 = np.einsum("ij,ij->i", ab, bp); d4 = np.einsum("ij,ij->i", ac, bp); cp = P - C; d5 = np.einsum("ij,ij->i", ab, cp); d6 = np.einsum("ij,ij->i", ac, cp)
    vc = d1 * d4 - d3 * d2; vb = d5 * d2 - d1 * d6; va = d3 * d6 - d5 * d4; n = len(P)
    u = np.zeros(n); v = np.zeros(n); w = np.zeros(n); reg = np.zeros(n, int); fei = np.zeros(n, bool)
    def poe(m, r, uu, vv, ww):
        nonlocal fei
        m = m & ~fei
        if m.any(): reg[m] = r; u[m] = uu[m] if np.ndim(uu) else uu; v[m] = vv[m] if np.ndim(vv) else vv; w[m] = ww[m] if np.ndim(ww) else ww; fei = fei | m
    z = np.zeros(n); o = np.ones(n)
    poe((d1 <= 0) & (d2 <= 0), 1, o, z, z)
    poe((d3 >= 0) & (d4 <= d3), 2, z, o, z)
    t = d1 / np.where(d1 - d3 == 0, 1.0, d1 - d3); poe((vc <= 0) & (d1 >= 0) & (d3 <= 0), 4, 1 - t, t, z)
    poe((d6 >= 0) & (d5 <= d6), 3, z, z, o)
    t = d2 / np.where(d2 - d6 == 0, 1.0, d2 - d6); poe((vb <= 0) & (d2 >= 0) & (d6 <= 0), 5, 1 - t, z, t)
    den = (d4 - d3) + (d5 - d6); t = (d4 - d3) / np.where(den == 0, 1.0, den); poe((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), 6, z, 1 - t, t)
    s = va + vb + vc; s = np.where(s == 0, 1.0, s); poe(np.ones(n, bool), 0, 1 - vb / s - vc / s, vb / s, vc / s)
    Q = u[:, None] * A + v[:, None] * B + w[:, None] * C
    return Q, reg, (u, v, w)

class CorpoTriangulos:
    def __init__(self, V, T, simetria_y=False, tol_solda=1e-9, y_tol=1e-9, passo_busca=None, usar_bvh=True, threads=None, sinal="pseudo-normal", crease_graus=None):
        assert sinal in ("pseudo-normal", "enrolamento"), sinal
        self.n_aproximados = 0; self._usar_bvh = bool(usar_bvh and _NUMBA); self._bvh = None; self._threads = threads; self._modo_sinal = sinal; self._dip = None
        assert sinal == "pseudo-normal" or self._usar_bvh, "sinal por enrolamento: precisa de numba (BVH)"
        V = np.asarray(V, float); T = np.asarray(T, int)
        if simetria_y:
            cap = (np.abs(V[T][:, :, 1]) <= y_tol).all(axis=1); T = T[~cap]; Vm = V * np.array([1.0, -1.0, 1.0]); T = np.vstack([T, T[:, ::-1] + len(V)]); V = np.vstack([V, Vm])
        chave = np.round(V / tol_solda).astype(np.int64); _, idx, inv = np.unique(chave, axis=0, return_index=True, return_inverse=True); V = V[idx]; T = inv.reshape(-1)[T]
        a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]; nr = np.cross(b - a, c - a); area = 0.5 * np.linalg.norm(nr, axis=1); esc = float(np.ptp(V, axis=0).max())
        ok = (area > 1e-12 * esc * esc) & (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2]); T = T[ok]; a, b, c, nr, area = a[ok], b[ok], c[ok], nr[ok], area[ok]
        if np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) < 0: T = T[:, ::-1]; nr = -nr
        self.V = V; self.T = T; self.nf = nr / (2.0 * area)[:, None]; self.area = area; self.c = 0.5 * (V.min(0) + V.max(0)); self.escala = esc
        a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        nv = np.zeros((len(V), 3))
        for i, (p, q, r) in enumerate(((a, b, c), (b, c, a), (c, a, b))):
            e1 = q - p; e2 = r - p; ang = np.arccos(np.clip(np.einsum("ij,ij->i", e1, e2) / np.maximum(np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1), 1e-300), -1, 1)); np.add.at(nv, T[:, i], ang[:, None] * self.nf)
        self.nv = nv / np.maximum(np.linalg.norm(nv, axis=1), 1e-300)[:, None]
        self.crease_graus = crease_graus; self.nvc = None
        if crease_graus is not None: self.nvc = self._normais_de_canto(T, a, b, c, float(crease_graus))
        e = np.stack([T[:, [0, 1]], T[:, [0, 2]], T[:, [1, 2]]], axis=1)
        k = np.sort(e, axis=2); chave = k[:, :, 0].astype(np.int64) * len(V) + k[:, :, 1]; _, einv = np.unique(chave.reshape(-1), return_inverse=True); einv = einv.reshape(-1, 3)
        ne = np.zeros((einv.max() + 1, 3));
        for j in range(3): np.add.at(ne, einv[:, j], self.nf)
        self.ne = ne / np.maximum(np.linalg.norm(ne, axis=1), 1e-300)[:, None]; self.einv = einv
        self.n_arestas_borda = int(np.sum(np.bincount(einv.reshape(-1)) == 1)); self.fechado = self.n_arestas_borda == 0
        self._tri = (a, b, c); self._passo_busca = passo_busca; self._arv = None

    def _normais_de_canto(self, T, a, b, c, crease_graus):
        nT = len(T); cos_c = np.cos(np.radians(crease_graus)); nV = int(T.max()) + 1
        ang = np.zeros((nT, 3))
        for i, (p_, q_, r_) in enumerate(((a, b, c), (b, c, a), (c, a, b))):
            e1 = q_ - p_; e2 = r_ - p_; ang[:, i] = np.arccos(np.clip(np.einsum("ij,ij->i", e1, e2) / np.maximum(np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1), 1e-300), -1, 1))
        v_flat = T.reshape(-1); t_flat = np.repeat(np.arange(nT), 3); w_flat = ang.reshape(-1)
        ordem = np.argsort(v_flat, kind="stable"); v_s = v_flat[ordem]; inicio = np.searchsorted(v_s, np.arange(nV)); cont = np.bincount(v_flat, minlength=nV); kmax = int(cont.max())
        inc = np.full((nV, kmax), -1, np.int64); pw = np.zeros((nV, kmax)); pos = np.arange(len(v_s)) - inicio[v_s]
        inc[v_s, pos] = t_flat[ordem]; pw[v_s, pos] = w_flat[ordem]
        saida = np.zeros((nT, 3, 3))
        for i in range(3):
            v = T[:, i]; idx = inc[v]; ok = (idx >= 0)
            nfi = self.nf[np.where(ok, idx, 0)]; cos = np.einsum("tkj,tj->tk", nfi, self.nf)
            peso = pw[v] * (ok & (cos >= cos_c)); n = np.einsum("tk,tkj->tj", peso, nfi)
            saida[:, i] = n / np.maximum(np.linalg.norm(n, axis=1), 1e-300)[:, None]
        return saida

    def _prepara_kd(self):
        a, b, c = self._tri; ed = np.concatenate([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)])
        l_busca = self._passo_busca if self._passo_busca is not None else 1.0 * float(np.median(ed)); A_, B_, C_, pai = a, b, c, np.arange(len(self.T))
        for _ in range(12):
            lm = np.maximum.reduce([np.linalg.norm(B_ - A_, axis=1), np.linalg.norm(C_ - B_, axis=1), np.linalg.norm(A_ - C_, axis=1)]); g = lm > l_busca
            if not g.any(): break
            Ab, Bb, Cb, pb = A_[g], B_[g], C_[g], pai[g]; Mab = 0.5 * (Ab + Bb); Mbc = 0.5 * (Bb + Cb); Mca = 0.5 * (Cb + Ab)
            A_ = np.vstack([A_[~g], Ab, Mab, Mca, Mab]); B_ = np.vstack([B_[~g], Mab, Bb, Mbc, Mbc]); C_ = np.vstack([C_[~g], Mca, Mbc, Cb, Mca]); pai = np.concatenate([pai[~g], pb, pb, pb, pb])
        cen = (A_ + B_ + C_) / 3.0; self._arv = cKDTree(cen); self._pai = pai; self._rmax = float(np.max(np.maximum.reduce([np.linalg.norm(A_ - cen, axis=1), np.linalg.norm(B_ - cen, axis=1), np.linalg.norm(C_ - cen, axis=1)])))

    def proximo(self, X, k0=24, k_max=128, bloco=20000, avaliacoes_max=300_000, sinal=True):
        X = np.atleast_2d(np.asarray(X, float)); N = len(X); self.n_aproximados = 0
        if self._usar_bvh: return self._proximo_bvh(X, sinal)
        d = np.empty(N); Q = np.empty((N, 3)); nrm = np.empty((N, 3)); tri = np.empty(N, int)
        for i0 in range(0, N, bloco):
            sl = slice(i0, min(i0 + bloco, N)); r = self._consulta(X[sl], k0, k_max, avaliacoes_max); d[sl], Q[sl], nrm[sl], tri[sl] = r
        return (d if sinal else np.abs(d)), Q, nrm, tri

    def _consulta(self, P, k0, k_max, avaliacoes_max):
        if self._arv is None: self._prepara_kd()
        n = len(P); melhor_d = np.full(n, np.inf); melhor_Q = np.zeros((n, 3)); melhor_t = np.zeros(n, int); melhor_reg = np.zeros(n, int); melhor_b = np.zeros((n, 3)); pend = np.arange(n); k = k0; a, b, c = self._tri
        while len(pend):
            kk = min(k, len(self._pai)); passo = max(1, avaliacoes_max // kk); falhou = []
            for j0 in range(0, len(pend), passo):
                pp = pend[j0:j0 + passo]; D, I = self._arv.query(P[pp], k=kk); D = D.reshape(len(pp), -1); I = I.reshape(len(pp), -1); t = self._pai[I]; m, kq = t.shape
                Pr = np.repeat(P[pp], kq, axis=0); tf = t.reshape(-1); Q, reg, (u, v, w) = _ptri(Pr, a[tf], b[tf], c[tf]); dd = np.linalg.norm(Pr - Q, axis=1).reshape(m, kq); jj = np.argmin(dd, axis=1); ar = np.arange(m); idx = ar * kq + jj
                melhor_d[pp] = dd[ar, jj]; melhor_Q[pp] = Q[idx]; melhor_t[pp] = tf[idx]; melhor_reg[pp] = reg[idx]; melhor_b[pp] = np.stack([u[idx], v[idx], w[idx]], axis=1); falhou.append(pp[melhor_d[pp] + self._rmax > D[:, -1]])
            pend = np.concatenate(falhou) if falhou else np.empty(0, int)
            if kk >= len(self._pai): break
            if k >= k_max: self.n_aproximados += len(pend); break
            k = min(2 * k, k_max)
        return self._sinal_normal(P, melhor_d, melhor_Q, melhor_t, melhor_reg, melhor_b)

    def _garante_bvh(self):
        if self._bvh is None:
            a, b, c = self._tri; tmin = np.minimum(np.minimum(a, b), c); tmax = np.maximum(np.maximum(a, b), c); cen = (a + b + c) / 3.0
            self._bvh = _constroi_bvh(np.ascontiguousarray(tmin), np.ascontiguousarray(tmax), np.ascontiguousarray(cen), 4); self._tri_c = tuple(np.ascontiguousarray(v) for v in (a, b, c))
        if self._threads is not None: _nb.set_num_threads(int(self._threads))

    def enrolamento(self, X, beta=4.0):
        assert self._usar_bvh, "enrolamento: precisa de numba (BVH)"; self._garante_bvh(); A, B, C = self._tri_c; nmin, nmax, esq, ini, cnt, ordem = self._bvh
        if self._dip is None: self._dip = _agrega_dipolos(A, B, C, nmin, nmax, esq, ini, cnt, ordem)
        av, cm, ar, rad = self._dip; return _enrolamento_bvh(np.ascontiguousarray(np.atleast_2d(np.asarray(X, float))), A, B, C, nmin, nmax, esq, ini, cnt, ordem, av, cm, rad, float(beta))

    def _proximo_bvh(self, X, sinal=True):
        self._garante_bvh()
        A, B, C = self._tri_c; nmin, nmax, esq, ini, cnt, ordem = self._bvh; d2, t, u, v, w, reg = _consulta_bvh(np.ascontiguousarray(X), A, B, C, nmin, nmax, esq, ini, cnt, ordem)
        Q = u[:, None] * A[t] + v[:, None] * B[t] + w[:, None] * C[t]
        return self._sinal_normal(X, np.sqrt(d2), Q, t, reg, np.stack([u, v, w], axis=1), sinal)

    def _sinal_normal(self, P, melhor_d, melhor_Q, melhor_t, melhor_reg, melhor_b, sinal_pedido=True):
        T = self.T[melhor_t]; u, v, w = melhor_b[:, 0], melhor_b[:, 1], melhor_b[:, 2]; nvt = self.nvc[melhor_t] if self.nvc is not None else None; nph = (u[:, None] * nvt[:, 0] + v[:, None] * nvt[:, 1] + w[:, None] * nvt[:, 2]) if nvt is not None else (u[:, None] * self.nv[T[:, 0]] + v[:, None] * self.nv[T[:, 1]] + w[:, None] * self.nv[T[:, 2]]); nph /= np.maximum(np.linalg.norm(nph, axis=1), 1e-300)[:, None]
        if getattr(self, "normal_plana", False): nph = self.nf[melhor_t]
        if not sinal_pedido: return melhor_d, melhor_Q, nph, melhor_t
        npseudo = self.nf[melhor_t].copy(); reg = melhor_reg
        for r_, col in ((1, 0), (2, 1), (3, 2)):
            m_ = reg == r_
            if m_.any(): npseudo[m_] = self.nv[T[m_, col]]
        for r_, col in ((4, 0), (5, 1), (6, 2)):
            m_ = reg == r_
            if m_.any(): npseudo[m_] = self.ne[self.einv[melhor_t[m_], col]]
        sinal = np.where(np.einsum("ij,ij->i", P - melhor_Q, npseudo) >= 0.0, 1.0, -1.0)
        if self._modo_sinal == "enrolamento": sinal = np.where(self.enrolamento(P) > 0.5, -1.0, 1.0)
        return sinal * melhor_d, melhor_Q, nph, melhor_t

    def dist(self, X, **kw):
        return self.proximo(np.asarray(X, float).reshape(-1, 3), **kw)[0].reshape(np.shape(X)[:-1])

    def meia_espessura(self, Q, n, t_max, n_prof=22):
        Q = np.asarray(Q, float); n = np.asarray(n, float); h = np.zeros(len(Q))
        for j in range(n_prof): h = np.maximum(h, np.maximum(-self.dist(Q - (t_max * 2.0 ** (-0.5 * j)) * n), 0.0))
        return h

    def _amostra_triangulos(self, M, rng, y_min=None):
        a, b, c = self._tri; cum = np.cumsum(self.area); i = np.minimum(np.searchsorted(cum / cum[-1], rng.random(M)), len(self.area) - 1); r1 = np.sqrt(rng.random(M)); r2 = rng.random(M)
        P = (1 - r1)[:, None] * a[i] + (r1 * (1 - r2))[:, None] * b[i] + (r1 * r2)[:, None] * c[i]
        return P if y_min is None else P[P[:, 1] > y_min]

    def superficie(self, s, campo_s=None, y_min=None, n_it=15, semente=0, cand_por_semente=100, conjunto=0):
        rng = np.random.default_rng(semente); sf = (lambda P: np.full(len(P), float(s))) if campo_s is None else campo_s
        pre = self._amostra_triangulos(40000, rng, y_min); f = len(pre) / 40000.0; s_pre = sf(pre); n_esp = int(round(self.area.sum() * f * float(np.mean(1.0 / s_pre ** 2)) / (np.sqrt(3.0) / 2.0))); s_min = float(s_pre.min()); q = float(np.mean((s_min / s_pre) ** 2))

        def amostra(M):
            n_cru = int(1.1 * M / (q * f)) + 10
            if n_cru <= _BLOCO_AMOSTRA:
                P = self._amostra_triangulos(n_cru, rng, y_min)
                if campo_s is not None: P = P[rng.random(len(P)) < (s_min / sf(P)) ** 2]
                return P
            pedacos = []
            while n_cru > 0:
                P = self._amostra_triangulos(min(n_cru, _BLOCO_AMOSTRA), rng, y_min); n_cru -= _BLOCO_AMOSTRA
                if campo_s is not None: P = P[rng.random(len(P)) < (s_min / sf(P)) ** 2]
                pedacos.append(P)
            return np.vstack(pedacos)
        if conjunto and campo_s is not None:
            Pc = np.vstack([self._amostra_triangulos(min(conjunto - i_, _BLOCO_AMOSTRA), rng, y_min) for i_ in range(0, conjunto, _BLOCO_AMOSTRA)]); cum = np.cumsum(1.0 / sf(Pc) ** 2); cum /= cum[-1]
            amostra = lambda M: Pc[np.minimum(np.searchsorted(cum, rng.random(M)), len(Pc) - 1)]
        P = amostra(max(10 * n_esp, 2000)); seeds = P[rng.choice(len(P), size=min(n_esp, len(P)), replace=False)]
        for _ in range(n_it):
            P = amostra(max(cand_por_semente * len(seeds), 2000)); _, j = cKDTree(seeds).query(P); cont = np.bincount(j, minlength=len(seeds)); soma = np.stack([np.bincount(j, P[:, a_], len(seeds)) for a_ in range(3)], axis=1)
            novo = np.where(cont[:, None] > 0, soma / np.maximum(cont, 1)[:, None], seeds); seeds = self.proximo(novo)[1]
        d, Q, nrm, _ = self.proximo(seeds)
        if y_min is not None: k = Q[:, 1] > y_min; Q, nrm = Q[k], nrm[k]
        return Q, nrm
