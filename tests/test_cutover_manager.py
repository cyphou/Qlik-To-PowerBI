"""Tests for powerbi_import.cutover_manager — cutover orchestration."""

import json
import os
import tempfile
import unittest

from powerbi_import.cutover_manager import (
    ReadinessCheck,
    ReadinessResult,
    CutoverStep,
    CutoverPlan,
    CutoverManager,
    _DEFAULT_CHECKS,
    _DEFAULT_STEPS,
)


class TestReadinessCheck(unittest.TestCase):
    """Test ReadinessCheck dataclass."""

    def test_creation(self):
        check = ReadinessCheck(name='data', description='Data check',
                                category='data')
        self.assertEqual(check.name, 'data')
        self.assertEqual(check.category, 'data')

    def test_to_dict(self):
        check = ReadinessCheck(name='data', description='Data check',
                                category='data')
        d = check.to_dict()
        self.assertEqual(d['name'], 'data')


class TestReadinessResult(unittest.TestCase):
    """Test ReadinessResult dataclass."""

    def test_pass(self):
        r = ReadinessResult(check_name='data', passed=True, detail='OK')
        self.assertTrue(r.passed)

    def test_fail(self):
        r = ReadinessResult(check_name='data', passed=False, detail='Missing tables')
        self.assertFalse(r.passed)

    def test_to_dict(self):
        r = ReadinessResult(check_name='data', passed=True, detail='OK')
        d = r.to_dict()
        self.assertEqual(d['check_name'], 'data')
        self.assertTrue(d['passed'])


class TestCutoverStep(unittest.TestCase):
    """Test CutoverStep dataclass."""

    def test_creation(self):
        step = CutoverStep(order=1, name='Backup',
                            status='pending')
        self.assertEqual(step.order, 1)
        self.assertEqual(step.status, 'pending')

    def test_statuses(self):
        for status in ('pending', 'in_progress', 'completed', 'skipped', 'failed'):
            step = CutoverStep(order=1, name='Step', status=status)
            self.assertEqual(step.status, status)

    def test_to_dict(self):
        step = CutoverStep(order=1, name='Backup', status='pending')
        d = step.to_dict()
        self.assertEqual(d['order'], 1)
        self.assertEqual(d['name'], 'Backup')


class TestCutoverPlan(unittest.TestCase):
    """Test CutoverPlan dataclass."""

    def test_creation(self):
        plan = CutoverPlan(app_name='Test', steps=[], readiness_results=[],
                            parallel_run_days=14)
        self.assertEqual(plan.parallel_run_days, 14)

    def test_to_dict(self):
        step = CutoverStep(order=1, name='Backup', status='pending')
        result = ReadinessResult(check_name='data', passed=True, detail='OK')
        plan = CutoverPlan(app_name='Test', steps=[step], readiness_results=[result],
                            parallel_run_days=7)
        d = plan.to_dict()
        self.assertEqual(len(d['steps']), 1)
        self.assertEqual(len(d['readiness_results']), 1)


class TestDefaultConstants(unittest.TestCase):
    """Test default constants."""

    def test_default_checks_count(self):
        self.assertGreaterEqual(len(_DEFAULT_CHECKS), 5)

    def test_default_steps_count(self):
        self.assertGreaterEqual(len(_DEFAULT_STEPS), 5)

    def test_checks_have_names(self):
        for check in _DEFAULT_CHECKS:
            self.assertTrue(check.name)

    def test_steps_ordered(self):
        orders = [s['order'] for s in _DEFAULT_STEPS]
        self.assertEqual(orders, sorted(orders))


class TestCutoverManager(unittest.TestCase):
    """Test CutoverManager."""

    def test_init(self):
        mgr = CutoverManager()
        self.assertIsNotNone(mgr)

    def test_create_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CutoverManager()
            plan = mgr.create_plan('Test')
            self.assertIsInstance(plan, CutoverPlan)
            self.assertGreater(len(plan.steps), 0)

    def test_evaluate_readiness_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CutoverManager()
            plan = mgr.create_plan('Test')
            plan = mgr.evaluate_readiness(plan)
            self.assertIsInstance(plan, CutoverPlan)

    def test_generate_runbook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CutoverManager()
            plan = mgr.create_plan('Test')
            runbook = mgr.generate_runbook(plan)
            self.assertIsInstance(runbook, str)
            self.assertIn('Test', runbook)

    def test_save_runbook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CutoverManager()
            plan = mgr.create_plan('Test')
            path = mgr.save_runbook(plan, os.path.join(tmpdir, 'runbook.md'))
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn('Test', content)

    def test_plan_with_custom_days(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = CutoverManager()
            plan = mgr.create_plan('Test', parallel_run_days=30)
            self.assertEqual(plan.parallel_run_days, 30)


class TestCutoverManagerWithData(unittest.TestCase):
    """Test CutoverManager with actual project data."""

    def test_readiness_with_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some intermediate JSON files
            import json as j
            with open(os.path.join(tmpdir, 'measures.json'), 'w') as f:
                j.dump([{'name': 'Sales'}], f)
            with open(os.path.join(tmpdir, 'datasources.json'), 'w') as f:
                j.dump([{'name': 'Source1'}], f)

            mgr = CutoverManager()
            plan = mgr.create_plan('Test')
            plan = mgr.evaluate_readiness(plan)
            self.assertIsInstance(plan, CutoverPlan)


if __name__ == '__main__':
    unittest.main()
