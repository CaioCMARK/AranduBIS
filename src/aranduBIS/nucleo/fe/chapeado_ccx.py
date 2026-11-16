from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from ..estrutura.asa import _elemento, _fim_do_chapeado, _perfis
from ..estrutura.materiais import propriedades
from ..modelador import aeronave_estrutura as ES
from ..modelador import aeronave_geometria as AG


class SemCalculix(RuntimeError):
    pass


def executavel() -> str:
    c = os.environ.get("ARANDUBIS_CCX") or shutil.which("ccx") or shutil.which("ccx_2.21") or shutil.which("ccx.exe")
    if not c:
        raise SemCalculix("CalculiX (ccx) nao encontrado: instale-o (Linux: apt install calculix-ccx; Windows: bConverged ou o "
                          "binario de calculix.de) ou aponte ARANDUBIS_CCX para o executavel")
    return c


def _secao(sec_el, x, Z, y):
    q = AG._secao_em(sec_el, float(y)); i, t = AG._no_vao(sec_el, float(y))
    return q, (1 - t) * Z[i][0] + t * Z[i + 1][0], (1 - t) * Z[i][1] + t * Z[i + 1][1]


def _contorno(x, zs, zi, xe, ns_pele, ns_alma):
    m = x <= xe
    xu = np.append(x[m], xe)[::-1]; zu = np.append(zs[m], np.interp(xe, x, zs))[::-1]
    xl = np.append(x[m], xe)[1:]; zl = np.append(zi[m], np.interp(xe, x, zi))[1:]
    P = np.vstack([np.column_stack([xu, zu]), np.column_stack([xl, zl])])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    sp = np.linspace(0, s[-1], 2 * ns_pele + 1)
    pele = np.column_stack([np.interp(sp, s, P[:, 0]), np.interp(sp, s, P[:, 1])])
    za, zb = np.interp(xe, x, zi), np.interp(xe, x, zs)
    alma = np.column_stack([np.full(2 * ns_alma - 1, xe), np.linspace(za, zb, 2 * ns_alma + 1)[1:-1]])
    pts = np.vstack([pele, alma])
    tipos = ["pele"] * ns_pele + ["alma"] * ns_alma
    return pts, tipos, ns_pele


def monta(esq: dict, nome: str, y0: float, y1: float, sigma_ref: float, dp: float = 0.0, ns_pele: int | None = None, ns_alma: int | None = None,
          ny: int | None = None, mats: dict | None = None, qualidade_balsa: float = 1.0, imperfeicao=None,
          z_LN: float | None = None, E_transv: float | None = None) -> dict:
    el = _elemento(esq, nome)
    cfg = el.get("estrutura") or {}
    ch = cfg.get("chapeado") or {}
    if not ch:
        raise ValueError(f"{nome}: sem chapeado declarado")
    lgs = cfg.get("longarinas") or []
    tw = float(lgs[0].get("largura", lgs[0].get("espessura_alma", 0.00238))) if lgs else 0.00238
    ts = float(ch.get("espessura", 0.001))
    mb = propriedades("balsa", esq, mats, qualidade_balsa)
    E1, G = mb["E"], mb["G"]; E2 = float(E_transv) if E_transv else 0.015 * E1; nu = mb["nu"]
    sec_el, x, Z = _perfis(el, esq)
    ym = 0.5 * (y0 + y1)
    xe = _fim_do_chapeado(ch, ym)
    L = abs(y1 - y0)
    if ns_pele is None or ns_alma is None:
        from .. import discretizacao as DS
        ns_pele = DS.chapeado_ns_pele(_arco(x, Z, sec_el, ym, xe)) if ns_pele is None else ns_pele
        ns_alma = DS.chapeado_ns_alma() if ns_alma is None else ns_alma
    ny = ny or max(4, int(round(ns_pele * L / max(1e-6, _arco(x, Z, sec_el, ym, xe)))))
    an = []
    for yy in (y0, y1):
        q, zs, zi = _secao(sec_el, x, Z, yy)
        pts, tipos, _ = _contorno(x, zs, zi, xe, ns_pele, ns_alma)
        c = float(q[3]); an.append(np.column_stack([q[0] + pts[:, 0] * c, pts[:, 1] * c]))
    n_s = len(an[0])
    nos, mapa = [], {}
    for j in range(2 * ny + 1):
        eta = j / (2 * ny); yy = y0 + eta * (y1 - y0)
        C = (1 - eta) * an[0] + eta * an[1]
        for i in range(n_s):
            if j % 2 == 1 and i % 2 == 1:
                continue
            mapa[i, j] = len(nos) + 1
            nos.append((C[i, 0], yy, C[i, 1]))
    nos = np.array(nos)
    if imperfeicao is not None:
        nos = nos + imperfeicao
    el_pele, el_alma, conect, sup = [], [], [], {}
    ne = len(tipos)
    k_ba = int(np.argmin(an[0][0:2 * ns_pele + 1:2, 0]))
    centro = np.array([nos[:, 0].mean(), nos[:, 2].mean()])
    for k in range(ne):
        I = 2 * k
        I2 = (I + 2) % n_s
        for j in range(ny):
            J = 2 * j
            c8 = [mapa[I, J], mapa[I, J + 2], mapa[I2, J + 2], mapa[I2, J], mapa[I, J + 1], mapa[(I + 1) % n_s, J + 2], mapa[I2, J + 1], mapa[(I + 1) % n_s, J]]
            conect.append(c8)
            eid = len(conect)
            (el_pele if tipos[k] == "pele" else el_alma).append(eid)
            if tipos[k] == "pele" and k < k_ba:
                p1, p2, p4 = nos[c8[0] - 1], nos[c8[1] - 1], nos[c8[3] - 1]
                nrm = np.cross(p2 - p1, p4 - p1)
                fora = np.array([p1[0] - centro[0], 0.0, p1[2] - centro[1]])
                sup[eid] = -1.0 if nrm @ fora > 0 else 1.0
    zt = float(nos[:, 2].max())
    zln = float(z_LN) if z_LN is not None else 0.5 * (nos[:, 2].max() + nos[:, 2].min())
    return {"nos": nos, "conect": conect, "pele": el_pele, "alma": el_alma, "sup": sup, "mapa": mapa, "ny": ny, "n_s": n_s, "n_pele": 2 * ns_pele,
            "ts": ts, "tw": tw, "E1": E1, "E2": E2, "G": G, "nu": nu, "XC": mb["XC"], "y0": y0, "y1": y1, "xe": xe, "zt": zt, "zln": zln,
            "sigma_ref": sigma_ref, "dp": dp, "L": L}


