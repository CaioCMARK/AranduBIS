from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import aeronave_estrutura as ES
from . import camada3d as C3
from . import superficies_comando as SC

VERSAO = 1

def _cruz2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])

class GeometriaInvalida(ValueError):
    pass

@dataclass
class Aeronave:
    nome: str
    V: np.ndarray
    T: np.ndarray
    zona: np.ndarray
    zonas: list
    linhas: dict = field(default_factory=dict)
    esquema: dict = field(default_factory=dict)
    camadas: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    itens_massa: list = field(default_factory=list)

    def triangulos_da_zona(self, nome):
        return np.flatnonzero(self.zona == self.zonas.index(nome))

    def pontos_da_linha(self, nome):
        return self.V[np.array(self.linhas[nome])]

    def so_camada(self, camada="aero"):
        if not self.camadas or all(c == camada for c in self.camadas): return self
        zs = [i for i, c in enumerate(self.camadas) if c == camada]
        if not zs: raise GeometriaInvalida(f"nenhuma zona na camada {camada!r}")
        mask = np.isin(self.zona, zs); T = self.T[mask]; usados = np.unique(T); novo = -np.ones(len(self.V), int); novo[usados] = np.arange(len(usados)); mapa = {z: i for i, z in enumerate(zs)}
        linhas = {k: [int(novo[i]) for i in v] for k, v in self.linhas.items() if (novo[np.array(v)] >= 0).all()}
        return Aeronave(self.nome, self.V[usados], novo[T], np.array([mapa[int(z)] for z in self.zona[mask]]), [self.zonas[i] for i in zs], linhas, self.esquema, [camada] * len(zs), self.info, self.itens_massa)

def _perfil_codigo(txt):
    s = "".join(ch for ch in str(txt) if ch.isdigit())
    if len(s) != 4:
        raise GeometriaInvalida(f"perfil {txt!r}: so NACA de 4 digitos nesta versao")
    return s

def anel_de_arquivo(caminho, secao):
    sec, d = None, {}
    for lin in Path(caminho).read_text(encoding="utf8").splitlines():
        t = lin.strip()
        if t.startswith("#"):
            n = t.lstrip("# ").strip()
            if n in ("Slat", "Main Element", "Flap"): sec = n; d[sec] = []
            continue
        if t and sec: d[sec].append([float(v) for v in t.split()[:2]])
    chave = {"slat": "Slat", "main": "Main Element", "principal": "Main Element", "flap": "Flap", "flape": "Flap"}.get(str(secao).lower(), secao)
    if chave not in d:
        raise GeometriaInvalida(f"{caminho}: secao {secao!r} nao existe (as de la: {sorted(d)})")
    P = np.array(d[chave], float)
    if np.allclose(P[0], P[-1]): P = P[:-1]
    x, y = P[:, 0], P[:, 1]
    if 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) < 0: P = P[::-1]
    P = np.roll(P, -int(np.argmax(P[:, 0])), axis=0)
    return P, int(np.argmin(P[:, 0]))

def _secoes(el):
    if "secoes_lineares" in el:
        s = el["secoes_lineares"]; n = int(s.get("n", 2)); y = np.linspace(float(s["y"][0]), float(s["y"][1]), max(2, n))
        return [(float(s.get("xle", 0.0)), float(yy), float(s.get("zle", 0.0)), float(s.get("corda", 1.0)), float(s.get("ainc", 0.0))) for yy in y]
    if "secoes" not in el or len(el["secoes"]) < 2:
        raise GeometriaInvalida(f"elemento {el.get('nome')!r}: precisa de >= 2 secoes (ou secoes_lineares)")
    S = [(float(s.get("xle", 0.0)), float(s["y"]), float(s.get("zle", 0.0)), float(s["corda"]), float(s.get("ainc", 0.0))) for s in el["secoes"]]
    if any(S[i + 1][1] <= S[i][1] for i in range(len(S) - 1)):
        raise GeometriaInvalida(f"elemento {el.get('nome')!r}: os y das secoes devem crescer")
    return S

def _perfis_secoes(el, esq):
    n = int(el.get("n_perfil", 40)); pasta = esq.get("_pasta", "."); base = el.get("arquivo") or el.get("perfil", "NACA 0012"); lista = el["secoes"]; Z = []; x = None
    for s in lista:
        x, zs, zi = ES.perfil_xy(s.get("arquivo") or s.get("perfil") or base, n, pasta); Z.append((zs, zi))
    return x, Z

def _quer_aneis(el):
    return "entelagem" in el or "controles" in el or "arquivo" in el or any(("perfil" in s or "arquivo" in s) for s in el.get("secoes", []))

def _no_vao(sec, y):
    ys = [q[1] for q in sec]; i = int(np.clip(np.searchsorted(ys, y, side="right") - 1, 0, len(ys) - 2)); return i, (y - ys[i]) / (ys[i + 1] - ys[i])

def _secao_em(sec, y):
    i, t = _no_vao(sec, y); a, b = np.array(sec[i]), np.array(sec[i + 1]); return tuple(a + t * (b - a))

def _nervuras_y(cfg, ys):
    y0, y1 = ys[0], ys[-1]; v = [float(q) for q in cfg]
    if y0 < -1e-9 and min(v) >= 0: v = v + [-q for q in v]
    return sorted({round(q, 9) for q in v if y0 - 1e-9 <= q <= y1 + 1e-9} | {y0, y1})

