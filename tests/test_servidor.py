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
    par = {"massa_kg": 12.0, "aeronave": {"S": 1.4, "CL_max": 2.0, "CL_corrida": 0.5, "CD_corrida": 0.06},
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
    assert any(r["origem"] == "equipe" for r in json.loads(pede(porta, "GET", "/api/regras")[1])["regras"])
