from pathlib import Path

import numpy as np
import pytest

from aranduBIS.nucleo.aero.polares import BancoPolares

RAIZ = Path(__file__).resolve().parents[1]
H5 = RAIZ.parent / "referencia_v1/Arandu/data/polares_baixore.h5"

@pytest.fixture(scope="module")
def banco():
    return BancoPolares.carregar_npz(RAIZ / "data/polares.npz")

def test_banco_traz_os_dois_ncrit(banco):
    nomes = sorted(banco.polares)
    assert len(nomes) == 46
    assert any(n.endswith("@n4") for n in nomes) and any(n.endswith("@n7") for n in nomes)
    assert banco["S1223@n4"].meta["ncrit"] == 4.0

def test_consulta_devolve_numeros_finitos_dentro_da_grade(banco):
    p = banco["S1223@n4"]
    cl, cd, cm = p(np.array([0.0, 5.0]), 100000.0, avisar=False)
    assert np.all(np.isfinite(cl)) and np.all(cd > 0) and cl[1] > cl[0]

@pytest.mark.skipif(not H5.exists(), reason="Arandu 0.2.0 ausente")
def test_npz_e_igual_ao_hdf5_original(banco):
    h = BancoPolares.carregar(H5)
    for nome in list(h.polares)[:10]:
        assert np.allclose(h[nome].cl, banco[nome].cl) and np.allclose(h[nome].cd, banco[nome].cd)
        assert h[nome].origem == banco[nome].origem
