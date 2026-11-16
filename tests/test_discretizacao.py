import threading

import pytest

from aranduBIS.nucleo import configuracao as C
from aranduBIS.nucleo import discretizacao as D


def test_automatico_registra_o_motivo_e_a_equipe_sobrepoe():
    with D.pedido({}):
        assert D.vlm_n_span("asa", 10.0) == 24
        assert D.vlm_n_span("deriva", 2.0) == 48
        u = D.usadas()
        assert all(x["origem"] == "auto" and x["motivo"] for x in u)
    with D.pedido({"vlm.n_span": 40, "flutter.n_modos": 1}):
        assert D.vlm_n_span("asa", 10.0) == 40
        assert D.flutter_n_modos() == 1
        u = {x["rotulo"]: x for x in D.usadas()}
        assert u["Painéis na envergadura (asa)"]["origem"] == "usuario"
        assert any("fora da faixa" in a for a in D.avisos())


def test_estacoes_seguem_as_nervuras():
    with D.pedido():
        assert D.estacoes_estrutura(1.0) == 41
        assert D.estacoes_estrutura(1.0, [0.0, 0.02, 0.04, 0.5]) == 101


def test_pedidos_em_threads_nao_se_misturam():
    out = {}

    def roda(nome, fix):
        with D.pedido(fix):
            out[nome] = D.vlm_n_chord()

    t = [threading.Thread(target=roda, args=(k, f)) for k, f in (("a", {"vlm.n_chord": 9}), ("b", {}))]
    [x.start() for x in t]; [x.join() for x in t]
    assert out == {"a": 9, "b": 4}


def test_opcao_auto_da_configuracao():
    c = C.Configuracao()
    assert c.valor("discretizacao.vlm.n_span") is None
    c.definir("discretizacao.vlm.n_span", 30)
    assert c.valor("discretizacao.vlm.n_span") == 30 and c.manual("discretizacao.vlm.n_span")
    c.definir("discretizacao.vlm.n_span", None)
    assert c.valor("discretizacao.vlm.n_span") is None
    with pytest.raises(C.ConfiguracaoInvalida):
        c.definir("discretizacao.vlm.n_span", 1000)


def test_orcamento_e_memoria():
    leve = D.custo_uvlm(100, 20, 40, 40, False, None)
    pesado = D.custo_uvlm(2000, 200, 2000, 400, True, 200)
    assert leve["segundos"] < 1 < pesado["segundos"]
    with D.pedido({"orcamento_s": 10}):
        D.confere_orcamento(leve, "x")
        with pytest.raises(ValueError, match="orçamento"):
            D.confere_orcamento(pesado, "x")
        D.confere_orcamento(pesado, "x", forcar=True)
    with pytest.raises(ValueError, match="memória"):
        D.confere_orcamento({"segundos": 1, "memoria_bytes": 1e15, "interacoes": 0}, "x", forcar=True)


def test_servidor_anexa_a_discretizacao_usada():
    from aranduBIS.fronteira import analise as AN, geometria as G
    esq = G.abre_exemplo("biplano/biplano_a.json")
    with D.pedido({"vlm.n_chord": 3}):
        r = AN.equilibrio({"esquema": esq, "V": 14, "rho": 1.1, "x_cg": 0.1})
        u = D.usadas()
    assert "erro" not in r, r.get("erro")
    assert any(x["rotulo"].startswith("Painéis na corda") and x["valor"] == 3 and x["origem"] == "usuario" for x in u)


def _vlm_de(esq):
    from aranduBIS.nucleo.aero.aeronave_vlm import superficies
    from aranduBIS.nucleo.aero.vlm import VLM
    return VLM(superficies(esq))


