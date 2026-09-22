"""Exact joint SOP minimization by labels: shared literals are counted once."""
from functools import lru_cache
from html import escape
from itertools import combinations
import re
from .logic import cubes, term
from .diagram import render_svg
from .sheffer import to_sheffer
from itertools import groupby


def parse_sets(n, sources):
    if type(n) is not int or not 1 <= n <= 4:
        raise ValueError('Количество переменных: от 1 до 4.')
    if not isinstance(sources, list) or not 2 <= len(sources) <= 4:
        raise ValueError('Добавьте от 2 до 4 функций.')
    result = []
    for i, source in enumerate(sources, 1):
        if not isinstance(source, str) or len(source) > 256:
            raise ValueError(f'F{i}: ожидается список номеров наборов.')
        source = source.strip()
        if source in ('', '∅', '-'):
            result.append(0)
            continue
        if not re.fullmatch(r'\d+(?:[\s,;]+\d+)*', source):
            raise ValueError(f'F{i}: разделяйте номера запятыми, пробелами или точкой с запятой.')
        values = [int(x) for x in re.split(r'[\s,;]+', source)]
        if any(x >= 1 << n for x in values):
            raise ValueError(f'F{i}: допустимы наборы от 0 до {(1 << n)-1}.')
        result.append(sum(1 << x for x in set(values)))
    return result


def minimum_cover(masks, weights, target):
    """Exact weighted set cover; secondary objective: number of chosen rows."""
    choices = {i: [j for j, mask in enumerate(masks) if mask >> i & 1]
               for i in range(target.bit_length()) if target >> i & 1}
    if any(not rows for rows in choices.values()):
        raise ValueError('Невозможно покрыть все столбцы.')

    @lru_cache(None)
    def visit(remaining):
        if not remaining:
            return 0, 0, ()
        cell = min((i for i in choices if remaining >> i & 1), key=lambda i: len(choices[i]))
        best = None
        for j in choices[cell]:
            weight, count, indices = visit(remaining & ~masks[j])
            candidate = weight + weights[j], count + 1, (j,) + indices
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        return best
    return sorted(visit(target)[2])


def literal_html(pattern, variables):
    return ''.join(('<span style="text-decoration:overline">' + escape(name) + '</span>')
                   if bit == 0 else escape(name) for name,bit in zip(variables,pattern) if bit != -1) or '1'


def function_html(name):
    return 'F<sub>' + escape(name[1:]) + '</sub>'


def matrix_export(columns, rows, covered, variables):
    style = 'border:1px solid #222;padding:5px 8px;white-space:nowrap;text-align:center;font-weight:normal'
    def cell(value, tag='td', attrs=''):
        return f'<{tag} style="{style}" {attrs}>{value}</{tag}>'
    html = ['<table class="implicant-table" border="1" cellspacing="0" cellpadding="5" style="border-collapse:collapse;color:#111;background:white;font-family:Times New Roman,serif;font-size:12pt">',
            '<caption style="font-weight:bold;padding:10px">Импликантная матрица системы логических функций</caption>']
    count = len(columns)
    if count:
        html.append('<thead><tr>' + cell('Импликанта', 'th', 'rowspan="4"') + cell('Конституента','th',f'colspan="{count}"') + '</tr><tr>')
        for _, items in groupby(columns, key=lambda c:c['minterm']):
            group = list(items)
            pattern = [int(bit) for bit in group[0]['bits']]
            html.append(cell(literal_html(pattern,variables),'th', f'colspan="{len(group)}"'))
        html.append('</tr><tr>' + ''.join(cell(function_html(c['function']),'th') for c in columns) + '</tr>')
        html.append('<tr>' + ''.join(cell(str(i+1),'th') for i in range(count)) + '</tr></thead>')
    else:
        html.append('<thead><tr>' + cell('Импликанта — единичные наборы отсутствуют','th') + '</tr></thead>')
    html.append('<tbody>')
    for row in rows:
        label = ' '.join(function_html(f) for f in row['labels'])
        heading = escape(row['mark']) + ' &#160; ' + literal_html(row['pattern'],variables) + ' &#160; ' + label
        html.append('<tr>' + cell(heading) + ''.join(cell('+' if x else '') for x in row['coverage']) + '</tr>')
    html.append('</tbody><tfoot><tr>' + cell('') + ''.join(cell(escape(x)) for x in covered) + '</tr></tfoot></table>')
    data = [['Импликанта / метка'] + [f'{c["bits"]} / {c["function"]}' for c in columns]]
    data += [[r['mark']+' '+r['term']+' '+','.join(r['labels'])] + ['+' if x else '' for x in r['coverage']] for r in rows]
    data.append(['Покрытие'] + covered)
    return ''.join(html), '\n'.join('\t'.join(row) for row in data)


