import copy
import json
import math
from pathlib import Path

import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.aero.dinamica import dinamica, inercias
from aranduBIS.nucleo.aero.equilibrio import monta
from aranduBIS.nucleo.aero.estabilidade import derivadas

RAIZ = Path(__file__).resolve().parents[1]
I_TIPICA = {"Ixx": 0.6, "Iyy": 0.8, "Izz": 1.2, "Ixz": 0.0}

@pytest.fixture(scope="module")
def gen():
    d = json.loads((RAIZ / "cases/geometria/generico/generico.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/generico")
    return d

def test_sinais_das_derivadas_laterais(gen):
    def com_diedro(g):
        c = copy.deepcopy(gen)
        asa = next(e for e in c["elementos"] if e["nome"] == "Asa")
        for s in asa["secoes"]:
            s["zle"] = abs(s["y"]) * math.tan(math.radians(g))
        return derivadas(monta(c, 0.5), 3.0, V=12, rho=1.1)
    d0, d5 = com_diedro(0), com_diedro(5)
    assert d0.Cn_beta > 0 and d0.CY_beta < 0 and d0.Cl_p < 0 and d0.Cn_r < 0
    assert d5.Cl_beta < d0.Cl_beta < 0.05

def test_modos_de_uma_aeronave_convencional(gen):
    r = dinamica(gen, x_cg=0.5, V=12, massa_kg=8.0, I=I_TIPICA)
    m = r["modos"]
    sp = m["curto_periodo"]
    assert (sp["oscilatorio"] and sp["zeta"] > 0.2) or (not sp["oscilatorio"] and max(sp["raizes"]) < 0)
    assert m["rolagem"]["tau"] > 0 and m["rolagem"]["lambda"] < 0
    dr = m["dutch_roll"]
    assert dr is None and any("dutch roll" in a for a in r["avisos"]) or (dr["omega"] > 0 and dr["periodo"] > 0)
    assert r["origem_massa"] == "voce" and r["origem_inercia"] == "voce"

def test_mais_inercia_em_rolagem_deixa_a_rolagem_mais_lenta(gen):
    leve = dinamica(gen, x_cg=0.5, V=12, massa_kg=8.0, I=I_TIPICA)["modos"]["rolagem"]["tau"]
    pesada = dinamica(gen, x_cg=0.5, V=12, massa_kg=8.0, I=dict(I_TIPICA, Ixx=2.4))["modos"]["rolagem"]["tau"]
    assert pesada > 3 * leve

def test_sem_massa_declarada_pede_massa_e_inercias(gen):
    with pytest.raises(ValueError, match="massa"):
        dinamica(gen, V=12)
    r = AN.dinamica({"esquema": gen, "V": 12})
    assert "massa" in r["erro"]

def test_modelo_com_massa_pequena_avisa_que_faltam_pecas():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    d["elementos"] = [e for e in d["elementos"] if e["nome"] != "massa_equivalente"]
    r = dinamica(d, V=12, massa_kg=12.0)
    assert any("faltam bateria, motor e carga" in a for a in r["avisos"])
    assert inercias(d)["Ixx"] > 0.1

def test_inercias_incompletas_sao_recusadas(gen):
    r = AN.dinamica({"esquema": gen, "V": 12, "massa_kg": 8.0, "inercias": {"Ixx": 1.0}})
    assert "erro" in r

def test_inercia_por_raio_de_giro():
    from aranduBIS.nucleo.aero.dinamica import inercias_por_raio
    from aranduBIS.nucleo.modelador import aeronave_geometria as AG
    e = AG.exemplo_biplano_demo()
    r = inercias_por_raio(e, 10.0)
    assert r["Ixx"] > 0 and r["Iyy"] > 0 and r["Izz"] > 0
    r2 = inercias_por_raio(e, 10.0, {"rx": 0.5})
    assert abs(r2["Ixx"] / r["Ixx"] - 4.0) < 1e-9
