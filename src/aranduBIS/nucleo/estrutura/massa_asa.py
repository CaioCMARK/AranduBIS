from __future__ import annotations

import numpy as np

from ..modelador import aeronave_geometria as AG

N_AMOSTRAS = 12

def _momentos_acumulados(V, T, Ys):
    tri = V[T]
    saida = np.zeros((len(Ys), 5))
    for k, Y in enumerate(Ys):
        P = tri - np.array([0.0, Y, 0.0])
        d = P[:, :, 1]
        dentro = d <= 0.0
        cnt = dentro.sum(1)
        pecas = [P[cnt == 3]]
        m1 = cnt == 1
        if m1.any():
            Q = P[m1]
            i = np.argmax(dentro[m1], axis=1)
            R = np.take_along_axis(Q, ((i[:, None] + np.arange(3)) % 3)[:, :, None], axis=1)
            dd = R[:, :, 1]
            t1, t2 = dd[:, 0] / (dd[:, 0] - dd[:, 1]), dd[:, 0] / (dd[:, 0] - dd[:, 2])
            pecas.append(np.stack([R[:, 0], R[:, 0] + t1[:, None] * (R[:, 1] - R[:, 0]), R[:, 0] + t2[:, None] * (R[:, 2] - R[:, 0])], 1))
        m2 = cnt == 2
        if m2.any():
            Q = P[m2]
            o = np.argmin(dentro[m2], axis=1)
            R = np.take_along_axis(Q, ((o[:, None] + np.arange(3)) % 3)[:, :, None], axis=1)
            dd = R[:, :, 1]
            q1 = R[:, 1] + (dd[:, 1] / (dd[:, 1] - dd[:, 0]))[:, None] * (R[:, 0] - R[:, 1])
            q2 = R[:, 2] + (dd[:, 2] / (dd[:, 2] - dd[:, 0]))[:, None] * (R[:, 0] - R[:, 2])
            pecas += [np.stack([q1, R[:, 1], R[:, 2]], 1), np.stack([q1, R[:, 2], q2], 1)]
        Pc = np.concatenate(pecas, axis=0)
        if len(Pc) == 0:
            continue
        a, b, c = Pc[:, 0], Pc[:, 1], Pc[:, 2]
        vol = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
        s = a + b + c
        saida[k] = [vol.sum(), (vol * s[:, 0] / 4).sum(), (vol * s[:, 2] / 4).sum(),
                    (vol / 20 * (a[:, 0] ** 2 + b[:, 0] ** 2 + c[:, 0] ** 2 + s[:, 0] ** 2)).sum(),
                    (vol / 20 * (a[:, 2] ** 2 + b[:, 2] ** 2 + c[:, 2] ** 2 + s[:, 2] ** 2)).sum()]
    return saida

def _triangulos_da_pele(V, T, lab, el, ate_xc, de_xc=0.0):
    sec = AG._secoes(el)
    ys = np.array([q[1] for q in sec]); xl = np.array([q[0] for q in sec]); cs = np.array([q[3] for q in sec]); pos = np.asarray(el.get("posicao", [0, 0, 0]), float)
    tri = T[lab <= 1]
    a, b, c = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]
    ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    cen = (a + b + c) / 3
    yb = cen[:, 1] - pos[1]
    xc = (cen[:, 0] - pos[0] - np.interp(yb, ys, xl)) / np.interp(yb, ys, cs)
    if not np.isscalar(ate_xc):
        par = sorted((abs(float(q[0])), float(q[1])) for q in ate_xc)
        ate_xc = np.interp(np.abs(yb), [q[0] for q in par], [q[1] for q in par])
    sel = (xc >= de_xc) & (xc <= ate_xc)
    return ar[sel], cen[sel]

