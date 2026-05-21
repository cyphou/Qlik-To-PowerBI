"""Tests for powerbi_import.full_lineage — end-to-end provenance tracking."""

import json
import os
import tempfile
import unittest

from powerbi_import.full_lineage import (
    LineageNode,
    LineageEdge,
    FullLineageMap,
    build_full_lineage,
    generate_lineage_html,
)


class TestLineageNode(unittest.TestCase):
    """Test LineageNode dataclass."""

    def test_creation(self):
        node = LineageNode(id='n1', kind='qlik_field', label='Sales')
        self.assertEqual(node.id, 'n1')
        self.assertEqual(node.kind, 'qlik_field')
        self.assertEqual(node.label, 'Sales')

    def test_with_metadata(self):
        node = LineageNode(id='n1', kind='dax_measure', label='Total Sales',
                            metadata={'table': 'Sales'})
        self.assertEqual(node.metadata['table'], 'Sales')

    def test_to_dict(self):
        node = LineageNode(id='n1', kind='tmdl_column', label='X')
        d = node.to_dict()
        self.assertEqual(d['id'], 'n1')
        self.assertEqual(d['kind'], 'tmdl_column')


class TestLineageEdge(unittest.TestCase):
    """Test LineageEdge dataclass."""

    def test_creation(self):
        edge = LineageEdge(source='n1', target='n2', relation='converts_to')
        self.assertEqual(edge.source, 'n1')
        self.assertEqual(edge.target, 'n2')
        self.assertEqual(edge.relation, 'converts_to')

    def test_to_dict(self):
        edge = LineageEdge(source='n1', target='n2', relation='feeds')
        d = edge.to_dict()
        self.assertEqual(d['source'], 'n1')
        self.assertEqual(d['target'], 'n2')


class TestFullLineageMap(unittest.TestCase):
    """Test FullLineageMap."""

    def test_empty(self):
        lm = FullLineageMap()
        self.assertEqual(len(lm.nodes), 0)
        self.assertEqual(len(lm.edges), 0)

    def test_add_node(self):
        lm = FullLineageMap()
        lm.add_node('n1', 'qlik_field', 'Sales')
        self.assertIn('n1', lm.nodes)
        self.assertEqual(lm.nodes['n1'].label, 'Sales')

    def test_add_edge(self):
        lm = FullLineageMap()
        lm.add_node('n1', 'qlik_field', 'Sales')
        lm.add_node('n2', 'dax_measure', 'Total Sales')
        lm.add_edge('n1', 'n2', 'converts_to')
        self.assertEqual(len(lm.edges), 1)

    def test_get_ancestors(self):
        lm = FullLineageMap()
        lm.add_node('a', 'source', 'A')
        lm.add_node('b', 'field', 'B')
        lm.add_node('c', 'measure', 'C')
        lm.add_edge('a', 'b', 'feeds')
        lm.add_edge('b', 'c', 'converts_to')
        ancestors = lm.get_ancestors('c')
        self.assertIn('a', ancestors)
        self.assertIn('b', ancestors)

    def test_get_descendants(self):
        lm = FullLineageMap()
        lm.add_node('a', 'source', 'A')
        lm.add_node('b', 'field', 'B')
        lm.add_node('c', 'measure', 'C')
        lm.add_edge('a', 'b', 'feeds')
        lm.add_edge('b', 'c', 'converts_to')
        descendants = lm.get_descendants('a')
        self.assertIn('b', descendants)
        self.assertIn('c', descendants)

    def test_get_orphans(self):
        lm = FullLineageMap()
        lm.add_node('a', 'source', 'A')
        lm.add_node('b', 'field', 'B')
        lm.add_node('orphan', 'field', 'Orphan')
        lm.add_edge('a', 'b', 'feeds')
        orphans = lm.get_orphans()
        self.assertIn('orphan', orphans)

    def test_save(self):
        lm = FullLineageMap()
        lm.add_node('n1', 'field', 'X')
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'lineage.json')
            lm.save(path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertIn('nodes', data)
            self.assertIn('edges', data)


class TestBuildFullLineage(unittest.TestCase):
    """Test build_full_lineage function."""

    def test_empty_data(self):
        lineage = build_full_lineage('TestApp', {}, {}, {}, {})
        self.assertIsInstance(lineage, FullLineageMap)

    def test_with_measures(self):
        qlik_data = {
            'measures': [{'name': 'Sales', 'expression': 'Sum(Sales)'}],
        }
        calc_map = {'Sales': 'SUM(T[Sales])'}
        lineage = build_full_lineage('TestApp', qlik_data, calc_map, {}, {})
        self.assertGreater(len(lineage.nodes), 0)

    def test_with_dimensions(self):
        qlik_data = {
            'dimensions': [{'name': 'Year', 'field': 'Year'}],
        }
        lineage = build_full_lineage('TestApp', qlik_data, {}, {}, {})
        self.assertGreater(len(lineage.nodes), 0)

    def test_with_datasources(self):
        qlik_data = {
            'datasources': [{'name': 'DB', 'tables': [
                {'name': 'Sales', 'columns': [{'name': 'Revenue'}]}
            ]}],
        }
        lineage = build_full_lineage('TestApp', qlik_data, {}, {}, {})
        self.assertGreater(len(lineage.nodes), 0)

    def test_with_model(self):
        qlik_data = {'measures': [{'name': 'Sales', 'expression': 'Sum(Sales)'}]}
        model = {'tables': [{'name': 'T', 'measures': [
            {'name': 'Sales', 'expression': 'SUM(T[Sales])'}
        ]}]}
        lineage = build_full_lineage('TestApp', qlik_data, {}, model, {})
        self.assertGreater(len(lineage.nodes), 0)

    def test_with_report_state(self):
        qlik_data = {'visualizations': [
            {'id': 'v1', 'type': 'barchart', 'measures': [{'name': 'Sales'}]}
        ]}
        report_state = {'pages': [{'visuals': [
            {'id': 'v1', 'type': 'clusteredBarChart'}
        ]}]}
        lineage = build_full_lineage('TestApp', qlik_data, {}, {}, report_state)
        self.assertGreater(len(lineage.nodes), 0)


class TestGenerateLineageHtml(unittest.TestCase):
    """Test HTML lineage report generation."""

    def test_empty_lineage(self):
        lm = FullLineageMap()
        html = generate_lineage_html(lm)
        self.assertIn('<html', html)

    def test_with_nodes(self):
        lm = FullLineageMap()
        lm.add_node('n1', 'qlik_field', 'Sales')
        lm.add_node('n2', 'dax_measure', 'Total Sales')
        lm.add_edge('n1', 'n2', 'converts_to')
        html = generate_lineage_html(lm)
        self.assertIn('qlik_field', html)
        self.assertIn('<html', html)


if __name__ == '__main__':
    unittest.main()