def _pivos_dos_comandos(comandos, secoes, x, Z):
    pivos = []
    for comando in comandos:
        lados = [1.0] if comando.get("modo", "sim") == "lado" else [1.0, -1.0]
        for lado in lados:
            existe = all(secoes[0][1] - 1e-9 <= lado * y_abs <= secoes[-1][1] + 1e-9 for y_abs in comando["y"])
            if not existe:
                continue
            pontas = []
            for y_abs in comando["y"]:
                y = lado * y_abs
                q = _secao_em(secoes, y)
                i, t = _no_vao(secoes, y)
                zs = (1 - t) * Z[i][0] + t * Z[i + 1][0]
                zi = (1 - t) * Z[i][1] + t * Z[i + 1][1]
                contorno = ES.anel_de(x, zs, zi)
                xc = SC.charneira_em(comando, q[3], q[0])
                zc = SC._altura_do_eixo(contorno, xc, comando.get("charneira", "meio"))
                incidencia = np.radians(q[4])
                ao_longo_da_corda = np.array([np.cos(incidencia), 0, -np.sin(incidencia)])
                normal = np.array([np.sin(incidencia), 0, np.cos(incidencia)])
                ponto = np.array(q[:3]) + q[3] * (xc * ao_longo_da_corda + zc * normal)
                pontas.append(np.round(ponto, 6).tolist())
            pivos.append({"comando": comando["nome"], "lado": "+y" if lado > 0 else "-y", "pontas": pontas})
    return pivos

def _constroi_asa_aneis(el, nome, esq):
    sec = _secoes(el)
    if "secoes" not in el: raise GeometriaInvalida(f"elemento {nome!r}: perfil por secao e entelagem pedem a lista 'secoes'")
    x, Z = _perfis_secoes(el, esq); n = len(x); ys = [q[1] for q in sec]; est = list(ys); ent = el.get("entelagem"); baias = None; corte = None
    if ent:
        try: ent = ES.com_filme(ent, esq)
        except ValueError as e: raise GeometriaInvalida(f"elemento {nome!r}: {e}")
        nerv = ent.get("nervuras") or (el.get("estrutura", {}).get("nervuras") or {}).get("y") or ys
        rib = _nervuras_y(nerv, ys); nb = max(2, int(ent.get("n_por_baia", 6))); baias = list(zip(rib, rib[1:]))
        for a, b in baias: est += list(np.linspace(a, b, nb + 1))
    comandos = el.get("controles") or []
    if comandos:
        try: SC.valida(comandos, nome)
        except SC.ControleInvalido as e: raise GeometriaInvalida(str(e))
        est += SC.estacoes_extras(comandos, ys)
    if comandos:
        esq["_info"].setdefault(nome, {})["pivos"] = _pivos_dos_comandos(comandos, sec, x, Z)
    y_ponta = max(abs(ys[0]), abs(ys[-1]))
    est = sorted({round(float(q), 9) for q in est}); aneis = []; D = []; flecha = 0.0; coef = 0.0; por_baia = [0.0] * (len(baias) if baias else 0)
    for y in est:
        q = _secao_em(sec, y); i, t = _no_vao(sec, y); zs = (1 - t) * Z[i][0] + t * Z[i + 1][0]; zi = (1 - t) * Z[i][1] + t * Z[i + 1][1]; zs0, zi0 = zs, zi
        if baias:
            k = int(np.clip(np.searchsorted([a for a, _ in baias], y, side="right") - 1, 0, len(baias) - 1)); a, b = baias[k]; eta = (y - 0.5 * (a + b)) / (b - a) if b > a else 0.0
            try: zs, zi = ES.aplica_entelagem(x, zs, zi, q[3], b - a, eta, ES.da_baia(ent, k, a, b))
            except ValueError as e: raise GeometriaInvalida(f"elemento {nome!r}: {e}")
            d = max(np.abs(zs - zs0).max(), np.abs(zi - zi0).max()); por_baia[k] = max(por_baia[k], d * q[3] * 1e3)
            if d * q[3] > flecha: flecha = d * q[3]; corte = {"y": y, "x": np.round(x, 5).tolist(), "zs0": np.round(zs0, 6).tolist(), "zi0": np.round(zi0, 6).tolist(), "zs": np.round(zs, 6).tolist(), "zi": np.round(zi, 6).tolist()}
            coef = max(coef, d)
        ai = np.radians(q[4]); cd = np.array([np.cos(ai), 0, -np.sin(ai)]); nd = np.array([np.sin(ai), 0, np.cos(ai)]); A0 = ES.anel_de(x, zs, zi)
        if comandos: A0 = SC.aplica(A0, comandos, y, y_ponta, q[3], q[0])
        aneis.append(np.array(q[:3]) + q[3] * (A0[:, 0:1] * cd + A0[:, 1:2] * nd)); D.append(A0)
    V = np.vstack(aneis); ns = len(est); mA = 2 * n - 2; T = []; lab = []; idx = lambda j, k: j * mA + (k % mA)
    for j in range(ns - 1):
        for k in range(mA):
            T += [[idx(j, k), idx(j, k + 1), idx(j + 1, k + 1)], [idx(j, k), idx(j + 1, k + 1), idx(j + 1, k)]]; z_ = 1 if (k >= n - 1) else 0; lab += [z_, z_]
    orelhas = C3.triangula_poligono(D[0])
    for j, z_ in ((0, 2), (ns - 1, 3)):
        for a, b, c in orelhas: T.append([idx(j, a), idx(j, b), idx(j, c)]); lab.append(z_)
    T = C3.orienta(V, T); L = {f"{nome}.bordo_fuga": [idx(j, 0) for j in range(ns)], f"{nome}.bordo_ataque": [idx(j, n - 1) for j in range(ns)],
                                f"{nome}.contorno_ponta-y": [idx(0, k) for k in range(mA)] + [idx(0, 0)], f"{nome}.contorno_ponta+y": [idx(ns - 1, k) for k in range(mA)] + [idx(ns - 1, 0)]}
    if ent:
        r, Tc = ES.razao_tensoes(ent); esq["_info"].setdefault(nome, {})["entelagem"] = {"flecha_max_mm": 1e3 * flecha, "coef_abaulamento_max": coef, "razao_tensoes": r, "tensao_corda_N_m": Tc, "baias": len(baias), "maior_baia_mm": 1e3 * max(b - a for a, b in baias), "corte": corte, "por_baia": [{"indice": k, "y": [a, b], "flecha_mm": por_baia[k]} for k, (a, b) in enumerate(baias)]}
    return V, np.asarray(T), np.array(lab), ["extradorso", "intradorso", "ponta-y", "ponta+y"], L

