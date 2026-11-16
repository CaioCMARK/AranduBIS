from __future__ import annotations

import math

import numpy as np

from .bemt import MU_AR, Pa, _coef
from .uvlm import UVLM, UVLMParticulas, _malha, _vel_grad_segmentos, _vel_segmentos
from .vpm import Particulas


def converte_fileira(part: Particulas, a, b, Gk, Gb, sigma, passo: int, fila_base: int):
    A, B, g = _malha(np.array([a, b]), np.asarray(Gk, float)[None, :])
    ns = len(Gk)
    g = g.copy()
    if Gb is not None:
        g[ns:2 * ns] += Gb
    sel = np.r_[np.arange(ns, 2 * ns), np.arange(2 * ns, len(g))]
    meio, alpha = 0.5 * (A[sel] + B[sel]), g[sel, None] * (B[sel] - A[sel])
    sig = np.broadcast_to(np.asarray(sigma, float), (len(g),))[sel] if np.ndim(sigma) else np.full(len(sel), float(sigma))
    ok = np.linalg.norm(alpha, axis=1) > 1e-14
    fila = fila_base + np.r_[np.arange(ns), 50000 + np.arange(len(g) - 2 * ns)]
    if ok.any():
        part.adiciona(meio[ok], alpha[ok], sig[ok], passo, fila[ok])
    return np.asarray(Gk, float).copy()


