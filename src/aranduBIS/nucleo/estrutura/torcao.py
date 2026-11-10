from __future__ import annotations

import numpy as np

from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from .asa import _perfis, secao
from .materiais import propriedades

def _contorno_d(x, zs, zi, c, xs_c, h_web, n_alma=10):
    m = x < xs_c - 1e-9
    xu, zu = np.append(x[m], xs_c), np.append(zs[m], np.interp(xs_c, x, zs))
    xl, zl = np.append(x[m], xs_c), np.append(zi[m], np.interp(xs_c, x, zi))
    pu = np.column_stack([xu, zu]) * c
    pl = np.column_stack([xl, zl]) * c
    segs = [("pele", pu[i], pu[i + 1]) for i in range(len(pu) - 1)]
    top, bot = pu[-1], pl[-1]
    segs += [("alma", top + (bot - top) * i / n_alma, top + (bot - top) * (i + 1) / n_alma) for i in range(n_alma)]
    segs += [("pele", pl[i + 1], pl[i]) for i in range(len(pl) - 2, -1, -1)]
    return segs, np.vstack([pu, pl[::-1]])

def _area(P):
    x, z = P[:, 0], P[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1)))

def _fechada(sec, x, zs, zi, c, mats, tw, ts):
    segs, poli = _contorno_d(x, zs, zi, c, sec["xs_c"], sec["h"])
    Eb, Gb = mats["balsa"]["E"], mats["balsa"]["G"]
    zna, EI = sec["zna"], sec["EI"]
    tub_sup = sum(E * A * (z - zna) for t, E, A, z in sec["partes"] if t == "tubo_sup")
    tub_inf = sum(E * A * (z - zna) for t, E, A, z in sec["partes"] if t == "tubo_inf")
    n_sup = next(i for i, s in enumerate(segs) if s[0] == "alma")
    n_inf = n_sup + sum(1 for s in segs if s[0] == "alma")
    q, qs, ds_, dz_, xm_, zm_, dx_, rig = 0.0, [], [], [], [], [], [], []
    for i, (tipo, p0, p1) in enumerate(segs):
        if i == n_sup:
            q -= tub_sup / EI
        if i == n_inf:
            q -= tub_inf / EI
        d = p1 - p0
        L = float(np.hypot(*d))
        t = tw if tipo == "alma" else ts
        zm = 0.5 * (p0[1] + p1[1])
        dq = -Eb * t * L * (zm - zna) / EI
        qs.append(q + 0.5 * dq)
        q += dq
        ds_.append(L)
        dx_.append(d[0]); dz_.append(d[1])
        xm_.append(0.5 * (p0[0] + p1[0])); zm_.append(zm)
        rig.append(L / (Gb * t))
    qs, ds_, dx_, dz_, xm_, zm_, rig = (np.array(v) for v in (qs, ds_, dx_, dz_, xm_, zm_, rig))
    qs = qs - np.sum(qs * rig) / np.sum(rig)
    Fz = float(np.sum(qs * dz_))
    Mo = float(np.sum(qs * (xm_ * dz_ - zm_ * dx_)))
    x_sc = Mo / Fz if abs(Fz) > 1e-12 else float(sec["xs_c"] * c)
    A = _area(poli)
    GJ = 4.0 * A * A / float(np.sum(rig))
    return GJ, x_sc / c, A

def _aberta(sec, x, zs, zi, c, mats, tw, ts, cfg, y):
    Gb, Eb = mats["balsa"]["G"], mats["balsa"]["E"]
    GJ = Gb * tw ** 3 * sec["h"] / 3.0 if sec["h"] > 0 else 0.0
    xs = sec["xs_c"] * c
    EAx = Eb * tw * sec["h"] * xs
    EA = Eb * tw * sec["h"]
    xe = sec["xe"]
    if xe > 0:
        for z_ in (zs, zi):
            m = x <= xe
            xx, zz = np.append(x[m], xe), np.append(z_[m], np.interp(xe, x, z_))
            ds = np.hypot(np.diff(xx), np.diff(zz)) * c
            GJ += Gb * ts ** 3 * float(ds.sum()) / 3.0
            EAx += Eb * ts * float(np.sum(ds * 0.5 * (xx[1:] + xx[:-1]) * c))
            EA += Eb * ts * float(ds.sum())
    for tb in cfg.get("tubos", []):
        y0, y1 = tb.get("y") or (-1e9, 1e9)
        if not (min(y0, y1) - 1e-9 <= y <= max(y0, y1) + 1e-9):
            continue
        de, di = float(tb["de"]), float(tb.get("di", 0.0))
        mt = mats["tubo_carbono"]
        GJ += mt["G"] * np.pi / 32.0 * (de ** 4 - di ** 4)
        A = 0.25 * np.pi * (de * de - di * di)
        xt = ES.posicao_x(tb, c, y)
        EAx += mt["E"] * A * xt
        EA += mt["E"] * A
    return GJ, EAx / EA / c

