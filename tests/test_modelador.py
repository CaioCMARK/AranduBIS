import subprocess
import sys
from pathlib import Path

import pytest

ROTEIROS = sorted((Path(__file__).parent / "roteiros").glob("roteiro_*.py"))

@pytest.mark.parametrize("r", ROTEIROS, ids=lambda p: p.stem)
def test_roteiro(r):
    p = subprocess.run([sys.executable, "-I", str(r)], capture_output=True,
                       text=True, timeout=600)
    assert p.returncode == 0, p.stdout[-800:] + p.stderr[-1500:]
