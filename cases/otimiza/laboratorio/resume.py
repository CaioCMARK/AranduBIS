"""Tabela comparativa das otimizacoes (saida/*.json): melhor solucao de cada configuracao, malha cheia."""
import json
from pathlib import Path

from aranduBIS.nucleo.aero import laboratorio_otim as LO

AQUI = Path(__file__).resolve().parent
if __name__ == "__main__":
    lin = []
    for n in LO.NOMES:
        f = AQUI / "saida" / f"{n}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf8"))
        r = d["refino"][0]
        q = r["resultados"]
        lin.append((r["pontuacao"] if r["viavel"] else -1.0, n, r, q))
    lin.sort(key=lambda t: -t[0])
    print(f"{'modelo':22s}{'viavel':>7s}{'P_VOO':>8s}{'PV':>6s}{'CP':>6s}{'b':>6s}{'S':>6s}{'N':>3s}{'MS%':>6s}{'Cnb':>7s}")
    for _, n, r, q in lin:
        print(f"{n:22s}{str(r['viavel']):>7s}{(r['pontuacao'] or 0):8.1f}{q.get('PV', 0):6.2f}{q.get('CP', 0):6.2f}{q.get('envergadura', 0):6.2f}{q.get('S_ref', 0):6.2f}"
              f"{int(q.get('n_superficies', 0)):3d}{100 * q.get('margem_estatica', 0):6.1f}{q.get('Cn_beta') or 0:7.3f}")
        print("   x:", {k: round(v, 3) for k, v in r["x"].items()}, [c["nome"] for c in r["restricoes"] if not c["ok"]])