def _partes_asa(el, nome, esq):
    cfg = el.get("estrutura") or {}; sec = _secoes(el); ys = [q[1] for q in sec]; n = int(el.get("n_perfil", 40)); P = []
    if _quer_aneis(el): x, Z = _perfis_secoes(el, esq)
    else: x, zs_, zi_ = ES.perfil_xy(el.get("perfil", "NACA 0012"), n, esq.get("_pasta", ".")); Z = [(zs_, zi_)] * len(sec)
    def anel_3d(y):
        q = _secao_em(sec, y); i, t = _no_vao(sec, y); zs = (1 - t) * Z[i][0] + t * Z[i + 1][0]; zi = (1 - t) * Z[i][1] + t * Z[i + 1][1]; return q, zs, zi
    def mapa(q, u, w):
        ai = np.radians(q[4]); cd = np.array([np.cos(ai), 0, -np.sin(ai)]); nd = np.array([np.sin(ai), 0, np.cos(ai)]); return np.array(q[:3]) + q[3] * (np.asarray(u)[..., None] * cd + np.asarray(w)[..., None] * nd)
    nv = cfg.get("nervuras")
    if nv:
        t = float(nv.get("espessura", 0.00238)); mat = nv.get("material", "balsa"); Vs, Ts, of = [], [], 0; orelhas = None
        for y in _nervuras_y(nv["y"], ys):
            q, zs, zi = anel_3d(y); R = ES.anel_de(x, zs, zi); m = len(R); dy = np.array([0.0, 0.5 * t, 0.0]); A0 = mapa(q, R[:, 0], R[:, 1]); y0 = max(y - 0.5 * t, ys[0]) - y; y1 = min(y + 0.5 * t, ys[-1]) - y; dy0 = np.array([0.0, y0, 0.0]); dy1 = np.array([0.0, y1, 0.0])
            if orelhas is None: orelhas = C3.triangula_poligono(R)
            Vs.append(np.vstack([A0 + dy0, A0 + dy1])); tt = [[a, b, c] for a, b, c in orelhas] + [[m + a, m + c, m + b] for a, b, c in orelhas]
            for k in range(m):
                k1 = (k + 1) % m; tt += [[k, m + k, m + k1], [k, m + k1, k1]]
            Ts.append(C3.orienta(np.vstack([A0 + dy0, A0 + dy1]), tt) + of); of += 2 * m
        Va, Ta = np.vstack(Vs), np.vstack(Ts); P.append((Va, Ta, np.zeros(len(Ta), int), ["nervuras"], mat))
    for il, lg in enumerate(cfg.get("longarinas", [])):
        lar = float(lg.get("largura", 0.00238)); mat = lg.get("material", "balsa"); y0, y1 = (lg.get("y") or [ys[0], ys[-1]])
        est = sorted({float(y0), float(y1)} | {q for q in ys if y0 < q < y1}); Vp = []
        for y in est:
            q, zs, zi = anel_3d(y); xc = ES.posicao_x(lg, q[3], y) / q[3]; hx = 0.5 * lar / q[3]; a, b = xc - hx, xc + hx; Vp.append(mapa(q, [a, b, b, a], [np.interp(a, x, zs), np.interp(b, x, zs), np.interp(b, x, zi), np.interp(a, x, zi)]))
        Va = np.vstack(Vp); tt = []; ns = len(est)
        for j in range(ns - 1):
            for k in range(4):
                k1 = (k + 1) % 4; tt += [[4 * j + k, 4 * j + k1, 4 * (j + 1) + k1], [4 * j + k, 4 * (j + 1) + k1, 4 * (j + 1) + k]]
        o = 4 * (ns - 1); tt += [[0, 1, 2], [0, 2, 3], [o, o + 2, o + 1], [o, o + 3, o + 2]]; Ta = C3.orienta(Va, tt); P.append((Va, np.asarray(Ta), np.zeros(len(Ta), int), [f"longarina{il}"], mat))
    for it, tb in enumerate(cfg.get("tubos", [])):
        de = float(tb["de"]); di = float(tb.get("di", 0.0)); lado = tb.get("lado", "extradorso"); y0, y1 = (tb.get("y") or [ys[0], ys[-1]]); est = sorted({float(y0), float(y1)} | {q for q in ys if y0 < q < y1}); Np = []
        for y in est:
            q, zs, zi = anel_3d(y); xc = ES.posicao_x(tb, q[3], y) / q[3]; z_ = np.interp(xc, x, zs) - 0.5 * de / q[3] if lado == "extradorso" else np.interp(xc, x, zi) + 0.5 * de / q[3]; Np.append(mapa(q, xc, z_))
        Bb = [[j, j + 1] for j in range(len(est) - 1)]; Va, Ta, _ = ES.barras_prisma(np.array(Np), Bb, [0.5 * de] * len(Bb)); P.append((Va, Ta, np.zeros(len(Ta), int), [f"tubo{it}"], {"material": tb.get("material", "tubo_carbono"), "de": de, "di": di}))
    return P

