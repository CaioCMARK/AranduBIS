import multiprocessing
import os
import sys

if getattr(sys, "frozen", False):
    os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(os.path.dirname(sys.executable), "dados", "numba_cache"))

from aranduBIS.servidor import opcoes_da_linha, quer_janela, servir

if __name__ == "__main__":
    multiprocessing.freeze_support()
    porta, abrir = opcoes_da_linha(sys.argv[1:])
    sys.exit(servir(porta=porta, abrir=abrir, janela=quer_janela(sys.argv[1:], getattr(sys, "frozen", False))))
