from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

import numpy as np

_NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"

def _mat_mul(a, b):
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])

def _transform(txt):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for nome, args in re.findall(r"(\w+)\s*\(([^)]*)\)", txt or ""):
        v = [float(q) for q in re.findall(_NUM, args)]; n = nome.lower()
        if n == "translate": t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        elif n == "scale": t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif n == "matrix": t = tuple(v[:6])
        elif n == "rotate":
            a = math.radians(v[0]); c, s = math.cos(a), math.sin(a); t = (c, s, -s, c, 0, 0)
            if len(v) >= 3: t = _mat_mul(_mat_mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        else: continue
        m = _mat_mul(m, t)
    return m

def _arco(p0, rx, ry, phi, fa, fs, p1, n_min=8):
    x0, y0 = p0; x1, y1 = p1
    if rx == 0 or ry == 0 or (x0 == x1 and y0 == y1): return [p1]
    ph = math.radians(phi); c, s = math.cos(ph), math.sin(ph); dx, dy = 0.5 * (x0 - x1), 0.5 * (y0 - y1); xp, yp = c * dx + s * dy, -s * dx + c * dy; rx, ry = abs(rx), abs(ry); lam = xp ** 2 / rx ** 2 + yp ** 2 / ry ** 2
    if lam > 1: rx *= math.sqrt(lam); ry *= math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * yp ** 2 - ry ** 2 * xp ** 2; den = rx ** 2 * yp ** 2 + ry ** 2 * xp ** 2; co = math.sqrt(max(0.0, num / den)) * (1 if fa != fs else -1); cxp, cyp = co * rx * yp / ry, -co * ry * xp / rx
    cx, cy = c * cxp - s * cyp + 0.5 * (x0 + x1), s * cxp + c * cyp + 0.5 * (y0 + y1); t0 = math.atan2((yp - cyp) / ry, (xp - cxp) / rx); t1 = math.atan2((-yp - cyp) / ry, (-xp - cxp) / rx); dt = t1 - t0
    if fs and dt < 0: dt += 2 * math.pi
    if not fs and dt > 0: dt -= 2 * math.pi
    n = max(n_min, int(abs(dt) / (math.pi / 18)) + 1); P = []
    for i in range(1, n + 1):
        t = t0 + dt * i / n; ux, uy = rx * math.cos(t), ry * math.sin(t); P.append((c * ux - s * uy + cx, s * ux + c * uy + cy))
    return P

def _caminho(d):
    tk = re.findall(rf"[MmLlHhVvCcSsQqTtAaZz]|{_NUM}", d); i = 0; cmd = None; sub = []; atual = []; cur = (0.0, 0.0); ini = cur; ctrl = None; n = lambda: float(tk[i]) if False else None
    def bezier(p0, pts, m=16):
        out = []
        for k in range(1, m + 1):
            t = k / m
            if len(pts) == 3:
                a, b, c = pts; u = 1 - t; out.append((u ** 3 * p0[0] + 3 * u * u * t * a[0] + 3 * u * t * t * b[0] + t ** 3 * c[0], u ** 3 * p0[1] + 3 * u * u * t * a[1] + 3 * u * t * t * b[1] + t ** 3 * c[1]))
            else:
                a, c = pts; u = 1 - t; out.append((u * u * p0[0] + 2 * u * t * a[0] + t * t * c[0], u * u * p0[1] + 2 * u * t * a[1] + t * t * c[1]))
        return out
    while i < len(tk):
        if re.fullmatch(r"[A-Za-z]", tk[i]): cmd = tk[i]; i += 1
        if cmd in "Zz":
            if atual: sub.append((atual, True)); atual = []
            cur = ini; cmd = None; continue
        if cmd is None: break
        rel = cmd.islower(); C = cmd.upper(); ox, oy = (cur if rel else (0.0, 0.0))
        def pega(k):
            nonlocal i
            v = [float(tk[i + q]) for q in range(k)]; i += k; return v
        if C == "M":
            x, y = pega(2); p = (x + ox, y + oy)
            if atual: sub.append((atual, False))
            atual = [p]; cur = ini = p; cmd = "l" if rel else "L"; ctrl = None
        elif C == "L":
            x, y = pega(2); cur = (x + ox, y + oy); atual.append(cur); ctrl = None
        elif C == "H":
            x = pega(1)[0]; cur = (x + ox, cur[1]); atual.append(cur); ctrl = None
        elif C == "V":
            y = pega(1)[0]; cur = (cur[0], y + oy); atual.append(cur); ctrl = None
        elif C == "C":
            v = pega(6); pts = [(v[0] + ox, v[1] + oy), (v[2] + ox, v[3] + oy), (v[4] + ox, v[5] + oy)]; atual += bezier(cur, pts); cur = pts[2]; ctrl = pts[1]
        elif C == "S":
            v = pega(4); a = (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl else cur; pts = [a, (v[0] + ox, v[1] + oy), (v[2] + ox, v[3] + oy)]; atual += bezier(cur, pts); cur = pts[2]; ctrl = pts[1]
        elif C == "Q":
            v = pega(4); pts = [(v[0] + ox, v[1] + oy), (v[2] + ox, v[3] + oy)]; atual += bezier(cur, pts, 12); cur = pts[1]; ctrl = pts[0]
        elif C == "T":
            v = pega(2); a = (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl else cur; pts = [a, (v[0] + ox, v[1] + oy)]; atual += bezier(cur, pts, 12); cur = pts[1]; ctrl = a
        elif C == "A":
            v = pega(7); p1 = (v[5] + ox, v[6] + oy); atual += _arco(cur, v[0], v[1], v[2], int(v[3]), int(v[4]), p1); cur = p1; ctrl = None
        else:
            raise ValueError(f"comando SVG {cmd!r} desconhecido")
    if atual: sub.append((atual, False))
    return sub

def _elementos(no, m, out):
    tag = no.tag.rsplit("}", 1)[-1]; m2 = _mat_mul(m, _transform(no.get("transform")))
    if tag in ("defs", "clipPath", "mask", "symbol", "title", "metadata", "style"): return
    g = lambda k, d=0.0: float(re.match(_NUM, no.get(k, str(d)) or "0").group(0))
    pol = []
    if tag == "path" and no.get("d"): pol = _caminho(no.get("d"))
    elif tag == "circle" or tag == "ellipse":
        cx, cy = g("cx"), g("cy"); rx = g("r") if tag == "circle" else g("rx"); ry = rx if tag == "circle" else g("ry"); pol = [([(cx + rx * math.cos(t), cy + ry * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 72, endpoint=False)], True)]
    elif tag == "rect":
        x, y, w, h = g("x"), g("y"), g("width"), g("height"); pol = [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)]
    elif tag in ("polygon", "polyline"):
        v = [float(q) for q in re.findall(_NUM, no.get("points", ""))]; pol = [(list(zip(v[0::2], v[1::2])), tag == "polygon")]
    for pts, fechada in pol:
        P = np.array(pts, float)
        if len(P) >= 3: out.append((np.c_[m2[0] * P[:, 0] + m2[2] * P[:, 1] + m2[4], m2[1] * P[:, 0] + m2[3] * P[:, 1] + m2[5]], fechada))
    for f in no: _elementos(f, m2, out)

def _unidade(raiz):
    w = raiz.get("width") or ""; vb = raiz.get("viewBox"); q = re.fullmatch(rf"\s*({_NUM})\s*(mm|cm|in|pt|px|m)?\s*", w)
    if not q or not vb or not q.group(2) or q.group(2) == "px": return None
    v = {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "in": 0.0254, "pt": 0.0254 / 72}[q.group(2)]; lar = [float(x) for x in re.findall(_NUM, vb)][2]
    return float(q.group(1)) * v / lar

def _area(P): return 0.5 * float(P[:, 0] @ np.roll(P[:, 1], -1) - P[:, 1] @ np.roll(P[:, 0], -1))

def _ponto_dentro(p, Q):
    x, y = p; X, Z = Q[:, 0], Q[:, 1]; A, B = np.roll(np.arange(len(Q)), 1), np.arange(len(Q)); c = ((Z[B] > y) != (Z[A] > y)) & (x < (X[A] - X[B]) * (y - Z[B]) / (Z[A] - Z[B] + 1e-300) + X[B]); return int(c.sum()) % 2 == 1

def svg_placa(texto, escala=None, centraliza=True):
    if "<!ENTITY" in texto: raise ValueError("SVG com entidades XML: recusado")
    try: raiz = ET.fromstring(texto)
    except ET.ParseError as e: raise ValueError(f"SVG invalido: {e}")
    out = []; _elementos(raiz, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), out); avisos = []
    fech = [P[:-1] if np.allclose(P[0], P[-1]) else P for P, f in out if f or np.allclose(P[0], P[-1])]
    if len(fech) < len(out): avisos.append(f"{len(out) - len(fech)} curva(s) aberta(s) ignorada(s)")
    if not fech: raise ValueError("SVG sem curvas fechadas")
    esc = escala or _unidade(raiz) or 1e-3
    if not (escala or _unidade(raiz)): avisos.append("SVG sem unidade fisica: assumi 1 unidade = 1 mm")
    fech.sort(key=lambda P: -abs(_area(P))); ext = fech[0]; F = []
    for P in fech[1:]:
        if len(P) >= 3 and _ponto_dentro(P.mean(0), ext): F.append(P)
        else: avisos.append("curva fora do contorno principal ignorada")
    t = lambda P: np.c_[P[:, 0], -P[:, 1]] * esc
    C = t(ext); Hs = [t(P) for P in F]; ctr = 0.5 * (C.min(0) + C.max(0)) if centraliza else np.zeros(2)
    C = C - ctr; Hs = [H - ctr for H in Hs]; dz = np.ptp(C, axis=0)
    return {"contorno": np.round(C, 7).tolist(), "furos": [np.round(H, 7).tolist() for H in Hs], "largura": float(dz[0]), "altura": float(dz[1]), "avisos": avisos}

def _saneia(nome): return re.sub(r"[^A-Za-z0-9_]+", "_", nome.strip()).strip("_") or "sup"

_FOLGA_SECAO_AVL = 0.02

def _secoes_com_controles(elemento):
    secoes = sorted(elemento.get("secoes", []), key=lambda q: q["y"])
    pedidos = set()
    for controle in elemento.get("controles", []):
        for borda in controle["y"]:
            pedidos.update((borda, -borda))
    for y in sorted(pedidos):
        if not secoes[0]["y"] < y < secoes[-1]["y"] or any(abs(q["y"] - y) < _FOLGA_SECAO_AVL for q in secoes):
            continue
        direita = next(i for i, q in enumerate(secoes) if q["y"] > y)
        a, b = secoes[direita - 1], secoes[direita]
        t = (y - a["y"]) / (b["y"] - a["y"])
        nova = dict(a)
        nova["y"] = y
        for chave in ("xle", "zle", "corda", "ainc"):
            nova[chave] = (1 - t) * float(a.get(chave) or 0.0) + t * float(b.get(chave) or 0.0)
        secoes.insert(direita, nova)
    return secoes

def _apelidos_de_comando(asas):
    nomes = list(dict.fromkeys(c["nome"] for e in asas for c in e.get("controles", [])))
    return {nome: f"C{i + 1}" for i, nome in enumerate(nomes)}

def _linhas_de_controle(elemento, y, corda_local, apelidos, xle=0.0):
    linhas = []
    for controle in elemento.get("controles", []):
        y0, y1 = controle["y"]
        if not y0 - _FOLGA_SECAO_AVL <= abs(y) <= y1 + _FOLGA_SECAO_AVL:
            continue
        modo = controle.get("modo", "sim")
        if modo == "lado" and y < 0:
            continue
        ganho = -1.0 if modo == "anti" and y < 0 else 1.0
        xhinge = float(controle.get("xc", 0.75))
        if "x" in controle:
            xhinge = min(0.95, max(0.05, (float(controle["x"]) - xle) / corda_local))
        elif "corda" in controle:
            xhinge = max(0.05, 1.0 - float(controle["corda"]) / corda_local)
        linhas += ["CONTROL", f"{apelidos[controle['nome']]} {ganho:g} {xhinge:g} 0 0 0 1"]
    return linhas

def avl_exporta(esq, mach=0.0, n_corda=8, n_env=70) -> dict:
    els = [e for e in esq.get("elementos", []) if e.get("camada", "aero") == "aero"]; asas = [e for e in els if e.get("tipo", "asa") == "asa"]; omit = [e["nome"] for e in els if e.get("tipo", "asa") != "asa"]; avisos = []
    if not asas: raise ValueError("nenhuma superficie `asa` na camada aero: o AVL nao tem o que calcular")
    r = esq.get("referencia") or {}
    if "Sref" not in r:
        ss = []
        for e in asas:
            q = sorted(e["secoes"], key=lambda z: z["y"]); ss.append(sum(0.5 * (a_["corda"] + b_["corda"]) * (b_["y"] - a_["y"]) for a_, b_ in zip(q, q[1:])))
        i = max(range(len(ss)), key=ss.__getitem__); q = asas[i]["secoes"]; b = max(z["y"] for z in q) - min(z["y"] for z in q); r = {"Sref": ss[i], "Cref": ss[i] / b, "Bref": b}; avisos.append("referencia do esquema ausente: usada a maior asa")
    apelidos = _apelidos_de_comando(asas)
    L = [esq.get("nome", "aeronave"), f"{mach:g}", "0 0 0.0", f"{r['Sref']:.6g} {r['Cref']:.6g} {r['Bref']:.6g}", f"{r.get('Xref', 0.0):.6g} {r.get('Yref', 0.0):.6g} {r.get('Zref', 0.0):.6g}", ""]
    for e in asas:
        if e.get("guinada") or e.get("arfagem"): avisos.append(f"{e['nome']}: guinada ou arfagem do elemento nao foi exportada")
        vert = abs(float(e.get("rolagem", 0.0)) - 90.0) < 1e-9; ps = list(map(float, e.get("posicao", [0, 0, 0]))); L += ["SURFACE", _saneia(e["nome"]), f"{n_corda} 1.0 {n_env} 1.0", "COMPONENT", "1", "TRANSLATE", f"{ps[0]:.6g} {ps[1]:.6g} {ps[2]:.6g}", ""]
        for z in _secoes_com_controles(e):
            x, y, w = float(z.get("xle", 0.0)), float(z["y"]), float(z.get("zle", 0.0)); y, w = (w, -y) if vert else (y, w); L += ["SECTION", f"{x:.6g} {y:.6g} {w:.6g} {float(z['corda']):.6g} {float(z.get('ainc', 0.0)):.6g}"]
            nf = z.get("arquivo") or e.get("arquivo"); pf = str(z.get("perfil") or e.get("perfil") or "")
            if nf: L += ["AFILE", str(nf)]
            elif pf.upper().startswith("NACA"): L += ["NACA", pf.split()[-1]]
            L += _linhas_de_controle(e, float(z["y"]), float(z["corda"]), apelidos, float(z.get("xle", 0.0)))
            L.append("")
    L += [f"# comando {curto} = {nome}" for nome, curto in apelidos.items()]
    return dict(texto="\n".join(L) + "\n", omitidos=omit, avisos=avisos, superficies=[e["nome"] for e in asas])

def _comandos_de_deflexao(nomes, deflexoes):
    desconhecidos = set(deflexoes) - set(nomes)
    if desconhecidos:
        raise ValueError(f"comando sem correspondente no AVL: {sorted(desconhecidos)}")
    return "".join(f"D{i + 1} D{i + 1} {deflexoes.get(nome, 0.0):g}\n" for i, nome in enumerate(nomes))

def avl_roda(texto, alfas, exe, pasta, deflexoes=None) -> list:
    import subprocess
    from pathlib import Path
    pasta = Path(pasta); (pasta / "aviao.avl").write_text(texto, encoding="ascii", errors="replace"); L = []
    nomes = re.findall(r"^# comando C\d+ = (\S+)$", texto, flags=re.M)
    for a in alfas:
        r = subprocess.run([str(exe)], input=f"LOAD aviao.avl\nOPER\n{_comandos_de_deflexao(nomes, deflexoes or {})}A A {a:g}\nX\n\nQUIT\n", capture_output=True, text=True, cwd=pasta, timeout=120); cl = re.search(r"CLtot\s*=\s*([-\d.Ee+]+)", r.stdout); cd = re.search(r"CDind\s*=\s*([-\d.Ee+]+)", r.stdout)
        if not cl or not cd: raise RuntimeError(f"AVL sem resultado em alfa {a:g}; fim da saida: {r.stdout[-300:]}")
        momentos = {nome: re.search(rf"{chave}\s*=\s*([-\d.Ee+]+)", r.stdout) for nome, chave in (("Cl", "Cltot"), ("Cm", "Cmtot"), ("Cn", "Cntot"))}
        L.append(dict(alfa=float(a), CL=float(cl[1]), CD_ind=float(cd[1]), **{k: float(v[1]) for k, v in momentos.items() if v}))
    return L

def avl_esquema(texto, nome="aeronave"):
    ln = []
    for l in texto.splitlines():
        t = re.split(r"[#!]", l)[0].strip()
        if t: ln.append(t)
    if len(ln) < 5: raise ValueError("arquivo AVL curto demais")
    titulo = ln[0]; i = 1; v = lambda s: [float(q) for q in s.split()]
    while not re.fullmatch(rf"\s*{_NUM}.*", ln[i]): i += 1
    i += 2
    S = v(ln[i]); i += 1; ref = v(ln[i]); i += 1; Ref = {"Sref": S[0], "Cref": S[1], "Bref": S[2], "Xref": ref[0], "Yref": ref[1], "Zref": ref[2]}
    sup = []; s = None; sec = None; chave = lambda t: t.split()[0][:4].upper(); avisos = []; KEYS = ("SURF", "SECT", "YDUP", "TRAN", "ANGL", "COMP", "INDE", "SCAL", "AFIL", "NACA", "AIRF", "CONT", "CLAF", "CDCL", "NOWA", "NOAL", "NOLO", "BODY", "BFIL", "DESI")
    while i < len(ln):
        t = ln[i]; k = chave(t); i += 1
        if k not in KEYS: continue
        if k == "SURF":
            s = {"nome": _saneia(ln[i]), "sec": [], "dup": None, "tran": [0, 0, 0], "ang": 0.0, "esc": [1, 1, 1]}; i += 2; sup.append(s); sec = None
        elif k == "BODY": s = None; sec = None; i += 2; avisos.append("BODY do AVL ignorado")
        elif k == "YDUP" and s is not None: s["dup"] = v(ln[i])[0]; i += 1
        elif k == "TRAN" and s is not None: s["tran"] = v(ln[i])[:3]; i += 1
        elif k == "ANGL" and s is not None: s["ang"] = v(ln[i])[0]; i += 1
        elif k == "SCAL" and s is not None: s["esc"] = v(ln[i])[:3]; i += 1
        elif k in ("COMP", "INDE", "CLAF", "BFIL", "DESI"): i += 1
        elif k == "SECT" and s is not None:
            d = v(ln[i]); i += 1; sec = {"x": d[0], "y": d[1], "z": d[2], "c": d[3], "ai": d[4] if len(d) > 4 else 0.0, "perfil": None, "ctrl": []}; s["sec"].append(sec)
        elif k == "AFIL" and sec is not None:
            r = t.split(None, 1); sec["perfil"] = {"arquivo": r[1].strip() if len(r) > 1 else ln[i].strip()}; i += 0 if len(r) > 1 else 1
        elif k == "AIRF":
            avisos.append("AIRFOIL embutido no AVL ignorado (use AFILE)")
            while i < len(ln) and re.fullmatch(rf"\s*{_NUM}\s+{_NUM}\s*", ln[i]): i += 1
        elif k == "NACA" and sec is not None:
            r = t.split(); sec["perfil"] = {"perfil": "NACA " + (r[1] if len(r) > 1 else ln[i].split()[0])}; i += 0 if len(r) > 1 else 1
        elif k == "CONT" and sec is not None:
            d = ln[i].split(); i += 1; sec["ctrl"].append((d[0], float(d[2])))
        elif k == "CDCL": i += 1
    if not sup: raise ValueError("arquivo AVL sem SURFACE")
    els = []; marcas = []
    for q in sup:
        if len(q["sec"]) < 2: avisos.append(f"{q['nome']}: menos de 2 secoes, ignorada"); continue
        ex, ey, ez = q["esc"]; P = [(a["x"] * ex, a["y"] * ey, a["z"] * ez, a["c"] * ex, a["ai"] + q["ang"], a["perfil"] or {}) for a in q["sec"]]
        ptp_y = max(p[1] for p in P) - min(p[1] for p in P); ptp_z = max(p[2] for p in P) - min(p[2] for p in P); el = {"nome": q["nome"], "tipo": "asa", "n_perfil": 40}; tr = list(map(float, q["tran"]))
        if ptp_y < 1e-9 and ptp_z > 1e-9:
            y0 = P[0][1]; tr[1] += y0; P = [(p[0], p[2], 0.0, p[3], p[4], p[5]) for p in P]; el["rolagem"] = 90.0; dup = None
        else: dup = q["dup"]
        if dup is not None:
            M = [(p[0], 2 * dup - p[1], p[2], p[3], p[4], p[5]) for p in P if abs(p[1] - dup) > 1e-9]; P = sorted(P + M, key=lambda p: p[1])
        else: P = sorted(P, key=lambda p: p[1])
        el["secoes"] = [{"y": p[1], "xle": p[0], "zle": p[2], "corda": p[3], "ainc": p[4], **p[5]} for p in P]
        if any(tr): el["posicao"] = tr
        els.append(el); ctr = {}
        for a in q["sec"]:
            for n_, xh in a["ctrl"]: ctr.setdefault(n_, []).append(a["y"])
        for n_, ys in ctr.items():
            if len(ys) < 2 and q["dup"] is None: continue
            y0, y1 = min(ys), max(ys)
            if "rolagem" in el: continue
            m_ = {"nome": f"{q['nome']}_{_saneia(n_)}", "feicao": f"{q['nome']}.bordo_fuga", "y": [y0 + tr[1], y1 + tr[1]]}
            if y1 > y0: marcas.append(m_)
    return {"versao": 1, "nome": _saneia(nome), "unidade": "m", "referencia": Ref, "titulo": titulo, "elementos": els, "marcas": marcas, "_avisos": avisos}

def pdf_tracos(caminho, pagina=0, cores=None):
    import fitz
    pg = fitz.open(str(caminho))[pagina]; R = pg.rotation_matrix; A = []
    for d in pg.get_drawings():
        c = d.get("color")
        if c is None: continue
        nome = (cores or {}).get(tuple(round(x, 2) for x in c))
        if not nome: continue
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1] * R, it[2] * R; A.append((a.x, a.y, b.x, b.y, nome))
    return A

