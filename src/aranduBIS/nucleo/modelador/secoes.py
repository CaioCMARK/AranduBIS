from __future__ import annotations

import numpy as np

from . import aeronave_estrutura as ES
from . import aeronave_geometria as AG
from pathlib import Path

def _perfil_de(el, esq, sec):
    if "perfil_pontos" in el:
        pp = el["perfil_pontos"]
        anel, _ = AG.anel_de_arquivo(Path(esq.get("_pasta", ".")) / pp["arquivo"], pp["secao"])
        return [np.asarray(anel, float)] * len(sec)
    n = int(el.get("n_perfil", 40))
    if "secoes" in el and AG._quer_aneis(el):
        x, Z = AG._perfis_secoes(el, esq)
        return [ES.anel_de(x, zs, zi) for zs, zi in Z]
    x, zs, zi = ES.perfil_xy(el.get("perfil", "NACA 0012"), n, esq.get("_pasta", "."))
    A = ES.anel_de(x, zs, zi)
    return [A] * len(sec)

def secoes_da_asa(esq: dict, nome: str) -> dict:
    el = next((e for e in esq.get("elementos", []) if e.get("nome") == nome and e.get("tipo", "asa") == "asa"), None)
    if el is None:
        raise ValueError(f"asa {nome!r} nao existe no modelo")
    sec = AG._secoes(el)
    aneis = _perfil_de(el, esq, sec)
    cfg = el.get("estrutura") or {}
    ys = [q[1] for q in sec]
    nerv = AG._nervuras_y((cfg.get("nervuras") or {}).get("y", []), ys) if cfg.get("nervuras") else []
    saida = []
    for i, ((xle, y, zle, c, ainc), A) in enumerate(zip(sec, aneis)):
        ai = np.radians(ainc)
        cd, nd = np.array([np.cos(ai), 0.0, -np.sin(ai)]), np.array([np.sin(ai), 0.0, np.cos(ai)])
        P = np.array([xle, y, zle]) + c * (A[:, 0:1] * cd + A[:, 1:2] * nd)
        P = AG._gira(P, el)
        lg = [{"x_mm": 1000.0 * ES.posicao_x(l, c, y), "largura_mm": 1000.0 * float(l.get("largura", 0.00238))} for l in cfg.get("longarinas", [])
              if (lambda r: min(r) - 1e-6 <= y <= max(r) + 1e-6)(l.get("y") or [ys[0], ys[-1]])]
        tb = []
        for t in cfg.get("tubos", []):
            r = t.get("y") or [ys[0], ys[-1]]
            if min(r) - 1e-6 <= y <= max(r) + 1e-6:
                tb.append({"x_mm": 1000.0 * ES.posicao_x(t, c, y), "d_mm": 1000.0 * float(t["de"]), "lado": t.get("lado", "extradorso")})
        ctl = [k["nome"] for k in el.get("controles", []) if min(k["y"]) - 1e-9 <= abs(y) <= max(k["y"]) + 1e-9 and (k.get("modo", "sim") != "lado" or y > 0)]
        saida.append({"i": i, "y": float(y), "xle": float(xle), "zle": float(zle), "corda": float(c), "ainc": float(ainc),
                      "perfil": (el.get("secoes", [{}] * len(sec))[i].get("arquivo") or el.get("secoes", [{}] * len(sec))[i].get("perfil") or el.get("perfil") or "") if "secoes" in el else el.get("perfil", ""),
                      "anel": np.round(A, 5).tolist(), "anel3d": np.round(P, 5).tolist(), "longarinas": lg, "tubos": tb, "controles": ctl,
                      "nervura": any(abs(y - q) < 1e-6 for q in nerv)})
    ch = cfg.get("chapeado") or {}
    return {"asa": nome, "secoes": saida, "chapeado_ate_xc": float(ch["ate_xc"]) if ch.get("ate_xc") else None,
            "chapeado_mm": 1000.0 * float(ch["espessura"]) if ch.get("espessura") else None, "rolagem": float(el.get("rolagem", 0.0)),
            "posicao": [float(q) for q in el.get("posicao", [0, 0, 0])]}
