import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN

RAIZ = Path(__file__).resolve().parents[1]
P = {"Vc": 15.0, "Vd": 18.0}

@pytest.fixture(scope="module")
def monoplano():
    d = json.loads((RAIZ / "cases/geometria/monoplano/monoplano_a.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/monoplano")
    return d

@pytest.fixture(scope="module")
def r(monoplano):
    return AN.juncao({**P, "esquema": monoplano})

def _asa(r, nome):
    return next(a for a in r["asas"] if a["asa"] == nome)

def _var(a, tipo):
    return next(v for v in a["variantes"] if v["tipo"] == tipo)

def test_solda_transmite_o_fletor_da_raiz(r):
    v = _var(_asa(r, "asa"), "solda")
    assert v["flexao_transmitida_Nm"] == pytest.approx(v["fletor_na_ligacao_Nm"], rel=0.03)
    assert v["flecha_ponta_mm"] > 0

def test_parafuso_alivia_a_ligacao_e_cede_mais(r):
    a = _asa(r, "asa")
    s, p = _var(a, "solda"), _var(a, "parafuso:x")
    assert p["flexao_transmitida_Nm"] < 0.8 * s["flexao_transmitida_Nm"]
    assert p["flecha_ponta_mm"] > s["flecha_ponta_mm"]
    assert p["delta"]["flexao_transmitida_Nm"] < 0 < p["delta"]["flecha_ponta_mm"]

def test_duas_rotulas_alinhadas_viram_mecanismo(r):
    a = _asa(r, "asa")
    assert a["n_ligacoes"] == 2
    assert _var(a, "rotula").get("mecanismo") is True
    assert any("mecanismo" in x for x in r["avisos"])

def test_fletor_nao_depende_da_junta_fora_da_ligacao(r):
    a = _asa(r, "asa")
    s, p = _var(a, "solda"), _var(a, "parafuso:x")
    assert p["fletor_Nm"][-3] == pytest.approx(s["fletor_Nm"][-3], rel=1e-6, abs=1e-9)

def test_ligacao_declarada_e_usada(monoplano):
    e = copy.deepcopy(monoplano)
    el = next(x for x in e["elementos"] if x["nome"] == "montante_tubos")
    zs = np.array([p[2] for p in el["nos"]])
    topo = [i for i in np.argsort(-zs)[:4]]
    el["vinculos"] = [{"no": int(i), "tipo": "ligacao", "alvo": "asa"} for i in topo]
    r2 = AN.juncao({**P, "esquema": e, "asa": "asa"})
    a = _asa(r2, "asa")
    assert a["declaradas"] and a["n_ligacoes"] == 4
    assert not any("Nenhuma ligacao declarada com asa" in x for x in r2["avisos"])

def test_tipo_desconhecido_e_erro(monoplano):
    r2 = AN.juncao({**P, "esquema": monoplano, "tipos": ["solda", "cola"]})
    assert "erro" in r2

def test_apoio_longe_faz_a_trelica_trabalhar(monoplano):
    e = copy.deepcopy(monoplano)
    el = next(x for x in e["elementos"] if x["nome"] == "montante_tubos")
    zs = [p[2] for p in el["nos"]]
    el["vinculos"] = [{"no": i, "tipo": "engaste"} for i, p in enumerate(el["nos"]) if p[2] < min(zs) + 0.08]
    r2 = AN.juncao({**P, "esquema": e, "asa": "asa"})
    v = _var(_asa(r2, "asa"), "solda")
    assert v["margem_trelica"] < 90
