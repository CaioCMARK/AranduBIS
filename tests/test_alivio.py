import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import alivio as AL

RAIZ = Path(__file__).resolve().parents[1]
RET = [[0.0, 0.0], [200.0, 0.0], [200.0, 40.0], [0.0, 40.0]]

def test_furos_respeitam_borda_ponte_e_ficam_dentro():
    r = AL.propoe(RET, [], 3.0, borda_mm=6.0, ponte_mm=5.0, d_min_mm=8.0)
    assert len(r["furos"]) >= 4
    assert max(f["d"] for f in r["furos"]) == pytest.approx(28.0, abs=1e-6)
    for f in r["furos"]:
        assert 8.0 <= f["d"] <= 28.0 + 1e-6 and f["c"][1] == pytest.approx(20.0)
        assert 6.0 + 0.5 * f["d"] - 1e-6 <= f["c"][0] <= 200.0 - 6.0 - 0.5 * f["d"] + 1e-6
    F = sorted(r["furos"], key=lambda f: f["c"][0])
    for a, b in zip(F, F[1:]):
        assert b["c"][0] - a["c"][0] >= 0.5 * (a["d"] + b["d"]) + 5.0 - 1e-6
    assert r["fracao"] == pytest.approx(sum(np.pi * 0.25 * f["d"] ** 2 for f in F) / 8000.0)

def test_furo_de_tubo_afasta_o_alivio():
    tubo = {"c": [100.0, 20.0], "d": 12.0}
    r = AL.propoe(RET, [tubo], 3.0, borda_mm=6.0, ponte_mm=5.0)
    for f in r["furos"]:
        assert np.hypot(f["c"][0] - 100.0, f["c"][1] - 20.0) >= 0.5 * f["d"] + 6.0 + 5.0 - 1e-6

def test_carga_alta_encolhe_ou_tira_o_furo_e_a_margem_fica_positiva():
    leve = AL.propoe(RET, [{"c": [60.0, 20.0], "d": 8.0}], 3.0, carga_N=5.0, tau_adm_MPa=1.0, sigma_adm_MPa=5.0)
    forte = AL.propoe(RET, [{"c": [60.0, 20.0], "d": 8.0}], 3.0, carga_N=400.0, tau_adm_MPa=1.0, sigma_adm_MPa=5.0)
    assert forte["fracao"] < leve["fracao"]
    assert all(f["margem"] >= 0 for f in forte["furos"])
    assert AL.propoe(RET, [{"c": [60.0, 20.0], "d": 8.0}], 3.0, carga_N=1e5)["furos"] == []

def test_esforcos_da_viga_biapoiada_e_do_balanco():
    VM, nome = AL.esforcos(0.0, 200.0, 100.0, [50.0, 150.0])
    V, M = VM(np.array([100.0]))
    assert "biapoiada" in nome and V[0] == pytest.approx(0.0, abs=1e-9) and M[0] == pytest.approx(-0.5 * 0.5 * 100.0 ** 2 + 50.0 * 50.0)
    VM, nome = AL.esforcos(0.0, 200.0, 100.0, [50.0])
    V, M = VM(np.array([49.999, 200.0]))
    assert "engastada" in nome and M[0] == pytest.approx(-0.25 * 50.0 ** 2, rel=1e-3) and M[1] == 0.0

def test_fronteira_poe_os_alivios_no_dxf_e_devolve_o_fator_de_massa():
    esq = json.loads((RAIZ / "cases/geometria/monoplano/monoplano_a.json").read_text(encoding="utf-8"))
    esq["_pasta"] = str(RAIZ / "cases/geometria/monoplano")
    base = AN.nervuras_dxf({"esquema": esq, "asa": "asa"})
    r = AN.nervuras_dxf({"esquema": esq, "asa": "asa", "alivio": True})
    assert "erro" not in r and base["alivio"] is None
    a = r["alivio"]
    assert a["n_furos"] > 0 and 0.0 < a["fracao_removida"] < 0.6 and a["fator_massa"] == pytest.approx(1.0 - a["fracao_removida"])
    assert a["margem_min"] is None or a["margem_min"] >= 0.0
    assert r["dxf"].count("CIRCLE") > base["dxf"].count("CIRCLE")
    assert r["area_total_cm2"] < base["area_total_cm2"]
    assert any(f["tipo"] == "alivio" for p in r["pecas"] for f in p["furos"])
