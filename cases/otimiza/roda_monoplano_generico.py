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


def referencia(esq: dict) -> dict:
    sec = next(e for e in esq["elementos"] if e["nome"] == "asa")["secoes"]
    b = 2 * max(abs(q["y"]) for q in sec)
    area = sum((sec[i + 1]["y"] - sec[i]["y"]) * (sec[i]["corda"] + sec[i + 1]["corda"]) / 2 for i in range(len(sec) - 1))
    return {"Sref": round(area, 3), "Cref": round(area / b, 4), "Bref": round(b, 3)}


def main(processos: int, populacao: int, geracoes: int, semente: int, salva: bool) -> None:
    prob = json.loads((Path(__file__).parent / "monoplano_generico.json").read_text(encoding="utf8"))
    prob["base"]["_pasta"] = str(RAIZ / "cases" / "geometria" / "monoplano")
    t0 = time.perf_counter()
    r = B.evolui(prob, populacao=populacao, geracoes=geracoes, semente=semente, processos=processos)
    t_evol = time.perf_counter() - t0
    fim = B.refina(prob, r, quantos=3, processos=min(processos, 3))
    t_total = time.perf_counter() - t0
    SAIDA.mkdir(exist_ok=True)
    h = r["historico"]
    g0, g1 = h[0]["objetivos"], h[-1]["objetivos"]
    todos = g0 + g1
    bins = np.linspace(min(todos), max(todos), 13)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].hist(g0, bins=bins, alpha=0.55, label=f"geracao 0 ({len(g0)} viaveis)", color="#8d9a6b")
    ax[0].hist(g1, bins=bins, alpha=0.65, label=f"geracao {len(h) - 1} ({len(g1)} viaveis)", color="#c99a1e")
    ax[0].set_xlabel("carga paga bruta (kg)")
    ax[0].set_ylabel("projetos")
    ax[0].set_title("Histograma da populacao")
    ax[0].legend()
    ax[1].plot([x["geracao"] for x in h], [x["melhor_objetivo"] for x in h], label="melhor", color="#4f5d2f")
    ax[1].plot([x["geracao"] for x in h], [x["media_objetivo"] for x in h], label="media (viaveis)", color="#c99a1e")
    ax[1].set_xlabel("geracao")
    ax[1].set_title("Convergencia")
    ax[1].legend()
    fig.tight_layout()
    png = SAIDA / f"monoplano_generico_{processos}n.png"
    fig.savefig(png, dpi=130)
    print(json.dumps({"processos": processos, "avaliacoes": r["avaliacoes"], "t_evolucao_s": round(t_evol, 1), "t_total_s": round(t_total, 1),
                      "melhor": fim[0]["objetivo"], "x": fim[0]["x"], "viaveis_final": len(g1), "png": str(png)}))
    if salva:
        destino = RAIZ / "cases" / "geometria" / "monoplano"
        for k, a in enumerate(fim[:3], start=1):
            esq, _ = P.monta(prob, a["x"])
            esq = {c: v for c, v in esq.items() if not c.startswith("_")}
            esq["nome"] = f"monoplano_otimizado_{k}"
            esq["referencia"] = dict(esq.get("referencia", {}), **referencia(esq), fonte="saida do otimizador (cases/otimiza/roda_monoplano_generico.py)")
            (destino / f"monoplano_otimizado_{k}.json").write_text(json.dumps(esq, indent=2, ensure_ascii=False), encoding="utf8")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]) if a else 4, int(a[1]) if len(a) > 1 else 24, int(a[2]) if len(a) > 2 else 12, int(a[3]) if len(a) > 3 else 0, "--salva" in a)
