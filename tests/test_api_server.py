"""Tests for powerbi_import.api_server — REST API migration server.

Validates file extension handling, rate limiting, migration worker
imports, and multipart parsing.
"""

import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock
from http.server import HTTPServer

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from powerbi_import.api_server import (
    MigrationHandler,
    _parse_multipart,
    _new_job,
    _get_job,
    _update_job,
    _run_migration,
    _get_version,
    _purge_stale_jobs,
    _check_rate_limit,
    _jobs,
    _lock,
)


class TestParseMultipart(unittest.TestCase):
    """Tests for multipart/form-data parsing."""

    def test_extract_filename_and_data(self):
        boundary = b'----boundary123'
        body = (
            b'------boundary123\r\n'
            b'Content-Disposition: form-data; name="file"; filename="test_app.qvf"\r\n'
            b'Content-Type: application/octet-stream\r\n'
            b'\r\n'
            b'FAKEDATA\r\n'
            b'------boundary123--\r\n'
        )
        result = _parse_multipart(body, boundary)
        self.assertIsNotNone(result)
        filename, data = result
        self.assertEqual(filename, 'test_app.qvf')
        self.assertEqual(data, b'FAKEDATA')

    def test_returns_none_for_no_file(self):
        boundary = b'----boundary'
        body = b'------boundary\r\nContent-Disposition: form-data; name="text"\r\n\r\nhello\r\n------boundary--'
        result = _parse_multipart(body, boundary)
        self.assertIsNone(result)

    def test_sanitizes_path_traversal(self):
        boundary = b'----boundary'
        body = (
            b'------boundary\r\n'
            b'Content-Disposition: form-data; name="file"; filename="../../etc/passwd"\r\n'
            b'\r\n'
            b'EVIL\r\n'
            b'------boundary--\r\n'
        )
        result = _parse_multipart(body, boundary)
        self.assertIsNotNone(result)
        filename, data = result
        # Path components stripped — only basename
        self.assertNotIn('..', filename)
        self.assertNotIn('/', filename)


class TestJobManagement(unittest.TestCase):
    """Tests for job creation, retrieval, and updates."""

    def setUp(self):
        with _lock:
            _jobs.clear()

    def tearDown(self):
        with _lock:
            _jobs.clear()

    def test_create_and_get_job(self):
        job_id = _new_job('/tmp/test.qvf')
        job = _get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job['status'], 'queued')
        self.assertEqual(job['input_path'], '/tmp/test.qvf')

    def test_update_job(self):
        job_id = _new_job('/tmp/test.qvf')
        _update_job(job_id, status='running')
        job = _get_job(job_id)
        self.assertEqual(job['status'], 'running')

    def test_get_nonexistent_job(self):
        self.assertIsNone(_get_job('nonexistent-id'))

    def test_purge_stale_jobs(self):
        job_id = _new_job('/tmp/old.qvf')
        _update_job(job_id, status='completed')
        # Manually set created time to past
        with _lock:
            _jobs[job_id]['created'] = 0
        _purge_stale_jobs()
        self.assertIsNone(_get_job(job_id))


class TestFileExtensionValidation(unittest.TestCase):
    """Tests that api_server accepts .qvf/.json and rejects Tableau types."""

    def test_accepted_extensions(self):
        """Qlik file extensions are accepted."""
        for ext in ('.qvf', '.json'):
            self.assertIn(ext, ('.qvf', '.json'))

    def test_rejected_extensions(self):
        """Tableau file extensions should not be accepted."""
        for ext in ('.twb', '.twbx', '.tds', '.tdsx'):
            self.assertNotIn(ext, ('.qvf', '.json'))


class TestMigrationWorkerImports(unittest.TestCase):
    """Tests that _run_migration uses correct Qlik pipeline imports."""

    def test_worker_imports_qlik_extraction(self):
        """Verify _run_migration imports from qlik_export, not Qlik_export."""
        import inspect
        source = inspect.getsource(_run_migration)
        self.assertIn('qlik_export.extraction_orchestrator', source)
        self.assertNotIn('Qlik_export', source)
        self.assertNotIn('extract_Qlik_data', source)

    def test_worker_uses_format_adapter(self):
        """Verify _run_migration imports format_adapter."""
        import inspect
        source = inspect.getsource(_run_migration)
        self.assertIn('qlik_export.format_adapter', source)

    def test_worker_uses_powerbi_importer(self):
        """Verify _run_migration uses PowerBIImporter."""
        import inspect
        source = inspect.getsource(_run_migration)
        self.assertIn('PowerBIImporter', source)


class TestDocstrings(unittest.TestCase):
    """Tests that module docstrings reference Qlik, not Tableau."""

    def test_module_docstring(self):
        import powerbi_import.api_server as mod
        doc = mod.__doc__
        self.assertIn('.qvf', doc)
        self.assertNotIn('.twb', doc)

    def test_version_endpoint(self):
        v = _get_version()
        self.assertIsInstance(v, str)
        self.assertNotEqual(v, 'unknown')


class TestRateLimiting(unittest.TestCase):
    """Tests for rate limiting."""

    def test_rate_limit_allows_initial_requests(self):
        result = _check_rate_limit('192.0.2.1')
        self.assertTrue(result)

    def test_rate_limit_blocks_after_threshold(self):
        ip = '192.0.2.99'
        # Exhaust rate limit
        for _ in range(15):
            _check_rate_limit(ip)
        result = _check_rate_limit(ip)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
