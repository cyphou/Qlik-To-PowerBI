"""Tests for powerbi_import.script_lineage — Qlik load script lineage."""

import unittest

from powerbi_import.script_lineage import (
    ScriptNode,
    ScriptEdge,
    ScriptLineageGraph,
    parse_script_lineage,
)


class TestScriptNode(unittest.TestCase):
    """Test ScriptNode dataclass."""

    def test_creation(self):
        node = ScriptNode(name='Sales', kind='table', fields=['Revenue', 'Qty'])
        self.assertEqual(node.name, 'Sales')
        self.assertEqual(node.kind, 'table')
        self.assertEqual(len(node.fields), 2)

    def test_kinds(self):
        for kind in ('table', 'source', 'inline', 'variable', 'mapping'):
            node = ScriptNode(name='X', kind=kind)
            self.assertEqual(node.kind, kind)

    def test_to_dict(self):
        node = ScriptNode(name='T', kind='table', fields=['A', 'B'])
        d = node.to_dict()
        self.assertEqual(d['name'], 'T')
        self.assertEqual(d['kind'], 'table')


class TestScriptEdge(unittest.TestCase):
    """Test ScriptEdge dataclass."""

    def test_creation(self):
        edge = ScriptEdge(source='DB', target='Sales', operation='LOAD')
        self.assertEqual(edge.source, 'DB')
        self.assertEqual(edge.target, 'Sales')
        self.assertEqual(edge.operation, 'LOAD')

    def test_to_dict(self):
        edge = ScriptEdge(source='A', target='B', operation='JOIN')
        d = edge.to_dict()
        self.assertEqual(d['source'], 'A')
        self.assertEqual(d['operation'], 'JOIN')


class TestScriptLineageGraph(unittest.TestCase):
    """Test ScriptLineageGraph class."""

    def test_empty(self):
        g = ScriptLineageGraph()
        self.assertEqual(len(g.nodes), 0)
        self.assertEqual(len(g.edges), 0)

    def test_add_node(self):
        g = ScriptLineageGraph()
        g.add_node('Sales', 'table', ['Revenue'])
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes['Sales'].kind, 'table')

    def test_add_edge(self):
        g = ScriptLineageGraph()
        g.add_node('DB', 'source')
        g.add_node('Sales', 'table')
        g.add_edge('DB', 'Sales', 'LOAD')
        self.assertEqual(len(g.edges), 1)

    def test_get_ancestors(self):
        g = ScriptLineageGraph()
        g.add_node('DB', 'source')
        g.add_node('Sales', 'table')
        g.add_node('Report', 'table')
        g.add_edge('DB', 'Sales', 'LOAD')
        g.add_edge('Sales', 'Report', 'RESIDENT')
        ancestors = g.get_ancestors('Report')
        self.assertIn('Sales', ancestors)

    def test_get_derived_tables(self):
        g = ScriptLineageGraph()
        g.add_node('DB', 'source')
        g.add_node('Sales', 'table')
        g.add_edge('DB', 'Sales', 'LOAD')
        derived = g.get_derived_tables()
        self.assertIn('Sales', derived)

    def test_to_dict(self):
        g = ScriptLineageGraph()
        g.add_node('T', 'table', ['A'])
        d = g.to_dict()
        self.assertIn('nodes', d)
        self.assertIn('edges', d)

    def test_get_table_nodes(self):
        g = ScriptLineageGraph()
        g.add_node('T1', 'table')
        g.add_node('S1', 'source')
        g.add_node('T2', 'table')
        tables = [n for n in g.nodes.values() if n.kind == 'table']
        self.assertEqual(len(tables), 2)


class TestParseScriptLineage(unittest.TestCase):
    """Test parse_script_lineage function."""

    def test_empty_script(self):
        g = parse_script_lineage('')
        self.assertIsInstance(g, ScriptLineageGraph)
        self.assertEqual(len(g.nodes), 0)

    def test_simple_load(self):
        script = """
Sales:
LOAD
    Revenue,
    Quantity
FROM [lib://DataFiles/sales.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',');
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_resident_load(self):
        script = """
Temp:
LOAD * FROM [lib://data.csv];

Summary:
LOAD
    Revenue
RESIDENT Temp;
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_sql_load(self):
        script = """
Sales:
LOAD *;
SQL SELECT * FROM dbo.Sales;
"""
        g = parse_script_lineage(script)
        self.assertIsInstance(g, ScriptLineageGraph)

    def test_concatenate(self):
        script = """
Sales:
LOAD * FROM [file1.csv];

CONCATENATE(Sales)
LOAD * FROM [file2.csv];
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_join(self):
        script = """
Main:
LOAD * FROM [main.csv];

JOIN(Main)
LOAD * FROM [extra.csv];
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_mapping_load(self):
        script = """
StatusMap:
MAPPING LOAD
    StatusCode,
    StatusName
FROM [lib://mapping.xlsx];
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_inline_data(self):
        script = """
Colors:
LOAD * INLINE [
    Code, Color
    1, Red
    2, Blue
];
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_let_variable(self):
        script = """
LET vToday = Today();
SET vPath = 'lib://DataFiles';
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_store_statement(self):
        script = """
Sales:
LOAD * FROM [data.csv];

STORE Sales INTO [lib://output/sales.qvd];
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)

    def test_complex_script(self):
        script = """
LET vPath = 'lib://DataFiles';

Transactions:
LOAD
    TransactionID,
    Amount,
    Date
FROM [$(vPath)/transactions.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',');

Summary:
LOAD
    Date,
    Sum(Amount) as TotalAmount
RESIDENT Transactions
GROUP BY Date;

STORE Summary INTO [lib://output/summary.qvd];
"""
        g = parse_script_lineage(script)
        self.assertGreater(len(g.nodes), 0)
        self.assertGreater(len(g.edges), 0)


if __name__ == '__main__':
    unittest.main()
