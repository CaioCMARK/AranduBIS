import json
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent

def perfil_refletido(nome="REFLEX-10.dat", t=0.10, k=0.030, r=0.60, n=60):
    b = np.linspace(0.0, np.pi, n)
    x = 0.5 * (1 - np.cos(b))
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    yc = k * x * (1 - x) * (r - x) / r * 4
    dyc = np.gradient(yc, x, edge_order=2)
    th = np.arctan(dyc)
    xu, yu = x - yt * np.sin(th), yc + yt * np.cos(th)
    xl, yl = x + yt * np.sin(th), yc - yt * np.cos(th)
    X = np.r_[xu[::-1], xl[1:]]
    Y = np.r_[yu[::-1], yl[1:]]
    th0 = np.arccos(1 - 2 * x)
    A0 = -np.trapezoid(dyc, th0) / np.pi
    A1 = 2 / np.pi * np.trapezoid(dyc * np.cos(th0), th0)
    A2 = 2 / np.pi * np.trapezoid(dyc * np.cos(2 * th0), th0)
    Cm0 = -np.pi / 4 * (A1 + A2 * 0 - A1 / 1.0 * 0) * 0 + (-np.pi / 4) * (A1 - A2 / 1.0)
    Cm0 = np.pi / 4 * (A2 - A1)
    (AQUI / nome).write_text("REFLEX-10\n" + "\n".join("%.6f %.6f" % (a, c) for a, c in zip(X, Y)) + "\n", encoding="ascii")
    return {"alpha0_graus": float(np.degrees(A0)), "Cm0": float(Cm0), "A1": float(A1), "A2": float(A2)}

