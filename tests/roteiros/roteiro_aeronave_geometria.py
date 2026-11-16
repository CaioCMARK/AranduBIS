import copy, sys, tempfile
from pathlib import Path
import numpy as np
RAIZ = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(RAIZ / "src"))
from aranduBIS.nucleo.modelador import camada3d as C3, aeronave_geometria as AG

esq = AG.exemplo_asa_ar3(); A = AG.constroi(esq)
sec = [(0.0, y_, 0.0, 1.0, 0.0) for y_ in np.linspace(-1.5, 1.5, 34)]; V0, T0 = C3.loft_asa(sec, n_perfil=60, cod="0012", quads=False)
assert np.array_equal(A.V, V0) and np.array_equal(A.T, np.asarray(T0)), "a asa de exemplo mudou em relacao ao loft_asa usado pelos geradores de malha"

assert len(A.zona) == len(A.T) and set(A.zonas) == {"asa.extradorso", "asa.intradorso", "asa.ponta-y", "asa.ponta+y"} and all((A.zona == i).any() for i in range(4))
c = A.V[A.T].mean(1)
assert (c[A.triangulos_da_zona("asa.extradorso")][:, 2] > 0).all() and (c[A.triangulos_da_zona("asa.intradorso")][:, 2] < 0).all()
assert np.allclose(c[A.triangulos_da_zona("asa.ponta-y")][:, 1], -1.5) and np.allclose(c[A.triangulos_da_zona("asa.ponta+y")][:, 1], 1.5)
def area(t): a, b, d = A.V[A.T[t]].transpose(1, 0, 2); return 0.5 * np.linalg.norm(np.cross(b - a, d - a), axis=1).sum()
ap = area(A.triangulos_da_zona("asa.ponta-y")); assert abs(ap - area(A.triangulos_da_zona("asa.ponta+y"))) < 1e-12 and 0.080 < ap < 0.084, ap

bf = A.pontos_da_linha("asa.bordo_fuga"); ba = A.pontos_da_linha("asa.bordo_ataque"); assert len(bf) == 34 and np.allclose(bf[:, 0], 1.0) and np.allclose(ba[:, 0], 0.0) and np.allclose(bf[:, 1], np.linspace(-1.5, 1.5, 34))
ct = A.pontos_da_linha("asa.contorno_ponta-y"); assert np.allclose(ct[:, 1], -1.5) and np.array_equal(ct[0], ct[-1]) and len(ct) == 2 * 60 - 2 + 1

with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "a.obj"; AG.escreve_obj(A, p); B = AG.le_obj(p)
    o = np.argsort(A.zona, kind="stable")
    assert np.array_equal(B.V, A.V) and np.array_equal(B.T, A.T[o]) and B.zonas == A.zonas and np.array_equal(B.zona, A.zona[o]) and B.linhas == A.linhas and B.nome == A.nome
    assert sorted(map(tuple, np.sort(B.T, 1).tolist())) == sorted(map(tuple, np.sort(A.T, 1).tolist()))

e2 = copy.deepcopy(esq); e2["marcas"] = [{"nome": "bf_direito", "feicao": "asa.bordo_fuga", "y": [0.0, 1.5]}]; A2 = AG.constroi(e2); y = A2.V[A2.linhas["bf_direito"], 1]
assert y.min() >= -1e-12 and abs(y.max() - 1.5) < 1e-12 and 15 <= len(y) <= 18

def falha(esq_, trecho):
    try: AG.constroi(esq_)
    except AG.GeometriaInvalida as e: assert trecho in str(e), str(e); return
    raise AssertionError("deveria falhar: " + trecho)
e3 = copy.deepcopy(esq); e3["marcas"] = [{"nome": "x", "feicao": "asa.nada"}]; falha(e3, "nao existe")
e3 = copy.deepcopy(esq); e3["marcas"] = [{"nome": "x", "feicao": "asa.bordo_fuga", "y": [0.0, 0.01]}]; falha(e3, ">= 2")
e3 = copy.deepcopy(esq); e3["elementos"][0]["perfil"] = "NACA 23012"; falha(e3, "4 digitos")
e3 = copy.deepcopy(esq); e3["elementos"][0]["tipo"] = "fuselagem"; falha(e3, "nao suportado")
e3 = copy.deepcopy(esq); e3["versao"] = 2; falha(e3, "versao")
e3 = copy.deepcopy(esq); del e3["elementos"][0]["secoes_lineares"]; e3["elementos"][0]["secoes"] = [{"y": 1, "corda": 1}, {"y": 0, "corda": 1}]; falha(e3, "crescer")

from collections import Counter
B = AG.carrega(RAIZ / "cases" / "geometria" / "30p30n_faixa.json"); cont = Counter()
for t in B.T:
    for i in range(3): cont[(int(t[i]), int(t[(i + 1) % 3]))] += 1
assert max(cont.values()) == 1 and all((b, a) in cont for (a, b) in cont), "30P-30N: superficie nao estanque/orientavel"
vol = np.einsum("ij,ij->i", B.V[B.T[:, 0]], np.cross(B.V[B.T[:, 1]], B.V[B.T[:, 2]])).sum() / 6; area = 0.0
for sec in ("Slat", "Main Element", "Flap"):
    P, i_ba = AG.anel_de_arquivo(RAIZ / "cases" / "geometria" / "30p30n.dat", sec); x, y = P[:, 0], P[:, 1]; area += 0.5 * (x @ np.roll(y, -1) - y @ np.roll(x, -1)); assert P[0, 0] == P[:, 0].max() and P[i_ba, 0] == P[:, 0].min()
assert abs(vol - area * 0.1) < 1e-12 * max(1, vol) and vol > 0, (vol, area * 0.1)
assert len(B.zonas) == 12 and all((B.zona == i).any() for i in range(12)) and set(B.linhas) >= {"slat.bordo_ataque", "flape.bordo_fuga"}
e3 = copy.deepcopy(esq); e3["_pasta"] = str(RAIZ / "cases" / "geometria"); e3["elementos"][0]["perfil_pontos"] = {"arquivo": "30p30n.dat", "secao": "Nada"}; falha(e3, "nao existe")
print("OK: aeronave_geometria (bit a bit igual ao loft_asa, zonas, OBJ ida e volta, marcas, erros, 30P-30N por pontos)")
