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

def test_equilibrio_usa_o_cg_do_modelo_quando_ha_massas():
    import json
    from pathlib import Path
    d = json.loads((Path(__file__).resolve().parents[1] / "cases/geometria/generico/generico.json").read_text(encoding="utf-8"))
    r = AN.equilibrio({"esquema": d, "x_cg": 0.5, "CL_alvo": 0.8})
    assert r["cg_origem"] == "voce" and r["estavel"] and r["trim"]["CL"] == pytest.approx(0.8, abs=1e-6)
    r2 = AN.equilibrio({"esquema": d})
    assert r2["cg_origem"] in ("estimado", "massas do modelo") and r2["margem_estatica"] > 0

def test_equilibrio_sem_asa_devolve_erro_legivel():
    r = AN.equilibrio({"esquema": {"elementos": []}, "x_cg": 0.1})
    assert "erro" in r and "asa" in r["erro"]

def test_limites_devolve_cl_max_com_origem_das_polares():
    import json
    from pathlib import Path
    d = json.loads((Path(__file__).resolve().parents[1] / "cases/geometria/generico/generico.json").read_text(encoding="utf-8"))
    r = AN.limites({"esquema": d, "x_cg": 0.5})
    assert 1.0 < r["CL_max"] < 2.0 and len(r["curva"]["alpha"]) >= 5
    assert {p["origem"] for p in r["polares"]} <= {"banco", "aproximado"}
    assert "erro" in AN.limites({"esquema": d, "ncrit": 5})
    assert "erro" in AN.limites({"esquema": {"elementos": []}, "x_cg": 0.1})

def test_propulsao_lista_e_curva():
    l = AN.propulsao({"lista": True})
    assert len(l["motores"]) >= 6 and any(h["nome"] == "22x10E" for h in l["helices"])
    r = AN.propulsao({"motor": "Scorpion SII-4035-330", "helice": "22x10E"})
    assert 30 < r["T0"] < 55 and r["T"][0] > r["T"][-1]
    assert r["rpm"][0] > 3000 and r["V"][0] == 0.0
    assert "erro" in AN.propulsao({"motor": "nao existe", "helice": "22x10E"})
    assert AN.propulsao({"motor": "Scorpion SII-4035-330", "helice": "22x10E", "P_w": 400})["T0"] < r["T0"]
