from __future__ import annotations

import math
import warnings

import numpy as np

from .arrasto import CD_ROMBUDO, Componente, CorpoRombudo, fator_forma_corpo, fator_forma_perfil
from .aeronave_vlm import sustenta

ESBELTEZ_CORPO = 3.0
CD_CORPO_ROMBUDO = 0.9
CD_MOTOR = 0.5

def _aero(el: dict) -> bool:
    return el.get("camada", "aero") != "estrutura"

def _poli(c):
    c = np.asarray(c, float)
    x, z = c[:, 0], c[:, 1]
    A = 0.5 * abs(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1)))
    P = float(np.sum(np.hypot(np.diff(np.r_[x, x[0]]), np.diff(np.r_[z, z[0]]))))
    return float(A), P

def componentes(esq: dict) -> tuple[list, list[str]]:
    comp, notas = [], []
    placas = []
    for el in esq.get("elementos", []):
        tipo, nome = el.get("tipo"), el.get("nome", "?")
        if tipo == "placa":
            if not _aero(el):
                notas.append(f"{nome}: camada de estrutura, dentro do envelope: fora.")
                continue
            c = np.asarray(el["contorno"], float)
            t = float(el.get("espessura", 0.05))
            A, P = _poli(c)
            ext_x, ext_z = c[:, 0].max() - c[:, 0].min(), c[:, 1].max() - c[:, 1].min()
            placas.append((c[:, 0].min(), c[:, 0].max(), c[:, 1].min(), c[:, 1].max(), t / 2, nome))
            frontal = t * ext_z
            d_eq = math.sqrt(4.0 * max(frontal, 1e-9) / math.pi)
            f = ext_x / d_eq
            if f < ESBELTEZ_CORPO:
                comp.append(CorpoRombudo(nome, frontal, CD_CORPO_ROMBUDO))
                notas.append(f"{nome}: curto e gordo (comprimento/diametro {f:.1f}): tratado como corpo rombudo.")
            else:
                comp.append(Componente(nome, 2.0 * A + P * t, ext_x, fator_forma_corpo(f)))
        elif tipo == "roda":
            comp.append(CorpoRombudo(nome, float(el["diametro"]) * float(el.get("largura", 0.01)), CD_ROMBUDO["roda_exposta"]))
        elif tipo == "corpo":
            est = el.get("estacoes", [])
            if est:
                a = max(float(e["a"]) for e in est); b = max(float(e["b"]) for e in est)
                comp.append(CorpoRombudo(nome, math.pi * a * b, CD_MOTOR))
        elif tipo == "asa" and not sustenta(el):
            notas.append(f"{nome}: nao sustenta (helice): o arrasto dela esta na tracao, nao aqui.")
    for el in esq.get("elementos", []):
        tipo, nome = el.get("tipo"), el.get("nome", "?")
        if tipo == "trelica" and _aero(el):
            nos = np.asarray(el["nos"], float)
            frontal, fora = 0.0, 0
            for i, j, k in el["barras"]:
                a, b = nos[i], nos[j]
                dentro = lambda p: any(x0 - 5e-3 <= p[0] <= x1 + 5e-3 and z0 - 5e-3 <= p[2] <= z1 + 5e-3 and abs(p[1]) <= h + 5e-3
                                       for x0, x1, z0, z1, h, _ in placas)
                if dentro(a) and dentro(b):
                    continue
                fora += 1
                frontal += float(el["tubos"][k]["de"]) * math.hypot(b[1] - a[1], b[2] - a[2])
            if frontal > 0:
                comp.append(CorpoRombudo(nome, frontal, CD_ROMBUDO["cilindro"]))
            notas.append(f"{nome}: {fora} de {len(el['barras'])} tubos expostos (os de dentro de uma placa nao contam).")
        elif tipo == "asa" and sustenta(el) and abs(float(el.get("rolagem", 0.0))) > 60.0:
            sec = el.get("secoes", [])
            if len(sec) >= 2:
                ys = [abs(float(s["y"])) for s in sec]
                cs = [float(s["corda"]) for s in sec]
                o = np.argsort(ys); area = float(np.sum(np.diff(np.take(ys, o)) * (np.take(cs, o)[1:] + np.take(cs, o)[:-1]) / 2))
                comp.append(Componente(nome, 2.0 * area, float(np.mean(cs)), fator_forma_perfil(0.12)))
                notas.append(f"{nome}: superficie vertical, sem polar: arrasto de atrito de placa fina.")
    return comp, notas

def parasita(esq: dict, S_ref: float, V: float, rho: float = 1.1) -> dict:
    from .arrasto import arrasto_parasita
    comp, notas = componentes(esq)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        total, partes = arrasto_parasita(comp, S_ref, V, rho, detalhar=True)
    return {"CD": float(total), "CdA": float(total * S_ref), "S_ref": float(S_ref),
            "partes": [{"nome": k, "CD": float(v), "CdA": float(v * S_ref)} for k, v in sorted(partes.items(), key=lambda kv: -kv[1])],
            "notas": notas}
