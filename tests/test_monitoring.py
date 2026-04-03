"""Tests for powerbi_import.monitoring — metrics collector and export."""

import json
import os
import tempfile
import unittest

from powerbi_import.monitoring import MigrationMonitor


class TestMigrationMonitorInit(unittest.TestCase):
    """Test monitor initialization."""

    def test_json_backend(self):
        m = MigrationMonitor(backend="json")
        self.assertEqual(m.backend_name, "json")

    def test_none_backend(self):
        m = MigrationMonitor(backend="none")
        self.assertEqual(m.backend_name, "none")

    def test_unknown_backend_falls_back_to_json(self):
        m = MigrationMonitor(backend="unknown")
        # Unknown key was looked up and returned None → JsonBackend used as default
        self.assertIsNotNone(m._backend)


class TestMigrationMonitorRecord(unittest.TestCase):
    """Test metric and event recording."""

    def test_record_metric(self):
        m = MigrationMonitor(backend="json")
        m.record_metric("test_metric", 42.0, app="demo")
        # Should not raise
        self.assertTrue(True)

    def test_record_event(self):
        m = MigrationMonitor(backend="json")
        m.record_event("test_event", status="ok")
        self.assertTrue(True)

    def test_record_migration(self):
        m = MigrationMonitor(backend="json")
        m.record_migration("app.qvf", duration_seconds=5.0, fidelity=95.0,
                           tables=3, measures=10, visuals=5, pages=2)
        self.assertTrue(True)


class TestMigrationMonitorFlush(unittest.TestCase):
    """Test flushing to JSON file."""

    def test_flush_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = os.path.join(td, "monitoring.jsonl")
            m = MigrationMonitor(backend="json", log_path=log_path)
            m.record_metric("dur", 10.0)
            m.record_event("done")
            count = m.flush()
            self.assertEqual(count, 2)
            self.assertTrue(os.path.isfile(log_path))
            with open(log_path) as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["type"], "metric")
            self.assertEqual(lines[1]["type"], "event")

    def test_flush_empty_no_file(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = os.path.join(td, "monitoring.jsonl")
            m = MigrationMonitor(backend="json", log_path=log_path)
            result = m.flush()
            self.assertIsNone(result)
            self.assertFalse(os.path.isfile(log_path))

    def test_multiple_flushes_append(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = os.path.join(td, "monitoring.jsonl")
            m = MigrationMonitor(backend="json", log_path=log_path)
            m.record_metric("a", 1)
            m.flush()
            m.record_metric("b", 2)
            m.flush()
            with open(log_path) as f:
                lines = [l for l in f if l.strip()]
            self.assertEqual(len(lines), 2)


class TestNoneBackend(unittest.TestCase):
    """Test no-op backend."""

    def test_record_and_flush_noop(self):
        m = MigrationMonitor(backend="none")
        m.record_metric("x", 1)
        m.record_event("y")
        # flush on none backend does nothing — should not raise
        m.flush()


if __name__ == "__main__":
    unittest.main()
