import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import trem as TR

P = {"Vc": 15.0, "Vd": 18.75, "V": 16.0, "rho": 1.2, "fator_seguranca": 1.5, "fator_pouso": 3.0, "K_flambagem": 1.0, "U_c": 5.0, "knockdown_pele": 0.6, "balsa_E_transv": 0.1}
FIXOS = {k: P[k] for k in ("fator_seguranca", "K_flambagem")}

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def monoplano():
    d = json.loads((RAIZ / "cases/geometria/monoplano/monoplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/monoplano")
    return d

@pytest.fixture(scope="module")
def r(monoplano):
    return TR.analisa(monoplano, fator_pouso=3.0, **FIXOS)

def caso(r, nome):
    return next(c for c in r["casos"] if c["caso"] == nome)

def test_reacoes_fecham_o_peso_e_o_momento(r):
    W, xcg = r["peso_N"], r["cg"][0]
    c = caso(r, "pouso_3_pontos")
    R = {k: v["R"] for k, v in c["rodas"].items()}
    assert sum(R.values()) == pytest.approx(3.0 * W, rel=1e-9)
    xm, xn = r["x_principais"], r["x_bequilha"]
    assert (R["roda_esq"] + R["roda_dir"]) * (xm - xcg) == pytest.approx(R["bequilha"] * (xcg - xn), rel=1e-9)
    assert caso(r, "pouso_2_pontos")["rodas"]["bequilha"]["R"] == 0.0

def test_modelo_fica_em_equilibrio_sem_apoio_real(r):
    for c in r["casos"]:
        assert c["residuo"] < 1e-8

def test_momento_na_barra_do_eixo_confere_com_a_mao(r, monoplano):
    c = caso(r, "pouso_3_pontos")
    b = max((b for b in c["piores"] if b["elemento"] == "trem"), key=lambda b: b["M"])
    alavanca = 0.17 - 0.045
    assert b["M"] == pytest.approx(1.5 * c["rodas"]["roda_dir"]["R"] * alavanca, rel=0.10)

def test_dois_pontos_e_pior_que_tres_e_fator_maior_reduz_margem(monoplano, r):
    assert caso(r, "pouso_2_pontos")["margem"] != caso(r, "pouso_3_pontos")["margem"]
    r2 = TR.analisa(monoplano, fator_pouso=2.0, **FIXOS)
    assert caso(r2, "pouso_3_pontos")["margem"] > caso(r, "pouso_3_pontos")["margem"]

def test_spin_up_nao_torce_o_eixo(r):
    c = caso(r, "pouso_3_pontos")
    assert max(b["T"] for b in c["piores"] if b["elemento"] == "trem") < 0.5

def test_cg_fora_das_rodas_e_recusado(monoplano):
    with pytest.raises(ValueError, match="entre a bequilha"):
        TR.analisa(monoplano, x_cg=0.5, fator_pouso=3.0, **FIXOS)

def test_fronteira_trem(monoplano):
    r2 = AN.trem({**P, "esquema": monoplano})
    assert "erro" not in r2 and r2["critico"]["margem"] < 1
    assert "erro" in AN.trem({**P, "esquema": monoplano, "fator_pouso": -1})
    sem = copy.deepcopy(monoplano)
    sem["elementos"] = [e for e in sem["elementos"] if e["tipo"] != "roda"]
    assert "rodas" in AN.trem({**P, "esquema": sem})["erro"]

def test_solda_do_eixo_cria_zona_rigida_e_alivia_o_eixo():
    esq = json.loads((RAIZ / "cases/geometria/monoplano/monoplano_a.json").read_text(encoding="utf-8")); esq["_pasta"] = str(RAIZ / "cases/geometria/monoplano")
    esq2, zonas = TR._com_solda(esq, 0.01)
    assert len(zonas) == 2
    for c, ext in zonas:
        assert all(abs(float((q - c)[1])) == pytest.approx(0.01, abs=1e-6) for q in ext)
    a = TR.analisa(esq, massa_kg=14.0, raio_solda=0.0, fator_pouso=3.0, **FIXOS); b = TR.analisa(esq, massa_kg=14.0, raio_solda=0.02, fator_pouso=3.0, **FIXOS)
    assert b["zonas_solda"] == 2
    assert b["casos"][0]["margem"] >= a["casos"][0]["margem"] - 1e-9
    assert TR.analisa(esq, massa_kg=14.0, raio_solda=0.5, fator_pouso=3.0, **FIXOS)["zonas_solda"] == 2
