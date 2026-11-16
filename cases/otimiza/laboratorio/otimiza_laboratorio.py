"""Otimiza uma configuracao do laboratorio pela regra SAE 2026 (aero/laboratorio_otim.py).

Uso:  python otimiza_laboratorio.py NOME [pop=12] [geracoes=20] [semente=1] [processos=2]
      python otimiza_laboratorio.py NOME avalia      (so o ponto padrao)
SEGURO=1 usa limites mais folgados na busca (margem estatica 6 %, estrutural 3 %, Cn_beta 0,04).
Saida: saida/NOME.json (historico, refino com a malha cheia e a melhor solucao).
"""
import json
import sys
import time
from pathlib import Path

from aranduBIS.nucleo.aero import laboratorio_otim as LO
from aranduBIS.nucleo.otimiza import busca as B

AQUI = Path(__file__).resolve().parent

if __name__ == "__main__":
    nome = sys.argv[1]
    import os
    prob = LO.problema(nome, seguro=bool(int(os.environ.get("SEGURO", "0"))))
    if sys.argv[2:] == ["avalia"]:
        r = LO.avalia(prob, {})
        print(json.dumps({k: v for k, v in r.items() if k not in ("resultados",)}, default=str)[:1500])
        raise SystemExit
    pop, ger, sem, proc = (int(v) for v in (sys.argv[2:] + ["12", "20", "1", "2"][len(sys.argv) - 2:])[:4])
    t0 = time.time()
    r = B.evolui(prob, populacao=pop, geracoes=ger, semente=sem, processos=proc, avalia=LO.avalia,
                 ao_gerar=lambda g: print(nome, g["geracao"], "melhor %.2f" % (g["melhor_objetivo"] or 0), g["melhor_viavel"], "viav", g["n_viaveis"],
                                          "%.0fs" % g["tempo_s"], flush=True))
    fin = B.refina(prob, r, quantos=8, processos=min(proc, 2), avalia=LO.avalia)
    (AQUI / "saida").mkdir(exist_ok=True)
    (AQUI / "saida" / f"{nome}.json").write_text(json.dumps({"modelo": nome, "historico": r["historico"], "refino": fin, "avaliacoes": r["avaliacoes"]},
                                                           ensure_ascii=False, default=str, indent=1), encoding="utf8")
    print("total %.0fs" % (time.time() - t0))