class _Pecas:

    def __init__(self, geom):
        self.geom = geom
        self.y, self.m, self.S, self.I, self.cat, self.origem = [], [], [], [], [], []

    def fatia(self, y_abs, m, Mx, Mz, Ixx, Izz, cat, origem):
        xe, ze = self.geom["xe"](y_abs), self.geom["ze"](y_abs)
        self.y.append(y_abs); self.m.append(m); self.S.append(Mx - xe * m)
        self.I.append(Ixx - 2 * xe * Mx + xe ** 2 * m + Izz - 2 * ze * Mz + ze ** 2 * m); self.cat.append(cat); self.origem.append(origem)

    def ponto(self, y_abs, m, x_abs, z_abs, cat, origem, var_x=0.0):
        self.fatia(y_abs, m, m * x_abs, m * z_abs, m * (x_abs ** 2 + var_x), m * z_abs ** 2, cat, origem)

    def distribuida(self, m, y0, y1, x_de_c, cat, origem, de_c=None):
        ys = np.linspace(y0, y1, N_AMOSTRAS) if y1 > y0 + 1e-9 else np.array([y0])
        for y in ys:
            c = self.geom["corda"](y)
            self.ponto(float(y), m / len(ys), self.geom["x_le"](y) + x_de_c * c, self.geom["ze"](y), cat, origem, var_x=0.0 if not de_c else (de_c * c) ** 2 / 12.0)

def _geometria(esq, nome, y_nos):
    el = next(e for e in esq["elementos"] if e["nome"] == nome)
    sec = AG._secoes(el)
    ys = np.array([q[1] for q in sec]); xl = np.array([q[0] for q in sec]); zl = np.array([q[2] for q in sec]); cs = np.array([q[3] for q in sec])
    pos = np.asarray(el.get("posicao", [0.0, 0.0, 0.0]), float)
    return {"el": el, "pos": pos, "simetrica": bool(ys.min() < -1e-9), "y_ponta": float(np.abs(ys).max()),
            "corda": lambda y: float(np.interp(y, ys, cs)), "x_le": lambda y: float(pos[0] + np.interp(y, ys, xl)),
            "ze": lambda y: float(pos[2] + np.interp(y, ys, zl)), "xe": None}

