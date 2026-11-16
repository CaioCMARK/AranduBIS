from __future__ import annotations

import ast
import math
from typing import Any

FUNCOES: dict[str, Any] = {
    "min": min, "max": max, "abs": abs, "round": round,
    "trunc": math.trunc, "floor": math.floor, "ceil": math.ceil,
    "sqrt": math.sqrt, "exp": math.exp, "log": math.log,
    "log10": math.log10, "sin": math.sin, "cos": math.cos,
    "tan": math.tan, "atan": math.atan, "pi": math.pi, "e": math.e,
}

EXPOENTE_MAXIMO = 64.0

_BINARIOS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Mod: lambda a, b: a % b,
    ast.FloorDiv: lambda a, b: a // b,
}

_COMPARACOES = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}

class ErroDeFormula(ValueError):

    def __init__(self, mensagem: str, formula: str = "", onde: str = ""):
        self.formula = formula
        self.onde = onde
        cabeca = f"{onde}: " if onde else ""
        corpo = f"{cabeca}{mensagem}"
        if formula:
            corpo += f"\n    formula: {formula}"
        super().__init__(corpo)

def _parecido(nome: str, candidatos) -> str:
    baixo = nome.lower()
    for c in candidatos:
        if c.lower() == baixo:
            return f" Voce quis dizer `{c}`?"
    for c in candidatos:
        if abs(len(c) - len(nome)) <= 1 and (c.startswith(nome[:3])
                                             or nome.startswith(c[:3])):
            return f" Voce quis dizer `{c}`?"
    return ""

def compilar(formula: str, onde: str = "") -> ast.Expression:
    if not isinstance(formula, str) or not formula.strip():
        raise ErroDeFormula("formula vazia", str(formula), onde)
    try:
        arvore = ast.parse(formula.strip(), mode="eval")
    except SyntaxError as e:
        raise ErroDeFormula(f"nao consegui ler: {e.msg}", formula, onde) from None
    _conferir(arvore.body, formula, onde)
    return arvore

def _conferir(no: ast.AST, formula: str, onde: str) -> None:
    if isinstance(no, ast.Constant):
        if isinstance(no.value, bool) or isinstance(no.value, (int, float)):
            return
        raise ErroDeFormula(
            f"so numero e permitido como valor literal, veio {no.value!r}",
            formula, onde)
    if isinstance(no, ast.Name):
        return
    if isinstance(no, ast.BinOp):
        if type(no.op) not in _BINARIOS and not isinstance(no.op, ast.Pow):
            raise ErroDeFormula(f"operador {type(no.op).__name__} nao e aceito",
                                formula, onde)
        _conferir(no.left, formula, onde)
        _conferir(no.right, formula, onde)
        return
    if isinstance(no, ast.UnaryOp):
        if not isinstance(no.op, (ast.UAdd, ast.USub, ast.Not)):
            raise ErroDeFormula(f"operador {type(no.op).__name__} nao e aceito",
                                formula, onde)
        _conferir(no.operand, formula, onde)
        return
    if isinstance(no, ast.BoolOp):
        for v in no.values:
            _conferir(v, formula, onde)
        return
    if isinstance(no, ast.Compare):
        for op in no.ops:
            if type(op) not in _COMPARACOES:
                raise ErroDeFormula(
                    f"comparacao {type(op).__name__} nao e aceita", formula, onde)
        _conferir(no.left, formula, onde)
        for c in no.comparators:
            _conferir(c, formula, onde)
        return
    if isinstance(no, ast.IfExp):
        _conferir(no.test, formula, onde)
        _conferir(no.body, formula, onde)
        _conferir(no.orelse, formula, onde)
        return
    if isinstance(no, ast.Call):
        if not isinstance(no.func, ast.Name):
            raise ErroDeFormula("so da para chamar as funcoes pelo nome",
                                formula, onde)
        if no.func.id not in FUNCOES:
            raise ErroDeFormula(
                f"funcao `{no.func.id}` nao existe."
                + _parecido(no.func.id, FUNCOES)
                + f" Disponiveis: {', '.join(sorted(FUNCOES))}", formula, onde)
        if no.keywords:
            raise ErroDeFormula("argumento com nome nao e aceito", formula, onde)
        for a in no.args:
            _conferir(a, formula, onde)
        return
    raise ErroDeFormula(
        f"construcao {type(no).__name__} nao e aceita aqui -- a formula so "
        f"aceita numeros, nomes, contas, comparacoes e as funcoes da lista",
        formula, onde)

