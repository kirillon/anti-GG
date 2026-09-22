"""Safe Boolean parser and exact minimum sum-of-products (at most 4 variables)."""
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
import re


@dataclass(frozen=True)
class Function:
    variables: tuple[str, ...]
    ones: frozenset[int]

    @property
    def truth(self):
        return [int(i in self.ones) for i in range(1 << len(self.variables))]


def parse(source: str) -> Function:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Введите булеву функцию.")
    if len(source) > 512:
        raise ValueError("Функция должна содержать не более 512 символов.")
    source = source.strip()
    declared = None
    if "=" in source:
        left, source = source.split("=", 1)
        match = re.fullmatch(r"\s*[fF]\s*(?:\(([^)]*)\))?\s*", left)
        if not match:
            raise ValueError("Слева от = допустимо F или F(A,B,C,D).")
        if match[1] is not None:
            declared = tuple(x.strip().upper() for x in match[1].split(","))
            if (not all(re.fullmatch(r"[A-Z][0-9]*", x) for x in declared)
                    or len(set(declared)) != len(declared)):
                raise ValueError("Некорректный список переменных в F(...).")
    for word, symbol in [("AND", "*"), ("OR", "+"), ("NOT", "!"), ("XOR", "^")]:
        source = re.sub(r"\b" + word + r"\b", lambda _: symbol, source, flags=re.I)
    source = source.translate(str.maketrans({"¬": "!", "~": "!", "∧": "*", "&": "*",
        "·": "*", "∨": "+", "|": "+", "⊕": "^", "′": "'"})).upper()
    tokens = re.findall(r"[A-Z][0-9]*|[01!+*^()']|\S", source)
    variables = declared if declared is not None else tuple(sorted(set(
        t for t in tokens if re.fullmatch(r"[A-Z][0-9]*", t))))
    if len(variables) > 4:
        raise ValueError("Диаграмма поддерживает не более 4 переменных.")
    pos = 0

    def atom(depth):
        nonlocal pos
        if depth > 48:
            raise ValueError("Слишком большая вложенность выражения.")
        if pos >= len(tokens):
            raise ValueError("Ожидалась переменная, константа или скобка.")
        token = tokens[pos]
        pos += 1
        if token == "!":
            node = ("!", atom(depth + 1))
        elif token == "(":
            node = expression(0, depth + 1)
            if pos >= len(tokens) or tokens[pos] != ")":
                raise ValueError("Не хватает закрывающей скобки.")
            pos += 1
        elif token in ("0", "1"):
            node = ("const", int(token))
        elif token in variables:
            node = ("var", variables.index(token))
        else:
            raise ValueError(f"Недопустимый символ или переменная: {token}")
        while pos < len(tokens) and tokens[pos] == "'":
            node = ("!", node)
            pos += 1
        return node

    def expression(min_precedence, depth):
        nonlocal pos
        node = atom(depth)
        while pos < len(tokens):
            token = tokens[pos]
            implicit = token in variables or token in ("0", "1", "!", "(")
            op = "*" if implicit else token
            precedence = {"+": 1, "^": 2, "*": 3}.get(op, -1)
            if precedence < min_precedence:
                break
            if not implicit:
                pos += 1
            node = (op, node, expression(precedence + 1, depth + 1))
        return node

    tree = expression(0, 0)
    if pos != len(tokens):
        raise ValueError(f"Лишний символ: {tokens[pos]}")

    def evaluate(node, bits):
        op = node[0]
        if op == "const":
            return bool(node[1])
        if op == "var":
            return bool(bits & (1 << (len(variables) - 1 - node[1])))
        if op == "!":
            return not evaluate(node[1], bits)
        a, b = evaluate(node[1], bits), evaluate(node[2], bits)
        return {"+": a or b, "*": a and b, "^": a != b}[op]

    return Function(variables, frozenset(i for i in range(1 << len(variables)) if evaluate(tree, i)))


@lru_cache(maxsize=5)
def cubes(n):
    """-1 means a free variable. Bit i in mask denotes truth-table row i."""
    result = []
    for pattern in product((-1, 0, 1), repeat=n):
        mask = sum(1 << i for i in range(1 << n) if all(
            bit == -1 or bit == ((i >> (n - j - 1)) & 1) for j, bit in enumerate(pattern)))
        result.append((pattern, mask))
    return tuple(result)


def term(pattern, variables):
    return " · ".join(("¬" if value == 0 else "") + name
                      for name, value in zip(variables, pattern) if value != -1) or "1"


def minimize(function, scores=None):
    """Minimize term count, then literal count. ML only orders the exact search."""
    n = len(function.variables)
    ones = sum(1 << i for i in function.ones)
    valid = [(p, mask) for p, mask in cubes(n) if mask & ones == mask]
    primes = [(p, m) for p, m in valid if not any(m != other and m & other == m for _, other in valid)]
    scores = scores or {}
    primes.sort(key=lambda item: (-scores.get(item[0], 0), item[0]))
    literals = [sum(b != -1 for b in p) for p, _ in primes]
    choices = {i: [j for j, (_, m) in enumerate(primes) if m >> i & 1] for i in function.ones}

    def cost(indices):
        return len(indices), sum(literals[j] for j in indices)

    @lru_cache(maxsize=None)
    def cover(remaining):
        if not remaining:
            return ()
        cell = min((i for i in function.ones if remaining >> i & 1), key=lambda i: len(choices[i]))
        best = None
        for j in choices[cell]:
            candidate = (j,) + cover(remaining & ~primes[j][1])
            if best is None or cost(candidate) < cost(best):
                best = candidate
        return best

    selected = sorted((primes[j] for j in cover(ones)), key=lambda item: item[0])
    groups = [{"pattern": list(p), "term": term(p, function.variables),
               "cells": [i for i in range(1 << n) if mask >> i & 1]} for p, mask in selected]
    return {"variables": list(function.variables), "truth": function.truth, "groups": groups,
            "formula": " + ".join(g["term"] for g in groups) or "0",
            "terms": len(groups), "literals": sum(sum(b != -1 for b in p) for p, _ in selected)}
