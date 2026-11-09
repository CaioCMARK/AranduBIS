from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from ..modelador import aeronave_estrutura as ES
from ..modelador.aeronave_geometria import GeometriaInvalida, _secoes
from .perfil import Perfil
from .planform import Estacao, Planform
from .vlm import Superficie, n_span_recomendado

FRACAO_REFERENCIA = 0.5

def _perfil(spec, n, pasta) -> Perfil:
    x, zs, zi = ES.perfil_xy(spec, n, pasta)
    return Perfil(nome=str(spec), x=np.concatenate([x[::-1], x[1:]]), y=np.concatenate([zs[::-1], zi[1:]]))

def _simetrica(sec) -> bool:
    esp = {round(s[1], 6): (s[0], s[2], s[3], s[4]) for s in sec}
    if 0.0 not in esp and not any(s[1] < 0 for s in sec) or not any(s[1] > 0 for s in sec):
        return False
    return all(round(-y, 6) in esp and np.allclose(esp[round(-y, 6)], v, atol=1e-9) for y, v in esp.items())

def _metade(sec):
    return [s for s in sec if s[1] >= -1e-12]

def superficie_do_elemento(el: dict, pasta: str = ".", n_span: int | None = None, n_chord: int = 4) -> Superficie:
    nome = el.get("nome", "asa")
    sec = _secoes(el)
    pos = np.asarray(el.get("posicao", [0.0, 0.0, 0.0]), float).reshape(3)
    rolagem = float(el.get("rolagem", 0.0))
    arfagem = float(el.get("arfagem", 0.0))
    if el.get("guinada"):
        raise GeometriaInvalida(f"{nome}: guinada nao e suportada no calculo aerodinamico (so no desenho)")
    vertical = abs(rolagem) > 60.0
    espelhada = _simetrica(sec) and not vertical
    base = _metade(sec) if espelhada else sec
    if espelhada and abs(base[0][1]) > 1e-9:
        a, b = [s for s in sec if s[1] < 0][-1], base[0]
        t = -a[1] / (b[1] - a[1])
        base = [tuple(a[k] + t * (b[k] - a[k]) if k != 1 else 0.0 for k in range(5))] + base
    xle0, y0, zle0, c0, ainc0 = base[0]
    n = int(el.get("n_perfil", 40))
    perfil_de = lambda s: el.get("arquivo") or el.get("perfil", "NACA 0012")
    estacoes = tuple(Estacao(y=float(s[1] - y0), corda=float(s[3]), x_le=float(s[0] - xle0),
                             z_le=float(s[2] - zle0), torcao=float(s[4] - ainc0)) for s in base)
    spec_raiz = (el.get("secoes") or [{}])[0].get("arquivo") or (el.get("secoes") or [{}])[0].get("perfil") or perfil_de(None)
    spec_ponta = (el.get("secoes") or [{}])[-1].get("arquivo") or (el.get("secoes") or [{}])[-1].get("perfil") or spec_raiz
    raiz, ponta = _perfil(spec_raiz, n, pasta), _perfil(spec_ponta, n, pasta)
    planta = Planform(estacoes=estacoes, nome=nome)
    if n_span is None:
        n_span = n_span_recomendado(planta.alongamento)
    return Superficie(
        planta,
        incidencia=float(ainc0 + arfagem), x_le=float(pos[0] + xle0), z=float(pos[2] + zle0),
        espelhada=espelhada, diedro=rolagem, y_raiz=float(pos[1] + (0.0 if espelhada else y0)),
        perfil=raiz, perfil_ponta=ponta if ponta.nome != raiz.nome else None,
        n_span=n_span, n_chord=n_chord, de_referencia=el.get("referencia"))

def superficies(esq: dict, n_span: int | None = None, n_chord: int = 4) -> list[Superficie]:
    pasta = esq.get("_pasta", ".")
    lista = [superficie_do_elemento(el, pasta, n_span, n_chord) for el in esq.get("elementos", []) if el.get("tipo") == "asa"]
    if not lista:
        raise GeometriaInvalida("o modelo nao tem nenhuma asa: nada para o calculo aerodinamico")
    area = lambda s: s.planform.area * (1.0 if s.espelhada else 0.5)
    horizontais = [s for s in lista if abs(s.diedro) <= 60.0]
    maior = max((area(s) for s in horizontais), default=0.0)
    for s in lista:
        if s.de_referencia is None:
            s.de_referencia = s in horizontais and area(s) >= FRACAO_REFERENCIA * maior
    if not any(s.de_referencia for s in lista):
        raise GeometriaInvalida("nenhuma superficie ficou como referencia: marque uma com \"referencia\": true")
    return lista
