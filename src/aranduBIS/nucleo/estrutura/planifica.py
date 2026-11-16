from __future__ import annotations

import math

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from ..modelador.dxf import CAMADAS, Dxf

LIMITE_PCT = {"balsa": 0.3, "compensado": 0.2, "papel": 1.0, "filme": 3.0, "mylar": 3.0, "carbono": 0.1, "fibra": 0.1, "vidro": 0.1, "isopor": 1.0, "depron": 2.0}
LIMITE_PADRAO_PCT = 0.5


def limite_do_material(material: str, dado=None) -> float:
    if dado is not None and float(dado) > 0:
        return float(dado)
    m = str(material or "").lower()
    for k, v in LIMITE_PCT.items():
        if k in m:
            return v
    return LIMITE_PADRAO_PCT


def _perfis(el, esq):
    sec = AG._secoes(el)
    if AG._quer_aneis(el):
        x, Z = AG._perfis_secoes(el, esq)
    else:
        x, zs_, zi_ = ES.perfil_xy(el.get("perfil", "NACA 0012"), int(el.get("n_perfil", 40)), esq.get("_pasta", "."))
        Z = [(zs_, zi_)] * len(sec)
    return sec, x, Z


def _pontos_secao(sec, x, Z, y):
    q = AG._secao_em(sec, y)
    i, t = AG._no_vao(sec, y)
    zs = (1 - t) * Z[i][0] + t * Z[i + 1][0]
    zi = (1 - t) * Z[i][1] + t * Z[i + 1][1]
    ai = math.radians(q[4])
    cd = np.array([math.cos(ai), 0.0, -math.sin(ai)])
    nd = np.array([math.sin(ai), 0.0, math.cos(ai)])
    org = np.array(q[:3], float)
    sup = org + q[3] * (x[:, None] * cd + zs[:, None] * nd)
    inf = org + q[3] * (x[:, None] * cd + zi[:, None] * nd)
    return sup, inf


def _corta_em(x, A, xc):
    k = int(np.searchsorted(x, xc))
    k = min(max(k, 1), len(x) - 1)
    f = (xc - x[k - 1]) / (x[k] - x[k - 1]) if x[k] > x[k - 1] else 0.0
    f = min(max(f, 0.0), 1.0)
    ponta = A[k - 1] + f * (A[k] - A[k - 1])
    return np.vstack([A[:k], ponta[None, :]])


def _reamostra(A, n):
    d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(A, axis=0), axis=1))]
    u = np.linspace(0.0, d[-1], n)
    return np.stack([np.interp(u, d, A[:, c]) for c in range(3)], axis=1)


def _curvas(sup, inf, x, xc, modo, nh=32):
    s = _reamostra(_corta_em(x, sup, xc), nh)
    i = _reamostra(_corta_em(x, inf, xc), nh)
    if modo == "separado":
        return [("extradorso", s), ("intradorso", i)]
    return [("envolvente", np.vstack([i[::-1], s[1:]]))]


def _triangulos(m1, nk):
    T = []
    for j in range(m1 - 1):
        for k in range(nk - 1):
            a, b, c, d = j * nk + k, j * nk + k + 1, (j + 1) * nk + k + 1, (j + 1) * nk + k
            T += [[a, b, c], [a, c, d]]
    return np.array(T, int)


def _locais(P, T):
    p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    e1 = p1 - p0
    l1 = np.linalg.norm(e1, axis=1)
    u = e1 / np.maximum(l1[:, None], 1e-15)
    n = np.cross(e1, p2 - p0)
    n /= np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-15)
    v = np.cross(n, u)
    d2 = p2 - p0
    return np.c_[np.zeros(len(T)), np.zeros(len(T))], np.c_[l1, np.zeros(len(T))], np.c_[np.einsum("ij,ij->i", d2, u), np.einsum("ij,ij->i", d2, v)]


