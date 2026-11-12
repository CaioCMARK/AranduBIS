import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import flutter as FL
from aranduBIS.nucleo.estrutura import massa_asa as MA

RAIZ = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_2026.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

@pytest.fixture(scope="module")
def base(biplano):
    return FL.dados_de_vibracao(biplano, "asa_inferior"), FL.itens_de_massa(biplano)

def _caixa(x0, x1, y0, y1, z0, z1):
    V = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], float)
    idx = lambda x, y, z: x * 4 + y * 2 + z
    quads = [(0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0), (1, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1), (0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1), (0, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0),
             (0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0), (0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1)]
    T = []
    for q in quads:
        a, b, c, d = (idx(*q[i:i + 3]) for i in (0, 3, 6, 9))
        T += [[a, b, c], [a, c, d]]
    T = np.array(T)
    v = np.einsum("ij,ij->i", V[T[:, 0]], np.cross(V[T[:, 1]], V[T[:, 2]])).sum() / 6
    if v < 0:
        T = T[:, ::-1]
    return V, T

def test_fatiamento_de_um_prisma_da_volume_e_momentos_exatos():
    V, T = _caixa(0.1, 0.3, -0.5, 0.5, 0.0, 0.04)
    Ys = np.array([-0.5, -0.2, 0.0, 0.3, 0.5])
    m = MA._momentos_acumulados(V, T, Ys)
    for k, Y in enumerate(Ys):
        vol = 0.2 * 0.04 * (Y + 0.5)
        assert m[k, 0] == pytest.approx(vol, abs=1e-12)
        assert m[k, 1] == pytest.approx(vol * 0.2, abs=1e-12)
        assert m[k, 3] == pytest.approx(vol * (0.2 ** 2 + 0.2 ** 2 / 12), abs=1e-12)
        assert m[k, 4] == pytest.approx(vol * (0.02 ** 2 + 0.04 ** 2 / 12), abs=1e-12)

def test_fatia_do_prisma_em_y_nao_depende_de_onde_cai_a_aresta():
    V, T = _caixa(0.0, 0.1, 0.0, 1.0, 0.0, 0.1)
    a = MA._momentos_acumulados(V, T, np.array([0.0, 0.333, 1.0]))
    assert np.diff(a[:, 0]) == pytest.approx([0.00333, 0.00667], abs=1e-9)

def test_sem_adicionais_a_massa_fecha_com_o_modelo(biplano, base):
    dv, itens = base
    r = MA.perfil_de_massa(biplano, "asa_inferior", dv["y"], dv["an"]["ea_c"], itens)
    esperado = sum(q["massa"] for q in itens if q["nome"].startswith("asa_inferior.")) / 2
    assert r["massa_kg"] == pytest.approx(esperado, rel=1e-6)
    assert np.trapezoid(r["m_lin"], r["y"]) == pytest.approx(esperado, rel=0.02)
    assert sum(c["massa_kg"] for c in r["categorias"]) == pytest.approx(esperado, rel=1e-6)
    assert {"nervuras", "longarinas", "tubos", "chapeado"} <= {c["nome"] for c in r["categorias"]}

def test_servo_na_ponta_pesa_na_ponta_e_leva_o_cg_para_fora(biplano, base):
    dv, itens = base
    r0 = MA.perfil_de_massa(biplano, "asa_inferior", dv["y"], dv["an"]["ea_c"], itens)
    r1 = MA.perfil_de_massa(biplano, "asa_inferior", dv["y"], dv["an"]["ea_c"], itens, [{"nome": "lastro", "massa_kg": 0.05, "y_m": 1.0, "x_c": 0.7}])
    assert r1["massa_kg"] == pytest.approx(r0["massa_kg"] + 0.05)
    assert r1["y_cg_m"] > r0["y_cg_m"]
    assert r1["x_cg_c"] > r0["x_cg_c"]
    i = int(np.argmin(abs(np.array(r1["y"]) - 1.0)))
    assert r1["m_lin"][i] > r0["m_lin"][i] + 0.5 * 0.05 / 0.1

