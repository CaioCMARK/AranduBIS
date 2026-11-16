from __future__ import annotations

import numpy as np

from .modelador import aeronave_geometria as AG

LIPO_WH_POR_KG = 133.0
FILMES_G_M2 = {"Oralight (36 g/m², fabricante)": 36.0, "Oracover (64 a 109 g/m² conforme a cor; média 87)": 87.0,
               "Oratex (90 a 110 g/m²; média 100)": 100.0}
MADEIRAS = {"balsa", "spruce", "liteply", "mdf"}

PADRAO = {"servo_g": None, "helice_g": None, "esc_g": None, "receptor_g": None, "cabos_g": None, "cola_pct": 10.0,
          "celulas": 6, "capacidade_Ah": 1.5, "motor": None}


def _servos(esq: dict) -> list[dict]:
    from .modelador.superficies_comando import resolve
    out = []
    for el in esq.get("elementos", []):
        if el.get("tipo", "asa") != "asa":
            continue
        sec = AG._secoes(el) if el.get("secoes") or el.get("secoes_lineares") else None
        pos = np.asarray(el.get("posicao", [0, 0, 0]), float)
        for c in el.get("controles", []):
            try:
                cr = resolve(c, el.get("secoes") or [])
            except Exception:
                cr = c
            y0, y1 = sorted(abs(float(v)) for v in cr["y"])
            lados = [1.0] if (c.get("modo") == "lado" or y0 < 1e-6 or (sec and min(q[1] for q in sec) >= -1e-9)) else [1.0, -1.0]
            ym = 0.5 * (y0 + y1)
            for s in lados:
                xyz = None
                if sec:
                    q = AG._secao_em(sec, s * ym)
                    xc = float(cr.get("xc", 0.75)) if "xc" in cr else 0.70
                    xyz = (pos + np.array([q[0] + xc * q[3], s * ym, q[2]])).tolist()
                out.append({"nome": f"servo_{c.get('nome', 'comando')}" + ("" if len(lados) == 1 else ("_dir" if s > 0 else "_esq")),
                            "superficie": c.get("nome"), "elemento": el["nome"], "posicao": xyz})
    return out


