"""Grava os JSON do laboratorio de configuracoes (a logica esta em aranduBIS/nucleo/aero/laboratorio.py).

    python monta_laboratorio.py            # grava os JSON desta pasta
    python monta_laboratorio.py --estudos  # roda os estudos e imprime as tabelas
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[2] / "src"))

from aranduBIS.nucleo.aero import laboratorio as L  # noqa: E402

if __name__ == "__main__":
    for arq, esq in L.exemplos().items():
        (AQUI / arq).write_text(json.dumps(L.referencia_de(esq), indent=1, ensure_ascii=False) + "\n", encoding="utf8")
        print("gravado", arq)
    if "--estudos" in sys.argv:
        print(json.dumps(L.roda_estudos(), indent=1, ensure_ascii=False))
