from __future__ import annotations

import numpy as np

from ..fe import Sistema
from ..fe.inercia import G0, alivio
from ..modelador import aeronave_geometria as AG
from .cauda import _grupos, margens_barras, monta

def _rodas(esq):
    rodas = []
    for el in esq.get("elementos", []):
        if el.get("tipo") == "roda":
            p = el.get("posicao", [0, 0, 0])
            rodas.append({"nome": el["nome"], "centro": np.array([p[0], el.get("y", p[1]), p[2]], float), "raio": 0.5 * float(el.get("diametro", 0.09))})
    return rodas

def _com_solda(esq, r):
    import copy
    e2 = copy.deepcopy(esq); zonas = []
    outros = [np.asarray(el["nos"], float) for el in e2["elementos"] if el.get("tipo") == "trelica" and el["nome"] != "trem"]
    for el in e2["elementos"]:
        if el.get("tipo") != "trelica" or el["nome"] != "trem" or len(el["nos"]) != 2 or len(el["barras"]) != 1:
            continue
        a, b = (np.asarray(q, float) for q in el["nos"]); L = float(np.linalg.norm(b - a)); u = (b - a) / L; tipo = el["barras"][0][2]
        ts = []
        for N in outros:
            d = N - a; t = d @ u; perp = np.linalg.norm(d - np.outer(t, u), axis=1)
            ts += [float(x) for x, q in zip(t, perp) if q < 3e-3 and 3e-3 < x < L - 3e-3]
        pes = []
        for t in sorted(ts):
            if not pes or t - pes[-1] > 3e-3:
                pes.append(t)
        if pes:
            lim = [0.9 * pes[0], 0.9 * (L - pes[-1])] + [0.45 * (b_ - a_) for a_, b_ in zip(pes, pes[1:])]
            r = min([r] + lim)
        pts = [0.0, L]
        for t in pes:
            pts += [t - r, t + r]
            zonas.append((a + u * t, [a + u * (t - r), a + u * (t + r)]))
        pts = sorted(set(round(x, 6) for x in pts))
        el["nos"] = [(a + u * t).tolist() for t in pts]; el["barras"] = [[i, i + 1, tipo] for i in range(len(pts) - 1)]
    return e2, zonas

