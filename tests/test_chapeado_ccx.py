import re
import shutil
import subprocess

import numpy as np
import pytest

from aranduBIS.nucleo.estrutura.flambagem import sigma_cr_ortotropica

pytestmark = pytest.mark.skipif(not shutil.which("ccx"), reason="CalculiX (ccx) nao instalado")

def test_placa_ortotropica_bate_com_a_formula(tmp_path):
    E1, E2, G12, nu12, t = 3.4e9, 0.051e9, 0.1258e9, 0.488, 0.0015
    a, b, nx, ny = 0.10, 0.06, 20, 12
    X = np.linspace(0, a, 2 * nx + 1); Y = np.linspace(0, b, 2 * ny + 1)
    nid, nos = {}, []
    for j, y in enumerate(Y):
        for i, x in enumerate(X):
            if i % 2 and j % 2:
                continue
            nid[i, j] = len(nos) + 1; nos.append((x, y))
    L = ["*NODE"] + [f"{k + 1}, {x:.6f}, {y:.6f}, 0" for k, (x, y) in enumerate(nos)] + ["*ELEMENT, TYPE=S8R, ELSET=P"]
    e = 0
    for j in range(ny):
        for i in range(nx):
            I, J = 2 * i, 2 * j; e += 1
            c = [nid[I, J], nid[I + 2, J], nid[I + 2, J + 2], nid[I, J + 2], nid[I + 1, J], nid[I + 2, J + 1], nid[I + 1, J + 2], nid[I, J + 1]]
            L.append(f"{e}, " + ", ".join(map(str, c)))
    L += ["*MATERIAL, NAME=B", "*ELASTIC, TYPE=ENGINEERING CONSTANTS", f"{E1}, {E2}, {E2}, {nu12}, {nu12}, 0.3, {G12}, {G12},", f"{0.1 * G12}",
          "*SHELL SECTION, ELSET=P, MATERIAL=B", f"{t}", "*BOUNDARY"]
    L += [f"{n}, 3, 3" for (i, j), n in nid.items() if i in (0, 2 * nx) or j in (0, 2 * ny)]
    L += [f"{n}, 1, 1" for (i, j), n in nid.items() if i == 0] + [f"{nid[0, 0]}, 2, 2"]
    F = {}
    for j in range(ny):
        for jj, w in ((2 * j, 1 / 6), (2 * j + 1, 2 / 3), (2 * j + 2, 1 / 6)):
            F[nid[2 * nx, jj]] = F.get(nid[2 * nx, jj], 0) - w * b / ny
    L += ["*STEP", "*BUCKLE", "2", "*CLOAD"] + [f"{n}, 1, {v:.9e}" for n, v in F.items()] + ["*END STEP"]
    (tmp_path / "p.inp").write_text("\n".join(L) + "\n")
    subprocess.run(["ccx", "-i", "p"], cwd=tmp_path, capture_output=True, timeout=300)
    lam = float(re.findall(r"^\s+1\s+([0-9.E+-]+)\s*$", (tmp_path / "p.dat").read_text(), re.M)[0])
    assert lam / t == pytest.approx(sigma_cr_ortotropica(E1, E2, G12, nu12, t, a, b), rel=0.05)

def test_baia_do_canard_casca_contra_analitico():
    from aranduBIS.fronteira import geometria as G
    from aranduBIS.nucleo.fe import chapeado_ccx as CC
    esq = G.abre_exemplo("generico/asa_canard.json")
    r = CC.analisa_baia(esq, "canard", 0.02, 0.10, 1.7e6, 90.0, z_LN=0.0, n_inc=8)
    assert r["sigma_cr_linear_MPa"] == pytest.approx(4.98, rel=0.15)
    assert 0.2 < r["knockdown_medido"] < 1.0
    assert r["abaulamento_convergiu"] and 0 < r["w_para_dentro_mm"] < 1.0
    th = r["tsai_hill"]
    assert th["convergiu"] and th["margem_tsai_hill"] > 0
    assert th["domina"] in ("fibra", "transversal", "cisalhamento")
    assert th["tsai_hill_max"] == pytest.approx(sum(th["termos"].values()), rel=0.2)