def _lscm(P, T, pin):
    N = len(P)
    a, b, c = _locais(P, T)
    x1, y1, x2, y2, x3, y3 = a[:, 0], a[:, 1], b[:, 0], b[:, 1], c[:, 0], c[:, 1]
    A2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
    w = 1.0 / np.sqrt(np.maximum(np.abs(A2), 1e-18))
    ca = np.c_[y2 - y3, y3 - y1, y1 - y2]
    cb = np.c_[x3 - x2, x1 - x3, x2 - x1]
    rows, cols, vals = [], [], []
    nt = len(T)
    for r in range(3):
        idx = T[:, r]
        rows += [np.arange(nt), np.arange(nt), nt + np.arange(nt), nt + np.arange(nt)]
        cols += [idx, N + idx, idx, N + idx]
        vals += [w * ca[:, r], -w * cb[:, r], w * cb[:, r], w * ca[:, r]]
    M = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(2 * nt, 2 * N)).tocsr()
    fixos = np.array([pin[0][0], pin[1][0], N + pin[0][0], N + pin[1][0]])
    valf = np.array([pin[0][1][0], pin[1][1][0], pin[0][1][1], pin[1][1][1]])
    livres = np.setdiff1d(np.arange(2 * N), fixos)
    Ml, Mf = M[:, livres], M[:, fixos]
    sol = spsolve((Ml.T @ Ml).tocsc(), Ml.T @ (-(Mf @ valf)))
    z = np.zeros(2 * N)
    z[livres] = sol
    z[fixos] = valf
    return np.c_[z[:N], z[N:]]


def _angulos(P, T):
    p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    def ang(u, v, w):
        a, b = v - u, w - u
        c = np.einsum("ij,ij->i", a, b) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-15)
        return np.arccos(np.clip(c, -1.0, 1.0))
    return ang(p0, p1, p2), ang(p1, p2, p0), ang(p2, p0, p1)


def _areas(P, T):
    return 0.5 * np.linalg.norm(np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]), axis=1)


def _areas2(Q, T):
    a, b = Q[T[:, 1]] - Q[T[:, 0]], Q[T[:, 2]] - Q[T[:, 0]]
    return 0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])


def achata(G):
    m1, nk, _ = G.shape
    P = G.reshape(-1, 3)
    T = _triangulos(m1, nk)
    p_a = 0
    d_ = np.linalg.norm(P[:nk] - P[p_a], axis=1)
    p_b = int(np.argmax(d_))
    dist = float(d_[p_b])
    Q = _lscm(P, T, [(p_a, (0.0, 0.0)), (p_b, (dist, 0.0))])
    ia = [(0, 1), (1, 2), (2, 0)]
    E = np.vstack([T[:, list(e)] for e in ia])
    E = np.unique(np.sort(E, axis=1), axis=0)
    l3 = np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1)
    l2 = np.linalg.norm(Q[E[:, 0]] - Q[E[:, 1]], axis=1)
    s = float(np.sum(l3 * l2) / np.sum(l2 * l2))
    Q = Q * s
    l2 = l2 * s
    eps = (l2 / np.maximum(l3, 1e-15) - 1.0) * 100.0
    A3, A2 = _areas(P, T), _areas2(Q, T)
    var_area = (A2 / np.maximum(A3, 1e-18) - 1.0) * 100.0
    a0, a1, a2 = _angulos(P, T)
    soma = np.zeros(len(P))
    for ang, col in ((a0, 0), (a1, 1), (a2, 2)):
        np.add.at(soma, T[:, col], ang)
    interior = np.zeros((m1, nk), bool)
    interior[1:-1, 1:-1] = True
    defeito = np.where(interior.ravel(), 2.0 * math.pi - soma, 0.0)
    ed = {(int(a), int(b)): i for i, (a, b) in enumerate(E)}
    estr_tri = np.array([max(abs(eps[ed[tuple(sorted((int(T[t, u]), int(T[t, v]))))]]) for u, v in ia) for t in range(len(T))])
    return {"Q": Q, "T": T, "P": P, "eps": eps, "estr_tri": estr_tri, "var_area_pct": var_area, "defeito": defeito, "area3": float(A3.sum()), "area2": float(A2.sum())}


def _rotaciona(Q, nk, m1):
    G = Q.reshape(m1, nk, 2)
    d = G[:, -1].mean(axis=0) - G[:, 0].mean(axis=0)
    a = -math.atan2(d[1], d[0]) if np.linalg.norm(d) > 1e-9 else 0.0
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    Q = Q @ R.T
    return Q - Q.min(axis=0)