def estacao(cfg, x, zs, zi, c, y, mats):
    s = secao(cfg, x, zs, zi, c, y, mats)
    ch = cfg.get("chapeado") or {}
    tw, ts = s["tw"], float(ch.get("espessura", 0.001))
    fechada = bool(ch) and s["xe"] >= s["xs_c"] - 1e-6 and s["h"] > 0
    if fechada:
        GJ, ea, A = _fechada(s, x, zs, zi, c, mats, tw, ts)
        return {"GJ": GJ, "ea_c": ea, "area": A, "fechada": True, "EI": s["EI"]}
    GJ, ea = _aberta(s, x, zs, zi, c, mats, tw, ts, cfg, y)
    return {"GJ": GJ, "ea_c": ea, "area": 0.0, "fechada": False, "EI": s["EI"]}

def _cl_delta(cf_c):
    th = np.arccos(np.clip(2.0 * np.asarray(cf_c) - 1.0, -1.0, 1.0))
    return 2.0 * (np.pi - th + np.sin(th)), -0.5 * np.sin(th) * (1.0 - np.cos(th))

def _matriz_torcao(y, GJ):
    n = len(y)
    dy = np.diff(y)
    GJs = 0.5 * (GJ[1:] + GJ[:-1])
    B = np.zeros((n, n))
    for i in range(n):
        m = np.zeros(n); m[i] = 1.0
        T = np.concatenate([np.cumsum((0.5 * (m[1:] + m[:-1]) * dy)[::-1])[::-1], [0.0]])
        Ts = 0.5 * (T[1:] + T[:-1])
        B[:, i] = np.concatenate([[0.0], np.cumsum(Ts / GJs * dy)])
    return B

def _integra(f, y):
    return float(np.sum(0.5 * (f[1:] + f[:-1]) * np.diff(y)))

def _pesos(y):
    w = np.zeros(len(y)); dy = np.diff(y)
    w[:-1] += 0.5 * dy; w[1:] += 0.5 * dy
    return w

def aeroelastica(y, c, GJ, ea_c, ac_c, ail, a, rho, Vd, fator, eficiencia=0.85, V_max_rel=3.0):
    y, c, GJ, ea_c = (np.asarray(v, float) for v in (y, c, GJ, ea_c))
    d = (ea_c - ac_c) * c
    B = _matriz_torcao(y, GJ)
    w = _pesos(y)
    A_th = B @ np.diag(a * c * d)
    ev = np.linalg.eigvals(A_th)
    ev = ev.real[np.abs(ev.imag) < 1e-9 * np.abs(ev).max() + 1e-300] if len(ev) else ev.real
    lam = float(ev.max()) if len(ev) and ev.max() > 1e-12 else None
    qD = 1.0 / lam if lam else None
    saida = {"VD": float(np.sqrt(2 * qD / rho)) if qD else None, "lam": lam}
    if ail is None:
        saida["VR"] = None
        return saida
    y0, y1, corda, xc = ail
    no = (y >= min(y0, y1) - 1e-9) & (y <= max(y0, y1) + 1e-9)
    cf_c = np.where(no, (corda / c) if corda else (1.0 - xc), 0.0)
    cld, cmd = _cl_delta(np.clip(cf_c, 1e-6, 0.9))
    cld, cmd = eficiencia * cld * no, eficiencia * cmd * no
    mdel = c * (c * cmd + cld * d)
    t_del = B @ mdel
    L_rig = float(np.sum(w * c * cld * np.abs(y)))
    Vs = np.arange(1.0, V_max_rel * Vd, 0.25)
    if saida["VD"]:
        Vs = Vs[Vs < 0.98 * saida["VD"]]
    razao, I = [], np.eye(len(y))
    for V in Vs:
        q = 0.5 * rho * V * V
        th = np.linalg.solve(I - q * A_th, q * t_del)
        razao.append(float(np.sum(w * c * (cld + a * th) * np.abs(y))) / L_rig)
    razao = np.array(razao)
    VR = None
    idx = np.where(razao <= 0)[0]
    if len(idx) and idx[0] > 0:
        j = idx[0]
        VR = float(Vs[j - 1] + (Vs[j] - Vs[j - 1]) * razao[j - 1] / (razao[j - 1] - razao[j]))
    elif len(idx):
        VR = float(Vs[0])
    saida.update({"VR": VR, "V": Vs.tolist(), "razao": razao.tolist(), "L_rigido": L_rig})
    return saida

