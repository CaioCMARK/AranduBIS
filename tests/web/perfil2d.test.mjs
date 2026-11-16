import test from "node:test";
import assert from "node:assert/strict";
import { carrega } from "./carrega.mjs";

const novo = () => { const pega = carrega(["chapa2d.js", "perfil2d.js"]); pega("var P = Perfil2D.puro"); return pega; };
const dado = (pega, x) => JSON.parse(pega(`JSON.stringify(${x} ?? null)`));

test("NACA 4412: espessura e curvatura maximas batem com o codigo", () => {
  const pega = novo();
  pega("var A = P.naca('4412'), m = P.medidas(A)");
  const m = dado(pega, "m");
  assert.ok(Math.abs(m.espessura - 0.12) < 0.004);
  assert.ok(Math.abs(m.curvatura - 0.04) < 0.003);
  assert.ok(Math.abs(m.x_curvatura - 0.4) < 0.06);
  assert.equal(pega("A[0][0]"), 1);
  assert.equal(pega("A[A.length-1][0]"), 1);
});

test("dat: ida e volta preserva os pontos (Selig)", () => {
  const pega = novo();
  pega("var A = P.naca('0012'), B = P.leDat(P.dat('x', A))");
  assert.deepEqual(dado(pega, "B"), dado(pega, "A"));
});

test("Lednicer: reconhece a contagem e monta o anel do bordo de fuga ao bordo de fuga", () => {
  const pega = novo();
  pega("var NL = String.fromCharCode(10); var A = P.naca('2412', 12), S = P.lados(A); var txt = 'x' + NL + S.sup.length + '. ' + S.inf.length + '.' + NL + S.sup.map(p => p.join(' ')).join(NL) + NL + S.inf.map(p => p.join(' ')).join(NL); var B = P.leDat(txt)");
  assert.equal(pega("B.length"), pega("A.length"));
  assert.ok(pega("B[0][1] > B[B.length - 1][1] - 1e-3 || B[2][1] > 0"));
});

test("simetrizar: a inferior vira o espelho da superior", () => {
  const pega = novo();
  pega("var A = P.simetriza(P.naca('4412')), m = P.medidas(A)");
  assert.ok(Math.abs(dado(pega, "m.curvatura")) < 0.01);
  assert.ok(dado(pega, "m.espessura") > 0.15);
});

test("inserir: o ponto novo entra entre os vizinhos", () => {
  const pega = novo();
  pega("var A = P.naca('0012', 20), n = A.length, i = P.insere(A, 0.5, 0.2)");
  assert.equal(pega("A.length"), pega("n") + 1);
  assert.ok(pega("i") > 0);
});

test("leDat recusa arquivo curto", () => {
  const pega = novo();
  assert.equal(dado(pega, "P.leDat(['a','0 0','1 0'].join(String.fromCharCode(10)))"), null);
});
