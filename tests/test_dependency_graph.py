"""Tests for powerbi_import.dependency_graph."""

import unittest

from powerbi_import.dependency_graph import (
    Node,
    Edge,
    DependencyGraph,
)


class TestNode(unittest.TestCase):
    def test_hash_by_id(self):
        n1 = Node(id='a', kind='table')
        n2 = Node(id='a', kind='measure')
        self.assertEqual(hash(n1), hash(n2))

    def test_equality(self):
        n1 = Node(id='x', kind='table')
        n2 = Node(id='x', kind='measure')
        self.assertEqual(n1, n2)

    def test_inequality(self):
        n1 = Node(id='a', kind='table')
        n2 = Node(id='b', kind='table')
        self.assertNotEqual(n1, n2)


class TestEdge(unittest.TestCase):
    def test_equality(self):
        e1 = Edge(source='a', target='b', relation='feeds')
        e2 = Edge(source='a', target='b', relation='feeds')
        self.assertEqual(e1, e2)


class TestDependencyGraph(unittest.TestCase):
    def test_add_node(self):
        g = DependencyGraph()
        n = g.add_node('t1', 'table', label='Table1')
        self.assertEqual(n.id, 't1')
        self.assertIn('t1', g.nodes)

    def test_add_duplicate_node(self):
        g = DependencyGraph()
        g.add_node('t1', 'table')
        n2 = g.add_node('t1', 'table')
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(n2.id, 't1')

    def test_add_edge(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_edge('a', 'b', 'feeds')
        self.assertEqual(len(g.edges), 1)

    def test_successors_predecessors(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_edge('a', 'b')
        self.assertIn('b', g.successors('a'))
        self.assertIn('a', g.predecessors('b'))

    def test_roots_and_leaves(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_node('c', 'visual')
        g.add_edge('a', 'b')
        g.add_edge('b', 'c')
        self.assertIn('a', g.roots())
        self.assertIn('c', g.leaves())

    def test_orphans(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_node('orphan', 'measure')
        g.add_edge('a', 'b')
        self.assertIn('orphan', g.orphans())

    def test_detect_cycles_none(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_edge('a', 'b')
        self.assertEqual(len(g.detect_cycles()), 0)

    def test_detect_cycles_present(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_edge('a', 'b')
        g.add_edge('b', 'a')
        cycles = g.detect_cycles()
        self.assertGreater(len(cycles), 0)

    def test_topological_sort(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_node('c', 'visual')
        g.add_edge('a', 'b')
        g.add_edge('b', 'c')
        topo = g.topological_sort()
        self.assertEqual(len(topo), 3)
        self.assertLess(topo.index('a'), topo.index('b'))
        self.assertLess(topo.index('b'), topo.index('c'))

    def test_topological_sort_cycle_empty(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_edge('a', 'b')
        g.add_edge('b', 'a')
        self.assertEqual(g.topological_sort(), [])

    def test_critical_path(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_node('c', 'measure')
        g.add_node('d', 'visual')
        g.add_edge('a', 'b')
        g.add_edge('b', 'c')
        g.add_edge('c', 'd')
        path = g.critical_path()
        self.assertEqual(path, ['a', 'b', 'c', 'd'])

    def test_downstream_impact(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_node('c', 'visual')
        g.add_edge('a', 'b')
        g.add_edge('b', 'c')
        impact = g.downstream_impact('a')
        self.assertIn('b', impact)
        self.assertIn('c', impact)

    def test_upstream_deps(self):
        g = DependencyGraph()
        g.add_node('a', 'ds')
        g.add_node('b', 'table')
        g.add_node('c', 'visual')
        g.add_edge('a', 'b')
        g.add_edge('b', 'c')
        deps = g.upstream_deps('c')
        self.assertIn('b', deps)
        self.assertIn('a', deps)


class TestFromExtraction(unittest.TestCase):
    def test_basic_extraction(self):
        data = {
            'datasources': [{'name': 'SQL_Server'}],
            'tables': [{'name': 'Sales', 'datasource': 'SQL_Server'}],
            'measures': [{'name': 'Total', 'table': 'Sales'}],
            'visuals': [{'id': 'v1', 'measures': ['Total'], 'fields': ['Sales.Amount']}],
        }
        g = DependencyGraph.from_extraction(data, app_name='TestApp')
        self.assertGreater(len(g.nodes), 0)
        self.assertGreater(len(g.edges), 0)

    def test_empty_extraction(self):
        g = DependencyGraph.from_extraction({})
        self.assertEqual(len(g.nodes), 0)


class TestSerialization(unittest.TestCase):
    def test_to_dict(self):
        g = DependencyGraph()
        g.add_node('a', 'ds', label='DS')
        g.add_node('b', 'table', label='T')
        g.add_edge('a', 'b')
        d = g.to_dict()
        self.assertEqual(d['node_count'], 2)
        self.assertEqual(d['edge_count'], 1)

    def test_to_mermaid(self):
        g = DependencyGraph()
        g.add_node('a', 'ds', label='DataSource')
        g.add_node('b', 'table', label='Table')
        g.add_edge('a', 'b', 'feeds')
        mermaid = g.to_mermaid()
        self.assertIn('graph LR', mermaid)
        self.assertIn('DataSource', mermaid)


if __name__ == '__main__':
    unittest.main()
