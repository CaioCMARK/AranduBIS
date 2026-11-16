import numpy as np
from collections import defaultdict

def normais_faces(V, T):
    N = []; A = []
    for t in T:
        Q = V[list(t)]; n = 0.5 * np.cross(Q, np.roll(Q, -1, axis=0)).sum(0); a = np.linalg.norm(n); N.append(n / a); A.append(a)
    return np.array(N), np.array(A)

def triangula(T):
    return np.array([[t[0], t[q], t[q + 1]] for t in T for q in range(1, len(t) - 1)])

def loft_asa(secoes, n_perfil=24, cod="4412", quads=False, dx_min=None, forma=None, anel=None):
    m, p, t = (int(cod[0]) / 100, int(cod[1]) / 10, int(cod[2:]) / 100) if forma is None else (0.0, 0.5, 0.0); b = np.linspace(0, np.pi, n_perfil); x = 0.5 * (1 - np.cos(b))
    if dx_min:
        k = [0]
        for i in range(1, len(x) - 1):
            if x[i] - x[k[-1]] >= dx_min and 1.0 - x[i] >= dx_min: k.append(i)
        x = x[k + [len(x) - 1]]; n_perfil = len(x)
    if forma is not None: x, yc, yt = forma(n_perfil); n_perfil = len(x); th = np.arctan(np.gradient(yc, x))
    else:
        yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        yc = np.where(x < p, m / p ** 2 * (2 * p * x - x ** 2), m / (1 - p) ** 2 * (1 - 2 * p + 2 * p * x - x ** 2)) if m > 0 else 0 * x
        dy = np.where(x < p, 2 * m / p ** 2 * (p - x), 2 * m / (1 - p) ** 2 * (p - x)) if m > 0 else 0 * x; th = np.arctan(dy)
    up = np.c_[x - yt * np.sin(th), yc + yt * np.cos(th)]; lo = np.c_[x + yt * np.sin(th), yc - yt * np.cos(th)]
    anel2d = np.vstack([up[::-1], lo[1:-1]]) if anel is None else np.asarray(anel, float); mA = len(anel2d); V = []

    for (xl, yl, zl, c, ai) in secoes:
        a = np.radians(ai); cd = np.array([np.cos(a), 0, -np.sin(a)]); nd = np.array([np.sin(a), 0, np.cos(a)])
        for (u, w) in anel2d: V.append(np.array([xl, yl, zl]) + c * (u * cd + w * nd))
    V = np.array(V); ns = len(secoes); T = []; idx = lambda j, k: j * mA + (k % mA)
    for j in range(ns - 1):
        for k in range(mA):
            if quads: T.append([idx(j, k), idx(j, k + 1), idx(j + 1, k + 1), idx(j + 1, k)])
            else: T += [[idx(j, k), idx(j, k + 1), idx(j + 1, k + 1)], [idx(j, k), idx(j + 1, k + 1), idx(j + 1, k)]]
    if anel is not None:
        orelhas = triangula_poligono(anel2d)
        for j in (0, ns - 1): T += [[idx(j, a), idx(j, b), idx(j, c)] for a, b, c in orelhas]
    for j in () if anel is not None else (0, ns - 1):
        U = lambda q: idx(j, n_perfil - 1 - q); L = lambda q: idx(j, n_perfil - 1 + q)
        for q in range(n_perfil - 1):
            pol = [U(q), U(q + 1), L(q + 1), L(q)]; u = [v for i, v in enumerate(pol) if v != pol[i - 1]]
            if quads and len(u) >= 3: T.append(u)
            elif not quads:
                for tri in ([U(q), U(q + 1), L(q + 1)], [U(q), L(q + 1), L(q)]):
                    if len(set(tri)) == 3: T.append(tri)
    return V, orienta(V, T)

