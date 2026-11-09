from __future__ import annotations

import numpy as np
import scipy.linalg as sl
import scipy.sparse as sp
import scipy.sparse.linalg as spl

def _eixos(pa, pb, v):
    ex = pb - pa
    L = float(np.linalg.norm(ex))
    if L <= 0:
        raise ValueError("viga de comprimento nulo")
    ex = ex / L
    z = np.cross(ex, v)
    if np.linalg.norm(z) < 1e-9:
        raise ValueError("o vetor de orientacao da viga e paralelo ao seu eixo")
    z = z / np.linalg.norm(z)
    return L, np.array([ex, np.cross(z, ex), z])

def rigidez_local(E, G, A, Iz, Iy, J, L):
    k = np.zeros((12, 12))
    def liga(i, j, v):
        k[i, i] += v; k[j, j] += v; k[i, j] -= v; k[j, i] -= v
    liga(0, 6, E * A / L)
    liga(3, 9, G * J / L)
    for (v_, t_, I) in ((1, 5, Iz), (2, 4, Iy)):
        s = 1.0 if v_ == 1 else -1.0
        a, b, c, d = 12 * E * I / L ** 3, 6 * E * I / L ** 2, 4 * E * I / L, 2 * E * I / L
        vi, ti, vj, tj = v_, t_, v_ + 6, t_ + 6
        k[vi, vi] += a; k[vj, vj] += a; k[vi, vj] -= a; k[vj, vi] -= a
        k[vi, ti] += s * b; k[ti, vi] += s * b; k[vi, tj] += s * b; k[tj, vi] += s * b
        k[vj, ti] -= s * b; k[ti, vj] -= s * b; k[vj, tj] -= s * b; k[tj, vj] -= s * b
        k[ti, ti] += c; k[tj, tj] += c; k[ti, tj] += d; k[tj, ti] += d
    return k

def massa_local(rho_lin, rho_polar, L):
    m = np.zeros((12, 12))
    m[0, 0] = m[6, 6] = rho_lin * L / 3; m[0, 6] = m[6, 0] = rho_lin * L / 6
    m[3, 3] = m[9, 9] = rho_polar * L / 3; m[3, 9] = m[9, 3] = rho_polar * L / 6
    f = rho_lin * L / 420.0
    for v_, t_, s in ((1, 5, 1.0), (2, 4, -1.0)):
        idx = [v_, t_, v_ + 6, t_ + 6]
        b = f * np.array([[156, 22 * L, 54, -13 * L], [22 * L, 4 * L * L, 13 * L, -3 * L * L],
                          [54, 13 * L, 156, -22 * L], [-13 * L, -3 * L * L, -22 * L, 4 * L * L]])
        sg = np.diag([1, s, 1, s])
        b = sg @ b @ sg
        for i in range(4):
            for j in range(4):
                m[idx[i], idx[j]] += b[i, j]
    return m

