"""Tests for powerbi_import.goals_generator — Qlik KPIs → PBI Goals."""

import json
import os
import tempfile
import unittest

from powerbi_import.goals_generator import (
    PbiGoal,
    GoalsGenerator,
    generate_goals,
    _KPI_PATTERNS,
)


class TestPbiGoal(unittest.TestCase):
    """Test PbiGoal dataclass."""

    def test_creation(self):
        goal = PbiGoal(name='Sales Target', current_measure='Sales',
                        target_measure='Target Sales',
                        current_dax='SUM(T[Sales])',
                        target_dax='SUM(T[Target])')
        self.assertEqual(goal.name, 'Sales Target')

    def test_with_status_rules(self):
        goal = PbiGoal(name='Sales', current_measure='Sales',
                        status_rules={'on_target': '>=0.9', 'at_risk': '>=0.7'})
        self.assertIn('on_target', goal.status_rules)

    def test_to_dict(self):
        goal = PbiGoal(name='Revenue', current_measure='Revenue',
                        current_dax='SUM(T[Revenue])')
        d = goal.to_dict()
        self.assertEqual(d['name'], 'Revenue')
        self.assertIn('currentValue', d)
        self.assertEqual(d['currentValue']['dax'], 'SUM(T[Revenue])')


class TestKpiPatterns(unittest.TestCase):
    """Test KPI pattern constants."""

    def test_patterns_exist(self):
        self.assertGreaterEqual(len(_KPI_PATTERNS), 5)

    def test_patterns_are_compiled_regex(self):
        import re
        for pattern in _KPI_PATTERNS:
            self.assertIsInstance(pattern, re.Pattern)


class TestGoalsGenerator(unittest.TestCase):
    """Test GoalsGenerator class."""

    def test_init(self):
        gen = GoalsGenerator(app_name='TestApp')
        self.assertEqual(gen.app_name, 'TestApp')

    def test_scan_measures_empty(self):
        gen = GoalsGenerator(app_name='TestApp')
        goals = gen.scan_measures([])
        self.assertEqual(len(goals), 0)

    def test_scan_measures_with_kpi(self):
        gen = GoalsGenerator(app_name='TestApp')
        measures = [
            {'name': 'Sales Target', 'expression': 'Sum(SalesTarget)'},
            {'name': 'Sales', 'expression': 'Sum(Sales)'},
        ]
        goals = gen.scan_measures(measures)
        # Should detect 'Sales Target' and pair it with 'Sales'
        self.assertGreater(len(goals), 0)

    def test_scan_kpi_objects(self):
        gen = GoalsGenerator(app_name='TestApp')
        visuals = [
            {'type': 'kpi', 'measures': [{'name': 'Sales'}]},
        ]
        goals = gen.scan_kpi_objects(visuals)
        self.assertGreater(len(goals), 0)

    def test_scan_kpi_objects_empty(self):
        gen = GoalsGenerator(app_name='TestApp')
        goals = gen.scan_kpi_objects([])
        self.assertEqual(len(goals), 0)

    def test_scan_variables(self):
        gen = GoalsGenerator(app_name='TestApp')
        variables = [
            {'name': 'Sales Target', 'definition': '1000'},
            {'name': 'Revenue Threshold', 'definition': '0.85'},
            {'name': 'vColor', 'definition': "'#FF0000'"},
        ]
        goals = gen.scan_variables(variables)
        # Should detect target/threshold variables
        self.assertGreater(len(goals), 0)

    def test_scan_variables_empty(self):
        gen = GoalsGenerator(app_name='TestApp')
        goals = gen.scan_variables([])
        self.assertEqual(len(goals), 0)

    def test_to_dict(self):
        gen = GoalsGenerator(app_name='TestApp')
        gen.scan_measures([
            {'name': 'KPI Target', 'expression': 'Sum(Target)'},
        ])
        d = gen.to_dict()
        self.assertIn('goals', d)
        self.assertIn('app_name', d)

    def test_save(self):
        gen = GoalsGenerator(app_name='TestApp')
        gen.scan_measures([
            {'name': 'Sales Target', 'expression': 'Sum(SalesTarget)'},
            {'name': 'Sales', 'expression': 'Sum(Sales)'},
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = gen.save(os.path.join(tmpdir, 'goals.json'))
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertIn('goals', data)


class TestGenerateGoals(unittest.TestCase):
    """Test convenience function."""

    def test_empty(self):
        result = generate_goals('TestApp', {})
        self.assertIsInstance(result, dict)
        self.assertIn('goals', result)

    def test_with_measures(self):
        qlik_data = {
            'measures': [
                {'name': 'Sales Target', 'expression': 'Sum(SalesTarget)'},
                {'name': 'Sales', 'expression': 'Sum(Sales)'},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_goals('TestApp', qlik_data,
                                    output_path=os.path.join(tmpdir, 'goals.json'))
            self.assertIsInstance(result, dict)
            self.assertGreater(len(result.get('goals', [])), 0)
            self.assertTrue(os.path.exists(os.path.join(tmpdir, 'goals.json')))

    def test_with_visualizations(self):
        qlik_data = {
            'visualizations': [
                {'type': 'kpi', 'measures': [{'name': 'Revenue'}]},
            ],
        }
        result = generate_goals('TestApp', qlik_data)
        self.assertIsInstance(result, dict)

    def test_with_variables(self):
        qlik_data = {
            'variables': [
                {'name': 'vTarget', 'definition': '500'},
            ],
        }
        result = generate_goals('TestApp', qlik_data)
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()
