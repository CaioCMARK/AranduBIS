from __future__ import annotations

from pathlib import Path

import json

import numpy as np

MATERIAIS = {
    "tubo_carbono": (1800.0, "valor de referencia"),
    "fibra_carbono": (1800.0, "valor de referencia"),
    "aco": (7900.0, "valor de referencia"),
    "balsa": (160.0, "tipico; varia de 100 a 250 entre lotes"),
    "nylon": (1140.0, "tipico (nylon 6)"),
    "aluminio": (2700.0, "tipico (6061)"),
    "liteply": (500.0, "tipico"),
    "mdf": (750.0, "tipico"),
    "isopor": (20.0, "tipico"),
}

def densidade(nome, esq=None):
    tab = (esq or {}).get("materiais") or {}
    if nome in tab:
        v = tab[nome]; return float(v["densidade"] if isinstance(v, dict) else v)
    if nome in MATERIAIS: return MATERIAIS[nome][0]
    raise ValueError(f"material {nome!r} sem densidade: declare em \"materiais\" (os de fabrica: {sorted(MATERIAIS)})")

def ler_dat(caminho):
    P = []
    for ln in Path(caminho).read_text(encoding="utf8", errors="replace").splitlines():
        t = ln.replace(",", " ").split()
        try: v = [float(q) for q in t[:2]]
        except ValueError: continue
        if len(v) == 2: P.append(v)
    if len(P) < 6: raise ValueError(f"{caminho}: poucos pontos ({len(P)})")
    P = np.array(P, float)
    if P[0, 0] > 1.5:
        n1 = int(P[0, 0]); P = P[1:]; A, B = P[:n1], P[n1:]
        if A[:, 1].mean() < B[:, 1].mean(): A, B = B, A
    else:
        i = int(np.argmin(P[:, 0])); A, B = P[:i + 1][::-1], P[i:]
        if A[:, 1].mean() < B[:, 1].mean(): A, B = B, A
    x0 = min(A[0, 0], B[0, 0]); c = max(A[:, 0].max(), B[:, 0].max()) - x0
    A = (A - [x0, 0]) / c; B = (B - [x0, 0]) / c
    z0 = 0.5 * (A[0, 1] + B[0, 1]); A[:, 1] -= z0; B[:, 1] -= z0
    return A[:, 0], A[:, 1], B[:, 0], B[:, 1]

def _naca(cod):
    m, p, t = int(cod[0]) / 100, int(cod[1]) / 10, int(cod[2:]) / 100; b = np.linspace(0, np.pi, 240); x = 0.5 * (1 - np.cos(b))
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    yc = np.where(x < p, m / p ** 2 * (2 * p * x - x ** 2), m / (1 - p) ** 2 * (1 - 2 * p + 2 * p * x - x ** 2)) if m > 0 else 0 * x
    dy = np.where(x < p, 2 * m / p ** 2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x)) if m > 0 else 0 * x; th = np.arctan(dy)
    return x - yt * np.sin(th), yc + yt * np.cos(th), x + yt * np.sin(th), yc - yt * np.cos(th)

def perfil_xy(spec, n, pasta="."):
    txt = str(spec); dig = "".join(c for c in txt if c.isdigit())
    if txt.lower().endswith(".dat"):
        xs, zs, xi, zi = ler_dat(Path(pasta) / txt)
    elif len(dig) == 4:
        xs, zs, xi, zi = _naca(dig)
    else:
        raise ValueError(f"perfil {txt!r}: use NACA de 4 digitos ou um arquivo .dat")
    x = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n)))
    a = np.interp(x, xs, zs); b = np.interp(x, xi, zi); te = 0.5 * (a[-1] + b[-1]); le = 0.5 * (a[0] + b[0]); a[0] = b[0] = le; a[-1] = b[-1] = te
    return x, a, b

def anel_de(x, zs, zi):
    return np.vstack([np.c_[x, zs][::-1], np.c_[x, zi][1:-1]])

_MODOS = ("razao_tensoes", "encurtamento", "temperatura_C", "tensao_envergadura")

def mescla(base, extra):
    o = dict(base)
    if any(k in extra for k in _MODOS):
        for k in _MODOS: o.pop(k, None)
    o.update(extra); return o

def filme_de(cfg, esq=None):
    f = cfg.get("filme")
    if isinstance(f, str):
        lib = (esq or {}).get("filmes") or {}
        if f not in lib: raise ValueError(f"filme {f!r} nao esta em 'filmes' (os do projeto: {sorted(lib)})")
        return lib[f]
    return f or {}

