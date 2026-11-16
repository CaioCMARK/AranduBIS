from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import numpy as np

from . import aeronave_estrutura as ES
from . import aeronave_geometria as AG

def _slug(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(t)).strip("_") or "perfil"

def _asas(esq: dict, nomes=None) -> list[dict]:
    els = [e for e in esq.get("elementos", []) if e.get("tipo", "asa") == "asa" and e.get("secoes")]
    return [e for e in els if not nomes or e["nome"] in nomes]

def _perfis(el: dict, esq: dict, n: int):
    el = {**el, "n_perfil": n}
    sec = AG._secoes(el)
    if AG._quer_aneis(el) and el.get("secoes"):
        x, Z = AG._perfis_secoes(el, esq)
    else:
        x, zs, zi = ES.perfil_xy(el.get("perfil", "NACA 0012"), n, esq.get("_pasta", "."))
        Z = [(zs, zi)] * len(sec)
    return sec, x, Z

def _nome_perfil(el: dict, i: int) -> str:
    s = (el.get("secoes") or [{}] * (i + 1))[i] if i < len(el.get("secoes") or []) else {}
    return str(s.get("arquivo") or s.get("perfil") or el.get("arquivo") or el.get("perfil") or "NACA 0012")

def _no(sec, x, Z, y):
    q = AG._secao_em(sec, float(y)); i, t = AG._no_vao(sec, float(y))
    zs, zi = (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]
    return q, zs, zi

def selig(nome: str, x, zs, zi) -> str:
    L = [nome]
    L += [f"{a:.6f} {b:.6f}" for a, b in zip(x[::-1], zs[::-1])]
    L += [f"{a:.6f} {b:.6f}" for a, b in zip(x[1:], zi[1:])]
    return "\n".join(L) + "\n"

def contorno(x, zs, zi) -> np.ndarray:
    return np.vstack([np.column_stack([x[::-1], zs[::-1]]), np.column_stack([x[1:], zi[1:]])])

def nervuras_y(el: dict, sec) -> list[float]:
    ys = [q[1] for q in sec]
    cfg = (el.get("estrutura") or {}).get("nervuras") or {}
    if cfg.get("y"):
        v = AG._nervuras_y(cfg["y"], ys)
    else:
        v = sorted({round(q, 9) for q in ys})
    return [y for y in v if y >= -1e-9] if min(ys) < -1e-9 else v

def nervuras(el: dict, esq: dict, n: int = 120) -> list[dict]:
    from ..estrutura import longarinas as LG
    sec, x, Z = _perfis(el, esq, n)
    cfg = el.get("estrutura") or {}
    out = []
    for k, y in enumerate(nervuras_y(el, sec)):
        q, zs, zi = _no(sec, x, Z, y)
        c = float(q[3])
        rec = LG.recortes(cfg, x, zs, zi, c, abs(y)) if cfg else []
        out.append({"nome": f"{el['nome']}_N{k + 1:02d}", "y": float(y), "corda": c, "ainc": float(q[4]),
                    "contorno": contorno(x, zs, zi) * c, "recortes": rec,
                    "altura_max": float((zs - zi).max() * c), "zs": zs * c, "zi": zi * c, "x": x * c})
    return out


class _Dxf:
    def __init__(self):
        self.L = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]

    def poli(self, P, camada="CORTE", fechada=True):
        self.L += ["0", "POLYLINE", "8", camada, "66", "1", "70", "1" if fechada else "0"]
        for a, b in P:
            self.L += ["0", "VERTEX", "8", camada, "10", f"{a:.4f}", "20", f"{b:.4f}"]
        self.L += ["0", "SEQEND", "8", camada]

    def circulo(self, cx, cz, r, camada="CORTE"):
        self.L += ["0", "CIRCLE", "8", camada, "10", f"{cx:.4f}", "20", f"{cz:.4f}", "40", f"{r:.4f}"]

    def texto(self, cx, cz, h, t, camada="TEXTO"):
        self.L += ["0", "TEXT", "8", camada, "10", f"{cx:.4f}", "20", f"{cz:.4f}", "40", f"{h:.4f}", "1", t]

    def linha(self, a, b, camada="REFERENCIA"):
        self.L += ["0", "LINE", "8", camada, "10", f"{a[0]:.4f}", "20", f"{a[1]:.4f}", "11", f"{b[0]:.4f}", "21", f"{b[1]:.4f}"]

    def texto_final(self) -> str:
        return "\n".join(self.L + ["0", "ENDSEC", "0", "EOF"]) + "\n"

