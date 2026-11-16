from __future__ import annotations

import math
import warnings

import numpy as np

from .. import discretizacao as DS
from .aeronave_vlm import superficies
from .vlm import VLM

FS = 1.25


def _grandezas(esq, n_span_por_nome, n_chord, V, rho):
    with warnings.catch_warnings(), DS.silencio():
        warnings.simplefilter("ignore")
        sup = superficies(esq, n_chord=n_chord)
        for s in sup:
            s.n_span = max(2, int(n_span_por_nome[s.nome]))
        v = VLM(sup)
    r0, r5 = v.resolver([0.0, 5.0], V=V, rho=rho)
    CLa = (r5.CL - r0.CL) / math.radians(5.0)
    Cma = (r5.Cm - r0.Cm) / math.radians(5.0)
    x_np = v.x_ref - Cma / CLa * v.c_ref if abs(CLa) > 1e-9 else float("nan")
    return v.N, {"CLα (1/rad)": CLa, "ponto neutro x (m)": x_np, "CL a 5°": r5.CL, "CDi a 5°": r5.CDi, "e de Oswald": r5.e_oswald}


def richardson(f1, f2, f3, r=2.0):
    d12, d23 = f1 - f2, f2 - f3
    if abs(d23) < 1e-14 * max(1.0, abs(f3)):
        return f3, None, 0.0, "não muda mais"
    if d12 * d23 <= 0:
        return None, None, FS * max(abs(d12), abs(d23)) / max(abs(f2), 1e-30), "oscila: erro pela maior diferença"
    p = math.log(abs(d12 / d23)) / math.log(r)
    if p <= 0.3:
        return None, p, FS * max(abs(d12), abs(d23)) / max(abs(f2), 1e-30), "convergência lenta: erro pela maior diferença"
    ext = f3 + (f3 - f2) / (r ** p - 1.0)
    return ext, p, FS * abs(ext - f2) / max(abs(ext), 1e-30), ""


def vlm(esq: dict, V: float = 15.0, rho: float = 1.1) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base = superficies(esq)
    ns0 = {s.nome: s.n_span for s in base}
    nc0 = base[0].n_chord
    familias = []
    for nome, malhas in (("Painéis na envergadura (× malha atual)", [(0.5, 1), (1, 1), (2, 1)]),
                         ("Painéis na corda (× malha atual)", [(1, 0.5), (1, 1), (1, 2)])):
        val, rot = [], []
        for fs, fc in malhas:
            ns = {k: max(2, round(v * fs)) for k, v in ns0.items()}
            nc = max(1, round(nc0 * fc))
            N, g = _grandezas(esq, ns, nc, V, rho)
            val.append(g)
            rot.append(f"{'½' if (fs, fc) in ((0.5, 1), (1, 0.5)) else '1' if (fs, fc) == (1, 1) else '2'}× ({N} painéis)")
        gs = []
        for k in val[0]:
            f1, f2, f3 = (v[k] for v in val)
            ext, p, err, nota = richardson(f1, f2, f3)
            gs.append({"nome": k, "valores": [f1, f2, f3], "extrapolado": ext, "p": p, "gci": err, "nota": nota})
        familias.append({"nome": nome, "malhas": rot, "grandezas": gs})
    piores = [g for f in familias for g in f["grandezas"] if g["gci"] is not None and g["gci"] > 0.02]
    nota = ("GCI = erro estimado da malha atual (Roache, Fs = 1,25). Abaixo de 1 a 2 % a malha está boa para projeto. "
            "Na envergadura o VLM converge devagar (ordem observada 0,5 a 1: a ponta da asa segura); na corda o CLα quase "
            "não muda e o que mais pede painéis é o CL de arqueamento (perfil arqueado). ")
    if piores:
        nota += "Acima de 2 %: " + ", ".join(sorted({g["nome"] for g in piores})) + " — refine a família que mais muda."
    DS.registra("VLM", "Estudo de convergência", "3 malhas × 2 famílias", "auto", "pedido pelo usuário no painel de malha")
    return {"familias": familias, "nota": nota, "n_span_atual": ns0, "n_chord_atual": nc0}
