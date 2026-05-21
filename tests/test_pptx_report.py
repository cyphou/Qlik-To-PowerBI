"""Tests for powerbi_import.pptx_report — PowerPoint executive summary."""

import os
import tempfile
import unittest

from powerbi_import.pptx_report import (
    PptxReport,
    generate_pptx_report,
)


class TestPptxReport(unittest.TestCase):
    """Test PptxReport class."""

    def test_init(self):
        rpt = PptxReport(app_name='TestApp', output_dir='.')
        self.assertEqual(rpt.app_name, 'TestApp')

    def test_build_slides_empty(self):
        rpt = PptxReport(app_name='TestApp', output_dir='.')
        slides = rpt._build_slides({})
        self.assertIsInstance(slides, list)
        self.assertGreater(len(slides), 0)

    def test_build_slides_with_stats(self):
        rpt = PptxReport(app_name='TestApp', output_dir='.')
        slides = rpt._build_slides(
            {'summary': {'total': 100, 'exact': 85, 'approximate': 10, 'unsupported': 5}},
        )
        self.assertIsInstance(slides, list)

    def test_build_slides_with_qa(self):
        rpt = PptxReport(app_name='TestApp', output_dir='.')
        slides = rpt._build_slides(
            {}, qa_data={'summary': {'total_checks': 5, 'passed': 3, 'remaining': 2}},
        )
        self.assertIsInstance(slides, list)

    def test_generate_pptx_or_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rpt = PptxReport(app_name='TestApp', output_dir=tmpdir)
            path = rpt.generate_pptx({})
            self.assertTrue(os.path.exists(path))
            # Should be .pptx or .md depending on python-pptx availability
            self.assertTrue(path.endswith('.pptx') or path.endswith('.md'))

    def test_generate_markdown_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rpt = PptxReport(app_name='TestApp', output_dir=tmpdir)
            slides = rpt._build_slides({})
            path = rpt._generate_markdown(slides)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith('.md'))
            with open(path) as f:
                content = f.read()
            self.assertIn('TestApp', content)

    def test_generate_markdown_with_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rpt = PptxReport(app_name='TestApp', output_dir=tmpdir)
            slides = rpt._build_slides(
                {'summary': {'total': 50, 'exact': 40, 'approximate': 8, 'unsupported': 2}},
            )
            path = rpt._generate_markdown(slides)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn('50', content)


class TestGeneratePptxReport(unittest.TestCase):
    """Test convenience function."""

    def test_convenience(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_pptx_report('TestApp', tmpdir, {})
            self.assertTrue(os.path.exists(path))

    def test_with_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_pptx_report(
                'TestApp', tmpdir,
                report_data={'summary': {'total': 10, 'exact': 8}},
            )
            self.assertTrue(os.path.exists(path))


class TestPptxReportEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_empty_app_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rpt = PptxReport(app_name='', output_dir=tmpdir)
            slides = rpt._build_slides({})
            path = rpt._generate_markdown(slides)
            self.assertTrue(os.path.exists(path))

    def test_special_chars_in_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rpt = PptxReport(app_name='App & Test', output_dir=tmpdir)
            slides = rpt._build_slides({})
            path = rpt._generate_markdown(slides)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn('App & Test', content)

    def test_slides_have_title_and_content(self):
        rpt = PptxReport(app_name='TestApp', output_dir='.')
        slides = rpt._build_slides({})
        for slide in slides:
            self.assertIn('title', slide)
            self.assertTrue('content' in slide or 'subtitle' in slide)


if __name__ == '__main__':
    unittest.main()
