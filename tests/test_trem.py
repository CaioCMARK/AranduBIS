import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import trem as TR

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def r(biplano):
    return TR.analisa(biplano)

def caso(r, nome):
    return next(c for c in r["casos"] if c["caso"] == nome)

def test_reacoes_fecham_o_peso_e_o_momento(r):
    W, xcg = r["peso_N"], r["cg"][0]
    c = caso(r, "pouso_3_pontos")
    R = {k: v["R"] for k, v in c["rodas"].items()}
    assert sum(R.values()) == pytest.approx(5.4 * W, rel=1e-9)
    xm, xn = r["x_principais"], r["x_bequilha"]
    assert (R["roda_esq"] + R["roda_dir"]) * (xm - xcg) == pytest.approx(R["bequilha"] * (xcg - xn), rel=1e-9)
    assert caso(r, "pouso_2_pontos")["rodas"]["bequilha"]["R"] == 0.0

def test_modelo_fica_em_equilibrio_sem_apoio_real(r):
    for c in r["casos"]:
        assert c["residuo"] < 1e-8

def test_momento_na_barra_do_eixo_confere_com_a_mao(r, biplano):
    c = caso(r, "pouso_3_pontos")
    b = max((b for b in c["piores"] if b["elemento"] == "trem"), key=lambda b: b["M"])
    alavanca = 0.165 - 0.0547
    assert b["M"] == pytest.approx(1.2 * c["rodas"]["roda_dir"]["R"] * alavanca, rel=0.10)

def test_dois_pontos_e_pior_que_tres_e_fator_maior_reduz_margem(biplano, r):
    assert caso(r, "pouso_2_pontos")["margem"] < caso(r, "pouso_3_pontos")["margem"]
    r2 = TR.analisa(biplano, fator_pouso=3.0)
    assert caso(r2, "pouso_3_pontos")["margem"] > caso(r, "pouso_3_pontos")["margem"]

def test_spin_up_nao_torce_o_eixo(r):
    c = caso(r, "pouso_3_pontos")
    assert max(b["T"] for b in c["piores"] if b["elemento"] == "trem") < 0.5

def test_cg_fora_das_rodas_e_recusado(biplano):
    with pytest.raises(ValueError, match="entre a bequilha"):
        TR.analisa(biplano, x_cg=0.5)

def test_fronteira_trem(biplano):
    r2 = AN.trem({"esquema": biplano})
    assert "erro" not in r2 and r2["critico"]["margem"] < 1
    assert "erro" in AN.trem({"esquema": biplano, "fator_pouso": -1})
    sem = copy.deepcopy(biplano)
    sem["elementos"] = [e for e in sem["elementos"] if e["tipo"] != "roda"]
    assert "rodas" in AN.trem({"esquema": sem})["erro"]
