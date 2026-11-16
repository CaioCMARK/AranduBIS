import copy
import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.nucleo.modelador import aeronave_estrutura as ES
from aranduBIS.nucleo.modelador import aeronave_geometria as AG
from aranduBIS.nucleo.modelador import aeronave_importa as IM

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DAT = RAIZ / "cases" / "geometria" / "generico"

def _esquema(**el_extra):
    el = {"nome": "asa", "tipo": "asa", "n_perfil": 60,
          "secoes": [{"y": -1.0, "xle": 0.0, "zle": 0.0, "corda": 0.30, "ainc": 0.0},
                     {"y": 0.0, "xle": 0.0, "zle": 0.0, "corda": 0.30, "ainc": 0.0},
                     {"y": 1.0, "xle": 0.0, "zle": 0.0, "corda": 0.30, "ainc": 0.0}]}
    el.update(el_extra)
    return {"versao": 1, "nome": "teste", "unidade": "m", "referencia": {"Sref": 0.6, "Cref": 0.3, "Bref": 2.0},
            "elementos": [el], "_pasta": str(PASTA_DAT)}

def _secao_central(esq):
    A = AG.constroi(esq)
    idx = [i for i, z in enumerate(A.zonas) if z.startswith("asa")]
    ids = np.unique(A.T[np.isin(A.zona, idx)])
    P = A.V[ids]
    S = P[np.isclose(P[:, 1], 0.0, atol=1e-9)][:, [0, 2]]
    i0, i1 = np.argmin(S[:, 0]), np.argmax(S[:, 0])
    v = S[i1] - S[i0]
    c, th = np.hypot(*v), np.arctan2(v[1], v[0])
    d = S - S[i0]
    x = (np.cos(-th) * d[:, 0] - np.sin(-th) * d[:, 1]) / c
    z = (np.sin(-th) * d[:, 0] + np.cos(-th) * d[:, 1]) / c
    return c, x, z

def _espessura_e_camber(x, z):
    esp, cam = [], []
    for b0, b1 in zip(np.linspace(0.02, 0.98, 25)[:-1], np.linspace(0.02, 0.98, 25)[1:]):
        m = (x >= b0) & (x < b1)
        if m.sum() >= 2:
            esp.append(z[m].max() - z[m].min()); cam.append(0.5 * (z[m].max() + z[m].min()))
    return max(esp), max(cam)

def test_naca4412_da_malha_confere_com_o_analitico():
    c, x, z = _secao_central(_esquema(perfil="NACA 4412"))
    assert c == pytest.approx(0.30, rel=1e-3)
    t, f = _espessura_e_camber(x, z)
    assert t == pytest.approx(0.12, abs=0.004) and f == pytest.approx(0.04, abs=0.003)

@pytest.mark.parametrize("campo", ["perfil", "arquivo"])
def test_perfil_dat_no_elemento_nao_e_lido_como_naca(campo):
    c, x, z = _secao_central(_esquema(**{campo: "S1223.dat"}))
    t, f = _espessura_e_camber(x, z)
    assert 0.115 < t < 0.135 and f > 0.075

def test_dat_ausente_da_erro_claro_em_vez_de_cair_em_naca():
    with pytest.raises(FileNotFoundError, match="NAOEXISTE"):
        AG.constroi(_esquema(perfil="NAOEXISTE.dat"))

def test_cada_secao_pode_ter_o_seu_perfil():
    esq = _esquema()
    esq["elementos"][0]["secoes"][1]["perfil"] = "S1223.dat"
    for i in (0, 2):
        esq["elementos"][0]["secoes"][i]["perfil"] = "NACA 0012"
    c, x, z = _secao_central(esq)
    t, f = _espessura_e_camber(x, z)
    assert f > 0.075

def test_perfil_reamostrado_pelo_modelador_confere_com_o_arquivo():
    x, zs, zi = ES.perfil_xy("S1223.dat", 80, str(PASTA_DAT))
    xs, zs0, xi, zi0 = ES.ler_dat(PASTA_DAT / "S1223.dat")
    assert np.max(np.abs(zs - np.interp(x, xs, zs0))) < 2e-3 and np.max(np.abs(zi - np.interp(x, xi, zi0))) < 2e-3

def test_avl_leva_o_perfil_dat_e_o_naca_sem_espaco():
    for perfil, esperado in (("S1223.dat", "AFILE\nS1223.dat"), ("NACA 4412", "NACA\n4412"), ("naca4412", "NACA\n4412")):
        r = IM.avl_exporta(_esquema(perfil=perfil))
        assert esperado in r["texto"] and not r["avisos"]

def test_avl_avisa_quando_nao_ha_perfil_que_ele_entenda():
    r = IM.avl_exporta(_esquema(perfil="NACA 23012"))
    assert "NACA\n" not in r["texto"] and any("placa plana" in a for a in r["avisos"])
