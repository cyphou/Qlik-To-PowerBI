"""Tests for powerbi_import.rollback_engine — severity-based quality gate."""

import json
import os
import shutil
import tempfile
import unittest

from powerbi_import.rollback_engine import (
    Severity,
    Verdict,
    RollbackEngine,
)


class TestSeverity(unittest.TestCase):
    def test_worse_returns_higher(self):
        self.assertEqual(Severity.worse(Severity.INFO, Severity.ERROR), Severity.ERROR)
        self.assertEqual(Severity.worse(Severity.CRITICAL, Severity.WARNING), Severity.CRITICAL)

    def test_worse_equal(self):
        self.assertEqual(Severity.worse(Severity.WARNING, Severity.WARNING), Severity.WARNING)

    def test_level_ordering(self):
        self.assertLess(Severity.level(Severity.INFO), Severity.level(Severity.WARNING))
        self.assertLess(Severity.level(Severity.WARNING), Severity.level(Severity.ERROR))
        self.assertLess(Severity.level(Severity.ERROR), Severity.level(Severity.CRITICAL))


class TestVerdict(unittest.TestCase):
    def test_clean_verdict(self):
        v = Verdict(Severity.INFO, [])
        self.assertTrue(v.should_ship)
        self.assertFalse(v.should_quarantine)
        self.assertFalse(v.should_rollback)
        self.assertEqual(v.exit_code, 0)

    def test_warning_verdict(self):
        v = Verdict(Severity.WARNING, [(Severity.WARNING, 'test', 'msg')])
        self.assertTrue(v.should_ship)
        self.assertEqual(v.exit_code, 1)

    def test_error_verdict(self):
        v = Verdict(Severity.ERROR, [(Severity.ERROR, 'test', 'msg')])
        self.assertTrue(v.should_quarantine)
        self.assertFalse(v.should_ship)
        self.assertEqual(v.exit_code, 2)

    def test_critical_verdict(self):
        v = Verdict(Severity.CRITICAL, [(Severity.CRITICAL, 'test', 'msg')])
        self.assertTrue(v.should_rollback)
        self.assertEqual(v.exit_code, 3)

    def test_to_dict(self):
        v = Verdict(Severity.INFO, [], 'Clean')
        d = v.to_dict()
        self.assertEqual(d['severity'], 'info')
        self.assertEqual(d['issue_count'], 0)
        self.assertIn('timestamp', d)

    def test_auto_message(self):
        v = Verdict(Severity.WARNING, [
            (Severity.WARNING, 's', 'm1'),
            (Severity.WARNING, 's', 'm2'),
        ])
        self.assertIn('2 warning', v.message)


class TestRollbackEngine(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.project = os.path.join(self.td, 'TestApp')
        os.makedirs(self.project)
        self.engine = RollbackEngine(self.project, 'TestApp')

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_evaluate_clean(self):
        verdict = self.engine.evaluate()
        self.assertEqual(verdict.severity, Severity.INFO)
        self.assertTrue(verdict.should_ship)

    def test_ingest_validation_errors(self):
        self.engine.ingest_validation({
            'errors': ['bad field', 'missing col'],
            'warnings': ['minor issue'],
        })
        verdict = self.engine.evaluate()
        self.assertEqual(verdict.severity, Severity.ERROR)

    def test_ingest_schema_result(self):
        self.engine.ingest_schema_result([{
            'issues': [
                {'severity': 'error', 'message': 'missing $schema', 'path': '$schema'},
            ]
        }])
        verdict = self.engine.evaluate()
        self.assertEqual(verdict.severity, Severity.ERROR)

    def test_ingest_schema_repaired(self):
        self.engine.ingest_schema_result([{
            'issues': [
                {'severity': 'warning', 'message': 'coerced', 'path': 'pos.x', 'repaired': True},
            ]
        }])
        verdict = self.engine.evaluate()
        self.assertEqual(verdict.severity, Severity.INFO)

    def test_ingest_cross_result(self):
        self.engine.ingest_cross_result({
            'issues': [
                {'severity': 'error', 'message': 'field not found'},
                {'severity': 'warning', 'message': 'unused measure'},
            ]
        })
        verdict = self.engine.evaluate()
        self.assertEqual(verdict.severity, Severity.ERROR)

    def test_ingest_repairs(self):
        self.engine.ingest_repairs({
            'repairs': [
                {'severity': 'error', 'description': 'fixed leak', 'category': 'dax'},
            ]
        })
        verdict = self.engine.evaluate()
        self.assertEqual(verdict.severity, Severity.WARNING)

    def test_ingest_qa_report(self):
        qa_path = os.path.join(self.td, 'qa_report.json')
        with open(qa_path, 'w') as f:
            json.dump({
                'validation': {
                    'error_details': ['err1'],
                    'warnings': 3,
                },
                'auto_fix': {'total_repairs': 5},
            }, f)
        self.engine.ingest_qa_report(qa_path)
        verdict = self.engine.evaluate()
        self.assertEqual(verdict.severity, Severity.ERROR)

    def test_execute_ship(self):
        verdict = Verdict(Severity.INFO, [])
        result = self.engine.execute(verdict)
        self.assertEqual(result['action'], 'ship')
        self.assertEqual(result['exit_code'], 0)

    def test_execute_quarantine(self):
        # Create a dummy file in project dir
        with open(os.path.join(self.project, 'test.json'), 'w') as f:
            f.write('{}')
        verdict = Verdict(Severity.ERROR, [(Severity.ERROR, 'test', 'bad')])
        result = self.engine.execute(verdict)
        self.assertEqual(result['action'], 'quarantine')
        self.assertIsNotNone(result['triage_path'])

    def test_execute_rollback(self):
        with open(os.path.join(self.project, 'test.json'), 'w') as f:
            f.write('{}')
        verdict = Verdict(Severity.CRITICAL, [(Severity.CRITICAL, 'test', 'fatal')])
        result = self.engine.execute(verdict, source_file='test.qvf')
        self.assertEqual(result['action'], 'rollback')

    def test_execute_strict_exit_code(self):
        verdict = Verdict(Severity.WARNING, [(Severity.WARNING, 's', 'm')])
        result = self.engine.execute(verdict, strict=True)
        self.assertEqual(result['exit_code'], 1)

    def test_execute_non_strict_exit_code(self):
        verdict = Verdict(Severity.WARNING, [(Severity.WARNING, 's', 'm')])
        result = self.engine.execute(verdict, strict=False)
        self.assertEqual(result['exit_code'], 0)


if __name__ == '__main__':
    unittest.main()