def _contorno(Q, m1, nk, margem):
    G = Q.reshape(m1, nk, 2)
    def desloca(borda, centro):
        t = np.gradient(borda, axis=0)
        n = np.c_[t[:, 1], -t[:, 0]]
        n /= np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-15)
        sinal = np.sign(np.einsum("ij,ij->i", n, borda - centro).mean()) or 1.0
        return borda + sinal * margem * n
    c = G.reshape(-1, 2).mean(axis=0)
    b0, bm = G[0], G[-1]
    if margem > 0:
        b0, bm = desloca(b0, c), desloca(bm, c)
    ponta_fim = [G[j, -1] for j in range(1, m1 - 1)]
    ponta_ini = [G[j, 0] for j in range(m1 - 2, 0, -1)]
    return np.vstack([b0, np.array(ponta_fim).reshape(-1, 2), bm[::-1], np.array(ponta_ini).reshape(-1, 2)])


def mapa_triangulos(esq: dict, el: dict, nome: str, faixas_: list, xcf) -> dict:
    V, T, lab, zn, _ = AG._TIPOS["asa"](el, nome, {**esq, "_info": {}})
    V = np.asarray(V, float)
    T = np.asarray(T, int)
    lab = np.asarray(lab, int)
    pele = np.isin(lab, [i for i, n in enumerate(zn) if n in ("extradorso", "intradorso")])
    c = V[T].mean(axis=1)
    sec = AG._secoes(el)
    cache = {}
    def secao(y):
        k = round(float(y), 6)
        if k not in cache:
            q = AG._secao_em(sec, float(y))
            cache[k] = (q[0], q[3])
        return cache[k]
    saida = np.zeros(len(T), int)
    for i in np.flatnonzero(pele):
        y = float(c[i, 1])
        xle, corda = secao(y)
        xc = (float(c[i, 0]) - xle) / corda if corda > 0 else 9.0
        if xc > xcf(y) + 1e-9:
            continue
        for modo_y in (False, True):
            yy = abs(y) if modo_y else y
            achou = next((k for k, f in enumerate(faixas_, 1) if f["y0_m"] - 1e-9 <= yy <= f["y1_m"] + 1e-9), 0)
            if achou:
                saida[i] = achou
                break
    rle = []
    for v in saida:
        v = int(v)
        if rle and rle[-1][0] == v:
            rle[-1][1] += 1
        else:
            rle.append([v, 1])
    return {"n": int(len(T)), "rle": rle}


