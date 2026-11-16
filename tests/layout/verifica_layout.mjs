import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const URL = process.env.ARANDU_URL || "http://127.0.0.1:8741/";
const PRINTS = process.argv[2] || null;
const CANDIDATOS = [process.env.CHROME, "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"].filter(Boolean);
const CHROME = CANDIDATOS.find(existsSync);
if (!CHROME) { console.log("Chrome/Edge nao encontrado: defina a variavel CHROME. Verificacao pulada."); process.exit(0); }

const TAMANHOS = [[1024, 640, 1], [1280, 720, 1.25], [1366, 768, 1], [1600, 900, 2], [1920, 1080, 1], [2560, 1440, 1]];
const TEMAS = ["escuro", "cinza", "claro"];
const espera = ms => new Promise(r => setTimeout(r, ms));
const perfil = mkdtempSync(join(tmpdir(), "arandu-layout-"));
const PORTA = 9340 + Math.floor(Math.random() * 50);
const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORTA}`, "--user-data-dir=" + perfil, "--hide-scrollbars",
  "--no-first-run", "--disable-gpu", "about:blank"], { stdio: "ignore" });

let ws;
const erros = [];
async function main() {
  let alvo;
  for (let i = 0; i < 60 && !alvo; i++) {
    try { alvo = (await (await fetch(`http://127.0.0.1:${PORTA}/json`)).json()).find(x => x.type === "page"); } catch (e) {  }
    if (!alvo) await espera(250);
  }
  if (!alvo) throw new Error("Chrome nao respondeu");
  ws = new WebSocket(alvo.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  let id = 0; const pend = new Map();
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
    else if (d.method === "Runtime.exceptionThrown") erros.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
    else if (d.method === "Runtime.consoleAPICalled" && d.params.type === "error") erros.push(d.params.args.map(a => a.value ?? a.description).join(" "));
  };
  const cdp = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const js = async e => (await cdp("Runtime.evaluate", { expression: e, awaitPromise: true, returnByValue: true })).result.result?.value;
  await cdp("Page.enable"); await cdp("Runtime.enable");
  if (PRINTS) mkdirSync(PRINTS, { recursive: true });

  let falhas = 0;
  for (const tema of TEMAS) for (const [w, h, dpr] of TAMANHOS) {
    await cdp("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: dpr, mobile: false });
    await cdp("Page.navigate", { url: URL }); await espera(1800);
    await js(`(async()=>{ Tema.escolhe(${JSON.stringify(tema)}); carrega(await chama("/api/exemplo?nome=biplano%2Fbiplano_b.json"), "biplano"); return 1 })()`);
    await espera(2500);
    const r = JSON.parse(await js(`JSON.stringify((()=>{
      const alt = s => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().height) : -1; };
      const vis = s => [...document.querySelectorAll(s)].filter(e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4; }).length;
      return { tema: document.documentElement.dataset.tema, barra: alt("#barra"), botoes: vis("#barra button"), etapas: alt(".etapas"),
               rolaX: document.documentElement.scrollWidth > innerWidth + 1, rolaY: document.documentElement.scrollHeight > innerHeight + 1,
               vista: alt(".vista"), canvasOK: document.getElementById("cv").width > 0 };
    })())`));
    const problemas = [];
    if (r.tema !== tema) problemas.push("tema nao aplicado");
    if (r.barra < 24) problemas.push(`barra de ferramentas com ${r.barra}px`);
    if (r.botoes < 8) problemas.push(`so ${r.botoes} botoes visiveis na barra`);
    if (r.etapas < 20) problemas.push("abas das etapas sumiram");
    if (r.rolaX) problemas.push("rolagem horizontal na pagina");
    if (r.rolaY) problemas.push("rolagem vertical na pagina");
    if (r.vista < 100 || !r.canvasOK) problemas.push("vista 3D sem area");
    if (PRINTS) {
      const s = await cdp("Page.captureScreenshot", { format: "png" });
      writeFileSync(join(PRINTS, `${tema}_${w}x${h}@${dpr}.png`), Buffer.from(s.result.data, "base64"));
    }
    console.log(`${problemas.length ? "FALHA" : "ok   "} ${tema.padEnd(6)} ${w}x${h} @${dpr}  barra=${r.barra}px botoes=${r.botoes}` + (problemas.length ? "  -> " + problemas.join("; ") : ""));
    falhas += problemas.length ? 1 : 0;
  }
  if (erros.length) { console.log("Erros no console:"); [...new Set(erros)].slice(0, 10).forEach(e => console.log("  " + e)); }
  return falhas + (erros.length ? 1 : 0);
}
let codigo = 1;
try { codigo = (await main()) ? 1 : 0; } catch (e) { console.log("ERRO:", e.message); }
try { ws && ws.close(); } catch (e) {  }
proc.kill(); await espera(500);
try { rmSync(perfil, { recursive: true, force: true }); } catch (e) {  }
console.log(codigo ? "RESULTADO: falhou" : "RESULTADO: tudo certo");
process.exit(codigo);
