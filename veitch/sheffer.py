"""Shared circuit using only binary NAND gates (Sheffer stroke)."""
def to_sheffer(outputs, variables):
    gates, lookup, inverses = [], {}, {}

    def nand(a, b):
        key = tuple(sorted((a, b)))
        if key not in lookup:
            name = f'T{len(gates)+1}'
            lookup[key] = name
            gates.append({'name': name, 'left': a, 'right': b, 'expression': f'{a} ↑ {b}'})
        return lookup[key]

    def negate(a):
        if a not in inverses:
            b = nand(a, a)
            inverses[a], inverses[b] = b, a
        return inverses[a]

    def constant(value):
        one = nand(variables[0], negate(variables[0]))
        return one if value else negate(one)

    result = []
    for output in outputs:
        terms = []
        for group in output['groups']:
            literals = [name if bit else negate(name) for name,bit in zip(variables,group['pattern']) if bit != -1]
            value = literals[0] if literals else constant(True)
            for literal in literals[1:]:
                value = negate(nand(value, literal))
            terms.append(value)
        value = terms[0] if terms else constant(False)
        for term in terms[1:]:
            value = nand(negate(value), negate(term))
        result.append({'name': output['name'], 'expression': value})
    # Remove gates cancelled during conversion and retain topological ordering.
    needed = {item['expression'] for item in result}
    for gate in reversed(gates):
        if gate['name'] in needed:
            needed.update((gate['left'],gate['right']))
    gates = [gate for gate in gates if gate['name'] in needed]
    text = '\n'.join(f'{g["name"]} = {g["expression"]}' for g in gates + result)
    return {'gates': gates, 'outputs': result, 'text': text}