def _ail_de(el, c_ref):
    from ..modelador.superficies_comando import resolve
    for ct in el.get("controles", []):
        if ct.get("modo") == "anti":
            ct = resolve(ct, el.get("secoes") or [])
            y0, y1 = (abs(float(v)) for v in ct["y"])
            return (min(y0, y1), max(y0, y1), float(ct["corda"]) if "corda" in ct else None, float(ct["xc"]) if "xc" in ct else None)
    return None

def analisa(esq: dict, nome: str, mats: dict | None = None, rho: float = 1.1, Vd: float = 15.9, fator: float = 1.2,
            x_ca_c: float = 0.25, cl_alpha_2d: float = 2 * np.pi, eficiencia: float = 0.85, calib_GJ: float = 1.0,
            ea_desloc_c: float = 0.0, n: int = 41) -> dict:
    from .asa import _elemento
    el = _elemento(esq, nome)
    cfg = el.get("estrutura") or {}
    if not cfg:
        raise ValueError(f"a asa {nome!r} nao declara estrutura")
    m = {k: propriedades(k, esq, mats) for k in ("balsa", "tubo_carbono")}
    sec_el, x, Z = _perfis(el, esq)
    ail = _ail_de(el, None)
    y_max = max(abs(s[1]) for s in sec_el)
    ys = set(np.linspace(0.0, y_max, n).round(9))
    if ail:
        ys |= {round(ail[0], 9), round(ail[1], 9)}
    ys = np.array(sorted(v for v in ys if v <= y_max + 1e-9))
    est, cs = [], []
    for yy in ys:
        q = AG._secao_em(sec_el, float(yy)); i, t = AG._no_vao(sec_el, float(yy))
        zs, zi = (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]
        est.append(estacao(cfg, x, zs, zi, float(q[3]), float(yy), m))
        cs.append(float(q[3]))
    GJ = calib_GJ * np.array([e["GJ"] for e in est])
    ea = np.array([e["ea_c"] for e in est]) + ea_desloc_c
    cs = np.array(cs)
    folga = ea - x_ca_c
    avisos = []
    if np.any(GJ <= 0):
        raise ValueError("GJ nulo em alguma estacao: a secao nao resiste a torcao")
    if not any(e["fechada"] for e in est):
        avisos.append("Nenhuma estacao tem caixa-D fechada (o chapeado acaba antes da longarina): a rigidez de torcao e a de secao aberta, muito menor.")
    elif not all(e["fechada"] for e in est):
        avisos.append("O chapeado deixa de fechar a caixa em parte da envergadura: ali o GJ cai para o de secao aberta.")
    r = aeroelastica(ys, cs, GJ, ea, x_ca_c, ail, cl_alpha_2d, rho, Vd, fator, eficiencia)
    V_req = fator * Vd
    sai = {"nome": nome, "y": ys.tolist(), "c": cs.tolist(), "GJ": GJ.tolist(), "ea_c": ea.tolist(), "ca_c": x_ca_c,
           "fechada": [e["fechada"] for e in est], "area": [e["area"] for e in est], "EI": [e["EI"] for e in est],
           "K_theta": float(1.0 / _integra(1.0 / GJ, ys)), "V_requerida": V_req, "fator": fator,
           "VD": r["VD"], "VR": r["VR"], "curva": {"V": r.get("V", []), "razao": r.get("razao", [])},
           "aileron": None if ail is None else {"y": [ail[0], ail[1]], "corda": ail[2], "xc": ail[3]},
           "folga_ea_ca_c": {"min": float(folga.min()), "max": float(folga.max())}, "calib_GJ": calib_GJ, "ea_desloc_c": ea_desloc_c}
    sai["margem_VR"] = None if r["VR"] is None else r["VR"] / V_req - 1.0
    sai["margem_VD"] = None if r["VD"] is None else r["VD"] / V_req - 1.0
    sai["GJ_minimo"] = None if r["VR"] is None else float(calib_GJ * (V_req / r["VR"]) ** 2)
    if r["VR"] is None and ail:
        avisos.append("A reversao nao ocorre ate 3 vezes Vd com esta rigidez.")
    if r["VD"] is None:
        avisos.append("Divergencia nao ocorre: a linha elastica fica a frente do centro aerodinamico em toda a envergadura, "
                      f"por pelo menos {100 * (-folga.max()):.1f} % da corda. Isso depende dessa posicao: confirme no ensaio (GVT) e use o deslocamento da linha elastica.")
    else:
        avisos.append(f"Ha divergencia a {r['VD']:.1f} m/s: a linha elastica esta atras do centro aerodinamico em parte da asa.")
    if ail is None:
        avisos.append("Sem aileron declarado nesta asa: so a divergencia e verificada.")
    return {**sai, "avisos": avisos, "fontes": {k: m[k]["fonte"] for k in m}}
