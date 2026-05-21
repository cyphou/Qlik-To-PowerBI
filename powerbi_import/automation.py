"""Automation — batch migration orchestration for multiple Qlik apps.

Provides a batch runner that processes a list of Qlik apps sequentially,
collecting results, handling failures, and generating a consolidated report.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger('qlik_to_powerbi.automation')

__all__ = [
    'BatchJob', 'BatchResult', 'BatchRunner',
    'run_batch_migration',
]


@dataclass
class BatchJob:
    """A single app migration job."""
    app_name: str
    input_path: str
    output_dir: str = ''
    options: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # lower = higher priority

    def to_dict(self) -> Dict[str, Any]:
        return {
            'app_name': self.app_name,
            'input_path': self.input_path,
            'output_dir': self.output_dir,
            'options': self.options,
            'priority': self.priority,
        }


@dataclass
class BatchResult:
    """Result of a single batch job execution."""
    app_name: str
    status: str  # 'success', 'partial', 'failed', 'skipped'
    output_dir: str = ''
    duration_seconds: float = 0.0
    fidelity_pct: float = 0.0
    error: str = ''
    items_total: int = 0
    items_exact: int = 0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'app_name': self.app_name,
            'status': self.status,
            'output_dir': self.output_dir,
            'duration_seconds': self.duration_seconds,
            'fidelity_pct': self.fidelity_pct,
            'items_total': self.items_total,
            'items_exact': self.items_exact,
        }
        if self.error:
            d['error'] = self.error
        if self.warnings:
            d['warnings'] = self.warnings
        return d


class BatchRunner:
    """Orchestrates batch migration of multiple Qlik apps."""

    def __init__(self, output_base: str = './batch_output',
                 on_progress: Optional[Callable[[str, int, int], None]] = None,
                 stop_on_failure: bool = False):
        self.output_base = output_base
        self.on_progress = on_progress
        self.stop_on_failure = stop_on_failure
        self.results: List[BatchResult] = []

    def run(self, jobs: List[BatchJob],
            migrate_fn: Optional[Callable] = None) -> List[BatchResult]:
        """Run batch migration for all jobs.

        Args:
            jobs: List of BatchJob instances to process.
            migrate_fn: Optional callable(input_path, output_dir, **options) -> dict
                       that performs the actual migration. If None, uses the
                       default pipeline.
        """
        sorted_jobs = sorted(jobs, key=lambda j: j.priority)
        total = len(sorted_jobs)
        self.results = []

        for i, job in enumerate(sorted_jobs):
            app_name = job.app_name
            if self.on_progress:
                self.on_progress(app_name, i + 1, total)

            logger.info("Batch job %d/%d: %s", i + 1, total, app_name)

            output_dir = job.output_dir or os.path.join(
                self.output_base, app_name.replace(' ', '_')
            )
            os.makedirs(output_dir, exist_ok=True)

            start = datetime.now()
            try:
                if migrate_fn:
                    result_data = migrate_fn(
                        job.input_path, output_dir, **job.options
                    )
                else:
                    result_data = self._default_migrate(
                        job.input_path, output_dir, job.options
                    )

                duration = (datetime.now() - start).total_seconds()
                summary = result_data.get('summary', {}) if isinstance(result_data, dict) else {}
                items_total = summary.get('total', 0)
                items_exact = summary.get('exact', 0)
                fidelity = round(items_exact * 100 / items_total) if items_total else 0

                status = 'success' if fidelity >= 80 else 'partial'
                result = BatchResult(
                    app_name=app_name, status=status,
                    output_dir=output_dir,
                    duration_seconds=duration,
                    fidelity_pct=fidelity,
                    items_total=items_total,
                    items_exact=items_exact,
                )
                self.results.append(result)

            except Exception as e:
                duration = (datetime.now() - start).total_seconds()
                error_msg = f'{type(e).__name__}: {e}'
                logger.error("Batch job failed for %s: %s", app_name, error_msg)

                result = BatchResult(
                    app_name=app_name, status='failed',
                    output_dir=output_dir,
                    duration_seconds=duration,
                    error=error_msg,
                )
                self.results.append(result)

                if self.stop_on_failure:
                    logger.warning("Stopping batch due to failure (stop_on_failure=True)")
                    break

        return self.results

    def _default_migrate(self, input_path: str, output_dir: str,
                         options: Dict[str, Any]) -> Dict[str, Any]:
        """Default migration using the standard pipeline."""
        try:
            from powerbi_import.import_to_powerbi import run_migration
            return run_migration(input_path, output_dir, **(options or {}))
        except ImportError:
            logger.warning("import_to_powerbi not available; returning empty result")
            return {'summary': {'total': 0, 'exact': 0}}

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all batch results."""
        by_status: Dict[str, int] = {}
        total_duration = 0.0
        total_items = 0
        total_exact = 0

        for r in self.results:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            total_duration += r.duration_seconds
            total_items += r.items_total
            total_exact += r.items_exact

        return {
            'total_jobs': len(self.results),
            'by_status': by_status,
            'total_duration_seconds': round(total_duration, 1),
            'total_items': total_items,
            'total_exact': total_exact,
            'overall_fidelity_pct': round(total_exact * 100 / total_items) if total_items else 0,
        }

    def save_report(self, output_path: str) -> str:
        """Save batch results to JSON."""
        report = {
            'created_at': datetime.now().isoformat(),
            'summary': self.get_summary(),
            'results': [r.to_dict() for r in self.results],
        }
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        logger.info("Batch report saved to %s", output_path)
        return output_path

    def generate_html_report(self) -> str:
        """Generate HTML summary of batch migration."""
        try:
            from powerbi_import.html_template import (
                html_open, html_close, section_open, section_close,
                data_table, stat_card, stat_grid, badge, esc,
            )
        except ImportError:
            from html_template import (
                html_open, html_close, section_open, section_close,
                data_table, stat_card, stat_grid, badge, esc,
            )

        summary = self.get_summary()
        html = html_open('Batch Migration Report',
                        subtitle=f'{summary["total_jobs"]} apps processed')

        cards = [
            {'value': summary['total_jobs'], 'label': 'Total Jobs'},
            {'value': summary.get('by_status', {}).get('success', 0), 'label': 'Success'},
            {'value': summary.get('by_status', {}).get('failed', 0), 'label': 'Failed'},
            {'value': f'{summary["overall_fidelity_pct"]}%', 'label': 'Overall Fidelity'},
        ]
        html += stat_grid(cards)

        html += section_open('Results', 'Job Results')
        headers = ['App', 'Status', 'Fidelity', 'Items', 'Duration', 'Error']
        rows = []
        for r in self.results:
            status_class = {
                'success': 'pass', 'partial': 'warn', 'failed': 'fail',
            }.get(r.status, '')
            rows.append([
                esc(r.app_name),
                badge(r.status, status_class),
                f'{r.fidelity_pct}%',
                f'{r.items_exact}/{r.items_total}',
                f'{r.duration_seconds:.1f}s',
                esc(r.error[:60]) if r.error else '',
            ])
        html += data_table(headers, rows)
        html += section_close()

        html += html_close()
        return html


def run_batch_migration(jobs: List[Dict[str, Any]],
                        output_base: str = './batch_output',
                        migrate_fn: Optional[Callable] = None,
                        stop_on_failure: bool = False) -> Dict[str, Any]:
    """Convenience function for batch migration."""
    batch_jobs = [BatchJob(**j) for j in jobs]
    runner = BatchRunner(output_base=output_base,
                        stop_on_failure=stop_on_failure)
    runner.run(batch_jobs, migrate_fn)

    report_path = os.path.join(output_base, 'batch_report.json')
    runner.save_report(report_path)

    return {
        'summary': runner.get_summary(),
        'results': [r.to_dict() for r in runner.results],
        'report_path': report_path,
    }
