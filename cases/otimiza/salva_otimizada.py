import json, os, sys
from pathlib import Path
import otimiza_asa_canard as O
from aranduBIS.nucleo.otimiza import problema as P

saida, destino = sys.argv[1:3]
d = json.loads((O.AQUI / "saida" / saida).read_text(encoding="utf8"))
x = max((a for a in d["refino"] if a.get("viavel")), key=lambda a: a["pontuacao"])["x"]
esq, _ = P.monta(O.problema(os.environ.get("ESQUEMA", "asa_canard.json")), x)
r = P.avalia(O.problema(os.environ.get("ESQUEMA", "asa_canard.json")), x)["resultados"]
from aranduBIS.nucleo.modelador import aeronave_geometria as AG
mc = AG.massa_e_cg(AG.constroi(esq))
Mt = r["PV"] + 9.0
m = Mt - mc["massa_kg"]
esq["elementos"].append({"nome": "sistemas_e_carga", "tipo": "ponto", "massa": round(m, 4), "posicao": [round((Mt * r["x_cg"] - mc["massa_kg"] * mc["cg_m"][0]) / m, 4), 0.0, 0.0],
                         "nota": "baterias, eletronica, servos, motor e carga de referencia agrupados no CG do projeto otimizado"})
esq.pop("_pasta", None); esq["nome"] = Path(destino).stem
esq["titulo"] = "Asa voadora com canard - projeto otimizado"
(O.RAIZ / "cases" / "geometria" / "generico" / destino).write_text(json.dumps(esq, indent=1, ensure_ascii=False), encoding="utf8")
print({k: round(v, 3) for k, v in x.items()})
