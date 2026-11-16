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
NOME = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--prob=")), "monoplano_generico")


def referencia(esq: dict) -> dict:
    sec = next(e for e in esq["elementos"] if e["nome"] == "asa")["secoes"]
    b = 2 * max(abs(q["y"]) for q in sec)
    area = sum((sec[i + 1]["y"] - sec[i]["y"]) * (sec[i]["corda"] + sec[i + 1]["corda"]) / 2 for i in range(len(sec) - 1))
    return {"Sref": round(area, 3), "Cref": round(area / b, 4), "Bref": round(b, 3)}


def main(processos: int, populacao: int, geracoes: int, semente: int, salva: bool) -> None:
    prob = json.loads((Path(__file__).parent / (NOME + ".json")).read_text(encoding="utf8"))
    prob["base"]["_pasta"] = str(RAIZ / "cases" / "geometria" / "monoplano")
    t0 = time.perf_counter()
    r = B.evolui(prob, populacao=populacao, geracoes=geracoes, semente=semente, processos=processos, F=0.6, CR=0.9, estrategia="aleatoria")
    t_evol = time.perf_counter() - t0
    fim = B.refina(prob, r, quantos=3, processos=min(processos, 3))
    t_total = time.perf_counter() - t0
    SAIDA.mkdir(exist_ok=True)
    h = r["historico"]
    g1 = h[-1]["objetivos"]
    quais = sorted({0, len(h) // 4, len(h) // 2, 3 * len(h) // 4, len(h) - 1})
    todos = [o for q in quais for o in h[q]["objetivos"]]
    bins = np.linspace(min(todos), max(todos), 16)
    fig = plt.figure(figsize=(3.2 * len(quais), 7.5))
    gs = fig.add_gridspec(2, len(quais), height_ratios=[3, 2.4], hspace=0.45)
    for c, q in enumerate(quais):
        a_ = fig.add_subplot(gs[0, c])
        a_.hist(h[q]["objetivos"], bins=bins, color="#c99a1e" if q == len(h) - 1 else "#8d9a6b")
        a_.set_title(f"geracao {q} ({len(h[q]['objetivos'])} viaveis)", fontsize=9)
        a_.set_xlabel("EE = 50*CP/PV", fontsize=8)
        if c == 0:
            a_.set_ylabel("projetos")
    m = fig.add_subplot(gs[1, :])
    g = [x["geracao"] for x in h]
    m.plot(g, [x["melhor_objetivo"] for x in h], label="melhor", color="#4f5d2f")
    m.plot(g, [x["media_objetivo"] for x in h], label="media (viaveis)", color="#c99a1e")
    m.set_xlabel("geracao"); m.set_ylabel("EE"); m.set_title("Convergencia"); m.legend()
    fig.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.08)
    png = SAIDA / f"{NOME}_{processos}n.png"
    fig.savefig(png, dpi=130)
    perfis = prob["variaveis"][3]["valores"]
    escolhidos = [("melhor", fim[0]["x"], fim[0]["objetivo"])]
    for q in (0, len(h) // 2):
        escolhidos.append((f"melhor da geracao {q}", h[q]["melhor_x"], h[q]["melhor_objetivo"]))
    pop = sorted([a for a in r["populacao"] if a["violacao"] <= 0.0 and a["objetivo"] is not None], key=lambda a: a["objetivo"])
    for rot, a in (("pior da populacao final", pop[0]), ("mediano da populacao final", pop[len(pop) // 2]), ("2o melhor", pop[-2])):
        escolhidos.append((rot, a["x"], a["objetivo"]))
    fig2, axs = plt.subplots(2, 3, figsize=(13, 6.2))
    for a_, (rot, x, ee) in zip(axs.ravel(), escolhidos):
        b, cr, af = x["b"], x["c_raiz"], x["afil"]
        b, cr, af = x["b"], x["c_raiz"], x["afil"]
        ct = cr * af
        esq_i, _ = P.monta(prob, x)
        sec = next(e for e in esq_i["elementos"] if e["nome"] == "asa")["secoes"]
        pts = [(q["y"], -q["xle"]) for q in sec] + [(q["y"], -(q["xle"] + q["corda"])) for q in reversed(sec)]
        a_.fill([q[0] for q in pts], [q[1] for q in pts], color="#c99a1e", ec="#4f5d2f", lw=1.5)
        a_.set_aspect("equal"); a_.set_xlim(-2.3, 2.3); a_.set_ylim(-0.85, 0.15)
        nome_p = perfis[int(round(x["perfil"]))].replace(".dat", "")
        a_.set_title(f"{rot}\nEE={ee:.2f}  b={b:.2f} m  c={cr:.2f}/{ct:.2f} m  {nome_p}", fontsize=9)
        a_.set_xlabel("envergadura (m)", fontsize=8)
    fig2.tight_layout()
    fig2.savefig(SAIDA / f"{NOME}_{processos}n_individuos.png", dpi=130)
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
    main(int(a[0]) if a and not a[0].startswith("--") else 4, int(a[1]) if len(a) > 1 else 24, int(a[2]) if len(a) > 2 else 12, int(a[3]) if len(a) > 3 else 0, "--salva" in a and NOME == "monoplano_generico")