def analisa(esq: dict, massa_kg: float | None = None, x_cg: float | None = None, z_cg: float | None = None, fator_pouso: float = 5.4,
            atrito_pouso: float = 0.3, fator_taxi_y: float = 0.5, fator_taxi_z: float = 1.0, fator_seguranca: float = 1.2,
            K_flambagem: float = 0.8, raio_inercia: float = 0.25, raio_solda: float = 0.0, mats: dict | None = None, qualidade_carbono: float = 1.0) -> dict:
    mc = AG.massa_e_cg(AG.constroi(esq))
    cg = mc["cg_m"]
    massa = float(massa_kg) if massa_kg else float(mc["massa_kg"])
    if not massa or massa <= 0:
        raise ValueError("sem massa: declare as pecas no modelo ou informe a massa")
    xcg = float(x_cg) if x_cg is not None else float(cg[0]); zcg = float(z_cg) if z_cg is not None else float(cg[2])
    W = massa * G0
    rodas = _rodas(esq)
    if len(rodas) < 3:
        raise ValueError("o modelo precisa de ao menos tres rodas (duas principais e a bequilha) para o pouso")
    nariz = min(rodas, key=lambda r: r["centro"][0])
    principais = [r for r in rodas if r is not nariz]
    x_m = float(np.mean([r["centro"][0] for r in principais])); x_n = float(nariz["centro"][0])
    if not (x_n < xcg < x_m):
        raise ValueError(f"o CG (x = {xcg:.3f} m) precisa ficar entre a bequilha ({x_n:.3f}) e as principais ({x_m:.3f}) para o pouso em tres pontos")
    esq_m, zonas = _com_solda(esq, raio_solda) if raio_solda > 0 else (esq, [])
    m, pos, info, avisos = monta(esq_m, mats, qualidade_carbono, tol=3e-3, divide=4e-3)
    for k, (centro, ext) in enumerate(zonas):
        i0 = int(np.argmin(np.linalg.norm(pos - centro, axis=1))) + 1
        esc = [int(np.argmin(np.linalg.norm(pos - q, axis=1))) + 1 for q in ext]
        if np.linalg.norm(pos[i0 - 1] - centro) < 3e-3 and i0 not in esc:
            m.rigido(90000 + k, i0, esc)
    grupos = _grupos(m)
    if len(grupos) > 1:
        avisos.append(f"A trelica tem {len(grupos)} partes sem ligacao ({', '.join(str(len(g)) for g in grupos)} nos): so a que tem as rodas e verificada.")
    no_de = lambda p, tol=0.02: (int(np.argmin(np.linalg.norm(pos - p, axis=1))) + 1) if np.min(np.linalg.norm(pos - p, axis=1)) < tol else None
    nos_roda = {}
    novo = max(m.nos) + 1
    for r in principais:
        n = no_de(r["centro"])
        if n is None:
            raise ValueError(f"a roda {r['nome']!r} nao esta ligada a trelica (nenhum no a menos de 2 cm do centro)")
        nos_roda[r["nome"]] = n
    d = np.linalg.norm(pos - nariz["centro"], axis=1)
    perto = [int(i) + 1 for i in np.argsort(d)[:2]]
    if d[perto[0] - 1] > 0.15:
        raise ValueError("a bequilha nao tem nos da trelica a menos de 15 cm (mancais)")
    m.no(novo, *nariz["centro"]); m.rigido(novo, novo, perto)
    nos_roda[nariz["nome"]] = novo
    comp = next(g for g in grupos if perto[0] in g)
    ligados = set(comp)
    todas = [r for r in rodas]
    barras = [(eid, pid, ga, gb) for eid, pid, ga, gb, _ in m.barras]
    centro_m = np.array([xcg, 0.0, zcg])
    P = np.array([pos[i - 1] for i in sorted(ligados)])
    ids = sorted(ligados)
    dm = np.linalg.norm(P - centro_m, axis=1)
    sel = [ids[i] for i in range(len(ids)) if dm[i] <= raio_inercia]
    if len(sel) < 4:
        sel = [ids[i] for i in np.argsort(dm)[:8]]
    m_i = massa / len(sel)
    pos_sel = np.array([pos[i - 1] for i in sel])
    ancora = sel[int(np.argmin([np.linalg.norm(pos[i - 1] - centro_m) for i in sel]))]
    m.engasta([ancora])
    casos = [("pouso_3_pontos", f"{fator_pouso:g} x peso na vertical, tres pontos, spin-up {atrito_pouso:g}", fator_pouso, True, 0.0, atrito_pouso),
             ("pouso_2_pontos", f"{fator_pouso:g} x peso so nas principais, spin-up {atrito_pouso:g}", fator_pouso, False, 0.0, atrito_pouso),
             ("taxi_lateral", f"{fator_taxi_z:g} x peso vertical e {fator_taxi_y:g} x peso lateral nos tres pneus", fator_taxi_z, True, fator_taxi_y, 0.0)]
    resultados = []
    for k, (nome, desc, n_z, tres, n_y, mu) in enumerate(casos, 1):
        Rtot = n_z * W
        if tres:
            Rm, Rn = Rtot * (xcg - x_n) / (x_m - x_n), Rtot * (x_m - xcg) / (x_m - x_n)
        else:
            Rm, Rn = Rtot, 0.0
        externas, cargas_roda = [], {}
        for r in todas:
            R = Rn if r is nariz else Rm / len(principais)
            Fy = n_y * W * (R / Rtot) if Rtot > 0 else 0.0
            Fx = mu * R if r is not nariz else 0.0
            F = np.array([Fx, Fy, R])
            ponto = r["centro"] - np.array([0.0, 0.0, r["raio"]])
            braco = np.array([0.0, 0.0, -r["raio"]])
            Mc = np.cross(braco, F)
            Mc[1] = 0.0
            externas.append((r["centro"], F, Mc))
            cargas_roda[r["nome"]] = {"R": float(R), "Fx": float(Fx), "Fy": float(Fy)}
            m.carga(k, nos_roda[r["nome"]], [F[0], F[1], F[2], Mc[0], Mc[1], Mc[2]])
        f, a_, alfa = alivio(pos_sel, np.full(len(sel), m_i), centro_m, externas)
        for i, n in enumerate(sel):
            m.carga(k, n, [f[i, 0], f[i, 1], f[i, 2], 0, 0, 0])
        resultados.append((nome, desc, cargas_roda, a_, alfa))
    S = Sistema(m)
    saida = []
    for k, (nome, desc, cargas_roda, a_, alfa) in enumerate(resultados, 1):
        r = S.estatica(k)
        lista = margens_barras(r["esforcos"], barras, info, pos, ligados, esq, mats, qualidade_carbono, fator_seguranca, K_flambagem)
        piores = sorted(lista, key=lambda b: (b["curta"], b["margem"]))[:8]
        curtas = sorted((b for b in lista if b["curta"]), key=lambda b: b["margem"])[:3]
        eixo = [b for b in lista if b["elemento"] == "trem"]
        desl = {rr["nome"]: [1000 * float(x) for x in r["u"][nos_roda[rr["nome"]]][:3]] for rr in todas}
        saida.append({"caso": nome, "descricao": desc, "rodas": cargas_roda, "margem": piores[0]["margem"], "piores": piores, "curtas": curtas,
                      "eixo_margem": min((b["margem"] for b in eixo), default=None), "deslocamento_rodas_mm": desl,
                      "a_g": [float(x) / G0 for x in a_], "alfa_rad_s2": [float(x) for x in alfa], "residuo": r["residuo_livres"]})
    pior = min(saida, key=lambda c: c["margem"])
    return {"casos": saida, "critico": {"caso": pior["caso"], "barra": pior["piores"][0]["id"], "modo": pior["piores"][0]["modo"], "margem": float(pior["margem"]),
            "elemento": pior["piores"][0]["elemento"], "tubo": pior["piores"][0]["tubo"]}, "massa_kg": massa, "peso_N": W, "cg": [xcg, zcg],
            "x_principais": x_m, "x_bequilha": x_n, "n_nos_inercia": len(sel), "n_barras": len(m.barras), "n_nos": len(m.nos), "zonas_solda": len(zonas), "raio_solda": raio_solda, "avisos": avisos,
            "fator_seguranca": fator_seguranca}
