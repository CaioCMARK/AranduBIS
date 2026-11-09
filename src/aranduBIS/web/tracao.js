"use strict";

const Tracao = (() => {
  const CHAVE = "aranduBIS.tracao";
  let v = { motor: "Scorpion SII-4035-330", helice: "22x10E", P_w: 600, rho: 1.1, V_max: 30, realista: true, celulas: "", v_celula: 3.6, capacidade_Ah: null, taxa_C: null };
  try { Object.assign(v, JSON.parse(localStorage.getItem(CHAVE) || "{}")); } catch (e) {  }
  let cat = null, res = null, tempo = null, seq = 0;
  const guarda = () => { try { localStorage.setItem(CHAVE, JSON.stringify(v)); } catch (e) {  } };
  const el = (tag, txt, cls) => Object.assign(document.createElement(tag), { textContent: txt || "", className: cls || "" });

  function escolha(rot, chave, opcoes, dica) {
    const l = el("label", rot); l.title = dica;
    const s = document.createElement("select");
    opcoes.forEach(([val, txt]) => { const o = el("option", txt); o.value = val; s.append(o); });
    s.value = v[chave];
    s.onchange = () => { v[chave] = s.value; guarda(); agenda(); };
    return [l, s];
  }

  function parametros() {
    const P = $("par2"); P.innerHTML = ""; $("tit_par2").textContent = "Motor e hélice";
    const G = document.createElement("div"); G.className = "prop"; P.append(G);
    if (!cat) { G.append(el("label", "Carregando o catálogo…")); return; }
    G.append(...escolha("Motor", "motor", cat.motores.map(m => [m.nome, `${m.nome} (${m.Kv} kV)`]), "Kv, R e I0 do catálogo do fabricante."));
    G.append(...escolha("Hélice APC", "helice", cat.helices.map(h => [h.nome, h.nome]), "Catálogo APC Thin Electric: só existem os pares diâmetro x passo vendidos."));
    [["P_w", "Potência na bateria (W)"], ["rho", "Densidade do ar (kg/m³)"], ["V_max", "Até a velocidade (m/s)"]].forEach(([k, r]) => {
      G.append(el("label", r), entrada("number", v[k], x => { if (x === null || !(x > 0)) { msg("Valor inválido em “" + r + "”.", true); parametros(); return; } v[k] = x; guarda(); agenda(); }));
    });
    const g2 = el("div", "Pack de bateria", "grupo-par"); P.append(g2);
    const H = document.createElement("div"); H.className = "prop"; P.append(H);
    H.append(...escolha("Células em série", "celulas", [["", "sem limite"], ["4", "4S"], ["5", "5S"], ["6", "6S"]], "A tensão do pack (células × V por célula) limita a rotação do motor."));
    [["v_celula", "V por célula sob carga", "3,6 V é hipótese; sob 40 A uma célula pequena cai bem abaixo da nominal."],
     ["capacidade_Ah", "Capacidade (Ah)", "Com a taxa C dá a corrente máxima do pack. Vazio = sem limite de corrente."],
     ["taxa_C", "Taxa de descarga (C)", "Vazio = sem limite de corrente."]].forEach(([k, r, d]) => {
      const l = el("label", r); l.title = d;
      const i = entrada("number", v[k], x => { if (x !== null && !(x > 0)) { msg("Valor inválido em “" + r + "”.", true); parametros(); return; } v[k] = x; guarda(); agenda(); });
      i.title = d; if (v[k] === null) i.placeholder = "sem limite"; H.append(l, i);
    });
    const l = el("label", "Perdas realistas"); l.title = "Enrolamento a 70 °C, perdas em vazio crescendo com a rotação e ESC com curva. Desligado = modelo simples.";
    const c = document.createElement("input"); c.type = "checkbox"; c.checked = v.realista;
    c.onchange = () => { v.realista = c.checked; guarda(); agenda(); };
    G.append(l, c);
  }

  function agenda() { clearTimeout(tempo); tempo = setTimeout(calcula, 150); }

  async function calcula() {
    const meu = ++seq;
    try {
      const r = await chama("/api/propulsao", Object.assign({}, v, { celulas: v.celulas ? +v.celulas : null }));
      if (meu !== seq) return;
      if (r.erro) { res = null; msg(r.erro, true); } else { res = r; msg("Pronto"); }
    } catch (e) { if (meu !== seq) return; res = null; msg(e.message, true); }
    mostra();
  }

  function veredito() {
    const V = $("veredito"); V.hidden = false; V.className = "veredito";
    if (!res) { V.textContent = "—"; return; }
    const mot = cat.motores.find(m => m.nome === res.motor), Ipk = Math.max(...res.I);
    V.classList.add((mot && mot.I_max && Ipk > mot.I_max) || res.limite[0] ? "ruim" : "ok");
    V.innerHTML = `<b>Tração estática ${fmt(res.T0, 1)} N</b> a ${fmt(res.P_w, 0)} W · ${fmt(res.rpm0, 0)} rpm · ${fmt(res.I[0], 0)} A a ${fmt(res.U[0], 1)} V`
      + ` · ${fmt(res.T[res.T.length - 1], 1)} N a ${fmt(res.V[res.V.length - 1], 0)} m/s`;
  }

  function graficos() {
    const C = $("graficos2"); C.innerHTML = "";
    const a = el("div", "", "graf"), b = el("div", "", "graf"); C.append(a, b);
    if (!res) return;
    const desenha = () => {
      Grafico.desenha(a, { titulo: "Tração × velocidade", xlab: "V (m/s)", ylab: "T (N)", series: [{ x: res.V, y: res.T, cor: "#4a86c5" }] });
      Grafico.desenha(b, { titulo: "Rotação e corrente × velocidade", xlab: "V (m/s)", ylab: "corrente (A)", series: [{ x: res.V, y: res.I, cor: "#d98a3d" }] });
    };
    desenha();
    if (!C._obs) { C._obs = true; Grafico.liga(C, () => { if (res && Analise.nome() === "tracao") desenha(); }); }
  }

  function baixo() {
    const A = $("abas2"); A.innerHTML = ""; A.append(el("div", "Pontos", "at"));
    const C = $("conteudo2"); C.innerHTML = "";
    if (!res) return;
    const t = document.createElement("table");
    t.innerHTML = "<tr><th>V (m/s)</th><th>T (N)</th><th>rpm</th><th>I (A)</th><th>tensão (V)</th><th>η hélice</th></tr>"
      + res.V.map((x, i) => `<tr><td>${fmt(x, 1)}</td><td>${fmt(res.T[i], 1)}</td><td>${fmt(res.rpm[i], 0)}</td><td>${fmt(res.I[i], 1)}</td><td>${fmt(res.U[i], 1)}</td><td>${fmt(res.eta_prop[i], 2)}</td></tr>`).join("");
    C.append(t);
    const b = el("button", "Usar esta tração na Decolagem"); b.title = "A Decolagem passa a usar a curva T(V) completa, no lugar da reta";
    b.onclick = () => { Decolagem.aplicaTracao(res.V, res.T, `${res.motor} + ${res.helice}`); msg("Curva de tração levada para a Decolagem."); };
    C.append(b);
    res.avisos.forEach(a => C.append(el("div", a, "nota")));
  }

  function mostra() { if (Analise.nome() !== "tracao") return; parametros(); veredito(); graficos(); baixo(); }

  Analise.registra("tracao", {
    async pinta() {
      $("graficos2").className = "graficos";
      if (!cat) { parametros(); try { cat = await chama("/api/propulsao", { lista: true }); } catch (e) { msg(e.message, true); return; } }
      parametros(); agenda(); if (res) mostra();
    },
  });
  return { dados: () => ({ v, res }) };
})();
