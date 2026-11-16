import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from aranduBIS import servidor as S

@pytest.fixture()
def srv(tmp_path):
    s = ThreadingHTTPServer(("127.0.0.1", 0), S.fazer_handler(S.Estado(tmp_path)))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1], tmp_path
    s.shutdown()
    s.server_close()

def pede(porta, metodo, caminho, corpo=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", porta, timeout=30)
    h = {"Content-Type": "application/json"}
    if host:
        h["Host"] = host
    c.request(metodo, caminho, json.dumps(corpo) if corpo is not None else None, h)
    r = c.getresponse()
    b = r.read()
    c.close()
    return r.status, b

def test_pagina_e_exemplos(srv):
    porta, _ = srv
    st, b = pede(porta, "GET", "/")
    assert st == 200 and b"AranduBIS" in b
    st, b = pede(porta, "GET", "/api/exemplos")
    assert st == 200 and json.loads(b)["exemplos"]

def test_constroi_pelo_http(srv):
    porta, _ = srv
    esq = json.loads(pede(porta, "GET", "/api/exemplo?nome=biplano/biplano_b.json")[1])
    st, b = pede(porta, "POST", "/api/constroi", esq)
    assert st == 200 and json.loads(b)["massa_kg"] > 0
    st, b = pede(porta, "POST", "/api/constroi", {"versao": 1, "elementos": []})
    assert st == 400 and "sem elementos" in json.loads(b)["erro"]

def test_host_de_fora_e_recusado(srv):
    porta, _ = srv
    st, _ = pede(porta, "GET", "/api/exemplos", host="exemplo.com")
    assert st == 403

def test_arquivo_fora_da_pasta_web_nao_sai(srv):
    porta, _ = srv
    assert pede(porta, "GET", "/web/../servidor.py")[0] == 404

def test_configuracao_valida_grava_e_persiste(srv):
    porta, pasta = srv
    st, b = pede(porta, "POST", "/api/configuracao", {"polares.ncrit_modo": "fixo", "polares.ncrit": 6})
    assert st == 200
    ops = {o["chave"]: o for o in json.loads(b)["opcoes"]}
    assert ops["polares.ncrit"]["valor"] == 6.0 and ops["polares.ncrit"]["ativa"]
    assert (pasta / "configuracao.json").is_file()
    st, b = pede(porta, "POST", "/api/configuracao", {"polares.ncrit": 99})
    assert st == 400
    st, b = pede(porta, "POST", "/api/configuracao", {"polares.fonte": "avl"})
    assert json.loads(b)["problemas"]

def test_arquivos_da_equipe_pelo_http(srv, tmp_path_factory):
    porta, _ = srv
    pasta = tmp_path_factory.mktemp("rel")
    (pasta / "a.txt").write_text("conteudo")
    assert pede(porta, "GET", "/api/arquivos?pasta=relatorios")[0] == 400
    st, _ = pede(porta, "POST", "/api/configuracao", {"pastas.relatorios": str(pasta)})
    assert st == 200
    st, b = pede(porta, "GET", "/api/arquivos?pasta=relatorios")
    assert st == 200 and json.loads(b)["itens"][0]["nome"] == "a.txt"
    st, b = pede(porta, "GET", "/api/arquivo?pasta=relatorios&caminho=a.txt")
    assert st == 200 and b == b"conteudo"
    assert pede(porta, "GET", "/api/arquivo?pasta=relatorios&caminho=../x")[0] == 400

def test_decolagem_e_pontuacao_pelo_http(srv):
    porta, pasta = srv
    par = {"massa_kg": 12.0, "aeronave": {"S": 1.4, "CL_max": 1.6, "CL_corrida": 0.5, "CD_corrida": 0.06},
           "tracao": {"T0": 60.0, "V0": 40.0}, "condicoes": {}}
    st, b = pede(porta, "POST", "/api/decolagem", par)
    assert st == 200 and "massa_maxima" in json.loads(b)
    par["aeronave"]["S"] = 0
    assert pede(porta, "POST", "/api/decolagem", par)[0] == 400
    st, b = pede(porta, "GET", "/api/regras")
    regras = json.loads(b)["regras"]
    assert any(r["nome"] == "sae2026_regular" for r in regras)
    st, b = pede(porta, "GET", "/api/regra?nome=sae2026_regular&origem=fabrica")
    regra = json.loads(b)
    st, b = pede(porta, "POST", "/api/regra/avalia", {"regra": regra, "valores": {"PV": 5, "CP_bruta": 10}})
    assert st == 200 and json.loads(b)["total"] > 0
    st, b = pede(porta, "POST", "/api/regra/grava", {"regra": regra, "nome": "minha_2027"})
    assert st == 200 and (pasta / "regras" / "minha_2027.json").is_file()
    assert pede(porta, "POST", "/api/regra/grava", {"regra": regra, "nome": "../x"})[0] == 400
    assert any(r["origem"] == "usuario" for r in json.loads(pede(porta, "GET", "/api/regras")[1])["regras"])

def pede_cru(porta, metodo, caminho, corpo_bruto, cabecalhos=None):
    c = http.client.HTTPConnection("127.0.0.1", porta, timeout=30)
    h = {"Content-Type": "application/json"}
    h.update(cabecalhos or {})
    c.request(metodo, caminho, corpo_bruto, h)
    r = c.getresponse()
    b = r.read()
    c.close()
    return r.status, b

def test_post_de_outra_origem_e_recusado(srv):
    porta, pasta = srv
    st, _ = pede_cru(porta, "POST", "/api/configuracao", json.dumps({"polares.fonte": "xfoil"}),
                     {"Origin": "http://site-malicioso.example", "Content-Type": "text/plain"})
    assert st == 403
    assert not (pasta / "configuracao.json").exists()

def test_post_da_propria_origem_passa(srv):
    porta, _ = srv
    st, _ = pede_cru(porta, "POST", "/api/aero/resumo", json.dumps({"esquema": {}}),
                     {"Origin": f"http://127.0.0.1:{porta}"})
    assert st == 200

@pytest.mark.parametrize("corpo", ["[1, 2]", '"texto"', "42", "null"])
def test_corpo_que_nao_e_objeto_da_400_e_nao_derruba_a_conexao(srv, corpo):
    porta, _ = srv
    st, b = pede_cru(porta, "POST", "/api/limites", corpo)
    assert st == 400 and "objeto" in json.loads(b)["erro"]

def test_excecao_inesperada_vira_500_com_mensagem(srv):
    porta, _ = srv
    st, b = pede_cru(porta, "POST", "/api/equilibrio", json.dumps({"esquema": "oi"}))
    assert st in (400, 500)
    assert "erro" in json.loads(b)

def test_configuracao_invalida_nao_aplica_nada(srv):
    porta, pasta = srv
    antes = json.loads(pede(porta, "GET", "/api/configuracao")[1])
    fonte = next(o["valor"] for o in antes["opcoes"] if o["chave"] == "polares.fonte")
    nova = "avl" if fonte != "avl" else "xfoil"
    st, b = pede(porta, "POST", "/api/configuracao", {"polares.fonte": nova, "chave.inexistente": 1})
    assert st == 400
    depois = json.loads(pede(porta, "GET", "/api/configuracao")[1])
    assert next(o["valor"] for o in depois["opcoes"] if o["chave"] == "polares.fonte") == fonte
    assert not (pasta / "configuracao.json").exists()

def test_malha_degenerada_da_erro_claro(srv):
    porta, _ = srv
    esq = json.loads(pede(porta, "GET", "/api/exemplo?nome=30p30n_faixa.json")[1])
    st, b = pede(porta, "POST", "/api/limites", {"esquema": esq, "V": 12.0})
    assert "degenerada" in json.loads(b)["erro"]

def test_pagina_oferece_exportacao_e_serve_o_script(srv):
    porta, _ = srv
    st, b = pede(porta, "GET", "/")
    assert st == 200 and b'id="b_exporta"' in b and b"/web/exporta.js" in b
    st, b = pede(porta, "GET", "/web/exporta.js")
    assert st == 200 and b"const Exporta" in b


def test_opcoes_da_linha():
    from aranduBIS.servidor import PORTA, opcoes_da_linha
    assert opcoes_da_linha([]) == (PORTA, True)
    assert opcoes_da_linha(["--sem-navegador"]) == (PORTA, False)
    assert opcoes_da_linha(["--porta", "8800", "--sem-navegador"]) == (8800, False)
    assert opcoes_da_linha(["--porta=8801"]) == (8801, True)

def test_janela_propria_so_quando_pedida_ou_no_executavel():
    from aranduBIS.servidor import quer_janela
    assert quer_janela([]) is False
    assert quer_janela(["--janela"]) is True
    assert quer_janela([], congelado=True) is True
    assert quer_janela(["--navegador"], congelado=True) is False
    assert quer_janela(["--janela", "--sem-navegador"]) is False
