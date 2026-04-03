"""
Self-healing recovery report.

Records every automatic repair action taken during migration so users
know exactly what was fixed, what intervention was applied, and what
manual follow-up (if any) is recommended.

The report integrates with MigrationReport via ``merge_into()``.

Usage:
    from powerbi_import.recovery_report import RecoveryReport

    recovery = RecoveryReport("Superstore_Sales")
    recovery.record("tmdl", "broken_column_ref",
                    description="Measure 'Profit YoY' references non-existent column [Region2]",
                    action="Removed column reference, measure hidden with MigrationNote",
                    severity="warning",
                    follow_up="Review measure 'Profit YoY' and fix column reference")
    recovery.save("artifacts/")
"""

import json
import os
from datetime import datetime


class RecoveryReport:
    """Tracks every self-repair action taken during migration."""

    # Severity levels
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'

    _VALID_SEVERITIES = {INFO, WARNING, ERROR}

    # Recovery categories
    TMDL = 'tmdl'
    VISUAL = 'visual'
    M_QUERY = 'm_query'
    RELATIONSHIP = 'relationship'

    def __init__(self, report_name):
        self.report_name = report_name
        self.created_at = datetime.now().isoformat()
        self.repairs = []

    def record(self, category, repair_type, *, description='',
               action='', severity='warning', follow_up='',
               item_name='', original_value='', repaired_value=''):
        """Record a single self-repair action.

        Args:
            category: Area of repair ('tmdl', 'visual', 'm_query', 'relationship')
            repair_type: Machine-readable repair code (e.g. 'broken_column_ref',
                         'visual_fallback', 'try_otherwise_wrap')
            description: What went wrong
            action: What the engine did to fix it
            severity: 'info', 'warning', or 'error'
            follow_up: Recommended manual follow-up (empty = none needed)
            item_name: Name of the affected item (measure, visual, table, etc.)
            original_value: Value/config before repair (optional)
            repaired_value: Value/config after repair (optional)
        """
        if severity not in self._VALID_SEVERITIES:
            severity = self.WARNING

        entry = {
            'category': category,
            'repair_type': repair_type,
            'severity': severity,
            'description': description,
            'action': action,
        }
        if item_name:
            entry['item_name'] = item_name
        if follow_up:
            entry['follow_up'] = follow_up
        if original_value:
            entry['original_value'] = original_value
        if repaired_value:
            entry['repaired_value'] = repaired_value

        self.repairs.append(entry)

    @property
    def has_repairs(self):
        return len(self.repairs) > 0

    def get_summary(self):
        """Return summary statistics."""
        by_category = {}
        by_severity = {self.INFO: 0, self.WARNING: 0, self.ERROR: 0}
        by_type = {}

        for r in self.repairs:
            cat = r['category']
            by_category[cat] = by_category.get(cat, 0) + 1
            sev = r.get('severity', self.WARNING)
            by_severity[sev] = by_severity.get(sev, 0) + 1
            rt = r['repair_type']
            by_type[rt] = by_type.get(rt, 0) + 1

        return {
            'total_repairs': len(self.repairs),
            'by_category': by_category,
            'by_severity': by_severity,
            'by_type': by_type,
            'needs_follow_up': sum(1 for r in self.repairs if r.get('follow_up')),
        }

    def to_dict(self):
        """Return full report as a dictionary."""
        return {
            'report_name': self.report_name,
            'created_at': self.created_at,
            'summary': self.get_summary(),
            'repairs': self.repairs,
        }

    def save(self, output_dir='artifacts/migration_reports'):
        """Save the recovery report as JSON."""
        os.makedirs(output_dir, exist_ok=True)
        safe_name = self.report_name.replace(' ', '_').replace('/', '_')
        filename = f'{safe_name}_recovery.json'
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath

    def merge_into(self, migration_report):
        """Append recovery summary into a MigrationReport instance.

        Adds each repair as a 'recovery' category item so it appears
        in the migration report alongside regular items.
        """
        for repair in self.repairs:
            status = 'approximate' if repair['severity'] == self.WARNING else 'placeholder'
            if repair['severity'] == self.INFO:
                status = 'exact'
            migration_report.add_item(
                category='recovery',
                name=repair.get('item_name') or repair['repair_type'],
                status=status,
                note=f"[{repair['repair_type']}] {repair['action']}",
            )

    def print_summary(self):
        """Print a console summary."""
        summary = self.get_summary()
        total = summary['total_repairs']
        if total == 0:
            print("  ✓ No self-healing repairs needed")
            return
        print(f"  ⚕ Self-healing: {total} repair(s) applied")
        for cat, count in summary['by_category'].items():
            print(f"    {cat}: {count}")
        follow = summary['needs_follow_up']
        if follow:
            print(f"    ⚠ {follow} item(s) need manual follow-up")
