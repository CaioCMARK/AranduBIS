import math

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.fronteira import geometria as G
from aranduBIS.nucleo.estrutura import planifica as PL
from aranduBIS.nucleo.modelador import dxf as DXF


def _grade(f, m1=7, nk=21):
    return np.array([[f(j / (m1 - 1), k / (nk - 1)) for k in range(nk)] for j in range(m1)])


def test_cilindro_desdobra_sem_deformar():
    R = 300.0
    G_ = _grade(lambda u, v: (R * math.sin(0.8 * v), 120.0 * u, R * math.cos(0.8 * v)))
    r = PL.achata(G_)
    assert np.abs(r["eps"]).max() < 1e-3
    assert np.abs(r["defeito"]).max() < 1e-6


def test_esfera_nao_desdobra_e_o_deficit_mede_a_curvatura():
    R = 1000.0
    a = 0.25
    G_ = _grade(lambda u, v: (R * math.cos(a * (u - 0.5)) * math.sin(a * (v - 0.5)), R * math.sin(a * (u - 0.5)), R * math.cos(a * (u - 0.5)) * math.cos(a * (v - 0.5))))
    r = PL.achata(G_)
    assert np.abs(r["eps"]).max() > 0.05
    area = r["area3"]
    interna = (7 - 2) * (21 - 2) / ((7 - 1) * (21 - 1))
    assert r["defeito"].sum() == pytest.approx(area * interna / R ** 2, rel=0.1)


def _asa(estrutura, secoes=None):
    sec = secoes or [{"y": 0.0, "xle": 0.0, "z": 0.0, "corda": 0.30, "ainc": 0.0}, {"y": 0.9, "xle": 0.05, "z": 0.0, "corda": 0.20, "ainc": 0.0}]
    return {"nome": "t", "_pasta": "cases/geometria/biplano", "elementos": [{"nome": "asa", "tipo": "asa", "perfil": "NACA 2412", "secoes": sec, "estrutura": estrutura}]}


def test_faixas_de_asa_reta_desdobram_bem():
    esq = _asa({"chapeado": {"ate_xc": 0.3, "espessura": 0.0015, "material": "balsa"}, "nervuras": {"y": [0.3, 0.6]}})
    r = PL.faixas(esq, "asa")
    assert len(r["faixas"]) >= 3
    assert all(f["status"] == "ok" for f in r["faixas"])
    assert r["limite_pct"] == pytest.approx(0.3)


def test_limite_do_material_e_do_usuario():
    assert PL.limite_do_material("balsa") == pytest.approx(0.3)
    assert PL.limite_do_material("filme termocontratil") == pytest.approx(3.0)
    assert PL.limite_do_material("balsa", 1.2) == pytest.approx(1.2)


def test_sem_chapeado_e_modo_invalido():
    esq = _asa({"nervuras": {"y": [0.3]}})
    with pytest.raises(ValueError, match="chapeado"):
        PL.faixas(esq, "asa")
    esq = _asa({"chapeado": {"ate_xc": 0.3}, "nervuras": {"y": [0.3]}})
    with pytest.raises(ValueError, match="modo"):
        PL.faixas(esq, "asa", modo="x")
    with pytest.raises(ValueError, match="nao existe"):
        PL.faixas(esq, "outra")


def test_margem_de_cola_aumenta_a_peca():
    esq = _asa({"chapeado": {"ate_xc": 0.3, "espessura": 0.0015}, "nervuras": {"y": [0.3, 0.6]}})
    sem = PL.faixas(esq, "asa", margem_cola_mm=0.0)["faixas"][1]["pecas"][0]
    com = PL.faixas(esq, "asa", margem_cola_mm=5.0)["faixas"][1]["pecas"][0]
    a = np.array(sem["contorno"]); b = np.array(com["contorno"])
    assert np.ptp(b[:, 1]) == pytest.approx(np.ptp(a[:, 1]) + 10.0, abs=0.5)


