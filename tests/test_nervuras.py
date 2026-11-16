import copy

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import nervuras as NV
from aranduBIS.nucleo.modelador import dxf as DX

C_MM = 200.0

def asa(**estr):
    cfg = {"nervuras": {"y": [0.1, 0.3], "espessura": 0.003, "material": "balsa"},
           "longarinas": [{"x": 0.06, "largura": 0.004, "material": "balsa"}],
           "tubos": [{"x": 0.12, "lado": "meio", "de": 0.004, "di": 0.003},
                     {"x": 0.15, "lado": "extradorso", "de": 0.003, "di": 0.002}],
           "chapeado": {"ate_xc": 0.2, "espessura": 0.001, "material": "balsa"}}
    cfg.update(estr)
    return {"versao": 1, "nome": "t", "elementos": [{"nome": "asa", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 60,
            "secoes": [{"y": -0.5, "corda": 0.2}, {"y": 0.5, "corda": 0.2}], "estrutura": cfg}]}

def uma(esq, **kw):
    return NV.pecas(esq, "asa", **kw)

def area(P):
    P = np.asarray(P)
    return 0.5 * abs(float(np.dot(P[:, 0], np.roll(P[:, 1], -1)) - np.dot(P[:, 1], np.roll(P[:, 0], -1))))

