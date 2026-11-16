import numpy as np
import pytest

from aranduBIS.fronteira import analise as AN
from aranduBIS.nucleo.modelador.secoes import secoes_da_asa

def esquema(**el):
    asa = {"nome": "asa", "tipo": "asa", "perfil": "NACA 4412", "n_perfil": 30,
           "secoes": [{"y": -0.5, "xle": 0.0, "zle": 0.0, "corda": 0.3, "ainc": 2.0}, {"y": 0.0, "xle": 0.02, "zle": 0.01, "corda": 0.4, "ainc": 4.0},
                      {"y": 0.5, "xle": 0.0, "zle": 0.0, "corda": 0.3, "ainc": 2.0}],
           "estrutura": {"nervuras": {"y": [0.25], "espessura": 0.003}, "longarinas": [{"x": 0.08, "largura": 0.004, "y": [-0.5, 0.0]}],
                         "tubos": [{"x": 0.08, "lado": "extradorso", "de": 0.004, "y": [0.0, 0.5]}], "chapeado": {"ate_xc": 0.2, "espessura": 0.001}},
           "controles": [{"nome": "aileron", "y": [0.3, 0.5], "corda": 0.08, "deflexao": 0.0, "modo": "anti", "charneira": "extradorso"}]}
    asa.update(el)
    return {"versao": 1, "nome": "t", "elementos": [asa]}

def test_uma_entrada_por_secao_com_os_dados_do_esquema():
    r = secoes_da_asa(esquema(), "asa")
    assert [s["y"] for s in r["secoes"]] == [-0.5, 0.0, 0.5]
    s = r["secoes"][1]
    assert (s["xle"], s["zle"], s["corda"], s["ainc"]) == (0.02, 0.01, 0.4, 4.0)
    assert len(s["anel"]) == len(s["anel3d"]) == 2 * 30 - 2

def test_perfil_no_espaco_com_corda_e_incidencia():
    s = secoes_da_asa(esquema(), "asa")["secoes"][1]
    A, P = np.array(s["anel"]), np.array(s["anel3d"])
    i_le, i_te = int(np.argmin(A[:, 0])), int(np.argmax(A[:, 0]))
    a = np.radians(4.0)
    assert P[i_le] == pytest.approx([0.02 + 0.4 * (A[i_le, 0] * np.cos(a) + A[i_le, 1] * np.sin(a)), 0.0, 0.01 + 0.4 * (-A[i_le, 0] * np.sin(a) + A[i_le, 1] * np.cos(a))], abs=1e-4)
    assert P[i_te][0] - P[i_le][0] == pytest.approx(0.4 * np.cos(a), abs=2e-3)
    assert P[i_le][2] - P[i_te][2] == pytest.approx(0.4 * np.sin(a), abs=2e-3)
    assert all(abs(p[1]) < 1e-9 for p in P)

def test_estrutura_e_nervura_so_onde_valem():
    r = secoes_da_asa(esquema(), "asa")["secoes"]
    assert [len(s["longarinas"]) for s in r] == [1, 1, 0] and [len(s["tubos"]) for s in r] == [0, 1, 1]
    assert r[1]["longarinas"][0]["x_mm"] == pytest.approx(80.0) and r[2]["tubos"][0]["d_mm"] == pytest.approx(4.0)
    assert [s["nervura"] for s in r] == [True, False, True]
    assert r[2]["controles"] == ["aileron"] and r[0]["controles"] == ["aileron"] and r[1]["controles"] == []

def test_chapeado_e_posicao_do_elemento():
    r = secoes_da_asa(esquema(posicao=[1.0, 0.0, 0.5]), "asa")
    assert r["chapeado_ate_xc"] == 0.2 and r["chapeado_mm"] == pytest.approx(1.0)
    p0 = np.array(secoes_da_asa(esquema(), "asa")["secoes"][1]["anel3d"])
    p1 = np.array(r["secoes"][1]["anel3d"])
    assert p1 - p0 == pytest.approx(np.tile([1.0, 0.0, 0.5], (len(p0), 1)), abs=1e-6)

def test_deriva_rolada_poe_a_envergadura_em_z():
    s = secoes_da_asa(esquema(rolagem=90.0), "asa")["secoes"][2]
    assert max(abs(p[1]) for p in s["anel3d"]) < 0.06 and max(p[2] for p in s["anel3d"]) > 0.49

def test_asa_com_secoes_lineares_e_erros():
    e = esquema()
    e["elementos"][0].pop("secoes")
    e["elementos"][0]["secoes_lineares"] = {"y": [-1, 1], "n": 5, "corda": 0.25}
    r = secoes_da_asa(e, "asa")
    assert len(r["secoes"]) == 5
    with pytest.raises(ValueError):
        secoes_da_asa(esquema(), "outra")

def test_fronteira():
    q = AN.secoes({"esquema": esquema(), "asa": "asa"})
    assert "erro" not in q and len(q["secoes"]) == 3
    assert "erro" in AN.secoes({"esquema": esquema(), "asa": "x"})
    assert "erro" in AN.secoes({"esquema": esquema()})
