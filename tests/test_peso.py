import numpy as np
import pytest

from aranduBIS.fronteira import geometria as G
from aranduBIS.nucleo import peso as P
from aranduBIS.nucleo.modelador import aeronave_geometria as AG

def test_peso_vazio_soma_os_tres_blocos():
    esq = G.abre_exemplo("biplano/biplano_a.json")
    r = P.calcula(esq, {"servo_g": 25, "helice_g": 80, "esc_g": 70, "receptor_g": 15, "cabos_g": 60, "cola_pct": 10}, "Scorpion SII-4035-330", 20.0)
    assert r["peso_vazio_kg"] == pytest.approx(r["estrutura_kg"] + r["montagem_kg"] + r["sistemas_kg"])
    assert r["carga_paga_max_kg"] == pytest.approx(20.0 - r["peso_vazio_kg"])
    motor = next(s for s in r["sistemas"] if s["item"] == "motor")
    assert motor["massa_kg"] == pytest.approx(0.435)
    bat = next(s for s in r["sistemas"] if s["item"].startswith("bateria"))
    assert bat["massa_kg"] == pytest.approx(6 * 3.7 * 1.5 / 133.0)
    assert len([s for s in r["sistemas"] if s["item"].startswith("servo_")]) == 6
    assert r["faltam"] == []

def test_sem_numero_vira_pendencia_e_nao_zero_escondido():
    esq = G.abre_exemplo("biplano/biplano_a.json")
    r = P.calcula(esq, {})
    assert any("servo" in f for f in r["faltam"]) and "motor" in r["faltam"]
    assert any("Ainda sem numero" in a for a in r["avisos"])

def test_servos_no_modelo_entram_na_asa():
    esq = G.abre_exemplo("biplano/biplano_a.json")
    antes = AG.massa_e_cg(AG.constroi(esq))["massa_kg"]
    novo = P.servos_no_modelo(esq, 25.0)
    sv = [e for e in novo["elementos"] if e["nome"].startswith("servo_")]
    assert len(sv) == 6 and all(e["tipo"] == "ponto" for e in sv)
    ail = [e for e in sv if "aileron_inferior" in e["nome"]]
    assert sorted(round(e["posicao"][1], 3) for e in ail) == [-1.0, 1.0]
    assert AG.massa_e_cg(AG.constroi(novo))["massa_kg"] == pytest.approx(antes + 6 * 0.025)
    assert len([e for e in P.servos_no_modelo(novo, 25.0)["elementos"] if e["nome"].startswith("servo_")]) == 6

def test_servo_na_asa_entra_no_flutter():
    from aranduBIS.nucleo.estrutura import flutter as FL
    esq = G.abre_exemplo("biplano/biplano_a.json")
    sem = FL.dados_de_vibracao(esq, "asa_inferior", Vd=18.75)
    com = FL.dados_de_vibracao(P.servos_no_modelo(esq, 40.0), "asa_inferior", Vd=18.75)
    assert com["M"] == pytest.approx(sem["M"] + 0.040, rel=0.02)
    k = int(np.argmax(np.asarray(com["m_lin"]) - np.asarray(sem["m_lin"])))
    assert 0.67 <= com["y"][k] <= 1.17