def monta(b=2.4, cr=0.66, ct=0.22, xle_ponta=0.55, washout=-3.0, ainc_raiz=2.0, nome="asa_canard"):
    h = b / 2
    ye = 0.31
    ent = 0.14
    x_ent = lambda y: xle_ponta * y / h
    secoes = []
    for y in (-h, -ye - 0.02, -ye, 0.0, ye, ye + 0.02, h):
        ay = abs(y)
        c = ct + (cr - ct) * (1 - ay / h)
        if ay <= ye:
            c = c - ent
        w = washout * ay / h
        secoes.append({"y": round(y, 4), "xle": round(x_ent(ay), 4), "zle": 0.0, "corda": round(c, 4), "ainc": round(ainc_raiz + w, 3), "arquivo": "REFLEX-10.dat"})
    nerv = [round(v, 3) for v in np.linspace(0.05, h - 0.03, 14)]
    asa = {"nome": "asa", "tipo": "asa", "n_perfil": 60, "posicao": [0.0, 0.0, 0.0], "secoes": secoes,
           "estrutura": {"nervuras": {"y": nerv, "espessura": 0.00238, "material": "balsa", "alivio": 0.45},
                         "cruzadas": [{"n": 12, "y": [0.0, h * 0.5], "area_m2": 0.0030, "espessura": 0.00238, "material": "balsa"},
                                      {"n": 10, "y": [h * 0.5, h * 0.95], "area_m2": 0.0015, "espessura": 0.00238, "material": "balsa"}],
                         "longarinas": [{"xc_y": [[0.0, 0.30], [h, 0.30]], "largura": 0.00238, "material": "balsa"}],
                         "tubos": [{"xc_y": [[0.0, 0.30], [h, 0.30]], "lado": lado, "de": 0.012, "di": 0.010, "y": yy}
                                   for lado in ("extradorso", "intradorso") for yy in ([-h, 0.0], [0.0, h])],
                         "chapeado": {"ate_xc": 0.30, "ate_xc_y": [[0.0, 0.31], [h, 0.31]], "espessura": 0.001, "material": "balsa"}},
           "controles": [{"nome": "elevon", "y": [0.55 * h, 0.97 * h], "x": 0.60 * 0.5, "deflexao": 0.0, "modo": "anti", "charneira": "meio", "dobradica": "chanfro", "limite": 20.0}],
           "entelagem": {"de_xc": 0.0, "gramatura_g_m2": 40.0, "coef_abaulamento": 0.0}}
    cc, bc = 0.14, 0.40
    canard = {"nome": "canard", "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 40, "posicao": [-0.34, 0.0, 0.07],
              "secoes": [{"y": -bc, "xle": 0.0, "zle": 0.0, "corda": cc, "ainc": 2.0}, {"y": bc, "xle": 0.0, "zle": 0.0, "corda": cc, "ainc": 2.0}],
              "estrutura": {"nervuras": {"y": [0.02, 0.1, 0.2, 0.3, 0.38], "espessura": 0.00238, "material": "balsa"},
                            "longarinas": [{"xc": 0.25, "largura": 0.00238, "material": "balsa"}, {"xc": 0.75, "largura": 0.00238, "material": "balsa"}],
                            "chapeado": {"ate_xc": 0.22, "espessura": 0.001, "material": "balsa"}},
              "entelagem": {"de_xc": 0.0, "gramatura_g_m2": 40.0, "coef_abaulamento": 0.0},
              "controles": [{"nome": "profundor", "y": [0.0, bc], "x": 0.6 * cc, "deflexao": 0.0, "modo": "sim", "charneira": "meio", "dobradica": "chanfro", "limite": 25.0}]}
    elementos = [asa, canard]
    for lado, s in (("esq", -1), ("dir", 1)):
        y = s * 0.62
        c_y = ct + (cr - ct) * (1 - abs(y) / h)
        x_te = x_ent(abs(y)) + c_y
        elementos.append({"nome": "deriva_" + lado, "tipo": "asa", "perfil": "NACA 0012", "n_perfil": 40, "rolagem": -90.0, "posicao": [round(x_te - 0.20, 4), y, 0.03],
                          "secoes": [{"y": 0.0, "xle": 0.0, "corda": 0.20}, {"y": 0.24, "xle": 0.05, "corda": 0.13}],
                          "estrutura": {"nervuras": {"y": [0.0, 0.08, 0.16, 0.23], "espessura": 0.00238, "material": "balsa"},
                                        "chapeado": {"ate_xc": 0.25, "espessura": 0.001, "material": "balsa"}},
                          "entelagem": {"de_xc": 0.0, "gramatura_g_m2": 40.0, "coef_abaulamento": 0.0},
                          "controles": [{"nome": "leme_" + lado, "y": [0.0, 0.24], "xc": 0.30, "deflexao": 0.0, "modo": "lado", "charneira": "meio", "movel": True, "dobradica": "pivo", "limite": 20.0}]})
    elementos.append({"nome": "fuselagem", "tipo": "corpo", "camada": "estrutura", "n_secao": 24,
                      "estacoes": [{"x": -0.44, "a": 0.02, "b": 0.02, "zc": 0.0}, {"x": -0.36, "a": 0.06, "b": 0.06, "zc": 0.0}, {"x": -0.15, "a": 0.095, "b": 0.095, "zc": 0.0},
                                   {"x": 0.25, "a": 0.095, "b": 0.095, "zc": 0.0}, {"x": 0.45, "a": 0.05, "b": 0.05, "zc": 0.0}, {"x": 0.52, "a": 0.03, "b": 0.03, "zc": 0.0}]})
    elementos.append({"nome": "helice", "tipo": "asa", "camada": "estrutura", "perfil": "NACA 0012", "n_perfil": 14, "rolagem": 90.0, "guinada": 90.0, "posicao": [0.58, 0.0, 0.0],
                      "secoes": [{"y": -0.3048, "corda": 0.03}, {"y": -0.17, "corda": 0.05}, {"y": 0.17, "corda": 0.05}, {"y": 0.3048, "corda": 0.03}]})
    roda = {"diametro": 0.092, "largura": 0.0084, "d_furo": 0.016, "d_cubo": 0.028, "anel": 0.006, "n_aros": 6, "aro": 0.005, "material": "nylon", "camada": "estrutura", "tipo": "roda"}
    elementos.append(dict(roda, nome="roda_esq", y=-0.30, posicao=[0.42, 0.0, -0.374]))
    elementos.append(dict(roda, nome="roda_dir", y=0.30, posicao=[0.42, 0.0, -0.374]))
    elementos.append(dict(roda, nome="bequilha", diametro=0.06, largura=0.0074, d_furo=0.0, d_cubo=0.016, anel=0.005, aro=0.004, y=0.0, posicao=[-0.30, 0.0, -0.39]))
    elementos.append({"nome": "carga_util", "tipo": "ponto", "massa": 0.001, "posicao": [0.10, 0.0, 0.0], "nota": "marcador (a carga vem de analise.carga_ref_kg)"})
    ys = np.array([s["y"] for s in asa["secoes"]])
    cs = np.array([s["corda"] for s in asa["secoes"]])
    S = float(np.trapezoid(cs, ys))
    mac = float(np.trapezoid(cs ** 2, ys) / S)
    return {"versao": 1, "nome": nome, "unidade": "m",
            "referencia": {"Sref": round(S, 4), "Cref": round(mac, 4), "Bref": b, "fonte": "geometria generica (asa voadora com canard), hipoteses de desenho"},
            "elementos": elementos, "marcas": []}

if __name__ == "__main__":
    print(perfil_refletido())
    esq = monta()
    (AQUI / "asa_canard.json").write_text(json.dumps(esq, indent=1, ensure_ascii=False), encoding="utf8")
    print(esq["referencia"])
