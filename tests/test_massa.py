import json
from pathlib import Path

import pytest

from aranduBIS.nucleo.estrutura.massa import balanco

CASO = Path(__file__).resolve().parents[1] / "cases/geometria/biplano/biplano_2026.json"

@pytest.fixture(scope="module")
def esq():
    e = json.loads(CASO.read_text(encoding="utf-8")); e["_pasta"] = str(CASO.parent); return e

def test_soma_dos_grupos_fecha_o_total(esq):
    r = balanco(esq, 15.15)
    assert sum(g["massa_kg"] for g in r["grupos"]) == pytest.approx(r["total_kg"])
    assert r["desenhada_kg"] + r["nao_modelada_kg"] == pytest.approx(r["total_kg"])

def test_massa_nao_modelada_fecha_mtow(esq):
    r = balanco(esq, 16.0)
    assert r["desenhada_kg"] + r["nao_modelada_sugerida_kg"] == pytest.approx(16.0)

def test_cg_e_media_ponderada(esq):
    r = balanco(esq)
    soma = sum(g["massa_kg"] * g["cg"][0] for g in r["grupos"]) / r["total_kg"]
    assert r["cg"][0] == pytest.approx(soma, rel=1e-6)

def test_sensibilidade_estrutura_mais_pesada_reduz_nao_modelada(esq):
    s = balanco(esq, 15.15)["sensibilidade"]
    assert s[-1]["nao_modelada_mtow_fixo_kg"] < s[0]["nao_modelada_mtow_fixo_kg"]
    assert s[-1]["massa_total_livre_kg"] > s[0]["massa_total_livre_kg"]

def test_sem_massas_levanta_erro():
    with pytest.raises(Exception):
        balanco({"elementos": []})
