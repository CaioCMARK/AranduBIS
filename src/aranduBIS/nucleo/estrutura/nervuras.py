from __future__ import annotations

import math

import numpy as np

from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from ..modelador.dxf import Dxf

EPS = 1e-9

def _area(P):
    return 0.5 * float(np.dot(P[:, 0], np.roll(P[:, 1], -1)) - np.dot(P[:, 1], np.roll(P[:, 0], -1)))

def _normais(P):
    d1 = P - np.roll(P, 1, axis=0)
    d2 = np.roll(P, -1, axis=0) - P
    n1 = np.c_[d1[:, 1], -d1[:, 0]]
    n2 = np.c_[d2[:, 1], -d2[:, 0]]
    n1 /= np.maximum(np.linalg.norm(n1, axis=1, keepdims=True), EPS)
    n2 /= np.maximum(np.linalg.norm(n2, axis=1, keepdims=True), EPS)
    n = n1 + n2
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), EPS)
    cos = np.clip(np.sum(n * n1, axis=1), 0.35, 1.0)
    return n / cos[:, None]

def desloca(P, d):
    return P + d * _normais(P)

def _recorta_x(P, xv, maior):
    dentro = (lambda p: p[0] >= xv - EPS) if maior else (lambda p: p[0] <= xv + EPS)
    out = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        da, db = dentro(a), dentro(b)
        if da:
            out.append(a)
        if da != db and abs(b[0] - a[0]) > EPS:
            t = (xv - a[0]) / (b[0] - a[0])
            out.append(a + t * (b - a))
    return np.array(out) if len(out) >= 3 else np.zeros((0, 2))

def _recesso(P, x_lim, t):
    if t <= 0:
        return P
    pts = []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        pts.append(a)
        if (a[0] - x_lim) * (b[0] - x_lim) < 0:
            pts.append(a + (x_lim - a[0]) / (b[0] - a[0]) * (b - a))
    Q = np.array(pts)
    N = _normais(Q)
    dentro = Q[:, 0] <= x_lim + EPS
    novo = []
    m = len(Q)
    for i in range(m):
        v = Q[i]
        if abs(v[0] - x_lim) < 1e-7:
            ant = Q[i - 1]
            interno = Q[i] + t * N[i] * -1.0
            if ant[0] > x_lim + EPS:
                novo += [v, interno]
            else:
                novo += [interno, v]
        elif dentro[i]:
            novo.append(v - t * N[i])
        else:
            novo.append(v)
    return np.array(novo)

def _distancia_ao_contorno(P, c):
    A, B = P, np.roll(P, -1, axis=0)
    AB = B - A
    t = np.clip(np.einsum("ij,ij->i", c - A, AB) / np.maximum(np.einsum("ij,ij->i", AB, AB), EPS), 0.0, 1.0)
    return float(np.min(np.linalg.norm(A + t[:, None] * AB - c, axis=1)))

def _dentro(P, c):
    x, z = c
    inside = False
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        if (a[1] > z) != (b[1] > z) and x < a[0] + (z - a[1]) / (b[1] - a[1]) * (b[0] - a[0]):
            inside = not inside
    return inside

def _entalhe(P, xt, zc, r, cima, passos=18):
    xa, xb = (xt + r, xt - r) if cima else (xt - r, xt + r)
    def acha(Q, xv, k0=0):
        for k in range(k0, len(Q)):
            a, b = Q[k], Q[(k + 1) % len(Q)]
            vai = (a[0] > xv > b[0]) if cima else (a[0] < xv < b[0])
            if vai:
                z = a[1] + (xv - a[0]) / (b[0] - a[0]) * (b[1] - a[1])
                if (z > zc) if cima else (z < zc):
                    return k, np.array([xv, z])
        return None, None
    ka, pa = acha(P, xa)
    if ka is None:
        return P
    P2 = np.roll(P, -(ka + 1), axis=0)
    kb, pb = acha(P2, xb)
    if kb is None:
        return P
    resto = P2[kb + 1:]
    f = np.linspace(0.0, np.pi, passos)
    if cima:
        arco = np.c_[xt + r * np.cos(f), zc - r * np.sin(f)]
    else:
        arco = np.c_[xt - r * np.cos(f), zc + r * np.sin(f)]
    return np.vstack([resto, pa, arco, pb])

