from __future__ import annotations

import numpy as np

from ..estrutura.asa import _elemento, _fim_do_chapeado, _perfis
from ..estrutura.materiais import propriedades
from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from .modelo import Modelo
from .solver import Sistema

def _estacoes(cfg, y_max, dy_max, com_regulares, com_cruzadas, area_secao):
    ys = {0.0, round(float(y_max), 9)}
    nv = cfg.get("nervuras") or {}
    ribs = {}
    if com_regulares and nv:
        for y in nv.get("y", []):
            y = abs(float(y))
            if 0 < y < y_max - 1e-9:
                ribs[round(y, 9)] = float(nv.get("espessura", 0.00238)) * (1.0 - float(nv.get("alivio", 0.0)))
    if com_cruzadas:
        for cz in cfg.get("cruzadas") or []:
            a, b = (abs(float(v)) for v in cz["y"])
            a, b = min(a, b), max(a, b)
            n = int(cz["n"])
            for k in range(n):
                y = a + (k + 0.5) * (b - a) / n
                if 0 < y < y_max - 1e-9:
                    t_eq = float(cz.get("espessura", 0.00238)) * float(cz["area_m2"]) / max(area_secao(y), 1e-9)
                    ribs[round(y, 9)] = ribs.get(round(y, 9), 0.0) + t_eq
    ys |= set(ribs)
    ys = sorted(ys)
    fino = [ys[0]]
    for b in ys[1:]:
        a = fino[-1]
        n = max(1, int(np.ceil((b - a) / dy_max - 1e-9)))
        fino += [a + (b - a) * k / n for k in range(1, n + 1)]
    return [round(v, 9) for v in fino], ribs

