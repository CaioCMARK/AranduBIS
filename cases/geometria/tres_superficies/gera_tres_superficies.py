import json, sys
from pathlib import Path
SAIDA = Path("C:/Users/gmelo/AranduBIS_publico/cases/geometria/tres_superficies")
LUMP = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

TUBOS = {"D3": {"de": 0.003, "di": 0.002, "material": "tubo_carbono"}, "D4": {"de": 0.004, "di": 0.003, "material": "tubo_carbono"},
         "D6": {"de": 0.006, "di": 0.004, "material": "tubo_carbono"}}

def trelica(nome, estacoes, secao, tl="D3", td="D3", tf="D3"):
    """Treliça prismática: 'estacoes' = lista de x; 'secao' = lista de (y, z) do polígono da seção (3 = triangular, 4 = retangular)."""
    n = len(secao)
    nos, barras = [], []
    for x in estacoes:
        for (y, z) in secao:
            nos.append([round(x, 4), y, z])
    for k, _ in enumerate(estacoes):
        b = k * n
        for i in range(n):
            barras.append([b + i, b + (i + 1) % n, tf])
        if n == 4:
            barras.append([b, b + 2, td])
        if k + 1 < len(estacoes):
            c = (k + 1) * n
            for i in range(n):
                barras.append([b + i, c + i, tl])
                j = (i + 1) % n
                barras.append([b + i, c + j, td] if k % 2 == 0 else [b + j, c + i, td])
    return {"nome": nome, "tipo": "trelica", "tubos": TUBOS, "nos": nos, "barras": barras}

def asa(nome, secoes, perfil, pos, nerv_y, tubos=None, ate_xc=0.07, controles=None, rolagem=0.0, longarina=0.28, esp_n=0.003, nota=None):
    e = {"nome": nome, "tipo": "asa", "n_perfil": 60, "posicao": pos, "secoes": [dict(s, perfil=perfil) for s in secoes],
         "estrutura": {"nervuras": {"y": nerv_y, "espessura": esp_n, "material": "balsa", "alivio": 0.4},
                       "longarinas": [{"xc": longarina, "largura": 0.006, "material": "balsa"}],
                       "chapeado": {"ate_xc": ate_xc, "espessura": 0.001, "material": "balsa"}},
         "entelagem": {"de_xc": 0.0, "gramatura_g_m2": 40.0, "coef_abaulamento": 0.0}}
    if tubos:
        e["estrutura"]["tubos"] = tubos
    if controles:
        e["controles"] = controles
    if rolagem:
        e["rolagem"] = rolagem
    return e

B2 = 1.1  # semi-envergadura da asa (estimativa)
SEC = [(-B2, 0.34, 0.05), (-0.65, 0.55, 0.0), (0.0, 0.55, 0.0), (0.65, 0.55, 0.0), (B2, 0.34, 0.05)]
secoes = [{"y": y, "xle": xle, "zle": 0.0, "corda": c, "ainc": 2.0} for (y, c, xle) in SEC]
tubos = []
for lado in ("extradorso", "intradorso"):
    tubos += [{"xc": 0.28, "lado": lado, "de": 0.008, "di": 0.006, "y": [-0.65, 0.65]},
              {"xc": 0.28, "lado": lado, "de": 0.005, "di": 0.0033, "y": [-B2, -0.65]},
              {"xc": 0.28, "lado": lado, "de": 0.005, "di": 0.0033, "y": [0.65, B2]}]