def _constroi_asa(el, nome, esq):
    if _quer_aneis(el): return _constroi_asa_aneis(el, nome, esq)
    sec = _secoes(el)
    if "perfil_pontos" in el:
        pp = el["perfil_pontos"]; anel, n_le = anel_de_arquivo(Path(esq.get("_pasta", ".")) / pp["arquivo"], pp["secao"]); n = n_le + 1
        V, T = C3.loft_asa(sec, cod="0012", quads=False, anel=anel); mA = len(anel)
    else:
        n = int(el.get("n_perfil", 40)); V, T = C3.loft_asa(sec, n_perfil=n, cod=_perfil_codigo(el.get("perfil", "NACA 0012")), quads=False); mA = 2 * n - 2
    ns = len(sec); T = np.asarray(T)
    z = {k: i for i, k in enumerate(("extradorso", "intradorso", "ponta-y", "ponta+y"))}
    j, k = T // mA, T % mA; cap0 = (j == 0).all(1); cap1 = (j == ns - 1).all(1); lab = np.empty(len(T), int)
    for t in range(len(T)):
        if cap0[t]: lab[t] = z["ponta-y"]
        elif cap1[t]: lab[t] = z["ponta+y"]
        else:
            ks = set(k[t].tolist()); lab[t] = z["intradorso"] if (0 in ks and mA - 1 in ks) or max(ks) > n - 1 else z["extradorso"]
    idx = lambda jj, kk: jj * mA + (kk % mA)
    L = {f"{nome}.bordo_fuga": [idx(jj, 0) for jj in range(ns)], f"{nome}.bordo_ataque": [idx(jj, n - 1) for jj in range(ns)],
         f"{nome}.contorno_ponta-y": [idx(0, kk) for kk in range(mA)] + [idx(0, 0)], f"{nome}.contorno_ponta+y": [idx(ns - 1, kk) for kk in range(mA)] + [idx(ns - 1, 0)]}
    return V, T, lab, list(z), L

def _constroi_placa(el, nome, esq):
    P = np.asarray(el.get("contorno", []), float)
    if P.ndim != 2 or P.shape[1] != 2 or len(P) < 3:
        raise GeometriaInvalida(f"elemento {nome!r} (placa): 'contorno' precisa de >= 3 pontos [x, z]")
    if np.allclose(P[0], P[-1]): P = P[:-1]
    t = float(el.get("espessura", 0.0)); y0 = float(el.get("y", 0.0))
    if not t > 0: raise GeometriaInvalida(f"elemento {nome!r} (placa): 'espessura' precisa ser > 0")
    m = len(P); A2 = 0.5 * float(P[:, 0] @ np.roll(P[:, 1], -1) - P[:, 1] @ np.roll(P[:, 0], -1))
    if abs(A2) < 1e-14 * max(1.0, float(np.ptp(P)) ** 2): raise GeometriaInvalida(f"elemento {nome!r} (placa): contorno com area nula (pontos colineares ou um 8 que se cruza)")
    if A2 < 0: P = P[::-1]
    furos = [np.asarray(H, float)[:-1] if np.allclose(H[0], H[-1]) else np.asarray(H, float) for H in el.get("furos", [])]
    if any(H.ndim != 2 or H.shape[1] != 2 or len(H) < 3 for H in furos): raise GeometriaInvalida(f"elemento {nome!r} (placa): cada furo precisa de >= 3 pontos [x, z]")
    try:
        Q, orelhas = ES.triangula_com_furos(P, furos) if furos else (P, C3.triangula_poligono(P))
    except ValueError as e:
        raise GeometriaInvalida(f"elemento {nome!r} (placa): {e}")
    Aalvo = abs(A2) - sum(abs(0.5 * float(H[:, 0] @ np.roll(H[:, 1], -1) - H[:, 1] @ np.roll(H[:, 0], -1))) for H in furos)
    if abs(sum(0.5 * abs(_cruz2(Q[b] - Q[a], Q[c] - Q[a])) for a, b, c in orelhas) - Aalvo) > 1e-7 * abs(A2):
        raise GeometriaInvalida(f"elemento {nome!r} (placa): o contorno se cruza (poligono nao simples)" + (" ou um furo sai da placa" if furos else ""))
    Nq = len(Q); V = np.vstack([np.c_[Q[:, 0], np.full(Nq, y0 - 0.5 * t), Q[:, 1]], np.c_[Q[:, 0], np.full(Nq, y0 + 0.5 * t), Q[:, 1]]]); T, lab = [], []
    for a, b, c in orelhas: T.append([a, b, c]); lab.append(0); T.append([Nq + a, Nq + b, Nq + c]); lab.append(1)
    laco = [(0, m, 2)]; of = m
    for H in furos: laco.append((of, len(H), 3)); of += len(H)
    for o, k_, z_ in laco:
        for i in range(k_):
            a, b = o + i, o + (i + 1) % k_; T += [[a, b, Nq + b], [a, Nq + b, Nq + a]]; lab += [z_, z_]
    T = C3.orienta(V, T); zn = ["face-y", "face+y", "contorno"] + (["furos"] if furos else [])
    return V, np.asarray(T), np.array(lab), zn, {f"{nome}.aresta-y": list(range(m)) + [0], f"{nome}.aresta+y": [Nq + i for i in range(m)] + [Nq]}

def _constroi_roda(el, nome, esq):
    D = float(el.get("diametro", 0.0)); lar = float(el.get("largura", 0.0)); df = float(el.get("d_furo", 0.0)); dc = float(el.get("d_cubo", 0.0)); ane = float(el.get("anel", 0.1 * D)); na = int(el.get("n_aros", 0)); aro = float(el.get("aro", 0.0)); cx, cz = el.get("centro", [0.0, 0.0])
    if not (D > 0 and lar > 0): raise GeometriaInvalida(f"elemento {nome!r} (roda): diametro e largura precisam ser > 0")
    Re, Rc = 0.5 * D, 0.5 * dc; Ri = Re - ane; nc = int(el.get("n_circulo", 72)); th = 2 * np.pi * np.arange(nc) / nc; circ = lambda r: np.c_[cx + r * np.cos(th), cz + r * np.sin(th)]; furos = []
    if df > 0: furos.append(circ(0.5 * df)[::2])
    if na > 0:
        if not (0 < Rc < Ri and df < dc): raise GeometriaInvalida(f"elemento {nome!r} (roda): precisa de d_furo < d_cubo e d_cubo/2 < raio interno do aro")
        di, de = np.arcsin(0.5 * aro / Rc) if aro < 2 * Rc else np.pi, np.arcsin(0.5 * aro / Ri) if aro < 2 * Ri else np.pi; passo = 2 * np.pi / na
        if di >= 0.5 * passo: raise GeometriaInvalida(f"elemento {nome!r} (roda): raios largos demais para {na} aros no cubo")
        for i in range(na):
            a0 = el.get("fase", 0.0) * np.pi / 180 + i * passo; a1 = a0 + passo; ext = np.linspace(a0 + de, a1 - de, 13); inn = np.linspace(a1 - di, a0 + di, 7)
            furos.append(np.vstack([np.c_[cx + Ri * np.cos(ext), cz + Ri * np.sin(ext)], np.c_[cx + Rc * np.cos(inn), cz + Rc * np.sin(inn)]]))
    return _constroi_placa({"contorno": circ(Re).tolist(), "espessura": lar, "y": el.get("y", 0.0), "furos": [H.tolist() for H in furos]}, nome, esq)

