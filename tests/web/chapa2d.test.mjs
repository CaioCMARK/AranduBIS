import test from "node:test";
import assert from "node:assert/strict";
import { carrega } from "./carrega.mjs";

const novo = () => { const pega = carrega(["chapa2d.js"]); pega("var P = Chapa2D.puro"); return pega; };
const dado = (pega, x) => JSON.parse(pega(`JSON.stringify(${x} ?? null)`));

test("corte: um tetraedro cortado no meio da um triangulo fechado", () => {
  const pega = novo();
  pega("var V = [0,0,0, 1,0,0, 0,0,1, 0,1,0], T = [0,1,2, 0,1,3, 1,2,3, 0,2,3], Z = [0,0,0,0]");
  const s = dado(pega, "P.corta(V, T, Z, null, 0.5)");
  assert.equal(s.length, 3);
  const pts = new Set(s.flatMap(q => [q.slice(0, 2).join(), q.slice(2).join()]));
  assert.deepEqual([...pts].sort(), ["0,0", "0,0.5", "0.5,0"]);
  assert.equal(dado(pega, "P.corta(V, T, Z, new Set([0]), 0.5)").length, 0);
  assert.equal(dado(pega, "P.corta(V, T, Z, null, 2)").length, 0);
});

test("inserir: o vertice novo cai no lado mais proximo", () => {
  const pega = novo();
  pega("var C = [[0,0],[0.3,0],[0.3,0.2],[0,0.2]]; var i = P.insere(C, 0.1, -0.02)");
  assert.equal(pega("i"), 1);
  assert.deepEqual(dado(pega, "C[1]"), [0.1, 0]);
  assert.equal(pega("C.length"), 5);
});

test("arredondar: o canto vira arco tangente aos dois lados, com o raio pedido", () => {
  const pega = novo();
  pega("var C = [[0,0],[0.3,0],[0.3,0.2],[0,0.2]]; var n = P.arredonda(C, 1, 0.05)");
  assert.equal(pega("n"), 9);
  assert.deepEqual(dado(pega, "[C[1], C[9]]"), [[0.25, 0], [0.3, 0.05]]);
  const r = dado(pega, "C.slice(1, 10).map(p => Math.hypot(p[0] - 0.25, p[1] - 0.05))");
  assert.ok(r.every(v => Math.abs(v - 0.05) < 1e-4));
  const a = pega("P.area(C)");
  assert.ok(Math.abs(a - (0.06 - (1 - Math.PI / 4) * 0.0025)) < 2e-5);
  assert.equal(pega("P.arredonda([[0,0],[0.3,0],[0.3,0.2],[0,0.2]], 1, 0.2)"), null);
});

test("cruzamento: detecta o contorno em oito e aceita o retangulo", () => {
  const pega = novo();
  assert.equal(pega("P.seCruza([[0,0],[1,0],[1,1],[0,1]])"), false);
  assert.equal(pega("P.seCruza([[0,0],[1,1],[1,0],[0,1]])"), true);
});

test("DXF: exporta em milimetros e le de volta o contorno e o furo", () => {
  const pega = novo();
  pega("var C = [[0,0],[0.3,0],[0.3,0.2],[0,0.2]], F = [P.circulo(0.1, 0.1, 0.02, 12)]; var t = P.dxf(C, F); var r = P.leDxf(t)");
  assert.ok(pega("t").includes("LWPOLYLINE") && pega("t").includes("300.000"));
  assert.deepEqual(dado(pega, "r.contorno"), [[0, 0], [0.3, 0], [0.3, 0.2], [0, 0.2]]);
  assert.equal(pega("r.furos.length"), 1);
  assert.ok(Math.abs(pega("Math.abs(P.area(r.furos[0]))") - pega("Math.abs(P.area(F[0]))")) < 1e-9);
});

test("DXF: linhas soltas encadeadas viram um contorno e circulo vira furo", () => {
  const pega = novo();
  const linha = (a, b) => ["0", "LINE", "8", "0", "10", a[0], "20", a[1], "11", b[0], "21", b[1]].join("\n");
  const txt = ["0", "SECTION", "2", "ENTITIES", linha([0, 0], [100, 0]), linha([100, 50], [100, 0]), linha([100, 50], [0, 50]), linha([0, 50], [0, 0]), "0", "CIRCLE", "10", "50", "20", "25", "40", "10", "0", "ENDSEC", "0", "EOF"].join("\n");
  pega(`var r = P.leDxf(${JSON.stringify(txt)})`);
  assert.equal(pega("r.contorno.length"), 4);
  assert.ok(Math.abs(pega("Math.abs(P.area(r.contorno))") - 0.005) < 1e-9);
  assert.equal(pega("r.furos.length"), 1);
  assert.equal(pega("P.leDxf('0\\nEOF')"), null);
});
