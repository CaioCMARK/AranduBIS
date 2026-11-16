import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]

def test_logica_dos_editores_no_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node nao encontrado")
    arquivos = sorted(str(p) for p in (RAIZ / "tests" / "web").glob("*.test.mjs"))
    assert arquivos
    r = subprocess.run([node, "--test", *arquivos], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=RAIZ)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]

def test_scripts_da_interface_tem_sintaxe_valida():
    node = shutil.which("node")
    if not node:
        pytest.skip("node nao encontrado")
    for p in sorted((RAIZ / "src" / "aranduBIS" / "web").glob("*.js")):
        r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, p.name + ": " + r.stderr[-500:]
