from __future__ import annotations

import copy
import math

from .formula import ErroDeFormula, avaliar as _avalia, compilar, nomes_usados

_CAMPOS_ARANDU = {
    "CP_bruta": ("kg", "carga paga que a física previu, antes de qualquer teto", 0.0),
    "PV": ("kg", "peso vazio", 0.0),
    "PP": ("g", "peso do planador (só Advanced)", 0.0),
    "t": ("s", "tempo de retirada da carga", 0.0),
    "AP": ("", "1 se o planador pousou de barriga, 0 se não", 0.0),
    "pouso_valido": ("", "1 se o pouso foi válido", 1.0),
    "parada_na_area": ("", "1 se parou na área demarcada", 0.0),
    "voo_validado": ("", "1 se a bateria foi validada", 1.0),
}

def vazia(nome: str = "Nova regra") -> dict:
    return {"versao": 1, "nome": nome, "ano": 0, "classe": "", "fonte": "", "constantes": {},
            "entradas": [], "grandezas": [], "itens": [], "so_conta_se": ""}

def normaliza(d: dict) -> dict:
    r = vazia(d.get("nome", "Regra"))
    for k in ("ano", "classe", "fonte"):
        r[k] = d.get(k, r[k])
    r["constantes"] = dict(d.get("constantes", {}))
    if "entradas" in d:
        r["entradas"] = [dict(e) for e in d["entradas"]]
        r["so_conta_se"] = d.get("so_conta_se", "")
    else:
        usados = set()
        for g in d.get("grandezas", []) + d.get("itens", []):
            for f in (g.get("formula", ""), g.get("quando", "")):
                if f:
                    try:
                        usados |= nomes_usados(f)
                    except ErroDeFormula:
                        pass
        r["entradas"] = [{"nome": k, "unidade": u, "descricao": ds, "padrao": p}
                         for k, (u, ds, p) in _CAMPOS_ARANDU.items() if k in usados or k == "voo_validado"]
        r["entradas"] += [{"nome": k, "unidade": "", "descricao": "cenário da equipe", "padrao": float(v)}
                          for k, v in d.get("cenario", {}).items()]
        r["so_conta_se"] = "voo_validado"
    r["grandezas"] = [{"nome": g["nome"], "formula": g["formula"], "unidade": g.get("unidade", ""),
                       "descricao": g.get("descricao", "")} for g in d.get("grandezas", [])]
    r["itens"] = [{"nome": i["nome"], "formula": i["formula"], "quando": i.get("quando", ""),
                   "descricao": i.get("descricao", "")} for i in d.get("itens", [])]
    return r

def conferir(regra: dict) -> list[str]:
    p: list[str] = []
    vistos: set[str] = set()

    def novo(nome, quem):
        if not nome or not str(nome).replace("_", "").isalnum() or str(nome)[0].isdigit():
            p.append(f"{quem}: nome inválido “{nome}” (use letras, números e _)")
        elif nome in vistos:
            p.append(f"{quem}: o nome “{nome}” já está em uso")
        vistos.add(nome)

    for k in regra.get("constantes", {}):
        novo(k, "constante")
    for e in regra.get("entradas", []):
        novo(e.get("nome"), "entrada")
    for g in regra.get("grandezas", []):
        onde = f"grandeza {g.get('nome')}"
        try:
            falta = sorted(nomes_usados(g.get("formula", ""), onde) - vistos)
            if falta:
                p.append(f"{onde}: usa {', '.join(falta)}, que ainda não existe nesta altura da regra")
        except ErroDeFormula as e:
            p.append(_curta(e))
        novo(g.get("nome"), onde)
    if not regra.get("itens"):
        p.append("A regra não tem nenhum item: a pontuação seria sempre zero.")
    nomes_item = set()
    for i in regra.get("itens", []):
        onde = f"item {i.get('nome')}"
        if i.get("nome") in nomes_item:
            p.append(f"{onde}: item repetido")
        nomes_item.add(i.get("nome"))
        for txt, rot in ((i.get("formula", ""), onde), (i.get("quando", ""), onde + " (condição)")):
            if not txt:
                continue
            try:
                falta = sorted(nomes_usados(txt, rot) - vistos)
                if falta:
                    p.append(f"{rot}: usa {', '.join(falta)}, que a regra não define")
            except ErroDeFormula as e:
                p.append(_curta(e))
    if regra.get("so_conta_se"):
        try:
            falta = sorted(nomes_usados(regra["so_conta_se"], "condição geral") - vistos)
            if falta:
                p.append(f"condição geral: usa {', '.join(falta)}, que a regra não define")
        except ErroDeFormula as e:
            p.append(_curta(e))
    return p

def _curta(e: Exception) -> str:
    t = str(e).split("\n")[0]
    for corte in (" Disponiveis", " Disponíveis", " Disponiv"):
        t = t.split(corte)[0]
    return t.rstrip(" .:") + "."

def _num(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else float(x)

def avaliar(regra: dict, valores: dict | None = None) -> dict:
    valores = valores or {}
    ctx: dict[str, float] = {k: float(v) for k, v in regra.get("constantes", {}).items()}
    for e in regra.get("entradas", []):
        v = valores.get(e["nome"], e.get("padrao", 0.0))
        ctx[e["nome"]] = float(v)
    grand, itens, total = [], [], 0.0

    def calc(txt, onde):
        try:
            return float(_avalia(compilar(txt, onde), ctx, onde)), None
        except ErroDeFormula as e:
            return None, _curta(e)
        except (ZeroDivisionError, OverflowError, ValueError) as e:
            return None, f"{onde}: {e}"

    for g in regra.get("grandezas", []):
        v, erro = calc(g["formula"], f"grandeza {g['nome']}")
        if v is not None:
            ctx[g["nome"]] = v
        grand.append({"nome": g["nome"], "valor": _num(v), "unidade": g.get("unidade", ""),
                      "formula": g["formula"], "erro": erro})
    conta = True
    if regra.get("so_conta_se"):
        c, erro = calc(regra["so_conta_se"], "condição geral")
        conta = bool(c) if erro is None else False
    for i in regra.get("itens", []):
        aplica, erro = True, None
        if i.get("quando"):
            q, erro = calc(i["quando"], f"item {i['nome']} (condição)")
            aplica = bool(q) if erro is None else False
        v = None
        if erro is None:
            v, erro = calc(i["formula"], f"item {i['nome']}")
        conta_o_item = conta and aplica and erro is None and v is not None
        if conta_o_item:
            total += v
        itens.append({"nome": i["nome"], "valor": _num(v), "aplica": aplica, "erro": erro,
                      "formula": i["formula"], "quando": i.get("quando", ""),
                      "conta": conta_o_item})
    return {"contexto": {k: _num(v) for k, v in ctx.items()}, "grandezas": grand, "itens": itens,
            "total": total if conta else 0.0, "conta": conta, "problemas": conferir(regra)}

def copia(regra: dict) -> dict:
    return copy.deepcopy(regra)
