import json
from pathlib import Path

import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.aero.dinamica import dinamica
from aranduBIS.nucleo.aero.envelope import envelope_cg

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

def test_envelope_do_biplano_e_estavel_nos_cantos(biplano):
    r = envelope_cg(biplano, V=13, massa_kg=15.15)
    assert len(r["itens"]) == 5 and r["ok"]
    assert 0.05 < r["margem_min"] <= r["margem_max"] < 0.2
    m = {i["nome"]: i["margem_estatica"] for i in r["itens"]}
    assert m["traseiro-baixo"] < m["dianteiro-baixo"]

def test_modelo_sem_envelope_diz_o_que_falta(biplano):
    d = dict(biplano); d.pop("envelope_cg")
    with pytest.raises(ValueError, match="envelope_cg"):
        envelope_cg(d)
    assert "erro" in AN.envelope_cg({"esquema": d})

def test_inercias_declaradas_no_modelo(biplano):
    r = dinamica(biplano, V=13)
    assert r["origem_inercia"] == "declarada no modelo" and abs(r["inercias"]["Ixx"] - 0.784) < 1e-9
    assert abs(r["m"] - 15.15) < 0.01
    sobreposta = dinamica(biplano, V=13, I={"Ixx": 1.0, "Iyy": 1.0, "Izz": 1.0, "Ixz": 0.0})
    assert sobreposta["origem_inercia"] == "voce"