def test_avisos_de_malha_canard_rente_a_esteira_e_asa_curta():
    import copy
    import warnings
    from aranduBIS.fronteira import geometria as G
    from aranduBIS.nucleo.aero.qualidade_malha import confere
    esq = G.abre_exemplo("generico/asa_canard.json")
    warnings.simplefilter("ignore")
    base = confere(_vlm_de(esq))
    e2 = copy.deepcopy(esq)
    for el in e2["elementos"]:
        if el.get("nome") == "canard":
            el["posicao"][2] = 0.0005
    novos = [a for a in confere(_vlm_de(e2)) if a not in base]
    assert any("ponto de controle" in a and "canard" in a for a in novos), novos
    e3 = copy.deepcopy(esq)
    asa = next(el for el in e3["elementos"] if el.get("nome") == "asa")
    for sc in asa.get("secoes", []):
        if "corda" in sc:
            sc["corda"] = 3.5
    assert any("alongamento" in a for a in confere(_vlm_de(e3)))


def test_avisos_so_dentro_de_um_pedido_e_uma_vez_por_geometria():
    import warnings
    from aranduBIS.fronteira import geometria as G
    warnings.simplefilter("ignore")
    esq = G.abre_exemplo("generico/asa_canard.json")
    _vlm_de(esq)
    with D.pedido():
        _vlm_de(esq); n1 = len(D.avisos())
        _vlm_de(esq); n2 = len(D.avisos())
    assert n1 >= 1 and n1 == n2


def test_convergencia_vlm_e_richardson():
    from aranduBIS.fronteira import analise as AN, geometria as G
    from aranduBIS.nucleo.aero.convergencia import richardson
    ext, p, err, _ = richardson(1.0 + 0.04, 1.0 + 0.01, 1.0 + 0.0025)
    assert p == pytest.approx(2.0) and ext == pytest.approx(1.0) and err == pytest.approx(1.25 * 0.01 / 1.0, rel=1e-6)
    assert richardson(1.0, 1.1, 1.0)[1] is None
    r = AN.convergencia_vlm({"esquema": G.abre_exemplo("biplano/biplano_a.json"), "rho": 1.1})
    assert "erro" not in r and len(r["familias"]) == 2
    cla = next(g for g in r["familias"][0]["grandezas"] if g["nome"].startswith("CLα"))
    assert cla["gci"] < 0.05


def test_flap_converge_com_n_chord():
    import json
    import warnings
    from pathlib import Path
    from aranduBIS.nucleo.aero.controle import autoridade_rolagem
    warnings.simplefilter("ignore")
    raiz = Path(__file__).resolve().parents[1]
    d = json.loads((raiz / "cases/geometria/biplano/biplano_b.json").read_text(encoding="utf-8"))
    d["_pasta"] = str(raiz / "cases/geometria/biplano")
    pb = []
    for nc in (4, 8, 16):
        with D.pedido({"vlm.n_chord": nc}):
            pb.append(autoridade_rolagem(d, massa_kg=11.0, raios={})["opcoes"]["sobe_desce"]["pb2V"])
    assert pb[0] < pb[1] < pb[2] and (pb[2] - pb[1]) < (pb[1] - pb[0])


def test_mede_a_maquina_e_estima_pelo_que_mediu(monkeypatch, tmp_path):
    from aranduBIS.nucleo import discretizacao as D
    monkeypatch.delenv("ARANDUBIS_INTERACOES_POR_S", raising=False)
    monkeypatch.setattr(D, "ARQ_MAQUINA", str(tmp_path / "maquina.json"))
    monkeypatch.setattr(D, "_MAQUINA", None)
    m = D.maquina()
    assert m["interacoes_por_s"] > 1e6 and m["particulas_por_s"] > 1e5 and m["segmento_grad_por_s"] > 1e5
    assert (tmp_path / "maquina.json").is_file() and m["cpu"]
    c = D.custo_vpm(400, 40, 30)
    monkeypatch.setattr(D, "_MAQUINA", {k: (v / 2 if isinstance(v, float) else v) for k, v in m.items()})
    assert D.custo_vpm(400, 40, 30)["segundos"] == pytest.approx(2 * c["segundos"])
    assert "threads" in D.descreve_maquina()
