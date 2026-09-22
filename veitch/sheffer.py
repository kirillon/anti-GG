"""Shared multi-input NAND circuit and fully expanded Sheffer expressions."""
from functools import lru_cache
from html import escape
from .circuit import render_circuit


def to_sheffer(outputs, variables):
    gates, lookup, inverses = [], {}, {}

    def nand(*inputs):
        key = tuple(sorted(inputs))
        if key not in lookup:
            name = f'T{len(gates)+1}'
            lookup[key] = name
            gates.append({'name': name, 'inputs': list(inputs),
                          'expression': 'NAND(' + ', '.join(inputs) + ')'})
        return lookup[key]

    def negate(signal):
        if signal not in inverses:
            inverse = nand(signal, signal)
            inverses[signal], inverses[inverse] = inverse, signal
        return inverses[signal]

    def constant(value):
        one = nand(variables[0], negate(variables[0]))
        return one if value else negate(one)

    result = []
    for output in outputs:
        # De Morgan: each term supplies its complement to the output NAND.
        complements = []
        for group in output['groups']:
            literals = [name if bit else negate(name)
                        for name, bit in zip(variables, group['pattern']) if bit != -1]
            if not literals:
                complements.append(constant(False))
            elif len(literals) == 1:
                complements.append(negate(literals[0]))
            else:
                complements.append(nand(*literals))
        if not complements:
            signal = constant(False)
        elif len(complements) == 1:
            signal = negate(complements[0])
        else:
            signal = nand(*complements)
        result.append({'name': output['name'], 'expression': signal})

    needed = {item['expression'] for item in result}
    for gate in reversed(gates):
        if gate['name'] in needed:
            needed.update(gate['inputs'])
    gates = [gate for gate in gates if gate['name'] in needed]
    by_name = {gate['name']: gate for gate in gates}

    @lru_cache(None)
    def expand(signal):
        if signal not in by_name:
            return signal, escape(signal)
        inputs = by_name[signal]['inputs']
        children = [expand(item) for item in inputs]
        formula = 'NAND(' + ', '.join(text for text, _ in children) + ')'
        if len(inputs) == 2 and inputs[0] == inputs[1]:
            html = ('<span class="sheffer-not" style="display:inline-block;border-top:1px solid currentColor;'
                    'line-height:1.2;padding-top:2px">' + children[0][1] + '</span>')
        else:
            html = '(' + ' ↑ <wbr>'.join(html for _, html in children) + ')'
        return formula, html

    for output in result:
        output['formula'], output['formula_html'] = expand(output['expression'])
    text = '\n'.join(f'{item["name"]} = {item["formula"]}' for item in result)
    return {'gates': gates, 'outputs': result, 'text': text,
            'svg': render_circuit(gates, result, variables)}
