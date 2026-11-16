import json

import pytest

from aranduBIS.fronteira import geometria as G

def test_exemplos_incluem_o_biplano():
    assert any(n.endswith("biplano_b.json") for n in G.exemplos())

def test_constroi_devolve_malha_massa_e_cg():
    esq = G.abre_exemplo("biplano/biplano_b.json")
    r = G.constroi(esq)
    assert len(r["V"]) == 3 * r["n_vertices"] and len(r["T"]) == 3 * r["n_triangulos"]
    assert len(r["zona"]) == r["n_triangulos"] and len(r["camadas"]) == len(r["zonas"])
    assert r["massa_kg"] > 0 and len(r["cg_m"]) == 3
    json.dumps(r)

def test_erro_vira_mensagem_em_portugues():
    with pytest.raises(G.ErroDeGeometria, match="sem elementos"):
        G.constroi({"versao": 1, "nome": "x", "elementos": []})

def test_exemplo_nao_sai_da_pasta():
    with pytest.raises(G.ErroDeGeometria):
        G.abre_exemplo("../../pyproject.toml")

def test_grava_e_reabre_sem_campos_internos(tmp_path):
    esq = G.abre_exemplo("biplano/biplano_b.json")
    p = G.grava(esq, tmp_path, "minha")
    d = json.loads(open(p, encoding="utf8").read())
    assert "_pasta" not in d and d["elementos"] == esq["elementos"]
    with pytest.raises(G.ErroDeGeometria):
        G.grava(esq, tmp_path, "../fora")
