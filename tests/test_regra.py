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

def test_restricoes_medem_quanto_falta_e_regras_de_tres_anos():
    import json
    from pathlib import Path
    from aranduBIS.nucleo import regra as R
    pasta = Path(__file__).resolve().parents[1] / "cases" / "regras"
    aviao = {"PV": 4.0, "CP_bruta": 10.0, "envergadura": 3.1, "altura": 0.7, "potencia": 600.0, "n_superficies": 2, "NR": 185.0}
    tot = {}
    for ano in (2024, 2025, 2026):
        reg = R.normaliza(json.loads((pasta / f"sae{ano}_regular.json").read_text(encoding="utf8")))
        assert R.conferir(reg) == []
        out = R.avaliar(reg, aviao); tot[ano] = out["total"]
        rest = {c["nome"]: c for c in out["restricoes"]}
        if ano == 2024:
            assert not out["viavel"] and not rest["envergadura"]["ok"] and not rest["altura"]["ok"]
            assert rest["custo"]["ok"] and abs(rest["custo"]["valor"] - 600 * 3.1 ** (0.1529 + 0.1233 * 2)) < 1e-6
            assert abs(rest["envergadura"]["violacao"] - 0.6 / 2.5) < 1e-9 and abs(rest["envergadura"]["folga"] + 0.6) < 1e-9
            assert out["violacao"] > rest["envergadura"]["violacao"]
        else:
            assert out["viavel"] and out["violacao"] == 0.0 and abs(rest["envergadura"]["folga"] - 0.9) < 1e-9
    assert tot[2024] > tot[2026] > tot[2025] > 0

def test_medidas_da_aeronave_e_cone():
    import numpy as np
    from aranduBIS.nucleo import medidas as M
    asa = {"nome": "asa", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 20, "posicao": [0, 0, 0.3],
           "secoes": [{"y": -1.0, "xle": 0, "zle": 0, "corda": 0.3, "ainc": 0}, {"y": 1.0, "xle": 0, "zle": 0, "corda": 0.3, "ainc": 0}]}
    eh = dict(asa, nome="eh", posicao=[1.0, 0, 0.3], secoes=[dict(s, y=0.3 * s["y"], corda=0.15) for s in asa["secoes"]])
    ev = dict(asa, nome="ev", rolagem=90.0, posicao=[1.0, 0, 0.3], secoes=[{"y": 0.0, "corda": 0.15}, {"y": 0.3, "corda": 0.15}])
    m = M.medidas({"versao": 1, "nome": "t", "elementos": [asa, eh, ev]}, cone_altura=2.0)
    assert abs(m["envergadura"] - 2.0) < 1e-6 and abs(m["comprimento"] - 1.15) < 1e-3 and m["n_superficies"] == 2 and m["superficies"] == ["asa", "eh"]
    assert m["altura"] > 0.3 and m["raio_cone"] > 1.0
    assert M.medidas({"versao": 1, "nome": "t", "elementos": [asa, eh, ev]}, excluir=("ev",))["altura"] < m["altura"]
    P = np.array([[1.0, 0, 0], [-1.0, 0, 0], [0, 0, 0.5]])
    assert abs(M.raio_do_cone(P, 1.0) - 1.0) < 1e-3 and M.raio_do_cone(P, 0.4) == float("inf")