def solve_system(n, sources):
    functions = parse_sets(n, sources)
    variables = [f'X{i}' for i in range(n - 1, -1, -1)]
    products, unique = [], {}
    for size in range(1, len(functions) + 1):
        for subset in combinations(range(len(functions)), size):
            ones = (1 << (1 << n)) - 1
            for i in subset:
                ones &= functions[i]
            valid = [(p, m) for p, m in cubes(n) if m & ones == m]
            primes = [(p, m) for p, m in valid if not any(m != other and m & other == m for _, other in valid)]
            for p, m in primes:
                unique[p] = m
            groups = [{'pattern': list(p), 'term': term(p, variables),
                       'cells': [i for i in range(1 << n) if m >> i & 1]} for p, m in primes]
            name = ' · '.join(f'F{i+1}' for i in subset)
            diagram = {'variables': variables, 'truth': [int(ones >> i & 1) for i in range(1 << n)],
                       'groups': groups, 'formula': ' + '.join(g['term'] for g in groups) or '0'}
            products.append({'name': name, 'functions': [i+1 for i in subset], **diagram,
                             'svg': render_svg(diagram, name=name, formula_label='Сокращённая ДНФ — все простые импликанты')})
    columns = [{'minterm': m, 'bits': format(m, f'0{n}b'), 'function': f'F{i+1}', 'index': i}
               for m in range(1 << n) for i, ones in enumerate(functions) if ones >> m & 1]
    rows, masks = [], []
    def row_order(item):
        pattern, mask = item
        labels = [i for i,ones in enumerate(functions) if ones & mask == mask]
        return (-len(labels), -sum(1 << i for i in labels), -sum(v != -1 for v in pattern), pattern)
    for pattern, mask in sorted(unique.items(), key=row_order):
        # All functions containing this cube form the unique longest label.
        labels = [i for i, ones in enumerate(functions) if ones & mask == mask]
        coverage = [c['index'] in labels and bool(mask >> c['minterm'] & 1) for c in columns]
        masks.append(sum(1 << i for i, value in enumerate(coverage) if value))
        rows.append({'pattern': list(pattern), 'term': term(pattern, variables),
                     'labels': [f'F{i+1}' for i in labels], 'literals': sum(v != -1 for v in pattern),
                     'cells': [m for m in range(1 << n) if mask >> m & 1], 'coverage': coverage})
    chosen = minimum_cover(masks, [row['literals'] for row in rows], (1 << len(columns)) - 1)
    essential = set()
    for c in range(len(columns)):
        covering = [i for i, mask in enumerate(masks) if mask >> c & 1]
        if len(covering) == 1:
            essential.add(covering[0])
    for i, row in enumerate(rows):
        row.update(selected=i in chosen, essential=i in essential,
                   mark='√' if i in essential else '*' if i in chosen else '')
    covered = ['√' if any(masks[i] >> c & 1 for i in essential) else '*' for c in range(len(columns))]
    outputs = []
    for i, ones in enumerate(functions):
        available = [j for j in chosen if f'F{i+1}' in rows[j]['labels']]
        local = minimum_cover([sum(1 << m for m in rows[j]['cells']) for j in available],
                              [1] * len(available), ones)
        indices = [available[j] for j in local]
        diagram = {'variables': variables, 'truth': [int(ones >> m & 1) for m in range(1 << n)],
                   'groups': [rows[j] for j in indices],
                   'formula': ' + '.join(rows[j]['term'] for j in indices) or '0'}
        outputs.append({'name': f'F{i+1}', 'row_indices': indices, **diagram,
                        'svg': render_svg(diagram, name=f'F{i+1}', formula_label='ДНФ совместной реализации')})
    html, tsv = matrix_export(columns, rows, covered, variables)
    return {'variables': variables, 'products': products, 'columns': columns, 'rows': rows,
            'selected': chosen, 'outputs': outputs, 'literal_count': sum(rows[j]['literals'] for j in chosen),
            'term_count': len(chosen), 'matrix_html': html, 'matrix_tsv': tsv,
            'sheffer': to_sheffer(outputs, variables)}