def test_pele_ate_o_bordo_de_fuga_fecha_a_volta_inteira():
    esq = _asa({"chapeado": {"ate_xc": 1.0, "espessura": 0.0015}, "nervuras": {"y": [0.3, 0.6]}})
    r = PL.faixas(esq, "asa", modo="envolvente")
    assert r["faixas"][0]["pecas"][0]["largura_mm"] > 400.0
    assert not math.isnan(r["faixas"][0]["deformacao_max_pct"])


def test_dxf_tem_camadas_e_espelho():
    esq = _asa({"chapeado": {"ate_xc": 0.3, "espessura": 0.0015}, "nervuras": {"y": [0.3, 0.6]}})
    conj = PL.faixas(esq, "asa")
    org = PL.organiza(conj)
    texto = PL.dxf(conj, org)
    ent = DXF.le(texto)
    camadas = {e["camada"] for _, e in ent}
    assert {"CORTE", "MARCAS", "GRAVACAO", "FOLHA"} <= camadas
    n_cortes = sum(1 for _, e in ent if e["camada"] == "CORTE")
    assert n_cortes == sum(f["quantidade"] * len(f["pecas"]) for f in conj["faixas"])


def test_fronteira_planificacao_do_biplano():
    esq = G.abre_exemplo("biplano/biplano_a.json")
    r = AN.planificacao({"esquema": esq, "asa": "asa_inferior"})
    assert "erro" not in r
    assert r["resumo"]["ok"] > 10 and sum(r["resumo"].values()) == len(r["faixas"])
    assert r["dxf"].startswith("0") or "SECTION" in r["dxf"]
    assert len(r["chapas"]) == sum(f["quantidade"] * len(f["pecas"]) for f in r["faixas"])
    assert AN.planificacao({"esquema": esq, "asa": "asa_inferior", "modo": "xx"}).get("erro")
    assert AN.planificacao({"esquema": {"nome": "x", "elementos": []}}).get("erro")


def test_cortes_manuais_em_y_e_modo_por_faixa():
    esq = G.abre_exemplo("biplano/biplano_a.json")
    r = AN.planificacao({"esquema": esq, "asa": "asa_inferior", "cortes_y_mm": [200, 500, 900]})
    assert "erro" not in r
    ys = sorted({round(f["y0_m"], 3) for f in r["faixas"]} | {round(f["y1_m"], 3) for f in r["faixas"]})
    assert 0.2 in ys and 0.5 in ys and 0.9 in ys and -0.2 in ys
    chave = next(f["chave"] for f in r["faixas"] if abs(f["y0_m"] - 0.5) < 1e-6)
    r2 = AN.planificacao({"esquema": esq, "asa": "asa_inferior", "cortes_y_mm": [200, 500, 900], "modos": {chave: "separado"}})
    f = next(f for f in r2["faixas"] if f["chave"] == chave)
    assert f["modo"] == "separado" and len(f["pecas"]) == 2
    assert AN.planificacao({"esquema": esq, "asa": "asa_inferior", "cortes_y_mm": [99999]}).get("erro")
    assert AN.planificacao({"esquema": esq, "asa": "asa_inferior", "cortes_y_mm": [200, 500, 900], "modos": {chave: "xx"}}).get("erro")


def test_mapa_de_triangulos_cobre_so_a_pele_ate_o_limite():
    esq = G.abre_exemplo("biplano/biplano_a.json")
    r = AN.planificacao({"esquema": esq, "asa": "asa_inferior"})
    n = r["mapa"]["n"]
    assert sum(c for _, c in r["mapa"]["rle"]) == n
    usados = {k for k, _ in r["mapa"]["rle"]}
    assert 0 in usados and max(usados) <= len(r["faixas"]) and len(usados) > 10
    com = sum(c for k, c in r["mapa"]["rle"] if k)
    assert 0.1 * n < com < 0.6 * n
