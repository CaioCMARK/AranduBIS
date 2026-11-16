import test from "node:test";
import assert from "node:assert/strict";
import { carrega } from "./carrega.mjs";

const novo = () => { const pega = carrega(["juntas.js"]); pega("var e = { nos: [[0,0,0],[1,0,0],[2,0,0]], barras: [[0,1,'T'],[1,2,'T']] }"); return pega; };
const dado = (pega, x) => JSON.parse(pega(`JSON.stringify(${x} ?? null)`));

test("junta: solda e o padrao e nao fica gravada", () => {
  const pega = novo();
  assert.equal(pega("Juntas.de(e, 1)"), "solda");
  pega("Juntas.define(e, 1, 'parafuso:x')");
  assert.deepEqual(dado(pega, "e.juntas"), [{ no: 1, tipo: "parafuso", eixo_livre: "x" }]);
  assert.equal(pega("Juntas.de(e, 1)"), "parafuso:x");
  pega("Juntas.define(e, 1, 'rotula')");
  assert.deepEqual(dado(pega, "e.juntas"), [{ no: 1, tipo: "rotula" }]);
  pega("Juntas.define(e, 1, 'solda')");
  assert.equal(dado(pega, "e.juntas"), null);
});

test("vinculo: engaste, apoio com translacoes e ligacao convivem no mesmo no", () => {
  const pega = novo();
  pega("Juntas.defineVinculo(e, 0, 'apoio'); Juntas.defineLigacao(e, 0, 'asa_inferior')");
  assert.deepEqual(dado(pega, "e.vinculos"), [{ no: 0, tipo: "apoio", graus: [1, 2, 3] }, { no: 0, tipo: "ligacao", alvo: "asa_inferior" }]);
  assert.equal(pega("Juntas.vinculoDe(e, 0)"), "apoio");
  assert.equal(pega("Juntas.ligacaoDe(e, 0)"), "asa_inferior");
  pega("Juntas.defineVinculo(e, 0, 'engaste')");
  assert.equal(pega("Juntas.vinculoDe(e, 0)"), "engaste");
  assert.equal(pega("Juntas.ligacaoDe(e, 0)"), "asa_inferior");
  pega("Juntas.defineVinculo(e, 0, ''); Juntas.defineLigacao(e, 0, '')");
  assert.equal(dado(pega, "e.vinculos"), null);
});

test("remapeia: no removido leva a junta junto e os demais sao renumerados", () => {
  const pega = novo();
  pega("Juntas.define(e, 1, 'rotula'); Juntas.define(e, 2, 'parafuso:y'); Juntas.defineVinculo(e, 2, 'engaste')");
  pega("Juntas.remapeia(e, { 0: 0, 2: 1 })");
  assert.deepEqual(dado(pega, "e.juntas"), [{ no: 1, tipo: "parafuso", eixo_livre: "y" }]);
  assert.deepEqual(dado(pega, "e.vinculos"), [{ no: 1, tipo: "engaste" }]);
});

test("copia: o no novo herda junta, vinculo e ligacao", () => {
  const pega = novo();
  pega("Juntas.define(e, 0, 'parafuso:z'); Juntas.defineVinculo(e, 0, 'engaste'); Juntas.defineLigacao(e, 0, 'asa'); Juntas.copia(e, 0, 2)");
  assert.equal(pega("Juntas.de(e, 2)"), "parafuso:z");
  assert.equal(pega("Juntas.vinculoDe(e, 2)"), "engaste");
  assert.equal(pega("Juntas.ligacaoDe(e, 2)"), "asa");
});

test("parafuso: o atalho cicla os eixos y, x, z", () => {
  const pega = novo();
  assert.equal(pega("Juntas.proximoParafuso('solda')"), "parafuso:y");
  assert.equal(pega("Juntas.proximoParafuso('parafuso:y')"), "parafuso:x");
  assert.equal(pega("Juntas.proximoParafuso('parafuso:z')"), "parafuso:y");
});