def calcula(esq: dict, opc: dict | None = None, motor_nome: str | None = None, mtow_kg: float | None = None) -> dict:
    o = {**PADRAO, **{k: v for k, v in (opc or {}).items() if v is not None and v != ""}}
    mc = AG.massa_e_cg(AG.constroi(esq))
    tipos = {e["nome"]: e.get("tipo", "asa") for e in esq.get("elementos", [])}
    estrutura, declarados, madeira = [], [], 0.0
    for q in mc["itens"]:
        dono = str(q["nome"]).split(".")[0]
        if tipos.get(dono) == "ponto":
            declarados.append({"item": q["nome"], "massa_kg": float(q["massa"]), "origem": "massa pontual declarada no modelo"})
            continue
        parte = str(q["nome"]).split(".", 1)[1] if "." in str(q["nome"]) else str(q["nome"])
        estrutura.append({"item": q["nome"], "elemento": dono, "parte": parte, "massa_kg": float(q["massa"]), "origem": q.get("origem", "")})
        orig = str(q.get("origem", ""))
        if any(m in orig for m in MADEIRAS) or any(k in parte for k in ("nervura", "longarina", "chapeado", "cruzadas")):
            if "tubo" not in parte:
                madeira += float(q["massa"])
    m_estr = sum(e["massa_kg"] for e in estrutura)
    com_massa = {e["elemento"] for e in estrutura} | {str(d["item"]).split(".")[0] for d in declarados}
    sem = [e["nome"] for e in esq.get("elementos", []) if e["nome"] not in com_massa and e.get("tipo") in ("corpo", "placa", "asa")
           and not (e.get("tipo") == "asa" and e.get("camada") == "estrutura" and not e.get("estrutura"))
           and not any(k in e["nome"].lower() for k in ("motor", "bateria", "helice", "hélice", "esc", "receptor", "servo"))]
    montagem = [{"item": "cola", "massa_kg": madeira * float(o["cola_pct"]) / 100.0,
                 "origem": f"{float(o['cola_pct']):g} % da madeira ({1000 * madeira:.0f} g): hipotese do usuário; pese uma peca colada e ajuste"}]
    sistemas, faltam = [], [f"{n} (desenhado sem material: sem massa)" for n in sem]
    nome_m = motor_nome or o.get("motor")
    if nome_m:
        from .aero.motor import CATALOGO
        mo = CATALOGO.get(nome_m)
        if mo is not None and mo.massa:
            sistemas.append({"item": "motor", "massa_kg": mo.massa / 1000.0, "origem": f"{nome_m}: catalogo do fabricante"})
        else:
            faltam.append(f"massa do motor {nome_m!r} (fora do catalogo)")
    else:
        faltam.append("motor")
    cel, ah = int(o["celulas"]), float(o["capacidade_Ah"])
    if cel > 0 and ah > 0:
        wh = cel * 3.7 * ah
        sistemas.append({"item": f"bateria {cel}S {1000 * ah:.0f} mAh", "massa_kg": wh / LIPO_WH_POR_KG,
                         "origem": f"{wh:.1f} Wh / {LIPO_WH_POR_KG:g} Wh/kg (media de packs 6S 1500 mAh do mercado, 218 a 283 g); pese a sua"})
    sv = _servos(esq)
    if sv:
        if o.get("servo_g") is not None:
            for s in sv:
                sistemas.append({"item": s["nome"], "massa_kg": float(o["servo_g"]) / 1000.0, "origem": "massa do servo informada", "posicao": s["posicao"],
                                 "elemento": s["elemento"]})
        else:
            faltam.append(f"massa do servo ({len(sv)} servos: um por superficie e por lado)")
    for k, rot in (("helice_g", "helice"), ("esc_g", "ESC"), ("receptor_g", "receptor"), ("cabos_g", "cabos, conectores e parafusos")):
        if o.get(k) is not None:
            sistemas.append({"item": rot, "massa_kg": float(o[k]) / 1000.0, "origem": "informada"})
        else:
            faltam.append(rot)
    m_mont = sum(x["massa_kg"] for x in montagem)
    m_sis = sum(x["massa_kg"] for x in sistemas)
    pv = m_estr + m_mont + m_sis
    por_el = {}
    for e in estrutura:
        por_el[e["elemento"]] = por_el.get(e["elemento"], 0.0) + e["massa_kg"]
    por_parte = {}
    for e in estrutura:
        chave = "tubos" if e["parte"].startswith("tubo") else "longarinas" if e["parte"].startswith("longarina") else "nervuras" if ("nervura" in e["parte"] or "cruzadas" in e["parte"]) else e["parte"].split(".")[-1]
        por_parte[chave] = por_parte.get(chave, 0.0) + e["massa_kg"]
    sai = {"estrutura": estrutura, "montagem": montagem, "sistemas": sistemas, "declarados": declarados,
           "estrutura_kg": m_estr, "montagem_kg": m_mont, "sistemas_kg": m_sis, "peso_vazio_kg": pv,
           "por_elemento": dict(sorted(por_el.items(), key=lambda kv: -kv[1])), "por_parte": dict(sorted(por_parte.items(), key=lambda kv: -kv[1])),
           "faltam": faltam, "servos": sv, "filmes": FILMES_G_M2,
           "avisos": ["Peso vazio sem a carga paga e sem as massas pontuais ja declaradas no modelo (listadas a parte)."]}
    if mtow_kg:
        sai["mtow_kg"] = float(mtow_kg)
        sai["carga_paga_max_kg"] = float(mtow_kg) - pv
    if faltam:
        sai["avisos"].append("Ainda sem numero: " + ", ".join(faltam) + ". O peso vazio fica abaixo do real ate preencher.")
    return sai


def servos_no_modelo(esq: dict, servo_g: float) -> dict:
    novo = {**esq, "elementos": [e for e in esq.get("elementos", []) if not str(e.get("nome", "")).startswith("servo_")]}
    for s in _servos(esq):
        if s["posicao"] is None:
            continue
        novo["elementos"].append({"nome": s["nome"], "tipo": "ponto", "massa": float(servo_g) / 1000.0, "posicao": s["posicao"],
                                  "fonte": f"calculadora de peso: servo de {s['superficie']}"})
    return novo
