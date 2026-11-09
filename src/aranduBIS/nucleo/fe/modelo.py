from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

@dataclass
class Modelo:
    nos: dict = field(default_factory=dict)
    materiais: dict = field(default_factory=dict)
    props: dict = field(default_factory=dict)
    barras: list = field(default_factory=list)
    massas: list = field(default_factory=list)
    rigidos: list = field(default_factory=list)
    spc: dict = field(default_factory=dict)
    cargas: dict = field(default_factory=dict)

    def no(self, i, x, y, z):
        self.nos[int(i)] = (float(x), float(y), float(z))

    def material(self, i, E, G=None, nu=0.3, rho=0.0):
        self.materiais[int(i)] = {"E": float(E), "G": float(G) if G else float(E) / (2 * (1 + nu)), "rho": float(rho)}

    def prop(self, i, mat, A, I1, I2, J, nsm=0.0):
        self.props[int(i)] = {"mat": int(mat), "A": float(A), "I1": float(I1), "I2": float(I2), "J": float(J), "nsm": float(nsm)}

    def barra(self, eid, pid, ga, gb, v):
        self.barras.append((int(eid), int(pid), int(ga), int(gb), tuple(float(a) for a in v)))

    def massa(self, eid, no, m):
        self.massas.append((int(eid), int(no), float(m)))

    def rigido(self, eid, mestre, escravos):
        self.rigidos.append((int(eid), int(mestre), [int(s) for s in escravos]))

    def engasta(self, nos, graus=(1, 2, 3, 4, 5, 6)):
        for n in nos:
            self.spc.setdefault(int(n), set()).update(int(g) for g in graus)

    def carga(self, caso, no, F):
        c = self.cargas.setdefault(int(caso), {})
        c[int(no)] = c.get(int(no), np.zeros(6)) + np.asarray(F, float)

    def indice(self):
        ids = sorted(self.nos)
        return {n: i for i, n in enumerate(ids)}

    def massa_total(self):
        m = sum(x[2] for x in self.massas)
        for _, pid, ga, gb, _v in self.barras:
            p = self.props[pid]; L = float(np.linalg.norm(np.array(self.nos[gb]) - np.array(self.nos[ga])))
            m += (self.materiais[p["mat"]]["rho"] * p["A"] + p["nsm"]) * L
        return m
