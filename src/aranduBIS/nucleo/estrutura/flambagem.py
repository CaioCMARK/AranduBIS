from __future__ import annotations

import math

import numpy as np

from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG
from .asa import INF, _elemento, _fim_do_chapeado, _perfis
from .materiais import propriedades

def sigma_cr_ortotropica(E1, E2, G12, nu12, t, a, b, fator=1.0, n_ondas=30):
    nu21 = nu12 * E2 / E1
    den = 12.0 * (1.0 - nu12 * nu21)
    D11, D22, D12, D66 = E1 * t ** 3 / den, E2 * t ** 3 / den, nu21 * E1 * t ** 3 / den, G12 * t ** 3 / 12.0
    f = min(D11 * (m * b / a) ** 2 + 2.0 * (D12 + 2.0 * D66) + D22 * (a / (m * b)) ** 2 for m in range(1, n_ondas + 1))
    return fator * math.pi ** 2 / (t * b * b) * f

def sigma_cr_curvo(E1, E2, G12, nu12, t, a, b, R, knockdown=1.0, nm=40, nn=40):
    nu21 = nu12 * E2 / E1
    den = 12.0 * (1.0 - nu12 * nu21)
    D11, D22, D12, D66 = E1 * t ** 3 / den, E2 * t ** 3 / den, nu21 * E1 * t ** 3 / den, G12 * t ** 3 / 12.0
    s11, s22, s12, s66 = 1.0 / E1, 1.0 / E2, -nu12 / E1, 1.0 / G12
    lam = (np.arange(1, nm + 1) * math.pi / a)[:, None]
    mu = (np.arange(1, nn + 1) * math.pi / b)[None, :]
    flex = (D11 * lam ** 4 + 2 * (D12 + 2 * D66) * lam ** 2 * mu ** 2 + D22 * mu ** 4) / (t * lam ** 2)
    mem = 0.0 if not np.isfinite(R) else (lam ** 2 / R ** 2) / (s22 * lam ** 4 + (s66 + 2 * s12) * lam ** 2 * mu ** 2 + s11 * mu ** 4)
    return knockdown * float((flex + mem).min())

def tau_cr_alma(E_eff, nu, t, h, a):
    k = 5.34 + 4.0 * (h / a) ** 2 if a >= h else 4.0 + 5.34 * (h / a) ** 2
    return k * math.pi ** 2 * E_eff / (12.0 * (1.0 - nu * nu)) * (t / h) ** 2

def _m(adm, atua):
    return INF if atua <= 1e-9 else min(INF, adm / atua - 1.0)

def _geom(sec_el, x, Z, el, cfg, y):
    q = AG._secao_em(sec_el, float(y)); i, t = AG._no_vao(sec_el, float(y))
    zs, zi = (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]
    c = float(q[3])
    xe = _fim_do_chapeado(cfg.get("chapeado") or {}, y)
    m = x <= xe
    xx, zz = np.append(x[m], xe), np.append(zs[m], np.interp(xe, x, zs))
    arco = float(np.hypot(np.diff(xx), np.diff(zz)).sum()) * c
    area = float(np.trapezoid(zs - zi, x)) * c * c if hasattr(np, "trapezoid") else float(np.trapz(zs - zi, x)) * c * c
    pts = np.column_stack([xx, zz]) * c
    corda = float(np.hypot(*(pts[-1] - pts[0])))
    d = pts[-1] - pts[0]
    sag = float(np.max(np.abs(d[0] * (pts[:, 1] - pts[0, 1]) - d[1] * (pts[:, 0] - pts[0, 0])) / max(corda, 1e-9)))
    R = corda ** 2 / (8 * sag) + sag / 2 if sag > 1e-5 else float("inf")
    return c, arco, area, R

