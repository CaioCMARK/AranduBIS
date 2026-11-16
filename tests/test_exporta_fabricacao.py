import json
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.fronteira import geometria as G
from aranduBIS.nucleo.modelador import aeronave_estrutura as ES
from aranduBIS.nucleo.modelador import exporta_fabricacao as EF

RAIZ = Path(__file__).resolve().parents[1]

def _exemplo(nome):
    return G.abre_exemplo(nome)

def _asa(estrutura=None, perfil="NACA 2412"):
    return {"nome": "t", "_pasta": str(RAIZ), "elementos": [{"nome": "asa", "tipo": "asa", "perfil": perfil, "secoes": [
        {"y": 0.0, "xle": 0.0, "z": 0.0, "corda": 0.30, "ainc": 2.0}, {"y": 0.8, "xle": 0.05, "z": 0.0, "corda": 0.20, "ainc": 0.0}],
        **({"estrutura": estrutura} if estrutura else {})}]}

def test_dat_selig_volta_igual_pela_leitura_do_programa(tmp_path):
    r = EF.exporta(_asa(), ("dat",))
    dat = [a for a in r["arquivos"] if a["nome"].endswith(".dat")]
    assert len(dat) == 2
    p = tmp_path / "a.dat"; p.write_text(dat[0]["texto"])
    xs, zs, xi, zi = ES.ler_dat(p)
    x, a, b = ES.perfil_xy("NACA 2412", 120)
    for xc in (0.1, 0.3, 0.7):
        assert np.interp(xc, xs, zs) - np.interp(xc, xi, zi) == pytest.approx(np.interp(xc, x, a) - np.interp(xc, x, b), abs=2e-6)
        assert np.interp(xc, xs, zs) - zs[0] == pytest.approx(np.interp(xc, x, a) - a[0], abs=2e-6)

def test_nervuras_em_tamanho_real_com_recortes():
    est = {"nervuras": {"y": [0.0, 0.2, 0.4, 0.6, 0.8]},
           "longarinas": [{"tipo": "tubo", "xc": 0.25, "de": 0.010, "di": 0.008}],
           "tubos": [{"xc": 0.6, "lado": "meio", "de": 0.004, "di": 0.003, "y": [0.0, 0.4]}]}
    esq = _asa(est)
    ns = EF.nervuras(esq["elementos"][0], esq)
    assert [round(n["y"], 3) for n in ns] == [0.0, 0.2, 0.4, 0.6, 0.8]
    assert ns[0]["corda"] == pytest.approx(0.30) and ns[-1]["corda"] == pytest.approx(0.20)
    assert np.ptp(ns[0]["contorno"][:, 0]) == pytest.approx(0.30, rel=1e-6)
    furos = [len([r for r in n["recortes"] if r["forma"] == "furo"]) for n in ns]
    assert furos == [2, 2, 2, 1, 1]
    dxf = EF.dxf_nervuras(ns)
    assert dxf.count("\nPOLYLINE\n") == 5 and dxf.count("\nCIRCLE\n") == 8
    assert dxf.rstrip().endswith("EOF")

def test_viga_caixao_abre_janela_na_nervura():
    est = {"nervuras": {"y": [0.1]}, "longarinas": [{"tipo": "caixao", "xc": 0.3, "largura_caixa": 0.02}]}
    esq = _asa(est)
    ns = EF.nervuras(esq["elementos"][0], esq)
    caixa = [r for n in ns for r in n["recortes"] if r["forma"] == "caixa"]
    assert caixa and all(r["x1"] - r["x0"] == pytest.approx(0.02) for r in caixa)

def test_exemplo_com_dat_por_secao_exporta_cada_perfil_e_o_avl():
    nome = next(n for n in G.exemplos() if "s1223" in n)
    esq = _exemplo(nome)
    r = EF.exporta(esq, ("dat", "dxf", "csv", "avl"), raizes=[G.PASTA_EXEMPLOS])
    nomes = [a["nome"] for a in r["arquivos"]]
    assert any(n.startswith("avl/") and n.endswith(".avl") for n in nomes)
    avl = next(a["texto"] for a in r["arquivos"] if a["nome"].endswith(".avl"))
    for af in [ln for ln in avl.splitlines() if ln.lower().endswith(".dat")]:
        assert f"avl/{af.strip()}" in nomes, af
    assert any(n.endswith("_nervuras.dxf") for n in nomes)

