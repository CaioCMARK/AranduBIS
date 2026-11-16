import math
import warnings

import pytest

from aranduBIS.nucleo.aero import laboratorio_otim as LO
from aranduBIS.nucleo.aero.equilibrio import longitudinal


@pytest.fixture(autouse=True)
def _sem_aviso():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


@pytest.mark.parametrize("nome", LO.NOMES)
def test_cadeia_inteira_sem_falha(nome):
    prob = LO.problema(nome)
    r = LO.avalia(prob, {})
    assert r["falha"] is None, r["falha"]
    q = r["resultados"]
    assert 2.0 < q["PV"] < 8.0 and q["CP"] > 4.0 and r["pontuacao"] > 50.0
    assert q["envergadura"] == pytest.approx(2.8, abs=0.06)
    assert q["Cn_beta"] is not None and math.isfinite(q["Cn_beta"])
    assert {c["nome"] for c in r["restricoes"]} >= {"envergadura", "potencia", "peso_total", "margem_estatica", "margem_estrutural", "Cn_beta"}


def test_numero_de_superficies_da_regra():
    n = {nome: LO.avalia(LO.problema(nome), {})["resultados"]["n_superficies"] for nome in ("asa_voadora_pontas", "bwb", "tandem", "burgess_dunne")}
    assert n == {"asa_voadora_pontas": 1, "bwb": 1, "tandem": 2, "burgess_dunne": 2}


def test_tubo_termina_na_secao_da_ponta():
    prob = LO.problema("monoplano_cauda")
    for kt in (0.7, 1.0, 1.3):
        r = LO.avalia(prob, {"kt": kt, "b": 3.1})
        assert r["falha"] is None, (kt, r["falha"])


def test_derivas_continuam_a_ponta_da_asa():
    prob = LO.problema("asa_voadora_pontas")
    esq = LO.prepara(prob, {"b": 3.4, "kc": 2.2, "sw": 0.8})["base"]
    asa = next(e for e in esq["elementos"] if e["nome"] == "asa")
    ponta = max(asa["secoes"], key=lambda s: s["y"])
    f = next(e for e in esq["elementos"] if e["nome"] == "deriva_dir")
    assert f["posicao"][1] == pytest.approx(ponta["y"], rel=1e-9)
    assert f["posicao"][0] == pytest.approx(asa["posicao"][0] + ponta["xle"], rel=1e-9)
    assert f["secoes"][0]["corda"] == pytest.approx(ponta["corda"], rel=1e-9)


def test_trim_por_flape_so_na_parte_externa():
    prob = LO.problema("bwb")
    p = LO.prepara(prob, {})
    esq = p["base"]
    kw = dict(V=14.0, rho=1.1, z_cg=0.0, CL_alvo=0.7, comando="asa", tipo="flape", x_charneira=0.7, n_span=12, n_chord=2)
    x_cg = 0.5
    a = longitudinal(esq, x_cg, y_min=0.0, **kw)["trim"]
    b = longitudinal(esq, x_cg, y_min=0.5, **kw)["trim"]
    assert a is not None and b is not None
    assert abs(b["deflexao"]) > abs(a["deflexao"])


@pytest.mark.parametrize("nome", ["asa_voadora_pontas", "monoplano_cauda"])
def test_otimo_salvo_reproduz_na_malha_cheia(nome):
    import json
    from pathlib import Path
    f = Path(LO.RAIZ) / "cases" / "otimiza" / "laboratorio" / "saida" / f"{nome}.json"
    d = json.loads(f.read_text(encoding="utf8"))["refino"][0]
    prob = LO.problema(nome)
    prob["analise"].pop("malha", None)
    r = LO.avalia(prob, d["x"])
    assert r["viavel"], [c["nome"] for c in r["restricoes"] if not c["ok"]]
    assert r["pontuacao"] == pytest.approx(d["pontuacao"], rel=1e-6)


def test_otimos_salvos_respeitam_varredura_e_comprimento():
    import json
    from pathlib import Path
    pasta = Path(LO.RAIZ) / "cases" / "otimiza" / "laboratorio" / "saida"
    vistos = 0
    for nome in LO.NOMES:
        r = json.loads((pasta / f"{nome}.json").read_text(encoding="utf8"))["refino"][0]
        q = r["resultados"]
        assert q["varredura_externa"] <= LO.VARRE_EXT_MAX + 1e-6, nome
        assert q["varredura_interna"] <= LO.VARRE_INT_MAX + 1e-6, nome
        assert q["comprimento_sup"] <= LO.COMP_SUP_MAX + 1e-6, nome
        vistos += 1
    assert vistos == len(LO.NOMES)