def _arco(x, Z, sec_el, y, xe):
    q, zs, zi = _secao(sec_el, x, Z, y)
    m = x <= xe
    return 2.0 * float(np.hypot(np.diff(x[m]), np.diff(zs[m])).sum()) * q[3]


def _texto(M: dict, passo: str, fator_carga: float = 1.0, com_pressao: bool = True, com_compressao: bool = True) -> str:
    nos, conect = M["nos"], M["conect"]
    L = ["*NODE"] + [f"{k + 1}, {a:.7e}, {b:.7e}, {c:.7e}" for k, (a, b, c) in enumerate(nos)]
    L += ["*ELEMENT, TYPE=S8R, ELSET=PELE"] + [f"{e}, " + ", ".join(map(str, conect[e - 1])) for e in M["pele"]]
    if M["alma"]:
        L += ["*ELEMENT, TYPE=S8R, ELSET=ALMA"] + [f"{e}, " + ", ".join(map(str, conect[e - 1])) for e in M["alma"]]
    E1, E2, G, nu = M["E1"], M["E2"], M["G"], M["nu"]
    L += ["*ORIENTATION, NAME=FIBRA, SYSTEM=RECTANGULAR", "0., 1., 0., 1., 0., 0.",
          "*MATERIAL, NAME=BALSA", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
          f"{E1:.6e}, {E2:.6e}, {E2:.6e}, {nu}, {nu}, 0.3, {G:.6e}, {G:.6e},", f"{0.1 * G:.6e}",
          "*SHELL SECTION, ELSET=PELE, MATERIAL=BALSA, ORIENTATION=FIBRA", f"{M['ts']}"]
    if M["alma"]:
        L += ["*SHELL SECTION, ELSET=ALMA, MATERIAL=BALSA, ORIENTATION=FIBRA", f"{M['tw']}"]
    ny = M["ny"]
    rib0 = [n for (i, j), n in M["mapa"].items() if j == 0]
    rib1 = [n for (i, j), n in M["mapa"].items() if j == 2 * ny]
    L += ["*NSET, NSET=NERV0"] + _linhas(rib0) + ["*NSET, NSET=NERV1"] + _linhas(rib1)
    L += ["*BOUNDARY", "NERV0, 1, 3", "NERV1, 1, 1", "NERV1, 3, 3"]
    F = {}
    if com_compressao and M["sigma_ref"] > 0:
        pele = set(M["pele"])
        for e, c8 in enumerate(conect, start=1):
            if (e - 1) % M["ny"] != M["ny"] - 1:
                continue
            a, b, m = c8[1], c8[2], c8[5]
            t = M["ts"] if e in pele else M["tw"]
            pa, pb = M["nos"][a - 1], M["nos"][b - 1]
            Lk = float(np.hypot(pa[0] - pb[0], pa[2] - pb[2]))
            for no, w in ((a, 1 / 6), (m, 2 / 3), (b, 1 / 6)):
                z = M["nos"][no - 1, 2]
                s = M["sigma_ref"] * (z - M["zln"]) / max(M["zt"] - M["zln"], 1e-9)
                F[no] = F.get(no, 0.0) + fator_carga * (-s) * t * Lk * w
    L += ["*STEP" + (", NLGEOM, INC=200" if passo == "estatico" else "")]
    if passo == "flambagem":
        L += ["*BUCKLE", "4"]
    else:
        n_inc = int(M.get("_n_inc", 10))
        L += ["*STATIC", f"{1.0 / n_inc:.6f}, 1.0, 1e-4, {1.0 / n_inc:.6f}"]
    if F:
        L += ["*CLOAD"] + [f"{n}, 2, {v:.9e}" for n, v in F.items() if abs(v) > 0]
    if com_pressao and M["dp"] and M["sup"] and passo == "estatico":
        L += ["*DLOAD"] + [f"{e}, P, {sg * fator_carga * M['dp']:.6e}" for e, sg in M["sup"].items()]
    if M.get("_saida3d"):
        L += ["*NODE FILE", "U", "*EL FILE", "S", "*END STEP"]
    else:
        L += ["*NODE FILE, OUTPUT=2D" + (", FREQUENCY=1" if passo == "estatico" else ""), "U", "*END STEP"]
    return "\n".join(L) + "\n"


