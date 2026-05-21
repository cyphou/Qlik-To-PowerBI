"""Tests for powerbi_import.pdf_renderer — PDF/HTML migration reports."""

import os
import tempfile
import unittest

from powerbi_import.pdf_renderer import (
    PdfRenderer,
    render_migration_pdf,
)


class TestPdfRenderer(unittest.TestCase):
    """Test PdfRenderer class."""

    def test_init(self):
        renderer = PdfRenderer(app_name='TestApp', output_dir='.')
        self.assertEqual(renderer.app_name, 'TestApp')

    def test_build_html(self):
        renderer = PdfRenderer(app_name='TestApp', output_dir='.')
        html = renderer._build_html({})
        self.assertIn('<html', html)
        self.assertIn('TestApp', html)

    def test_build_html_with_stats(self):
        renderer = PdfRenderer(app_name='TestApp', output_dir='.')
        html = renderer._build_html(
            report_data={'summary': {'total': 100, 'exact': 85, 'approximate': 10, 'unsupported': 5}},
        )
        self.assertIn('100', html)

    def test_build_html_with_qa(self):
        renderer = PdfRenderer(app_name='TestApp', output_dir='.')
        html = renderer._build_html(
            report_data={},
            qa_data={'summary': {'total_checks': 3, 'passed': 2, 'autofixed': 0, 'remaining': 1}},
        )
        self.assertIsInstance(html, str)

    def test_render_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            renderer = PdfRenderer(app_name='TestApp', output_dir=tmpdir)
            path = renderer.render_html({})
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn('TestApp', content)

    def test_render_html_with_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            renderer = PdfRenderer(app_name='TestApp', output_dir=tmpdir)
            path = renderer.render_html(
                report_data={'summary': {'total': 50, 'exact': 40}},
            )
            self.assertTrue(os.path.exists(path))

    def test_render_pdf_fallback_to_html(self):
        """When weasyprint is not installed, should fallback to HTML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            renderer = PdfRenderer(app_name='TestApp', output_dir=tmpdir)
            path = renderer.render_pdf({})
            self.assertTrue(os.path.exists(path))
            # Should either be .pdf or .html depending on weasyprint availability
            self.assertTrue(path.endswith('.pdf') or path.endswith('.html'))


class TestRenderMigrationPdf(unittest.TestCase):
    """Test convenience function."""

    def test_convenience(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = render_migration_pdf('TestApp', tmpdir, {})
            self.assertTrue(os.path.exists(path))

    def test_with_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = render_migration_pdf(
                'TestApp', tmpdir,
                report_data={'summary': {'total': 10, 'exact': 8}},
            )
            self.assertTrue(os.path.exists(path))


class TestPdfRendererEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_empty_app_name(self):
        renderer = PdfRenderer(app_name='', output_dir='.')
        html = renderer._build_html({})
        self.assertIn('<html', html)

    def test_special_chars_in_name(self):
        renderer = PdfRenderer(app_name='App & <Test>', output_dir='.')
        html = renderer._build_html({})
        self.assertIn('<html', html)
        # Should be escaped
        self.assertNotIn('<Test>', html)

    def test_multiple_renders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            renderer = PdfRenderer(app_name='TestApp', output_dir=tmpdir)
            path1 = renderer.render_html({})
            path2 = renderer.render_html({})
            self.assertTrue(os.path.exists(path1))
            self.assertTrue(os.path.exists(path2))


if __name__ == '__main__':
    unittest.main()
