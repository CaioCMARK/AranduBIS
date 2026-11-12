import json
import math
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.estrutura import pouso_dinamico as PD
from aranduBIS.nucleo.estrutura import trem as TR

RAIZ = Path(__file__).resolve().parents[1]
G0 = PD.G0

@pytest.fixture(scope="module")
def biplano():
    d = json.loads((RAIZ / "cases/geometria/biplano/biplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(RAIZ / "cases/geometria/biplano")
    return d

def _simetrico(k=20000.0):
    rodas = {"principal": {"x": -0.2, "z": -0.3, "R": 0.04, "n": 1, "nomes": ["a"]}, "bequilha": {"x": 0.2, "z": -0.3, "R": 0.04, "n": 1, "nomes": ["b"]}}
    p = {"m": 10.0, "Iyy": 0.5, "S": 1.0, "c": 0.3, "rho": 1.1, "CLa": 0.0, "CLmax": 1.0, "CL0": 0.0, "alfa0": 0.0, "Cma": 0.0, "Cmq": 0.0, "CD": 0.0, "mu": 0.0,
         "trens": {"principal": {"k_pneu": k, "k_perna": 1e12, "zeta": 0.0, "curso": 0.0}, "bequilha": {"k_pneu": k, "k_perna": 1e12, "zeta": 0.0, "curso": 0.0}}}
    return p, rodas

def test_tres_pontos_da_altura_e_arfagem_com_os_fundos_no_solo():
    h, th = PD.atitude_de_tres_pontos({"principal": {"x": -0.07, "z": -0.32, "R": 0.046}, "bequilha": {"x": 0.34, "z": -0.34, "R": 0.03}})
    for r in ({"x": -0.07, "z": -0.32, "R": 0.046}, {"x": 0.34, "z": -0.34, "R": 0.03}):
        assert h + r["x"] * math.sin(th) + (r["z"] - r["R"]) * math.cos(th) == pytest.approx(0.0, abs=1e-9)

def test_queda_simetrica_sem_amortecimento_pico_igual_a_v_raiz_de_k_m():
    p, rodas = _simetrico()
    v = 0.8
    r = PD.simula(p, rodas, PD._h0_pouso(rodas, 0.0), 0.0, -v, 10.0, 0.5, dt=2e-4, passo_saida=5)
    k_total = 2 * 20000.0
    esperado = v * math.sqrt(k_total * p["m"]) + p["m"] * G0
    assert r["pico"]["N_total"] == pytest.approx(esperado, rel=0.06)
    assert r["pico"]["N_principal"] == pytest.approx(r["pico"]["N_bequilha"], rel=0.02)
    assert abs(max(r["theta_graus"], key=abs)) < 0.05

def test_energia_conservada_sem_amortecimento_ate_sair_do_chao():
    p, rodas = _simetrico()
    r = PD.simula(p, rodas, PD._h0_pouso(rodas, 0.0), 0.0, -1.0, 10.0, 0.6, dt=2e-4, passo_saida=5)
    t = np.array(r["t"]); i_sai = np.flatnonzero((np.array(r["N_principal"]) + np.array(r["N_bequilha"]) == 0) & (t > 0.05))[0]
    assert abs(r["vz"][i_sai]) == pytest.approx(1.0, rel=0.03)

def test_amortecimento_reduz_o_pico_e_o_quique():
    p, rodas = _simetrico()
    base = PD.simula(p, rodas, PD._h0_pouso(rodas, 0.0), 0.0, -1.0, 10.0, 0.6, dt=2e-4, passo_saida=5)
    for g in p["trens"].values():
        g["zeta"] = 0.5
    amort = PD.simula(p, rodas, PD._h0_pouso(rodas, 0.0), 0.0, -1.0, 10.0, 0.6, dt=2e-4, passo_saida=5)
    assert amort["pico"]["N_total"] < base["pico"]["N_total"]
    assert PD.quicadas(amort)["n"] <= PD.quicadas(base)["n"]

def test_pico_cresce_com_a_razao_de_descida():
    p, rodas = _simetrico()
    f = [PD.simula(p, rodas, PD._h0_pouso(rodas, 0.0), 0.0, -v, 10.0, 0.5, dt=5e-4, passo_saida=5)["pico"]["N_total"] for v in (0.5, 1.0, 2.0)]
    assert f[0] < f[1] < f[2]
    assert (f[2] - 10 * G0) > 1.8 * (f[1] - 10 * G0) * 0.9

def test_perfis_de_pista():
    z, dz = PD.perfil_de_pista("lombada", 0.02, 0.4, 1.0)
    assert z(0.9) == 0 and z(1.2) == pytest.approx(0.02) and z(1.5) == 0
    z, _ = PD.perfil_de_pista("degrau", 0.03, 0.1, 1.0)
    assert z(0.5) == 0 and z(2.0) == pytest.approx(0.03)
    z, _ = PD.perfil_de_pista("irregular", 0.005, 0.3, 0.0)
    xs = np.linspace(2, 200, 4000)
    assert np.std([z(x) for x in xs]) == pytest.approx(0.005, rel=0.35)
    with pytest.raises(ValueError):
        PD.perfil_de_pista("lunar", 1, 1, 0)

def test_taxi_em_pista_plana_volta_a_distribuicao_estatica(biplano):
    r = PD.analisa(biplano, massa_kg=11.0, S=0.8, c_med=0.34, CL_alpha=4.2, Cm_alpha=-0.8, CL_max=1.5, Vs=12.9, perfil_pista="plana", razoes=(0.5, 1.0), mu_rolamento=0.0, CD=0.0)
    W = r["peso_N"]
    t = np.array(r["casos"]["taxi"]["t"])
    N = np.array(r["casos"]["taxi"]["N_principal"])[t > 1.2]
    Nb = np.array(r["casos"]["taxi"]["N_bequilha"])[t > 1.2]
    assert N.mean() + Nb.mean() == pytest.approx(W, rel=0.02)
    th = math.radians(np.mean(np.array(r["casos"]["taxi"]["theta_graus"])[t > 1.2]))
    rx = {k: r["rodas"][k]["x"] * math.cos(th) - r["rodas"][k]["z"] * math.sin(th) for k in ("principal", "bequilha")}
    assert Nb.mean() / W == pytest.approx(-rx["principal"] / (rx["bequilha"] - rx["principal"]), rel=0.03)

def test_pouso_com_rigidez_da_perna_da_trelica_e_ligacao_com_o_fe(biplano):
    r = PD.analisa(biplano, massa_kg=11.0, S=0.8, c_med=0.34, CL_alpha=4.2, Cm_alpha=-0.8, CL_max=1.5, Vs=12.9, razoes=(0.5, 1.0, 2.0), aplica_fe=True)
    assert r["rigidez_perna_N_m"]["origem"].startswith("treli")
    assert 5e3 < r["rigidez_perna_N_m"]["principal"] < 5e5
    for k in ("pouso_3_pontos", "pouso_2_pontos", "taxi"):
        assert r["casos"][k]["pico"]["N_principal"] > 0
    v = r["varredura"]["pouso_3_pontos"]["fator_total"]
    assert v[0] < v[1] < v[2]
    nomes = [c["caso"] for c in r["fe"]["casos"]]
    assert len(nomes) == 6 and all("_dinamico_" in n for n in nomes)
    assert r["fe"]["critico"]["margem"] == min(c["margem"] for c in r["fe"]["casos"])
    c = r["fe"]["casos"][0]
    assert sum(w["R"] for k, w in c["rodas"].items() if k != "bequilha") == pytest.approx(r["casos"]["pouso_3_pontos"]["pico"]["N_principal"], rel=1e-6)

def test_casos_extra_no_trem_nao_mudam_os_casos_de_sempre(biplano):
    a = TR.analisa(biplano, massa_kg=11.0)
    b = TR.analisa(biplano, massa_kg=11.0, casos_extra=[{"nome": "x", "descricao": "d", "Rm": 400.0, "Rn": 100.0, "mu": 0.0}])
    assert [c["caso"] for c in b["casos"]] == [c["caso"] for c in a["casos"]] + ["x"]
    assert b["casos"][0]["margem"] == pytest.approx(a["casos"][0]["margem"])
    assert b["casos"][3]["rodas"]["bequilha"]["R"] == 100.0

def test_api_pouso_dinamico(biplano):
    r = AN.pouso_dinamico({"esquema": biplano, "CL_max": 1.5, "massa_kg": 11.0, "razoes": [0.5], "aplica_fe": False})
    assert "erro" not in r, r
    assert set(r["casos"]) == {"pouso_3_pontos", "pouso_2_pontos", "taxi"}
    assert r["ref_aero"]["S"] > 0 and r["Vs"] > 0
    r2 = AN.pouso_dinamico({"esquema": biplano, "CL_max": 1.5, "massa_kg": 11.0, "vel_descida": 2.0})
    assert r2["casos"]["pouso_3_pontos"]["pico"]["N_principal"] > r["casos"]["pouso_3_pontos"]["pico"]["N_principal"]
    assert "erro" in AN.pouso_dinamico({"esquema": biplano, "CL_max": 1.5, "vel_descida": -1})