def _grupos_de_tubos(cfg, y, c_m, x, zs, zi, folga_mm, tol=1e-6):
    achados = {}
    for tb in cfg.get("tubos", []):
        y0, y1 = tb.get("y") or [-1e9, 1e9]
        if not (min(y0, y1) - tol <= y <= max(y0, y1) + tol):
            continue
        de = float(tb["de"])
        xc = ES.posicao_x(tb, c_m, y) / c_m
        lado = tb.get("lado", "extradorso")
        zsup, zinf = float(np.interp(xc, x, zs)), float(np.interp(xc, x, zi))
        z = 0.5 * (zsup + zinf) if lado == "meio" else zsup - 0.5 * de / c_m if lado == "extradorso" else zinf + 0.5 * de / c_m
        k = (round(xc * c_m, 6), lado)
        if k not in achados or de * 1000.0 + folga_mm > achados[k][2]:
            achados[k] = (xc * c_m * 1000.0, z * c_m * 1000.0, de * 1000.0 + folga_mm, lado)
    return list(achados.values())

def nervura(esq: dict, el: dict, y: float, kerf_mm: float = 0.0, folga_tubo_mm: float = 0.1, folga_longarina_mm: float = 0.1,
            bf_min_mm: float = 1.0, recesso_chapeado: bool = True, parede_min_mm: float = 1.2, avisos: list | None = None, rot: str = "N",
            angulo_graus: float = 0.0) -> list[dict]:
    avisos = avisos if avisos is not None else []
    if abs(angulo_graus) >= 80.0:
        raise ValueError("angulo da nervura deve ficar entre -80 e 80 graus")
    kx = 1.0 / math.cos(math.radians(angulo_graus))
    cfg = el.get("estrutura") or {}
    sec = AG._secoes(el)
    ys = [q[1] for q in sec]
    n = int(el.get("n_perfil", 40))
    if AG._quer_aneis(el):
        x, Z = AG._perfis_secoes(el, esq)
    else:
        x, zs_, zi_ = ES.perfil_xy(el.get("perfil", "NACA 0012"), n, esq.get("_pasta", "."))
        Z = [(zs_, zi_)] * len(sec)
    q = AG._secao_em(sec, y)
    i, t = AG._no_vao(sec, y)
    zs = (1 - t) * Z[i][0] + t * Z[i + 1][0]
    zi = (1 - t) * Z[i][1] + t * Z[i + 1][1]
    c_m = q[3]
    c = c_m * 1000.0
    X, Zs, Zi = x * c * kx, zs * c, zi * c
    esp = Zs - Zi
    cheios = np.where(esp >= bf_min_mm)[0]
    kmax = int(cheios[-1]) if len(cheios) else len(X) - 1
    if kmax < len(X) - 1 and len(cheios):
        f = (bf_min_mm - esp[kmax]) / (esp[kmax + 1] - esp[kmax])
        xc_ = X[kmax] + f * (X[kmax + 1] - X[kmax])
        zs_c, zi_c = Zs[kmax] + f * (Zs[kmax + 1] - Zs[kmax]), Zi[kmax] + f * (Zi[kmax + 1] - Zi[kmax])
        X, Zs, Zi = np.r_[X[:kmax + 1], xc_], np.r_[Zs[:kmax + 1], zs_c], np.r_[Zi[:kmax + 1], zi_c]
    P = np.vstack([np.c_[X, Zs][::-1], np.c_[X[1:], Zi[1:]]])
    if _area(P) < 0:
        P = P[::-1]
    ch = cfg.get("chapeado") or {}
    if recesso_chapeado and ch and float(ch.get("espessura", 0)) > 0:
        P = _recesso(P, float(ch.get("ate_xc", 0.0)) * c * kx, float(ch["espessura"]) * 1000.0)
    cortes = []
    for lg in cfg.get("longarinas", []):
        y0, y1 = lg.get("y") or [ys[0], ys[-1]]
        if not (min(y0, y1) - 1e-6 <= y <= max(y0, y1) + 1e-6):
            continue
        xl = ES.posicao_x(lg, c_m, y) * 1000.0 * kx
        h = 0.5 * (float(lg.get("largura", 0.00238)) * 1000.0 * kx + folga_longarina_mm)
        if P[:, 0].min() < xl - h and xl + h < P[:, 0].max():
            cortes.append((xl - h, xl + h))
        else:
            avisos.append(f"{rot}: a longarina em x = {xl:.1f} mm cai fora do perfil nessa estacao e foi ignorada")
    cortes.sort()
    faixas, a = [], P[:, 0].min() - 1.0
    for lo, hi in cortes:
        faixas.append((a, lo))
        a = hi
    faixas.append((a, P[:, 0].max() + 1.0))
    r_tubos = []
    for tb in _grupos_de_tubos(cfg, y, c_m, x, zs, zi, folga_tubo_mm):
        tb = (tb[0] * kx, tb[1], tb[2], tb[3])
        xt, d = tb[0], tb[2]
        if any(lo - 0.5 * d < xt < hi + 0.5 * d for lo, hi in cortes):
            avisos.append(f"Tubo de {d - folga_tubo_mm:.1f} mm em x = {xt:.1f} mm coincide com o rasgo da longarina: a alma ocupa o lugar e a nervura nao leva furo nem entalhe ali.")
        else:
            r_tubos.append(tb)
    saida = []
    for k, (a, b) in enumerate(faixas):
        Q = _recorta_x(_recorta_x(P, a, True), b, False)
        if len(Q) < 3 or abs(_area(Q)) < 1.0:
            continue
        if _area(Q) < 0:
            Q = Q[::-1]
        furos = []
        for xt, zt, d, lado in r_tubos:
            r = 0.5 * d * kx
            if not (a < xt < b):
                continue
            if xt - r < a or xt + r > b:
                avisos.append(f"{rot}: tubo em x = {xt:.1f} mm toca a borda da peca (rasgo da longarina ou ponta); verifique a montagem")
                continue
            if _dentro(Q, (xt, zt)) and _distancia_ao_contorno(Q, np.array([xt, zt])) - r >= parede_min_mm:
                furos.append({"c": [float(xt), float(zt)], "d": float(d), "dx": float(d * kx)})
            else:
                cima = lado == "extradorso" or (lado == "meio" and zt > float(np.interp(xt, X, 0.5 * (Zs + Zi))))
                Q = _entalhe(Q, xt, zt, r, cima)
        area = abs(_area(Q)) - sum(np.pi * 0.25 * f["d"] * f["dx"] for f in furos)
        if kerf_mm:
            Q = desloca(Q, 0.5 * kerf_mm)
            for f in furos:
                f["d"] = max(f["d"] - kerf_mm, 0.1)
                f["dx"] = max(f["dx"] - kerf_mm, 0.1)
        nome = rot + ("" if len(faixas) == 1 else "ABCDEFGH"[k])
        saida.append({"nome": nome, "contorno": Q.tolist(), "furos": furos, "x0": float(Q[:, 0].min()), "x1": float(Q[:, 0].max()),
                      "z0": float(Q[:, 1].min()), "z1": float(Q[:, 1].max()), "area_mm2": float(area)})
    return saida

