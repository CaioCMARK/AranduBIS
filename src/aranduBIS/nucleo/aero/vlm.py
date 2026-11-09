from __future__ import annotations

def _lido(nome, padrao):
    return padrao

import dataclasses
import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from .perfil import Perfil
from .planform import Planform

FRACAO_CORDA_MINIMA = 0.01

def n_span_recomendado(AR: float) -> int:
    if AR >= 4.0:
        return 24
    if AR >= 1.0:
        return 48
    if AR >= 0.5:
        return 96
    return 160

COND_MAXIMA = 1.0e5

def _velocidade_segmento(P, A, B, eps: float = 1e-10,
                         eps_rel: float = 1e-7, xp=np):
    r1 = P[:, None, :] - A[None, :, :]
    r2 = P[:, None, :] - B[None, :, :]
    cr = xp.cross(r1, r2)
    n2 = xp.einsum("...k,...k->...", cr, cr)
    n1 = xp.linalg.norm(r1, axis=-1)
    nn = xp.linalg.norm(r2, axis=-1)
    r0 = (B - A)[None, :, :]
    L = xp.linalg.norm(r0, axis=-1)
    K = xp.einsum("...k,...k->...", r0,
                  r1 / xp.maximum(n1, eps)[..., None] - r2 / xp.maximum(nn, eps)[..., None])
    v = cr / xp.maximum(n2, eps * eps)[..., None] * (K / (4.0 * np.pi))[..., None]
    h = xp.sqrt(n2) / xp.maximum(L, eps)
    degenerado = (h < eps_rel * xp.maximum(L, eps)) | (n1 < eps) | (nn < eps)
    return xp.where(degenerado[..., None], 0.0, v)

def _areas_dos_paineis(q):
    return 0.5 * np.linalg.norm(np.cross(q[:, 2] - q[:, 0], q[:, 3] - q[:, 1]), axis=1)

def _n_para_gpu() -> int:
    return 10**9

N_PARA_GPU = 200

def _modulo_de_array(n: int, usar_gpu):
    return np

@lru_cache(maxsize=1)
def _cupy_ou_numpy():
    try:
        import cupy
        cupy.zeros(1)
        return cupy
    except Exception:
        return np

@dataclass
class Superficie:

    planform: Planform
    incidencia: float = 0.0
    x_le: float = 0.0
    z: float = 0.0
    espelhada: bool = True
    diedro: float = 0.0
    y_raiz: float = 0.0
    de_referencia: bool | None = None
    perfil: Perfil | None = None
    perfil_ponta: Perfil | None = None
    n_span: int = round(_lido("vlm_n_span", 24))
    n_chord: int = round(_lido("vlm_n_chord", 4))

    def __post_init__(self) -> None:
        if self.espelhada and self.n_span > 0:
            corte = abs(np.cos(np.radians(self.diedro))) * self.n_span
            if corte < 1.0:
                raise ValueError(
                    f"{self.planform.nome}: superficie ESPELHADA com diedro de "
                    f"{self.diedro:g} graus e degenerada -- as duas metades "
                    f"ficam a menos de um painel uma da outra "
                    f"(separacao/painel = {corte:.3f}).\n"
                    "Para dispositivo de ponta use DUAS superficies com "
                    "`espelhada=False`, uma em cada ponta -- ou chame "
                    "`dispositivos_de_ponta()`, que ja as monta posicionadas.")

    @property
    def nome(self) -> str:
        return self.planform.nome

def dispositivos_de_ponta(asa: "Superficie", planta, cant: float = 90.0,
                          recuo: float = 0.0, n_span: int = 20,
                          n_chord: int | None = None,
                          perfil=None) -> list["Superficie"]:
    pf = asa.planform
    semi = pf.semi_envergadura
    ponta = pf.estacoes[-1]
    die = np.radians(asa.diedro)

    y_ponta = semi * np.cos(die)
    z_ponta = asa.z + ponta.z_le + semi * np.sin(die)
    x_ponta = asa.x_le + ponta.x_le + recuo

    saida = []
    for lado, sinal in (("dir", +1.0), ("esq", -1.0)):
        diedro = cant if sinal > 0 else 180.0 - cant
        planta_lado = dataclasses.replace(planta, nome=f"{planta.nome}_{lado}")
        saida.append(Superficie(
            planta_lado, diedro=diedro, y_raiz=sinal * y_ponta, z=z_ponta,
            x_le=x_ponta, espelhada=False, perfil=perfil,
            n_span=n_span, n_chord=n_chord if n_chord else asa.n_chord))
    return saida

