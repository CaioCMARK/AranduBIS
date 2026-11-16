import json

import pytest

from aranduBIS.fronteira import arquivos as AQ
from aranduBIS.nucleo.configuracao import Configuracao

@pytest.fixture()
def cfg(tmp_path):
    (tmp_path / "rel" / "2026").mkdir(parents=True)
    (tmp_path / "rel" / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "rel" / "2026" / "b.txt").write_text("oi")
    (tmp_path / "rel" / ".oculto").write_text("x")
    (tmp_path / "segredo.txt").write_text("nao")
    return Configuracao({"pastas.relatorios": str(tmp_path / "rel")})

def test_lista_pastas_primeiro_e_esconde_ocultos(cfg):
    r = AQ.lista(cfg, "relatorios")
    assert [i["nome"] for i in r["itens"]] == ["2026", "a.pdf"] and r["itens"][0]["pasta"]
    assert AQ.lista(cfg, "relatorios", "2026")["itens"][0]["caminho"] == "2026/b.txt"

def test_pasta_nao_configurada_diz_onde_configurar():
    with pytest.raises(AQ.ErroDeArquivo, match="Configurações"):
        AQ.lista(Configuracao(), "base")

def test_nao_sai_da_pasta_configurada(cfg):
    for ruim in ("..", "../segredo.txt", "2026/../../segredo.txt"):
        with pytest.raises(AQ.ErroDeArquivo):
            AQ.lista(cfg, "relatorios", ruim) if ruim == ".." else AQ.caminho_do_arquivo(cfg, "relatorios", ruim)
    assert AQ.caminho_do_arquivo(cfg, "relatorios", "a.pdf").name == "a.pdf"
    with pytest.raises(AQ.ErroDeArquivo):
        AQ.lista(cfg, "outra")