def com_filme(cfg, esq):
    o = dict(cfg)
    if isinstance(o.get("filme"), str): o["filme"] = filme_de(o, esq)
    for k in ("extradorso", "intradorso"):
        if isinstance(o.get(k), dict) and isinstance(o[k].get("filme"), str): o[k] = com_filme(o[k], esq)
    if o.get("baias"): o["baias"] = [com_filme(q, esq) for q in o["baias"]]
    return o

def da_baia(cfg, k, a, b):
    o = {q: v for q, v in cfg.items() if q != "baias"}; yc = 0.5 * (a + b)
    for q in cfg.get("baias") or []:
        vale = q.get("indice") == k if "indice" in q else ("y" in q and min(q["y"]) <= yc <= max(q["y"]))
        if not vale: continue
        ex = {c: v for c, v in q.items() if c not in ("indice", "y", "extradorso", "intradorso")}; o = mescla(o, ex)
        for lado in ("extradorso", "intradorso"):
            if q.get(lado): o[lado] = mescla(o.get(lado) or {}, q[lado])
    return o

def calibra(cfg, medido_mm, calculado_mm):
    if not (medido_mm > 0 and calculado_mm > 0): raise ValueError("calibracao: precisa de flecha medida e calculada positivas")
    f = medido_mm / calculado_mm; o = json.loads(json.dumps(cfg)); ant = float(o.get("coef_abaulamento", 1.0)); o["coef_abaulamento"] = ant * f

    def escala(q):
        for lado in ("extradorso", "intradorso"):
            if isinstance(q.get(lado), dict) and "coef_abaulamento" in q[lado]: q[lado]["coef_abaulamento"] = float(q[lado]["coef_abaulamento"]) * f
    escala(o)
    for q in o.get("baias") or []:
        if "coef_abaulamento" in q: q["coef_abaulamento"] = float(q["coef_abaulamento"]) * f
        escala(q)
    o["calibracao"] = {"medido_mm": float(medido_mm), "calculado_mm": float(calculado_mm), "coef_antes": ant}; return o

def _encurtamentos(cfg, fl):
    if "temperatura_C" in cfg:
        cu = fl.get("curva_encurtamento") or []
        if len(cu) < 2: raise ValueError("temperatura_C pede `curva_encurtamento` no filme: lista de [T, % corda, % envergadura], com ao menos 2 linhas")
        cu = sorted(cu, key=lambda q: q[0]); T = [float(q[0]) for q in cu]; t = float(cfg["temperatura_C"]); return float(np.interp(t, T, [float(q[1]) for q in cu])), float(np.interp(t, T, [float(q[2]) for q in cu]))
    enc = cfg.get("encurtamento") or fl.get("encurtamento") or {}
    return float(enc.get("corda", 1.0)), float(enc.get("envergadura", 1.0))

def razao_tensoes(cfg):
    if "razao_tensoes" in cfg:
        r = float(cfg["razao_tensoes"])
        if not r > 0: raise ValueError("razao_tensoes precisa ser > 0")
        return r, float(cfg.get("tensao_corda", 100.0))
    if "tensao_envergadura" in cfg:
        Tc, Te = float(cfg.get("tensao_corda", 100.0)), float(cfg["tensao_envergadura"])
        if not (Tc > 0 and Te > 0): raise ValueError("tensoes do filme precisam ser > 0")
        return Tc / Te, Tc
    fl = cfg.get("filme") or {}; c_, e_ = _encurtamentos(cfg, fl); ec, ee = c_ / 100, e_ / 100
    E = float(fl.get("E_GPa", 2.0)) * 1e9; t = float(fl.get("espessura_um", 25.0)) * 1e-6; nu = float(fl.get("nu", 0.3)); k = E * t / (1 - nu * nu)
    Tc, Te = k * (ec + nu * ee), k * (ee + nu * ec)
    if not (Tc > 0 and Te > 0): raise ValueError("encurtamentos dao tensao nao positiva: o filme ficaria frouxo")
    return Tc / Te, Tc

