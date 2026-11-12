import multiprocessing
import sys

from aranduBIS.servidor import servir

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(servir())
