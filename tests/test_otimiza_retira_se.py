from aranduBIS.nucleo.otimiza import problema as P


def _prob():
    return {
        "base": {"elementos": [{"nome": "a"}, {"nome": "b"}]},
        "variaveis": [{"nome": "tem_b", "minimo": 0, "maximo": 1, "padrao": 1, "valores": [0, 1]}],
        "ligacoes": [{"retira_se": ["b"], "formula": "1 - tem_b"}],
    }


def test_retira_se_remove_quando_formula_positiva():
    esq, _ = P.monta(_prob(), {"tem_b": 0})
    assert [e["nome"] for e in esq["elementos"]] == ["a"]


def test_retira_se_mantem_quando_formula_nula():
    esq, _ = P.monta(_prob(), {"tem_b": 1})
    assert [e["nome"] for e in esq["elementos"]] == ["a", "b"]
