"""Tests for powerbi_import.self_healing_report — audit trail."""

import json
import os
import tempfile
import unittest

from powerbi_import.self_healing_report import (
    SelfHealingEntry,
    SelfHealingReport,
)


class TestSelfHealingEntry(unittest.TestCase):
    """Test SelfHealingEntry dataclass."""

    def test_creation(self):
        entry = SelfHealingEntry(
            healer='datatype_casing', category='model',
            item_name='T[X]', description='Fixed casing',
            action='casing', severity='info',
        )
        self.assertEqual(entry.healer, 'datatype_casing')
        self.assertEqual(entry.severity, 'info')

    def test_timestamp(self):
        entry = SelfHealingEntry(
            healer='test', category='model',
            item_name='X', description='desc', action='fix',
        )
        self.assertIsNotNone(entry.timestamp)

    def test_to_dict(self):
        entry = SelfHealingEntry(
            healer='test', category='model',
            item_name='X', description='desc', action='fix',
            severity='warning', original_value='INT64', repaired_value='int64',
        )
        d = entry.to_dict()
        self.assertEqual(d['healer'], 'test')
        self.assertEqual(d['original_value'], 'INT64')
        self.assertEqual(d['repaired_value'], 'int64')


class TestSelfHealingReport(unittest.TestCase):
    """Test SelfHealingReport."""

    def test_empty_report(self):
        rpt = SelfHealingReport()
        self.assertEqual(rpt.repair_count, 0)
        self.assertEqual(rpt.warning_count, 0)
        self.assertEqual(rpt.error_count, 0)

    def test_record_info(self):
        rpt = SelfHealingReport()
        rpt.record(healer='test', category='model', item_name='X',
                    description='Fixed', action='fix', severity='info')
        self.assertEqual(rpt.repair_count, 1)
        self.assertEqual(rpt.warning_count, 0)

    def test_record_warning(self):
        rpt = SelfHealingReport()
        rpt.record(healer='test', category='model', item_name='X',
                    description='Warn', action='check', severity='warning')
        self.assertEqual(rpt.warning_count, 1)

    def test_record_error(self):
        rpt = SelfHealingReport()
        rpt.record(healer='test', category='model', item_name='X',
                    description='Error', action='fail', severity='error')
        self.assertEqual(rpt.error_count, 1)

    def test_get_summary(self):
        rpt = SelfHealingReport()
        rpt.record(healer='h1', category='model', item_name='A',
                    description='Fixed A', action='fix', severity='info')
        rpt.record(healer='h2', category='dax', item_name='B',
                    description='Warn B', action='check', severity='warning')
        summary = rpt.get_summary()
        self.assertIn('total_repairs', summary)
        self.assertEqual(summary['total_repairs'], 2)

    def test_to_dict(self):
        rpt = SelfHealingReport()
        rpt.record(healer='h1', category='model', item_name='A',
                    description='Fixed', action='fix')
        d = rpt.to_dict()
        self.assertIn('entries', d)
        self.assertIn('summary', d)

    def test_save_jsonl(self):
        rpt = SelfHealingReport()
        rpt.record(healer='h1', category='model', item_name='A',
                    description='Fixed', action='fix')
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'healing.jsonl')
            result = rpt.save_jsonl(path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data['healer'], 'h1')

    def test_save_json(self):
        rpt = SelfHealingReport()
        rpt.record(healer='h1', category='model', item_name='A',
                    description='Fixed', action='fix')
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'healing.json')
            result = rpt.save_json(path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertIn('entries', data)

    def test_print_summary(self):
        rpt = SelfHealingReport()
        rpt.record(healer='h1', category='model', item_name='A',
                    description='Fixed', action='fix')
        # Should not raise
        rpt.print_summary()

    def test_multiple_records(self):
        rpt = SelfHealingReport()
        for i in range(10):
            rpt.record(healer=f'h{i}', category='model', item_name=f'item{i}',
                        description=f'Fix {i}', action='fix',
                        severity='info' if i % 3 == 0 else 'warning')
        self.assertEqual(len(rpt.entries), 10)

    def test_before_after_values(self):
        rpt = SelfHealingReport()
        rpt.record(healer='casing', category='model', item_name='X',
                    description='Fixed casing', action='fix',
                    original_value='Int64', repaired_value='int64')
        entry = rpt.entries[0]
        self.assertEqual(entry.original_value, 'Int64')
        self.assertEqual(entry.repaired_value, 'int64')


if __name__ == '__main__':
    unittest.main()