def _constroi_trelica(el, nome, esq):
    N = np.asarray(el.get("nos", []), float); tub = el.get("tubos") or {}
    if N.ndim != 2 or N.shape[1] != 3: raise GeometriaInvalida(f"elemento {nome!r} (trelica): 'nos' precisa ser uma lista de [x, y, z]")
    Br = el.get("barras", [])
    if not Br: raise GeometriaInvalida(f"elemento {nome!r} (trelica): sem barras")
    B = []; tipos = []
    for b in Br:
        i, j = int(b[0]), int(b[1]); ty = b[2] if len(b) > 2 else "padrao"
        if not (0 <= i < len(N) and 0 <= j < len(N)) or i == j: raise GeometriaInvalida(f"elemento {nome!r} (trelica): barra {b} com no invalido")
        if ty not in tub: raise GeometriaInvalida(f"elemento {nome!r} (trelica): tubo {ty!r} nao esta em 'tubos' ({sorted(tub)})")
        B.append((i, j)); tipos.append(ty)
    nomes = sorted(set(tipos)); r = [0.5 * float(tub[t]["de"]) for t in tipos]; f = int(el.get("faces", 8))
    try: V, T, br = ES.barras_prisma(N, B, r, f)
    except ValueError as e: raise GeometriaInvalida(f"elemento {nome!r} (trelica): {e}")
    lab = np.array([nomes.index(tipos[i]) for i in br]); return V, T, lab, [f"tubo_{t}" for t in nomes], {}

def _constroi_malha(el, nome, esq):
    p = Path(esq.get("_pasta", ".")) / el["arquivo"]; esc = float(el.get("escala", 1.0))
    if not p.exists(): raise GeometriaInvalida(f"elemento {nome!r} (malha): arquivo {p.name!r} nao existe")
    import trimesh
    M = trimesh.load(str(p), force="mesh"); V = np.asarray(M.vertices, float) * esc; T = np.asarray(M.faces, int)
    return V, T, np.zeros(len(T), int), ["casca"], {}

def _anel_estacao(e, n, nome):
    yc, zc = float(e.get("yc", 0.0)), float(e.get("zc", 0.0))
    if "pontos" in e:
        Q = np.asarray(e["pontos"], float)
        if Q.ndim != 2 or Q.shape[1] != 2 or len(Q) < 3: raise GeometriaInvalida(f"elemento {nome!r} (corpo): 'pontos' da estacao x={e.get('x')} precisa de >= 3 pontos [y, z]")
        Q = np.vstack([Q, Q[:1]]) if not np.allclose(Q[0], Q[-1]) else Q; s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
        u = np.linspace(0, s[-1], n, endpoint=False); R = np.c_[np.interp(u, s, Q[:, 0]), np.interp(u, s, Q[:, 1])]
        if 0.5 * float(R[:, 0] @ np.roll(R[:, 1], -1) - R[:, 1] @ np.roll(R[:, 0], -1)) < 0: R = R[::-1]
        R = np.roll(R, -int(np.argmax(R[:, 1] - 1e-9 * np.abs(R[:, 0]))), axis=0)
        return R + [yc, zc]
    a, b, pw = float(e.get("a", 0.0)), float(e.get("b", 0.0)), float(e.get("expoente", 2.0))
    if not (a > 0 and b > 0 and pw > 0): raise GeometriaInvalida(f"elemento {nome!r} (corpo): estacao x={e.get('x')} precisa de a > 0, b > 0 (semi-eixos em y e z) e expoente > 0, ou de 'pontos'")
    th = 0.5 * np.pi + 2 * np.pi * np.arange(n) / n; c, s_ = np.cos(th), np.sin(th)
    return np.c_[a * np.sign(c) * np.abs(c) ** (2 / pw), b * np.sign(s_) * np.abs(s_) ** (2 / pw)] + [yc, zc]

def _constroi_corpo(el, nome, esq):
    E = el.get("estacoes", [])
    if len(E) < 2: raise GeometriaInvalida(f"elemento {nome!r} (corpo): precisa de >= 2 estacoes")
    xs = [float(e["x"]) for e in E]
    if any(xs[i + 1] <= xs[i] for i in range(len(xs) - 1)): raise GeometriaInvalida(f"elemento {nome!r} (corpo): os x das estacoes devem crescer")
    n = int(el.get("n_secao", 32))
    if n < 8: raise GeometriaInvalida(f"elemento {nome!r} (corpo): n_secao >= 8")
    V = np.vstack([np.c_[np.full(n, x), _anel_estacao(e, n, nome)] for x, e in zip(xs, E)]); ns = len(E); T, lab = [], []
    for j in range(ns - 1):
        for k in range(n): k1 = (k + 1) % n; T += [[j * n + k, j * n + k1, (j + 1) * n + k1], [j * n + k, (j + 1) * n + k1, (j + 1) * n + k]]; lab += [0, 0]
    for j, z in ((0, 1), (ns - 1, 2)):
        R = V[j * n:(j + 1) * n][:, 1:]
        for a, b, c in C3.triangula_poligono(R): T.append([j * n + a, j * n + b, j * n + c]); lab.append(z)
    T = C3.orienta(V, T); zr = V[:, 2].reshape(ns, n)
    return V, np.asarray(T), np.array(lab), ["casca", "tampa-x", "tampa+x"], {f"{nome}.cumeeira": [j * n + int(np.argmax(zr[j])) for j in range(ns)], f"{nome}.quilha": [j * n + int(np.argmin(zr[j])) for j in range(ns)],
                                                                          f"{nome}.contorno_x-": list(range(n)) + [0], f"{nome}.contorno_x+": [(ns - 1) * n + k for k in range(n)] + [(ns - 1) * n]}