def pecas(esq: dict, nome_asa: str, **kw) -> dict:
    el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome_asa and e.get("tipo") == "asa"), None)
    if el is None:
        raise ValueError(f"asa {nome_asa!r} nao existe no modelo")
    nv = (el.get("estrutura") or {}).get("nervuras")
    if not nv:
        raise ValueError(f"a asa {nome_asa!r} nao tem nervuras declaradas (estrutura.nervuras.y)")
    ys = [q[1] for q in AG._secoes(el)]
    lista = AG._nervuras_y(nv["y"], ys)
    avisos, nervs = [], []
    for k, y in enumerate(lista, 1):
        ang = AG._angulo_nervura(nv, y, ys)
        ps = nervura(esq, el, y, avisos=avisos, rot=f"N{k:02d}", angulo_graus=ang, **kw)
        q = AG._secao_em(AG._secoes(el), y)
        nervs.append({"i": k, "y_m": float(y), "corda_mm": 1000.0 * q[3], "ainc": float(q[4]), "angulo": float(ang), "pecas": ps})
    avisos = list(dict.fromkeys(avisos))
    return {"asa": nome_asa, "espessura_mm": 1000.0 * float(nv.get("espessura", 0.00238)), "material": nv.get("material", "balsa"),
            "nervuras": nervs, "avisos": avisos}

def organiza(conj: dict, folha_mm=(600.0, 300.0), espaco_mm: float = 4.0, margem_mm: float = 5.0) -> dict:
    W, H = float(folha_mm[0]), float(folha_mm[1])
    todas = [p for n in conj["nervuras"] for p in n["pecas"]]
    todas.sort(key=lambda p: -(p["z1"] - p["z0"]))
    folhas, folha, x, y, alt_linha = [], 0, margem_mm, margem_mm, 0.0
    avisos = []
    for p in todas:
        w, h = p["x1"] - p["x0"], p["z1"] - p["z0"]
        if w + 2 * margem_mm > W or h + 2 * margem_mm > H:
            avisos.append(f"{p['nome']}: peca de {w:.0f} x {h:.0f} mm nao cabe na folha de {W:.0f} x {H:.0f} mm")
        if x + w + margem_mm > W and x > margem_mm:
            x, y, alt_linha = margem_mm, y + alt_linha + espaco_mm, 0.0
        if y + h + margem_mm > H and y > margem_mm:
            folha += 1
            x, y, alt_linha = margem_mm, margem_mm, 0.0
        p["folha"] = folha
        p["pos"] = [x - p["x0"], y - p["z0"]]
        x += w + espaco_mm
        alt_linha = max(alt_linha, h)
    n = (max((p["folha"] for p in todas), default=-1) + 1)
    return {"folhas": n, "folha_mm": [W, H], "avisos": avisos}