def abaula(x, z, y, b, r, dp_sobre_Tc=0.0, m_max=120):
    x = np.asarray(x, float); z = np.asarray(z, float); y = np.atleast_1d(np.asarray(y, float)); x0, x1 = x[0], x[-1]; L = x1 - x0
    if L <= 0: return np.tile(z, (len(y), 1))
    N = max(2 * m_max, 256); xu = np.linspace(x0, x1, N + 1); zu = np.interp(xu, x, z); lin = z[0] + (z[-1] - z[0]) * (xu - x0) / L; s = zu - lin
    m = np.arange(1, m_max + 1); k = m * np.pi / L; lam = k * np.sqrt(r)
    B = np.sin(np.outer(m, np.pi * (xu - x0) / L))
    sm = 2 * (B[:, 1:-1] @ s[1:-1]) / N
    pm = np.where(m % 2 == 1, 4 / (m * np.pi), 0.0)
    ay = np.abs(y)[:, None]; C = (np.exp(lam * (ay - b / 2)) + np.exp(-lam * (ay + b / 2))) / (1 + np.exp(-lam * b))
    A = sm[None, :] * C + dp_sobre_Tc * pm[None, :] / k[None, :] ** 2 * (1 - C)
    Bx = np.sin(np.outer(m, np.pi * (x - x0) / L))
    lx = z[0] + (z[-1] - z[0]) * (x - x0) / L
    res = z - (lx + (sm[None, :] @ Bx)[0])
    return (lx + res)[None, :] + A @ Bx

def aplica_entelagem(x, zs, zi, c, b, eta, cfg):
    Z = []
    for sinal, z, lado in ((+1.0, zs, "extradorso"), (-1.0, zi, "intradorso")):
        q = mescla(cfg, cfg[lado]) if cfg.get(lado) else cfg
        if q.get("ativo") is False: Z.append(z.copy()); continue
        r, Tc = razao_tensoes(q); dp = float(q.get("dp", 0.0)); ka = float(q.get("coef_abaulamento", 1.0)); de = float(q.get("de_xc", 0.0)); ate = float(q.get("ate_xc", 1.0))
        cortes = sorted({de, ate, *[float(v) for v in q.get("apoios_xc", []) if de < float(v) < ate]}); w = z.copy()
        for a, f in zip(cortes, cortes[1:]):
            sel = (x >= a - 1e-12) & (x <= f + 1e-12)
            if sel.sum() < 3: continue
            xv = np.r_[a, x[(x > a + 1e-12) & (x < f - 1e-12)], f]; zv = np.interp(xv, x, z)
            wv = abaula(xv * c, zv * c, [eta * b], b, r, sinal * dp / Tc)[0] / c
            w[sel] = np.interp(x[sel], xv, zv + ka * (wv - zv))
        Z.append(w)
    return Z[0], Z[1]

def _area2(P): return 0.5 * float(P[:, 0] @ np.roll(P[:, 1], -1) - P[:, 1] @ np.roll(P[:, 0], -1))