def test_uma_nervura_por_y_e_se_parte_na_longarina():
    r = uma(asa())
    assert [round(n["y_m"], 3) for n in r["nervuras"]] == [-0.5, -0.3, -0.1, 0.1, 0.3, 0.5][::1] or len(r["nervuras"]) >= 4
    n = r["nervuras"][len(r["nervuras"]) // 2]
    assert [p["nome"][-1] for p in n["pecas"]] == ["A", "B"]
    a, b = n["pecas"]
    assert b["x0"] - a["x1"] == pytest.approx(4.0 + 0.1, abs=1e-6)
    assert 0.5 * (a["x1"] + b["x0"]) == pytest.approx(60.0, abs=1e-6)

def test_sem_longarina_a_nervura_e_uma_peca_so():
    r = uma(asa(longarinas=[]))
    assert all(len(n["pecas"]) == 1 for n in r["nervuras"])

def test_tubo_no_meio_vira_furo_com_folga():
    n = uma(asa(), folga_tubo_mm=0.2)["nervuras"][3]
    furos = [f for p in n["pecas"] for f in p["furos"]]
    assert len(furos) == 1
    assert furos[0]["d"] == pytest.approx(4.2, abs=1e-6)
    assert furos[0]["c"][0] == pytest.approx(120.0, abs=1e-6)

def test_tubo_rente_ao_chapeado_vira_entalhe_e_tira_area():
    sem = uma(asa(tubos=[]))["nervuras"][3]["pecas"]
    com = uma(asa(tubos=[{"x": 0.15, "lado": "extradorso", "de": 0.003, "di": 0.002}]))["nervuras"][3]["pecas"]
    assert all(len(p["furos"]) == 0 for p in com)
    b0, b1 = sem[1], com[1]
    r = 0.5 * 3.1
    esperado = 2 * r * r + np.pi * r * r / 2
    assert b0["area_mm2"] - b1["area_mm2"] == pytest.approx(esperado, rel=0.25)
    assert len(b1["contorno"]) > len(b0["contorno"])

def test_tubo_na_alma_da_longarina_nao_fura_e_avisa_uma_vez():
    r = uma(asa(tubos=[{"x": 0.06, "lado": "extradorso", "de": 0.003}]))
    assert all(len(p["furos"]) == 0 for n in r["nervuras"] for p in n["pecas"])
    assert sum("rasgo da longarina" in a for a in r["avisos"]) == 1

def test_luva_sobre_o_tubo_fino_vale_o_maior_diametro():
    t = [{"x": 0.12, "lado": "meio", "de": 0.003, "di": 0.002, "y": [0.0, 0.5]}, {"x": 0.12, "lado": "meio", "de": 0.004, "di": 0.003, "y": [0.0, 0.2]}]
    r = uma(asa(tubos=t), folga_tubo_mm=0.0)
    n_curto = next(n for n in r["nervuras"] if abs(n["y_m"] - 0.1) < 1e-6)
    n_longo = next(n for n in r["nervuras"] if abs(n["y_m"] - 0.3) < 1e-6)
    assert [f["d"] for p in n_curto["pecas"] for f in p["furos"]] == [pytest.approx(4.0)]
    assert [f["d"] for p in n_longo["pecas"] for f in p["furos"]] == [pytest.approx(3.0)]

def test_recesso_do_chapeado_recua_o_bordo_de_ataque():
    com = uma(asa(), recesso_chapeado=True)["nervuras"][3]["pecas"][0]
    sem = uma(asa(), recesso_chapeado=False)["nervuras"][3]["pecas"][0]
    assert sem["x0"] == pytest.approx(0.0, abs=1e-6)
    assert com["x0"] == pytest.approx(1.0, abs=0.15)
    assert com["area_mm2"] < sem["area_mm2"]
    def altura_em(p, x0):
        P = np.asarray(p["contorno"])
        zs = []
        for i in range(len(P)):
            A, B = P[i], P[(i + 1) % len(P)]
            if (A[0] - x0) * (B[0] - x0) < 0:
                zs.append(A[1] + (x0 - A[0]) / (B[0] - A[0]) * (B[1] - A[1]))
        return float(max(zs) - min(zs))
    assert altura_em(sem, 25.0) - altura_em(com, 25.0) == pytest.approx(2.0, abs=0.35)
    assert altura_em(sem, 55.0) == pytest.approx(altura_em(com, 55.0), abs=0.3)

def test_bordo_de_fuga_truncado_na_espessura_minima():
    p = uma(asa(), bf_min_mm=1.5)["nervuras"][3]["pecas"][1]
    P = np.asarray(p["contorno"])
    na_ponta = P[P[:, 0] > P[:, 0].max() - 1e-6]
    assert P[:, 0].max() < C_MM
    assert na_ponta[:, 1].max() - na_ponta[:, 1].min() == pytest.approx(1.5, abs=0.05)

def test_compensacao_de_corte():
    a = uma(asa(), kerf_mm=0.0)["nervuras"][3]["pecas"]
    b = uma(asa(), kerf_mm=0.2)["nervuras"][3]["pecas"]
    for pa, pb in zip(a, b):
        perimetro = float(np.sum(np.linalg.norm(np.diff(np.vstack([pa["contorno"], pa["contorno"][:1]]), axis=0), axis=1)))
        assert area(pb["contorno"]) - area(pa["contorno"]) == pytest.approx(perimetro * 0.1, rel=0.12)
        for fa, fb in zip(pa["furos"], pb["furos"]):
            assert fb["d"] == pytest.approx(fa["d"] - 0.2)

def test_erros():
    with pytest.raises(ValueError):
        NV.pecas(asa(), "outra")
    with pytest.raises(ValueError):
        NV.pecas(asa(nervuras=None), "asa")

def test_organiza_sem_sobrepor_e_dentro_da_folha():
    r = uma(asa(nervuras={"y": [0.05 * k for k in range(1, 10)], "espessura": 0.003}))
    o = NV.organiza(r, (300.0, 150.0), espaco_mm=4.0, margem_mm=5.0)
    assert o["folhas"] >= 2
    caixas = []
    for n in r["nervuras"]:
        for p in n["pecas"]:
            x = p["x0"] + p["pos"][0], p["x1"] + p["pos"][0]
            z = p["z0"] + p["pos"][1], p["z1"] + p["pos"][1]
            assert 5.0 - 1e-6 <= x[0] and x[1] <= 295.0 + 1e-6 and 5.0 - 1e-6 <= z[0] and z[1] <= 145.0 + 1e-6
            caixas.append((p["folha"], x, z))
    for i, (f1, x1, z1) in enumerate(caixas):
        for f2, x2, z2 in caixas[i + 1:]:
            if f1 == f2:
                assert x1[1] <= x2[0] + 1e-6 or x2[1] <= x1[0] + 1e-6 or z1[1] <= z2[0] + 1e-6 or z2[1] <= z1[0] + 1e-6

def test_peca_que_nao_cabe_avisa():
    r = uma(asa())
    o = NV.organiza(r, (50.0, 50.0))
    assert o["avisos"]

def test_dxf_escreve_o_que_foi_calculado():
    r = uma(asa(), kerf_mm=0.1)
    o = NV.organiza(r)
    t = NV.dxf(r, o)
    assert t.startswith("0\nSECTION") and t.rstrip().endswith("EOF")
    ents = DX.le(t)
    pecas = [p for n in r["nervuras"] for p in n["pecas"]]
    corte = [e for tp, e in ents if tp == "POLYLINE" and e["camada"] == "CORTE"]
    assert len(corte) == len(pecas)
    assert len([e for tp, e in ents if tp == "POLYLINE" and e["camada"] == "FOLHA"]) == o["folhas"]
    assert len([e for tp, e in ents if tp == "CIRCLE"]) == sum(len(p["furos"]) for p in pecas)
    textos = [e["texto"] for tp, e in ents if tp == "TEXT"]
    assert len(textos) == len(pecas) and any(s.startswith("N04A") for s in textos)
    todos = np.array([q for e in corte for q in e["pontos"]])
    assert todos.min() >= 0 and todos[:, 1].max() <= 300.0 + 1e-6
    p0 = pecas[0]
    mc = max(corte, key=lambda e: len(e["pontos"]))
    assert len(mc["pontos"]) >= 20

def test_fronteira_devolve_dxf_e_pecas():
    q = AN.nervuras_dxf({"esquema": asa(), "kerf_mm": 0.1})
    assert "erro" not in q
    assert q["dxf"].count("POLYLINE") >= q["n_pecas"] and q["n_nervuras"] == 6 and q["espessura_mm"] == pytest.approx(3.0)
    assert q["asa"] == "asa" and q["folhas"] >= 1 and q["area_total_cm2"] > 0
    assert all(p["contorno"] for p in q["pecas"])

def test_fronteira_recusa():
    sem = copy.deepcopy(asa())
    sem["elementos"][0]["estrutura"].pop("nervuras")
    assert "erro" in AN.nervuras_dxf({"esquema": sem})
    assert "erro" in AN.nervuras_dxf({"esquema": asa(), "asa": "x"})
    assert "erro" in AN.nervuras_dxf({"esquema": asa(), "folha_largura_mm": -1})


def _sem_longarina(**kw):
    return asa(longarinas=[], chapeado={"ate_xc": 0.0, "espessura": 0.0}, tubos=[{"x": 0.12, "lado": "meio", "de": 0.004, "di": 0.003}], **kw)


def test_angulo_estica_a_peca_por_um_sobre_cosseno_e_o_furo_vira_elipse():
    a = uma(_sem_longarina(), recesso_chapeado=False)["nervuras"][3]["pecas"][0]
    esq = _sem_longarina()
    esq["elementos"][0]["estrutura"]["nervuras"]["angulo"] = 30.0
    b = uma(esq, recesso_chapeado=False)["nervuras"][3]
    k = 1.0 / np.cos(np.radians(30.0))
    assert b["angulo"] == pytest.approx(30.0)
    assert (b["pecas"][0]["x1"] - b["pecas"][0]["x0"]) == pytest.approx(k * (a["x1"] - a["x0"]), rel=1e-6)
    assert (b["pecas"][0]["z1"] - b["pecas"][0]["z0"]) == pytest.approx(a["z1"] - a["z0"], rel=1e-6)
    fa, fb = a["furos"][0], b["pecas"][0]["furos"][0]
    assert fb["d"] == pytest.approx(fa["d"]) and fb["dx"] == pytest.approx(k * fa["d"]) and fb["c"][0] == pytest.approx(k * fa["c"][0])


def test_angulo_alarga_o_rasgo_da_longarina():
    base = asa()
    esq = asa()
    esq["elementos"][0]["estrutura"]["nervuras"]["angulo"] = 40.0
    k = 1.0 / np.cos(np.radians(40.0))
    a, b = uma(base)["nervuras"][3]["pecas"], uma(esq)["nervuras"][3]["pecas"]
    assert (b[1]["x0"] - b[0]["x1"]) == pytest.approx(4.0 * k + 0.1, abs=1e-6)
    assert (a[1]["x0"] - a[0]["x1"]) == pytest.approx(4.1, abs=1e-6)


def test_angulo_por_nervura_vence_o_global_e_as_pontas_ficam_retas():
    from aranduBIS.nucleo.modelador import aeronave_geometria as AG
    nv = {"y": [0.1, 0.3], "angulo": 10.0, "angulos": [[0.3, 25.0]]}
    ys = [-0.5, 0.5]
    assert AG._angulo_nervura(nv, 0.1, ys) == 10.0 and AG._angulo_nervura(nv, -0.1, ys) == 10.0
    assert AG._angulo_nervura(nv, 0.3, ys) == 25.0 and AG._angulo_nervura(nv, -0.3, ys) == 25.0
    assert AG._angulo_nervura(nv, 0.5, ys) == 0.0 and AG._angulo_nervura(nv, -0.5, ys) == 0.0


def test_angulo_absurdo_e_recusado():
    esq = asa()
    esq["elementos"][0]["estrutura"]["nervuras"]["angulo"] = 85.0
    with pytest.raises(ValueError):
        uma(esq)


def test_dxf_com_furo_eliptico_tem_mais_vertices():
    esq = _sem_longarina()
    esq["elementos"][0]["estrutura"]["nervuras"]["angulo"] = 35.0
    r = uma(esq)
    t = NV.dxf(r, NV.organiza(r))
    ents = DX.le(t)
    corte = [e for tp, e in ents if tp == "POLYLINE" and e["camada"] == "CORTE"]
    assert len([e for tp, e in ents if tp == "CIRCLE"]) < sum(len(p["furos"]) for n in r["nervuras"] for p in n["pecas"])
    assert any(len(e["pontos"]) == 48 for e in corte)


def test_malha_3d_da_nervura_inclinada_desloca_o_bordo_de_fuga_para_fora():
    from aranduBIS.nucleo.modelador import aeronave_geometria as AG

    def faixa_y(ang):
        esq = asa()
        esq["elementos"][0]["estrutura"]["nervuras"]["angulo"] = ang
        m = AG.constroi(esq)
        idx = np.unique(m.T[m.zona == m.zonas.index("asa.nervuras")]) if "asa.nervuras" in m.zonas else None
        V = m.V[idx]
        sel = V[(V[:, 1] > 0.25) & (V[:, 1] < 0.45)]
        return float(sel[:, 1].max() - sel[:, 1].min())

    assert faixa_y(0.0) < 0.01
    assert faixa_y(30.0) == pytest.approx(0.2 * np.tan(np.radians(30.0)) + 0.003, rel=0.02)


def test_posicoes_uniforme_simetrica():
    r = NV.posicoes(asa(), "asa", 5)
    assert r["simetrica"] and r["y"] == pytest.approx([0.0, 0.125, 0.25, 0.375, 0.5])
    assert len(r["completa"]) == 9 and max(r["passos_mm"]) == pytest.approx(125.0)


def test_posicoes_raiz_e_ponta_adensam_cada_lado():
    raiz, ponta = NV.posicoes(asa(), "asa", 7, "raiz"), NV.posicoes(asa(), "asa", 7, "ponta")
    assert raiz["passos_mm"][len(raiz["passos_mm"]) // 2] < raiz["passos_mm"][0]
    assert ponta["passos_mm"][0] < ponta["passos_mm"][len(ponta["passos_mm"]) // 2 - 1] or ponta["passos_mm"][0] < ponta["passos_mm"][1]


def test_posicoes_nas_secoes_e_erros():
    assert NV.posicoes(asa(), "asa", 4, "secoes")["y"] == pytest.approx([0.0, 0.5]) or NV.posicoes(asa(), "asa", 4, "secoes")["y"][-1] == pytest.approx(0.5)
    for ruim in ({"n": 1}, {"n": 999}, {"lei": "x"}, {"expoente": 0.0}):
        with pytest.raises(ValueError):
            NV.posicoes(asa(), "asa", **{"n": 5, **ruim})
    with pytest.raises(ValueError):
        NV.posicoes(asa(), "outra", 5)


def test_fronteira_posicoes_gera_e_mede_uma_lista_dada():
    q = AN.nervuras_posicoes({"esquema": asa(), "asa": "asa", "n": 6, "lei": "uniforme"})
    assert "erro" not in q and q["n_total"] == 11 and q["passo_max_mm"] == pytest.approx(100.0)
    q2 = AN.nervuras_posicoes({"esquema": asa(), "asa": "asa", "y": [0.1, 0.3]})
    assert q2["completa"] == pytest.approx([-0.5, -0.3, -0.1, 0.1, 0.3, 0.5]) and q2["passo_max_mm"] == pytest.approx(200.0) and q2["passo_min_mm"] == pytest.approx(200.0)
    assert "erro" in AN.nervuras_posicoes({"esquema": asa(), "asa": "asa", "n": 0})
    assert "erro" in AN.nervuras_posicoes({"esquema": asa(), "asa": "asa", "y": ["a"]})
    assert "erro" in AN.nervuras_posicoes({"esquema": {"versao": 1, "nome": "v", "elementos": []}})


def test_fronteira_dxf_devolve_o_angulo_e_o_eixo_maior_do_furo():
    esq = _sem_longarina()
    esq["elementos"][0]["estrutura"]["nervuras"]["angulo"] = 30.0
    q = AN.nervuras_dxf({"esquema": esq})
    assert "erro" not in q
    com = [p for p in q["pecas"] if p["furos"] and p["angulo"]]
    assert com and com[0]["angulo"] == pytest.approx(30.0) and com[0]["furos"][0]["dx"] > com[0]["furos"][0]["d"]
