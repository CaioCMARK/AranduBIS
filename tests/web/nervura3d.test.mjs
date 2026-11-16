import test from "node:test";
import assert from "node:assert/strict";
import { carrega } from "./carrega.mjs";

const novo = () => {
  const pega = carrega(["estado.js", "nervura3d.js"], { Secao3D: { dados: () => ({ dados: null }) }, elemento: () => null });
  pega("var P = Nervura3D.puro; var asa = { tipo: 'asa', secoes: [{ y: -1 }, { y: 0 }, { y: 1 }], estrutura: { nervuras: { y: [0.2, 0.5, 0.8], angulos: [[0.5, 10]], angulo: 0 } } }; var n = asa.estrutura.nervuras; var L = P.limites(asa)");
  return pega;
};
const dado = (pega, x) => JSON.parse(pega(`JSON.stringify(${x})`));

test("limites: asa simetrica edita so a semi-asa", () => {
  const pega = novo();
  assert.deepEqual(dado(pega, "L"), { lo: 0, hi: 1, simetrica: true });
  assert.deepEqual(dado(pega, "P.limites({ secoes: [{ y: 0.1 }, { y: 0.9 }] })"), { lo: 0.1, hi: 0.9, simetrica: false });
});

test("prende: a nervura para a 5 mm das vizinhas e das pontas", () => {
  const pega = novo();
  assert.ok(Math.abs(pega("P.prende(n, L, 0.5, 0.9)") - 0.795) < 1e-9);
  assert.ok(Math.abs(pega("P.prende(n, L, 0.5, 0.0)") - 0.205) < 1e-9);
  assert.ok(Math.abs(pega("P.prende(n, L, 0.8, 5.0)") - 1.0) < 1e-9);
  assert.equal(pega("P.prende(n, L, 0.5, 0.6)"), 0.6);
});

test("aplicaY: mover a nervura leva o angulo proprio junto", () => {
  const pega = novo();
  pega("P.aplicaY(n, 0.5, 0.6)");
  assert.deepEqual(dado(pega, "n.y"), [0.2, 0.6, 0.8]);
  assert.equal(pega("P.angDe(n, 0.6)"), 10);
  assert.equal(pega("P.angDe(n, 0.2)"), 0);
});

test("itens: asa simetrica desenha o espelho de cada nervura", () => {
  const pega = novo();
  const it = dado(pega, "P.itens(asa, n, L, { k: 1, y: 0.55 })");
  assert.equal(it.length, 6);
  assert.deepEqual(it.filter(q => q.k === 1).map(q => q.y), [0.55, -0.55]);
  assert.ok(it.filter(q => q.esp).every(q => q.y < 0));
});

test("maiorVao: a nervura nova entra no meio do maior vao", () => {
  const pega = novo();
  pega("n.y = [0.1, 0.2, 0.9]");
  assert.ok(Math.abs(pega("P.maiorVao(asa)") - 0.55) < 1e-9);
});

test("anel: interpola entre as secoes e inclina em torno de 25 % da corda", () => {
  const pega = novo();
  pega("var S = [{ y: 0, anel3d: [[0, 0, 0], [1, 0, 0]] }, { y: 1, anel3d: [[0, 1, 0.2], [0.5, 1, 0.2]] }]");
  assert.deepEqual(dado(pega, "P.anel(S, 0.5, 0)"), [[0, 0.5, 0.1], [0.75, 0.5, 0.1]]);
  const inc = dado(pega, "P.anel(S, 0.5, 45)");
  assert.ok(Math.abs(inc[0][1] - (0.5 - 0.1875)) < 1e-9 && Math.abs(inc[1][1] - (0.5 + 0.5625)) < 1e-9);
});