_TIPOS = {"asa": _constroi_asa, "placa": _constroi_placa, "corpo": _constroi_corpo, "roda": _constroi_roda, "trelica": _constroi_trelica, "malha": _constroi_malha}
CAMADA_PADRAO = {"trelica": "estrutura"}

def _gira(V, el):
    if el.get("arfagem"):
        th = np.radians(float(el["arfagem"])); c_, s_ = np.cos(th), np.sin(th); V = V @ np.array([[c_, 0.0, -s_], [0.0, 1.0, 0.0], [s_, 0.0, c_]])
    if el.get("rolagem"):
        th = np.radians(float(el["rolagem"])); c_, s_ = np.cos(th), np.sin(th); V = V @ np.array([[1.0, 0.0, 0.0], [0.0, c_, s_], [0.0, -s_, c_]])
    if el.get("guinada"):
        th = np.radians(float(el["guinada"])); c_, s_ = np.cos(th), np.sin(th); V = V @ np.array([[c_, s_, 0.0], [-s_, c_, 0.0], [0.0, 0.0, 1.0]])
    if "posicao" in el: V = V + np.asarray(el["posicao"], float).reshape(3)
    return V

def _solido(V, T):
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]; d = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6; v = float(d.sum())
    return v, ((a + b + c) * d[:, None]).sum(0) / (4 * v) if abs(v) > 1e-30 else V.mean(0)

def _massa_elemento(el, nome, V, T, zona_base, esq, itens):
    if el.get("tipo", "asa") == "trelica":
        N = np.asarray(el["nos"], float); tub = el.get("tubos") or {}; tm = {}
        for b in el["barras"]:
            t = tub[b[2] if len(b) > 2 else "padrao"]; L = np.linalg.norm(N[int(b[1])] - N[int(b[0])]); de, di = float(t["de"]), float(t.get("di", 0.0)); m = 0.25 * np.pi * (de ** 2 - di ** 2) * L * ES.densidade(t.get("material", "tubo_carbono"), esq); q = tm.setdefault("t", [0.0, np.zeros(3)]); q[0] += m; q[1] += m * 0.5 * (_gira(N[[int(b[0])]], el)[0] + _gira(N[[int(b[1])]], el)[0])
        if tm: itens.append({"nome": nome, "massa": float(tm["t"][0]), "cg": (tm["t"][1] / tm["t"][0]).tolist(), "origem": f"{len(el['barras'])} tubos: secao anular x comprimento x densidade (sem colas e nos)"})
        return
    if "massa" in el:
        v, c = _solido(V, T); itens.append({"nome": nome, "massa": float(el["massa"]), "cg": (el.get("cg") or c.tolist()), "origem": "dada"}); return
    if "material" in el:
        v, c = _solido(V, T); itens.append({"nome": nome, "massa": abs(v) * ES.densidade(el["material"], esq), "cg": c.tolist(), "origem": f"{el['material']}: densidade x volume"})

