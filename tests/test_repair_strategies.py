"""Tests for powerbi_import.repair_strategies — deterministic repairs."""

import unittest

from powerbi_import.repair_strategies import (
    RepairResult,
    RepairStrategy,
    RepairRegistry,
    build_default_registry,
    _repair_qlik_leak,
    _repair_paren_balance,
    _repair_empty_measure,
    _repair_m_if_else,
    _repair_single_quotes_m,
)


class TestRepairResult(unittest.TestCase):
    """Test RepairResult dataclass."""

    def test_creation(self):
        r = RepairResult(status='repaired', artifact='m1',
                         strategy='leak_fix', issues_before=['i1', 'i2'], issues_after=[])
        self.assertEqual(r.status, 'repaired')
        self.assertEqual(r.artifact, 'm1')

    def test_statuses(self):
        for status in ('repaired', 'unchanged', 'rejected', 'error'):
            r = RepairResult(status=status, artifact='x', strategy='s')
            self.assertEqual(r.status, status)

    def test_to_dict(self):
        r = RepairResult(status='repaired', artifact='m1',
                         strategy='fix', notes='done')
        d = r.to_dict()
        self.assertEqual(d['status'], 'repaired')
        self.assertIn('notes', d)


class TestRepairStrategy(unittest.TestCase):
    """Test RepairStrategy dataclass."""

    def test_creation(self):
        def dummy(artifact, issues, context):
            return artifact
        s = RepairStrategy(name='test', fn=dummy, category='deterministic',
                           applies_to='dax')
        self.assertEqual(s.name, 'test')
        self.assertEqual(s.category, 'deterministic')

    def test_categories(self):
        def dummy(artifact, issues, context):
            return artifact
        for cat in ('deterministic', 'llm'):
            s = RepairStrategy(name='test', fn=dummy, category=cat)
            self.assertEqual(s.category, cat)


class TestRepairRegistry(unittest.TestCase):
    """Test RepairRegistry."""

    def test_add_and_list(self):
        reg = RepairRegistry()
        def dummy(artifact, issues, context):
            return artifact
        strat = RepairStrategy(name='test', fn=dummy, category='deterministic')
        reg.add(strat)
        self.assertEqual(len(reg.strategies), 1)

    def test_run_no_change(self):
        reg = RepairRegistry()
        def noop(artifact, issues, context):
            return artifact
        strat = RepairStrategy(name='noop', fn=noop, category='deterministic',
                                applies_to='dax')
        reg.add(strat)
        results = reg.run('SUM(T[X])', [])
        self.assertIsInstance(results, list)

    def test_run_with_change(self):
        reg = RepairRegistry()
        def fix(artifact, issues, context):
            return artifact.replace('bad', 'good')
        strat = RepairStrategy(name='fixer', fn=fix, category='deterministic',
                                applies_to='dax')
        reg.add(strat)
        results = reg.run('bad expression', ['needs fix'])
        # Should have at least one result
        self.assertGreaterEqual(len(results), 1)


class TestBuildDefaultRegistry(unittest.TestCase):
    """Test default registry creation."""

    def test_has_strategies(self):
        reg = build_default_registry()
        self.assertGreater(len(reg.strategies), 0)

    def test_has_at_least_five(self):
        reg = build_default_registry()
        self.assertGreaterEqual(len(reg.strategies), 5)


class TestRepairQlikLeak(unittest.TestCase):
    """Test _repair_qlik_leak."""

    def test_no_leak(self):
        result = _repair_qlik_leak('SUM(T[Sales])', [], {})
        self.assertEqual(result, 'SUM(T[Sales])')

    def test_aggr_replaced(self):
        result = _repair_qlik_leak('AGGR(Sum(Sales), Year)', [], {})
        self.assertNotIn('AGGR', result)

    def test_alt_replaced(self):
        result = _repair_qlik_leak("ALT(Field, 'default')", [], {})
        self.assertNotIn('ALT(', result)

    def test_only_replaced(self):
        result = _repair_qlik_leak('ONLY(Field)', [], {})
        self.assertNotIn('ONLY(', result)


class TestRepairParenBalance(unittest.TestCase):
    """Test _repair_paren_balance."""

    def test_balanced(self):
        result = _repair_paren_balance('SUM(T[X])', [], {})
        self.assertEqual(result, 'SUM(T[X])')

    def test_missing_close(self):
        result = _repair_paren_balance('SUM(T[X]', [], {})
        self.assertEqual(result.count('('), result.count(')'))

    def test_missing_open(self):
        result = _repair_paren_balance('SUM T[X])', [], {})
        self.assertEqual(result.count('('), result.count(')'))

    def test_empty(self):
        result = _repair_paren_balance('', [], {})
        self.assertEqual(result, '')


class TestRepairEmptyMeasure(unittest.TestCase):
    """Test _repair_empty_measure."""

    def test_non_empty_unchanged(self):
        result = _repair_empty_measure('SUM(T[X])', [], {})
        self.assertEqual(result, 'SUM(T[X])')

    def test_empty_gets_placeholder(self):
        result = _repair_empty_measure('', [], {})
        self.assertIn('BLANK()', result)

    def test_whitespace_gets_placeholder(self):
        result = _repair_empty_measure('   ', [], {})
        self.assertIn('BLANK()', result)


class TestRepairMIfElse(unittest.TestCase):
    """Test _repair_m_if_else."""

    def test_no_change(self):
        result = _repair_m_if_else('if x then y else z', [], {})
        self.assertEqual(result, 'if x then y else z')

    def test_empty(self):
        result = _repair_m_if_else('', [], {})
        self.assertEqual(result, '')


class TestRepairSingleQuotesM(unittest.TestCase):
    """Test _repair_single_quotes_m."""

    def test_no_change(self):
        result = _repair_single_quotes_m('"hello"', [], {})
        self.assertEqual(result, '"hello"')

    def test_empty(self):
        result = _repair_single_quotes_m('', [], {})
        self.assertEqual(result, '')


if __name__ == '__main__':
    unittest.main()
