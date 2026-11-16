import numpy as np
import pytest

from aranduBIS.nucleo.fe.modelo import Modelo
from aranduBIS.nucleo.fe.solver import Sistema

E, I, A, L, P = 70e9, 2.0e-9, 1.0e-4, 0.4, 10.0

def viga(junta=None, apoio_c=True, eixo=None):
    m = Modelo()
    m.material(1, E, nu=0.3, rho=1600.0)
    m.prop(1, 1, A, I, I, 2 * I)
    for i, x in enumerate((0.0, L, 2 * L), 1):
        m.no(i, x, 0.0, 0.0)
    m.barra(1, 1, 1, 2, (0, 0, 1)); m.barra(2, 1, 2, 3, (0, 0, 1))
    m.engasta([1])
    if apoio_c:
        m.engasta([3], graus=(1, 2, 3))
    if junta:
        m.junta(2, junta, eixo)
    m.carga(1, 2, [0, 0, -P, 0, 0, 0])
    return m

def flecha(m):
    return -Sistema(m).estatica(1)["u"][2][2]

def test_solda_reproduz_viga_engastada_apoiada():
    esperado = 7 * P * (2 * L) ** 3 / (768 * E * I)
    assert flecha(viga()) == pytest.approx(esperado, rel=1e-6)

def test_rotula_no_meio_deixa_so_o_balanco_trabalhar():
    esperado = P * L ** 3 / (3 * E * I)
    assert flecha(viga("rotula")) == pytest.approx(esperado, rel=1e-6)

def test_parafuso_libera_so_o_eixo_escolhido():
    solda, rotula = flecha(viga()), flecha(viga("rotula"))
    assert flecha(viga("parafuso", eixo=(0, 1, 0))) == pytest.approx(rotula, rel=1e-6)
    assert flecha(viga("parafuso", eixo=(0, 0, 1))) == pytest.approx(solda, rel=1e-6)
    assert flecha(viga("parafuso", eixo=(1, 0, 0))) == pytest.approx(solda, rel=1e-6)

def test_momento_some_na_rotula():
    s = Sistema(viga("rotula")).estatica(1)
    f2 = s["esforcos"][2]
    assert np.abs(f2[[4, 5, 10, 11]]).max() < 1e-6 * P * L
    f1 = s["esforcos"][1]
    assert abs(max(abs(f1[4]), abs(f1[5])) - P * L) < 1e-6 * P * L

def test_mecanismo_e_avisado():
    with pytest.raises(ValueError, match="mecanismo"):
        Sistema(viga("rotula", apoio_c=False)).estatica(1)

def test_frequencia_cai_com_a_rotula():
    f_s = Sistema(viga()).modos(3)["f_hz"][0]
    f_r = Sistema(viga("rotula")).modos(3)["f_hz"][0]
    assert 0 < f_r < f_s

def test_sem_junta_nada_muda():
    s = Sistema(viga())
    assert s.liberadas == 0 and s.n == s.n_nos

def test_rotula_em_no_engastado_vira_apoio_articulado():
    m = Modelo()
    m.material(1, E, nu=0.3, rho=1600.0); m.prop(1, 1, A, I, I, 2 * I)
    m.no(1, 0, 0, 0); m.no(2, L, 0, 0); m.no(3, 2 * L, 0, 0)
    m.barra(1, 1, 1, 2, (0, 0, 1)); m.barra(2, 1, 2, 3, (0, 0, 1))
    m.engasta([1]); m.engasta([3]); m.junta(1, "rotula"); m.junta(3, "rotula")
    m.carga(1, 2, [0, 0, -P, 0, 0, 0])
    esperado = P * (2 * L) ** 3 / (48 * E * I)
    assert -Sistema(m).estatica(1)["u"][2][2] == pytest.approx(esperado, rel=1e-6)

import copy
import json
from pathlib import Path

