import sys

from .servidor import opcoes_da_linha, quer_janela, servir

if __name__ == "__main__":
    porta, abrir = opcoes_da_linha(sys.argv[1:])
    sys.exit(servir(porta=porta, abrir=abrir, janela=quer_janela(sys.argv[1:], False)))
