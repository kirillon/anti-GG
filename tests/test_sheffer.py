import ast
import random
import unittest
import xml.etree.ElementTree as ET
from veitch.logic import Function, minimize, parse
from veitch.sheffer import to_sheffer


def evaluate_formula(node, values):
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'NAND':
        return not all(evaluate_formula(arg, values) for arg in node.args)
    raise AssertionError('Unexpected formula node')


class ShefferTests(unittest.TestCase):
    def verify(self, functions):
        variables = functions[0].variables
        outputs = [dict(minimize(f), name=f'F{i+1}') for i, f in enumerate(functions)]
        circuit = to_sheffer(outputs, variables)
        trees = [ast.parse(o['formula'], mode='eval').body for o in circuit['outputs']]
        for assignment in range(1 << len(variables)):
            values = {name: bool(assignment >> (len(variables)-i-1) & 1) for i, name in enumerate(variables)}
            signals = dict(values)
            for gate in circuit['gates']:
                self.assertGreaterEqual(len(gate['inputs']), 2)
                signals[gate['name']] = not all(signals[name] for name in gate['inputs'])
            for f, output, tree in zip(functions, circuit['outputs'], trees):
                self.assertEqual(signals[output['expression']], assignment in f.ones)
                self.assertEqual(evaluate_formula(tree, values), assignment in f.ones)
        for output in circuit['outputs']:
            self.assertNotRegex(output['formula'], r'\bT\d+\b')
            self.assertNotRegex(output['formula_html'], r'\bT\d+\b')
        svg = ET.fromstring(circuit['svg'])
        ns = {'s': 'http://www.w3.org/2000/svg'}
        self.assertEqual({g.get('data-gate') for g in svg.findall('.//s:g[@data-gate]', ns)},
                         {g['name'] for g in circuit['gates']})
        edges = {(p.get('data-source'), p.get('data-target'), int(p.get('data-input')))
                 for p in svg.findall('.//s:path[@data-source]', ns)}
        expected = {(source, gate['name'], i) for gate in circuit['gates'] for i, source in enumerate(gate['inputs'])}
        expected.update((o['expression'], o['name'], 0) for o in circuit['outputs'])
        self.assertEqual(edges, expected)
        self.assertEqual({o.get('data-output') for o in svg.findall('.//s:text[@data-output]', ns)},
                         {o['name'] for o in circuit['outputs']})
        return circuit

    def test_textbook_examples(self):
        first = self.verify([parse('F(A,B,C)=!A+B*!C')])
        self.assertEqual(first['outputs'][0]['formula'], 'NAND(NAND(B, NAND(C, C)), A)')
        second = self.verify([parse('F(A,B,C)=!A*B*!C')])
        term = 'NAND(NAND(A, A), B, NAND(C, C))'
        self.assertEqual(second['outputs'][0]['formula'], f'NAND({term}, {term})')
        self.assertTrue(any(len(g['inputs']) == 3 for g in second['gates']))
        self.assertTrue(second['outputs'][0]['formula_html'].startswith('<span'))

    def test_constants_and_single_literals(self):
        for source in ('0', '1', 'A', '!A', 'A*B', '!A*!B', 'A+B+C+D', 'A*B*C*D'):
            with self.subTest(source=source):
                self.verify([parse('F(A,B,C,D)=' + source)])

    def test_all_three_variable_functions(self):
        for mask in range(256):
            self.verify([Function(tuple('ABC'), frozenset(i for i in range(8) if mask >> i & 1))])

    def test_four_variable_systems(self):
        rng = random.Random(73)
        for _ in range(50):
            self.verify([Function(tuple('ABCD'), frozenset(i for i in range(16) if rng.getrandbits(1))) for _ in range(4)])

    def test_shared_elements(self):
        f = parse('F(A,B,C)=!A+B*!C')
        single = self.verify([f])
        shared = self.verify([f, f])
        self.assertEqual(single['gates'], shared['gates'])
        self.assertEqual(shared['outputs'][0]['expression'], shared['outputs'][1]['expression'])