nerv = [round(0.06 + 0.1 * k, 3) for k in range(11)]
ail = [{"nome": "aileron", "y": [0.62, 1.05], "corda": 0.085, "deflexao": -6.0, "modo": "anti", "charneira": "extradorso", "dobradica": "batente"}]
elementos = [
    asa("asa", secoes, "S1223.dat", [0.0, 0.0, 0.20], nerv, tubos, 0.07, ail),
    asa("canard", [{"y": -0.45, "xle": 0.0, "zle": 0.0, "corda": 0.2, "ainc": 3.0}, {"y": 0.45, "xle": 0.0, "zle": 0.0, "corda": 0.2, "ainc": 3.0}],
        "NACA 4412", [-0.38, 0.0, 0.17], [0.03, 0.12, 0.22, 0.32, 0.42], None, 0.08),
    asa("empenagem_h", [{"y": -0.42, "xle": 0.0, "zle": 0.0, "corda": 0.18, "ainc": 0.0}, {"y": 0.42, "xle": 0.0, "zle": 0.0, "corda": 0.18, "ainc": 0.0}],
        "NACA 0012", [1.95, 0.0, 0.22], [0.02, 0.1, 0.2, 0.3, 0.4], None, 0.22, [{"nome": "profundor", "y": [0.0, 0.42], "corda": 0.06, "deflexao": 0.0, "modo": "sim", "charneira": "extradorso", "dobradica": "batente"}], longarina=0.22),
    asa("deriva", [{"y": 0.0, "corda": 0.2}, {"y": 0.4, "corda": 0.16}], "NACA 0012", [1.95, 0.0, 0.22], [0.0, 0.1, 0.2, 0.3, 0.39], None, 0.22,
        [{"nome": "leme", "y": [0.0, 0.4], "corda": 0.06, "deflexao": 0.0, "modo": "lado", "charneira": "extradorso", "dobradica": "batente"}], rolagem=90.0, longarina=0.22),
    trelica("fuselagem_tubos", [-0.85 + 0.1 * k for k in range(13)], [(-0.1, 0.0), (0.1, 0.0), (0.1, 0.16), (-0.1, 0.16)], "D4", "D3", "D3"),
    trelica("boom_tubos", [0.35 + 0.1 * k for k in range(17)], [(-0.05, 0.15), (0.05, 0.15), (0.0, 0.24)], "D4", "D3", "D3"),
    {"nome": "trem", "tipo": "trelica", "tubos": {"D10": {"de": 0.01, "di": 0.008, "material": "tubo_carbono"}}, "nos": [[0.25, -0.22, -0.12], [0.25, 0.22, -0.12]], "barras": [[0, 1, "D10"]]},
    {"nome": "roda_esq", "tipo": "roda", "diametro": 0.09, "largura": 0.0081, "d_furo": 0.016, "d_cubo": 0.028, "anel": 0.006, "n_aros": 6, "aro": 0.005, "material": "nylon", "y": -0.22, "posicao": [0.25, 0.0, -0.12], "camada": "estrutura"},
    {"nome": "roda_dir", "tipo": "roda", "diametro": 0.09, "largura": 0.0081, "d_furo": 0.016, "d_cubo": 0.028, "anel": 0.006, "n_aros": 6, "aro": 0.005, "material": "nylon", "y": 0.22, "posicao": [0.25, 0.0, -0.12], "camada": "estrutura"},
    {"nome": "roda_nariz", "tipo": "roda", "diametro": 0.07, "largura": 0.006, "d_furo": 0.0, "d_cubo": 0.02, "anel": 0.005, "n_aros": 6, "aro": 0.004, "material": "nylon", "y": 0.0, "posicao": [-0.5, 0.0, -0.1], "camada": "estrutura"},
    {"nome": "motor", "tipo": "corpo", "camada": "estrutura", "n_secao": 24, "estacoes": [{"x": -0.98, "a": 0.04, "b": 0.04, "zc": 0.08}, {"x": -0.9, "a": 0.04, "b": 0.04, "zc": 0.08}]},
    {"nome": "helice", "tipo": "asa", "camada": "estrutura", "perfil": "NACA 0012", "n_perfil": 14, "rolagem": 90.0, "guinada": 90.0, "posicao": [-1.0, 0.0, 0.08],
     "secoes": [{"y": -0.23, "corda": 0.025}, {"y": -0.12, "corda": 0.04}, {"y": 0.12, "corda": 0.04}, {"y": 0.23, "corda": 0.025}]},
    {"nome": "massa_equivalente", "tipo": "ponto", "massa": LUMP, "posicao": [-0.15, 0.0, 0.07], "nota": "Motor, bateria, eletronica e servos somados num ponto (valor de referencia a calibrar)."},
]
S = sum((secoes[i + 1]["y"] - secoes[i]["y"]) * (secoes[i]["corda"] + secoes[i + 1]["corda"]) / 2 for i in range(4))
d = {"versao": 1, "nome": "tres_superficies_a", "unidade": "m", "marcas": [],
     "referencia": {"Sref": round(S, 3), "Cref": round(S / (2 * B2), 4), "Bref": 2 * B2, "fonte": "estimativa a partir de fotos"},
     "elementos": elementos}
SAIDA.mkdir(parents=True, exist_ok=True)
json.dump(d, open(SAIDA / "tres_superficies_a.json", "w", encoding="utf8"), indent=2, ensure_ascii=False)
shutil = __import__("shutil"); shutil.copy("C:/Users/gmelo/AranduBIS_publico/cases/geometria/monoplano/S1223.dat", SAIDA / "S1223.dat")
print("Sref", round(S, 3), "b", 2 * B2)