def constroi(esq: dict) -> Aeronave:
    if esq.get("versao", VERSAO) != VERSAO:
        raise GeometriaInvalida(f"versao {esq.get('versao')} do esquema nao suportada (esta e a {VERSAO})")
    if not esq.get("elementos"):
        raise GeometriaInvalida("sem elementos")
    esq_ = dict(esq); esq_["_info"] = {}; Vs, Ts, zl, zonas, camadas, linhas, off, nomes, itens = [], [], [], [], [], {}, 0, set(), []
    for el in esq["elementos"]:
        nome = el["nome"]
        if nome in nomes or not nome.replace("_", "").isalnum():
            raise GeometriaInvalida(f"nome de elemento invalido ou repetido: {nome!r}")
        nomes.add(nome)
        tipo = el.get("tipo", "asa")
        if tipo == "ponto":
            if "massa" not in el: raise GeometriaInvalida(f"elemento {nome!r} (ponto): falta 'massa'")
            itens.append({"nome": nome, "massa": float(el["massa"]), "cg": list(map(float, el.get("posicao", [0, 0, 0]))), "origem": "dada"}); continue
        if tipo not in _TIPOS:
            raise GeometriaInvalida(f"elemento {nome!r}: tipo {tipo!r} ainda nao suportado (os de agora: {sorted(_TIPOS)})")
        V, T, lab, znomes, L = _TIPOS[tipo](el, nome, esq_)
        V = _gira(V, el)
        for pivo in esq_.get("_info", {}).get(nome, {}).get("pivos", []):
            pivo["pontas"] = np.round(_gira(np.array(pivo["pontas"], float), el), 6).tolist()
        cam = el.get("camada", CAMADA_PADRAO.get(tipo, "aero")); base = len(zonas); zonas += [f"{nome}.{k}" for k in znomes]; camadas += [cam] * len(znomes)
        for k, ids in L.items(): linhas[k] = [off + i for i in ids]
        Vs.append(V); Ts.append(T + off); zl.append(lab + base); off += len(V); _massa_elemento(el, nome, V, T, base, esq_, itens)
        if tipo == "asa" and el.get("estrutura"):
            cfg = el["estrutura"]
            for Vp, Tp, lp, zp, mat in _partes_asa(el, nome, esq_):
                Vp = _gira(Vp, el); base = len(zonas); zonas += [f"{nome}.{k}" for k in zp]; camadas += ["estrutura"] * len(zp); Vs.append(Vp); Ts.append(Tp + off); zl.append(lp + base); off += len(Vp)
                if isinstance(mat, dict):
                    v_, c_ = _solido(Vp, Tp); fr = 1.0 - (mat["di"] / mat["de"]) ** 2; itens.append({"nome": f"{nome}.{zp[0]}", "massa": abs(v_) * fr * ES.densidade(mat["material"], esq_), "cg": c_.tolist(), "origem": "tubo da mesa"})
                else:
                    v_, c_ = _solido(Vp, Tp); al = float((cfg.get("nervuras") or {}).get("alivio", 1.0)) if str(zp[0]).startswith("nervuras") else 1.0
                    itens.append({"nome": f"{nome}.{zp[0]}", "massa": abs(v_) * al * ES.densidade(mat, esq_), "cg": c_.tolist(), "origem": f"{mat}: densidade x volume" + (f" x alivio {al:g}" if al != 1.0 else "")})
            if cfg.get("chapeado"):
                ch = cfg["chapeado"]; ax = float(ch.get("ate_xc", 0.25)); Az, c_ = _area_casca(V, T, lab, el, esq_, ax); m_ = Az * float(ch.get("espessura", 0.001)) * ES.densidade(ch.get("material", "balsa"), esq_); itens.append({"nome": f"{nome}.chapeado", "massa": m_, "cg": c_.tolist(), "origem": "area ate x/c x espessura x densidade"})
        if tipo == "asa" and el.get("estrutura", {}).get("cruzadas"):
            cfg = el["estrutura"]; S_ = sorted((abs(float(q["y"])), float(q.get("xle", 0.0)), float(q["corda"])) for q in el["secoes"]); ps = np.array(el.get("posicao", [0, 0, 0]), float)
            for k, cz in enumerate(cfg["cruzadas"]):
                y0, y1 = (abs(float(v)) for v in cz["y"]); ym = 0.5 * (y0 + y1); xle_, c_ = np.interp(ym, [q[0] for q in S_], [q[1] for q in S_]), np.interp(ym, [q[0] for q in S_], [q[2] for q in S_])
                m_ = int(cz["n"]) * float(cz["area_m2"]) * float(cz.get("espessura", 0.00238)) * ES.densidade(cz.get("material", "balsa"), esq_)
                itens.append({"nome": f"{nome}.cruzadas{k}", "massa": m_, "cg": [ps[0] + xle_ + float(cz.get("x_c", 0.55)) * c_, 0.0, ps[2]], "origem": f"{cz['n']} nervuras em X x area x espessura x densidade"})
        if tipo == "asa" and el.get("controles"):
            S_ = sorted((abs(float(q["y"])), float(q.get("xle", 0.0)), float(q["corda"])) for q in el["secoes"]); ps = np.array(el.get("posicao", [0, 0, 0]), float)
            for cmd in el["controles"]:
                m_ = SC.massa_dobradica(cmd, S_[-1][0])
                if m_ > 0:
                    ym = 0.5 * (cmd["y"][0] + min(cmd["y"][1], S_[-1][0])); xle_, c_ = np.interp(ym, [q[0] for q in S_], [q[1] for q in S_]), np.interp(ym, [q[0] for q in S_], [q[2] for q in S_])
                    itens.append({"nome": f"{nome}.{cmd['nome']}.dobradica", "massa": m_, "cg": [ps[0] + xle_ + SC.charneira_em(cmd, c_, xle_) * c_, 0.0, ps[2]], "origem": f"dobradica {cmd['dobradica']}: g/m x comprimento (hipotese)"})
        if tipo == "asa" and el.get("entelagem"):
            ent = el["entelagem"]; de = float(ent.get("de_xc", 0.0)); Az, c_ = _area_casca(V, T, lab, el, esq_, 1.1, de); g_ = float(ES.filme_de(ent, esq_).get("gramatura_g_m2", 40.0)); itens.append({"nome": f"{nome}.entelagem", "massa": Az * g_ * 1e-3, "cg": c_.tolist(), "origem": f"area de filme x {g_:g} g/m2"})
    if not Vs: raise GeometriaInvalida("nenhum elemento com geometria")
    A = Aeronave(esq.get("nome", "aeronave"), np.vstack(Vs), np.vstack(Ts), np.concatenate(zl), zonas, linhas, esq, camadas, esq_["_info"], itens)
    for mk in esq.get("marcas", []):
        base = mk["feicao"]
        if base not in A.linhas:
            raise GeometriaInvalida(f"marca {mk['nome']!r}: feicao {base!r} nao existe (as de linha: {sorted(A.linhas)})")
        if mk["nome"] in A.linhas:
            raise GeometriaInvalida(f"marca {mk['nome']!r}: nome ja usado")
        sel = list(A.linhas[base])
        for c, eixo in enumerate("xyz"):
            if mk.get(eixo):
                lo, hi = mk[eixo]; sel = [i for i in sel if lo - 1e-12 <= A.V[i, c] <= hi + 1e-12]
        if len(sel) < 2:
            raise GeometriaInvalida(f"marca {mk['nome']!r}: o trecho {({k: mk[k] for k in 'xyz' if k in mk} or 'inteiro')} de {base!r} tem {len(sel)} vertice(s); precisa de >= 2 (aumente as secoes)")
        A.linhas[mk["nome"]] = sel
    return A

def _area_casca(V, T, lab, el, esq, ate_xc, de_xc=0.0):
    sec = _secoes(el); ys = np.array([q[1] for q in sec]); xl = np.array([q[0] for q in sec]); cs = np.array([q[3] for q in sec]); pos = np.asarray(el.get("posicao", [0, 0, 0]), float)
    tri = T[lab <= 1]; a, b, c = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]; ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1); cen = (a + b + c) / 3
    yb = cen[:, 1] - pos[1]; xc = (cen[:, 0] - pos[0] - np.interp(yb, ys, xl)) / np.interp(yb, ys, cs); sel = (xc >= de_xc) & (xc <= ate_xc); A_ = float(ar[sel].sum())
    return A_, ((cen[sel] * ar[sel, None]).sum(0) / A_ if A_ > 0 else V.mean(0))