def dxf_nervuras(ns: list[dict], folga_mm: float = 15.0) -> str:
    d = _Dxf(); oz = 0.0
    for nv in ns:
        P = nv["contorno"] * 1000.0
        zmax, zmin = float(P[:, 1].max()), float(P[:, 1].min())
        oz -= zmax
        d.poli([(a, b + oz) for a, b in P])
        d.linha((0.0, oz), (nv["corda"] * 1000.0, oz))
        x, zs, zi = nv["x"], nv["zs"], nv["zi"]
        for r in nv["recortes"]:
            if r["forma"] == "furo":
                d.circulo(1000 * r["x"], 1000 * r["z"] + oz, 500 * r["d"])
            else:
                x0, x1 = r["x0"], r["x1"]
                topo = max(np.interp(x0, x, zs), np.interp(x1, x, zs)) + 0.001
                base = min(np.interp(x0, x, zi), np.interp(x1, x, zi)) - 0.001
                d.poli([(1000 * x0, 1000 * base + oz), (1000 * x1, 1000 * base + oz), (1000 * x1, 1000 * topo + oz), (1000 * x0, 1000 * topo + oz)])
        h = max(2.5, min(5.0, 0.04 * nv["corda"] * 1000.0))
        d.texto(0.35 * nv["corda"] * 1000.0, oz - 0.5 * h, h, f"{nv['nome']}  y={1000 * nv['y']:.1f} mm  c={1000 * nv['corda']:.1f} mm")
        oz += zmin - folga_mm
    return d.texto_final()

def csv_nervuras(ns: list[dict]) -> str:
    L = ["nervura;y_mm;corda_mm;incidencia_graus;ponto;x_mm;z_mm"]
    for nv in ns:
        for k, (a, b) in enumerate(nv["contorno"] * 1000.0):
            L.append(f"{nv['nome']};{1000 * nv['y']:.2f};{1000 * nv['corda']:.2f};{nv['ainc']:.3f};{k};{a:.3f};{b:.3f}")
    L.append("")
    L.append("nervura;recorte;x_mm;z_mm;diametro_mm;x0_mm;x1_mm")
    for nv in ns:
        for r in nv["recortes"]:
            if r["forma"] == "furo":
                L.append(f"{nv['nome']};furo;{1000 * r['x']:.3f};{1000 * r['z']:.3f};{1000 * r['d']:.3f};;")
            else:
                L.append(f"{nv['nome']};{r['forma']};;;;{1000 * r['x0']:.3f};{1000 * r['x1']:.3f}")
    return "\n".join(L) + "\n"

def _original(pasta: Path, pf: str, raizes) -> Path | None:
    if not pf.lower().endswith(".dat"):
        return None
    try:
        p = (pasta / pf).resolve()
    except OSError:
        return None
    if not p.is_file() or pasta.resolve() not in p.parents:
        return None
    if raizes is not None and not any(Path(r).resolve() in p.parents for r in raizes):
        return None
    return p

