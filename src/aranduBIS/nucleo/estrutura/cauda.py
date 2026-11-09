from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from ..fe import Modelo, Sistema, escreve
from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from .asa import INF
from .materiais import propriedades

G0 = 9.80665

def _unifica(pontos, tol):
    pai = list(range(len(pontos)))
    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]; i = pai[i]
        return i
    for a, b in cKDTree(pontos).query_pairs(tol):
        pai[raiz(a)] = raiz(b)
    r = {}
    return [r.setdefault(raiz(i), len(r)) for i in range(len(pontos))]

def _orienta(d):
    d = d / np.linalg.norm(d)
    v = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    return tuple(v)

def monta(esq: dict, mats: dict | None = None, qualidade_carbono: float = 1.0, tol: float = 1e-3):
    pts, origem = [], []
    for el in esq.get("elementos", []):
        if el.get("tipo") != "trelica":
            continue
        N = AG._gira(np.asarray(el["nos"], float), el)
        for i, p in enumerate(N):
            pts.append(p); origem.append((el["nome"], i))
    if not pts:
        raise ValueError("o modelo nao tem elemento do tipo trelica (tubos de carbono)")
    pts = np.array(pts)
    fund = _unifica(pts, tol)
    n_nos = max(fund) + 1
    pos = np.zeros((n_nos, 3)); cont = np.zeros(n_nos)
    for p, f in zip(pts, fund):
        pos[f] += p; cont[f] += 1
    pos /= cont[:, None]
    desl = {}
    k = 0
    for el in esq["elementos"]:
        if el.get("tipo") == "trelica":
            desl[el["nome"]] = k; k += len(el["nos"])
    m = Modelo()
    for i, p in enumerate(pos):
        m.no(i + 1, *p)
    mat_id, prop_id, info, avisos, eid = {}, {}, {}, [], 0
    for el in esq["elementos"]:
        if el.get("tipo") != "trelica":
            continue
        tubos = el.get("tubos") or {}
        for b in el["barras"]:
            chave = b[2] if len(b) > 2 else "padrao"
            if chave not in tubos:
                raise ValueError(f"trelica {el['nome']!r}: tubo {chave!r} nao esta no catalogo")
            t = tubos[chave]
            nome_mat = t.get("material", "tubo_carbono")
            if nome_mat not in mat_id:
                p = propriedades(nome_mat, esq, mats, qualidade_carbono=qualidade_carbono)
                mat_id[nome_mat] = len(mat_id) + 1
                m.material(mat_id[nome_mat], p["E"], p["G"], rho=ES.densidade(nome_mat, esq))
                info[nome_mat] = p
            de, di = float(t["de"]), float(t.get("di", 0.0))
            if (el["nome"], chave) not in prop_id:
                prop_id[(el["nome"], chave)] = len(prop_id) + 1
                I = np.pi / 64 * (de ** 4 - di ** 4)
                m.prop(prop_id[(el["nome"], chave)], mat_id[nome_mat], 0.25 * np.pi * (de * de - di * di), I, I, 2 * I)
            ga, gb = fund[desl[el["nome"]] + int(b[0])] + 1, fund[desl[el["nome"]] + int(b[1])] + 1
            if ga == gb:
                avisos.append(f"{el['nome']}: barra {b[0]}-{b[1]} tem os dois nos fundidos (comprimento nulo) e foi ignorada")
                continue
            eid += 1
            m.barra(eid, prop_id[(el["nome"], chave)], ga, gb, _orienta(pos[gb - 1] - pos[ga - 1]))
            info[eid] = {"elemento": el["nome"], "tubo": chave, "de": de, "di": di, "material": nome_mat, "ga": ga, "gb": gb}
    return m, pos, info, avisos

def _grupos(m):
    pai = {n: n for n in m.nos}
    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]; i = pai[i]
        return i
    for _, _, ga, gb, _v in m.barras:
        pai[raiz(ga)] = raiz(gb)
    g = {}
    for n in m.nos:
        g.setdefault(raiz(n), []).append(n)
    return list(g.values())

def _area_planta(el):
    s = AG._secoes(el)
    return float(sum(0.5 * (a[3] + b[3]) * (b[1] - a[1]) for a, b in zip(s[:-1], s[1:])))

def _ponto_empenagem(esq, nome):
    el = next((e for e in esq["elementos"] if e.get("nome") == nome and e.get("tipo") == "asa"), None)
    if el is None:
        return None
    S = AG._secoes(el)
    tem_rolagem = bool(el.get("rolagem"))
    c = float(np.mean([s[3] for s in S])); b = max(s[1] for s in S) - min(s[1] for s in S)
    base = np.array(el.get("posicao", [0, 0, 0]), float)
    if abs(float(el.get("rolagem", 0.0)) - 90.0) < 1e-6:
        pt = base + np.array([0.25 * c, 0.0, 0.5 * max(abs(s[1]) for s in S)])
    else:
        pt = base + np.array([0.25 * c, 0.0, 0.0])
    return {"el": el, "ponto": pt, "S": _area_planta(el), "c": c, "b": b, "vertical": tem_rolagem}

