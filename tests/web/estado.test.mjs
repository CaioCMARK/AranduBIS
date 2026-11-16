import test from "node:test";
import assert from "node:assert/strict";
import { carrega } from "./carrega.mjs";

test("estado: globais antigas e Estado apontam para o mesmo valor", () => {
  const pega = carrega(["estado.js"]);
  pega("esq = { elementos: [{ nome: 'a' }, { nome: 'b' }] }; sel = 1");
  assert.equal(pega("Estado.sel"), 1);
  assert.equal(pega("Estado.elemento().nome"), "b");
  pega("Estado.sel = 0");
  assert.equal(pega("sel"), 0);
  assert.equal(pega("Estado.elemento().nome"), "a");
});

test("estado: ouvinte recebe a chave, o valor novo e o anterior, e so quando muda", () => {
  const pega = carrega(["estado.js"]);
  pega("var visto = []; var para = Estado.ouve((k, novo, antes) => visto.push([k, novo, antes]))");
  pega("sel = 3; sel = 3; aba = 'Peso'; para(); sel = 5");
  assert.deepEqual(JSON.parse(pega("JSON.stringify(visto)")), [["sel", 3, -1], ["aba", "Peso", "Seções"]]);
});

test("estado: sem aeronave nao ha elemento", () => {
  const pega = carrega(["estado.js"]);
  assert.equal(pega("Estado.elemento()"), null);
});
