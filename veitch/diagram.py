"""Vector diagram; wraparound groups are split at the boundary and share a color/id."""
from html import escape
from itertools import groupby
import re

COLORS = ("#007f78", "#c24d19", "#6655c5", "#be3977", "#2579b8", "#7a7613", "#965525", "#484ac9")


def gray(bits):
    return [i ^ (i >> 1) for i in range(1 << bits)]


def runs(values):
    return [(group[0], group[-1] + 1) for _, items in groupby(enumerate(sorted(values)), lambda v: v[1] - v[0])
            if (group := [v for _, v in items])]


def geometry(result):
    n = len(result["variables"])
    row_indices = list(range(0, n, 2)) if n > 1 else []
    col_indices = [i for i in range(n) if i not in row_indices]
    rb, cb = len(row_indices), len(col_indices)
    # Textbook orientation: 10,11,01,00 on both axes for four variables.
    rows = [v ^ (1 << (rb-1)) for v in gray(rb)] if rb else [0]
    columns = [v ^ (1 << (cb-1)) for v in gray(cb)] if cb else [0]
    def assignment(r, c):
        return sum(((value >> (len(indices)-j-1)) & 1) << (n-i-1)
                   for value,indices in ((r,row_indices),(c,col_indices)) for j,i in enumerate(indices))
    cells = [[assignment(r,c) for c in columns] for r in rows]
    rectangles = []
    for group in result["groups"]:
        members = set(group["cells"])
        rr = {r for r, row in enumerate(cells) for i in row if i in members}
        cc = {c for row in cells for c, i in enumerate(row) if i in members}
        rectangles.append([(r0, r1, c0, c1) for r0, r1 in runs(rr) for c0, c1 in runs(cc)])
    return rb, cb, rows, columns, cells, rectangles


def render_svg(result, name="F", formula_label="Минимальная ДНФ"):
    rb, cb, rows, cols, cells, rectangles = geometry(result)
    n = len(result['variables'])
    row_indices = list(range(0,n,2)) if n > 1 else []
    col_indices = [i for i in range(n) if i not in row_indices]
    width, size, x0, y0 = 900, 80, 260, 150
    formula_y = y0 + len(rows)*size + 110
    height = formula_y + 110 + len(result['groups'])*28
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
           '<title>Диаграмма Вейча</title>',
           f'<desc>{escape(formula_label)}: {escape(result["formula"])}</desc>',
           f'<rect width="{width}" height="{height}" fill="white"/>',
           '<g font-family="Times New Roman, DejaVu Serif, serif" fill="#111">']
    def text(x,y,value,font=20,**attrs):
        extras = ' '.join(f'{k.replace("_","-")}="{v}"' for k,v in attrs.items())
        chunks = re.split(r'(¬[A-Z][0-9]*)',str(value))
        content = ''.join(f'<tspan text-decoration="overline">{escape(c[1:])}</tspan>' if c.startswith('¬') else escape(c) for c in chunks)
        out.append(f'<text x="{x}" y="{y}" font-size="{font}" {extras}>{content}</text>')
    def line(x1,y1,x2,y2):
        out.append(f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="#555" stroke-width="1"/>')
    text(450,40,'Диаграмма Вейча' + (' — '+name if name != 'F' else ''),25,text_anchor='middle',font_weight='bold')
    text(450,70,'В клетке: значение функции; внизу — номер набора',16,text_anchor='middle')
    for axis, indices, values in [('row',row_indices,rows),('col',col_indices,cols)]:
        for j,index in enumerate(indices):
            for bit in (0,1):
                for start,end in runs({k for k,v in enumerate(values) if (v >> (len(indices)-j-1)) & 1 == bit}):
                    label = ('' if bit else '¬') + result['variables'][index]
                    if axis == 'row':
                        x = x0-22 if j == 0 else x0+len(cols)*size+22
                        top,bottom = y0+start*size,y0+end*size
                        line(x,top,x,bottom);line(x-5,top,x+5,top);line(x-5,bottom,x+5,bottom)
                        text(x-20 if j == 0 else x+20,(top+bottom)/2+7,label,22,text_anchor='end' if j == 0 else 'start',font_style='italic')
                    else:
                        y = y0-22 if j == 0 else y0+len(rows)*size+25
                        left,right = x0+start*size,x0+end*size
                        line(left,y,right,y);line(left,y-5,left,y+5);line(right,y-5,right,y+5)
                        text((left+right)/2,y-12 if j == 0 else y+28,label,22,text_anchor='middle',font_style='italic')
    for r,row in enumerate(cells):
        for c,cell in enumerate(row):
            x,y = x0+c*size,y0+r*size
            out.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="white" stroke="#777"/>')
            text(x+size/2,y+45,result['truth'][cell],26,text_anchor='middle')
            text(x+size-10,y+size-9,cell,13,text_anchor='end',fill='#555')
    for j,rects in enumerate(rectangles):
        inset = 4+(j%8)*3
        dash = ['', '8 3', '3 3', '10 3 2 3'][j%4]
        for r0,r1,c0,c1 in rects:
            x,y = x0+c0*size+inset,y0+r0*size+inset
            w,h = (c1-c0)*size-2*inset,(r1-r0)*size-2*inset
            out.append(f'<rect data-group="{j+1}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="none" stroke="#111" stroke-width="1.8" stroke-dasharray="{dash}"/>')
            text(x+7,y+15,j+1,12)
    text(40,formula_y,formula_label,18)
    formula = name+' = '+result['formula']
    text(40,formula_y+34,formula,min(25,790/max(len(formula)*.6,1)))
    text(40,formula_y+67,'Части группы через края карты обозначены одинаковым номером.',15)
    for j,group in enumerate(result['groups']):
        text(40,formula_y+103+j*28,f'{j+1}. {group["term"]}   —   наборы: {", ".join(map(str,group["cells"]))}',17)
    out.append('</g></svg>')
    return ''.join(out)
