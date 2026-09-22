"""Deterministic orthogonal SVG layout for a shared, acyclic NAND circuit."""
from collections import defaultdict
from html import escape


def render_circuit(gates, outputs, variables):
    depth = dict.fromkeys(variables, 0)
    for gate in gates:
        depth[gate['name']] = 1 + max(depth[name] for name in gate['inputs'])
    output_depth = max(depth.values()) + 1
    edges = []
    for gate in gates:
        edges.extend((source, gate['name'], i, depth[gate['name']])
                     for i, source in enumerate(gate['inputs']))
    edges.extend((output['expression'], output['name'], 0, output_depth) for output in outputs)
    incoming = defaultdict(list)
    for edge in edges:
        incoming[edge[3]].append(edge)
    column = {0: 40}
    for level in range(1, output_depth + 1):
        column[level] = column[level - 1] + 150 + 14 * len(incoming[level])

    positions, boxes, pins = {}, {}, {}
    y = 100
    for name in variables:
        positions[name] = (90, y)
        y += 44
    for gate in sorted(gates, key=lambda g: (depth[g['name']], int(g['name'][1:]))):
        name, inputs = gate['name'], gate['inputs']
        height = max(64, 24 * (len(inputs) + 1))
        x = column[depth[name]]
        boxes[name] = (x, y, 80, height)
        positions[name] = (x + 90, y + height / 2)
        for i in range(len(inputs)):
            pins[name, i] = (x, y + height * (i + 1) / (len(inputs) + 1))
        y += height + 48
    for output in outputs:
        pins[output['name'], 0] = (column[output_depth], y)
        y += 48
    width, height = max(700, column[output_depth] + 120), y + 30
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="circuit-title">',
           '<title id="circuit-title">Общая схема системы на элементах И-НЕ</title>',
           '<desc>Прямоугольник &amp; с кружком — многовходовый И-НЕ. Точка означает соединение; пересечение без точки не соединено.</desc>',
           f'<rect width="{width}" height="{height}" fill="white"/>',
           '<g font-family="DejaVu Sans, Arial, sans-serif" font-size="16" fill="#111">',
           '<text x="30" y="30" font-size="21">Система в базисе Шеффера · И-НЕ</text>',
           '<text x="30" y="57" font-size="13">● — соединение; пересечение без точки — без соединения</text>']
    branches = defaultdict(list)
    for level, items in incoming.items():
        for lane, (source, target, index, _) in enumerate(items):
            # A separate vertical lane per edge prevents unrelated wires merging.
            bend = column[level] - 22 - lane * 14
            branches[source].append((bend, target, index))
    for source, items in branches.items():
        sx, sy = positions[source]
        end = max(bend for bend, _, _ in items)
        out.append(f'<path data-signal="{escape(source)}" d="M {sx} {sy} H {end}" fill="none" stroke="#333" stroke-width="1.5"/>')
        for bend, target, index in items:
            tx, ty = pins[target, index]
            out.append(f'<path data-source="{escape(source)}" data-target="{escape(target)}" data-input="{index}" '
                       f'd="M {bend} {sy} V {ty} H {tx}" fill="none" stroke="#333" stroke-width="1.5"/>')
            if len(items) > 1:
                out.append(f'<circle cx="{bend}" cy="{sy}" r="3"/>')
    for name in variables:
        x, y = positions[name]
        out.append(f'<text x="30" y="{y+5}">{escape(name)}</text><path d="M 55 {y} H {x}" stroke="#333"/>')
    for gate in gates:
        name = gate['name']
        x, y, w, h = boxes[name]
        out.append(f'<g data-gate="{escape(name)}"><rect x="{x}" y="{y}" width="{w}" height="{h}" '
                   f'fill="white" stroke="#111" stroke-width="2"/><text x="{x+w/2}" y="{y+h/2+7}" '
                   f'text-anchor="middle" font-size="24">&amp;</text><circle cx="{x+w+5}" cy="{y+h/2}" '
                   f'r="5" fill="white" stroke="#111" stroke-width="2"/>'
                   f'<text x="{x}" y="{y-10}">{escape(name)}</text></g>')
    for output in outputs:
        x, y = pins[output['name'], 0]
        out.append(f'<text data-output="{escape(output["name"])}" x="{x+8}" y="{y+5}">{escape(output["name"])}</text>')
    out.append('</g></svg>')
    return ''.join(out)