def _linhas(ids, por=12):
    ids = sorted(ids)
    return [", ".join(map(str, ids[k:k + por])) for k in range(0, len(ids), por)]


def _roda(texto: str, pasta: Path, nome: str = "baia") -> tuple[str, str]:
    (pasta / f"{nome}.inp").write_text(texto)
    r = subprocess.run([executavel(), "-i", nome], cwd=pasta, capture_output=True, text=True, timeout=600)
    dat = (pasta / f"{nome}.dat").read_text() if (pasta / f"{nome}.dat").is_file() else ""
    frd = (pasta / f"{nome}.frd").read_text() if (pasta / f"{nome}.frd").is_file() else ""
    if r.returncode != 0 and not frd:
        raise RuntimeError("CalculiX falhou: " + (r.stdout[-400:] + r.stderr[-400:]).strip())
    return dat, frd + "\n#STDOUT\n" + r.stdout


def _tempos(frd: str) -> list[float]:
    return [float(ln[12:24]) for ln in frd.splitlines() if ln.startswith("  100CL")]


def _blocos_U(frd: str, n_nos: int) -> list[np.ndarray]:
    out, cur = [], None
    for ln in frd.splitlines():
        if ln.startswith(" -4  DISP"):
            cur = np.zeros((n_nos, 3)); out.append(cur)
        elif ln.startswith(" -3"):
            cur = None
        elif cur is not None and ln.startswith(" -1"):
            nid = int(ln[3:13])
            if nid <= n_nos:
                cur[nid - 1] = [float(ln[13:25]), float(ln[25:37]), float(ln[37:49])]
    return out


def flambagem(M: dict, pasta: Path) -> dict:
    dat, frd = _roda(_texto(M, "flambagem"), pasta, "flamb")
    lam = [float(v) for v in re.findall(r"^\s+\d+\s+([0-9.E+-]+)\s*$", dat.split("B U C K L I N G")[-1], re.M)]
    if not lam:
        raise RuntimeError("CalculiX nao devolveu autovalores de flambagem")
    modos = _blocos_U(frd, len(M["nos"]))
    return {"lambda": lam, "sigma_cr": lam[0] * M["sigma_ref"], "modo": modos[0] if modos else None}