def massa_e_cg(A) -> dict:
    it = A.itens_massa; M = sum(q["massa"] for q in it)
    cg = (sum(np.array(q["cg"], float) * q["massa"] for q in it) / M).tolist() if M > 0 else None
    return {"massa_kg": float(M), "cg_m": cg, "itens": it}

def carrega(caminho) -> Aeronave:
    esq = json.loads(Path(caminho).read_text(encoding="utf8")); esq.setdefault("_pasta", str(Path(caminho).resolve().parent))
    return constroi(esq)

def escreve_obj(A: Aeronave, caminho, camada="aero"):
    A = A.so_camada(camada)
    L = ["# mach-aeronave v%d  nome=%s" % (VERSAO, A.nome)]
    L += ["v %.17g %.17g %.17g" % tuple(p) for p in A.V]
    for zi, nome in enumerate(A.zonas):
        L.append(f"g {nome}"); L += ["f %d %d %d" % tuple(int(i) + 1 for i in A.T[t]) for t in np.flatnonzero(A.zona == zi)]
    for nome, ids in A.linhas.items():
        L.append(f"g @linha {nome}"); L.append("l " + " ".join(str(int(i) + 1) for i in ids))
    Path(caminho).write_text("\n".join(L) + "\n", encoding="utf8")

def le_obj(caminho) -> Aeronave:
    V, T, zona, zonas, linhas, atual, nome = [], [], [], [], {}, None, "aeronave"
    for ln in Path(caminho).read_text(encoding="utf8").splitlines():
        if ln.startswith("# mach-aeronave"):
            nome = ln.split("nome=", 1)[1].strip() if "nome=" in ln else nome
        elif ln.startswith("v "):
            V.append([float(x) for x in ln.split()[1:4]])
        elif ln.startswith("g "):
            g = ln[2:].strip()
            if g.startswith("@linha "):
                atual = ("linha", g[7:].strip())
            else:
                if g not in zonas: zonas.append(g)
                atual = ("zona", zonas.index(g))
        elif ln.startswith("f ") and atual and atual[0] == "zona":
            T.append([int(x.split("/")[0]) - 1 for x in ln.split()[1:]]); zona.append(atual[1])
        elif ln.startswith("l ") and atual and atual[0] == "linha":
            linhas[atual[1]] = [int(x) - 1 for x in ln.split()[1:]]
    return Aeronave(nome, np.array(V), np.array(T, int), np.array(zona, int), zonas, linhas)

def exemplo_asa_ar3() -> dict:
    return {"versao": 1, "nome": "asa_ar3_naca0012", "unidade": "m",
            "elementos": [{"nome": "asa", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 60, "secoes_lineares": {"y": [-1.5, 1.5], "n": 34, "xle": 0.0, "zle": 0.0, "corda": 1.0, "ainc": 0.0}}],
            "marcas": []}

def exemplo_biplano_demo() -> dict:
    sec = lambda cs: [{"y": y, "xle": 0.0, "zle": 0.0, "corda": c, "ainc": 0.0} for y, c in cs]
    return {"versao": 1, "nome": "biplano_demo", "unidade": "m", "elementos": [
        {"nome": "asa_inferior", "tipo": "asa", "perfil": "NACA 4412", "n_perfil": 40, "secoes": sec([(-1.2, 0.25), (-0.66, 0.33), (0.0, 0.36), (0.66, 0.33), (1.2, 0.25)])},
        {"nome": "asa_superior", "tipo": "asa", "perfil": "NACA 4412", "n_perfil": 40, "posicao": [-0.10, 0.0, 0.45], "secoes": sec([(-1.2, 0.30), (0.0, 0.36), (1.2, 0.30)])},
        {"nome": "torre", "tipo": "placa", "espessura": 0.012, "y": 0.0, "material": "balsa", "contorno": [[0.08, 0.0], [0.30, 0.0], [0.26, 0.23], [0.30, 0.45], [0.08, 0.45], [0.12, 0.23]], "furos": [[[0.14, 0.05], [0.24, 0.05], [0.21, 0.18], [0.16, 0.18]], [[0.16, 0.28], [0.21, 0.28], [0.24, 0.40], [0.14, 0.40]]]},
        {"nome": "lanca", "tipo": "placa", "espessura": 0.010, "y": 0.0, "material": "balsa", "contorno": [[0.30, 0.43], [1.55, 0.43], [1.55, 0.12], [1.62, 0.05], [1.75, 0.05], [1.75, 0.47], [0.30, 0.47]]},
        {"nome": "empenagem_h", "tipo": "asa", "perfil": "NACA 0009", "n_perfil": 30, "posicao": [1.58, 0.0, 0.12], "secoes": sec([(-0.35, 0.16), (0.35, 0.16)])},
        {"nome": "roda_esq", "tipo": "roda", "diametro": 0.092, "largura": 0.008, "d_furo": 0.016, "d_cubo": 0.028, "anel": 0.006, "n_aros": 6, "aro": 0.005, "material": "nylon", "y": -0.15, "posicao": [0.2, 0.0, -0.2]},
        {"nome": "roda_dir", "tipo": "roda", "diametro": 0.092, "largura": 0.008, "d_furo": 0.016, "d_cubo": 0.028, "anel": 0.006, "n_aros": 6, "aro": 0.005, "material": "nylon", "y": 0.15, "posicao": [0.2, 0.0, -0.2]},
        {"nome": "motor", "tipo": "ponto", "massa": 0.4, "posicao": [0.0, 0.0, 0.2]},
        {"nome": "carga", "tipo": "corpo", "n_secao": 32, "posicao": [0.0, 0.0, -0.12],
         "estacoes": [{"x": 0.05, "a": 0.05, "b": 0.04, "expoente": 3}, {"x": 0.20, "a": 0.09, "b": 0.06, "expoente": 4}, {"x": 0.36, "a": 0.05, "b": 0.04, "expoente": 3}]}],
        "marcas": [{"nome": "aileron_dir", "feicao": "asa_inferior.bordo_fuga", "y": [0.6, 1.2]}]}
