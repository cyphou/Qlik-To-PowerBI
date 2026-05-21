"""Tests for powerbi_import.script_lineage_report — HTML lineage visualization."""

import os
import tempfile
import unittest

from powerbi_import.script_lineage import ScriptLineageGraph, parse_script_lineage
from powerbi_import.script_lineage_report import (
    generate_script_lineage_html,
    generate_script_lineage_report,
)


class TestGenerateScriptLineageHtml(unittest.TestCase):
    """Test HTML generation."""

    def test_empty_graph(self):
        g = ScriptLineageGraph()
        html = generate_script_lineage_html(g)
        self.assertIn('<html', html)

    def test_with_nodes(self):
        g = ScriptLineageGraph()
        g.add_node('Sales', 'table', ['Revenue', 'Qty'])
        g.add_node('DB', 'source')
        g.add_edge('DB', 'Sales', 'LOAD')
        html = generate_script_lineage_html(g)
        self.assertIn('Sales', html)

    def test_with_app_name(self):
        g = ScriptLineageGraph()
        g.add_node('T', 'table')
        html = generate_script_lineage_html(g, app_name='MyApp')
        self.assertIn('MyApp', html)

    def test_mermaid_diagram(self):
        g = ScriptLineageGraph()
        g.add_node('A', 'source')
        g.add_node('B', 'table')
        g.add_edge('A', 'B', 'LOAD')
        html = generate_script_lineage_html(g)
        # Should contain Mermaid markup or some diagram notation
        self.assertIn('<html', html)

    def test_from_parsed_script(self):
        script = """
Sales:
LOAD Revenue, Qty
FROM [lib://data.csv];
"""
        g = parse_script_lineage(script)
        html = generate_script_lineage_html(g, app_name='Test')
        self.assertIn('<html', html)


class TestGenerateScriptLineageReport(unittest.TestCase):
    """Test report file generation."""

    def test_saves_html(self):
        g = ScriptLineageGraph()
        g.add_node('Sales', 'table')
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_script_lineage_report(g, 'TestApp', tmpdir)
            # Should return filepath string
            self.assertIsInstance(result, str)
            self.assertTrue(os.path.exists(result))

    def test_saves_json(self):
        g = ScriptLineageGraph()
        g.add_node('Sales', 'table')
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_script_lineage_report(g, 'TestApp', tmpdir)
            # JSON file should be created alongside HTML
            json_path = os.path.join(tmpdir, 'TestApp_lineage.json')
            self.assertTrue(os.path.exists(json_path))

    def test_with_complex_graph(self):
        g = ScriptLineageGraph()
        g.add_node('DB', 'source')
        g.add_node('Sales', 'table', ['Revenue', 'Qty'])
        g.add_node('Summary', 'table', ['TotalRevenue'])
        g.add_edge('DB', 'Sales', 'LOAD')
        g.add_edge('Sales', 'Summary', 'RESIDENT')
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_script_lineage_report(g, 'TestApp', tmpdir)
            self.assertIsInstance(result, str)

    def test_empty_graph_report(self):
        g = ScriptLineageGraph()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_script_lineage_report(g, 'EmptyApp', tmpdir)
            self.assertIsInstance(result, str)


class TestScriptLineageReportIntegration(unittest.TestCase):
    """Integration tests with parsed scripts."""

    def test_full_pipeline(self):
        script = """
LET vPath = 'lib://Data';

Transactions:
LOAD
    ID,
    Amount
FROM [$(vPath)/trans.csv];

Summary:
LOAD
    Sum(Amount) as Total
RESIDENT Transactions;

STORE Summary INTO [lib://out/summary.qvd];
"""
        g = parse_script_lineage(script)
        html = generate_script_lineage_html(g, app_name='Pipeline Test')
        self.assertIn('<html', html)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_script_lineage_report(g, 'Pipeline Test', tmpdir)
            self.assertIsInstance(result, str)


if __name__ == '__main__':
    unittest.main()