def estatico(M: dict, pasta: Path, fator: float = 1.0, n_inc: int = 10, pressao: bool = True, compressao: bool = True) -> dict:
    M = {**M, "_n_inc": n_inc}
    dat, frd = _roda(_texto(M, "estatico", fator, com_pressao=pressao, com_compressao=compressao), pasta, "est")
    U = _blocos_U(frd, len(M["nos"]))
    tt = _tempos(frd)[:len(U)]
    return {"ok": bool(tt) and tt[-1] >= 1.0 - 1e-6, "U": U, "fatores": [fator * t for t in tt]}

def _bloco(frd: str, cabeca: str, ncol: int, ultimo: bool = True) -> dict:
    L = frd.splitlines()
    inicios = [i for i, ln in enumerate(L) if ln.startswith(cabeca)]
    if not inicios:
        return {}
    out = {}
    for ln in L[(inicios[-1] if ultimo else inicios[0]) + 1:]:
        if ln.startswith(" -3"):
            break
        if ln.startswith(" -1"):
            out[int(ln[3:13])] = [float(ln[13 + 12 * k:25 + 12 * k]) for k in range(ncol)]
    return out


def tensoes_no_material(M: dict, pasta: Path, fator: float, mats_tsai: dict) -> dict:
    from scipy.spatial import cKDTree
    Mx = {**M, "_n_inc": 10, "_saida3d": True}
    dat, frd = _roda(_texto(Mx, "estatico", fator), pasta, "th")
    X = _bloco(frd, "    2C", 3, ultimo=False)
    S = _bloco(frd, " -4  STRESS", 6)
    if not X or not S:
        raise RuntimeError("CalculiX nao devolveu tensoes")
    ids = np.array(sorted(S)); P = np.array([X[i] for i in ids]); T = np.array([S[i] for i in ids])
    _, k = cKDTree(M["nos"]).query(P)
    inv = {n - 1: ij for ij, n in M["mapa"].items()}
    n_s = M["n_s"]

    def tangente(o):
        i, j = inv[o]
        passo = 1 if (i + 1) % n_s != 0 and ((i + 1) % n_s, j) in M["mapa"] and ((i - 1) % n_s, j) in M["mapa"] else 2
        a, b = M["mapa"].get(((i + passo) % n_s, j)), M["mapa"].get(((i - passo) % n_s, j))
        d = M["nos"][a - 1] - M["nos"][b - 1]; d[1] = 0.0
        return d / (np.linalg.norm(d) + 1e-15)
    tg = np.array([tangente(o) for o in range(len(M["nos"]))])
    pele = np.array([inv[o][0] <= M["n_pele"] for o in range(len(M["nos"]))])
    sel = pele[k]
    t = tg[k]
    sxx, syy, szz, sxy, syz, szx = T.T
    s11 = syy
    s22 = t[:, 0] ** 2 * sxx + t[:, 2] ** 2 * szz + 2 * t[:, 0] * t[:, 2] * szx
    s12 = t[:, 0] * sxy + t[:, 2] * syz
    m = mats_tsai
    X1 = np.where(s11 >= 0, m["X"], m["XC"]); Y2 = np.where(s22 >= 0, m["YT"], m["YC"])
    th = (s11 / X1) ** 2 - s11 * s22 / X1 ** 2 + (s22 / Y2) ** 2 + (s12 / m["S"]) ** 2
    th = np.where(sel, th, 0.0)
    j = int(np.argmax(th))
    termos = {"fibra": float((s11[j] / X1[j]) ** 2), "transversal": float((s22[j] / Y2[j]) ** 2), "cisalhamento": float((s12[j] / m["S"]) ** 2)}
    return {"tsai_hill_max": float(th[j]), "margem_tsai_hill": float(1.0 / np.sqrt(max(th[j], 1e-30)) - 1.0),
            "onde": P[j].tolist(), "s1_MPa": float(s11[j] / 1e6), "s2_MPa": float(s22[j] / 1e6), "s12_MPa": float(s12[j] / 1e6),
            "domina": max(termos, key=termos.get), "termos": termos,
            "s2_max_MPa": float(np.abs(s22[sel]).max() / 1e6), "s12_max_MPa": float(np.abs(s12[sel]).max() / 1e6),
            "convergiu": "Job finished" in frd}


def _w_normal(M: dict, U: np.ndarray) -> np.ndarray:
    nos = M["nos"]; cx = np.array([nos[:, 0].mean(), 0, nos[:, 2].mean()])
    d = nos - cx; d[:, 1] = 0.0
    n = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)
    return np.sum(U * n, axis=1)