def verifica(esq: dict, nome: str, asa: dict, mats: dict | None = None, qualidade_balsa: float = 1.0, E_transv_GPa: float = 0.12,
             knockdown: float = 0.5, margem_alvo: float = 0.0) -> dict:
    el = _elemento(esq, nome)
    cfg = el.get("estrutura") or {}
    sec_el, x, Z = _perfis(el, esq)
    mb = propriedades("balsa", esq, mats, qualidade_balsa)
    E1, G, nu = mb["E"], mb["G"], mb["nu"]
    E2 = E_transv_GPa * 1e9
    rho = ES.densidade("balsa", esq)
    y = np.array(asa["y"])
    tens_pele = np.max([c["tensao_MPa"]["pele_comp"] for c in asa["casos"]], axis=0) * 1e6
    tens_alma = np.max([c["tensao_MPa"]["alma_cis"] for c in asa["casos"]], axis=0) * 1e6
    ch = cfg.get("chapeado") or {}
    ts = float(ch.get("espessura", 0.001))
    tw = float((cfg.get("longarinas") or [{}])[0].get("largura", 0.00238))
    tn = float((cfg.get("nervuras") or {}).get("espessura", 0.00238))
    ys_n = (cfg.get("nervuras") or {}).get("y", [])
    ymax = float(y[-1])
    bordas = sorted({0.0, ymax} | {round(abs(float(v)), 9) for v in ys_n if abs(float(v)) <= ymax + 1e-9})
    paineis, sup = [], 0.0
    for y0, y1 in zip(bordas[:-1], bordas[1:]):
        a = y1 - y0
        if a < 0.02:
            continue
        no = (y >= y0 - 1e-9) & (y <= y1 + 1e-9)
        ym = 0.5 * (y0 + y1)
        c, arco, area, R = _geom(sec_el, x, Z, el, cfg, ym)
        s_ = max([float(tens_pele[no].max()) if no.any() else 0.0] + [float(np.interp(v, y, tens_pele)) for v in (y0, y1)])
        t_ = max([float(tens_alma[no].max()) if no.any() else 0.0] + [float(np.interp(v, y, tens_alma)) for v in (y0, y1)])
        h = float(np.interp(ym, y, asa["estacoes"]["h"]))
        p = {"y0": y0, "y1": y1, "a": a, "b": arco, "h": h, "c": c, "sigma_pele_MPa": s_ / 1e6, "tau_alma_MPa": t_ / 1e6}
        if ch and arco > 0:
            kd = lambda aa, f=knockdown, r=R: sigma_cr_curvo(E1, E2, G, nu, ts, aa, arco, r, f)
            cr = kd(a)
            p.update(R=R if np.isfinite(R) else None, sigma_cr_MPa=cr / 1e6, sigma_cr_plana_MPa=sigma_cr_ortotropica(E1, E2, G, nu, ts, a, arco) / 1e6,
                     margem_pele=_m(cr, s_), knockdown_para_margem_zero=float(s_ / max(sigma_cr_curvo(E1, E2, G, nu, ts, a, arco, R, 1.0), 1e-9)))
            alvo = (1.0 + margem_alvo) * s_
            a_req = None
            for aa in np.geomspace(max(0.02, 0.1 * a), a, 60):
                if kd(aa) >= alvo:
                    a_req = float(aa)
            p["vao_necessario"] = a_req
            if p["margem_pele"] >= margem_alvo:
                p["nervuras_falsas"] = 0
            elif a_req is not None and a_req >= 0.04:
                p["nervuras_falsas"] = math.ceil(a / a_req) - 1
            else:
                p["nervuras_falsas"] = None
            p["massa_nervura_g"] = 1000.0 * area * tn * rho
        if h > 0:
            tc = tau_cr_alma(math.sqrt(E1 * E2), nu, tw, h, a)
            p["tau_cr_MPa"] = tc / 1e6
            p["margem_alma"] = _m(tc, t_)
        paineis.append(p)
    pele = [p for p in paineis if "margem_pele" in p]
    pior_pele = min(pele, key=lambda p: p["margem_pele"]) if pele else None
    alma = [p for p in paineis if "margem_alma" in p]
    pior_alma = min(alma, key=lambda p: p["margem_alma"]) if alma else None
    extra = sum((p.get("nervuras_falsas") or 0) * 2 for p in pele)
    massa_extra = sum((p.get("nervuras_falsas") or 0) * 2 * p.get("massa_nervura_g", 0.0) for p in pele)
    ref = pior_pele or paineis[0]
    sens = {"a": [], "margem": [], "b": ref["b"]} if pior_pele else None
    if pior_pele:
        for aa in np.geomspace(0.02, 0.6, 50):
            sens["a"].append(float(aa))
            sens["margem"].append(float(min(20.0, _m(sigma_cr_curvo(E1, E2, G, nu, ts, aa, ref["b"], ref["R"] or float("inf"), knockdown), ref["sigma_pele_MPa"] * 1e6))))
    return {"nome": nome, "paineis": paineis, "pior_pele": pior_pele, "pior_alma": pior_alma, "nervuras": [float(v) for v in bordas[1:-1]],
            "n_nervuras_falsas": extra, "paineis_sem_solucao": [p["y0"] for p in pele if p.get("nervuras_falsas") is None], "massa_falsas_g": massa_extra, "sensibilidade": sens, "E_transv_GPa": E_transv_GPa,
            "knockdown": knockdown, "espessura_chapeado": ts}
