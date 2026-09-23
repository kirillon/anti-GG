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
    column = {0: 35}
    for level in range(1, output_depth + 1):
        column[level] = column[level - 1] + 115 + 10 * len(incoming[level])

    positions, boxes, pins = {}, {}, {}
    levels = defaultdict(list)
    for gate in gates:
        levels[depth[gate['name']]].append(gate)
    def gate_height(gate):
        return 24 if len(set(gate['inputs'])) == 1 else max(40, 18 * (len(gate['inputs']) - 1))
    span = max([280, len(variables)*70] + [sum(gate_height(g)+55 for g in group) for group in levels.values()])
    for i, name in enumerate(variables):
        positions[name] = (65, 75 + (i+.5)*span/max(1,len(variables)))
    for level, group in levels.items():
        total = sum(gate_height(g)+55 for g in group)
        y = 75 + (span-total)/2
        for gate in group:
            name, inputs = gate['name'], gate['inputs']
            h = gate_height(gate)
            w = 30 if len(set(inputs)) == 1 else 52
            x = column[level]
            if len(set(inputs)) == 1 and inputs[0] in variables:
                y = positions[inputs[0]][1]-h/2
            boxes[name] = (x,y,w,h)
            positions[name] = (x+w+10,y+h/2)
            for i in range(len(inputs)):
                pins[name,i] = (x,y+h/2 if len(set(inputs)) == 1 else y+h*(i+1)/(len(inputs)+1))
            y += h+55
    for i, output in enumerate(outputs):
        source = output['expression']
        pins[output['name'],0] = (column[output_depth], positions[source][1])
        # Separate aliases of the same source so their labels remain legible.
        if any(o['expression']==source for o in outputs[:i]):
            pins[output['name'],0] = (column[output_depth],75+(i+.5)*span/len(outputs))
    width, height = max(700,column[output_depth]+70), span+120
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="circuit-title">',
           '<title id="circuit-title">Общая схема системы на элементах И-НЕ</title>',
           '<desc>ANSI/IEEE 91: D-образный И-НЕ с инверсией на выходе; треугольник — инвертор. Точки означают соединения.</desc>',
           f'<rect width="{width}" height="{height}" fill="white"/>',
           '<g font-family="DejaVu Sans, Arial, sans-serif" font-size="12" fill="#111">',
           '<text x="30" y="30" font-size="21">Комбинационная схема · ANSI/IEEE 91</text>',
           '<text x="30" y="57" font-size="13">■ — соединение; пересечение без точки — без соединения</text>']
    branches = defaultdict(list)
    for level, items in incoming.items():
        labelled = set()
        variable_lanes = {source: i for i, source in enumerate(dict.fromkeys(e[0] for e in items if e[0] in variables))}
        routed = [e for e in items if not (e[0] in variables and level > 1)]
        lanes = {(e[1],e[2]):i for i,e in enumerate(routed)}
        for source, target, index, _ in items:
            lane = lanes.get((target,index),0)
            # A separate vertical lane per edge prevents unrelated wires merging.
            bend = column[level] - 16 - lane * 10
            if source in variables and level > 1:
                bend = column[level] - 16 - len(routed) * 10 - variable_lanes[source] * 16
                tx, ty = pins[target,index]
                if source not in labelled:
                    out.append(f'<text x="{bend-3}" y="72" font-size="9" fill="#3333ff">{escape(source)}</text>')
                    labelled.add(source)
                out.append(f'<path data-source="{escape(source)}" data-target="{escape(target)}" data-input="{index}" '
                           f'd="M {bend} 78 V {ty} H {tx}" fill="none" stroke="#3333ff" stroke-width="0.8"/>')
                if sum(e[0] == source for e in items) > 1:
                    out.append(f'<rect x="{bend-2}" y="{ty-2}" width="4" height="4" fill="#00dede"/>')
            else:
                branches[source].append((bend, target, index))
    for source, items in branches.items():
        sx, sy = positions[source]
        end = max(bend for bend, _, _ in items)
        out.append(f'<path data-signal="{escape(source)}" d="M {sx} {sy} H {end}" fill="none" stroke="#3333ff" stroke-width="0.8"/>')
        for bend, target, index in items:
            tx, ty = pins[target, index]
            out.append(f'<path data-source="{escape(source)}" data-target="{escape(target)}" data-input="{index}" '
                       f'd="M {bend} {sy} V {ty} H {tx}" fill="none" stroke="#3333ff" stroke-width="0.8"/>')
            if len(items) > 1:
                out.append(f'<rect x="{bend-2}" y="{sy-2}" width="4" height="4" fill="#00dede"/>')
    for name in variables:
        x, y = positions[name]
        out.append(f'<text x="20" y="{y+4}" fill="#3333ff">{escape(name)}</text><path d="M 55 {y} H {x}" stroke="#3333ff"/>')
    for gate in gates:
        name = gate['name']
        x, y, w, h = boxes[name]
        inverter = len(set(gate['inputs'])) == 1
        out.append(f'<g data-gate="{escape(name)}" data-kind="{"INV" if inverter else "NAND"}">')
        if inverter:
            out.append(f'<path d="M{x} {y} L{x+w} {y+h/2} L{x} {y+h} Z" fill="white" stroke="#c33" stroke-width="0.8"/>')
        else:
            out.append(f'<path d="M{x} {y} H{x+w*.48} C{x+w*1.17} {y} {x+w*1.17} {y+h} {x+w*.48} {y+h} H{x} Z" fill="white" stroke="#c33" stroke-width="0.8"/>')
        out.append(f'<circle cx="{x+w+5}" cy="{y+h/2}" r="5" fill="white" stroke="#c33" stroke-width="0.8"/>'
                   f'<text x="{x+w/2}" y="{y-9 if inverter else y+h/2+4}" text-anchor="middle" fill="#16802a">{escape(name)}</text>'
                   f'<text x="{x}" y="{y+h+20}" font-size="9" fill="#a22">{"INV" if inverter else "NAND"+str(len(gate["inputs"]))}</text></g>')
    for output in outputs:
        x, y = pins[output['name'], 0]
        out.append(f'<text data-output="{escape(output["name"])}" x="{x+8}" y="{y+4}" fill="#3333ff">{escape(output["name"])}</text>')
    out.append('</g></svg>')
    return ''.join(out)
