import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura.cargas import G, distribuicao, envelope_vn

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

def vn(**kw):
    a = dict(massa_kg=15.0, S=1.5, CL_max=1.8, CL_alpha=5.0, c_med=0.33, rho=1.1, Vc=13.0, Vd=16.0)
    a.update(kw)
    return envelope_vn(**a)

def test_estol_e_manobra_seguem_a_formula_classica():
    r = vn()
    Vs = np.sqrt(2 * 15.0 * G / (1.5 * 1.1 * 1.8))
    assert r["Vs"] == pytest.approx(Vs) and r["Va"] == pytest.approx(Vs * np.sqrt(1.8))
    i = int(np.argmin(np.abs(np.array(r["curvas"]["V"]) - r["Va"] * 0.7)))
    assert r["curvas"]["manobra_pos"][i] == pytest.approx((r["curvas"]["V"][i] / Vs) ** 2)
    assert max(r["curvas"]["manobra_pos"]) == pytest.approx(1.8)

def test_rajada_pratt_cooper_cresce_com_a_velocidade_e_com_a_rajada():
    a, b = vn(U_c=2.0), vn(U_c=4.0)
    assert b["dn_Vc"] == pytest.approx(2 * a["dn_Vc"])
    assert 0 < vn(Vc=10.0)["dn_Vc"] < vn(Vc=14.0)["dn_Vc"]
    assert 0 < vn()["Kg"] < 1

def test_rajada_acima_do_limite_de_manobra_avisa():
    r = vn(n_max=1.2, U_c=6.0)
    assert r["n_projeto"] > 1.2 and any("rajada dimensiona" in a for a in r["avisos"])

def test_fator_de_carga_negativo_so_entra_com_n_min_negativo():
    assert not any(p["nome"].startswith("negativo") for p in vn()["pontos"])
    r = vn(n_min=-1.0)
    assert any(p["nome"] == "negativo_Vg" for p in r["pontos"]) and min(r["curvas"]["manobra_neg"]) == pytest.approx(-1.0)

def test_cortante_e_fletor_fecham_com_o_equilibrio(biplano):
    d = distribuicao(biplano, 0.098, 0.2275, V=13.0, n=1.0, massa_kg=15.15, rho=1.1)
    assert d["convergiu"]
    assert d["sustentacao_total_N"] == pytest.approx(d["peso_N"], rel=0.03)
    asas = [s for s in d["superficies"] if s["referencia"]]
    assert len(asas) == 2
    for s in asas:
        assert s["cortante"][0] == pytest.approx(s["cortante_raiz"], rel=0.01) and s["cortante"][-1] > 0
        assert all(np.diff(s["cortante"]) <= 1e-9) and all(np.diff(s["fletor"]) <= 1e-9)
        assert s["fletor"][-1] < 0.05 * s["fletor"][0]
        lados = s["lados"]
        assert lados["dir"]["fletor_raiz"] == pytest.approx(lados["esq"]["fletor_raiz"], rel=0.02)

def test_alivio_inercial_reduz_o_fletor_e_cresce_com_n(biplano):
    com = distribuicao(biplano, 0.098, 0.2275, V=13.0, n=1.8, massa_kg=15.15, massas_sup={"asa_inferior": 0.3, "asa_superior": 0.3})
    sem = distribuicao(biplano, 0.098, 0.2275, V=13.0, n=1.8, massa_kg=15.15, massas_sup={"asa_inferior": 0.0, "asa_superior": 0.0})
    f = lambda d: next(s for s in d["superficies"] if s["nome"] == "asa_inferior")["fletor_raiz"]
    assert 0 < f(com) < f(sem)
    um = distribuicao(biplano, 0.098, 0.2275, V=13.0, n=1.0, massa_kg=15.15)
    assert f(sem) > 1.5 * next(s for s in um["superficies"] if s["nome"] == "asa_inferior")["fletor_raiz"]

def test_fronteira_cargas_devolve_criticos_e_erros_legiveis(biplano):
    r = AN.cargas({"esquema": biplano, "Vc": 13.0, "Vd": 15.9, "CL_max": 2.0})
    assert "erro" not in r and set(r["criticos"]) >= {"asa_inferior", "asa_superior"}
    c = r["criticos"]["asa_inferior"]
    assert c["fletor_ultimo"] == pytest.approx(1.2 * c["fletor_raiz"])
    assert "erro" in AN.cargas({"esquema": biplano, "Vc": 13.0, "Vd": 12.0})
    assert "erro" in AN.cargas({"esquema": {"elementos": []}})
