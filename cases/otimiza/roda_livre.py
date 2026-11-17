"""Otimizacao com muitas variaveis do gemeo de tres superficies, com checkpoint a cada geracao.

Uso: python roda_livre.py [processos] [populacao] [geracoes] [semente]
"""
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from aranduBIS.nucleo.otimiza import busca as B
from aranduBIS.nucleo.otimiza import problema as P

SAIDA = Path(__file__).parent / "saida"
NOME = "tres_superficies_livre"


def figuras(prob, r, fim, t_evol):
    h = r["historico"]
    quais = sorted({0, len(h) // 8, len(h) // 4, len(h) // 2, len(h) - 1})
    todos = [o for q in quais for o in h[q]["objetivos"]]
    bins = np.linspace(min(todos), max(todos), 21)
    fig = plt.figure(figsize=(3.2 * len(quais), 7.5))
    gs = fig.add_gridspec(2, len(quais), height_ratios=[3, 2.4], hspace=0.45)
    for c, q in enumerate(quais):
        a = fig.add_subplot(gs[0, c])
        a.hist(h[q]["objetivos"], bins=bins, color="#c99a1e" if q == len(h) - 1 else "#8d9a6b")
        a.set_title(f"geracao {q} ({len(h[q]['objetivos'])} viaveis)", fontsize=9)
        a.set_xlabel("EE = 50*CP/PV", fontsize=8)
        if c == 0:
            a.set_ylabel("projetos")
    m = fig.add_subplot(gs[1, :])
    g = [x["geracao"] for x in h]
    m.plot(g, [x["melhor_objetivo"] for x in h], label="melhor", color="#4f5d2f")
    m.plot(g, [x["media_objetivo"] for x in h], label="media (viaveis)", color="#c99a1e")
    m.set_xlabel("geracao"); m.set_ylabel("EE"); m.set_title("Convergencia"); m.legend()
    fig.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.08)
    fig.savefig(SAIDA / f"{NOME}_histograma.png", dpi=120)
    plt.close(fig)
    pop = [a for a in r["populacao"] if a["violacao"] <= 0.0]
    vs = prob["variaveis"]
    nl = -(-len(vs) // 6)
    fig, ax = plt.subplots(nl, 6, figsize=(18, 2.6 * nl))
    for a in ax.ravel()[len(vs):]:
        a.axis("off")
    for a, v in zip(ax.ravel(), vs):
        vals = [p["x"][v["nome"]] for p in pop]
        a.hist(vals, bins=min(14, len(v["valores"])) if v.get("valores") else 14, range=(v["minimo"], v["maximo"]), color="#8d9a6b")
        a.axvline(fim[0]["x"][v["nome"]], color="#c99a1e", lw=2)
        a.axvline(v["padrao"], color="k", ls="--", lw=1)
        a.set_title(v["nome"], fontsize=9)
    fig.suptitle("Variaveis na populacao final (amarelo: melhor refinado; tracejado: base)")
    fig.tight_layout()
    fig.savefig(SAIDA / f"{NOME}_variaveis.png", dpi=120)
    plt.close(fig)


def main(processos, populacao, geracoes, semente):
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)  # nao deixa o PC dormir enquanto a otimizacao roda
    prob = json.loads((Path(__file__).parent / (NOME + ".json")).read_text(encoding="utf8"))
    prob["base"]["_pasta"] = str(RAIZ / "cases" / "geometria" / "tres_superficies")
    SAIDA.mkdir(exist_ok=True)
    hist = []

    def ao_gerar(reg):
        hist.append(reg)
        (SAIDA / f"{NOME}_historico.json").write_text(json.dumps({"parcial": True, "historico": hist}), encoding="utf8")
        (SAIDA / f"{NOME}_progresso.txt").write_text(
            f"geracao {reg['geracao']}/{geracoes}  melhor EE {reg['melhor_objetivo']:.2f}  viaveis {reg['n_viaveis']}  "
            f"div {reg['diversidade']:.3f}  t {reg['tempo_s']:.0f}s\n{json.dumps(reg['melhor_x'])}\n", encoding="utf8")

    t0 = time.perf_counter()
    r = B.evolui(prob, populacao=populacao, geracoes=geracoes, semente=semente, processos=processos, F=0.6, CR=0.9,
                 estrategia="aleatoria", ao_gerar=ao_gerar)
    t_evol = time.perf_counter() - t0
    fim = B.refina(prob, r, quantos=5, processos=min(processos, 5))
    (SAIDA / f"{NOME}_historico.json").write_text(json.dumps({"parcial": False, "historico": r["historico"], "refinados": [{"x": a["x"], "objetivo": a["objetivo"]} for a in fim], "t_evolucao_s": t_evol, "avaliacoes": r["avaliacoes"]}), encoding="utf8")
    figuras(prob, r, fim, t_evol)
    destino = RAIZ / "cases" / "geometria" / "tres_superficies"
    for k, a in enumerate(fim, start=1):
        esq, _ = P.monta(prob, a["x"])
        esq = {c: v for c, v in esq.items() if not c.startswith("_")}
        esq["nome"] = f"tres_superficies_livre_{k}"
        esq["referencia"] = dict(esq.get("referencia", {}), fonte="saida do otimizador (cases/otimiza/roda_livre.py)")
        (destino / f"tres_superficies_livre_{k}.json").write_text(json.dumps(esq, indent=2, ensure_ascii=False), encoding="utf8")
    (SAIDA / f"{NOME}_progresso.txt").write_text("CONCLUIDO\n" + json.dumps({"melhor": fim[0]["objetivo"], "x": fim[0]["x"], "t_evolucao_s": round(t_evol), "avaliacoes": r["avaliacoes"]}), encoding="utf8")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]) if a else 8, int(a[1]) if len(a) > 1 else 192, int(a[2]) if len(a) > 2 else 200, int(a[3]) if len(a) > 3 else 0)