def dxf(conj: dict, org: dict, folha=True, rotulos=True, altura_texto_mm: float = 3.0, parede_min_mm: float = 1.2) -> str:
    d = Dxf()
    W, H = org["folha_mm"]
    for k in range(org["folhas"]):
        if folha:
            ox = k * (W + 20.0)
            d.polilinha([(ox, 0), (ox + W, 0), (ox + W, H), (ox, H)], "FOLHA")
    for n in conj["nervuras"]:
        for p in n["pecas"]:
            ox, oy = p["pos"][0] + p["folha"] * (W + 20.0), p["pos"][1]
            d.polilinha([(x + ox, z + oy) for x, z in p["contorno"]], "CORTE")
            for f in p["furos"]:
                if f.get("dx", f["d"]) > f["d"] + 1e-6:
                    a, b = 0.5 * f["dx"], 0.5 * f["d"]
                    d.polilinha([(f["c"][0] + ox + a * math.cos(s), f["c"][1] + oy + b * math.sin(s)) for s in np.linspace(0.0, 2.0 * math.pi, 49)[:-1]], "CORTE")
                else:
                    d.circulo(f["c"][0] + ox, f["c"][1] + oy, f["d"], "CORTE")
            if rotulos:
                rot = f"{p['nome']} y={n['y_m'] * 1000:+.0f}"
                xm = 0.5 * (p["x0"] + p["x1"])
                alt = p["z1"] - p["z0"]
                largura_txt = len(rot) * 0.8 * altura_texto_mm
                cabe = alt >= 3.2 * altura_texto_mm and (p["x1"] - p["x0"]) >= largura_txt + 2.0 and not any(abs(f["c"][0] - xm) < 0.5 * largura_txt + 0.5 * f["d"] for f in p["furos"])
                if cabe:
                    d.texto(xm - 0.5 * largura_txt + ox, 0.5 * (p["z0"] + p["z1"]) + oy - 0.5 * altura_texto_mm, rot, altura_texto_mm, "GRAVACAO")
                else:
                    d.texto(p["x0"] + ox, p["z0"] + oy - 1.4 * altura_texto_mm, rot, altura_texto_mm, "ROTULO")
    return d.texto_dxf()


def posicoes(esq: dict, nome_asa: str, n: int, lei: str = "uniforme", expoente: float = 1.6) -> dict:
    el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome_asa and e.get("tipo") == "asa"), None)
    if el is None:
        raise ValueError(f"asa {nome_asa!r} nao existe no modelo")
    n = int(n)
    if n < 2:
        raise ValueError("o numero de nervuras deve ser pelo menos 2")
    if n > 400:
        raise ValueError("o numero de nervuras deve ser no maximo 400")
    if lei not in ("uniforme", "raiz", "ponta", "secoes"):
        raise ValueError("distribuicao deve ser uniforme, raiz, ponta ou secoes")
    if not expoente > 0:
        raise ValueError("expoente deve ser positivo")
    ys = [q[1] for q in AG._secoes(el)]
    y0, y1 = ys[0], ys[-1]
    simetrica = y0 < -1e-9 and y1 > 1e-9 and abs(y0 + y1) < 1e-6 * max(abs(y0), abs(y1))
    lo, hi = (0.0, y1) if simetrica else (y0, y1)
    if lei == "secoes":
        est = sorted({round(abs(y) if simetrica else y, 9) for y in ys if lo - 1e-9 <= (abs(y) if simetrica else y) <= hi + 1e-9})
        valores = est
    else:
        u = np.linspace(0.0, 1.0, n)
        if lei == "raiz":
            u = u ** expoente
        elif lei == "ponta":
            u = 1.0 - (1.0 - u) ** expoente
        valores = [float(lo + s * (hi - lo)) for s in u]
    valores = [round(float(v), 6) for v in valores]
    completa = AG._nervuras_y(valores, ys)
    return {"y": valores, "simetrica": bool(simetrica), "completa": [float(v) for v in completa], "passos_mm": [1000.0 * float(b - a) for a, b in zip(completa, completa[1:])]}