def nomes_usados(formula: str, onde: str = "") -> set[str]:
    arvore = compilar(formula, onde)
    return {n.id for n in ast.walk(arvore)
            if isinstance(n, ast.Name) and n.id not in FUNCOES}

def avaliar(formula: str | ast.Expression, contexto: dict[str, float],
            onde: str = "") -> float:
    arvore = (formula if isinstance(formula, ast.Expression)
              else compilar(formula, onde))
    texto = formula if isinstance(formula, str) else ""
    return _avaliar(arvore.body, contexto, texto, onde)

def _avaliar(no: ast.AST, ctx: dict[str, float], formula: str,
             onde: str) -> Any:
    if isinstance(no, ast.Constant):
        return no.value
    if isinstance(no, ast.Name):
        if no.id in ctx:
            return ctx[no.id]
        if no.id in FUNCOES:
            return FUNCOES[no.id]
        raise ErroDeFormula(
            f"`{no.id}` nao existe."
            + _parecido(no.id, list(ctx) + list(FUNCOES))
            + f" Disponiveis: {', '.join(sorted(ctx))}", formula, onde)
    if isinstance(no, ast.BinOp):
        a = _avaliar(no.left, ctx, formula, onde)
        b = _avaliar(no.right, ctx, formula, onde)
        if isinstance(no.op, ast.Pow):
            if abs(b) > EXPOENTE_MAXIMO:
                raise ErroDeFormula(
                    f"expoente {b} passa do teto de {EXPOENTE_MAXIMO:g}; "
                    f"nenhuma equacao de regulamento chega perto disso",
                    formula, onde)
            try:
                return a ** b
            except (OverflowError, ZeroDivisionError) as e:
                raise ErroDeFormula(f"{a} ** {b} nao tem valor: {e}",
                                    formula, onde) from None
        try:
            return _BINARIOS[type(no.op)](a, b)
        except ZeroDivisionError:
            raise ErroDeFormula("divisao por zero", formula, onde) from None
    if isinstance(no, ast.UnaryOp):
        v = _avaliar(no.operand, ctx, formula, onde)
        if isinstance(no.op, ast.USub):
            return -v
        if isinstance(no.op, ast.UAdd):
            return +v
        return not v
    if isinstance(no, ast.BoolOp):
        vals = [_avaliar(v, ctx, formula, onde) for v in no.values]
        if isinstance(no.op, ast.And):
            return all(vals)
        return any(vals)
    if isinstance(no, ast.Compare):
        esq = _avaliar(no.left, ctx, formula, onde)
        for op, dir_ in zip(no.ops, no.comparators):
            dv = _avaliar(dir_, ctx, formula, onde)
            if not _COMPARACOES[type(op)](esq, dv):
                return False
            esq = dv
        return True
    if isinstance(no, ast.IfExp):
        if _avaliar(no.test, ctx, formula, onde):
            return _avaliar(no.body, ctx, formula, onde)
        return _avaliar(no.orelse, ctx, formula, onde)
    if isinstance(no, ast.Call):
        fn = FUNCOES[no.func.id]
        args = [_avaliar(a, ctx, formula, onde) for a in no.args]
        try:
            return fn(*args)
        except (TypeError, ValueError) as e:
            raise ErroDeFormula(f"`{no.func.id}` reclamou: {e}",
                                formula, onde) from None
    raise ErroDeFormula(f"construcao {type(no).__name__} nao e aceita",
                        formula, onde)
