from __future__ import annotations

import numpy as np

from .modelo import Modelo

def _f(x):
    return repr(float(x))

def escreve(mod: Modelo, caminho=None, titulo="AranduBIS") -> str:
    L = [f"$ {titulo}", "SOL 101", "CEND", "SPC = 1"]
    for k, caso in enumerate(sorted(mod.cargas), 1):
        L += [f"SUBCASE {caso}", f"  LOAD = {caso}"]
    L.append("BEGIN BULK")
    for i, (x, y, z) in sorted(mod.nos.items()):
        L.append(f"GRID,{i},,{_f(x)},{_f(y)},{_f(z)}")
    for i, m in sorted(mod.materiais.items()):
        nu = m["E"] / (2 * m["G"]) - 1
        L.append(f"MAT1,{i},{_f(m['E'])},{_f(m['G'])},{_f(nu)},{_f(m['rho'])}")
    for i, p in sorted(mod.props.items()):
        L.append(f"PBAR,{i},{p['mat']},{_f(p['A'])},{_f(p['I1'])},{_f(p['I2'])},{_f(p['J'])},{_f(p['nsm'])}")
    for eid, pid, ga, gb, v in mod.barras:
        L.append(f"CBAR,{eid},{pid},{ga},{gb},{_f(v[0])},{_f(v[1])},{_f(v[2])}")
    for eid, no, m in mod.massas:
        L.append(f"CONM2,{eid},{no},,{_f(m)}")
    for eid, mestre, esc in mod.rigidos:
        L.append(f"RBE2,{eid},{mestre},123456," + ",".join(str(s) for s in esc))
    for no, graus in sorted(mod.spc.items()):
        L.append(f"SPC1,1,{''.join(str(g) for g in sorted(graus))},{no}")
    for caso, c in sorted(mod.cargas.items()):
        for no, F in sorted(c.items()):
            if np.any(F[:3]):
                n = np.linalg.norm(F[:3]); d = F[:3] / n
                L.append(f"FORCE,{caso},{no},,{_f(n)},{_f(d[0])},{_f(d[1])},{_f(d[2])}")
            if np.any(F[3:]):
                n = np.linalg.norm(F[3:]); d = F[3:] / n
                L.append(f"MOMENT,{caso},{no},,{_f(n)},{_f(d[0])},{_f(d[1])},{_f(d[2])}")
    L.append("ENDDATA")
    txt = "\n".join(L) + "\n"
    if caminho:
        open(caminho, "w", encoding="utf-8").write(txt)
    return txt

def le(txt: str) -> Modelo:
    m = Modelo()
    bulk = False
    for lin in txt.splitlines():
        lin = lin.split("$")[0].strip()
        if not lin:
            continue
        if lin.upper().startswith("BEGIN BULK"):
            bulk = True
            continue
        if not bulk or lin.upper() == "ENDDATA":
            continue
        c = [t.strip() for t in lin.split(",")]
        k = c[0].upper()
        if k == "GRID":
            m.no(c[1], c[3], c[4], c[5])
        elif k == "MAT1":
            m.material(c[1], c[2], c[3] or None, float(c[4] or 0.3), float(c[5] or 0.0))
        elif k == "PBAR":
            m.prop(c[1], c[2], c[3], c[4], c[5], c[6], float(c[7]) if len(c) > 7 and c[7] else 0.0)
        elif k == "CBAR":
            m.barra(c[1], c[2], c[3], c[4], (c[5], c[6], c[7]))
        elif k == "CONM2":
            m.massa(c[1], c[2], c[4])
        elif k == "RBE2":
            m.rigido(c[1], c[2], [int(s) for s in c[4:] if s])
        elif k == "SPC1":
            m.engasta([int(s) for s in c[3:] if s], [int(ch) for ch in c[2]])
        elif k in ("FORCE", "MOMENT"):
            n = float(c[4]) * np.array([float(c[5]), float(c[6]), float(c[7])])
            m.carga(c[1], c[2], np.concatenate([n, np.zeros(3)]) if k == "FORCE" else np.concatenate([np.zeros(3), n]))
        else:
            raise ValueError(f"cartao {k} fora do subconjunto suportado")
    return m
