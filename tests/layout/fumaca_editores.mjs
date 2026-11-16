import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const URL = process.env.ARANDU_URL || "http://127.0.0.1:8741/";
const CANDIDATOS = [process.env.CHROME, "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome", "/usr/bin/chromium", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"].filter(Boolean);
const CHROME = CANDIDATOS.find(existsSync);
if (!CHROME) { console.log("Chrome/Edge nao encontrado: defina a variavel CHROME. Verificacao pulada."); process.exit(0); }

const espera = ms => new Promise(r => setTimeout(r, ms));
const perfil = mkdtempSync(join(tmpdir(), "arandu-fumaca-"));
const PORTA = 9460 + Math.floor(Math.random() * 50);
const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORTA}`, "--user-data-dir=" + perfil, "--hide-scrollbars", "--no-first-run", "--disable-gpu", "about:blank"], { stdio: "ignore" });

const PREPARA = `(() => {
  const R = () => vista.cv.getBoundingClientRect();
  window.ev = (t, x, y, o = {}) => (t === "mousedown" ? vista.cv : window).dispatchEvent(new MouseEvent(t, { bubbles: true, clientX: R().left + x, clientY: R().top + y, button: 0, ...o }));
  window.clica = (p, o) => { const q = vista.projetaXY(...p); ev("mousedown", q[0], q[1], o); ev("mouseup", q[0], q[1], o); };
  window.tec = (k, o = {}) => window.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, ...o }));
  window.pausa = ms => new Promise(r => setTimeout(r, ms));
  return 1;
})()`;

const TESTES = [
  ["interface nova carregada", `JSON.stringify({ ok: Interface.nova && document.querySelectorAll(".paleta button").length === 7 && !!document.getElementById("inspetor") })`],
  ["nos: inspetor move o no e o par simetrico, e desfaz", `(async () => {
    Interface.ativa("nos"); await pausa(300);
    const e = elemento(), s = No3D.selecao(), antes = e.nos[s.id].slice(), i = document.querySelector("#inspetor input");
    i.value = (+i.value + 5).toFixed(1); i.dispatchEvent(new Event("change")); await pausa(100);
    const moveu = Math.abs(elemento().nos[s.id][0] - antes[0] - 0.005) < 1e-6;
    desfaz(); await pausa(100);
    return JSON.stringify({ ok: e.tipo === "trelica" && moveu && Math.abs(elemento().nos[s.id][0] - antes[0]) < 1e-9 });
  })()`],
  ["nos: grupo, copiar, colar e espelhar", `(async () => {
    const e = elemento(), A = No3D.puro.alcas(e), n0 = e.nos.length;
    clica(A[4].p); clica(A[9].p, { shiftKey: true });
    const g = No3D.puro.grupo.size; tec("c", { ctrlKey: true }); tec("v", { ctrlKey: true });
    const n1 = elemento().nos.length; tec("i"); const n2 = elemento().nos.length;
    desfaz(); desfaz(); await pausa(100);
    return JSON.stringify({ ok: g === 2 && n1 === n0 + 2 && n2 === n0 + 4 && elemento().nos.length === n0 });
  })()`],
  ["nervuras: seleciona e move pelo inspetor", `(async () => {
    Interface.ativa("nervuras"); await pausa(2500);
    const s = Nervura3D.selecao(), i = document.querySelector("#inspetor input");
    if (!s || s.y === null || !i) return JSON.stringify({ ok: false, s });
    i.value = (s.y * 1000 + 3).toFixed(1); i.dispatchEvent(new Event("change")); await pausa(100);
    const y = Nervura3D.selecao().y; desfaz(); await pausa(100);
    return JSON.stringify({ ok: Math.abs(y - s.y - 0.003) < 1e-6 });
  })()`],
  ["medir: distancia entre dois nos", `(async () => {
    Interface.ativa("medir"); await pausa(200);
    const t = esq.elementos.find(e => e.tipo === "trelica"), o = t.posicao || [0, 0, 0], a = t.nos[0].map((v, k) => v + o[k]), b = t.nos[5].map((v, k) => v + o[k]);
    clica(a); clica(b);
    const esperado = (Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) * 1000).toFixed(1);
    const ok = (vista.hud || [""])[0].includes(esperado);
    Interface.ativa("selecionar");
    return JSON.stringify({ ok, hud: vista.hud, esperado });
  })()`],
  ["perfil 2D: abre, gera NACA e aplica; menu de contexto", `(async () => {
    const e = esq.elementos.findIndex(x => (x.tipo || "asa") === "asa" && Array.isArray(x.secoes)); seleciona(e); await pausa(300);
    Interface.ativa("perfil"); await pausa(1200);
    const d = document.getElementById("dlg_perfil"), abriu = d.open, n = Perfil2D.estado().P.length;
    const ent = [...d.querySelectorAll(".c2-painel input")];
    ent[2].value = 3; ent[2].dispatchEvent(new Event("change")); ent[4].value = 10; ent[4].dispatchEvent(new Event("change"));
    [...d.querySelectorAll("button")].find(b => b.textContent === "Gerar").click(); await pausa(200);
    const cod = Perfil2D.estado().nacaCod;
    [...d.querySelectorAll("button")].find(b => b.textContent === "Aplicar").click(); await pausa(600);
    const perfil = elemento().perfil;
    document.querySelectorAll("#lista > div")[e].dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, clientX: 100, clientY: 260 })); await pausa(200);
    const itens = document.querySelectorAll(".menu-pop.contexto .menu-item").length;
    document.querySelector(".menu-pop.contexto .menu-item").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); await pausa(100);
    const fechou = !document.querySelector(".menu-pop.contexto");
    return JSON.stringify({ ok: abriu && n > 20 && cod === "3010" && perfil === "NACA 3010" && itens >= 6 && fechou, abriu, n, cod, perfil, itens, fechou });
  })()`],
  ["chapa 2D: abre, cria furo e aplica", `(async () => {
    const s = document.getElementById("s_inserir"); s.value = "placa"; s.dispatchEvent(new Event("change")); await pausa(400);
    Interface.ativa("chapa"); await pausa(300);
    const d = document.getElementById("dlg_chapa"), svg = d.querySelector("svg"), R = svg.getBoundingClientRect();
    const e2 = (t, x, y) => (t === "mousedown" ? svg : window).dispatchEvent(new MouseEvent(t, { bubbles: true, clientX: R.left + x, clientY: R.top + y, button: 0 }));
    d.querySelector("[data-ferr=furo]").click();
    e2("mousedown", R.width / 2, R.height / 2); e2("mousemove", R.width / 2 + 30, R.height / 2); e2("mouseup", R.width / 2 + 30, R.height / 2);
    const furos = Chapa2D.estado().F.length;
    [...d.querySelectorAll(".c2-acoes button")].find(b => b.textContent === "Aplicar").click(); await pausa(200);
    const e = elemento(), ok = furos === 1 && !d.open && e.tipo === "placa" && (e.furos || []).length === 1;
    desfaz(); desfaz(); await pausa(200);
    return JSON.stringify({ ok, furos });
  })()`],
  ["comandos e atalhos abrem", `(async () => {
    tec("k", { ctrlKey: true }); await pausa(100);
    const c = document.getElementById("dlg_comandos"), n = c.querySelectorAll(".cmd").length; c.close();
    tec("?"); await pausa(100);
    const a = document.getElementById("dlg_atalhos"), k = a.querySelectorAll("kbd").length; a.close();
    return JSON.stringify({ ok: n > 20 && k > 30 });
  })()`],
];

let ws; const erros = []; let falhas = 0;
try {
  let alvo;
  for (let i = 0; i < 60 && !alvo; i++) { try { alvo = (await (await fetch(`http://127.0.0.1:${PORTA}/json`)).json()).find(x => x.type === "page"); } catch (e) {  } if (!alvo) await espera(250); }
  if (!alvo) throw new Error("Chrome nao respondeu");
  ws = new WebSocket(alvo.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
  let id = 0; const pend = new Map();
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
    else if (d.method === "Runtime.exceptionThrown") erros.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
    else if (d.method === "Runtime.consoleAPICalled" && d.params.type === "error") erros.push(d.params.args.map(a => a.value ?? a.description).join(" "));
  };
  const cdp = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const js = async e => { const r = await cdp("Runtime.evaluate", { expression: e, awaitPromise: true, returnByValue: true }); return r.result.exceptionDetails ? JSON.stringify({ ok: false, excecao: r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text }) : r.result.result?.value; };
  await cdp("Page.enable"); await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await cdp("Page.navigate", { url: URL }); await espera(1500);
  await js(`localStorage.setItem("aranduBIS.inicio.visto", "1"); localStorage.setItem("aranduBIS.interface", "nova"); 1`);
  await cdp("Page.navigate", { url: URL }); await espera(2000);
  await js(`(async () => { carrega(await chama("/api/exemplo?nome=monoplano%2Fmonoplano_a.json"), "monoplano_a"); return 1; })()`);
  for (let i = 0; i < 90; i++) { await espera(1000); if (await js(`!!(malha && esq && esq.nome === "monoplano_a" && malha.zonas.some(z => z.startsWith("montante_tubos.")))`)) break; }
  await js(PREPARA);
  for (const [nome, codigo] of TESTES) {
    let r; try { r = JSON.parse(await js(codigo)); } catch (e) { r = { ok: false, erro: String(e) }; }
    console.log(`${r.ok ? "ok   " : "FALHA"} ${nome}` + (r.ok ? "" : "  -> " + JSON.stringify(r)));
    falhas += r.ok ? 0 : 1;
  }
  if (erros.length) { console.log("Erros no console:"); [...new Set(erros)].slice(0, 10).forEach(e => console.log("  " + e)); falhas++; }
} catch (e) { console.log("ERRO:", e.message); falhas++; }
try { ws && ws.close(); } catch (e) {  }
proc.kill(); await espera(400);
try { rmSync(perfil, { recursive: true, force: true }); } catch (e) {  }
console.log(falhas ? `RESULTADO: ${falhas} falha(s)` : "RESULTADO: tudo certo");
process.exit(falhas ? 1 : 0);
