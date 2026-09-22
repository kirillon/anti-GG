import unittest
import xml.etree.ElementTree as ET
from veitch.logic import minimize, parse
from veitch.diagram import geometry, render_svg, gray


class DiagramTests(unittest.TestCase):
    def test_gray_neighbors_include_boundary(self):
        for bits in (1, 2):
            values = gray(bits)
            for a, b in zip(values, values[1:] + values[:1]):
                self.assertEqual((a ^ b).bit_count(), 1)

    def test_wraparound_four_corners(self):
        result = minimize(parse("F(A,B,C,D)=!C*!D"))
        *_, cells, rectangles = geometry(result)
        self.assertEqual(result["groups"][0]["cells"], [0, 4, 8, 12])
        self.assertEqual(len(rectangles[0]), 4)
        self.assertEqual({cells[r][c] for r in (0, 3) for c in (0, 3)}, {0, 4, 8, 12})

    def test_rectangles_match_terms_and_svg_is_valid(self):
        for source in ["0", "1", "A", "A+B", "A^B^C", "F(A,B,C,D)=!C*!D", "A*B+B*C"]:
            result = minimize(parse(source))
            *_, cells, rectangles = geometry(result)
            for group, rects in zip(result["groups"], rectangles):
                drawn = {cells[r][c] for r0, r1, c0, c1 in rects for r in range(r0, r1) for c in range(c0, c1)}
                self.assertEqual(drawn, set(group["cells"]))
            svg = ET.fromstring(render_svg(result))
            ns = {"s": "http://www.w3.org/2000/svg"}
            self.assertIn(result["formula"], svg.find("s:desc", ns).text)
            self.assertEqual(len(svg.findall(".//s:rect[@data-group]", ns)), sum(map(len, rectangles)))

    def test_textbook_cell_order(self):
        *_, cells, _ = geometry(minimize(parse("F(A,B,C,D)=1")))
        self.assertEqual(cells, [[12,13,9,8],[14,15,11,10],[6,7,3,2],[4,5,1,0]])
