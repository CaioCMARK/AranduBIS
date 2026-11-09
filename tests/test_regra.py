import random
import sys
from pathlib import Path

import pytest

from aranduBIS.nucleo import regra as R

import json

ARQ = Path(__file__).resolve().parents[1] / "cases" / "regras" / "sae2026_regular.json"

def _regra():
    return R.normaliza(json.loads(ARQ.read_text(encoding="utf8")))

def test_le_o_formato_do_arandu_e_nao_tem_problema():
    r = _regra()
    assert R.conferir(r) == []
    nomes = {e["nome"] for e in r["entradas"]}
    assert {"PV", "CP_bruta", "t", "NR", "envergadura"} <= nomes and r["so_conta_se"] == "voo_validado"

def test_avalia_um_caso_conhecido():
    r = _regra()
    a = R.avaliar(r, {"PV": 5.0, "CP_bruta": 10.0, "NR": 185.0, "envergadura": 0.0,
                      "parada_na_area": 1.0, "t": 20.0})
    g = {x["nome"]: x["valor"] for x in a["grandezas"]}
    assert g["CP"] == 10.0 and g["EE"] == 2.0 and g["P_EE"] == 100.0
    assert g["FPV"] == pytest.approx(1.10)
    it = {x["nome"]: x for x in a["itens"]}
    assert it["P_VOO"]["valor"] == pytest.approx(1.10 * 1.0 * 100.0 * (0.185 * 4 - 0.775 * 2 + 1.81) * 1.0)
    assert it["B_PO"]["conta"] and it["B_PO"]["valor"] == 4.0
    assert a["total"] == pytest.approx(sum(x["valor"] for x in a["itens"] if x["conta"]))

def test_item_condicional_some_da_soma_mas_aparece():
    r = _regra()
    a = R.avaliar(r, {"PV": 5, "CP_bruta": 10, "parada_na_area": 0})
    it = {x["nome"]: x for x in a["itens"]}
    assert not it["B_PO"]["aplica"] and not it["B_PO"]["conta"]

def test_voo_nao_validado_zera():
    a = R.avaliar(_regra(), {"PV": 5, "CP_bruta": 10, "voo_validado": 0})
    assert a["total"] == 0.0 and not a["conta"]

def test_edicao_muda_a_pontuacao():
    r = _regra()
    for g in r["grandezas"]:
        if g["nome"] == "P_EE":
            g["formula"] = "80 * EE"
    a = R.avaliar(r, {"PV": 5, "CP_bruta": 10})
    assert {x["nome"]: x["valor"] for x in a["grandezas"]}["P_EE"] == 160.0

def test_erros_aparecem_todos_e_em_portugues():
    r = _regra()
    r["grandezas"].append({"nome": "ruim", "formula": "ZZ + 1", "unidade": "", "descricao": ""})
    r["grandezas"].append({"nome": "ruim2", "formula": "1 +", "unidade": "", "descricao": ""})
    r["itens"].append({"nome": "I", "formula": "10 / 0", "quando": "", "descricao": ""})
    p = R.conferir(r)
    assert any("ZZ" in x for x in p) and any("ruim2" in x for x in p)
    a = R.avaliar(r, {"PV": 5, "CP_bruta": 10})
    assert {x["nome"]: x for x in a["itens"]}["I"]["erro"]
    assert {x["nome"]: x for x in a["grandezas"]}["ruim"]["erro"]

def test_nome_repetido_e_invalido():
    r = _regra()
    r["grandezas"].append({"nome": "EE", "formula": "1", "unidade": "", "descricao": ""})
    r["constantes"]["2x"] = 1
    p = " ".join(R.conferir(r))
    assert "já está em uso" in p and "nome inválido" in p

ARANDU = Path(__file__).resolve().parents[2] / "referencia_v1" / "Arandu" / "src"

@pytest.mark.skipif(not ARANDU.is_dir(), reason="Arandu 0.2.0 não está ao lado")
def test_igual_a_regra_tabelada_do_arandu_em_missoes_sorteadas():
    sys.path.insert(0, str(ARANDU))
    try:
        from arandu.score.base import Missao
        from arandu.score.tabelada import RegraTabelada
        velha = RegraTabelada.ler(ARQ)
        import inspect
        campos = set(inspect.signature(Missao).parameters)
    finally:
        sys.path.remove(str(ARANDU))
    rnd = random.Random(7)
    r = _regra()
    for _ in range(40):
        pv, cp = rnd.uniform(3, 12), rnd.uniform(0, 18)
        t, area = rnd.uniform(5, 45), rnd.random() < 0.5
        kw = dict(carga_paga=cp, peso_vazio=pv, tempo_retirada=t, parada_na_area=area, voo_validado=True)
        kw = {k: v for k, v in kw.items() if k in campos}
        ref = velha.pontuar(Missao(**kw)).total
        novo = R.avaliar(r, {"CP_bruta": cp, "PV": pv, "t": t, "parada_na_area": float(area)})["total"]
        assert novo == pytest.approx(ref, rel=1e-9, abs=1e-9)

def test_mensagem_de_nome_desconhecido_e_curta():
    r = _regra()
    r["itens"].append({"nome": "X", "formula": "ZZ + 1", "quando": "", "descricao": ""})
    a = R.avaliar(r, {"PV": 5, "CP_bruta": 10})
    erro = {x["nome"]: x for x in a["itens"]}["X"]["erro"]
    assert "ZZ" in erro and len(erro) < 160 and "\n" not in erro