def triangula_poligono(P):
    P = np.asarray(P, float); n = len(P); ind = list(range(n))
    A = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - P[:, 1] * np.roll(P[:, 0], -1))
    if A < 0: ind.reverse()
    cross = lambda o, a, b: (P[a, 0] - P[o, 0]) * (P[b, 1] - P[o, 1]) - (P[a, 1] - P[o, 1]) * (P[b, 0] - P[o, 0])
    T = []; guarda = 0
    while len(ind) > 3 and guarda < 10 * n * n:
        guarda += 1; m = len(ind); achou = False
        for i in range(m):
            a, b, c = ind[i - 1], ind[i], ind[(i + 1) % m]
            if cross(a, b, c) <= 1e-18: continue
            dentro = False
            for q in ind:
                if q in (a, b, c): continue
                if cross(a, b, q) >= 0 and cross(b, c, q) >= 0 and cross(c, a, q) >= 0: dentro = True; break
            if not dentro: T.append((a, b, c)); ind.pop(i); achou = True; break
        if not achou:
            ar = [abs(cross(ind[i - 1], ind[i], ind[(i + 1) % len(ind)])) for i in range(len(ind))]; ind.pop(int(np.argmin(ar)))
    if len(ind) == 3 and abs(cross(*ind)) > 1e-18: T.append(tuple(ind))
    return T

def orienta(V, T):
    T = [list(t) for t in T]; ar = defaultdict(list)
    for f, t in enumerate(T):
        for e in range(len(t)): a, b = t[e], t[(e + 1) % len(t)]; ar[(min(a, b), max(a, b))].append(f)
    visto = np.zeros(len(T), bool)
    for s in range(len(T)):
        if visto[s]: continue
        visto[s] = True; pilha = [s]
        while pilha:
            f = pilha.pop(); t = T[f]
            for e in range(len(t)):
                a, b = t[e], t[(e + 1) % len(t)]
                for g in ar[(min(a, b), max(a, b))]:
                    if visto[g]: continue
                    visto[g] = True; tg = T[g]
                    if any(tg[q] == a and tg[(q + 1) % len(tg)] == b for q in range(len(tg))): T[g] = tg[::-1]
                    pilha.append(g)
    tr = triangula(T); vol = np.sum(np.einsum("ij,ij->i", V[tr[:, 0]], np.cross(V[tr[:, 1]], V[tr[:, 2]]))) / 6
    T = T if vol > 0 else [t[::-1] for t in T]
    return np.array(T) if all(len(t) == 3 for t in T) else T

def _laco(arestas):
    cont = [e for e in arestas if (e[1], e[0]) not in arestas]
    if not cont: return None
    prox = {a: b for a, b in cont}
    if len(prox) != len(cont): return None
    a0 = cont[0][0]; laco = [a0]; a = prox[a0]
    while a != a0:
        laco.append(a); a = prox.get(a)
        if a is None or len(laco) > len(cont): return None
    return laco if len(laco) == len(cont) else None

def _medidas(pts):
    q = np.roll(pts, -1, axis=0); nv = np.sum(np.cross(pts, q), axis=0) / 2; A = float(np.linalg.norm(nv)); P = float(np.sum(np.linalg.norm(q - pts, axis=1)))
    if A <= 0 or P <= 0: return 0.0, np.inf
    n = nv / A; dev = float(np.abs((pts - pts.mean(0)) @ n).max()); return 4 * A / P, dev / np.sqrt(A)

