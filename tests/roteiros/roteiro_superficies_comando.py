import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from aranduBIS.nucleo.modelador import aeronave_geometria as AG
from aranduBIS.nucleo.modelador import aeronave_importa as IM
from aranduBIS.nucleo.modelador import corpo_triangulos as CT
from aranduBIS.nucleo.modelador import superficies_comando as SC

def asa(controles=None):
    elemento = {
        "nome": "asa",
        "tipo": "asa",
        "perfil": "NACA 0012",
        "n_perfil": 40,
        "secoes": [
            {"y": -1.0, "corda": 0.3, "perfil": "NACA 0012"},
            {"y": 1.0, "corda": 0.3, "perfil": "NACA 0012"},
        ],
    }
    if controles:
        elemento["controles"] = controles
    return {"versao": 1, "nome": "t", "elementos": [elemento]}

def ponto_mais_para_tras(geometria, y):
    V = geometria.V
    estacao = V[np.abs(V[:, 1] - V[np.argmin(np.abs(V[:, 1] - y)), 1]) < 1e-9]
    return estacao[np.argmax(estacao[:, 0])]

limpa = AG.constroi(asa())
zero = AG.constroi(asa([{"nome": "a", "y": [0.4, 0.8], "xc": 0.75, "deflexao": 0.0, "modo": "anti"}]))
assert (
    abs(limpa.V[:, 2].max() - zero.V[:, 2].max()) < 1e-9
    and abs(limpa.V[:, 0].max() - zero.V[:, 0].max()) < 1e-9
)

delta = 15.0
flape = AG.constroi(asa([{"nome": "f", "y": [0.2, 0.8], "xc": 0.7, "deflexao": delta, "modo": "sim"}]))
bf = ponto_mais_para_tras(flape, 0.5)
esperado = -0.3 * 0.3 * np.sin(np.radians(delta))
print(f"1 ok: bordo de fuga em z = {bf[2]:.5f}, esperado {esperado:.5f}")
assert abs(bf[2] - esperado) < 2e-3
bf_menos = ponto_mais_para_tras(flape, -0.5)
assert abs(bf_menos[2] - bf[2]) < 1e-9, "flape: os dois lados iguais"

aileron = AG.constroi(asa([{"nome": "a", "y": [0.2, 0.8], "xc": 0.7, "deflexao": delta, "modo": "anti"}]))
direita = ponto_mais_para_tras(aileron, 0.5)
esquerda = ponto_mais_para_tras(aileron, -0.5)
print(f"2 ok: aileron, z {direita[2]:.5f} e {esquerda[2]:.5f}")
assert direita[2] < -0.01 and esquerda[2] > 0.01

fora = ponto_mais_para_tras(aileron, 0.95)
assert abs(fora[2]) < 1e-9

corpo = CT.CorpoTriangulos(aileron.V, aileron.T, sinal="pseudo-normal")
print(f"3 ok: arestas sem par {corpo.n_arestas_borda}")
assert corpo.fechado and corpo.n_arestas_borda == 0

movel = AG.constroi(
    asa([{"nome": "l", "y": [0.0, 1.0], "xc": 0.25, "deflexao": 10.0, "modo": "sim", "movel": True}])
)
ba = movel.V[np.argmin(movel.V[:, 0])]
assert ba[2] > 0.0, "movel: o bordo de ataque sobe quando o bordo de fuga desce"

def asa_afilada(controle):
    elemento = {
        "nome": "asa",
        "tipo": "asa",
        "n_perfil": 40,
        "perfil": "NACA 0012",
        "controles": [controle],
        "secoes": [
            {"y": -1.0, "corda": 0.2, "perfil": "NACA 0012"},
            {"y": 0.0, "corda": 0.4, "perfil": "NACA 0012"},
            {"y": 1.0, "corda": 0.2, "perfil": "NACA 0012"},
        ],
    }
    return {"versao": 1, "nome": "t", "elementos": [elemento]}

constante = {"nome": "a", "y": [0.3, 0.8], "corda": 0.08, "deflexao": 15.0, "modo": "sim"}
assert (
    abs(SC.charneira_em(constante, 0.4) - 0.8) < 1e-12 and abs(SC.charneira_em(constante, 0.2) - 0.6) < 1e-12
)
geo = AG.constroi(asa_afilada(constante))
y_est = np.unique(np.round(geo.V[:, 1], 6))
for y_teste in (0.4, 0.7):
    y_real = y_est[np.argmin(np.abs(y_est - y_teste))]
    estacao = geo.V[np.abs(geo.V[:, 1] - y_real) < 1e-6]
    bf = estacao[np.argmax(estacao[:, 0])]
    assert abs(bf[2] + 0.08 * np.sin(np.radians(15.0))) < 3e-3, (y_real, bf)

anel = np.array([[1, 0], [0.5, 0.05], [0, 0], [0.5, -0.05]], float)
assert abs(SC._altura_do_eixo(anel, 0.5, "extradorso") - 0.05) < 1e-12
assert abs(SC._altura_do_eixo(anel, 0.5, "intradorso") + 0.05) < 1e-12
assert abs(SC._altura_do_eixo(anel, 0.5, "meio")) < 1e-12

for ruim in (
    {"nome": "x", "y": [0.5, 0.2]},
    {"nome": "x", "y": [0.1, 0.5], "xc": 1.2},
    {"nome": "x", "y": [0.1, 0.5], "modo": "outro"},
    {"nome": "x", "y": [0.1, 0.5], "deflexao": 60},
    {"nome": "x", "y": [0.1, 0.5], "deflexao": 25, "limite": 20},
    {"nome": "x", "y": [0.1, 0.5], "charneira": "outra"},
    {"nome": "x", "y": [0.1, 0.5], "corda": -0.1},
):
    try:
        AG.constroi(asa([ruim]))
        raise SystemExit(f"devia recusar {ruim}")
    except AG.GeometriaInvalida:
        pass

base = asa([{"nome": "a", "y": [0.2, 0.8], "xc": 0.7, "deflexao": 0.0, "modo": "anti"}])
novo = SC.com_deflexoes(base, {"a": 12.0})
assert novo["elementos"][0]["controles"][0]["deflexao"] == 12.0
assert base["elementos"][0]["controles"][0]["deflexao"] == 0.0
try:
    SC.com_deflexoes(base, {"nao_existe": 1.0})
    raise SystemExit("devia recusar comando desconhecido")
except SC.ControleInvalido:
    pass

texto = IM.avl_exporta(base)["texto"]
assert texto.count("CONTROL") == 4, texto
assert "C1 1 0.7 0 0 0 1" in texto and "C1 -1 0.7 0 0 0 1" in texto and "# comando C1 = a" in texto
assert texto.count("SECTION") == 6
com_eixo = asa([{"nome": "a", "y": [0.2, 0.8], "xc": 0.7, "deflexao": 0.0, "modo": "anti", "charneira": "extradorso"}])
geometria_pivo = AG.constroi(com_eixo)
pivos = geometria_pivo.info["asa"]["pivos"]
assert [p["lado"] for p in pivos] == ["+y", "-y"]
ponta_interna, ponta_externa = pivos[0]["pontas"]
assert abs(ponta_interna[1] - 0.2) < 1e-9 and abs(ponta_externa[1] - 0.8) < 1e-9
assert abs(ponta_interna[0] - 0.7 * 0.3) < 1e-6, "x do eixo = xc * corda"
assert ponta_interna[2] > 0.0, "eixo no extradorso fica acima da corda"
print("OK: superficies_comando")
