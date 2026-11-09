import json

import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.fronteira import geometria as G

PAR = {
    "massa_kg": 12.0,
    "aeronave": {"S": 1.4, "CL_max": 2.0, "CL_corrida": 0.5, "CD_corrida": 0.06},
    "tracao": {"T0": 60.0, "V0": 40.0},
    "condicoes": {"pista_m": 55.0, "obstaculo_m": 0.9},
}

def test_resumo_aero_do_exemplo_pega_so_as_asas_que_sustentam():
    r = AN.resumo_aero(G.abre_exemplo("biplano/biplano_2026.json"))
    nomes = {s["nome"] for s in r["superficies"]}
    assert nomes == {"asa_inferior", "asa_superior"}
    assert 1.0 < r["area_m2"] < 2.0 and r["envergadura_m"] == pytest.approx(2.4, abs=1e-6)
    assert r["alongamento"] == pytest.approx(r["envergadura_m"] ** 2 / r["area_m2"])

def test_papel_explicito_vence_o_nome():
    esq = {"elementos": [{"nome": "empenagem_x", "tipo": "asa", "papel": "sustentacao",
                          "secoes": [{"y": -1, "corda": 0.2}, {"y": 1, "corda": 0.2}]}]}
    assert AN.resumo_aero(esq)["area_m2"] == pytest.approx(0.4)

def test_decolagem_devolve_tudo_que_a_tela_precisa_e_serializa():
    r = AN.decolagem(PAR)
    json.dumps(r)
    assert r["transpos"] and r["folga_m"] > 0
    assert r["massa_maxima"]["massa_kg"] > 12.0
    assert len(r["serie"]["x"]) == len(r["serie"]["h"]) <= 400
    assert set(r["serie"]["forcas"]) == {"T", "D", "atrito", "L", "W"}
    assert len(r["varredura"]) == 25

def test_nao_decolou_vira_mensagem_e_nao_excecao():
    p = json.loads(json.dumps(PAR))
    p["massa_kg"] = 45.0
    r = AN.decolagem(p)
    json.dump(r, open(__import__("os").devnull, "w"))
    assert not r["transpos"] and r["motivo"]

def test_entrada_invalida_diz_qual_campo():
    p = json.loads(json.dumps(PAR))
    p["aeronave"]["S"] = -1
    with pytest.raises(AN.ErroDeAnalise, match="S"):
        AN.decolagem(p)
    p = json.loads(json.dumps(PAR))
    del p["aeronave"]["CL_max"]
    with pytest.raises(AN.ErroDeAnalise, match="CL_max"):
        AN.decolagem(p)
