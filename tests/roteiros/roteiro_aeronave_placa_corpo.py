import copy, sys
from collections import Counter
from pathlib import Path
import numpy as np
RAIZ = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(RAIZ / "src"))
from aranduBIS.nucleo.modelador import aeronave_geometria as AG

def fechada(A, so=None):
    T = A.T if so is None else A.T[so]; c = Counter()
    for t in T:
        for i in range(3): c[(int(t[i]), int(t[(i + 1) % 3]))] += 1
    return max(c.values()) == 1 and all((b, a) in c for (a, b) in c)

def volume(A, so=None):
    T = A.T if so is None else A.T[so]; return float(np.einsum("ij,ij->i", A.V[T[:, 0]], np.cross(A.V[T[:, 1]], A.V[T[:, 2]])).sum() / 6)

def falha(esq, trecho):
    try: AG.constroi(esq)
    except AG.GeometriaInvalida as e: assert trecho in str(e), str(e); return
    raise AssertionError("deveria falhar: " + trecho)

L = [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]]
esq = {"versao": 1, "nome": "t", "elementos": [{"nome": "torre", "tipo": "placa", "contorno": L, "espessura": 0.05, "y": 0.3}]}
A = AG.constroi(esq)
assert fechada(A) and abs(volume(A) - 3 * 0.05) < 1e-12, volume(A)
assert set(A.zonas) == {"torre.face-y", "torre.face+y", "torre.contorno"}
c = A.V[A.T].mean(1)
assert np.allclose(c[A.triangulos_da_zona("torre.face-y")][:, 1], 0.3 - 0.025) and np.allclose(c[A.triangulos_da_zona("torre.face+y")][:, 1], 0.3 + 0.025)
assert abs(volume(A) - 0.15) < 1e-12 and len(A.triangulos_da_zona("torre.contorno")) == 2 * len(L)
e = A.pontos_da_linha("torre.aresta+y"); assert np.allclose(e[:, 1], 0.325) and np.array_equal(e[0], e[-1]) and len(e) == len(L) + 1
e2 = copy.deepcopy(esq); e2["elementos"][0]["contorno"] = L[::-1] + [L[-1]]; e2["elementos"][0]["contorno"] = list(reversed(L)) + [list(reversed(L))[0]]
B = AG.constroi(e2); assert fechada(B) and abs(volume(B) - 0.15) < 1e-12
e3 = copy.deepcopy(esq); e3["elementos"][0]["posicao"] = [1.0, -2.0, 0.5]; C = AG.constroi(e3)
assert np.allclose(C.V, A.V + [1.0, -2.0, 0.5]) and np.array_equal(C.T, A.T) and abs(volume(C) - 0.15) < 1e-12
e3 = copy.deepcopy(esq); e3["marcas"] = [{"nome": "braco_alto", "feicao": "torre.aresta+y", "z": [1.0, 2.0]}]; D = AG.constroi(e3); zz = D.V[D.linhas["braco_alto"], 2]
assert zz.min() >= 1.0 - 1e-12 and zz.max() <= 2.0 + 1e-12 and len(zz) >= 4
f = copy.deepcopy(esq); f["elementos"][0]["espessura"] = 0; falha(f, "espessura")
f = copy.deepcopy(esq); f["elementos"][0]["contorno"] = [[0, 0], [1, 0]]; falha(f, ">= 3")
f = copy.deepcopy(esq); f["elementos"][0]["contorno"] = [[0, 0], [3, 0], [0, 1], [1, 2]]; falha(f, "cruza")
f = copy.deepcopy(esq); f["elementos"][0]["contorno"] = [[0, 0], [1, 1], [2, 2]]; falha(f, "area nula")
f = copy.deepcopy(esq); f["elementos"][0]["contorno"] = [[0, 0], [2, 2], [2, 0], [0, 2]]; falha(f, "area nula")

n, r, Lc = 24, 0.3, 2.0
cil = {"versao": 1, "nome": "c", "elementos": [{"nome": "fus", "tipo": "corpo", "n_secao": n, "estacoes": [{"x": 0.0, "a": r, "b": r}, {"x": 1.0, "a": r, "b": r}, {"x": Lc, "a": r, "b": r}]}]}
K = AG.constroi(cil); assert fechada(K) and set(K.zonas) == {"fus.casca", "fus.tampa-x", "fus.tampa+x"}
assert abs(volume(K) - Lc * 0.5 * n * r * r * np.sin(2 * np.pi / n)) < 1e-12, volume(K)
cu, qu = K.pontos_da_linha("fus.cumeeira"), K.pontos_da_linha("fus.quilha"); assert len(cu) == 3 and np.allclose(cu[:, 2], r) and np.allclose(qu[:, 2], -r) and np.allclose(cu[:, 0], [0, 1, Lc])
assert np.allclose(K.V[K.T[K.triangulos_da_zona("fus.tampa-x")]].mean(1)[:, 0], 0.0) and np.allclose(K.V[K.T[K.triangulos_da_zona("fus.tampa+x")]].mean(1)[:, 0], Lc)
def area_anel(p, n_=256):
    q = {"versao": 1, "elementos": [{"nome": "b", "tipo": "corpo", "n_secao": n_, "estacoes": [{"x": 0, "a": 1.0, "b": 0.5, "expoente": p}, {"x": 1, "a": 1.0, "b": 0.5, "expoente": p}]}]}
    return volume(AG.constroi(q))