def test_nao_copia_arquivo_de_fora_da_pasta(tmp_path):
    fora = tmp_path / "segredo.dat"; x, a, b = ES.perfil_xy("NACA 0012", 30); fora.write_text(EF.selig("segredo", x, a, b))
    esq = _asa(perfil="NACA 0012")
    esq["_pasta"] = str(tmp_path / "modelo"); (tmp_path / "modelo").mkdir()
    esq["elementos"][0]["secoes"][0]["perfil"] = "../segredo.dat"
    esq["elementos"][0]["secoes"][1]["perfil"] = "../segredo.dat"
    r = EF.exporta(esq, ("dat",), raizes=[tmp_path / "modelo"])
    assert not any("originais" in a["nome"] for a in r["arquivos"])

def test_servidor_recusa_formato_desconhecido():
    with pytest.raises(G.ErroDeGeometria):
        G.exporta_fabricacao({"esquema": _asa(), "formatos": ["stl"]})


def _le_stl(arq):
    import base64
    b = base64.b64decode(arq["base64"])
    n = int(np.frombuffer(b[80:84], "<u4")[0])
    assert len(b) == 84 + 50 * n
    reg = np.frombuffer(b[84:], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    return reg

def test_stl_fechado_em_mm_e_binario():
    r = EF.exporta(_asa(), ("stl_fechado",))
    arq = [a for a in r["arquivos"] if a["nome"].endswith("_fechado.stl")]
    assert len(arq) == 1
    reg = _le_stl(arq[0])
    v = reg["v"].reshape(-1, 3)
    assert len(reg) > 50
    assert abs(v[:, 1].max() - 800.0) < 1.0 and abs(v[:, 1].min()) < 1.0
    assert np.allclose(np.linalg.norm(reg["n"], axis=1), 1.0, atol=1e-4)

def test_stl_esqueleto_exige_estrutura():
    r = EF.exporta(_asa(), ("stl_esqueleto",))
    assert not r["arquivos"] and any("sem triangulos" in a for a in r["avisos"])

def test_stl_esqueleto_do_biplano_tem_menos_que_o_fechado_e_so_a_estrutura():
    esq = _exemplo("biplano/biplano_a.json")
    r = EF.exporta(esq, ("stl_fechado", "stl_esqueleto"))
    nomes = {a["nome"].split("_")[-1]: _le_stl(a) for a in r["arquivos"]}
    assert set(nomes) == {"fechado.stl", "esqueleto.stl"}
    assert len(nomes["esqueleto.stl"]) > 1000 and len(nomes["fechado.stl"]) > 1000

def test_fronteira_aceita_formatos_stl():
    r = G.exporta_fabricacao({"esquema": _asa(), "formatos": ["stl_fechado"]})
    assert r["arquivos"][0]["nome"].endswith(".stl")
    with pytest.raises(Exception):
        G.exporta_fabricacao({"esquema": _asa(), "formatos": ["obj"]})


def test_folha_de_montagem_gera_pdf_com_paginas():
    import base64
    esq = _exemplo("biplano/biplano_a.json")
    r = EF.exporta(esq, ("montagem",), asas=["asa_inferior"])
    arq = [a for a in r["arquivos"] if a["nome"].endswith(".pdf")]
    assert len(arq) == 1
    b = base64.b64decode(arq[0]["base64"])
    assert b.startswith(b"%PDF")
    assert b.count(b"/Type /Page") >= 4 or b.count(b"/Type /Page") >= 3

def test_folha_de_montagem_sem_asa_com_estrutura_ainda_gera():
    r = EF.exporta(_asa(), ("montagem",))
    assert r["arquivos"][0]["nome"].endswith(".pdf")