def recorta(tracos, caixa):
    x0, y0, x1, y1 = caixa; return [a for a in tracos if x0 <= min(a[0], a[2]) and max(a[0], a[2]) <= x1 and y0 <= min(a[1], a[3]) and max(a[1], a[3]) <= y1]

def barras_2d(S, mm_por_pt, tol_no=7.0, tol_col=4.0, L_min=3.0):
    seg = []
    for a in S:
        p = np.array([a[0], -a[1]], float) * mm_por_pt; q = np.array([a[2], -a[3]], float) * mm_por_pt
        if np.linalg.norm(q - p) >= L_min: seg.append((p, q, a[4]))
    mud = True
    while mud:
        mud = False
        for i in range(len(seg)):
            for j in range(i + 1, len(seg)):
                p, q, c = seg[i]; r, s, c2 = seg[j]; L = np.linalg.norm(q - p); u = (q - p) / L; n = np.array([-u[1], u[0]])
                if c != c2 or abs((r - p) @ n) > 1.2 or abs((s - p) @ n) > 1.2: continue
                t = sorted([(0.0, 0), (L, 1), ((r - p) @ u, 2), ((s - p) @ u, 3)]); b0, b1 = sorted([(r - p) @ u, (s - p) @ u])
                if b0 > L + tol_no or 0.0 > b1 + tol_no: continue
                pts = (p, q, r, s); seg[i] = (pts[t[0][1]], pts[t[-1][1]], c); seg.pop(j); mud = True; break
            if mud: break
    P = np.array([p for s in seg for p in s[:2]]); rot = -np.ones(len(P), int); C = []
    for i in range(len(P)):
        if rot[i] >= 0: continue
        g = np.flatnonzero((np.linalg.norm(P - P[i], axis=1) < tol_no) & (rot < 0)); rot[g] = len(C); C.append(P[g].mean(0))
    C = np.array(C); B = {}
    for k, s in enumerate(seg):
        i, j = rot[2 * k], rot[2 * k + 1]
        if i == j: continue
        pi, pj = C[i], C[j]; L = np.linalg.norm(pj - pi); u = (pj - pi) / L; n = np.array([-u[1], u[0]]); meio = []
        for q in range(len(C)):
            if q in (i, j): continue
            t = (C[q] - pi) @ u
            if tol_no < t < L - tol_no and abs((C[q] - pi) @ n) < tol_col: meio.append((t, q))
        cad = [i] + [q for _, q in sorted(meio)] + [j]
        for a, b in zip(cad, cad[1:]):
            ch = (min(a, b), max(a, b)); B[ch] = max(B.get(ch, ""), s[2])
    return C, [(a, b, c) for (a, b), c in sorted(B.items())]

class Trelica:

    def __init__(self, tol=7.0): self.tol = tol; self.N = []; self.B = {}

    def no(self, p):
        p = np.asarray(p, float)
        if self.N:
            d = np.linalg.norm(np.array(self.N) - p, axis=1); i = int(np.argmin(d))
            if d[i] < self.tol: return i
        self.N.append(p); return len(self.N) - 1

    def barra(self, p, q, tipo):
        i, j = self.no(p), self.no(q)
        if i != j: ch = (min(i, j), max(i, j)); self.B[ch] = max(self.B.get(ch, ""), tipo)

    def esquema(self, mm=True):
        f = 1e-3 if mm else 1.0
        return np.round(np.array(self.N) * f, 6).tolist(), [[a, b, c] for (a, b), c in sorted(self.B.items())]
