"use strict";

const Vibracao3 = (() => {
  const CHAVE = "aranduBIS.vibracao";
  const COR = ["#4a86c5", "#d98a3d", "#6aa84f", "#8c7a2e", "#8e6bbf", "#3aa6a6", "#b09040", "#777"];
  let v = { usar_curva: true, rpm_min: 3000, rpm_max: 9000, n_pas: 2, margem_min: 20, ordens_extra: "", incluir_asas: true, massa_empenagem_h_kg: null, massa_deriva_kg: null,
    massa_motor_kg: null, pos_motor: [null, null, null], suporte_usar: false, suporte: { comprimento_m: 0.08, de_m: 0.02, di_m: 0.018 }, adicionais: [] };
  let res = null, tempo = null, seq = 0;
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  const ativa = () => Etapa3.ativa() && Etapa3.nome() === "vibracao";
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });
  const pct = x => fmt(100 * x, 0) + " %";
  const SIT = { dentro: "dentro da faixa", perto: "perto", ok: "afastado" };

  function corpo() {
    const t = Tracao.dados().v, c = {
      esquema: esq, materiais: Asa3.materiais(), x_apoio: Cauda3.dados().v.x_apoio, incluir_asas: !!v.incluir_asas, n_pas: v.n_pas || 2, margem_min: (v.margem_min || 20) / 100,
      massa_empenagem_h_kg: v.massa_empenagem_h_kg || 0, massa_deriva_kg: v.massa_deriva_kg || 0, massa_motor_kg: v.massa_motor_kg || 0,
      adicionais: v.adicionais.filter(a => a.massa_kg > 0), ordens_extra: String(v.ordens_extra || "").split(/[\s,;]+/).map(Number).filter(x => x > 0),
    };
    if (v.pos_motor.every(x => x !== null)) c.pos_motor = v.pos_motor;
    if (v.suporte_usar) c.suporte_motor = v.suporte;
    if (v.usar_curva) Object.assign(c, { motor: t.motor, helice: t.helice, P_w: t.P_w, rho: t.rho, V_max: t.V_max, realista: t.realista });
    else Object.assign(c, { rpm_min: v.rpm_min, rpm_max: v.rpm_max });
    const m = MassaAsa3.dados().v;
    if (m && m.usar) c.massa_real = { usar: true, adicionais: m.adicionais.filter(a => a.massa_kg || a.gramatura_g_m2), medidas: m.medidas };
    return c;
  }

  function campo(P, rot, dica, valor, ao, extra) {
    const l = el("label", rot); l.title = dica;
    const i = entrada("number", valor, x => { ao(x); guarda(); agenda(); }, extra || {}); i.title = dica; P.append(l, i);
    return i;
  }

  function parametros() {
    const P = $("par3"); P.innerHTML = ""; $("tit_par3").textContent = "Vibração da cauda e do motor";
    let G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Massas (a cauda vibra com elas, não vazia)", "grupo-par"), G);
    campo(G, "Empenagem horizontal (kg)", "Massa da horizontal montada (balsa, filme, servo do profundor). Espalhada em 5 pontos na envergadura para dar a inércia de rolagem.", v.massa_empenagem_h_kg, x => { v.massa_empenagem_h_kg = x; });
    campo(G, "Deriva (kg)", "Massa da deriva montada (com o servo do leme). Espalhada na altura.", v.massa_deriva_kg, x => { v.massa_deriva_kg = x; });
    campo(G, "Motor + hélice (kg)", "Massa do conjunto. Entra nos modos da cauda se a posição abaixo cair em cima da treliça; para o suporte do motor, é a massa na ponta do balanço.", v.massa_motor_kg, x => { v.massa_motor_kg = x; });
    G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Posição do motor (opcional, m)", "grupo-par"), G);
    ["x", "y", "z"].forEach((r, k) => campo(G, r, "Se o motor estiver a menos de 150 mm da treliça livre, a massa entra nos modos da cauda; senão ele está no apoio (fuselagem).", v.pos_motor[k], x => { v.pos_motor[k] = x; }));
    G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Suporte do motor (balanço de tubo)", "grupo-par"), G);
    const c = document.createElement("input"); c.type = "checkbox"; c.checked = !!v.suporte_usar; c.onchange = () => { v.suporte_usar = c.checked; guarda(); agenda(); };
    const lc = el("label", "Calcular o suporte"); lc.title = "Tubo em balanço com o conjunto motor + hélice na ponta (flexão; Euler-Bernoulli, 33/140 da massa do tubo)."; G.append(lc, c);
    [["comprimento_m", "Comprimento (m)"], ["de_m", "Diâmetro externo (m)"], ["di_m", "Diâmetro interno (m)"]].forEach(([k, r]) => campo(G, r, "Do tubo que segura o motor.", v.suporte[k], x => { v.suporte[k] = x; }));
    G = document.createElement("div"); G.className = "prop"; P.append(el("div", "Excitação da hélice", "grupo-par"), G);
    const cc = document.createElement("input"); cc.type = "checkbox"; cc.checked = !!v.usar_curva; cc.onchange = () => { v.usar_curva = cc.checked; guarda(); agenda(); parametros(); };
    const lcc = el("label", "Faixa de rpm da curva motor + hélice"); lcc.title = "Ligado: usa a rotação da vista Tração (motor, hélice e potência de lá) de parado até a velocidade máxima, e mostra a velocidade de voo de cada ressonância."; G.append(lcc, cc);
    if (!v.usar_curva) {
      campo(G, "rpm mínima", "Menor rotação em operação.", v.rpm_min, x => { v.rpm_min = x; });
      campo(G, "rpm máxima", "Maior rotação em operação.", v.rpm_max, x => { v.rpm_max = x; });
    } else {
      const t = Tracao.dados().v;
      G.append(el("div", `${t.motor} + ${t.helice}, ${fmt(t.P_w, 0)} W`, "nota"));
    }
    campo(G, "Número de pás", "A passagem das pás excita em n × rpm / 60.", v.n_pas, x => { v.n_pas = x; });
    campo(G, "Separação mínima (%)", "Regra usual: 20 % entre a frequência do modo e a de excitação em toda a faixa.", v.margem_min, x => { v.margem_min = x; });
    const i = entrada("text", v.ordens_extra, x => { v.ordens_extra = x; guarda(); agenda(); }); i.placeholder = "ex.: 2 4"; i.title = "Outras ordens de rotação a verificar (separadas por espaço)."; G.append(el("label", "Outras ordens"), i);
    const ca = document.createElement("input"); ca.type = "checkbox"; ca.checked = !!v.incluir_asas; ca.onchange = () => { v.incluir_asas = ca.checked; guarda(); agenda(); };
    const la = el("label", "Incluir modos das asas"); la.title = "Os três primeiros modos de cada asa com estrutura (usa a massa real, se ligada, e a calibração)."; G.append(la, ca);
    P.append(el("div", "Apoio da treliça e materiais: os da vista Cauda e Configurações.", "nota"));
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 500); }

  async function calcula() {
    const meu = ++seq;
    if (!esq || !esq.elementos.length) { res = null; msg("Abra ou desenhe uma aeronave na etapa 1.", true); mostra(true); return; }
    msg("Calculando os modos e as ressonâncias…");
    try {
      const r = await chama("/api/vibracao", corpo());
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra(true);
  }

  function veredito() {
    const V = $("veredito3"); V.hidden = false; V.className = "veredito neutro";
    if (!res) { V.textContent = "Informe as massas da empenagem, da deriva e do motor e a faixa de rotação."; return; }
    const d = res.ressonancias.filter(r => r.situacao === "dentro"), p = res.ressonancias.filter(r => r.situacao === "perto");
    V.classList.remove("neutro"); V.classList.add(d.length ? "ruim" : p.length ? "neutro" : "ok");
    const f1 = res.modos.find(m => !m.local);
    const pior = d[0] || p[0];
    V.innerHTML = `<b>${d.length ? d.length + " ressonância" + (d.length > 1 ? "s" : "") + " dentro da faixa " + fmt(res.faixa_rpm[0], 0) + " a " + fmt(res.faixa_rpm[1], 0) + " rpm" : p.length ? "Nenhuma ressonância na faixa, " + p.length + " perto (menos de " + pct(res.margem_min) + ")" : "Todos os modos afastados da excitação em pelo menos " + pct(res.margem_min)}</b>`
      + (pior ? ` · pior: ${pior.modo} com ${pior.ordem} (${fmt(pior.f_modo_hz, 1)} Hz, ${fmt(pior.rpm_ressonancia, 0)} rpm${pior.V_ms != null ? ", " + fmt(pior.V_ms, 1) + " m/s" : ""})` : "")
      + (f1 ? ` · 1º modo da cauda ${fmt(f1.f_hz, 1)} Hz (${f1.natureza}), ${fmt(res.massa_somada_kg * 1000, 0)} g somados à treliça de ${fmt(res.massa_trelica_kg * 1000, 0)} g` : "")
      + (res.suporte_motor ? ` · suporte do motor ${fmt(res.suporte_motor.f_hz, 0)} Hz` : "");
  }

  function graficos() {
    const C = $("graficos3"); C.innerHTML = "";
    if (!res) return;
    const g = [0, 1].map(() => el("div", "", "graf")); C.append(...g);
    const c = res.campbell, [a, b] = res.faixa_rpm;
    const desenha = () => {
      const ords = c.ordens.map((o, i) => ({ nome: o.nome, x: c.rpm, y: o.f_hz, cor: COR[i % COR.length] }));
      const modos = c.modos.map((m, i) => ({ nome: "", x: [a, b], y: [m.f_hz, m.f_hz], cor: "#888", tracejado: true }));
      const pontos = res.ressonancias.filter(r => r.situacao === "dentro").map(r => ({ x: r.rpm_ressonancia, y: r.f_modo_hz, cor: "#b9831a" }));
      const ymax = Math.max(...c.ordens.map(o => o.f_hz[o.f_hz.length - 1])) * 1.6;
      Grafico.desenha(g[0], { titulo: "Diagrama de Campbell (linhas cinza = modos)", xlab: "rotação (rpm)", ylab: "Hz", yMin: 0, yMax: ymax, series: ords.concat(modos), pontos });
      if (res.rpm_v) {
        const V = res.rpm_v.V, R = res.rpm_v.rpm;
        const s = c.ordens.map((o, i) => ({ nome: o.nome, x: V, y: R.map(r => o.ordem * r / 60), cor: COR[i % COR.length] }));
        const m2 = c.modos.map(m => ({ nome: "", x: [V[0], V[V.length - 1]], y: [m.f_hz, m.f_hz], cor: "#888", tracejado: true }));
        Grafico.desenha(g[1], { titulo: "Excitação ao longo do voo (rotação da curva motor + hélice)", xlab: "V (m/s)", ylab: "Hz", yMin: 0, yMax: ymax, series: s.concat(m2) });
      } else {
        const ms = res.modos.filter(m => !m.local);
        Grafico.desenha(g[1], { titulo: "Frequência dos modos da cauda: com massas × tubo vazio", xlab: "modo", ylab: "Hz (escala linear)", series: [
          { nome: "com as massas", x: ms.map(m => m.i), y: ms.map(m => m.f_hz), cor: COR[0] }, { nome: "tubo vazio", x: ms.map(m => m.i), y: ms.map(m => m.f_sem_massas_hz), cor: COR[1], tracejado: true }] });
      }
    };
    desenha();
    if (!C._obsc) { C._obsc = true; Grafico.liga(C, () => { if (res && ativa()) desenha(); }); }
  }

  function adicionais(C) {
    C.append(el("div", "Outras massas na treliça (câmera, bateria no boom, antena…)", "grupo-par"));
    const T = document.createElement("table");
    T.innerHTML = "<tr><th>nome</th><th>massa (kg)</th><th>x (m)</th><th>y (m)</th><th>z (m)</th><th></th></tr>";
    v.adicionais.forEach((a, i) => {
      const tr = document.createElement("tr");
      [["nome", "text", "120px"], ["massa_kg", "number", "70px"], ["x", "number", "60px"], ["y", "number", "60px"], ["z", "number", "60px"]].forEach(([k, t, w]) => {
        const td = document.createElement("td"); td.append(entrada(t, a[k], x => { a[k] = x === null ? 0 : x; guarda(); agenda(); }, { style: "width:" + w })); tr.append(td);
      });
      const td = document.createElement("td"), b = el("button", "✕"); b.onclick = () => { v.adicionais.splice(i, 1); guarda(); agenda(); mostra(true); }; td.append(b); tr.append(td);
      T.append(tr);
    });
    C.append(T);
    const b = el("button", "+ massa"); b.onclick = () => { v.adicionais.push({ nome: "massa", massa_kg: 0.05, x: 0.8, y: 0, z: 0 }); guarda(); mostra(true); };
    C.append(b);
  }

  function baixo() {
    const A = $("abas3"); A.innerHTML = ""; A.append(el("div", "Modos e ressonâncias", "at"));
    const C = $("conteudo3"); C.innerHTML = "";
    adicionais(C);
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>modo</th><th>com as massas (Hz)</th><th>tubo vazio (Hz)</th><th>natureza</th><th>massa mobilizada (y / z)</th></tr>"
      + res.modos.map(m => `<tr><td>${m.i}</td><td>${fmt(m.f_hz, 1)}</td><td>${fmt(m.f_sem_massas_hz, 1)}</td><td>${m.natureza}</td><td>${m.local ? "local" : pct(m.massa_efetiva.y) + " / " + pct(m.massa_efetiva.z)}</td></tr>`).join("");
    C.append(el("div", "Modos da treliça da cauda (engastada no apoio)", "grupo-par"), t);
    if (res.suporte_motor) {
      const s = res.suporte_motor;
      C.append(el("div", `Suporte do motor: tubo ${fmt(1000 * s.de_m, 1)} × ${fmt(1000 * s.di_m, 1)} mm, ${fmt(1000 * s.L_m, 0)} mm em balanço, ${fmt(1000 * s.massa_conjunto_kg, 0)} g na ponta: ${fmt(s.f_hz, 1)} Hz (EI = ${fmt(s.EI, 1)} N·m²).`, "nota"));
    }
    const r = document.createElement("table");
    r.innerHTML = "<tr><th>modo</th><th>f (Hz)</th><th>excitação</th><th>rpm de ressonância</th><th>V (m/s)</th><th>separação</th><th>situação</th></tr>"
      + res.ressonancias.slice(0, 24).map(x => `<tr class="${x.situacao === "dentro" ? "ruim" : ""}"><td>${x.modo}</td><td>${fmt(x.f_modo_hz, 1)}</td><td>${x.ordem}</td><td>${fmt(x.rpm_ressonancia, 0)}</td><td>${x.V_ms != null ? fmt(x.V_ms, 1) : "—"}</td><td>${pct(x.separacao)}</td><td>${SIT[x.situacao]}</td></tr>`).join("");
    C.append(el("div", "Cruzamentos com a rotação (os piores primeiro)", "grupo-par"), r);
    res.notas.forEach(x => C.append(el("div", x, "nota")));
    res.avisos.forEach(x => C.append(el("div", x, "nota")));
    C.append(el("div", "Modelo de vigas com nós rígidos (juntas coladas sem folga) e a fuselagem como apoio rígido: as frequências reais costumam ficar abaixo. O ideal é confrontar com um ensaio de impacto na cauda e calibrar. "
      + "1P é o desbalanceamento da hélice; nP, a passagem das pás pela esteira do motor e da fuselagem. A ressonância só vira problema se o motor ficar na rotação por tempo (cruzeiro), não ao atravessá-la na decolagem.", "nota"));
  }

  function mostra(forca) { if (!ativa()) return; if (forca || !document.activeElement || document.activeElement.tagName !== "INPUT") { parametros(); veredito(); graficos(); baixo(); } }
  Etapa3.registra("vibracao", { pinta() { parametros(); veredito(); baixo(); agenda(); } });
  return { dados: () => ({ v, res }), corpo };
})();