def test_massa_medida_fecha_o_total_e_escala_so_a_estrutura(biplano, base):
    dv, itens = base
    ad = [{"nome": "servo", "massa_kg": 0.03, "y_m": 0.8, "x_c": 0.6}]
    r = MA.perfil_de_massa(biplano, "asa_inferior", dv["y"], dv["an"]["ea_c"], itens, ad, massa_medida_kg=0.25, x_cg_medido_c=0.30, y_cg_medido_m=0.5)
    assert r["massa_kg"] == pytest.approx(0.25)
    assert r["escala_estrutura"] == pytest.approx((0.25 - 0.03) / r["massa_estrutura_calculada_kg"])
    assert r["validacao"]["massa"]["medido"] == 0.25 and "x_cg_c" in r["validacao"] and "y_cg_m" in r["validacao"]
    assert any("estrutura do modelo teve de valer" in a for a in r["avisos"])
    with pytest.raises(ValueError):
        MA.perfil_de_massa(biplano, "asa_inferior", dv["y"], dv["an"]["ea_c"], itens, ad, massa_medida_kg=0.03)

def test_filme_por_gramatura_soma_area_de_pele_vezes_gramatura(biplano, base):
    dv, itens = base
    r = MA.perfil_de_massa(biplano, "asa_inferior", dv["y"], dv["an"]["ea_c"], itens, [{"nome": "filme", "gramatura_g_m2": 30, "y_m": 0.0}])
    m = r["adicionais"][0]["massa_kg"]
    area_aprox = 2 * 1.2 * 0.3
    assert 0.5 * area_aprox * 0.03 < m < 1.6 * area_aprox * 0.03

def test_massa_na_ponta_baixa_a_primeira_frequencia_mais_que_na_raiz(biplano):
    f = []
    for y_m in (0.1, 1.0):
        d = FL.dados_de_vibracao(biplano, "asa_inferior", massa_real={"usar": True, "adicionais": [{"nome": "x", "massa_kg": 0.08, "y_m": y_m, "x_c": 0.3}]})
        c = d["c"]
        xa = d["x_alfa_c"] * c
        v = FL.modos_de_vibracao(d["y"], d["EI"], d["GJ"], d["m_lin"], d["m_lin"] * xa, d["m_lin"] * ((d["r_giro_c"] * c) ** 2 + xa ** 2), 6)
        f.append(min(v["f_hz"]))
    assert f[1] < f[0]

def test_adicionais_por_asa_so_valem_na_asa_pedida(biplano):
    mr = {"usar": True, "adicionais": [{"asa": "asa_superior", "nome": "lastro", "massa_kg": 0.1, "y_m": 1.0}]}
    a = FL.dados_de_vibracao(biplano, "asa_inferior", massa_real=mr)
    b = FL.dados_de_vibracao(biplano, "asa_superior", massa_real=mr)
    assert b["M"] - a["M"] == pytest.approx(0.1, abs=0.03)
    assert a["perfil_massa"]["massa_adicionais_kg"] == 0.0 and b["perfil_massa"]["massa_adicionais_kg"] == pytest.approx(0.1)

def test_api_massa_asa_e_flutter_com_massa_real(biplano):
    mr = {"usar": True, "adicionais": [{"nome": "servo", "massa_kg": 0.02, "y_m": 0.9, "x_c": 0.6}], "medidas": {"asa_inferior": {"massa_medida_kg": 0.2}}}
    r = AN.massa_asa({"esquema": biplano, "massa_real": mr})
    assert "erro" not in r
    a = next(x for x in r["asas"] if x["nome"] == "asa_inferior")
    assert a["massa_kg"] == pytest.approx(0.2) and len(a["f_hz"]) == 6 and len(a["f_hz_hipotese_antiga"]) == 6
    f = AN.flutter({"esquema": biplano, "massa_real": mr, "V_max_rel": 1.5})
    assert "erro" not in f
    assert next(x for x in f["asas"] if x["nome"] == "asa_inferior")["origem_massa"].startswith("distribuicao por estacao")
    assert next(x for x in f["asas"] if x["nome"] == "asa_inferior")["f_vacuo_hz_massa_uniforme"]
    assert "erro" in AN.massa_asa({"esquema": biplano, "massa_real": {"usar": True, "adicionais": [{"nome": "x", "massa_kg": "a"}]}})
