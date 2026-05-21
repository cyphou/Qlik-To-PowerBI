"""Self-healing audit trail — JSONL report of auto-repair actions.

Records every repair action with before/after snapshots so that
migration operators can review what the self-healing engine changed.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger('qlik_to_powerbi.self_healing_report')

__all__ = ['SelfHealingReport', 'SelfHealingEntry']


class SelfHealingEntry:
    """A single self-healing action record."""

    def __init__(self, healer: str, category: str, item_name: str,
                 description: str, action: str, severity: str = 'warning',
                 original_value: str = '', repaired_value: str = ''):
        self.timestamp = datetime.now().isoformat()
        self.healer = healer
        self.category = category
        self.item_name = item_name
        self.description = description
        self.action = action
        self.severity = severity
        self.original_value = original_value
        self.repaired_value = repaired_value

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'timestamp': self.timestamp,
            'healer': self.healer,
            'category': self.category,
            'item_name': self.item_name,
            'description': self.description,
            'action': self.action,
            'severity': self.severity,
        }
        if self.original_value:
            d['original_value'] = self.original_value
        if self.repaired_value:
            d['repaired_value'] = self.repaired_value
        return d


class SelfHealingReport:
    """Accumulates self-healing entries and writes a JSONL audit trail."""

    def __init__(self, report_name: str = ''):
        self.report_name = report_name
        self.entries: List[SelfHealingEntry] = []
        self.created_at = datetime.now().isoformat()

    def record(self, healer: str, category: str, item_name: str,
               description: str, action: str, severity: str = 'warning',
               original_value: str = '', repaired_value: str = '') -> SelfHealingEntry:
        entry = SelfHealingEntry(
            healer=healer, category=category, item_name=item_name,
            description=description, action=action, severity=severity,
            original_value=original_value, repaired_value=repaired_value,
        )
        self.entries.append(entry)
        return entry

    @property
    def repair_count(self) -> int:
        return len(self.entries)

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.entries if e.severity == 'warning')

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.entries if e.severity == 'error')

    def get_summary(self) -> Dict[str, Any]:
        by_healer: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for e in self.entries:
            by_healer[e.healer] = by_healer.get(e.healer, 0) + 1
            by_category[e.category] = by_category.get(e.category, 0) + 1
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        return {
            'report_name': self.report_name,
            'created_at': self.created_at,
            'total_repairs': self.repair_count,
            'by_healer': by_healer,
            'by_category': by_category,
            'by_severity': by_severity,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'summary': self.get_summary(),
            'entries': [e.to_dict() for e in self.entries],
        }

    def save_jsonl(self, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in self.entries:
                f.write(json.dumps(entry.to_dict()) + '\n')
        logger.info("Self-healing JSONL saved to %s (%d entries)",
                     output_path, len(self.entries))
        return output_path

    def save_json(self, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Self-healing report saved to %s", output_path)
        return output_path

    def print_summary(self) -> None:
        summary = self.get_summary()
        print(f"\nSelf-Healing Report: {self.report_name}")
        print(f"  Total repairs: {summary['total_repairs']}")
        if summary['by_healer']:
            print("  By healer:")
            for h, c in sorted(summary['by_healer'].items()):
                print(f"    {h}: {c}")
        if summary['by_severity']:
            print("  By severity:")
            for s, c in sorted(summary['by_severity'].items()):
                print(f"    {s}: {c}")