def _funde(poli, posicao, y, fusao, tol_plano, max_membros, max_desvio=60.0):
    nl = len(y) - 1; arest = [{(c[q], c[(q + 1) % len(c)]) for q in range(len(c))} for _, c in poli]
    atual = [dict(membros=[i], laco=list(poli[i][1]), subs=[], fundida=False, arestas=arest[i]) for i in range(len(poli))]; niveis = [atual]
    for k in range(1, nl):
        grupos = [dict(membros=list(g["membros"]), laco=list(g["laco"]), subs=[g], fundida=False, arestas=set(g["arestas"])) for g in atual]
        dono = {e: i for i, g in enumerate(grupos) for e in g["arestas"]}; vivo = [True] * len(grupos); h = y[k + 1] - y[k]; L = k + 1

        def larg(g): return _medidas(np.array([posicao(c, L) for c in g["laco"]]))[0]
        fila = sorted((larg(g), i) for i, g in enumerate(grupos) if larg(g) < fusao * h)
        import heapq
        heapq.heapify(fila)
        while fila:
            w, i = heapq.heappop(fila)
            if not vivo[i]: continue
            g = grupos[i]
            if abs(larg(g) - w) > 1e-15 * max(1.0, w): continue
            viz = {}
            lc0 = g["laco"]
            for (a, b) in [(lc0[q], lc0[(q + 1) % len(lc0)]) for q in range(len(lc0))]:
                j = dono.get((b, a))
                if j is not None and j != i and vivo[j]: viz[j] = viz.get(j, 0.0) + float(np.linalg.norm(posicao(a, L) - posicao(b, L)))
            for j in sorted(viz, key=lambda j: -viz[j]):
                h2 = grupos[j]
                if len(g["membros"]) + len(h2["membros"]) > max_membros: continue
                ar = g["arestas"] | h2["arestas"]; lc = _laco(ar)
                if lc is None: continue
                wl, dv = _medidas(np.array([posicao(c, L) for c in lc]))
                if dv > tol_plano: continue
                subs2 = g["subs"] + h2["subs"]; cG = np.mean([posicao(c, L) for c in lc] + [posicao(c, L - 1) for c in lc], axis=0); pior = 0.0
                for sg in subs2:
                    pk = np.array([posicao(c, L - 1) for c in sg["laco"]]); cg = np.mean([posicao(c, L - 1) for c in sg["laco"]] + [posicao(c, L - 2) for c in sg["laco"]], axis=0)
                    nn = np.sum(np.cross(pk, np.roll(pk, -1, axis=0)), axis=0); nn = nn / max(np.linalg.norm(nn), 1e-300); v = cG - cg
                    pior = max(pior, np.degrees(np.arccos(min(1.0, abs(v @ nn) / max(np.linalg.norm(v), 1e-300)))))
                if pior > max_desvio: continue
                g2 = dict(membros=g["membros"] + h2["membros"], laco=lc, subs=subs2, fundida=True, arestas=ar)
                vivo[i] = vivo[j] = False; grupos.append(g2); vivo.append(True); n = len(grupos) - 1
                for e in ar: dono[e] = n
                if wl < fusao * h: heapq.heappush(fila, (wl, n))
                break
        atual = [g for g, v in zip(grupos, vivo) if v]; niveis.append(atual)
    return niveis

def celulas_fundidas(poli, ponto, posicao, y, fusao, tol_plano=0.3, max_membros=3, max_desvio=60.0, sentido="cima"):
    nl = len(y) - 1; y = np.asarray(y, float)
    if sentido == "cima":
        niveis = _funde(poli, posicao, y, fusao, tol_plano, max_membros, max_desvio)
    else:
        yr = y[-1] - y[::-1]; niveis = _funde(poli, lambda c, k: posicao(c, nl - k), yr, fusao, tol_plano, max_membros, max_desvio)
    cel, nivel, fundida, celula_topo = [], [], [], []

    def celula(G, k, t):
        lp = G["laco"]; n = len(lp)
        if sentido == "cima":
            baixo = [[ponto(c, k) for c in lp][::-1]] if (k == 0 or not G["subs"]) else [[ponto(c, k) for c in g["laco"]][::-1] for g in G["subs"]]
            alto = [[ponto(c, k + 1) for c in lp]]
        else:
            baixo = [[ponto(c, k) for c in lp][::-1]]; alto = [[ponto(c, k + 1) for c in lp]] if (k == nl - 1 or not G["subs"]) else [[ponto(c, k + 1) for c in g["laco"]] for g in G["subs"]]
        cel.append(baixo + alto + [[ponto(lp[q], k), ponto(lp[(q + 1) % n], k), ponto(lp[(q + 1) % n], k + 1), ponto(lp[q], k + 1)] for q in range(n)])
        nivel.append(k); fundida.append(G["fundida"]); celula_topo.append(t)
        for g in G["subs"]: celula(g, k - 1 if sentido == "cima" else k + 1, t)
    raizes = sorted(niveis[nl - 1], key=lambda G: min(G["membros"]))
    for G in raizes: celula(G, nl - 1 if sentido == "cima" else 0, min(G["membros"]))
    topo = [[ponto(c, nl) for c in G["laco"]] for G in raizes] if sentido == "cima" else [[ponto(c, nl) for c in cc] for _, cc in poli]
    return cel, np.array(nivel), np.array(fundida, bool), np.array(celula_topo), topo