def _interp_U(fat, Us, alvo):
    ks = int(np.searchsorted(fat, alvo))
    if ks >= len(fat):
        return None
    if ks == 0:
        return np.zeros_like(Us[0])
    a, b = ks - 1, ks
    t = (alvo - fat[a]) / max(fat[b] - fat[a], 1e-12)
    Ua = np.zeros_like(Us[0]) if a == 0 else Us[a - 1]
    return (1 - t) * Ua + t * Us[b - 1]


def _tsai_padrao(esq, mats, qualidade_balsa=1.0) -> dict:
    mb = propriedades("balsa", esq, mats, qualidade_balsa)
    return {k: mb[k] for k in ("X", "XC", "YT", "YC", "S")}


def analisa_baia(esq: dict, nome: str, y0: float, y1: float, sigma_ref: float, dp: float, imperf_t: float = 0.5,
                 fator_max: float | None = None, n_inc: int = 12, tsai: dict | None = None, **kw) -> dict:
    with tempfile.TemporaryDirectory(prefix="arandubis_ccx_") as tmp:
        pasta = Path(tmp)
        M = monta(esq, nome, y0, y1, sigma_ref, dp, **kw)
        fl = flambagem(M, pasta)
        lam1 = fl["lambda"][0]
        imp = None
        if fl["modo"] is not None and imperf_t > 0:
            mo = fl["modo"]
            imp = mo / max(np.abs(mo).max(), 1e-12) * imperf_t * M["ts"]
        Mi = monta(esq, nome, y0, y1, sigma_ref, dp, imperfeicao=imp, **kw)
        fmax = fator_max or max(1.5, 1.3 * lam1)
        rc = estatico(Mi, pasta, fmax, n_inc, pressao=False)
        rp = estatico(Mi, pasta, 1.0, n_inc) if dp else None
        th = None
        mt = tsai or _tsai_padrao(esq, kw.get("mats"), kw.get("qualidade_balsa", 1.0))
        try:
            fth = 1.0 if (rp is None or rp["ok"]) else max(0.05, (rp["fatores"] or [0.05])[-1])
            th = tensoes_no_material(Mi, pasta, fth, mt)
            th["fator"] = fth
        except RuntimeError as e:
            th = {"erro": str(e)}
    ts = M["ts"]
    fat = np.array([0.0] + rc["fatores"])
    wmax = np.array([0.0] + [float(np.abs(_w_normal(Mi, U)).max()) for U in rc["U"]])
    f_t = None
    if len(wmax) > 1 and (wmax >= ts).any():
        k = int(np.argmax(wmax >= ts))
        f_t = float(np.interp(ts, wmax[k - 1:k + 1], fat[k - 1:k + 1]))
    elif not rc["ok"] and len(fat) > 1:
        f_t = float(fat[-1])
    out = {"y0": y0, "y1": y1, "xe_c": M["xe"], "ts": ts, "sigma_ref_MPa": sigma_ref / 1e6, "dp_Pa": dp,
           "sigma_cr_linear_MPa": fl["sigma_cr"] / 1e6, "lambda": fl["lambda"], "imperfeicao_t": imperf_t,
           "curva": {"fator": fat.tolist(), "w_max_mm": (1000 * wmax).tolist()},
           "fator_flambagem": f_t, "sigma_flambagem_MPa": f_t * sigma_ref / 1e6 if f_t else None,
           "knockdown_medido": (f_t / lam1) if f_t and lam1 > 0 else None, "tsai_hill": th}
    if rp is not None:
        fp = np.array([0.0] + rp["fatores"])
        U1 = _interp_U(fp, rp["U"], 1.0) if rp["ok"] else (rp["U"][-1] if rp["U"] else None)
        out["abaulamento_convergiu"] = rp["ok"]
        out["abaulamento_ate_fator"] = float(fp[-1])
        if U1 is not None:
            w = _w_normal(Mi, U1)
            out["w_para_fora_mm"] = float(1000 * w.max()); out["w_para_dentro_mm"] = float(-1000 * w.min())
            mid = sorted(((i, n) for (i, j), n in M["mapa"].items() if j == M["ny"]))
            idx = [n - 1 for i, n in mid] + [mid[0][1] - 1]
            P0 = Mi["nos"][idx]; Pd = P0 + U1[idx]
            out["perfil_meio"] = {"x": P0[:, 0].tolist(), "z": P0[:, 2].tolist(), "x_def": Pd[:, 0].tolist(), "z_def": Pd[:, 2].tolist()}
    return out