@dataclass
class ResultadoVLM:

    alpha: float
    CL: float
    CDi: float
    e_oswald: float
    gamma: np.ndarray
    CY: float = 0.0
    Cl: float = 0.0
    Cm: float = 0.0
    Cn: float = 0.0
    forca_painel: np.ndarray | None = None
    dCp: np.ndarray | None = None
    cl_faixa: dict[str, np.ndarray] = field(default_factory=dict)
    cm_faixa: dict[str, np.ndarray] = field(default_factory=dict)
    y_faixa: dict[str, np.ndarray] = field(default_factory=dict)
    CL_superficie: dict[str, float] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (f"<VLM alpha={self.alpha:.2f}° CL={self.CL:.4f} "
                f"CDi={self.CDi:.5f} e={self.e_oswald:.4f}>")

class VLM:

    def __init__(self, superficies: list[Superficie], altura_solo: float | None = None,
                 comprimento_esteira: float = 50.0,
                 x_ref: float = 0.0, z_ref: float = 0.0,
                 usar_gpu: bool | None = None):
        if not superficies:
            raise ValueError("precisa de ao menos uma superfície")
        self.superficies = superficies
        self.x_ref, self.z_ref = x_ref, z_ref
        self.altura_solo = altura_solo
        self.usar_gpu = usar_gpu
        self.comprimento_esteira = comprimento_esteira
        self._montar()

    def _paineis_de(self, s: Superficie):
        pf, ns, nc = s.planform, s.n_span, s.n_chord
        semi = pf.semi_envergadura

        if s.espelhada:
            th = np.linspace(0.0, np.pi, ns + 1)
            y = -semi * np.cos(th)
        else:
            th = np.linspace(0.0, np.pi / 2, ns + 1)
            y = semi * np.sin(th)

        xf = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, nc + 1)))

        ys = np.array([e.y for e in pf.estacoes])
        cs = np.array([e.corda for e in pf.estacoes])
        xles = np.array([e.x_le for e in pf.estacoes])
        zles = np.array([e.z_le for e in pf.estacoes])
        torcoes = np.array([e.torcao for e in pf.estacoes])

        c_min = FRACAO_CORDA_MINIMA * pf.corda_raiz
        c_bruta = np.interp(np.abs(y), ys, cs)
        c = np.maximum(c_bruta, c_min)
        if np.any(c_bruta < c_min):
            import warnings
            warnings.warn(
                f"{pf.nome}: {int(np.sum(c_bruta < c_min))} estações com corda abaixo de "
                f"{FRACAO_CORDA_MINIMA:.1%} da raiz foram grampeadas em {c_min:.5f} m. "
                "Ponta afiada degrada o condicionamento da matriz de influência.",
                stacklevel=3,
            )
        xle = np.interp(np.abs(y), ys, xles) + s.x_le
        zle = np.interp(np.abs(y), ys, zles)

        if s.perfil is not None:
            xc_r, zc_r = s.perfil.linha_de_camber(200)
            camb_r = np.interp(xf, xc_r, zc_r)
            if s.perfil_ponta is not None:
                xc_p, zc_p = s.perfil_ponta.linha_de_camber(200)
                camb_p = np.interp(xf, xc_p, zc_p)
            else:
                camb_p = camb_r
            w = (np.abs(y) / semi)[None, :]
            camber = camb_r[:, None] * (1 - w) + camb_p[:, None] * w
        else:
            camber = np.zeros((nc + 1, ns + 1))

        inc = np.radians(s.incidencia + np.interp(np.abs(y), ys, torcoes))
        die = np.radians(s.diedro)
        y_geo = s.y_raiz + y * np.cos(die)
        z_geo = s.z + zle + np.abs(y) * np.sin(die) if s.espelhada else s.z + zle + y * np.sin(die)

        nos = np.zeros((nc + 1, ns + 1, 3))
        for m, f in enumerate(xf):
            dx = f * c
            dz = camber[m] * c
            nos[m, :, 0] = xle + dx * np.cos(inc) + dz * np.sin(inc)
            nos[m, :, 1] = y_geo
            nos[m, :, 2] = z_geo - dx * np.sin(inc) + dz * np.cos(inc)
        return nos, c

    def _montar(self) -> None:
        nomes = [s.nome for s in self.superficies]
        repetidos = {n for n in nomes if nomes.count(n) > 1}
        if repetidos:
            raise ValueError(
                f"superficies com nome repetido: {sorted(repetidos)}. O nome vem "
                f"da Planform e indexa os dados por faixa, entao repeti-lo faz "
                f"uma superficie apagar a outra. De nomes distintos as plantas "
                f"(ex.: 'asa inferior' e 'asa superior').")

        aneis, cps, normais = [], [], []
        self._fatias = {}
        i0 = 0

        for s in self.superficies:
            nos, c_nos = self._paineis_de(s)
            nc, ns = s.n_chord, s.n_span

            Q = nos[1:] - nos[:-1]
            frente = nos[:-1] + 0.25 * Q
            tras = np.concatenate([frente[1:], (nos[-1] + 0.25 * Q[-1])[None]], axis=0)

            r = np.zeros((nc, ns, 4, 3))
            r[:, :, 0] = frente[:, :-1]
            r[:, :, 1] = frente[:, 1:]
            r[:, :, 2] = tras[:, 1:]
            r[:, :, 3] = tras[:, :-1]
            aneis.append(r.reshape(nc * ns, 4, 3))

            fm = 0.5 * (nos[:-1, :-1] + nos[:-1, 1:])
            rm = 0.5 * (nos[1:, :-1] + nos[1:, 1:])
            cps.append((fm + 0.75 * (rm - fm)).reshape(nc * ns, 3))

            d1 = (nos[1:, 1:] - nos[:-1, :-1]).reshape(nc * ns, 3)
            d2 = (nos[1:, :-1] - nos[:-1, 1:]).reshape(nc * ns, 3)
            n = np.cross(d2, d1)
            normais.append(n / np.linalg.norm(n, axis=1, keepdims=True))

            Lw = np.array([self.comprimento_esteira * s.planform.envergadura, 0.0, 0.0])
            wA, wB = tras[-1, :-1], tras[-1, 1:]
            x_seg = 0.5 * (r[:, :, 0, 0] + r[:, :, 1, 0])
            x_le = 0.5 * (nos[0, :-1, 0] + nos[0, 1:, 0])
            c_faixa = 0.5 * (c_nos[:-1] + c_nos[1:])
            self._fatias[s.nome] = dict(
                inicio=i0, n=nc * ns, nc=nc, ns=ns,
                x_segmento=x_seg, x_quarto=x_le + 0.25 * c_faixa,
                esteira=np.stack([wA, wB, wB + Lw, wA + Lw], axis=1),
                y=0.5 * (nos[0, :-1, 1] + nos[0, 1:, 1]),
                c=0.5 * (c_nos[:-1] + c_nos[1:]),
                dy=np.diff(nos[0, :, 1]),
                d_env=np.hypot(np.diff(nos[0, :, 1]), np.diff(nos[0, :, 2])),
                S=s.planform.area, b=s.planform.envergadura,
            )
            i0 += nc * ns

        self.aneis = np.concatenate(aneis)
        self.cps = np.concatenate(cps)
        self.normais = np.concatenate(normais)
        self.N = len(self.aneis)

        _horizontais = [s_ for s_ in self.superficies
                        if abs(math.cos(math.radians(s_.diedro))) > 0.5]
        _declaradas = [s_ for s_ in _horizontais if s_.de_referencia]

        if _declaradas:
            _ref = _declaradas
        elif len(_horizontais) <= 1:
            _ref = _horizontais or [self.superficies[0]]
        else:
            import warnings
            warnings.warn(
                "VLM com "
                f"{len(_horizontais)} superficies sustentadoras "
                f"({', '.join(s_.planform.nome for s_ in _horizontais)}) e "
                "nenhuma declarou `de_referencia`. Usando so "
                f"'{_horizontais[0].planform.nome}' para S_ref/b_ref/c_ref, que "
                "e o comportamento anterior ao item 58. Num BIPLANO isso deixa "
                "o CL indefinido (sustentacao de duas asas sobre a area de "
                "uma, e qual delas depende da ordem da lista); numa asa com "
                "EMPENAGEM esta certo. Declare `de_referencia=True` nas asas "
                "para resolver.",
                stacklevel=3)
            _ref = [_horizontais[0]]

        self.S_ref = float(sum(s_.planform.area for s_ in _ref))
        self.b_ref = float(max(s_.planform.envergadura for s_ in _ref))
        self.c_ref = float(sum(s_.planform.mac * s_.planform.area
                               for s_ in _ref) / self.S_ref)
        self.AR_ref = self.b_ref**2 / self.S_ref

        for s in self.superficies:
            rec = n_span_recomendado(s.planform.alongamento)
            if s.n_span < rec:
                import warnings
                warnings.warn(
                    f"{s.nome}: AR={s.planform.alongamento:.2f} pede n_span>={rec}, "
                    f"veio {s.n_span}. Em asa curta o vortice de ponta domina e "
                    "subresolver a envergadura superestima o CL_alpha em varios "
                    "por cento. Ver n_span_recomendado().",
                    stacklevel=3,
                )

        Avec = self._influencia(self.cps)
        A = np.einsum("ijk,ik->ij", Avec, self.normais)
        self.cond = float(np.linalg.cond(A))
        if self.cond > COND_MAXIMA:
            import warnings
            warnings.warn(
                f"matriz de influência mal-condicionada (cond = {self.cond:.2e} > "
                f"{COND_MAXIMA:.0e}). Resultado não é confiável — procure painéis "
                "degenerados: ponta afiada, corda nula, superfícies coincidentes.",
                stacklevel=3,
            )
        self._lu = lu_factor(A)

        self._meio = 0.5 * (self.aneis[:, 0] + self.aneis[:, 1])
        self._areas = _areas_dos_paineis(np.asarray(self.aneis, dtype=float))

        self._forca_mat = np.ascontiguousarray(
            self._influencia(self._meio).transpose(0, 2, 1).reshape(-1, self.N))
        self._dl = self.aneis[:, 1] - self.aneis[:, 0]

    def _influencia(self, pontos: np.ndarray) -> np.ndarray:
        v = self._influencia_sistema(pontos, espelhar=False)
        if self.altura_solo is not None:
            p_img = pontos.copy()
            p_img[:, 2] = -2.0 * self.altura_solo - p_img[:, 2]
            v_img = self._influencia_sistema(p_img, espelhar=False)
            v_img[:, :, 2] *= -1.0
            v += v_img
        return v

    def _influencia_sistema(self, pontos: np.ndarray, espelhar: bool) -> np.ndarray:
        xp = _modulo_de_array(self.N, self.usar_gpu)
        if xp is np:
            return self._influencia_em(pontos, np)
        try:
            return self._influencia_no_kernel(pontos)
        except Exception:
            pass
        return xp.asnumpy(self._influencia_em(xp.asarray(pontos), xp))

    def _colunas_de_esteira(self):
        if getattr(self, "_esteira_plana", None) is None:
            w, c = [], []
            for info in self._fatias.values():
                w.append(info["esteira"])
                i0 = info["inicio"] + (info["nc"] - 1) * info["ns"]
                c.append(np.arange(i0, i0 + info["ns"]))
            self._esteira_plana = (np.concatenate(w) if w else None,
                                   np.concatenate(c) if c else None)
        return self._esteira_plana

    def _influencia_no_kernel(self, pontos):
        from arandu.aero import kernel_vlm_gpu as kv

        w, c = self._colunas_de_esteira()
        return kv.influencia(np.ascontiguousarray(pontos),
                             np.ascontiguousarray(self.aneis), w, c)

    def _geometria_em(self, xp):
        if xp is np:
            return self.aneis, [i["esteira"] for i in self._fatias.values()]
        cache = getattr(self, "_geom_gpu", None)
        if cache is None:
            cache = (xp.asarray(self.aneis),
                     [xp.asarray(i["esteira"]) for i in self._fatias.values()])
            self._geom_gpu = cache
        return cache

    def _influencia_em(self, pontos, xp):
        aneis, esteiras = self._geometria_em(xp)
        v = xp.zeros((len(pontos), self.N, 3))
        for k in range(4):
            v += _velocidade_segmento(pontos, aneis[:, k],
                                      aneis[:, (k + 1) % 4], xp=xp)
        if esteiras:
            w = xp.concatenate(esteiras, axis=0) if len(esteiras) > 1 else esteiras[0]
            vw = xp.zeros((len(pontos), len(w), 3))
            for k in range(4):
                vw += _velocidade_segmento(pontos, w[:, k],
                                           w[:, (k + 1) % 4], xp=xp)
            j = 0
            for info in self._fatias.values():
                ns = info["ns"]
                i0 = info["inicio"] + (info["nc"] - 1) * ns
                v[:, i0:i0 + ns] += vw[:, j:j + ns]
                j += ns
        return v

    def resolver(self, alphas, V: float = 1.0, rho: float = 1.0,
                 delta_alpha: dict[str, np.ndarray] | None = None,
                 delta_flap: dict[str, np.ndarray] | None = None,
                 x_charneira: float = 0.8, beta: float = 0.0,
                 p: float = 0.0, q_taxa: float = 0.0, r_taxa: float = 0.0,
                 v_local: np.ndarray | None = None,
                 guardar_campos: bool = False
                 ) -> list[ResultadoVLM]:
        alphas = np.atleast_1d(np.asarray(alphas, dtype=float))
        if v_local is not None:
            v_local = np.asarray(v_local, dtype=float)
            if v_local.shape != (self.N, 3):
                raise ValueError(
                    f"v_local deve ter forma ({self.N}, 3), veio {v_local.shape}")
        if self.altura_solo is not None and not getattr(self, "_pular_solo", False):
            return [self._resolver_com_solo(float(a), V, rho) for a in alphas]

        extra = np.zeros(self.N)
        for fonte, so_flape in ((delta_alpha, False), (delta_flap, True)):
            if not fonte:
                continue
            for nome, da in fonte.items():
                info = self._fatias[nome]
                if len(da) != info["ns"]:
                    raise ValueError(
                        f"correcao['{nome}'] tem {len(da)} valores, "
                        f"esperado {info['ns']} (uma por faixa)")
                bloco = np.tile(np.asarray(da, dtype=float), (info["nc"], 1))
                if so_flape:
                    frac = (info["x_segmento"] - info["x_quarto"][None, :] +
                            0.25 * info["c"][None, :]) / info["c"][None, :]
                    bloco = bloco * (frac >= x_charneira)
                i0_, n_ = info["inicio"], info["n"]
                extra[i0_:i0_ + n_] = extra[i0_:i0_ + n_] + bloco.ravel()

        saida = []
        be = np.radians(beta)

        if p or q_taxa or r_taxa:
            omega = np.array([-p, q_taxa, -r_taxa], dtype=float)
            braco = self.cps - np.array([self.x_ref, 0.0, self.z_ref])
            rhs_rot = np.einsum("ij,ij->i", -np.cross(omega, braco),
                                self.normais)
        else:
            rhs_rot = 0.0
        rhs_vloc = (np.einsum("ij,ij->i", v_local, self.normais)
                    if v_local is not None else 0.0)

        rad = np.radians(np.asarray(alphas, dtype=float))
        Vinf_todos = V * np.stack([np.cos(rad) * np.cos(be),
                                   np.full(rad.shape, -np.sin(be)),
                                   np.sin(rad) * np.cos(be)], axis=1)
        B = -(self.normais @ Vinf_todos.T) - (
            V * extra + rhs_rot + rhs_vloc)[:, None]
        G_todos = lu_solve(self._lu, B)
        Vind_todos = (self._forca_mat @ G_todos).reshape(self.N, 3, -1)

        for _j, a in enumerate(alphas):
            al = rad[_j]
            Vinf = Vinf_todos[_j]
            V_chega = np.broadcast_to(Vinf, (self.N, 3))
            if v_local is not None:
                V_chega = V_chega + v_local
            G = G_todos[:, _j]
            Vloc = V_chega + Vind_todos[:, :, _j]
            gnet = self._circulacao_liquida(G)
            dF = rho * gnet[:, None] * np.cross(Vloc, self._dl)
            F = np.sum(dF, axis=0)
            braco_m = self._meio - np.array([self.x_ref, 0.0, self.z_ref])
            M = np.sum(np.cross(braco_m, dF), axis=0)

            q = 0.5 * rho * V * V
            dcp = (np.einsum("ij,ij->i", dF, self.normais)
                   / (q * self._areas)) if guardar_campos else None
            forca = np.ascontiguousarray(dF) if guardar_campos else None
            CL = float(F @ np.array([-np.sin(al), 0.0, np.cos(al)]) / (q * self.S_ref))
            CDi = float(F @ np.array([np.cos(al), 0.0, np.sin(al)]) / (q * self.S_ref))
            e = CL**2 / (np.pi * self.AR_ref * CDi) if CDi > 1e-12 else float("nan")
            qS = q * self.S_ref
            CY = float(F[1] / qS)
            Cl_ = float(-M[0] / (qS * self.b_ref))
            Cm_ = float(M[1] / (qS * self.c_ref))
            Cn_ = float(-M[2] / (qS * self.b_ref))

            cl_f, cm_f, y_f, CL_s = {}, {}, {}, {}
            for nome, info in self._fatias.items():
                g2 = G[info["inicio"]:info["inicio"] + info["n"]].reshape(info["nc"], info["ns"])
                gs = g2[-1]
                cl_f[nome] = 2.0 * gs / (V * info["c"])
                gnet2 = np.vstack([g2[:1], np.diff(g2, axis=0)])
                braco = info["x_segmento"] - info["x_quarto"][None, :]
                cm_f[nome] = -2.0 * np.sum(gnet2 * braco, axis=0) / (V * info["c"] ** 2)
                y_f[nome] = info["y"]
                CL_s[nome] = float(2.0 * np.sum(gs * info["dy"]) / (V * info["S"]))

            saida.append(ResultadoVLM(alpha=float(a), CL=CL, CDi=CDi, e_oswald=e,
                                      gamma=G, CY=CY, Cl=Cl_, Cm=Cm_, Cn=Cn_,
                                      cl_faixa=cl_f, cm_faixa=cm_f,
                                      y_faixa=y_f, CL_superficie=CL_s,
                                      dCp=dcp, forca_painel=forca))
        return saida

    def _resolver_com_solo(self, alpha: float, V: float, rho: float) -> ResultadoVLM:
        import dataclasses

        giradas = [dataclasses.replace(s, incidencia=s.incidencia + alpha)
                   for s in self.superficies]
        aux = VLM(giradas, altura_solo=self.altura_solo,
                  comprimento_esteira=self.comprimento_esteira)
        aux._pular_solo = True
        r = aux.resolver(0.0, V=V, rho=rho)[0]
        return dataclasses.replace(r, alpha=alpha)

    def _circulacao_liquida(self, G: np.ndarray) -> np.ndarray:
        gnet = np.empty_like(G)
        for info in self._fatias.values():
            i, n, nc, ns = info["inicio"], info["n"], info["nc"], info["ns"]
            g2 = G[i:i + n].reshape(nc, ns).copy()
            g2[1:] -= G[i:i + n].reshape(nc, ns)[:-1]
            gnet[i:i + n] = g2.ravel()
        return gnet

    def downwash_em(self, pontos: np.ndarray, alpha: float, V: float = 1.0) -> np.ndarray:
        pontos = np.atleast_2d(np.asarray(pontos, dtype=float))
        al = np.radians(alpha)

        if self.altura_solo is not None and not getattr(self, "_pular_solo", False):
            import dataclasses

            giradas = [dataclasses.replace(s, incidencia=s.incidencia + alpha)
                       for s in self.superficies]
            aux = VLM(giradas, altura_solo=self.altura_solo,
                      comprimento_esteira=self.comprimento_esteira)
            aux._pular_solo = True
            c, s_ = np.cos(al), np.sin(al)
            p = pontos.copy()
            p[:, 0] = pontos[:, 0] * c
            p[:, 2] = pontos[:, 2] - pontos[:, 0] * s_
            return aux.downwash_em(p, 0.0, V=V)

        Vinf = V * np.array([np.cos(al), 0.0, np.sin(al)])
        G = lu_solve(self._lu, -(self.normais @ Vinf))
        w = np.einsum("nmk,m->nk", self._influencia(pontos), G)
        return np.degrees(np.arctan2(-w[:, 2], V + w[:, 0]))

    def __repr__(self) -> str:
        solo = f", solo a {self.altura_solo:.3f} m" if self.altura_solo is not None else ""
        nomes = ", ".join(s.nome for s in self.superficies)
        return f"<VLM {self.N} painéis [{nomes}]{solo}, cond={self.cond:.2e}>"
