"""Tests for powerbi_import.report_packager — ZIP bundle generation."""

import json
import os
import tempfile
import unittest
import zipfile

from powerbi_import.report_packager import (
    ReportPackager,
    package_migration,
)


class TestReportPackager(unittest.TestCase):
    """Test ReportPackager class."""

    def test_init(self):
        pkg = ReportPackager(app_name='TestApp', output_dir='.')
        self.assertEqual(pkg.app_name, 'TestApp')

    def test_package_minimal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = ReportPackager(app_name='TestApp', output_dir=tmpdir)
            path = pkg.package()
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith('.zip'))

    def test_package_contains_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = ReportPackager(app_name='TestApp', output_dir=tmpdir)
            path = pkg.package()
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                manifest_entries = [n for n in names if 'manifest.json' in n]
                self.assertGreater(len(manifest_entries), 0)

    def test_package_with_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create intermediate JSON files
            json_dir = os.path.join(tmpdir, 'intermediate_json')
            os.makedirs(json_dir, exist_ok=True)
            with open(os.path.join(json_dir, 'measures.json'), 'w') as f:
                json.dump([{'name': 'Sales'}], f)

            pkg = ReportPackager(app_name='TestApp', output_dir=tmpdir)
            path = pkg.package()
            self.assertTrue(os.path.exists(path))

    def test_package_with_pbip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake pbip project
            pbip_dir = os.path.join(tmpdir, 'TestApp.pbip')
            os.makedirs(pbip_dir, exist_ok=True)
            with open(os.path.join(pbip_dir, 'TestApp.pbip'), 'w') as f:
                f.write('{}')

            pkg = ReportPackager(app_name='TestApp', output_dir=tmpdir)
            path = pkg.package()
            self.assertTrue(os.path.exists(path))

    def test_package_with_reports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a reports dir
            reports_dir = os.path.join(tmpdir, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            with open(os.path.join(reports_dir, 'summary.html'), 'w') as f:
                f.write('<html>Summary</html>')

            pkg = ReportPackager(app_name='TestApp', output_dir=tmpdir)
            path = pkg.package()
            self.assertTrue(os.path.exists(path))


class TestPackageMigration(unittest.TestCase):
    """Test convenience function."""

    def test_convenience(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = package_migration('TestApp', tmpdir)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith('.zip'))

    def test_creates_valid_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = package_migration('TestApp', tmpdir)
            self.assertTrue(zipfile.is_zipfile(path))


class TestReportPackagerEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def test_empty_app_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = ReportPackager(app_name='', output_dir=tmpdir)
            path = pkg.package()
            self.assertTrue(os.path.exists(path))

    def test_special_chars_in_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = ReportPackager(app_name='App Test', output_dir=tmpdir)
            path = pkg.package()
            self.assertTrue(os.path.exists(path))

    def test_nested_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            nested = os.path.join(tmpdir, 'a', 'b', 'c')
            os.makedirs(nested, exist_ok=True)
            with open(os.path.join(nested, 'file.txt'), 'w') as f:
                f.write('data')

            pkg = ReportPackager(app_name='TestApp', output_dir=tmpdir)
            path = pkg.package()
            self.assertTrue(os.path.exists(path))


if __name__ == '__main__':
    unittest.main()
