import test from "node:test";
import assert from "node:assert/strict";
import { carrega } from "./carrega.mjs";

const novo = () => {
  const pega = carrega(["estado.js", "juntas.js", "nos3d.js"], { elemento: () => null });
  pega("var P = No3D.puro; var t = { tipo: 'trelica', posicao: [1, 0, 0], nos: [[0, 0, 0], [0, 0.2, 0], [0, -0.2, 0], [0.5, 0, 0.1]], barras: [[0, 1, 'T'], [0, 2, 'T'], [1, 3, 'T'], [2, 3, 'T']] }; var r = { tipo: 'roda', posicao: [0.3, 0, -0.2], y: 0.25 }; var r2 = { tipo: 'roda', posicao: [0.3, 0, -0.2], y: -0.25 }; esq = { elementos: [t, r, r2] }");
  return pega;
};
const dado = (pega, x) => JSON.parse(pega(`JSON.stringify(${x} ?? null)`));

test("alcas: no de trelica soma a posicao; roda usa y proprio", () => {
  const pega = novo();
  assert.deepEqual(dado(pega, "P.alcas(t)[3]"), { id: 3, p: [1.5, 0, 0.1] });
  assert.deepEqual(dado(pega, "P.alcas(r)"), [{ id: 0, p: [0.3, 0.25, -0.2] }]);
});

test("escreve: grava em coordenada local, arredondada", () => {
  const pega = novo();
  pega("P.escreve(t, 3, [1.61234567, 0, 0.3]); P.escreve(r, 0, [0.4, 0.3, -0.25])");
  assert.deepEqual(dado(pega, "t.nos[3]"), [0.61235, 0, 0.3]);
  assert.deepEqual(dado(pega, "[r.posicao, r.y]"), [[0.4, 0, -0.25], 0.3]);
});

test("espelho: acha o no simetrico na trelica e a roda do outro lado", () => {
  const pega = novo();
  assert.equal(pega("P.espelho(t, 1, P.alcas(t)[1].p).id"), 2);
  assert.equal(pega("P.espelho(t, 0, P.alcas(t)[0].p)"), null);
  assert.equal(pega("P.espelho(r, 0, P.alcas(r)[0].p).e === r2"), true);
  pega("P.define({ sim: false })");
  assert.equal(pega("P.espelho(t, 1, P.alcas(t)[1].p)"), null);
});

test("removeNos: tira as barras do no e renumera o resto, com as juntas", () => {
  const pega = novo();
  pega("Juntas.define(t, 3, 'rotula'); Juntas.define(t, 1, 'parafuso:y'); var mapa = P.removeNos(t, [1])");
  assert.deepEqual(dado(pega, "mapa"), { 0: 0, 2: 1, 3: 2 });
  assert.deepEqual(dado(pega, "t.barras"), [[0, 1, "T"], [1, 2, "T"]]);
  assert.equal(pega("t.nos.length"), 3);
  assert.deepEqual(dado(pega, "t.juntas"), [{ no: 2, tipo: "rotula" }]);
});

test("temBarra: nao depende do sentido", () => {
  const pega = novo();
  assert.equal(pega("P.temBarra(t, 3, 1)"), 2);
  assert.equal(pega("P.temBarra(t, 0, 3)"), -1);
});

test("resolve: o arrasto na tela vira deslocamento no plano ou no eixo escolhido", () => {
  const pega = novo();
  pega("P.define({ plano: 1, eixo: null })");
  const d = dado(pega, "P.resolve({ p: [0, 0, 0] }, 50, -20)");
  assert.ok(Math.abs(d[0] - 0.5) < 1e-9 && d[1] === 0 && Math.abs(d[2] - 0.2) < 1e-9);
  pega("P.define({ eixo: 'x' })");
  const e = dado(pega, "P.resolve({ p: [0, 0, 0] }, 30, 999)");
  assert.ok(Math.abs(e[0] - 0.3) < 1e-9 && e[1] === 0 && e[2] === 0);
});