def faixas(esq: dict, nome_asa: str, modo: str = "auto", n_vao: int = 6, limite_pct=None, margem_cola_mm: float = 5.0, xc=None, cortes_y=None, modos=None) -> dict:
    el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome_asa and e.get("tipo") == "asa"), None)
    if el is None:
        raise ValueError(f"asa {nome_asa!r} nao existe no modelo")
    cfg = el.get("estrutura") or {}
    ch = cfg.get("chapeado") or {}
    if xc is None and not ch:
        raise ValueError(f"a asa {nome_asa!r} nao tem chapeado declarado (estrutura.chapeado); informe ate onde a pele vai (x/c)")
    pares = None if xc is not None else ch.get("ate_xc_y")
    if pares:
        py = np.array([abs(float(a)) for a, _ in pares])
        px = np.array([float(b) for _, b in pares])
        o = np.argsort(py)
        py, px = py[o], px[o]
        def xcf(y):
            return float(np.interp(abs(y), py, px))
    else:
        c0 = float(xc if xc is not None else ch.get("ate_xc", 0.25))
        def xcf(y):
            return c0
    xc = max(xcf(0.0), 0.0)
    for y_ in (0.0, 1.0):
        if not 0.02 <= xcf(y_) <= 1.0:
            raise ValueError("a pele deve ir ate um x/c entre 0,02 e 1")
    if modo not in ("auto", "envolvente", "separado"):
        raise ValueError("modo: auto, envolvente ou separado")
    n_vao = int(n_vao)
    if not 2 <= n_vao <= 24:
        raise ValueError("divisoes por faixa entre 2 e 24")
    material = ch.get("material", "balsa")
    lim = limite_do_material(material, limite_pct)
    sec, x, Z = _perfis(el, esq)
    ys = [q[1] for q in sec]
    nv = cfg.get("nervuras")
    lista = [float(v) for v in AG._nervuras_y((nv or {}).get("y") or ys, ys)] if nv else list(map(float, ys))
    if cortes_y:
        simetrica = any(q < -1e-9 for q in ys)
        pts = {float(min(ys)), float(max(ys))}
        for c in cortes_y:
            c = float(c)
            if not min(ys) - 1e-9 <= c <= max(ys) + 1e-9 and not (simetrica and min(ys) - 1e-9 <= -c <= max(ys) + 1e-9):
                raise ValueError(f"corte em y = {c:g} m fora da asa ({min(ys):g} a {max(ys):g} m)")
            pts.add(c)
            if simetrica and min(ys) - 1e-9 <= -c <= max(ys) + 1e-9:
                pts.add(-c)
        lista = list(pts)
    lista = sorted(set(round(v, 9) for v in lista))
    if len(lista) < 2:
        raise ValueError("preciso de pelo menos duas nervuras (ou secoes) para formar uma faixa")
    pares = list(zip(lista, lista[1:]))
    avisos, faixas_, vistos = [], [], set()
    if cfg.get("angulos") or (nv or {}).get("angulo") or (nv or {}).get("angulos"):
        avisos.append("nervuras inclinadas: as faixas seguem as estacoes em y, nao o plano inclinado de cada nervura")
    for y0, y1 in pares:
        ym = 0.5 * (y0 + y1)
        if ym < -1e-9:
            continue
        espelho = any(abs(a + y1) < 1e-6 and abs(b + y0) < 1e-6 for a, b in pares)
        qtd = 2 if (espelho and ym > 1e-9) else 1
        ysb = np.linspace(y0, y1, n_vao + 1)
        S = [tuple(1000.0 * a for a in _pontos_secao(sec, x, Z, y)) for y in ysb]
        def resolve(m):
            pecas = []
            cs = [_curvas(sp, ip, x, xcf(yy), m) for (sp, ip), yy in zip(S, ysb)]
            for c_ in range(len(cs[0])):
                G = np.stack([cs[j][c_][1] for j in range(len(cs))])
                R = achata(G)
                pecas.append((cs[0][c_][0], G.shape[0], G.shape[1], R))
            return pecas
        def pior(pecas):
            return max(float(np.nan_to_num(np.abs(R["eps"]).max(), nan=1e9)) for _, _, _, R in pecas)
        modo_f = (modos or {}).get(str(int(round(1000.0 * y0))), modo)
        if modo_f not in ("auto", "envolvente", "separado"):
            raise ValueError("modo de uma faixa: auto, envolvente ou separado")
        escolhido = "envolvente" if modo_f in ("auto", "envolvente") else "separado"
        pecas = resolve(escolhido)
        if modo_f == "auto" and pior(pecas) > lim:
            alt = resolve("separado")
            if pior(alt) < 0.7 * pior(pecas):
                pecas, escolhido = alt, "separado"
        err = pior(pecas)
        status = "ok" if err <= lim else ("atencao" if err <= 4.0 * lim else "nao")
        saida = []
        for nome_p, m1, nk, R in pecas:
            Q = _rotaciona(R["Q"], nk, m1)
            saida.append({"nome": nome_p, "contorno": _contorno(Q, m1, nk, margem_cola_mm).round(3).tolist(), "linha_bordo_ataque": None,
                          "v": Q.round(3).tolist(), "t": R["T"].tolist(), "estr": R["estr_tri"].round(4).tolist(), "m1": int(m1), "nk": int(nk),
                          "largura_mm": float(Q[:, 0].max()), "altura_mm": float(Q[:, 1].max()), "area_mm2": float(R["area2"]), "area3d_mm2": float(R["area3"]),
                          "deformacao_max_pct": float(np.abs(R["eps"]).max()), "deformacao_media_pct": float(np.abs(R["eps"]).mean()),
                          "defeito_angular_max_graus": float(np.degrees(np.abs(R["defeito"]).max())), "curvatura_total_rad": float(R["defeito"].sum()),
                          "var_area_max_pct": float(np.abs(R["var_area_pct"]).max())})
            if nome_p == "envolvente":
                kle = int(round((nk - 1) / 2))
                G2 = Q.reshape(m1, nk, 2)
                saida[-1]["linha_bordo_ataque"] = G2[:, kle].round(3).tolist()
        faixas_.append({"y0_m": y0, "y1_m": y1, "quantidade": qtd, "modo": escolhido, "modo_pedido": modo_f, "chave": str(int(round(1000.0 * y0))), "status": status, "deformacao_max_pct": err, "pecas": saida,
                        "largura_vao_mm": 1000.0 * (y1 - y0)})
    if not faixas_:
        raise ValueError("nenhuma faixa no semi-vao positivo")
    mapa = mapa_triangulos(esq, el, nome_asa, faixas_, xcf)
    return {"mapa": mapa, "asa": nome_asa, "material": material, "limite_pct": lim, "ate_xc": float(xc), "n_vao": n_vao, "margem_cola_mm": float(margem_cola_mm), "faixas": faixas_, "avisos": avisos}


