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
        self.n_nos = 6 * len(self.idx)
        self.n = self.n_nos
        self._monta()
        self._restricoes()

    def _gl(self, no):
        i = self.idx[no]
        return np.arange(6 * i, 6 * i + 6)

    def _monta(self):
        mod = self.mod
        I, J, Vk, Vm = [], [], [], []
        self.locais = []
        self.liberadas = 0
        self._dono = {}
        preso = set()
        for no, graus in mod.spc.items():
            if any(g > 3 for g in graus):
                preso.add(no)
        for _, mestre, lista in mod.rigidos:
            preso.add(mestre); preso.update(lista)
        hospede = {}
        for eid, pid, ga, gb, v in mod.barras:
            p = mod.props[pid]; mat = mod.materiais[p["mat"]]
            pa, pb = np.array(mod.nos[ga]), np.array(mod.nos[gb])
            L, R = _eixos(pa, pb, np.array(v))
            T = np.kron(np.eye(4), R)
            kl = rigidez_local(mat["E"], mat["G"], p["A"], p["I1"], p["I2"], p["J"], L)
            ml = massa_local(mat["rho"] * p["A"] + p["nsm"], mat["rho"] * (p["I1"] + p["I2"]), L)
            gl = np.concatenate([self._gl(ga), self._gl(gb)])
            kg, mg = T.T @ kl @ T, T.T @ ml @ T
            livres = []
            for ponta, no in ((0, ga), (1, gb)):
                for d in mod.liberacoes.get((eid, ponta), ()):
                    livres.append((ponta, np.asarray(d, float)))
                jt = mod.juntas.get(no)
                if jt is None or (eid, ponta) in mod.liberacoes:
                    continue
                if no not in preso and no not in hospede:
                    hospede[no] = eid
                    continue
                ex = R[0]
                if jt[0] == "rotula":
                    dirs = [R[1], R[2]]
                else:
                    a = np.asarray(jt[1], float); a = a - float(a @ ex) * ex
                    dirs = [a / np.linalg.norm(a)] if np.linalg.norm(a) > 1e-3 else []
                for d in dirs:
                    livres.append((ponta, d))
            if livres:
                nf = len(livres)
                B = np.zeros((12, 12 + nf)); B[:, :12] = np.eye(12)
                for k, (ponta, d) in enumerate(livres):
                    B[3 + 6 * ponta:6 + 6 * ponta, 12 + k] = d
                for k, (ponta, _d) in enumerate(livres):
                    self._dono[self.n + k] = (ga, gb)[ponta]
                gl = np.concatenate([gl, np.arange(self.n, self.n + nf)])
                self.n += nf; self.liberadas += nf
                kg, mg = B.T @ kg @ B, B.T @ mg @ B
                T = T @ B
            r, c = np.meshgrid(gl, gl, indexing="ij")
            I.append(r.ravel()); J.append(c.ravel()); Vk.append(kg.ravel()); Vm.append(mg.ravel())
            self.locais.append((eid, gl, T, kl, L))
        from .casca import rigidez_global as _cascag
        self._massa_casca = []
        for eid, mat, t, ns in mod.cascas:
            m = mod.materiais[mat]
            P = np.array([mod.nos[k] for k in ns])
            if "E2" in m:
                kg, Tc = _cascag(P, m["E"], m["nu"], t, E2=m["E2"], G12=m["G"])
            else:
                kg, Tc = _cascag(P, m["E"], m["E"] / (2 * m["G"]) - 1, t)
            gl = np.concatenate([self._gl(k) for k in ns])
            r, c = np.meshgrid(gl, gl, indexing="ij")
            I.append(r.ravel()); J.append(c.ravel()); Vk.append(kg.ravel()); Vm.append(np.zeros(kg.size))
            area = 0.5 * np.linalg.norm(np.cross(P[2] - P[0], P[3] - P[1]))
            self._massa_casca += [(k, m["rho"] * t * area / 4.0) for k in ns]
        n = self.n
        self.K = sp.coo_matrix((np.concatenate(Vk), (np.concatenate(I), np.concatenate(J))), shape=(n, n)).tocsr() if I else sp.csr_matrix((n, n))
        self.M = sp.coo_matrix((np.concatenate(Vm), (np.concatenate(I), np.concatenate(J))), shape=(n, n)).tocsr() if I else sp.csr_matrix((n, n))
        d = np.zeros(n)
        for _, no, m in mod.massas:
            d[self._gl(no)[:3]] += m
        for no, m in self._massa_casca:
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
        for k in range(self.n_nos, n):
            T[k, k] = 1.0
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
            parcial = mod.rigidos_graus.get(no)
            if parcial is not None:
                arm = {0: ((4, r[2]), (5, -r[1])), 1: ((3, -r[2]), (5, r[0])), 2: ((3, r[1]), (4, -r[0]))}
                for k in range(6):
                    if k + 1 not in parcial:
                        T[g[k], g[k]] = 1.0
                        continue
                    T[g[k], gm[k]] = 1.0
                    for kk, v in arm.get(k, ()):
                        T[g[k], gm[kk]] = v
                continue
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
            parcial = mod.rigidos_graus.get(no)
            for gdl in graus:
                dono = no if parcial is not None and gdl not in parcial else alvo
                fixos.add(6 * self.idx[dono] + gdl - 1)
        self.nos_soltos = set()
        if mod.spc:
            pai = {no: no for no in mod.nos}
            def raiz(i):
                while pai[i] != i:
                    pai[i] = pai[pai[i]]; i = pai[i]
                return i
            for _e, _p, ga, gb, _v in mod.barras:
                pai[raiz(ga)] = raiz(gb)
            for _e, mestre, lista in mod.rigidos:
                for q in lista:
                    pai[raiz(q)] = raiz(mestre)
            for _e, _m, _t, ns in mod.cascas:
                for q in ns[1:]:
                    pai[raiz(q)] = raiz(ns[0])
            presos = {raiz(no) for no in mod.spc}
            soltos = {no for no in mod.nos if raiz(no) not in presos}
            self.nos_soltos = soltos
            for no in soltos:
                fixos.update(range(6 * self.idx[no], 6 * self.idx[no] + 6))
            fixos.update(k for k, no in self._dono.items() if no in soltos)
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
        if self.liberadas:
            self._confere_mecanismo()
            ur = spl.spsolve(self.Kr, fr)
        else:
            ur = spl.spsolve(self.Kr, fr)
        if not np.all(np.isfinite(ur)) or np.linalg.norm(self.Kr @ ur - fr) > 1e-6 * max(np.linalg.norm(fr), 1e-30):
            raise ValueError(self._msg_singular())
        u = self.T @ ur
        if self.liberadas:
            P = np.array(list(self.mod.nos.values())); tam = float(np.linalg.norm(P.max(0) - P.min(0))) or 1.0
            if float(np.abs(u[:self.n_nos].reshape(-1, 6)[:, :3]).max()) > 1e3 * tam:
                raise ValueError(self._msg_singular())
        saida = {"u": {no: u[6 * i:6 * i + 6] for no, i in self.idx.items()}}
        reac = self.K @ u - f
        saida["reacao_total"] = float(np.linalg.norm(f))
        ef = {}
        for eid, gl, T, kl, L in self.locais:
            ef[eid] = kl @ (T @ u[gl])
        saida["esforcos"] = ef
        saida["residuo_livres"] = float(np.linalg.norm(self.Kr @ ur - fr) / max(np.linalg.norm(fr), 1e-30))
        return saida

    def _confere_mecanismo(self):
        if getattr(self, "_mec_ok", False):
            return
        d = self.Kr.diagonal()
        if d.size == 0:
            return
        if np.any(d <= 0):
            raise ValueError(self._msg_singular())
        Dm = sp.diags(1.0 / np.sqrt(d))
        Ks = (Dm @ self.Kr @ Dm).tocsc()
        try:
            if Ks.shape[0] < 600:
                lam = float(sl.eigvalsh(Ks.toarray(), subset_by_index=[0, 0])[0])
            else:
                lam = float(spl.eigsh(Ks, k=1, sigma=0, which="LM", return_eigenvectors=False)[0])
        except (RuntimeError, spl.ArpackError, np.linalg.LinAlgError):
            raise ValueError(self._msg_singular()) from None
        if not np.isfinite(lam) or lam < 1e-12:
            raise ValueError(self._msg_singular())
        self._mec_ok = True

    def _msg_singular(self):
        if self.liberadas:
            return "mecanismo: com as juntas articuladas (parafuso ou rotula) a estrutura fica sem rigidez; volte alguma junta para solda, acrescente uma barra ou um apoio"
        return "modelo singular: faltam engastes ou ha mecanismo"

    def modos(self, n_modos=6):
        n = self.Kr.shape[0]
        if n < 1500:
            w2, V = sl.eigh(self.Kr.toarray(), self.Mr.toarray())
            w2, V = w2[:n_modos], V[:, :n_modos]
        else:
            w2, V = spl.eigsh(self.Kr, k=n_modos, M=self.Mr, sigma=0, which="LM")
            o = np.argsort(w2); w2, V = w2[o], V[:, o]
        f = np.sqrt(np.clip(w2, 0, None)) / (2 * np.pi)
        if self.liberadas and len(f) and f[0] < 1e-3:
            raise ValueError(self._msg_singular())
        formas = [self.T @ V[:, k] for k in range(V.shape[1])]
        return {"f_hz": f.tolist(), "formas": [{no: u[6 * i:6 * i + 6] for no, i in self.idx.items()} for u in formas]}
