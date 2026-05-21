"""Tests for powerbi_import.preceptor — preceptorship review loop."""

import json
import os
import tempfile
import unittest

from powerbi_import.preceptor import (
    CoachingItem,
    ReviewScorecard,
    ReviewCycle,
    ReviewReport,
    PreceptorLoop,
    run_preceptor_review,
    DIMENSIONS,
    MIN_PASS_SCORE,
    MAX_CYCLES,
    _review_completeness,
    _review_dax_correctness,
    _review_m_query_validity,
    _review_tmdl_structure,
    _review_pbir_fidelity,
    _review_visual_equivalence,
)


class TestCoachingItem(unittest.TestCase):
    """Test CoachingItem dataclass."""

    def test_creation(self):
        item = CoachingItem(dimension='completeness', score=3,
                            issue='Missing columns', location='table1')
        self.assertEqual(item.dimension, 'completeness')
        self.assertEqual(item.location, 'table1')
        self.assertEqual(item.issue, 'Missing columns')

    def test_to_dict(self):
        item = CoachingItem(dimension='dax', score=2,
                            issue='Qlik leak', location='m1')
        d = item.to_dict()
        self.assertEqual(d['dimension'], 'dax')
        self.assertEqual(d['issue'], 'Qlik leak')


class TestReviewScorecard(unittest.TestCase):
    """Test ReviewScorecard dataclass."""

    def test_scores(self):
        sc = ReviewScorecard()
        sc.set_score('completeness', 5.0)
        sc.set_score('dax_correctness', 4.0)
        self.assertEqual(sc.scores['completeness'], 5.0)
        self.assertEqual(sc.scores['dax_correctness'], 4.0)

    def test_average_score(self):
        sc = ReviewScorecard()
        for dim in DIMENSIONS:
            sc.set_score(dim, 5.0)
        self.assertEqual(sc.average(), 5.0)

    def test_average_mixed(self):
        sc = ReviewScorecard()
        sc.set_score('completeness', 4.0)
        sc.set_score('dax_correctness', 3.0)
        sc.set_score('m_query_validity', 5.0)
        sc.set_score('tmdl_structure', 4.0)
        sc.set_score('pbir_fidelity', 3.0)
        sc.set_score('visual_equivalence', 5.0)
        avg = sc.average()
        self.assertAlmostEqual(avg, 4.0, places=1)

    def test_to_dict(self):
        sc = ReviewScorecard()
        d = sc.to_dict()
        self.assertIn('scores', d)
        self.assertIn('average', d)


class TestReviewCycle(unittest.TestCase):
    """Test ReviewCycle dataclass."""

    def test_creation(self):
        cycle = ReviewCycle(cycle_number=1)
        self.assertEqual(cycle.cycle_number, 1)
        self.assertIsNotNone(cycle.scorecard)

    def test_to_dict(self):
        cycle = ReviewCycle(cycle_number=1)
        cycle.scorecard.set_score('completeness', 4.0)
        item = CoachingItem(dimension='dax', score=2, issue='leak', location='m1')
        cycle.add_coaching(item)
        d = cycle.to_dict()
        self.assertEqual(d['cycle'], 1)
        self.assertEqual(len(d['coaching_items']), 1)


class TestReviewReport(unittest.TestCase):
    """Test ReviewReport dataclass."""

    def test_approved(self):
        rpt = ReviewReport(report_name='Test')
        rpt.status = ReviewReport.APPROVED
        self.assertEqual(rpt.status, 'approved')

    def test_statuses(self):
        for status in (ReviewReport.APPROVED, ReviewReport.COACHING,
                       ReviewReport.ESCALATED_WARN, ReviewReport.ESCALATED_BLOCK):
            rpt = ReviewReport(report_name='X')
            rpt.status = status
            self.assertEqual(rpt.status, status)

    def test_to_dict(self):
        rpt = ReviewReport(report_name='MyApp')
        rpt.status = ReviewReport.COACHING
        d = rpt.to_dict()
        self.assertEqual(d['report_name'], 'MyApp')
        self.assertEqual(d['status'], 'coaching')


class TestPreceptorLoopConstants(unittest.TestCase):
    """Test module-level constants."""

    def test_dimensions(self):
        self.assertEqual(len(DIMENSIONS), 6)
        self.assertIn('completeness', DIMENSIONS)
        self.assertIn('dax_correctness', DIMENSIONS)

    def test_min_pass_score(self):
        self.assertIsInstance(MIN_PASS_SCORE, (int, float))
        self.assertGreater(MIN_PASS_SCORE, 0)

    def test_max_cycles(self):
        self.assertIsInstance(MAX_CYCLES, int)
        self.assertGreater(MAX_CYCLES, 0)


class TestPreceptorLoopInit(unittest.TestCase):
    """Test PreceptorLoop initialization."""

    def test_default_init(self):
        loop = PreceptorLoop()
        self.assertIsNotNone(loop)

    def test_custom_min_score(self):
        loop = PreceptorLoop(min_score=3.0)
        self.assertEqual(loop.min_score, 3.0)


class TestPreceptorLoopReviewDimensions(unittest.TestCase):
    """Test individual review dimension functions (module-level)."""

    def test_review_completeness_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            score, detail, items = _review_completeness(tmpdir, {})
            self.assertIsInstance(score, (int, float))
            self.assertIsInstance(items, list)

    def test_review_completeness_with_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qlik = {'measures': [{'name': 'Sales'}], 'dimensions': [{'name': 'Year'}]}
            score, detail, items = _review_completeness(tmpdir, qlik)
            self.assertGreaterEqual(score, 0)

    def test_review_dax_correctness_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            score, detail, items = _review_dax_correctness(tmpdir, {})
            self.assertIsInstance(score, (int, float))

    def test_review_m_query_validity_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            score, detail, items = _review_m_query_validity(tmpdir, {})
            self.assertIsInstance(score, (int, float))

    def test_review_tmdl_structure_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            score, detail, items = _review_tmdl_structure(tmpdir, {})
            self.assertIsInstance(score, (int, float))

    def test_review_pbir_fidelity_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            score, detail, items = _review_pbir_fidelity(tmpdir, {})
            self.assertIsInstance(score, (int, float))

    def test_review_visual_equivalence_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            score, detail, items = _review_visual_equivalence(tmpdir, {})
            self.assertIsInstance(score, (int, float))


class TestPreceptorLoopRun(unittest.TestCase):
    """Test PreceptorLoop.run() with temp directories."""

    def test_run_empty_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = PreceptorLoop()
            report = loop.run(tmpdir, tmpdir)
            self.assertIsInstance(report, ReviewReport)
            self.assertIn(report.status,
                          ('approved', 'coaching', 'escalated_warn', 'escalated_block'))

    def test_run_with_json_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write minimal extraction JSON
            data = {'measures': [{'name': 'Sales', 'expression': 'Sum(Sales)'}]}
            with open(os.path.join(tmpdir, 'measures.json'), 'w') as f:
                json.dump(data, f)

            loop = PreceptorLoop()
            report = loop.run(tmpdir, tmpdir)
            self.assertIsInstance(report, ReviewReport)
            self.assertGreaterEqual(report.total_cycles, 1)


class TestRunPreceptorReview(unittest.TestCase):
    """Test convenience function."""

    def test_convenience_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_preceptor_review(tmpdir, tmpdir)
            self.assertIsInstance(report, ReviewReport)


if __name__ == '__main__':
    unittest.main()