def organiza(conj: dict, folha_mm=(1000.0, 300.0), espaco_mm: float = 6.0, margem_mm: float = 5.0) -> dict:
    W, H = float(folha_mm[0]), float(folha_mm[1])
    itens = []
    for i, f in enumerate(conj["faixas"], 1):
        for p in f["pecas"]:
            C = np.array(p["contorno"])
            itens.append({"rot": f"F{i:02d}" + ("" if p["nome"] == "envolvente" else "-" + p["nome"][:3]), "faixa": i, "p": p, "C": C - C.min(axis=0), "w": float(np.ptp(C[:, 0])), "h": float(np.ptp(C[:, 1])), "n": f["quantidade"]})
    itens.sort(key=lambda t: -t["h"])
    avisos, folha, x, y, alt = [], 0, margem_mm, margem_mm, 0.0
    cols = []
    for it in itens:
        for c_ in range(it["n"]):
            w, h = it["w"], it["h"]
            if w + 2 * margem_mm > W or h + 2 * margem_mm > H:
                avisos.append(f"{it['rot']}: peca de {w:.0f} x {h:.0f} mm nao cabe na folha de {W:.0f} x {H:.0f} mm")
            if x + w + margem_mm > W and x > margem_mm:
                x, y, alt = margem_mm, y + alt + espaco_mm, 0.0
            if y + h + margem_mm > H and y > margem_mm:
                folha += 1
                x, y, alt = margem_mm, margem_mm, 0.0
            cols.append({"item": it, "copia": c_, "folha": folha, "pos": (x, y), "espelho": c_ == 1})
            x += w + espaco_mm
            alt = max(alt, h)
    return {"colocados": cols, "folhas": (max((c["folha"] for c in cols), default=-1) + 1), "folha_mm": [W, H], "avisos": avisos}


def dxf(conj: dict, org: dict, folha=True, rotulos=True, altura_texto_mm: float = 4.0) -> str:
    d = Dxf({**CAMADAS, "MARCAS": 4})
    W, H = org["folha_mm"]
    for k in range(org["folhas"]):
        if folha:
            ox = k * (W + 20.0)
            d.polilinha([(ox, 0), (ox + W, 0), (ox + W, H), (ox, H)], "FOLHA")
    for c in org["colocados"]:
        it = c["item"]
        ox, oy = c["pos"][0] + c["folha"] * (W + 20.0), c["pos"][1]
        C = it["C"].copy()
        p = it["p"]
        origem = np.array(p["contorno"]).min(axis=0)
        def tr(Z):
            Z = np.asarray(Z, float) - origem
            if c["espelho"]:
                Z = np.c_[it["w"] - Z[:, 0], Z[:, 1]]
            return Z + np.array([ox, oy])
        d.polilinha(tr(np.array(p["contorno"])).tolist(), "CORTE")
        if p.get("linha_bordo_ataque"):
            d.polilinha(tr(p["linha_bordo_ataque"]).tolist(), "MARCAS", fechada=False)
        if rotulos:
            ctr = tr(np.array(p["contorno"])).mean(axis=0)
            d.texto(ctr[0] - 8.0, ctr[1] - 0.5 * altura_texto_mm, it["rot"] + (" (esp.)" if c["espelho"] else ""), altura_texto_mm, "GRAVACAO")
    return d.texto_dxf()
