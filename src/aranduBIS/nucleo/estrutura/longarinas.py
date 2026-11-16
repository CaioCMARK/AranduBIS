from __future__ import annotations

import math

import numpy as np

from ..modelador import aeronave_estrutura as ES

TIPOS = ("alma", "tubo", "caixao")
CARBONO = {"tubo_carbono", "fibra_carbono", "carbono"}

PADRAO_CAIXAO = {"largura_caixa": 0.02, "n_almas": 2, "espessura_alma": 0.0016, "material_alma": "balsa",
                 "espessura_mesa": 0.003, "material_mesa": "spruce"}
PADRAO_TUBO = {"de": 0.012, "di": 0.010, "material": "tubo_carbono", "lado": "meio"}

def tipo(lg: dict) -> str:
    t = lg.get("tipo", "alma")
    if t not in TIPOS:
        raise ValueError(f"longarina de tipo {t!r} desconhecido: use um de {TIPOS}")
    return t

def ativa(item: dict, y: float) -> bool:
    y0, y1 = item.get("y") or (-1e9, 1e9)
    return min(y0, y1) - 1e-9 <= y <= max(y0, y1) + 1e-9

def _p(lg: dict, k: str, padrao: dict):
    return lg.get(k, padrao[k])

def tem_alma(lg: dict) -> bool:
    return tipo(lg) in ("alma", "caixao")

def materiais(cfg: dict) -> set[str]:
    m = {"balsa"}
    for lg in cfg.get("longarinas", []):
        t = tipo(lg)
        if t == "alma":
            m.add(lg.get("material", "balsa"))
        elif t == "tubo":
            m.add(lg.get("material", PADRAO_TUBO["material"]))
        else:
            m.add(_p(lg, "material_alma", PADRAO_CAIXAO)); m.add(_p(lg, "material_mesa", PADRAO_CAIXAO))
    for tb in cfg.get("tubos", []):
        m.add(tb.get("material", "tubo_carbono"))
    return m

def _z(x, z_, xc):
    return float(np.interp(xc, x, z_))

def primitivas(lg: dict, x, zs, zi, c: float, y: float) -> dict:
    t = tipo(lg)
    xs = ES.posicao_x(lg, c, y)
    zu, zl = _z(x, zs, xs / c) * c, _z(x, zi, xs / c) * c
    out = {"tipo": t, "x": xs, "almas": [], "tubos": [], "mesas": [], "celulas": []}
    if t == "alma":
        out["almas"].append({"x": xs, "tw": float(lg.get("largura", 0.00238)), "zt": zu, "zb": zl, "mat": lg.get("material", "balsa")})
    elif t == "tubo":
        de, di = float(_p(lg, "de", PADRAO_TUBO)), float(_p(lg, "di", PADRAO_TUBO))
        lado = lg.get("lado", "meio")
        z = 0.5 * (zu + zl) if lado == "meio" else (zu - 0.5 * de if lado == "extradorso" else zl + 0.5 * de)
        out["tubos"].append({"x": xs, "z": z, "de": de, "di": di, "mat": lg.get("material", PADRAO_TUBO["material"]), "fura": True})
        if de > zu - zl:
            out["aviso"] = f"y = {y:.2f} m: o tubo-longarina de {1000 * de:.1f} mm nao cabe no perfil ({1000 * (zu - zl):.1f} mm)"
    else:
        b = float(_p(lg, "largura_caixa", PADRAO_CAIXAO)); n = int(_p(lg, "n_almas", PADRAO_CAIXAO))
        tw, tm = float(_p(lg, "espessura_alma", PADRAO_CAIXAO)), float(_p(lg, "espessura_mesa", PADRAO_CAIXAO))
        bm = float(lg.get("largura_mesa", b))
        ma, mm = _p(lg, "material_alma", PADRAO_CAIXAO), _p(lg, "material_mesa", PADRAO_CAIXAO)
        a0, a1 = xs - 0.5 * bm, xs + 0.5 * bm
        zt = 0.5 * (_z(x, zs, a0 / c) + _z(x, zs, a1 / c)) * c
        zb = 0.5 * (_z(x, zi, a0 / c) + _z(x, zi, a1 / c)) * c
        out["mesas"] += [{"x0": a0, "x1": a1, "t": tm, "z": zt - 0.5 * tm, "lado": "sup", "mat": mm},
                         {"x0": a0, "x1": a1, "t": tm, "z": zb + 0.5 * tm, "lado": "inf", "mat": mm}]
        xw = [xs - 0.5 * b + 0.5 * tw, xs + 0.5 * b - 0.5 * tw] if n >= 2 else [xs]
        for xa in xw:
            out["almas"].append({"x": xa, "tw": tw, "zt": _z(x, zs, xa / c) * c - tm, "zb": _z(x, zi, xa / c) * c + tm, "mat": ma})
        if n >= 2:
            out["celula"] = {"b": b - tw, "h": (zt - zb) - tm, "tw": tw, "tm": tm, "mat_alma": ma, "mat_mesa": mm, "x": xs}
        if 2 * tm >= zt - zb:
            out["aviso"] = f"y = {y:.2f} m: as mesas da viga caixao ({1000 * tm:.1f} mm cada) nao cabem no perfil ({1000 * (zt - zb):.1f} mm)"
    return out

