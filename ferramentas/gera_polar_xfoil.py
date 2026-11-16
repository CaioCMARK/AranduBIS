from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aranduBIS.nucleo.aero.polares import BancoPolares, ler_arquivo_xflr5, montar_de_arquivos

REYNOLDS = [40_000, 60_000, 80_000, 110_000, 150_000, 200_000, 280_000, 400_000, 500_000]
A_MIN, A_MAX, PASSO = -10.0, 22.0, 0.5

def roda(xfoil: Path, perfil: Path, re: int, ncrit: float, pasta: Path) -> Path | None:
    saida = pasta / f"Polar_Re{re // 1000}k.dat"
    saida.unlink(missing_ok=True)
    cmd = "\n".join(["PLOP", "G F", "", f"LOAD {perfil.name}", "", "PANE", "OPER", f"VISC {re}", "VPAR", f"N {ncrit}", "",
                     "ITER 400", "PACC", saida.name, "", f"ASEQ 0 {A_MAX} {PASSO}", "INIT", f"ASEQ 0 {A_MIN} {PASSO}",
                     "PACC", "", "QUIT", ""])
    try:
        subprocess.run([str(pasta / "xfoil.exe")], input=cmd, cwd=str(pasta), capture_output=True, text=True, timeout=400)
    except subprocess.TimeoutExpired:
        print(f"  Re={re}: tempo esgotado", flush=True)
    if not saida.exists():
        return None
    n = sum(1 for ln in saida.read_text(encoding="latin-1").splitlines() if ln.strip() and ln.strip()[0] in "-0123456789")
    print(f"  Ncrit {ncrit:g}  Re={re:>7}: {n:>3} pontos", flush=True)
    return saida if n >= 10 else None

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("perfil", type=Path)
    ap.add_argument("--xfoil", type=Path, required=True)
    ap.add_argument("--ncrit", type=float, nargs="+", default=[4.0, 7.0])
    ap.add_argument("--banco", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "polares.npz")
    a = ap.parse_args()
    nome = a.perfil.read_text(encoding="latin-1").splitlines()[0].strip()
    banco = BancoPolares.carregar_npz(a.banco)
    with tempfile.TemporaryDirectory() as tmp:
        for ncrit in a.ncrit:
            pasta = Path(tmp) / f"n{ncrit:g}"
            pasta.mkdir()
            shutil.copy(a.xfoil, pasta / "xfoil.exe")
            shutil.copy(a.perfil, pasta / a.perfil.name)
            with ThreadPoolExecutor(4) as ex:
                arqs = [p for p in ex.map(lambda r: roda(a.xfoil, a.perfil, r, ncrit, pasta), REYNOLDS) if p]
            if len(arqs) < 3:
                print(f"Ncrit {ncrit:g}: so {len(arqs)} estacoes convergiram, nada gravado")
                continue
            topo = {a: ler_arquivo_xflr5(a)["alpha"].max() for a in arqs}
            alvo = max(topo.values()) - 3.0
            boas = [a for a in arqs if topo[a] >= alvo]
            if len(boas) >= 5:
                for f in set(arqs) - set(boas):
                    print(f"  descartada {f.name}: parou em {topo[f]:.1f} graus (as melhores vao a {alvo + 3:.1f})")
                arqs = boas
            pol = montar_de_arquivos(arqs, nome=f"{nome}@n{int(ncrit)}")
            pol.meta["fonte"] = f"XFOIL, perfil {a.perfil.name}; gerado por ferramentas/gera_polar_xfoil.py"
            banco.adicionar(pol)
            print(f"Ncrit {ncrit:g}: {pol.nome} com {len(pol.re)} Reynolds, alpha {pol.alpha[0]:.1f} a {pol.alpha[-1]:.1f}, "
                  f"cl_max {pol.cl.max():.2f}")
    banco.salvar_npz(a.banco)
    print("banco salvo:", a.banco)

if __name__ == "__main__":
    main()