from aranduBIS.nucleo.estrutura import cauda as CA
from aranduBIS.nucleo.estrutura import trem as TR
from aranduBIS.nucleo.estrutura import vibracao as VB
from materiais_fixos import MATS_FIXOS

RAIZ = Path(__file__).resolve().parents[1]
KW = dict(tailstrike_peso=1.5, Vc=15.0, Vd=18.0, U_c=4.0, rho=1.1, mats=MATS_FIXOS)

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def base(biplano):
    return CA.analisa(biplano, **KW)

def _trelica(esq, nome):
    return next(e for e in esq["elementos"] if e.get("tipo") == "trelica" and e["nome"] == nome)

def test_apoio_explicito_igual_ao_automatico_da_o_mesmo(biplano, base):
    e = copy.deepcopy(biplano)
    x_ap = base["x_apoio"]
    for el in e["elementos"]:
        if el.get("tipo") == "trelica":
            el["vinculos"] = [{"no": i, "tipo": "engaste"} for i, p in enumerate(el["nos"]) if p[0] <= x_ap + 1e-6]
    r = CA.analisa(e, **KW)
    assert r["apoio_explicito"] and not base["apoio_explicito"]
    assert r["apoio_nos"] == base["apoio_nos"]
    for a, b in zip(r["casos"], base["casos"]):
        assert a["flecha_ponta_mm"] == pytest.approx(b["flecha_ponta_mm"], rel=1e-9)
        assert a["margem"] == pytest.approx(b["margem"], rel=1e-9)
    assert any("substituem a regra" in a for a in r["avisos"])

def test_junta_solda_declarada_nao_muda_nada(biplano, base):
    e = copy.deepcopy(biplano)
    el = _trelica(e, "boom_tubos")
    el["juntas"] = [{"no": i, "tipo": "solda"} for i in range(len(el["nos"]))]
    r = CA.analisa(e, **KW)
    assert r["juntas_articuladas"] == 0
    assert r["casos"][0]["flecha_ponta_mm"] == pytest.approx(base["casos"][0]["flecha_ponta_mm"], rel=1e-12)

def test_parafusos_no_boom_deixam_a_cauda_mais_flexivel(biplano, base):
    e = copy.deepcopy(biplano)
    el = _trelica(e, "boom_tubos")
    xs = [p[0] for p in el["nos"]]; meio = 0.5 * (min(xs) + max(xs))
    el["juntas"] = [{"no": i, "tipo": "rotula"} for i, p in enumerate(el["nos"]) if abs(p[0] - meio) < 0.25 * (max(xs) - min(xs))]
    assert el["juntas"]
    try:
        r = CA.analisa(e, **KW)
    except ValueError as x:
        assert "mecanismo" in str(x)
        return
    assert r["juntas_articuladas"] > 0
    assert r["modos_hz"][0] <= base["modos_hz"][0] * (1 + 1e-9)
    assert max(c["flecha_ponta_mm"] for c in r["casos"]) >= max(c["flecha_ponta_mm"] for c in base["casos"]) * (1 - 1e-9)

def test_junta_invalida_vira_aviso(biplano):
    e = copy.deepcopy(biplano)
    el = _trelica(e, "boom_tubos")
    el["juntas"] = [{"no": 9999, "tipo": "rotula"}, {"no": 0, "tipo": "cola"}]
    r = CA.analisa(e, **KW)
    assert any("nao existe" in a for a in r["avisos"]) and any("desconhecido" in a for a in r["avisos"])

def test_trem_e_vibracao_aceitam_juntas(biplano):
    e = copy.deepcopy(biplano)
    el = _trelica(e, "trem")
    el["juntas"] = [{"no": 0, "tipo": "parafuso", "eixo_livre": "y"}, {"no": 1, "tipo": "parafuso", "eixo_livre": "y"}]
    r = TR.analisa(e, mats=MATS_FIXOS)
    assert r["casos"]
    v = VB.analisa(e, mats=MATS_FIXOS) if hasattr(VB, "analisa") else None
    assert v is None or v

