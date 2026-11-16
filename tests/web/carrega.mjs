import vm from "node:vm";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "src", "aranduBIS", "web");

export function carrega(arquivos, extras = {}) {
  const nada = () => {};
  const no = () => new Proxy(function () {}, { get: (_, k) => (k === "style" || k === "dataset" || k === "classList" ? no() : k === "length" ? 0 : k === Symbol.toPrimitive ? () => "" : no()), apply: () => no(), set: () => true });
  const ctx = {
    console, setTimeout, clearTimeout, Math, JSON,
    document: { getElementById: () => no(), createElement: () => no(), createElementNS: () => no(), addEventListener: nada, querySelector: () => no(), querySelectorAll: () => [], documentElement: no(), body: no() },
    localStorage: { getItem: () => null, setItem: nada, removeItem: nada },
    vista: { projetaXY: (x, y, z) => [100 * x + 30 * y, -100 * z + 20 * y], ferramenta: null, extra: null, pontos: null, hud: null, desenha: nada },
    msg: nada, muda: f => f(), agenda: nada, addEventListener: nada, removeEventListener: nada,
    ...extras,
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const a of arquivos) vm.runInContext(readFileSync(join(WEB, a), "utf8"), ctx, { filename: a });
  return nome => vm.runInContext(nome, ctx);
}
