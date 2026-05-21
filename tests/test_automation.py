"""Tests for powerbi_import.automation — batch migration orchestration."""

import os
import tempfile
import unittest

from powerbi_import.automation import (
    BatchJob,
    BatchResult,
    BatchRunner,
    run_batch_migration,
)


class TestBatchJob(unittest.TestCase):
    """Test BatchJob dataclass."""

    def test_creation(self):
        job = BatchJob(app_name='App1', input_path='app1.qvf',
                        output_dir='out/')
        self.assertEqual(job.app_name, 'App1')
        self.assertEqual(job.input_path, 'app1.qvf')

    def test_with_options(self):
        job = BatchJob(app_name='App1', input_path='app1.qvf',
                        output_dir='out/', options={'verbose': True})
        self.assertEqual(job.options['verbose'], True)

    def test_with_priority(self):
        job = BatchJob(app_name='App1', input_path='app1.qvf',
                        output_dir='out/', priority=1)
        self.assertEqual(job.priority, 1)

    def test_to_dict(self):
        job = BatchJob(app_name='App1', input_path='app1.qvf',
                        output_dir='out/')
        d = job.to_dict()
        self.assertEqual(d['app_name'], 'App1')


class TestBatchResult(unittest.TestCase):
    """Test BatchResult dataclass."""

    def test_success(self):
        r = BatchResult(app_name='App1', status='success', output_dir='out/')
        self.assertEqual(r.status, 'success')

    def test_failed(self):
        r = BatchResult(app_name='App1', status='failed',
                         error='Import error')
        self.assertEqual(r.status, 'failed')
        self.assertEqual(r.error, 'Import error')

    def test_statuses(self):
        for status in ('success', 'partial', 'failed', 'skipped'):
            r = BatchResult(app_name='App1', status=status)
            self.assertEqual(r.status, status)

    def test_to_dict(self):
        r = BatchResult(app_name='App1', status='success',
                         output_dir='out/', duration_seconds=42.5)
        d = r.to_dict()
        self.assertEqual(d['status'], 'success')
        self.assertIn('duration_seconds', d)


class TestBatchRunner(unittest.TestCase):
    """Test BatchRunner class."""

    def test_init(self):
        runner = BatchRunner()
        self.assertIsNotNone(runner)

    def test_run_empty(self):
        runner = BatchRunner()
        results = runner.run([])
        self.assertEqual(len(results), 0)

    def test_run_with_missing_input(self):
        runner = BatchRunner()
        job = BatchJob(app_name='Missing', input_path='nonexistent.qvf',
                        output_dir='out/')
        results = runner.run([job])
        self.assertEqual(len(results), 1)
        self.assertIn(results[0].status, ('failed', 'skipped', 'partial'))

    def test_run_with_custom_migrate(self):
        def custom_migrate(input_path, output_dir, **kwargs):
            return {'status': 'success', 'tables': 5}

        runner = BatchRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake input file
            input_file = os.path.join(tmpdir, 'app.qvf')
            with open(input_file, 'w') as f:
                f.write('fake')
            job = BatchJob(app_name='TestApp', input_path=input_file,
                            output_dir=tmpdir)
            results = runner.run([job], migrate_fn=custom_migrate)
            self.assertEqual(len(results), 1)

    def test_get_summary(self):
        runner = BatchRunner()
        runner.results = [
            BatchResult(app_name='A', status='success'),
            BatchResult(app_name='B', status='failed', error='err'),
            BatchResult(app_name='C', status='success'),
        ]
        summary = runner.get_summary()
        self.assertEqual(summary['total_jobs'], 3)
        self.assertEqual(summary['by_status']['success'], 2)
        self.assertEqual(summary['by_status']['failed'], 1)

    def test_save_report(self):
        runner = BatchRunner()
        runner.results = [
            BatchResult(app_name='A', status='success'),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = runner.save_report(os.path.join(tmpdir, 'report.json'))
            self.assertTrue(os.path.exists(path))

    def test_generate_html_report(self):
        runner = BatchRunner()
        runner.results = [
            BatchResult(app_name='A', status='success'),
            BatchResult(app_name='B', status='failed', error='Import error'),
        ]
        html = runner.generate_html_report()
        self.assertIsInstance(html, str)
        self.assertIn('<html', html)
        self.assertIn('A', html)


class TestBatchRunnerPriority(unittest.TestCase):
    """Test BatchRunner with priorities."""

    def test_priority_ordering(self):
        execution_order = []

        def track_migrate(input_path, output_dir, **kwargs):
            execution_order.append(os.path.basename(input_path))
            return {'status': 'success'}

        runner = BatchRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ['low', 'high', 'mid']:
                path = os.path.join(tmpdir, f'{name}.qvf')
                with open(path, 'w') as f:
                    f.write('fake')

            jobs = [
                BatchJob(app_name='Low', input_path=os.path.join(tmpdir, 'low.qvf'),
                          output_dir=tmpdir, priority=3),
                BatchJob(app_name='High', input_path=os.path.join(tmpdir, 'high.qvf'),
                          output_dir=tmpdir, priority=1),
                BatchJob(app_name='Mid', input_path=os.path.join(tmpdir, 'mid.qvf'),
                          output_dir=tmpdir, priority=2),
            ]
            runner.run(jobs, migrate_fn=track_migrate)
            # High priority should run first
            if execution_order:
                self.assertEqual(execution_order[0], 'high.qvf')


class TestRunBatchMigration(unittest.TestCase):
    """Test convenience function."""

    def test_convenience_empty(self):
        result = run_batch_migration([])
        self.assertIsInstance(result, dict)
        self.assertIn('summary', result)
        self.assertEqual(len(result['results']), 0)

    def test_convenience_with_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, 'app.qvf')
            with open(input_file, 'w') as f:
                f.write('fake')
            jobs = [
                {'app_name': 'Test', 'input_path': input_file,
                 'output_dir': tmpdir},
            ]
            result = run_batch_migration(jobs, output_base=tmpdir)
            self.assertIsInstance(result, dict)
            self.assertEqual(len(result['results']), 1)


if __name__ == '__main__':
    unittest.main()
