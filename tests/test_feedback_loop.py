"""Tests for powerbi_import.feedback_loop."""

import json
import os
import tempfile
import unittest

from powerbi_import.feedback_loop import FeedbackEntry, FeedbackLoop


class TestFeedbackEntry(unittest.TestCase):
    def test_to_dict(self):
        e = FeedbackEntry(
            timestamp='2025-01-01T00:00:00',
            category='dax_leak',
            description='test',
            severity='error',
        )
        d = e.to_dict()
        self.assertEqual(d['category'], 'dax_leak')
        self.assertEqual(d['severity'], 'error')
        self.assertFalse(d['resolved'])


class TestFeedbackLoop(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.log_path = os.path.join(self.td, 'feedback.json')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.td, ignore_errors=True)

    def test_report(self):
        fb = FeedbackLoop(self.log_path)
        entry = fb.report('dax_leak', 'AGGR found in DAX')
        self.assertEqual(entry.category, 'dax_leak')
        self.assertEqual(len(fb.entries), 1)

    def test_persistence(self):
        fb1 = FeedbackLoop(self.log_path)
        fb1.report('crash', 'something broke')
        fb2 = FeedbackLoop(self.log_path)
        self.assertEqual(len(fb2.entries), 1)

    def test_resolve(self):
        fb = FeedbackLoop(self.log_path)
        fb.report('other', 'test')
        self.assertTrue(fb.resolve(0))
        self.assertTrue(fb.entries[0].resolved)

    def test_resolve_invalid_index(self):
        fb = FeedbackLoop(self.log_path)
        self.assertFalse(fb.resolve(99))

    def test_report_dax_leak(self):
        fb = FeedbackLoop(self.log_path)
        entry = fb.report_dax_leak('AGGR(Sum(Sales), Region)')
        self.assertEqual(entry.category, 'dax_leak')
        self.assertEqual(entry.severity, 'error')
        self.assertTrue(entry.auto_generated)

    def test_report_visual_mismatch(self):
        fb = FeedbackLoop(self.log_path)
        entry = fb.report_visual_mismatch('customExtension')
        self.assertEqual(entry.category, 'visual_mismatch')

    def test_summary(self):
        fb = FeedbackLoop(self.log_path)
        fb.report('dax_leak', 'leak1', severity='error')
        fb.report('other', 'minor', severity='warning')
        fb.resolve(1)
        s = fb.summary()
        self.assertEqual(s['total'], 2)
        self.assertEqual(s['resolved'], 1)
        self.assertEqual(s['open'], 1)
        self.assertIn('dax_leak', s['by_category'])

    def test_generate_dashboard_html(self):
        fb = FeedbackLoop(self.log_path)
        fb.report('dax_leak', 'test leak')
        html = fb.generate_dashboard_html()
        self.assertIn('Feedback Dashboard', html)
        self.assertIn('test leak', html)

    def test_load_corrupt_file(self):
        with open(self.log_path, 'w') as f:
            f.write('not json')
        fb = FeedbackLoop(self.log_path)
        self.assertEqual(len(fb.entries), 0)


if __name__ == '__main__':
    unittest.main()
