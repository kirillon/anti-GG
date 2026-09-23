import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
import xml.etree.ElementTree as ET
import zipfile
from veitch.system import solve_system
from veitch.timing import netlist, simulate
from veitch.excel import export_timing, ROOT


class TimingTests(unittest.TestCase):
    def circuit(self):
        r=solve_system(4,['0,2,4,6,10,12,14','2,3,10','0,1,2,3,9,11'])
        return r,netlist(r['sheffer'],r['variables'])

    def test_zero_delay_matches_truth_tables(self):
        r,c=self.circuit(); d=simulate(c,1,0,0)
        for o in r['outputs']:
            self.assertEqual(d['values'][o['name']][:16],o['truth'])

    def test_delays_and_initial_state(self):
        c={'variables':['X0'],'gates':[{'name':'I1','kind':'INV','inputs':['X0']},
            {'name':'D1','kind':'NAND','inputs':['X0','I1']}], 'outputs':[{'name':'F1','expression':'D1'}]}
        d=simulate(c,4,2,3)
        self.assertEqual(d['values']['I1'][:8],[1,1,1,1,1,1,1,0])
        # Transport model deliberately preserves the pulse caused by unequal paths.
        self.assertEqual(d['values']['F1'][:10],[1,1,1,1,1,1,1,0,0,1])
        self.assertEqual(d['initial']['D1'],1)

    def test_both_edges_use_same_delays_for_inv_and_nand(self):
        c={'variables':['X1','X0'],'gates':[
            {'name':'I1','kind':'INV','inputs':['X0']},
            {'name':'D1','kind':'NAND','inputs':['X0','X0']}], 'outputs':[]}
        d=simulate(c,6,2,3)
        expected=[1]*9+[0]*5+[1]*7+[0]*3
        self.assertEqual(d['values']['I1'][:24],expected)
        self.assertEqual(d['values']['I1'],d['values']['D1'])

    def test_simultaneous_events_prefer_later_origin(self):
        c={'variables':['X1','X0'],'gates':[{'name':'I1','kind':'INV','inputs':['X0']}], 'outputs':[]}
        d=simulate(c,1,0,1)
        self.assertEqual(d['values']['I1'][:4],[1,1,1,1])
        self.assertEqual(d['values']['I1'][4],0)

    def test_labels_and_ieee_symbols(self):
        _,c=self.circuit()
        self.assertTrue(all(g['name'].startswith('I' if g['kind']=='INV' else 'D') for g in c['gates']))
        svg=ET.fromstring(c['svg']);ns={'s':'http://www.w3.org/2000/svg'}
        self.assertTrue(svg.findall('.//s:g[@data-kind="INV"]',ns))
        self.assertTrue(svg.findall('.//s:g[@data-kind="NAND"]',ns))

    def test_compact_layout_has_separate_signal_buses(self):
        _,c=self.circuit()
        svg=ET.fromstring(c['svg']); ns={'s':'http://www.w3.org/2000/svg'}
        self.assertLess(float(svg.attrib['height']),float(svg.attrib['width']))
        buses={}
        for path in svg.findall('.//s:path[@data-source]',ns):
            x=path.attrib['d'].split()[1]
            source=path.attrib['data-source']
            self.assertEqual(buses.setdefault(x,source),source)

    def test_invalid_parameters(self):
        _,c=self.circuit()
        for args in [(0,2,3),(33,2,3),(12,-1,3),(12,2,9),(True,2,3),(12,1.5,3)]:
            with self.assertRaises(ValueError):simulate(c,*args)

    def test_constant_and_direct_outputs(self):
        r=solve_system(1,['','0,1','1'])
        d=simulate(netlist(r['sheffer'],r['variables']),1,0,0)
        self.assertEqual(d['values']['F1'],[0]*d['steps'])
        self.assertEqual(d['values']['F2'],[1]*d['steps'])
        self.assertEqual(d['values']['F3'],d['values']['X0'])

    def test_workbook_export_formulas_and_cached_values(self):
        _,c=self.circuit();d=simulate(c)
        raw=export_timing(d)
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            root=ET.fromstring(z.read('xl/worksheets/sheet2.xml'))
            formulas=root.findall('.//s:f',ns)
            self.assertTrue(any('INDEX(' in f.text for f in formulas))
            self.assertTrue(any('PRODUCT(' in f.text for f in formulas))
            for i,name in enumerate(d['signals']):
                row=root.find(f'.//s:row[@r="{i+7}"]',ns)
                values=[int(float(cell.find('s:v',ns).text)) for cell in list(row)[2:]]
                self.assertEqual(values,d['values'][name])
            wave=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
            self.assertTrue(wave.findall('s:conditionalFormatting',ns))
            self.assertTrue(wave.findall('s:mergeCells/s:mergeCell',ns))
