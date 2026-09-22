import itertools
import random
import unittest
from veitch.logic import Function, parse, minimize, cubes


def brute_minimum(function):
    """Independent oracle: enumerate combinations of prime cubes, not search states."""
    n, target = len(function.variables), set(function.ones)
    if not target:
        return (0, 0)
    valid = []
    for pattern in itertools.product((None, 0, 1), repeat=n):
        members = {i for i in range(2 ** n) if all(value is None or
                   int(format(i, f"0{n}b")[j]) == value for j, value in enumerate(pattern))}
        if members <= target:
            valid.append((members, sum(v is not None for v in pattern)))
    prime = [(s, literals) for s, literals in valid if not any(s < other for other, _ in valid)]
    for count in range(1, len(prime) + 1):
        best = None
        for combination in itertools.combinations(prime, count):
            if set().union(*(s for s, _ in combination)) == target:
                cost = sum(literals for _, literals in combination)
                best = cost if best is None else min(best, cost)
        if best is not None:
            return count, best


class ParserTests(unittest.TestCase):
    def test_notations(self):
        for source in ["A*B + A*!B", "AB+AB'", "A∧B ∨ A∧¬B", "A AND B OR A AND NOT B", "A&B | A&~B"]:
            with self.subTest(source=source):
                self.assertEqual(parse(source).ones, frozenset({2, 3}))

    def test_precedence(self):
        self.assertEqual(parse("A+B*C").ones, frozenset({3, 4, 5, 6, 7}))
        self.assertEqual(parse("A^B*C").ones, frozenset({3, 4, 5, 6}))
        self.assertEqual(parse("!(A+B)").ones, frozenset({0}))
        self.assertEqual(parse("(A+B)'").ones, frozenset({0}))

    def test_declared_order_and_unused_variables(self):
        function = parse("F(B,A,C,D) = A")
        self.assertEqual(function.variables, ("B", "A", "C", "D"))
        self.assertEqual(function.ones, frozenset({4, 5, 6, 7, 12, 13, 14, 15}))
        self.assertEqual(parse("x1 * !x2").variables, ("X1", "X2"))

    def test_constants(self):
        self.assertEqual(minimize(parse("0"))["formula"], "0")
        self.assertEqual(minimize(parse("1"))["formula"], "1")
        self.assertEqual(minimize(parse("A+!A"))["formula"], "1")
        self.assertEqual(minimize(parse("A*!A"))["formula"], "0")

    def test_invalid(self):
        for source in [None, 42, "", " ", "A+", "A)", "(A", "A/B", "A+B+C+D+E", "2", "__import__('os')",
                       "F(A,A)=A", "F(A)=B", "F()=1", "Q=A", "(" * 50 + "A" + ")" * 50, "A" * 513]:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    parse(source)


class MinimizerTests(unittest.TestCase):
    def check_result(self, function, scores=None):
        result = minimize(function, scores)
        union = set()
        for group in result["groups"]:
            self.assertTrue(set(group["cells"]) <= function.ones)
            self.assertIn(len(group["cells"]), [1, 2, 4, 8, 16])
            union.update(group["cells"])
        self.assertEqual(union, function.ones)
        # Reparse the answer with the original variables to verify its Boolean meaning.
        declaration = "F(" + ",".join(function.variables) + ")=" if function.variables else ""
        self.assertEqual(parse(declaration + result["formula"]).ones, function.ones)
        self.assertEqual((result["terms"], result["literals"]), brute_minimum(function))

    def test_all_three_variable_functions_are_minimal(self):
        for truth_id in range(256):
            self.check_result(Function(("A", "B", "C"), frozenset(i for i in range(8) if truth_id >> i & 1)))

    def test_four_variables_random_and_adversarial_ml(self):
        rng = random.Random(8)
        for truth_id in [0, 65535, 0xA55A, 0x8421] + rng.sample(range(65536), 200):
            # Arbitrarily wrong ML scores may alter a tie, never the minimum cost.
            scores = {p: rng.random() for p, _ in cubes(4)}
            self.check_result(Function(tuple("ABCD"), frozenset(i for i in range(16) if truth_id >> i & 1)), scores)

    def test_overlapping_groups(self):
        function = parse("A*B+B*C")
        result = minimize(function)
        self.assertEqual((result["terms"], result["literals"]), (2, 4))
        self.assertTrue(set(result["groups"][0]["cells"]) & set(result["groups"][1]["cells"]))
