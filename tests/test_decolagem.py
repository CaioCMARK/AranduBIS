import math
import sys
from pathlib import Path

import numpy as np
import pytest

from aranduBIS.nucleo import decolagem as D

AE = D.Aeronave(S=1.4, CL_max=2.0, CL_corrida=0.5, CD_corrida=0.06,
                tracao_v=(0.0, 30.0), tracao_n=(60.0, 24.0))
COND = D.Condicoes()

def test_densidade_do_ar_bate_com_a_atmosfera_padrao():
    assert D.densidade_do_ar(0) == pytest.approx(1.225)
    assert D.densidade_do_ar(1330) == pytest.approx(1.0761, abs=2e-3)

def test_leve_passa_e_pesado_nao():
    assert D.simular(8.0, AE, COND).transpos
    pesado = D.simular(40.0, AE, COND)
    assert not pesado.transpos and pesado.motivo

def test_mais_peso_nunca_sobe_mais():
    alt = [r["altura_m"] for r in D.varredura_de_massa(AE, COND, np.linspace(6, 16, 11)) if r["decolou"]]
    assert all(a >= b - 1e-6 for a, b in zip(alt, alt[1:]))

def test_massa_maxima_passa_embaixo_e_falha_em_cima():
    r = D.massa_maxima(AE, COND, tol_kg=0.002)
    m = r["massa_kg"]
    assert m and r["limitada_por"] == "obstáculo"
    assert D.simular(m, AE, COND, forcas=False).transpos
    assert not D.simular(m + 0.05, AE, COND, forcas=False).transpos

def test_obstaculo_mais_alto_reduz_a_massa_maxima():
    m1 = D.massa_maxima(AE, COND)["massa_kg"]
    m2 = D.massa_maxima(AE, D.Condicoes(obstaculo_m=1.2))["massa_kg"]
    assert m2 < m1

def test_series_de_forca_alinhadas_e_peso_correto():
    r = D.simular(12.0, AE, COND)
    n = len(r.x)
    assert all(len(v) == n for v in r.forcas.values()) and len(r.h) == n == len(r.t)
    assert r.forcas["W"][0] == pytest.approx(12.0 * D.G)
    assert r.forcas["L"][0] == 0.0 and r.forcas["atrito"][0] > 0
    assert r.forcas["T"][n // 4] > r.forcas["D"][n // 4]

def test_sem_tracao_e_recusado_com_mensagem():
    ae = D.Aeronave(1.4, 2.0, 0.5, 0.06, (0.0, 30.0), (0.0, 0.0))
    r = D.simular(12.0, ae, COND)
    assert not r.decolou and "Tração" in r.motivo

def test_pista_curta_demais_nao_atinge_velocidade():
    r = D.simular(12.0, AE, D.Condicoes(pista_m=5.0))
    assert not r.decolou and "rotação" in r.motivo

def test_entradas_invalidas():
    with pytest.raises(ValueError):
        D.simular(0, AE, COND)
    with pytest.raises(ValueError):
        D.simular(10, D.Aeronave(1.4, 0.4, 0.5, 0.06), COND)

ARANDU = Path(__file__).resolve().parents[2] / "referencia_v1" / "Arandu" / "src"

@pytest.mark.skipif(not ARANDU.is_dir(), reason="Arandu 0.2.0 não está ao lado")
@pytest.mark.parametrize("m", [8.0, 12.0, 14.5])
def test_mesmo_resultado_que_o_arandu_0_2(m):
    sys.path.insert(0, str(ARANDU))
    try:
        from arandu.perf import decolagem as velho
    finally:
        sys.path.remove(str(ARANDU))
    rho = COND.rho
    ref = velho.simular(m, 1.4, 2.0, lambda v: 60.0 - (60.0 - 24.0) * min(max(v, 0), 30) / 30.0,
                        0.5, 0.06, rho=rho, mu=COND.mu, pista_m=COND.pista_m,
                        obstaculo_m=COND.obstaculo_m, d_alpha_rotacao=COND.d_alpha_rotacao,
                        taxa_rotacao=COND.taxa_rotacao, margem_rotacao=COND.margem_rotacao)
    novo = D.simular(m, AE, COND)
    assert novo.decolou == ref.decolou
    if ref.decolou:
        assert novo.distancia_rotacao == pytest.approx(ref.distancia_rotacao, rel=2e-3)
        assert novo.altura_obstaculo == pytest.approx(ref.altura_no_obstaculo, abs=5e-3)