class Sistema:
    def __init__(self, mod):
        self.mod = mod
        self.idx = mod.indice()
        self.n = 6 * len(self.idx)
        self._monta()
        self._restricoes()

    def _gl(self, no):
        i = self.idx[no]
        return np.arange(6 * i, 6 * i + 6)

    def _monta(self):
        mod = self.mod
        I, J, Vk, Vm = [], [], [], []
        self.locais = []
        for eid, pid, ga, gb, v in mod.barras:
            p = mod.props[pid]; mat = mod.materiais[p["mat"]]
            pa, pb = np.array(mod.nos[ga]), np.array(mod.nos[gb])
            L, R = _eixos(pa, pb, np.array(v))
            T = np.kron(np.eye(4), R)
            kl = rigidez_local(mat["E"], mat["G"], p["A"], p["I1"], p["I2"], p["J"], L)
            ml = massa_local(mat["rho"] * p["A"] + p["nsm"], mat["rho"] * (p["I1"] + p["I2"]), L)
            gl = np.concatenate([self._gl(ga), self._gl(gb)])
            kg, mg = T.T @ kl @ T, T.T @ ml @ T
            r, c = np.meshgrid(gl, gl, indexing="ij")
            I.append(r.ravel()); J.append(c.ravel()); Vk.append(kg.ravel()); Vm.append(mg.ravel())
            self.locais.append((eid, gl, T, kl, L))
        n = self.n
        self.K = sp.coo_matrix((np.concatenate(Vk), (np.concatenate(I), np.concatenate(J))), shape=(n, n)).tocsr() if I else sp.csr_matrix((n, n))
        self.M = sp.coo_matrix((np.concatenate(Vm), (np.concatenate(I), np.concatenate(J))), shape=(n, n)).tocsr() if I else sp.csr_matrix((n, n))
        d = np.zeros(n)
        for _, no, m in mod.massas:
            d[self._gl(no)[:3]] += m
        self.M = self.M + sp.diags(d)

    def _restricoes(self):
        mod, n = self.mod, self.n
        escravos = {}
        for _, mestre, lista in mod.rigidos:
            for s in lista:
                if s in escravos:
                    raise ValueError(f"o no {s} e escravo de duas ligacoes rigidas")
                escravos[s] = mestre
        T = sp.lil_matrix((n, n))
        for no, i in self.idx.items():
            g = np.arange(6 * i, 6 * i + 6)
            if no not in escravos:
                T[g, g] = 1.0
                continue
            m = escravos[no]
            while m in escravos:
                m = escravos[m]
            r = np.array(mod.nos[no]) - np.array(mod.nos[m])
            gm = self._gl(m)
            for k in range(6):
                T[g[k], gm[k]] = 1.0
            T[g[0], gm[4]] = r[2]; T[g[0], gm[5]] = -r[1]
            T[g[1], gm[3]] = -r[2]; T[g[1], gm[5]] = r[0]
            T[g[2], gm[3]] = r[1]; T[g[2], gm[4]] = -r[0]
        fixos = set()
        for no, graus in mod.spc.items():
            alvo = escravos.get(no, no)
            while alvo in escravos:
                alvo = escravos[alvo]
            for gdl in graus:
                fixos.add(6 * self.idx[alvo] + gdl - 1)
        livres_mestre = np.array([k for k in range(n) if k not in fixos])
        T = T.tocsr()
        usados = np.unique(T.nonzero()[1])
        usados = set(usados.tolist())
        self.livres = np.array([k for k in livres_mestre if k in usados])
        self.T = T[:, self.livres]
        self.Kr = (self.T.T @ self.K @ self.T).tocsc()
        self.Mr = (self.T.T @ self.M @ self.T).tocsc()

    def estatica(self, caso):
        f = np.zeros(self.n)
        for no, F in self.mod.cargas.get(caso, {}).items():
            f[self._gl(no)] += F
        if not self.mod.spc:
            raise ValueError("modelo sem engaste: a estatica precisa de ao menos um apoio (SPC1)")
        fr = self.T.T @ f
        ur = spl.spsolve(self.Kr, fr)
        if not np.all(np.isfinite(ur)) or np.linalg.norm(self.Kr @ ur - fr) > 1e-6 * max(np.linalg.norm(fr), 1e-30):
            raise ValueError("modelo singular: faltam engastes ou ha mecanismo")
        u = self.T @ ur
        saida = {"u": {no: u[6 * i:6 * i + 6] for no, i in self.idx.items()}}
        reac = self.K @ u - f
        saida["reacao_total"] = float(np.linalg.norm(f))
        ef = {}
        for eid, gl, T, kl, L in self.locais:
            ef[eid] = kl @ (T @ u[gl])
        saida["esforcos"] = ef
        saida["residuo_livres"] = float(np.linalg.norm((self.K @ u - f)[self.livres]) / max(np.linalg.norm(f), 1e-30))
        return saida

    def modos(self, n_modos=6):
        n = self.Kr.shape[0]
        if n < 1500:
            w2, V = sl.eigh(self.Kr.toarray(), self.Mr.toarray())
            w2, V = w2[:n_modos], V[:, :n_modos]
        else:
            w2, V = spl.eigsh(self.Kr, k=n_modos, M=self.Mr, sigma=0, which="LM")
            o = np.argsort(w2); w2, V = w2[o], V[:, o]
        f = np.sqrt(np.clip(w2, 0, None)) / (2 * np.pi)
        formas = [self.T @ V[:, k] for k in range(V.shape[1])]
        return {"f_hz": f.tolist(), "formas": [{no: u[6 * i:6 * i + 6] for no, i in self.idx.items()} for u in formas]}