def triangula_com_furos(P, furos=()):
    pts = [np.asarray(P, float)]; anel = list(range(len(P))); of = len(P); F = []
    for H in furos:
        H = np.asarray(H, float); F.append((H, of)); pts.append(H); of += len(H)
    V = np.vstack(pts)
    if _area2(V[:len(P)]) < 0: anel = anel[::-1]
    F.sort(key=lambda hf: -hf[0][:, 0].max())
    for H, o in F:
        ids = list(range(o, o + len(H)))
        if _area2(H) > 0: ids = ids[::-1]
        i0 = int(np.argmax(V[ids, 0])); ids = ids[i0:] + ids[:i0]; q = V[ids[0]]
        a = np.array(anel); Pa, Pb = V[a], V[np.roll(a, -1)]; melhor = None; bd = np.inf
        dy1 = Pa[:, 1] - q[1]; dy2 = Pb[:, 1] - q[1]; cruza = (dy1 * dy2 <= 0) & (dy1 != dy2)
        for i in np.flatnonzero(cruza):
            t = dy1[i] / (dy1[i] - dy2[i]); xc = Pa[i, 0] + t * (Pb[i, 0] - Pa[i, 0])
            if xc >= q[0] and xc - q[0] < bd:
                bd = xc - q[0]; melhor = i if Pa[i, 0] >= Pb[i, 0] else (i + 1) % len(a)
        if melhor is None: raise ValueError("furo fora do contorno da placa")
        cand = V[a]; d = cand - q; alvo = melhor
        A_, B_, C_ = q, V[a[alvo]], np.array([q[0] + bd, q[1]]); v0 = C_ - A_; v1 = B_ - A_; dn = v0[0] * v1[1] - v0[1] * v1[0]
        if abs(dn) > 1e-15:
            v2 = cand - A_; u_ = (v2[:, 0] * v1[1] - v2[:, 1] * v1[0]) / dn; w_ = (v0[0] * v2[:, 1] - v0[1] * v2[:, 0]) / dn
            dentro = np.flatnonzero((u_ > 1e-12) & (w_ > 1e-12) & (u_ + w_ < 1 - 1e-12) & (a != a[alvo]))
            if len(dentro):
                ang = np.abs(np.arctan2(d[dentro, 1], d[dentro, 0])); alvo = int(dentro[np.lexsort((np.hypot(d[dentro, 0], d[dentro, 1]), np.round(ang, 9)))[0]])
        ocorrencias = np.flatnonzero(a == a[alvo])
        if len(ocorrencias) > 1:
            for k_ in ocorrencias:
                pa, pm, pb = V[a[k_ - 1]], V[a[k_]], V[a[(k_ + 1) % len(a)]]; esq = lambda o, p_, r_: (p_[0] - o[0]) * (r_[1] - o[1]) - (p_[1] - o[1]) * (r_[0] - o[0])
                conv_ = esq(pa, pm, pb) >= 0; l1 = esq(pa, pm, q) > 0; l2 = esq(pm, pb, q) > 0
                if (l1 and l2) if conv_ else (l1 or l2): alvo = int(k_); break
        anel = list(a[:alvo + 1]) + ids + [ids[0]] + list(a[alvo:])
    idx = list(anel); T = []; guarda = 0; X, Y = V[:, 0], V[:, 1]
    while len(idx) > 3 and guarda < 4 * len(anel) ** 2:
        guarda += 1; m = len(idx); arr = np.array(idx); ax, ay = X[np.roll(arr, 1)], Y[np.roll(arr, 1)]; bx, by = X[arr], Y[arr]; cx, cy = X[np.roll(arr, -1)], Y[np.roll(arr, -1)]
        conv = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax); achou = False
        for i in np.argsort(-conv):
            if conv[i] <= 1e-18: break
            a_, b_, c_ = idx[i - 1], idx[i], idx[(i + 1) % m]; Ax, Ay, Bx, By, Cx, Cy = X[a_], Y[a_], X[b_], Y[b_], X[c_], Y[c_]
            s1 = (Bx - Ax) * (Y[arr] - Ay) - (By - Ay) * (X[arr] - Ax); s2 = (Cx - Bx) * (Y[arr] - By) - (Cy - By) * (X[arr] - Bx); s3 = (Ax - Cx) * (Y[arr] - Cy) - (Ay - Cy) * (X[arr] - Cx)
            eh = (arr == a_) | (arr == b_) | (arr == c_); mesmo = ((X[arr] == Ax) & (Y[arr] == Ay)) | ((X[arr] == Bx) & (Y[arr] == By)) | ((X[arr] == Cx) & (Y[arr] == Cy))
            if np.any((s1 >= 0) & (s2 >= 0) & (s3 >= 0) & ~eh & ~mesmo): continue
            T.append((a_, b_, c_)); idx.pop(i); achou = True; break
        if not achou:
            ar = np.abs(conv); idx.pop(int(np.argmin(ar)))
    if len(idx) == 3: T.append(tuple(idx))
    return V, T

def barras_prisma(N, B, raios, faces=8):
    N = np.asarray(N, float); B = np.asarray(B, int); nb = len(B); a = N[B[:, 0]]; b = N[B[:, 1]]; d = b - a; L = np.linalg.norm(d, axis=1)
    if nb and (L < 1e-12).any(): raise ValueError(f"barra de comprimento zero: {B[np.argmin(L)].tolist()}")
    u = d / L[:, None]; r0 = np.where((np.abs(u[:, 2]) < 0.9)[:, None], np.array([[0.0, 0.0, 1.0]]), np.array([[0.0, 1.0, 0.0]])); e1 = np.cross(u, r0); e1 /= np.linalg.norm(e1, axis=1)[:, None]; e2 = np.cross(u, e1)
    th = 2 * np.pi * np.arange(faces) / faces; anel = np.cos(th)[None, :, None] * e1[:, None, :] + np.sin(th)[None, :, None] * e2[:, None, :]; anel = anel * np.asarray(raios, float)[:, None, None]
    V = np.concatenate([a[:, None, :] + anel, b[:, None, :] + anel], axis=1).reshape(-1, 3); tb = []
    for k in range(faces):
        k1 = (k + 1) % faces; tb += [(k, k1, faces + k1), (k, faces + k1, faces + k)]
    for k in range(1, faces - 1):
        tb += [(0, k + 1, k), (faces, faces + k, faces + k + 1)]
    tb = np.array(tb); of = 2 * faces * np.arange(nb)[:, None, None]; T = (tb[None, :, :] + of).reshape(-1, 3)
    return V, T, np.repeat(np.arange(nb), len(tb))

def posicao_x(item: dict, c: float, y: float) -> float:
    par = item.get("xc_y")
    if par:
        par = sorted((abs(float(a)), float(b)) for a, b in par)
        return float(np.interp(abs(y), [q[0] for q in par], [q[1] for q in par])) * c
    return float(item["x"]) if "x" in item else float(item["xc"]) * c