assert abs(area_anel(2.0) - np.pi * 0.5) < 2e-4 and 1.9 < area_anel(12.0) < 2.0, (area_anel(2.0), area_anel(12.0))
ret = [[-0.2, -0.1], [0.2, -0.1], [0.2, 0.1], [-0.2, 0.1]]
P = {"versao": 1, "elementos": [{"nome": "b", "tipo": "corpo", "n_secao": 64, "estacoes": [{"x": 0, "pontos": ret, "zc": 0.5}, {"x": 3, "pontos": ret, "zc": 0.5}]}]}
Q = AG.constroi(P); assert fechada(Q) and abs(volume(Q) - 0.08 * 3) < 5e-3 and np.allclose(Q.pontos_da_linha("b.cumeeira")[:, 2], 0.6) and np.allclose(Q.pontos_da_linha("b.quilha")[:, 2], 0.4)
Fm = {"versao": 1, "elementos": [{"nome": "b", "tipo": "corpo", "n_secao": 48, "estacoes": [{"x": 0, "a": 0.2, "b": 0.15, "expoente": 6}, {"x": 1.5, "a": 0.2, "b": 0.15, "expoente": 3}, {"x": 3, "a": 0.05, "b": 0.05, "expoente": 2}]}]}
M = AG.constroi(Fm); assert fechada(M) and 0 < volume(M) < 3 * 4 * 0.2 * 0.15
tudo = {"versao": 1, "nome": "mix", "elementos": [AG.exemplo_asa_ar3()["elementos"][0], copy.deepcopy(esq["elementos"][0]), copy.deepcopy(cil["elementos"][0])]}
tudo["elementos"][1]["posicao"] = [0.4, 0.0, 0.1]; tudo["elementos"][2]["posicao"] = [-3.0, 0.0, 0.0]
X = AG.constroi(tudo); assert len(X.zonas) == 4 + 3 + 3 and X.T.max() == len(X.V) - 1 and all((X.zona == i).any() for i in range(len(X.zonas)))
ids = sorted({i for v in X.linhas.values() for i in v}); assert ids[0] >= 0 and ids[-1] < len(X.V)
import tempfile
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "m.obj"; AG.escreve_obj(X, p); Y = AG.le_obj(p); assert np.array_equal(Y.V, X.V) and Y.zonas == X.zonas and Y.linhas == X.linhas
w0 = AG.exemplo_asa_ar3(); W0 = AG.constroi(w0); w1 = copy.deepcopy(w0); w1["elementos"][0]["rolagem"] = 90.0; w1["elementos"][0]["posicao"] = [0.0, 0.0, 2.0]; W1 = AG.constroi(w1)
assert abs(volume(W1) - volume(W0)) < 1e-9 and fechada(W1) and volume(W1) > 0
assert np.allclose([W1.V[:, 2].min(), W1.V[:, 2].max()], [2.0 - 1.5, 2.0 + 1.5], atol=1e-12) and abs(W1.V[:, 1].max()) < 0.07 and np.allclose(W1.V[:, 0], W0.V[:, 0])
w2 = copy.deepcopy(w0); w2["elementos"][0]["rolagem"] = 0.0; assert np.array_equal(AG.constroi(w2).V, W0.V)
falha({"versao": 1, "elementos": [{"nome": "b", "tipo": "corpo", "estacoes": [{"x": 0, "a": 1, "b": 1}]}]}, ">= 2")
falha({"versao": 1, "elementos": [{"nome": "b", "tipo": "corpo", "estacoes": [{"x": 1, "a": 1, "b": 1}, {"x": 0, "a": 1, "b": 1}]}]}, "crescer")
falha({"versao": 1, "elementos": [{"nome": "b", "tipo": "corpo", "estacoes": [{"x": 0, "a": 0, "b": 1}, {"x": 1, "a": 1, "b": 1}]}]}, "a > 0")
falha({"versao": 1, "elementos": [{"nome": "b", "tipo": "helice"}]}, "ainda nao suportado")
print("OK: placa (L nao convexo, volume exato), corpo (cilindro, superelipse, pontos, forma que muda), posicao, marca por z, varios elementos, erros")
