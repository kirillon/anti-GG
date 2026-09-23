from itertools import product
import unittest
import xml.etree.ElementTree as ET
from veitch.logic import cubes, parse
from veitch.system import solve_system, parse_sets


class SystemTests(unittest.TestCase):
    def test_four_variable_case_from_user_has_minimal_cover(self):
        result = solve_system(4, [
            '0,2,4,6,8,11,13,15',
            '0,2,4,6,8,11,13',
            '0,2,4,6,13,15',
        ])
        # Regression: every output must be covered exactly by the selected
        # implicants, and the joint cover must contain no redundant row.
        for output in result['outputs']:
            covered = set()
            for group in output['groups']:
                covered.update(group['cells'])
            expected = set(result['columns'][i]['minterm']
                           for i, column in enumerate(result['columns'])
                           if column['function'] == output['name'])
            self.assertEqual(covered, expected)
        for index in result['selected']:
            reduced = [i for i in result['selected'] if i != index]
            self.assertFalse(all(
                any(result['rows'][j]['coverage'][column] for j in reduced)
                for column in range(len(result['columns']))
            ))
        f1_patterns = {tuple(g['pattern']) for g in result['outputs'][0]['groups']}
        self.assertIn((1, -1, 1, 1), f1_patterns)  # cells 11 and 15
        self.assertNotIn((1, 0, 1, 1), f1_patterns)  # singleton 11 is absorbed
    def verify(self, result, functions):
        circuit = result['sheffer']
        for assignment in range(1 << len(result['variables'])):
            signals = {name:bool(assignment >> (len(result['variables'])-i-1) & 1) for i,name in enumerate(result['variables'])}
            for gate in circuit['gates']:
                signals[gate['name']] = not all(signals[name] for name in gate['inputs'])
            for i,output in enumerate(circuit['outputs']):
                self.assertEqual(signals[output['expression']],assignment in functions[i])
        for i, output in enumerate(result['outputs']):
            formula = 'F(' + ','.join(result['variables']) + ')=' + output['formula']
            self.assertEqual(parse(formula).ones, frozenset(functions[i]))
        for column in range(len(result['columns'])):
            self.assertTrue(any(result['rows'][i]['coverage'][column] for i in result['selected']))
        for row in result['rows']:
            expected = [f'F{i+1}' for i, ones in enumerate(functions) if set(row['cells']) <= set(ones)]
            self.assertEqual(row['labels'], expected)
        self.assertEqual(len(result['rows']), len({tuple(row['pattern']) for row in result['rows']}))

    def test_textbook_example(self):
        functions = [[0,2,4,6,10,12,14], [2,3,10], [0,1,2,3,9,11]]
        r = solve_system(4, [','.join(map(str, f)) for f in functions])
        self.verify(r, functions)
        self.assertEqual((r['literal_count'], r['term_count']), (13, 5))
        self.assertEqual((len(r['rows']), len(r['columns']), len(r['products'])), (9,16,7))
        self.assertEqual(sum(row['essential'] for row in r['rows']), 4)
        self.assertEqual(sum(row['mark'] == '*' for row in r['rows']), 1)
        for diagram in r['products']:
            expected = set.intersection(*(set(functions[i-1]) for i in diagram['functions']))
            self.assertEqual({i for i,v in enumerate(diagram['truth']) if v}, expected)
            self.assertIn('Сокращённая ДНФ', diagram['svg'])

    def test_all_two_variable_pairs_against_exhaustive_oracle(self):
        # Enumerate all subsets of ALL valid cubes, independently of prime extraction.
        for a,b in product(range(16), repeat=2):
            functions = [{i for i in range(4) if f >> i & 1} for f in (a,b)]
            r = solve_system(2, [','.join(map(str, sorted(f))) for f in functions])
            self.verify(r, functions)
            target = {(j,i) for j,f in enumerate(functions) for i in f}
            candidates = []
            for pattern, mask in cubes(2):
                cells = {i for i in range(4) if mask >> i & 1}
                covered = {(j,i) for j,f in enumerate(functions) if cells <= f for i in cells}
                if covered: candidates.append((covered, sum(b != -1 for b in pattern)))
            best = (100,100)
            for bits in range(1 << len(candidates)):
                chosen = [c for j,c in enumerate(candidates) if bits >> j & 1]
                if set().union(*(c[0] for c in chosen)) == target:
                    best = min(best, (sum(c[1] for c in chosen),len(chosen)))
            self.assertEqual((r['literal_count'],r['term_count']), best)

    def test_empty_constant_identical_and_disjoint(self):
        for functions in [[[],[]], [list(range(4)),list(range(4))], [[1,3],[1,3],[1,3]], [[0],[3]], [[],[0],[1],[2]]]:
            r = solve_system(2, [','.join(map(str,f)) for f in functions])
            self.verify(r, functions)
            self.assertEqual(len(r['products']), 2**len(functions)-1)
        r = solve_system(2, ['0,1,2,3','0,1,2,3'])
        self.assertEqual((r['literal_count'],r['term_count']), (0,1))
        self.assertEqual(r['rows'][0]['labels'], ['F1','F2'])

    def test_input_validation(self):
        self.assertEqual(parse_sets(2, ['1,1; 3','∅']), [10,0])
        for n, fs in [(True,['0','1']), (0,['','']), (5,['','']), (2,['0']), (2,['']*5),
                      (2,['4','']), (2,['-1','']), (2,['1.5','']), (2,['0,,','']), (2,[None,'']), (2,'0,1')]:
            with self.subTest(n=n,fs=fs), self.assertRaises(ValueError): parse_sets(n,fs)

    def test_matrix_export_preserves_every_column(self):
        r = solve_system(3, ['0,1,2','1,2,3'])
        table = ET.fromstring(r['matrix_html'])
        self.assertEqual(len(table.findall('.//tr')), len(r['rows'])+5)
        for row in table.findall('tbody/tr'):
            self.assertEqual(len(row), len(r['columns'])+1)
        self.assertEqual(sum(int(c.get('colspan','1')) for c in table.findall('thead/tr')[1]),len(r['columns']))
        self.assertIn('+',r['matrix_html'])
        self.assertIn('text-decoration:overline',r['matrix_html'])
        self.assertEqual(len(r['matrix_tsv'].splitlines()), len(r['rows'])+2)