def stl_da_camada(esq: dict, camada: str, escala: float = 1000.0):
    A = AG.constroi(esq)
    if camada not in A.camadas:
        return "", 0, 0
    A = A.so_camada(camada)
    V = A.V * escala
    T = A.T
    p0, p1, p2 = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    nn = np.linalg.norm(n, axis=1)
    ok = nn > 1e-12
    n[ok] /= nn[ok, None]
    ids = np.flatnonzero(ok)
    reg = np.zeros(len(ids), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    reg["n"] = n[ids]
    reg["v"] = np.stack([p0[ids], p1[ids], p2[ids]], axis=1)
    cab = f"{esq.get('nome', 'aeronave')} {camada} mm".encode("ascii", "replace")[:80].ljust(80, b" ")
    dados = cab + np.uint32(len(ids)).tobytes() + reg.tobytes()
    arestas = {}
    for a, b, c in T[ok]:
        for u, v in ((a, b), (b, c), (c, a)):
            k = (min(u, v), max(u, v)); arestas[k] = arestas.get(k, 0) + 1
    abertas = sum(1 for c in arestas.values() if c == 1)
    return dados, int(ok.sum()), abertas

def exporta(esq: dict, formatos=("dat", "dxf", "csv"), asas=None, n_perfil: int = 120, raizes=None) -> dict:
    arqs, avisos, vistos = [], [], set()
    pasta = Path(esq.get("_pasta", "."))
    els = _asas(esq, asas)
    so_stl = set(formatos) <= {"stl_fechado", "stl_esqueleto", "montagem"}
    if not els and not so_stl:
        raise ValueError("nenhuma superficie do tipo asa com secoes no modelo")
    for el in els:
        nome = _slug(el["nome"])
        sec, x, Z = _perfis(el, esq, n_perfil)
        if "dat" in formatos:
            for i, q in enumerate(sec):
                i_z = min(i, len(Z) - 1)
                pf = _nome_perfil(el, i) if el.get("secoes") else str(el.get("perfil", "NACA 0012"))
                arqs.append({"nome": f"perfis/{nome}_secao{i + 1:02d}_y{1000 * q[1]:+.0f}mm.dat",
                             "texto": selig(f"{pf} ({el['nome']}, y = {q[1]:.4f} m, corda {q[3]:.4f} m)", x, *Z[i_z])})
            for i in range(len(sec)):
                pf = _nome_perfil(el, i)
                orig = _original(pasta, pf, raizes)
                if orig and pf not in vistos:
                    vistos.add(pf)
                    arqs.append({"nome": f"perfis/originais/{Path(pf).name}", "texto": orig.read_text(encoding="utf8", errors="replace")})
        if ("dxf" in formatos or "csv" in formatos) and el.get("estrutura"):
            ns = nervuras(el, esq, n_perfil)
            if not (el.get("estrutura") or {}).get("nervuras"):
                avisos.append(f"{el['nome']}: sem nervuras declaradas; saiu uma por secao do modelo")
            if not (el.get("estrutura") or {}).get("longarinas"):
                avisos.append(f"{el['nome']}: sem longarina declarada; nervuras sem recortes")
            if "dxf" in formatos:
                arqs.append({"nome": f"nervuras/{nome}_nervuras.dxf", "texto": dxf_nervuras(ns)})
            if "csv" in formatos:
                arqs.append({"nome": f"nervuras/{nome}_nervuras.csv", "texto": csv_nervuras(ns)})
    if "avl" in formatos:
        from .aeronave_importa import avl_exporta
        r = avl_exporta(esq)
        arqs.append({"nome": f"avl/{_slug(esq.get('nome', 'aeronave'))}.avl", "texto": r["texto"]})
        for el in _asas(esq):
            for i in range(len(el.get("secoes") or [])):
                pf = _nome_perfil(el, i)
                orig = _original(pasta, pf, raizes)
                nm = f"avl/{Path(pf).as_posix()}"
                if orig and nm not in {a["nome"] for a in arqs}:
                    arqs.append({"nome": nm, "texto": orig.read_text(encoding="utf8", errors="replace")})
                elif pf.lower().endswith(".dat") and not orig and f"avl:{pf}" not in vistos:
                    vistos.add(f"avl:{pf}")
                    avisos.append(f"{pf}: arquivo de perfil nao copiado para o pacote do AVL; coloque-o ao lado do .avl")
        avisos += r["avisos"]
        if r["omitidos"]:
            avisos.append("o AVL so recebe superficies: ficaram de fora " + ", ".join(r["omitidos"]))
    if "montagem" in formatos:
        from .folha_montagem import folhas
        pdf, av = folhas(esq, asas)
        arqs.append({"nome": f"montagem/{_slug(esq.get('nome', 'aeronave'))}_folha_de_montagem.pdf", "base64": base64.b64encode(pdf).decode("ascii")})
        avisos += av
    for fmt, camada, sufixo in (("stl_fechado", "aero", "fechado"), ("stl_esqueleto", "estrutura", "esqueleto")):
        if fmt in formatos:
            texto, n_tri, abertas = stl_da_camada(esq, camada)
            if n_tri == 0:
                avisos.append(f"STL {sufixo}: sem triangulos" + (" (declare estrutura nas asas ou treliças)" if camada == "estrutura" else ""))
                continue
            arqs.append({"nome": f"stl/{_slug(esq.get('nome', 'aeronave'))}_{sufixo}.stl", "base64": base64.b64encode(texto).decode("ascii")})
            if abertas:
                avisos.append(f"STL {sufixo}: {abertas} aresta(s) de borda aberta; confira a malha antes de imprimir")
    if ("dxf" in formatos or "csv" in formatos) and not any(el.get("estrutura") for el in els):
        avisos.append("nenhuma asa com estrutura declarada: nao saiu nervura (declare-as na aba Estrutura da asa)")
    return {"arquivos": arqs, "avisos": avisos}