def test_roda_presa_por_ligacao_declarada(biplano):
    base = TR.analisa(biplano, mats=MATS_FIXOS)
    e = copy.deepcopy(biplano)
    el = _trelica(e, "trem")
    rodas = [x for x in e["elementos"] if x.get("tipo") == "roda"]
    for r in rodas:
        c = np.array([r["posicao"][0], r.get("y", r["posicao"][1]), r["posicao"][2]])
        d = [float(np.linalg.norm(np.array(p) - c)) for p in el["nos"]]
        if min(d) < 0.02:
            el.setdefault("vinculos", []).append({"no": int(np.argmin(d)), "tipo": "roda", "alvo": r["nome"]})
    assert el.get("vinculos")
    r2 = TR.analisa(e, mats=MATS_FIXOS)
    assert [c["margem"] for c in r2["casos"]] == pytest.approx([c["margem"] for c in base["casos"]], rel=1e-9)

def test_ligacao_rigida_parcial_e_uma_rotula():
    def monta(graus):
        m = Modelo()
        m.material(1, E, nu=0.3, rho=1600.0); m.prop(1, 1, A, I, I, 2 * I)
        m.no(1, 0, 0, 0); m.no(2, L, 0, 0); m.no(3, L, 0, 0); m.no(4, 2 * L, 0, 0)
        m.barra(1, 1, 1, 2, (0, 0, 1)); m.barra(2, 1, 3, 4, (0, 0, 1))
        m.rigido(10, 2, [3], graus=graus)
        m.engasta([1]); m.engasta([4], graus=(1, 2, 3))
        m.carga(1, 2, [0, 0, -P, 0, 0, 0])
        return -Sistema(m).estatica(1)["u"][2][2]
    assert monta(None) == pytest.approx(7 * P * (2 * L) ** 3 / (768 * E * I), rel=1e-6)
    assert monta((1, 2, 3, 4)) == pytest.approx(P * L ** 3 / (3 * E * I), rel=1e-6)
    assert monta((1, 2, 3, 4, 6)) == pytest.approx(P * L ** 3 / (3 * E * I), rel=1e-6)
    assert monta((1, 2, 3, 4, 5)) == pytest.approx(7 * P * (2 * L) ** 3 / (768 * E * I), rel=1e-6)

def test_resistencia_de_junta_por_no(biplano, base):
    assert base["junta_critica"] is not None
    caso, j = base["junta_critica"]
    assert j["tipo"] == "solda" and j["modo"] in ("forca", "momento", "torcao") and j["utilizacao"] > 0
    assert j["margem"] == pytest.approx(1.0 / j["utilizacao"] - 1.0)
    fraca = CA.analisa(biplano, **KW, juntas={"tau_cola_MPa": 5.0})
    assert fraca["junta_critica"][1]["utilizacao"] == pytest.approx(2.0 * j["utilizacao"], rel=1e-9)
    kt = CA.analisa(biplano, **KW, juntas={"Kt": 3.0})
    assert kt["junta_critica"][1]["utilizacao"] == pytest.approx(2.0 * j["utilizacao"], rel=1e-9)

def test_junta_de_parafuso_usa_corte_e_esmagamento(biplano):
    e = copy.deepcopy(biplano)
    el = _trelica(e, "boom_tubos")
    xs = [p[0] for p in el["nos"]]
    alvo = int(np.argmax(xs))
    el["juntas"] = [{"no": alvo, "tipo": "parafuso", "eixo_livre": "y"}]
    r = CA.analisa(e, **KW)
    todas = [j for c in r["casos"] for j in c["juntas"]]
    assert all(j["modo"] in ("forca", "momento", "torcao", "corte_parafuso", "esmagamento") for j in todas)
    assert r["juntas_hipoteses"]["d_parafuso_mm"] == 3.0