class HeliceLinha:

    def __init__(self, pa: Pa, centro, rpm: float, eixo=(1.0, 0.0, 0.0), sentido: int = 1, n_el: int = 12,
                 dpsi_graus: float = 10.0, fileiras_aneis: int = 2, sobreposicao: float = 1.3, rho: float = 1.225,
                 nucleo_aneis: float = 0.02, relax: float = 0.5, iter_gamma: int = 40, id_base: int = 900000):
        self.pa, self.B = pa, int(pa.B)
        self.c0 = np.asarray(centro, float)
        e = np.asarray(eixo, float); self.ex = e / np.linalg.norm(e)
        aux = np.array([0.0, 0.0, 1.0]) if abs(self.ex[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
        self.e1 = np.cross(aux, self.ex); self.e1 /= np.linalg.norm(self.e1)
        self.e2 = np.cross(self.ex, self.e1)
        self.sentido = 1 if sentido >= 0 else -1
        self.Om = 2 * math.pi * rpm / 60.0
        self.rpm = float(rpm)
        self.dt = math.radians(dpsi_graus) / self.Om
        self.R = pa.R
        e_ = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n_el + 1)))
        self.r_b = (pa.r_cubo_R + (1 - pa.r_cubo_R) * e_) * pa.R
        self.r_m = 0.5 * (self.r_b[1:] + self.r_b[:-1]); self.dr = np.diff(self.r_b)
        x = self.r_m / pa.R
        self.c = np.interp(x, pa.r_R, pa.c_R) * pa.R
        self.beta = np.radians(np.interp(x, pa.r_R, pa.beta_graus))
        self.K = max(1, int(fileiras_aneis))
        self.sobre, self.rho, self.rc = float(sobreposicao), float(rho), float(nucleo_aneis) * pa.R
        self.relax, self.iter_gamma = float(relax), int(iter_gamma)
        self.psi = 0.0
        self.t = 0.0
        self.passo_n = 0
        self.id_base = int(id_base)
        self.pas = [{"nos": [self._linha(b)], "G": [], "Gb": None, "Gamma": np.zeros(n_el)} for b in range(self.B)]
        self.hist = {"t": [], "T": [], "Q": [], "P": []}
        self.ultimo = None
        self._pico = {}
        self.solo = None

    def _er(self, psi):
        return math.cos(psi) * self.e1 + math.sin(psi) * self.e2

    def _linha(self, b, psi=None):
        psi = self.psi if psi is None else psi
        pb = psi + 2 * math.pi * b / self.B
        return self.c0 + np.outer(self.r_b, self._er(pb))

    def omega(self):
        return -self.sentido * self.Om * self.ex

    def segmentos(self):
        A, B, G = [], [], []
        for p in self.pas:
            if p["G"]:
                a, b, g = _malha(np.array(p["nos"]), np.array(p["G"]))
                A.append(a); B.append(b); G.append(g)
                if p["Gb"] is not None:
                    L = p["nos"][len(p["G"])]
                    A.append(L[:-1]); B.append(L[1:]); G.append(p["Gb"])
        if not G:
            return None
        A, B, G = np.concatenate(A), np.concatenate(B), np.concatenate(G)
        k = G != 0
        return np.ascontiguousarray(A[k]), np.ascontiguousarray(B[k]), np.ascontiguousarray(G[k])

    def induzida(self, P, rc=None):
        seg = self.segmentos()
        P = np.atleast_2d(P)
        if seg is None:
            return np.zeros_like(P)
        rc = self.rc if rc is None else rc
        v = _vel_segmentos(P, *seg, rc)
        if self.solo is not None:
            v = v + _vel_segmentos(P, *self.solo.segmentos(seg), rc)
        return v

    def avanca_linhas(self, u_total):
        velhas = [np.array(p["nos"]) for p in self.pas]
        P = np.concatenate([v.reshape(-1, 3) for v in velhas])
        Pn = P + u_total(P) * self.dt
        if self.solo is not None:
            Pn = self.solo.afasta(Pn, 0.01 * self.R)
        j = 0
        self.psi += -self.sentido * self.Om * self.dt
        for bi, (p, v) in enumerate(zip(self.pas, velhas)):
            n = v.shape[0] * v.shape[1]
            novas = list(Pn[j:j + n].reshape(v.shape)); j += n
            p["nos"] = [self._linha(bi)] + novas
            p["G"] = [self.sentido * p["Gamma"]] + p["G"]
        self.t += self.dt
        self.passo_n += 1

    def _avalia(self, u):
        om = self.omega()
        Gn, saida = [], []
        n = len(self.r_m)
        for bi in range(self.B):
            mid = self._meio[bi]
            rel = u[bi * n:(bi + 1) * n] - np.cross(om, mid - self.c0)
            er = self._er(self.psi + 2 * math.pi * bi / self.B)
            em = np.cross(om / self.Om, er)
            Ua = rel @ self.ex
            Ut = -(rel @ em)
            phi = np.arctan2(Ua, Ut)
            W = np.hypot(Ua, Ut)
            alpha = np.degrees(self.beta - phi)
            Re = self.rho * W * self.c / MU_AR
            cl, cd = _coef(self.pa.perfil, alpha, Re)
            Gn.append(0.5 * W * self.c * cl)
            saida.append((phi, W, alpha, cl, cd))
        return Gn, saida

    def resolve_gamma(self, u_ext, tol: float = 1e-4):
        self._meio = [0.5 * (p["nos"][0][1:] + p["nos"][0][:-1]) for p in self.pas]
        M = np.concatenate(self._meio)
        ue = u_ext(M)
        w, res0 = self.relax, np.inf
        for it in range(self.iter_gamma):
            Gn, saida = self._avalia(ue + self.induzida(M))
            res = max(float(np.max(np.abs(g - p["Gamma"]))) for g, p in zip(Gn, self.pas))
            esc = max(1e-9, max(float(np.max(np.abs(g))) for g in Gn))
            if it == 0 and not any(np.any(p["Gamma"]) for p in self.pas):
                w_it = 1.0
            else:
                if res > res0:
                    w = max(0.05, 0.5 * w)
                w_it = w
            if res <= tol * esc:
                break
            for g, p in zip(Gn, self.pas):
                p["Gamma"] = p["Gamma"] + w_it * (g - p["Gamma"])
                p["G"][0] = self.sentido * p["Gamma"]
            res0 = res
        self.convergiu = res <= tol * esc
        self.iters = it + 1
        T = Q = 0.0
        for (phi, W, alpha, cl, cd) in saida:
            dT = 0.5 * self.rho * W ** 2 * self.c * (cl * np.cos(phi) - cd * np.sin(phi))
            dQ = 0.5 * self.rho * W ** 2 * self.c * (cl * np.sin(phi) + cd * np.cos(phi)) * self.r_m
            T += float(np.sum(dT * self.dr)); Q += float(np.sum(dQ * self.dr))
        self.ultimo = {"alpha": [s[2] for s in saida], "Gamma": [p["Gamma"].copy() for p in self.pas]}
        self.hist["t"].append(self.t); self.hist["T"].append(T); self.hist["Q"].append(Q); self.hist["P"].append(Q * self.Om)
        return T, Q

    def converte(self, part: Particulas, passo: int):
        for bi, p in enumerate(self.pas):
            while len(p["G"]) > self.K:
                k = len(p["G"]) - 1
                a, b = p["nos"][k], p["nos"][k + 1]
                desl = np.linalg.norm(b - a, axis=1)
                larg = np.linalg.norm(a[1:] - a[:-1], axis=1)
                ns = len(p["G"][k])
                sig_lat = self.sobre * np.maximum(desl, 1e-6)
                sig_tr = self.sobre * np.maximum(0.5 * (desl[1:] + desl[:-1]), 0.5 * larg)
                sig = np.r_[sig_tr, sig_tr, sig_lat]
                self._pico[(bi, passo)] = int(np.argmax(np.abs(p["G"][k])))
                p["Gb"] = converte_fileira(part, a, b, p["G"][k], p["Gb"], sig, passo, self.id_base + bi * 200000)
                p["G"] = p["G"][:k]
                p["nos"] = p["nos"][:k + 1]

    def rola(self, part: Particulas, passo: int, idade: float | None) -> int:
        if not idade or not len(part):
            return 0
        base, f = self.id_base, part.fila
        minha = (f >= base) & (f < base + self.B * 200000) & (part.nivel == 0) & (passo - part.nasc >= idade)
        idx = np.nonzero(minha)[0]
        if len(idx) < 2:
            return 0
        loc = f[idx] - base
        bi, r = loc // 200000, loc % 200000
        lat = r >= 50000
        j = np.where(lat, r - 50000, r)
        chave = bi * 10_000_000 + part.nasc[idx]
        tira = np.zeros(len(part), bool)
        for k in np.unique(chave):
            m = chave == k
            jp = self._pico.pop((int(k // 10_000_000), int(k % 10_000_000)), None)
            for grupo in self._grupos(idx[m], lat[m], j[m], part, jp):
                if len(grupo) < 1:
                    continue
                w = np.linalg.norm(part.A[grupo], axis=1)
                ws = w.sum()
                if ws <= 1e-300:
                    tira[grupo] = True
                    continue
                xc = (w[:, None] * part.X[grupo]).sum(0) / ws
                esp = math.sqrt(float((w * ((part.X[grupo] - xc) ** 2).sum(1)).sum() / ws))
                q = grupo[np.argmax(w)]
                part.X[q] = xc
                part.A[q] = part.A[grupo].sum(0)
                part.S[q] = max(float(part.S[grupo].max()), esp)
                part.nivel[q] = 1
                tira[grupo] = True
                tira[q] = False
        n = int(tira.sum())
        if n:
            part.remove(tira)
        return n

    @staticmethod
    def _grupos(g, lat, j, part, j_pico=None):
        out = []
        o = np.argsort(j[lat])
        gl, jl = g[lat][o], j[lat][o]
        if len(gl):
            if j_pico is not None:
                k = int(np.searchsorted(jl, j_pico + 1))
            else:
                a = part.A[gl]
                s = a @ a[-1]
                k = len(gl) - 1
                while k > 0 and s[k - 1] > 0:
                    k -= 1
            if k < len(gl):
                out.append(gl[k:])
            if k > 0:
                out.append(gl[:k])
        gr = g[~lat]
        if len(gr):
            out.append(gr)
        return out

    def media(self, voltas: float = 1.0) -> dict:
        n = max(1, int(round(voltas * 2 * math.pi / (self.Om * self.dt))))
        T = float(np.mean(self.hist["T"][-n:])); Q = float(np.mean(self.hist["Q"][-n:]))
        rps = self.rpm / 60.0; D = 2 * self.R
        P = Q * self.Om
        return {"T": T, "Q": Q, "P": P, "CT": T / (self.rho * rps ** 2 * D ** 4), "CP": P / (self.rho * rps ** 3 * D ** 5)}


def simula_isolada(pa: Pa, V: float, rpm: float, rho: float = 1.225, voltas: float = 6.0, dpsi_graus: float = 10.0,
                   n_el: int = 12, fileiras_aneis: int = 2, nucleo: str = "gaussiano", voltas_rolagem: float | None = 0.5,
                   relaxacao: float = 0.0, voltas_esteira: float | None = None, incidencia_graus: float = 0.0,
                   guarda_a_cada: int | None = None):
    h = HeliceLinha(pa, (0.0, 0.0, 0.0), rpm, n_el=n_el, dpsi_graus=dpsi_graus, fileiras_aneis=fileiras_aneis, rho=rho)
    a = math.radians(incidencia_graus)
    Vinf = V * np.array([math.cos(a), 0.0, math.sin(a)])
    part = Particulas(nucleo, nu=1.5e-5)
    inst = []
    por_volta = 360.0 / dpsi_graus
    idade_rola = voltas_rolagem * por_volta if voltas_rolagem else None
    v_ref = max(abs(V), h.Om * h.R)

    def u_ext(P):
        return Vinf + part.velocidade(P)[0]

    def u_tot(P):
        return u_ext(P) + h.induzida(P)

    n = int(math.ceil(voltas * por_volta))
    for k in range(n):
        passo_particulas(part, h, Vinf, k, v_ref, u_tot, relaxacao)
        h.resolve_gamma(u_ext)
        h.converte(part, k)
        h.rola(part, k, idade_rola)
        if voltas_esteira and len(part):
            velho = (k - part.nasc) > voltas_esteira * por_volta
            if velho.any():
                part.remove(velho)
        if guarda_a_cada and (k % guarda_a_cada == 0 or k == n - 1):
            inst.append({"t": h.t, "T": h.hist["T"][-1], "aneis": [np.array(p["nos"]) for p in h.pas],
                         "X": part.X.copy(), "w": np.linalg.norm(part.A, axis=1)})
    return h, part, inst


def gradiente_segmentos(h: "HeliceLinha", X, rc):
    seg = h.segmentos()
    if seg is None:
        return np.zeros((len(X), 3)), np.zeros((len(X), 3, 3))
    return _vel_grad_segmentos(X, *seg, rc)


def passo_particulas(part: Particulas, h: "HeliceLinha", Vinf, k, v_ref, u_tot, relaxacao, extra=None):
    if len(part):
        X = part.X
        rc = float(np.median(part.S))
        up, gp = part.velocidade(X, gradiente=True)
        ua, ga = gradiente_segmentos(h, X, rc)
        up = up + ua + Vinf; gp = gp + ga
        if extra is not None:
            ue, ge = extra(X, rc)
            up = up + ue; gp = gp + ge
    h.avanca_linhas(u_tot)
    if len(part):
        part.avanca(up, gp, h.dt, v_ref)
        if relaxacao > 0:
            part.relaxa(relaxacao)
        part.confere(v_ref, "esteira da hélice")


def discretizacao_auto() -> dict:
    return {"dpsi": (15.0, "≈ 24 subpassos por volta; o núcleo das partículas da hélice é proporcional ao arco do subpasso "
                           "e o sopro sai ~10 % fraco em quantidade de movimento com 15°, ~6 % com 10° (1ª ordem)"),
            "n_el": (12, "12 elementos em cosseno: a tração muda < 0,5 % com 20"),
            "voltas_rolagem": (0.5, "enrolamento de Betz (ponta + raiz) depois de meia volta: corta ~8× as partículas "
                                    "da esteira longe sem mudar a tração")}


ID_HELICE = 10_000_000


class UVLMHelice(UVLMParticulas):

    def __init__(self, superficies, V, helices, *a, dpsi_graus: float = 10.0, relaxacao: float = 0.0,
                 voltas_rolagem: float = 0.5, comprimento_esteira: float | None = None, **kw):
        super().__init__(superficies, V, *a, **kw)
        hs = list(helices)
        if not hs:
            raise ValueError("UVLMHelice sem hélice: use UVLMParticulas.")
        Om = [2 * math.pi * float(d["rpm"]) / 60.0 for d in hs]
        self.n_sub = max(1, int(round(self.dt * max(Om) / math.radians(dpsi_graus))))
        self.dt_sub = self.dt / self.n_sub
        self.helices = []
        for i, (d, om) in enumerate(zip(hs, Om)):
            self.helices.append(HeliceLinha(d["pa"], d["centro"], d["rpm"], eixo=d.get("eixo", (1.0, 0.0, 0.0)),
                                            sentido=d.get("sentido", 1), n_el=int(d.get("n_el", 12)),
                                            dpsi_graus=math.degrees(om * self.dt_sub),
                                            fileiras_aneis=int(d.get("fileiras_aneis", 2)), rho=self.rho,
                                            id_base=ID_HELICE * (i + 1)))
        self.relaxacao = float(relaxacao)
        for h in self.helices:
            h.solo = self.solo
            if self.solo is not None and np.any(self.solo.dist(np.array([p["nos"][0] for p in h.pas]).reshape(-1, 3)) <= 0):
                raise ValueError("Efeito solo: a hélice bate no chão nessa altura e ângulo.")
        self._idade_rola = [max(1.0, voltas_rolagem * 2 * math.pi / (om * self.dt_sub)) if voltas_rolagem else None
                            for om in Om]
        x_fim = float(self.R[..., 0].max()) + 0.5 * self.vlm.b_ref
        if comprimento_esteira is None:
            comprimento_esteira = max(x_fim - min(h.c0[0] for h in self.helices), 4 * max(h.R for h in self.helices))
        self.comprimento_esteira = float(comprimento_esteira)
        self._max_idade_h = int(math.ceil(self.comprimento_esteira / (self.V * self.dt_sub)))
        self._relogio = 0
        self.v_ref = max([self.V] + [h.Om * h.R for h in self.helices])
        self.hist_helice = [{"t": [], "T": [], "Q": [], "P": []} for _ in self.helices]
        self._quadros, self._q_cada = None, 1

    def _induzida(self, P, corpo: bool = True, esteira: bool = True, sem_primeira: bool = False):
        v = super()._induzida(P, corpo=corpo, esteira=esteira, sem_primeira=sem_primeira)
        if esteira:
            for h in self.helices:
                v = v + h.induzida(P)
        return v

    def _idade(self, fila):
        out = np.full(len(fila), float(self.idade_fusao * self.n_sub) if self.idade_fusao else 0.0)
        out[fila >= ID_HELICE] = 0.0
        return out

    def _subpasso(self, t, seg):
        part = self.part
        hs = self.helices
        if self.solo is not None:
            self.solo.t = t

        def asa(P, rc):
            return self._vseg(P, seg, rc)

        def helices_menos(P, i=None, rc=None):
            v = np.zeros_like(P)
            for k, o in enumerate(hs):
                if k != i:
                    v = v + o.induzida(P, rc)
            return v

        rc_h = max([self.rc] + [h.rc for h in hs])

        def u_tot(P):
            return (self._ar(P, t) + asa(P, rc_h) + helices_menos(P) +
                    (part.velocidade(P)[0] if len(part) else 0.0))

        n = len(part)
        if n:
            X = part.X
            rc = float(np.median(part.S))
            u, g = part.velocidade(X, gradiente=True)
            todos = [x for x in [seg] + [h.segmentos() for h in hs] if x is not None]
            if self.solo is not None:
                todos = todos + [self.solo.segmentos(x) for x in todos]
            if todos:
                uf, gf = _vel_grad_segmentos(X, *(np.concatenate([x[k] for x in todos]) for k in range(3)), rc)
                u = u + uf; g = g + gf
            u = u + self._ar(X, t)
        for h in hs:
            h.avanca_linhas(u_tot)
        if n:
            part.avanca(u, g, self.dt_sub, self.v_ref)
            if self.solo is not None:
                part.X = self.solo.afasta(part.X, 0.0)
            if self.relaxacao > 0:
                part.relaxa(self.relaxacao)
            part.confere(self.v_ref, "esteira da hélice")
        for i, h in enumerate(hs):
            def u_ext(P, i=i):
                return (self._ar(P, t) + asa(P, max(self.rc, hs[i].rc)) + helices_menos(P, i) +
                        (part.velocidade(P)[0] if len(part) else 0.0))
            h.resolve_gamma(u_ext)
            h.converte(part, self._relogio)
            h.rola(part, self._relogio, self._idade_rola[i])
        self._relogio += 1
        if self._quadros is not None and self._relogio % self._q_cada == 0:
            d = self.instantaneo()
            d["t"] = t + self.dt_sub
            self._quadros.append(d)
        part.funde(self._relogio, self._idade)
        if len(part):
            velho = (part.fila >= ID_HELICE) & (self._relogio - part.nasc > self._max_idade_h)
            if self.max_idade:
                velho |= (part.fila < ID_HELICE) & (self._relogio - part.nasc > self.max_idade * self.n_sub)
            if velho.any():
                part.remove(velho)

    def _convecta(self, t):
        seg = self._segmentos()
        for j in range(self.n_sub):
            self._subpasso(t + j * self.dt_sub, seg)
        if self.solo is not None:
            self.solo.t = t
        UVLM._convecta(self, t)
        self._passo = self._relogio
        for si, s in enumerate(self.te):
            while len(s["G"]) > self.K:
                self._converte(si, s)
        for hh, h in zip(self.hist_helice, self.helices):
            k = self.n_sub
            for c in ("T", "Q", "P"):
                hh[c].append(float(np.mean(h.hist[c][-k:])))
            hh["t"].append(self.t + self.dt)

    def roda(self, n_passos: int, a_cada: int | None = None, guarda: list | None = None):
        if a_cada and guarda is not None:
            n_q = max(1, int(math.ceil(n_passos / a_cada)))
            self._q_cada = max(1, int(round(n_passos * self.n_sub / n_q)))
            self._quadros = guarda
        try:
            for _ in range(int(n_passos)):
                self.passo()
        finally:
            self._quadros = None
        return self.h

    def instantaneo(self) -> dict:
        d = super().instantaneo()
        d["aneis"] = d["aneis"] + [np.array(p["nos"]) for h in self.helices for p in h.pas]
        d["pas"] = [np.array(p["nos"][0]) for h in self.helices for p in h.pas]
        d["T"] = [float(h.hist["T"][-1]) if h.hist["T"] else 0.0 for h in self.helices]
        return d
