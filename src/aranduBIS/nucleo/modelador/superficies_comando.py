from __future__ import annotations

import numpy as np

FAIXA_CORDA = 0.02
FAIXA_ENVERGADURA = 0.012
MODOS = ("sim", "anti", "lado")
CHARNEIRAS = ("meio", "extradorso", "intradorso")

class ControleInvalido(ValueError):
    pass

def valida(controles, nome_elemento):
    for c in controles:
        rotulo = f"elemento {nome_elemento!r}, comando {c.get('nome')!r}"
        if not c.get("nome"):
            raise ControleInvalido(f"elemento {nome_elemento!r}: comando sem nome")
        y = c.get("y")
        if not y or len(y) != 2 or not 0 <= y[0] < y[1]:
            raise ControleInvalido(f"{rotulo}: 'y' precisa ser [inicio, fim], com 0 <= inicio < fim")
        if not 0.0 < float(c.get("xc", 0.75)) < 1.0:
            raise ControleInvalido(f"{rotulo}: 'xc' precisa estar entre 0 e 1")
        if "corda" in c and float(c["corda"]) <= 0.0:
            raise ControleInvalido(f"{rotulo}: 'corda' precisa ser positiva")
        if c.get("charneira", "meio") not in CHARNEIRAS:
            raise ControleInvalido(f"{rotulo}: 'charneira' precisa ser uma de {CHARNEIRAS}")
        if "limite" in c and abs(float(c.get("deflexao", 0.0))) > float(c["limite"]):
            raise ControleInvalido(f"{rotulo}: deflexao acima do batente de {c['limite']} graus")
        if c.get("modo", "sim") not in MODOS:
            raise ControleInvalido(f"{rotulo}: 'modo' precisa ser um de {MODOS}")
        if abs(float(c.get("deflexao", 0.0))) > 45.0:
            raise ControleInvalido(f"{rotulo}: deflexao acima de 45 graus")

def suave(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def _sinal_do_lado(controle, y):
    modo = controle.get("modo", "sim")
    if modo == "anti":
        return 1.0 if y >= 0 else -1.0
    if modo == "lado":
        return 1.0 if y >= 0 else 0.0
    return 1.0

def fator_envergadura(controle, y, y_ponta):
    y0, y1 = controle["y"]
    a = abs(y)
    subida = 1.0 if y0 <= 1e-9 else suave((a - y0 + FAIXA_ENVERGADURA) / FAIXA_ENVERGADURA)
    descida = 1.0 if y1 >= y_ponta - 1e-9 else suave((y1 + FAIXA_ENVERGADURA - a) / FAIXA_ENVERGADURA)
    return subida * descida

def estacoes_extras(controles, ys):
    y_ponta = max(abs(ys[0]), abs(ys[-1]))
    extras = []
    for c in controles:
        for borda in c["y"]:
            if borda <= 1e-9 or borda >= y_ponta - 1e-9:
                continue
            for fracao in (-1.0, -0.5, 0.0, 0.5, 1.0):
                centro = (
                    borda - 0.5 * FAIXA_ENVERGADURA if borda == c["y"][0] else borda + 0.5 * FAIXA_ENVERGADURA
                )
                a = centro + fracao * 0.5 * FAIXA_ENVERGADURA
                extras += [a, -a]
    return [y for y in extras if ys[0] < y < ys[-1]]

def charneira_em(controle, corda_local):
    if "corda" in controle:
        return max(0.05, 1.0 - float(controle["corda"]) / corda_local)
    return float(controle.get("xc", 0.75))

def aplica(anel, controles, y, y_ponta, corda_local=1.0):
    anel = np.array(anel, float)
    for c in controles:
        fator = fator_envergadura(c, y, y_ponta) * _sinal_do_lado(c, y)
        angulo = np.radians(float(c.get("deflexao", 0.0))) * fator
        if angulo != 0.0:
            xc = charneira_em(c, corda_local)
            anel = _gira_atras_da_charneira(
                anel, xc, angulo, bool(c.get("movel")), c.get("charneira", "meio")
            )
    return anel

def _altura_do_eixo(anel, xc, charneira):
    x, z = anel[:, 0], anel[:, 1]
    cruzamentos = []
    for i in range(len(x)):
        j = (i + 1) % len(x)
        if (x[i] - xc) * (x[j] - xc) <= 0 and x[i] != x[j]:
            cruzamentos.append(z[i] + (xc - x[i]) / (x[j] - x[i]) * (z[j] - z[i]))
    if charneira == "extradorso":
        return max(cruzamentos)
    if charneira == "intradorso":
        return min(cruzamentos)
    return 0.5 * (min(cruzamentos) + max(cruzamentos))

def _gira_atras_da_charneira(anel, xc, angulo, movel, charneira="meio"):
    zc = _altura_do_eixo(anel, xc, charneira)
    du = anel[:, 0] - xc
    dw = anel[:, 1] - zc
    if movel:
        peso = np.ones(len(anel))
    else:
        peso = suave((du + FAIXA_CORDA) / (2.0 * FAIXA_CORDA))
    giro = angulo * peso
    cos_giro, sen_giro = np.cos(giro), np.sin(giro)
    return np.c_[xc + du * cos_giro + dw * sen_giro, zc - du * sen_giro + dw * cos_giro]

def com_deflexoes(esquema, deflexoes):
    import copy

    novo = copy.deepcopy(esquema)
    faltando = set(deflexoes)
    for elemento in novo.get("elementos", []):
        for c in elemento.get("controles", []):
            if c["nome"] in deflexoes:
                c["deflexao"] = float(deflexoes[c["nome"]])
                faltando.discard(c["nome"])
    if faltando:
        raise ControleInvalido(f"comando sem correspondente no projeto: {sorted(faltando)}")
    return novo

def lista(esquema):
    saida = []
    for elemento in esquema.get("elementos", []):
        for c in elemento.get("controles", []):
            saida.append({"elemento": elemento.get("nome"), **c})
    return saida
