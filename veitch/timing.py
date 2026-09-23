"""One netlist drives the IEEE-symbol schematic, simulation and Excel formulas."""
from html import escape
from .circuit import render_circuit


def netlist(sheffer, variables):
    aliases = {name: name for name in variables}
    gates, counts = [], {'INV': 0, 'NAND': 0}
    levels = dict.fromkeys(variables, 0)
    for gate in sheffer['gates']:
        levels[gate['name']] = 1 + max(levels[x] for x in gate['inputs'])
    for gate in sorted(sheffer['gates'], key=lambda g: levels[g['name']]):
        inputs = gate['inputs']
        kind = 'INV' if len(set(inputs)) == 1 else 'NAND'
        counts[kind] += 1
        name = ('I' if kind == 'INV' else 'D') + str(counts[kind])
        aliases[gate['name']] = name
        gates.append({'name': name, 'kind': kind,
                      'inputs': [aliases[x] for x in (inputs[:1] if kind == 'INV' else inputs)]})
    outputs = [{'name': o['name'], 'expression': aliases[o['expression']]} for o in sheffer['outputs']]
    return {'variables': variables, 'gates': gates, 'outputs': outputs,
            'svg': render_circuit(gates, outputs, variables)}


def simulate(circuit, period=12, t01=2, t10=3):
    for name, value, low, high in [('Период', period, 1, 32), ('Задержка 0 → 1', t01, 0, 8),
                                   ('Задержка 1 → 0', t10, 0, 8)]:
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{name}: целое число от {low} до {high}.')
    variables, gates, outputs = circuit['variables'], circuit['gates'], circuit['outputs']
    depth_delay = dict.fromkeys(variables, 0)
    initial = dict.fromkeys(variables, 0)
    for gate in gates:
        delay = max(t01, t10)
        depth_delay[gate['name']] = max(depth_delay[x] for x in gate['inputs']) + delay
        initial[gate['name']] = int(not all(initial[x] for x in gate['inputs']))
    count = 1 << len(variables)
    tail = max(1, (max(depth_delay.values()) + period - 1) // period)
    steps = (count + tail) * period
    values = {name: [min(t // period, count-1) >> (len(variables)-i-1) & 1 for t in range(steps)]
              for i, name in enumerate(variables)}
    for gate in gates:
        name = gate['name']
        ideal = [int(not all(values[x][t] for x in gate['inputs'])) for t in range(steps)]
        events = {}
        previous = initial[name]
        for t, value in enumerate(ideal):
            if value != previous:
                # Later-originating transitions win if events arrive together.
                events[t + (t01 if value else t10)] = value
            previous = value
        state = initial[name]
        values[name] = []
        for t in range(steps):
            state = events.get(t, state)
            values[name].append(state)
    for output in outputs:
        values[output['name']] = list(values[output['expression']])
        initial[output['name']] = initial[output['expression']]
    signals = list(reversed(variables)) + [g['name'] for g in gates] + [o['name'] for o in outputs]
    result = {'period': period, 't01': t01, 't10': t10,
              'steps': steps, 'signals': signals, 'values': values, 'initial': initial,
              'circuit': circuit, 'tail_blocks': tail}
    result['svg'] = render_timing(result)
    return result


def render_timing(result):
    period, steps, signals = result['period'], result['steps'], result['signals']
    sx, sy, dx, dy = 180, 96, 6, 38
    width, height = sx+steps*dx+30, sy+len(signals)*dy+40
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
           '<title>Временная диаграмма комбинационной схемы</title>',
           f'<rect width="{width}" height="{height}" fill="white"/>',
           '<g font-family="Arial,sans-serif" font-size="14" fill="#111">',
           '<text x="20" y="28" font-size="20">Временная диаграмма</text>',
           f'<text x="20" y="53">Период набора: {period}; t01: {result["t01"]}; t10: {result["t10"]} такт(ов). Жёлтый — 1.</text>']
    for t in range(0,steps,period):
        x = sx+t*dx
        out.append(f'<text x="{x+4}" y="82">{t//period}</text><path d="M{x} {sy}V{height-28}" stroke="#555"/>')
    for i, name in enumerate(signals):
        y = sy+i*dy
        out.append(f'<text x="20" y="{y+23}">{escape(name)}</text>')
        values = result['values'][name]
        path = []
        for t, value in enumerate(values):
            x, level = sx+t*dx, y+28-value*20
            if value:
                out.append(f'<rect x="{x}" y="{y+8}" width="{dx}" height="20" fill="#ffc000"/>')
            path.append(f'M{x} {level}h{dx}' if t == 0 else f'V{level}h{dx}')
        out.append(f'<path d="{" ".join(path)}" stroke="#111" fill="none" stroke-width="1.4"/>')
    out.append('</g></svg>')
    return ''.join(out)