def monta(esq: dict, nome: str, mats: dict | None = None, regulares: bool = True, cruzadas: bool = True, dy_max: float = 0.06,
          n_corda: int = 6, com_tubos: bool = True):
    el = _elemento(esq, nome)
    cfg = el.get("estrutura") or {}
    if not cfg.get("longarinas"):
        raise ValueError("a asa nao declara longarina")
    sec_el, x, Z = _perfis(el, esq)
    m = {k: propriedades(k, esq, mats) for k in ("balsa", "tubo_carbono")}
    y_max = max(abs(s[1]) for s in sec_el)
    lg = cfg["longarinas"][0]
    tw = float(lg.get("largura", 0.00238))
    ch = cfg.get("chapeado") or {}
    ts = float(ch.get("espessura", 0.001))

    def secao(y):
        q = AG._secao_em(sec_el, float(y))
        i, t = AG._no_vao(sec_el, float(y))
        zs = (1 - t) * Z[i][0] + t * Z[i + 1][0]
        zi = (1 - t) * Z[i][1] + t * Z[i + 1][1]
        return q, zs, zi

    def area_secao(y):
        q, zs, zi = secao(y)
        return float(np.trapezoid(zs - zi, x)) * q[3] ** 2

    ys, ribs = _estacoes(cfg, y_max, dy_max, regulares, cruzadas, area_secao)
    mod = Modelo()
    Eb = m["balsa"]["E"]
    mod.material(1, Eb, m["balsa"]["G"], nu=m["balsa"].get("nu", 0.01), E2=m["balsa"].get("E2", Eb / 20.0))
    mod.material(2, m["tubo_carbono"]["E"], m["tubo_carbono"]["G"], rho=0.0)
    cont = [0]

    def novo(p):
        cont[0] += 1
        mod.no(cont[0], *p)
        return cont[0]

    grades, UP, LO = [], [], []
    for y in ys:
        q, zs, zi = secao(y)
        c = q[3]
        xs = ES.posicao_x(lg, c, y) / c
        xe = _fim_do_chapeado(ch, y) if ch else 0.0
        a, b = (min(xs, xe) if xe > 0 else xs), max(xs, xe)
        g = list(np.linspace(0.0, a, n_corda + 1)) + ([b] if b - a > 1e-6 else [])
        grades.append((g, xs, xe))
        ai = np.radians(q[4])
        cd = np.array([np.cos(ai), 0, -np.sin(ai)])
        nd = np.array([np.sin(ai), 0, np.cos(ai)])
        pt = lambda u, z, q=q, c=c, cd=cd, nd=nd: np.array(q[:3]) + c * (u * cd + z * nd)
        up = [novo(pt(u, float(np.interp(u, x, zs)))) for u in g]
        lo = [up[0]] + [novo(pt(u, float(np.interp(u, x, zi)))) for u in g[1:]]
        UP.append(up)
        LO.append(lo)
    el_id = [0]

    def casca(mat, t, ns):
        el_id[0] += 1
        mod.casca(el_id[0], mat, t, ns)

    for k in range(len(ys) - 1):
        g0, xs0, xe0 = grades[k]
        g1, _, xe1 = grades[k + 1]
        for i in range(min(len(g0), len(g1)) - 1):
            if ch and max(g0[i + 1], g1[i + 1]) <= max(xe0, xe1) + 1e-9:
                casca(1, ts, (UP[k][i], UP[k + 1][i], UP[k + 1][i + 1], UP[k][i + 1]))
                casca(1, ts, (LO[k][i], LO[k + 1][i], LO[k + 1][i + 1], LO[k][i + 1]))
        iw = next(i for i, u in enumerate(g0) if abs(u - xs0) < 1e-9)
        casca(1, tw, (UP[k][iw], UP[k + 1][iw], LO[k + 1][iw], LO[k][iw]))
    for k, y in enumerate(ys):
        if k == 0 or y not in ribs:
            continue
        g = grades[k][0]
        for i in range(len(g) - 1):
            casca(1, ribs[y], (UP[k][i], UP[k][i + 1], LO[k][i + 1], LO[k][i]))
    if com_tubos:
        vistos, pid = set(), 0
        for tb in cfg.get("tubos", []):
            de, di = float(tb["de"]), float(tb.get("di", 0.0))
            y0, y1 = tb.get("y") or (0.0, y_max)
            a, b = sorted((abs(float(y0)), abs(float(y1))))
            chave = (round(a, 6), round(b, 6), tb.get("lado", "extradorso"), de, di)
            if chave in vistos or tb.get("lado") == "meio":
                continue
            vistos.add(chave)
            pid += 1
            A = 0.25 * np.pi * (de ** 2 - di ** 2)
            I = np.pi / 64 * (de ** 4 - di ** 4)
            mod.prop(pid, 2, A, I, I, 2 * I)
            arr = UP if tb.get("lado", "extradorso") == "extradorso" else LO
            for k in range(len(ys) - 1):
                if ys[k] >= a - 1e-9 and ys[k + 1] <= b + 1e-9:
                    g, xs, _ = grades[k]
                    iw = next(i for i, u in enumerate(g) if abs(u - xs) < 1e-9)
                    el_id[0] += 1
                    mod.barra(el_id[0], pid, arr[k][iw], arr[k + 1][iw], (0.0, 0.0, 1.0))
    mod.engasta(set(UP[0]) | set(LO[0]))
    return mod, ys, UP, LO, ribs

def torcao_fe(esq: dict, nome: str, mats: dict | None = None, regulares: bool = True, cruzadas: bool = True, T: float = 1.0, **kw) -> dict:
    mod, ys, UP, LO, ribs = monta(esq, nome, mats, regulares, cruzadas, **kw)
    ponta = sorted(set(UP[-1]) | set(LO[-1]))
    pts = np.array([mod.nos[n] for n in ponta])
    mestre = max(mod.nos) + 1
    mod.no(mestre, pts[:, 0].mean(), ys[-1], pts[:, 2].mean())
    mod.rigido(1, mestre, ponta)
    mod.carga(1, mestre, [0, 0, 0, 0, T, 0])
    u = Sistema(mod).estatica(1)["u"]
    theta = []
    for k in range(len(ys)):
        ns = sorted(set(UP[k]) | set(LO[k]))
        X = np.array([mod.nos[n][0] for n in ns])
        W = np.array([u[n][2] for n in ns])
        theta.append(-float(np.polyfit(X, W, 1)[0]))
    theta = np.array(theta)
    GJ = T * np.diff(ys) / np.maximum(np.diff(theta), 1e-30)
    return {"y": ys, "theta": theta.tolist(), "GJ_trecho": GJ.tolist(), "K_theta": float(T / theta[-1]), "giro_ponta": float(theta[-1]),
            "n_nos": len(mod.nos), "n_cascas": len(mod.cascas), "n_barras": len(mod.barras), "n_nervuras": len(ribs)}