def gj_celula(cel: dict, mats: dict) -> float:
    b, h = cel["b"], cel["h"]
    if b <= 0 or h <= 0:
        return 0.0
    Ga, Gm = mats[cel["mat_alma"]]["G"], mats[cel["mat_mesa"]]["G"]
    return 4.0 * (b * h) ** 2 / (2.0 * h / (Ga * cel["tw"]) + 2.0 * b / (Gm * cel["tm"]))

def gj_tubo(de: float, di: float, G: float) -> float:
    return G * math.pi / 32.0 * (de ** 4 - di ** 4)

def poligonos(lg: dict, x, zs, zi, c: float, y: float) -> list[tuple[str, str, list, list]]:
    p = primitivas(lg, x, zs, zi, c, y)
    out = []
    for k, a in enumerate(p["almas"]):
        u0, u1 = (a["x"] - 0.5 * a["tw"]) / c, (a["x"] + 0.5 * a["tw"]) / c
        if p["tipo"] == "alma":
            w = [_z(x, zs, u0), _z(x, zs, u1), _z(x, zi, u1), _z(x, zi, u0)]
        else:
            w = [a["zt"] / c, a["zt"] / c, a["zb"] / c, a["zb"] / c]
        out.append((f"alma{k}", a["mat"], [u0, u1, u1, u0], w))
    for m in p["mesas"]:
        u0, u1 = m["x0"] / c, m["x1"] / c
        if m["lado"] == "sup":
            w = [_z(x, zs, u0), _z(x, zs, u1), _z(x, zs, u1) - m["t"] / c, _z(x, zs, u0) - m["t"] / c]
        else:
            w = [_z(x, zi, u0) + m["t"] / c, _z(x, zi, u1) + m["t"] / c, _z(x, zi, u1), _z(x, zi, u0)]
        out.append((f"mesa_{m['lado']}", m["mat"], [u0, u1, u1, u0], w))
    return out

def recortes(cfg: dict, x, zs, zi, c: float, y: float) -> list[dict]:
    out = []
    for lg in cfg.get("longarinas", []):
        if not ativa(lg, y):
            continue
        p = primitivas(lg, x, zs, zi, c, y)
        for a in p["almas"]:
            if p["tipo"] == "alma":
                out.append({"forma": "fenda", "x0": a["x"] - 0.5 * a["tw"], "x1": a["x"] + 0.5 * a["tw"]})
        for t in p["tubos"]:
            out.append({"forma": "furo", "x": t["x"], "z": t["z"], "d": t["de"]})
        if p["tipo"] == "caixao":
            m0 = p["mesas"][0]
            b = float(_p(lg, "largura_caixa", PADRAO_CAIXAO))
            out.append({"forma": "caixa", "x0": p["x"] - 0.5 * max(b, m0["x1"] - m0["x0"]), "x1": p["x"] + 0.5 * max(b, m0["x1"] - m0["x0"])})
    for tb in cfg.get("tubos", []):
        if not ativa(tb, y):
            continue
        de = float(tb["de"]); xt = ES.posicao_x(tb, c, y); lado = tb.get("lado", "extradorso")
        zu, zl = _z(x, zs, xt / c) * c, _z(x, zi, xt / c) * c
        z = 0.5 * (zu + zl) if lado == "meio" else (zu - 0.5 * de if lado == "extradorso" else zl + 0.5 * de)
        out.append({"forma": "furo", "x": xt, "z": z, "d": de, "borda": lado != "meio"})
    return out