def analisa(esq: dict, casos_cargas: list | None = None, peso_N: float = 148.5, rho: float = 1.1, Vc: float = 13.0, Vd: float = 15.9,
            U_c: float = 4.0, fator_seguranca: float = 1.2, x_apoio: float = 0.30, CL_max_h: float = 0.8, K_flambagem: float = 0.8,
            tailstrike_peso: float = 0.0, mats: dict | None = None, qualidade_carbono: float = 1.0, raio_ligacao: float = 0.10) -> dict:
    m, pos, info, avisos = monta(esq, mats, qualidade_carbono)
    grupos = _grupos(m)
    if len(grupos) > 1:
        avisos.append(f"A trelica tem {len(grupos)} partes sem ligacao entre si ({', '.join(str(len(g)) + ' nos' for g in grupos)}). So as que tocam o apoio (x <= {x_apoio} m) entram nas verificacoes; o trem, por exemplo, tem seu proprio passo.")
    apoio = [n for n, p in m.nos.items() if p[0] <= x_apoio + 1e-6]
    if not apoio:
        raise ValueError(f"nenhum no da trelica com x <= {x_apoio} m para servir de apoio")
    ligados = {n for g in grupos if any(a in g for a in apoio) for n in g}
    m.engasta(apoio)
    h = _ponto_empenagem(esq, "empenagem_h"); v = _ponto_empenagem(esq, "deriva")
    novo = max(m.nos) + 1
    def liga(ponto):
        nonlocal novo
        if no_h:
            m.no(novo, *ponto); m.rigido(novo, no_h, [novo])
            novo += 1
            return novo - 1, []
        d = np.linalg.norm(pos - ponto, axis=1)
        perto = [i + 1 for i in np.argsort(d)[:8] if d[i] <= raio_ligacao and (i + 1) in ligados and (i + 1) not in apoio] or \
                [i + 1 for i in np.argsort(d) if (i + 1) in ligados and (i + 1) not in apoio][:4]
        m.no(novo, *ponto); m.rigido(novo, novo, perto)
        novo += 1
        return novo - 1, perto
    cargas = []
    ponta = max((p for n, p in m.nos.items() if n in ligados), key=lambda p: p[0])
    no_h = no_v = no_ponta = None
    if h:
        no_h, lig_h = liga(h["ponto"])
        q_h = 0.5 * rho * Vd ** 2
        F_trim = max((abs(s["sustentacao_N"]) for c in (casos_cargas or []) for s in c["superficies"] if s["nome"] == "empenagem_h"), default=0.0)
        sinal = 1.0
        if casos_cargas:
            s_ = max(((abs(s["sustentacao_N"]), s["sustentacao_N"]) for c in casos_cargas for s in c["superficies"] if s["nome"] == "empenagem_h"), default=(0, 1))[1]
            sinal = 1.0 if s_ >= 0 else -1.0
        cargas.append(("trim", f"empenagem horizontal no pior ponto do V-n: {F_trim:.1f} N", {no_h: [0, 0, sinal * F_trim, 0, 0, 0]}))
        Fp = q_h * h["S"] * CL_max_h
        cargas.append(("profundor_fundo_cima", f"profundor a fundo em Vd, para cima: {Fp:.1f} N (CL {CL_max_h})", {no_h: [0, 0, Fp, 0, 0, 0]}))
        cargas.append(("profundor_fundo_baixo", f"profundor a fundo em Vd, para baixo: {Fp:.1f} N", {no_h: [0, 0, -Fp, 0, 0, 0]}))
    if v:
        no_v, lig_v = liga(v["ponto"])
        AR = v["b"] ** 2 / max(v["S"], 1e-9) if v["b"] else 1.0
        a = 2 * np.pi * AR / (AR + 2.0)
        for nome_c, Vv, U in (("rajada_lateral_Vc", Vc, U_c), ("rajada_lateral_Vd", Vd, 0.5 * U_c)):
            F = 0.5 * rho * Vv ** 2 * v["S"] * a * U / Vv
            cargas.append((nome_c, f"rajada lateral de {U:.1f} m/s na deriva em {Vv:.1f} m/s: {F:.1f} N a {v['ponto'][2]:.2f} m de altura", {no_v: [0, F, 0, 0, 0, 0]}))
    no_ponta = max((n for n in ligados), key=lambda n: m.nos[n][0])
    if tailstrike_peso > 0:
        Ft = tailstrike_peso * peso_N
        cargas.append(("tailstrike", f"reacao vertical na ponta do boom: {tailstrike_peso:.2f} x peso = {Ft:.0f} N (hipotese)", {no_ponta: [0, 0, Ft, 0, 0, 0]}))
    for k, (_, _, c) in enumerate(cargas, 1):
        for no, F in c.items():
            m.carga(k, no, F)
    S = Sistema(m)
    barras = [(eid, pid, ga, gb) for eid, pid, ga, gb, _ in m.barras]
    adm = {}
    resultados = []
    for k, (nome_c, desc, _) in enumerate(cargas, 1):
        r = S.estatica(k)
        lista = []
        for eid, pid, ga, gb in barras:
            d = info[eid]
            if ga not in ligados:
                continue
            p = propriedades(d["material"], esq, mats, qualidade_carbono=qualidade_carbono)
            adm[d["material"]] = p
            f = fator_seguranca * r["esforcos"][eid]
            A = 0.25 * np.pi * (d["de"] ** 2 - d["di"] ** 2); I = np.pi / 64 * (d["de"] ** 4 - d["di"] ** 4); c_ = d["de"] / 2
            L = float(np.linalg.norm(pos[gb - 1] - pos[ga - 1]))
            N = f[6]
            M = max(np.hypot(f[4], f[5]), np.hypot(f[10], f[11]))
            V_ = max(np.hypot(f[1], f[2]), np.hypot(f[7], f[8]))
            sb = M * c_ / I
            s_comp, s_tr = max(0.0, -N / A) + sb, max(0.0, N / A) + sb
            tau = abs(f[9]) * c_ / (2 * I) + 2 * V_ / A
            Pcr = np.pi ** 2 * p["E"] * I / (K_flambagem * L) ** 2
            marg = {"compressao": INF if s_comp < 1e-9 else min(INF, p["XC"] / s_comp - 1),
                    "tracao": INF if s_tr < 1e-9 else min(INF, p["X"] / s_tr - 1),
                    "cisalhamento": INF if tau < 1e-9 else min(INF, p["S"] / tau - 1),
                    "flambagem": INF if N >= -1e-9 else min(INF, Pcr / (-N) - 1)}
            lista.append({"id": eid, "elemento": d["elemento"], "tubo": d["tubo"], "L": L, "N": float(N), "M": float(M), "T": float(abs(f[9])),
                          "margens": marg, "margem": min(marg.values()), "modo": min(marg, key=marg.get),
                          "curta": bool(L < 10 * d["de"])})
        bins, mb = {}, {}
        for n in ligados:
            if m.nos[n][0] > x_apoio:
                bins.setdefault(round(m.nos[n][0] / 0.05) * 0.05, []).append(r["u"][n])
        xs = sorted(bins)
        perfil = {"x": xs, "uz": [1000 * float(np.mean([u[2] for u in bins[x]])) for x in xs], "uy": [1000 * float(np.mean([u[1] for u in bins[x]])) for x in xs],
                  "rx": [float(np.degrees(np.mean([u[3] for u in bins[x]]))) for x in xs]}
        for b in lista:
            xb = 0.5 * (pos[info[b["id"]]["ga"] - 1][0] + pos[info[b["id"]]["gb"] - 1][0])
            if not b["curta"] and xb > x_apoio:
                xm = round(xb / 0.05) * 0.05
                mb[xm] = min(mb.get(xm, INF), b["margem"])
        xm_ = sorted(mb)
        margem_x = {"x": xm_, "m": [float(min(mb[x], 20.0)) for x in xm_]}
        u_h = r["u"][no_h] if no_h else None
        u_v = r["u"][no_v] if no_v else None
        piores = sorted(lista, key=lambda b: (b["curta"], b["margem"]))[:8]
        curtas = sorted((b for b in lista if b["curta"]), key=lambda b: b["margem"])[:3]
        u_p = r["u"][no_ponta]
        resultados.append({"caso": nome_c, "descricao": desc, "margem": piores[0]["margem"], "piores": piores, "curtas": curtas, "perfil": perfil, "margem_x": margem_x,
                           "flecha_ponta_mm": 1000 * float(abs(u_p[2])), "deslocamento_ponta_mm": [1000 * float(x) for x in u_p[:3]],
                           "rotacao_h_graus": None if u_h is None else [float(np.degrees(x)) for x in u_h[3:]],
                           "rotacao_v_graus": None if u_v is None else [float(np.degrees(x)) for x in u_v[3:]]})
    pior = min(resultados, key=lambda c: c["margem"])
    modos = S.modos(4)["f_hz"]
    return {"casos": resultados, "critico": {"caso": pior["caso"], "barra": pior["piores"][0]["id"], "modo": pior["piores"][0]["modo"],
            "margem": pior["margem"], "elemento": pior["piores"][0]["elemento"]},
            "modos_hz": modos, "n_nos": len(m.nos), "n_barras": len(m.barras), "massa_kg": float(m.massa_total()), "apoio_nos": len(apoio),
            "partes": [len(g) for g in grupos], "ligadas": len(ligados), "avisos": avisos, "fator_seguranca": fator_seguranca, "x_apoio": x_apoio,
            "bdf": escreve(m, titulo=f"AranduBIS {esq.get('nome', '')} trelica da cauda")}