def _externa(v, V, vizinhos):
    u = -np.mean([V[w] - V[v] for w in vizinhos[v]], axis=0); n = np.linalg.norm(u); return u / n if n > 0 else np.array([1.0, 0.0, 0.0])

def _slerp(a, b, t):
    c = np.clip(a @ b, -1, 1); th = np.arccos(c)
    if th < 1e-9: return a
    return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)

def _arco_externo(n1, n2, t, m):
    e = np.cross(n1, n2)
    if np.linalg.norm(e) > 1e-9:
        e = e / np.linalg.norm(e); m = m - (m @ e) * e
    m = m / np.linalg.norm(m)
    return _slerp(n1, m, 2 * t) if t <= 0.5 else _slerp(m, n2, 2 * t - 1)

def camada(V, T, y, ang_aresta=35.0, ang_leque=15.0, h_topo=None, fusao=None, tol_plano=0.3, max_membros=12, max_desvio=60.0):
    T = [list(t) for t in T]; nf, af = normais_faces(V, T); nv = len(V); arestas = defaultdict(list)
    for f, t in enumerate(T):
        for e in range(len(t)): a, b = t[e], t[(e + 1) % len(t)]; arestas[(min(a, b), max(a, b))].append(f)
    viva = {k: len(fs) == 2 and np.degrees(np.arccos(np.clip(nf[fs[0]] @ nf[fs[1]], -1, 1))) > ang_aresta for k, fs in arestas.items()}
    inc = defaultdict(list)
    for f, t in enumerate(T):
        for q in range(len(t)): inc[t[q]].append(f)
    retalho = {}; nret = {}
    for v in range(nv):
        fs = inc[v]; pai = {f: f for f in fs}
        def acha(f):
            while pai[f] != f: pai[f] = pai[pai[f]]; f = pai[f]
            return f
        for f in fs:
            for g in fs:
                if g <= f: continue
                comum = set(T[f]) & set(T[g])
                if len(comum) == 2:
                    a, b = sorted(comum)
                    if not viva[(a, b)]: pai[acha(f)] = acha(g)
        raizes = sorted({acha(f) for f in fs}); mapa = {r: i for i, r in enumerate(raizes)}; ns = []
        for r in raizes:
            w = np.zeros(3)
            for f in fs:
                if acha(f) != r: continue
                t = T[f]; q = t.index(v); a, b = V[t[(q + 1) % len(t)]] - V[v], V[t[(q - 1) % len(t)]] - V[v]; ang = np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1)); w += ang * nf[f]
            ns.append(w / np.linalg.norm(w))
        for f in fs: retalho[(v, f)] = mapa[acha(f)]
        nret[v] = np.array(ns)
    mmax = max(len(n) for n in nret.values()); assert mmax <= 3, f"vertice com {mmax} retalhos: nao suportado"
    giro = max([np.degrees(np.arccos(np.clip(nret[v][i] @ nret[v][j], -1, 1))) for v in range(nv) for i in range(len(nret[v])) for j in range(i + 1, len(nret[v]))] + [0])
    K = max(1, int(np.ceil(giro / ang_leque)))
    if h_topo:
        K = max(1, min(K, int(round(np.radians(giro) * y[-1] / h_topo))))
    vizinhos = defaultdict(set)
    for t in T:
        for q in range(len(t)): vizinhos[t[q]].add(t[(q + 1) % len(t)]); vizinhos[t[q]].add(t[(q - 1) % len(t)])
    col = {}; base = []; dirs = []

    def coluna(v, pesos):
        chave = (v, tuple(sorted((r, w) for r, w in pesos.items() if w > 0)))
        if chave not in col:
            d = sum(w * nret[v][r] for r, w in pesos.items()); nd = np.linalg.norm(d)
            rs = [(r, w) for r, w in pesos.items() if w > 0]
            if len(rs) == 2 and nd < 0.15 * sum(w for _, w in rs):
                (r1, w1), (r2, w2) = rs; d = _arco_externo(nret[v][r1], nret[v][r2], w2 / (w1 + w2), _externa(v, V, vizinhos))
            elif nd < 1e-12: d = nret[v][next(iter(pesos))]
            else: d = d / nd
            col[chave] = len(base); base.append(v); dirs.append(d)
        return col[chave]
    nl = len(y) - 1

    def ponto(c, k):
        if k == 0: return ("v", base[c])
        return ("c", c, k)
    cel = []; tipo = []; nivel = []; topo = []; poli = []; fundida = []; celula_topo = []

    def poe(faces_por_nivel, tp):
        for k in range(nl):
            cel.append(faces_por_nivel(k)); tipo.append(tp); nivel.append(k)
    for f, t in enumerate(T):
        c = [coluna(v, {retalho[(v, f)]: K}) for v in t]
        def faces_prisma(k, c=c):
            b = [ponto(ci, k) for ci in c]; s = [ponto(ci, k + 1) for ci in c]; n = len(c)
            return [b[::-1], s] + [[b[q], b[(q + 1) % n], s[(q + 1) % n], s[q]] for q in range(n)]
        if fusao is None: poe(faces_prisma, 0); topo.append([ponto(ci, nl) for ci in c])
        else: poli.append((0, c))
    for (a, b), fs in arestas.items():
        if not viva[(a, b)]: continue
        f1, f2 = fs; t1 = T[f1]; q = t1.index(a)
        if t1[(q + 1) % len(t1)] != b: a, b = b, a
        Ca = [coluna(a, {retalho[(a, f1)]: K - i, retalho[(a, f2)]: i}) for i in range(K + 1)]; Cb = [coluna(b, {retalho[(b, f1)]: K - i, retalho[(b, f2)]: i}) for i in range(K + 1)]
        for i in range(K):
            quad = [Cb[i], Ca[i], Ca[i + 1], Cb[i + 1]]
            def faces_cunha(k, qd=quad):
                b0 = [ponto(ci, k) for ci in qd]; s = [ponto(ci, k + 1) for ci in qd]
                return [b0[::-1], s] + [[b0[q], b0[(q + 1) % 4], s[(q + 1) % 4], s[q]] for q in range(4)]
            if fusao is None: poe(faces_cunha, 1); topo.append([ponto(ci, nl) for ci in quad])
            else: poli.append((1, quad))
    for v in range(nv):
        if len(nret[v]) != 3: continue
        fs = inc[v]; r_de = {retalho[(v, f)] for f in fs}; ordem = []
        f0 = fs[0]; atual = f0; vistos = []
        for _ in range(len(fs)):
            t = T[atual]; q = t.index(v); prox_v = t[(q - 1) % len(t)]
            vistos.append(retalho[(v, atual)])
            nxt = [g for g in arestas[(min(v, prox_v), max(v, prox_v))] if g != atual]; atual = nxt[0]
            if atual == f0: break
        for r in vistos:
            if r not in ordem: ordem.append(r)
        A, B, C = ordem
        for i in range(K):
            for j in range(K - i):
                l = K - i - j
                tris = [((i, j, l), (i + 1, j, l - 1), (i, j + 1, l - 1))]
                if l - 1 > 0 and i + j + 2 <= K: tris.append(((i + 1, j, l - 1), (i + 1, j + 1, l - 2), (i, j + 1, l - 1)))
                for tri in tris:
                    cc = [coluna(v, {A: w[0], B: w[1], C: w[2]}) for w in tri]
                    def faces_canto(k, cc=cc):
                        b0 = [ponto(ci, k) for ci in cc]; s = [ponto(ci, k + 1) for ci in cc]
                        return [b0[::-1], s] + [[b0[q], b0[(q + 1) % 3], s[(q + 1) % 3], s[q]] for q in range(3)]
                    if fusao is None: poe(faces_canto, 2); topo.append([ponto(ci, nl) for ci in cc])
                    else: poli.append((2, cc))
    if fusao is not None:
        dirs_ = np.array(dirs); base_ = np.array(base)
        def posicao(c, k): return V[base_[c]] + y[k] * dirs_[c]
        niveis = _funde(poli, posicao, y, fusao, tol_plano, max_membros, max_desvio); top = niveis[nl - 1]
        def celula(G, k, t):
            lp = G["laco"]; n = len(lp)
            if k == 0 or not G["subs"]: baixo = [[ponto(c, k) for c in lp][::-1]]
            else: baixo = [[ponto(c, k) for c in g["laco"]][::-1] for g in G["subs"]]
            cel.append(baixo + [[ponto(c, k + 1) for c in lp]] + [[ponto(lp[q], k), ponto(lp[(q + 1) % n], k), ponto(lp[(q + 1) % n], k + 1), ponto(lp[q], k + 1)] for q in range(n)])
            tipo.append(poli[G["membros"][0]][0]); nivel.append(k); fundida.append(G["fundida"]); celula_topo.append(t)
            for g in G["subs"]: celula(g, k - 1, t)
        for t, i in enumerate(sorted(range(len(top)), key=lambda i: min(top[i]["membros"]))):
            G = top[i]; topo.append([ponto(c, nl) for c in G["laco"]]); celula(G, nl - 1, t)
    base = np.array(base); dirs = np.array(dirs); chaves = {}; Pl = []
    def ix(pt):
        if pt not in chaves:
            chaves[pt] = len(Pl); Pl.append(V[pt[1]] if pt[0] == "v" else V[base[pt[1]]] + y[pt[2]] * dirs[pt[1]])
        return chaves[pt]
    celulas = []
    for faces in cel:
        fl = []
        for fc in faces:
            ids = [ix(p) for p in fc]; u = [i for q, i in enumerate(ids) if i != ids[q - 1]]
            if len(u) >= 3: fl.append(u)
        celulas.append(fl)
    topo_ix = [[ix(p) for p in fc] for fc in topo]
    if fusao is None: celula_topo = np.repeat(np.arange(len(topo)), nl); fundida = np.zeros(len(cel), bool)
    return dict(P=np.array(Pl), celulas=celulas, tipo=np.array(tipo), nivel=np.array(nivel), topo=topo_ix, K=K, celula_topo=np.asarray(celula_topo), fundida=np.asarray(fundida, bool), n_vivas=int(sum(viva.values())), n_cantos=int(sum(len(n) == 3 for n in nret.values())),
                n_colunas=len(base), retalhos=np.array([len(nret[v]) for v in range(nv)]))

def geometria_celula(P, faces):
    pts = np.array(sorted({i for f in faces for i in f})); c0 = P[pts].mean(0); vol = 0.0; cm = np.zeros(3); tet_min = np.inf; tets = []
    for f in faces:
        F = P[f]; fc = F.mean(0)
        for q in range(len(f)):
            a, b = F[q], F[(q + 1) % len(f)]; v6 = np.dot(a - c0, np.cross(b - c0, fc - c0)); tets.append(v6 / 6); vol += v6 / 6; cm += v6 / 6 * (c0 + a + b + fc) / 4
    tets = np.array(tets); return vol, (cm / vol if vol != 0 else c0), tets.min() / (abs(vol) / len(tets) + 1e-300)