def perfil_de_massa(esq: dict, nome: str, y, ea_c, itens: list, adicionais: list | None = None, massa_medida_kg: float | None = None,
                    x_cg_medido_c: float | None = None, y_cg_medido_m: float | None = None) -> dict:
    y = np.asarray(y, float)
    ea_c = np.broadcast_to(np.asarray(ea_c, float), y.shape)
    G = _geometria(esq, nome, y)
    el = G["el"]
    G["xe"] = lambda yy: G["x_le"](yy) + float(np.interp(yy, y, ea_c)) * G["corda"](yy)
    P = _Pecas(G)
    peso_lado = 0.5 if G["simetrica"] else 1.0
    esq_ = dict(esq); esq_["_info"] = {}
    it = {q["nome"]: q for q in itens if q["nome"] == nome or str(q["nome"]).startswith(nome + ".")}
    ponta = G["y_ponta"]
    mid = 0.5 * (y[1:] + y[:-1])
    pos_arestas = np.unique(np.r_[0.0, mid, ponta + 1e-6]) if y[0] <= 1e-9 else np.unique(np.r_[y[0] - 0.5 * (y[1] - y[0]), mid, ponta + 1e-6])
    arestas = np.unique(np.r_[-pos_arestas, pos_arestas]) if G["simetrica"] else pos_arestas
    usados = set()

    def malha(V, T, nome_item, cat):
        q = it.get(nome_item)
        if q is None:
            return
        usados.add(nome_item)
        mom = _momentos_acumulados(V, T, arestas)
        tot = mom[-1, 0]
        if abs(tot) < 1e-14:
            return
        f = q["massa"] / tot
        d = np.diff(mom, axis=0)
        for k in range(len(d)):
            if abs(d[k, 0]) < 1e-14:
                continue
            yc = 0.5 * (arestas[k] + arestas[k + 1])
            P.fatia(abs(yc), peso_lado * f * d[k, 0], peso_lado * f * d[k, 1], peso_lado * f * d[k, 2], peso_lado * f * d[k, 3], peso_lado * f * d[k, 4], cat, q["origem"])

    def pele(V, T, lab, ate, de, nome_item, cat):
        q = it.get(nome_item)
        if q is None:
            return
        usados.add(nome_item)
        ar, cen = _triangulos_da_pele(V, T, lab, el, ate, de)
        if len(ar) == 0:
            return
        for a_, c_ in zip(ar, cen):
            P.ponto(abs(float(c_[1] - G["pos"][1])), peso_lado * q["massa"] * a_ / ar.sum(), float(c_[0]), float(c_[2]), cat, q["origem"])

    if el.get("estrutura"):
        for Vp, Tp, _, zp, mat in AG._partes_asa(el, nome, esq_):
            Vp = AG._gira(Vp, el)
            z0 = str(zp[0])
            malha(Vp, np.asarray(Tp), f"{nome}.{z0}", "nervuras" if z0.startswith("nerv") else "longarinas" if z0.startswith("long") else "tubos")
    if nome in it:
        V, T, lab, _, _ = AG._constroi_asa(el, nome, esq_)
        V = AG._gira(V, el)
        malha(V, np.asarray(T), nome, "casco maciço")
    else:
        V = T = lab = None
    if el.get("estrutura", {}).get("chapeado") or el.get("entelagem"):
        V, T, lab, _, _ = AG._constroi_asa(el, nome, esq_)
        V = AG._gira(V, el)
        T = np.asarray(T)
        ch = (el.get("estrutura") or {}).get("chapeado")
        if ch:
            pele(V, T, lab, ch.get("ate_xc_y") or float(ch.get("ate_xc", 0.25)), 0.0, f"{nome}.chapeado", "chapeado")
        if el.get("entelagem"):
            pele(V, T, lab, 1.1, float(el["entelagem"].get("de_xc", 0.0)), f"{nome}.entelagem", "entelagem")
    for k, cz in enumerate((el.get("estrutura") or {}).get("cruzadas") or []):
        q = it.get(f"{nome}.cruzadas{k}")
        if q is not None:
            usados.add(q["nome"])
            y0, y1 = sorted(abs(float(v)) for v in cz["y"])
            P.distribuida(peso_lado * q["massa"], y0, y1, float(cz.get("x_c", 0.55)), "nervuras em X", q["origem"])
    for cmd in el.get("controles") or []:
        q = it.get(f"{nome}.{cmd['nome']}.dobradica")
        if q is not None:
            usados.add(q["nome"])
            y0, y1 = sorted(abs(float(v)) for v in cmd["y"])
            y1 = min(y1, ponta)
            ys_ = np.linspace(y0, y1, N_AMOSTRAS)
            for yy in ys_:
                c = G["corda"](yy)
                xc = AG.SC.charneira_em(cmd, c, G["x_le"](yy) - G["pos"][0]) * c
                P.ponto(float(yy), peso_lado * q["massa"] / len(ys_), G["x_le"](yy) + xc, G["ze"](yy), "dobradiças", q["origem"])
    for nm_, q in it.items():
        if nm_ not in usados:
            P.ponto(float(np.clip(abs(q["cg"][1]), y[0], y[-1])), peso_lado * q["massa"], float(q["cg"][0]), float(q["cg"][2]), "outros do modelo", q["origem"])
    n_modelo = len(P.y)
    est_kg = float(sum(P.m[:n_modelo]))

    avisos = []
    extras = []
    for a in adicionais or []:
        nm_ = str(a.get("nome") or "adicional")
        y0 = abs(float(a.get("y_m", 0.0)))
        y1 = abs(float(a["y_fim_m"])) if a.get("y_fim_m") not in (None, "") else y0
        y0, y1 = min(y0, y1), max(y0, y1)
        if y1 > ponta * 1.001:
            avisos.append(f"{nm_}: y = {y1:g} m passa da ponta da asa ({ponta:g} m); a massa foi levada para a ponta.")
        y0, y1 = min(y0, ponta), min(y1, ponta)
        x_c = float(a.get("x_c", 0.35))
        if a.get("gramatura_g_m2") not in (None, ""):
            if V is None:
                V, T, lab, _, _ = AG._constroi_asa(el, nome, esq_)
                V, T = AG._gira(V, el), np.asarray(T)
            ar, cen = _triangulos_da_pele(V, T, lab, el, float(a.get("ate_xc", 1.1)), float(a.get("de_xc", 0.0)))
            yy = np.abs(cen[:, 1] - G["pos"][1])
            sel = (yy >= y0 - 1e-9) & (yy <= (y1 if y1 > y0 else ponta) + 1e-9)
            m_tot = peso_lado * float(ar[sel].sum()) * float(a["gramatura_g_m2"]) * 1e-3
            if m_tot <= 0:
                avisos.append(f"{nm_}: nenhuma pele no trecho pedido.")
                continue
            for a_, c_, s_ in zip(ar, cen, sel):
                if s_:
                    P.ponto(abs(float(c_[1] - G["pos"][1])), m_tot * a_ / ar[sel].sum(), float(c_[0]), float(c_[2]), nm_, "filme medido", 0.0)
            extras.append({"nome": nm_, "massa_kg": m_tot, "origem": f"filme {float(a['gramatura_g_m2']):g} g/m2 x area de pele"})
            continue
        m_ = float(a.get("massa_kg", 0.0))
        if not m_ > 0:
            avisos.append(f"{nm_}: massa precisa ser maior que zero; ignorada.")
            continue
        P.distribuida(m_, y0, y1, x_c, nm_, "informada", de_c=float(a["largura_c"]) if a.get("largura_c") not in (None, "") else None)
        extras.append({"nome": nm_, "massa_kg": m_, "origem": "informada"})
    extra_kg = float(sum(e["massa_kg"] for e in extras))

    escala = 1.0
    if massa_medida_kg:
        if massa_medida_kg <= extra_kg:
            raise ValueError(f"A massa medida da semi-asa ({massa_medida_kg:g} kg) nao passa da soma das adicionais ({extra_kg:g} kg).")
        escala = (massa_medida_kg - extra_kg) / est_kg if est_kg > 0 else 1.0
        for i in range(n_modelo):
            P.m[i] *= escala; P.S[i] *= escala; P.I[i] *= escala
        if escala > 1.5 or escala < 0.7:
            avisos.append(f"Para fechar a massa medida a estrutura do modelo teve de valer {escala:.2f} x o calculado: confira as adicionais (servo, aileron, cola, "
                          "fita) e a densidade dos materiais antes de confiar na distribuição.")
    pm, pS, pI, py = np.array(P.m), np.array(P.S), np.array(P.I), np.array(P.y)
    n = len(y)
    trib = np.zeros(n)
    dy = np.diff(y)
    trib[:-1] += 0.5 * dy; trib[1:] += 0.5 * dy
    cats = sorted(set(P.cat), key=lambda c: -pm[[k for k, cc in enumerate(P.cat) if cc == c]].sum())
    Mn, Sn, In = np.zeros(n), np.zeros(n), np.zeros(n)
    por_cat = {c: np.zeros(n) for c in cats}
    yc = np.clip(py, y[0], y[-1])
    j = np.clip(np.searchsorted(y, yc) - 1, 0, n - 2)
    t = (yc - y[j]) / (y[j + 1] - y[j])
    for idx, (jj, tt) in enumerate(zip(j, t)):
        for nn, w in ((jj, 1 - tt), (jj + 1, tt)):
            Mn[nn] += w * pm[idx]; Sn[nn] += w * pS[idx]; In[nn] += w * pI[idx]
            por_cat[P.cat[idx]][nn] += w * pm[idx]
    c_no = np.array([G["corda"](v) for v in y])
    m_lin = Mn / trib
    ok = m_lin > 1e-3 * m_lin.mean()
    S_lin, I_lin = Sn / trib, In / trib
    x_alfa_c = np.where(ok, S_lin / np.maximum(m_lin, 1e-12) / c_no, 0.1)
    r2 = np.where(ok, I_lin / np.maximum(m_lin, 1e-12) - (S_lin / np.maximum(m_lin, 1e-12)) ** 2, 0.0)
    r_cg_c = np.where(ok, np.sqrt(np.maximum(r2, 0.0)) / c_no, 0.28)
    r_cg_c = np.maximum(r_cg_c, 0.05)
    m_lin = np.where(ok, m_lin, 1e-3 * m_lin.mean())
    M = float(pm.sum())
    x_ea_no = np.array([G["xe"](v) for v in y])
    x_cg_abs = float(np.sum(Mn * (x_ea_no + np.where(ok, Sn / np.maximum(Mn, 1e-12), 0.0))) / Mn.sum())
    y_cg = float(np.sum(Mn * y) / Mn.sum())
    c_cg = float(np.interp(y_cg, y, c_no))
    x_cg_c = float((x_cg_abs - G["x_le"](y_cg)) / c_cg)
    saida = {"y": y.tolist(), "c": c_no.tolist(), "m_lin": m_lin.tolist(), "x_alfa_c": x_alfa_c.tolist(), "r_cg_c": r_cg_c.tolist(),
             "x_cg_c_local": ((x_ea_no - np.array([G["x_le"](v) for v in y])) / c_no + x_alfa_c).tolist(),
             "massa_kg": M, "massa_estrutura_modelo_kg": est_kg * escala, "massa_estrutura_calculada_kg": est_kg, "escala_estrutura": float(escala),
             "massa_adicionais_kg": extra_kg, "adicionais": extras, "x_cg_c": x_cg_c, "x_cg_m": x_cg_abs, "y_cg_m": y_cg,
             "categorias": [{"nome": c, "massa_kg": float(por_cat[c].sum()), "y_cg_m": float((por_cat[c] * y).sum() / max(por_cat[c].sum(), 1e-12)),
                             "m_lin": (por_cat[c] / trib).tolist()} for c in cats],
             "validacao": None, "avisos": avisos}
    if massa_medida_kg or x_cg_medido_c or y_cg_medido_m:
        v = {}
        if massa_medida_kg:
            v["massa"] = {"medido": float(massa_medida_kg), "modelo_sem_ajuste": est_kg + extra_kg, "erro_pct": 100 * (est_kg + extra_kg) / massa_medida_kg - 100}
            if abs(v["massa"]["erro_pct"]) > 8:
                avisos.append(f"O somado do modelo ({est_kg + extra_kg:.3f} kg) difere {abs(v['massa']['erro_pct']):.0f} % da medida: falta ou sobra massa nas adicionais.")
        if x_cg_medido_c:
            v["x_cg_c"] = {"medido": float(x_cg_medido_c), "modelo": x_cg_c, "erro_c": x_cg_c - float(x_cg_medido_c)}
            if abs(x_cg_c - x_cg_medido_c) > 0.03:
                avisos.append(f"O CG do modelo na corda (x/c = {x_cg_c:.3f}) está a {abs(x_cg_c - x_cg_medido_c):.3f} corda do medido: o flutter é sensível a isso; "
                              "reveja a posição das adicionais (servo, aileron, lastro).")
        if y_cg_medido_m:
            v["y_cg_m"] = {"medido": float(y_cg_medido_m), "modelo": y_cg, "erro_m": y_cg - float(y_cg_medido_m)}
            if abs(y_cg - y_cg_medido_m) > 0.05 * ponta:
                avisos.append(f"O CG do modelo na envergadura (y = {y_cg:.3f} m) está a {abs(y_cg - y_cg_medido_m) * 1000:.0f} mm do medido.")
        saida["validacao"] = v
    return saida
