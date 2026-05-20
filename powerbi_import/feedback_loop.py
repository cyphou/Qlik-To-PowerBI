"""Feedback loop — issue reporting and regression fixture generation.

Provides a ``--report-issue`` CLI entry point for users to file issues,
and a dashboard for tracking zero-error progress.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from dataclasses import dataclass, field


@dataclass
class FeedbackEntry:
    """A single feedback/issue entry."""
    timestamp: str
    category: str           # 'dax_leak', 'visual_mismatch', 'crash', 'other'
    description: str
    source_file: str = ''
    severity: str = 'warning'
    auto_generated: bool = False
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'category': self.category,
            'description': self.description,
            'source_file': self.source_file,
            'severity': self.severity,
            'auto_generated': self.auto_generated,
            'resolved': self.resolved,
        }


class FeedbackLoop:
    """Manages a feedback log for migration issues."""

    def __init__(self, log_path: str = 'feedback_log.json'):
        self.log_path = log_path
        self.entries: List[FeedbackEntry] = []
        self._load()

    def _load(self) -> None:
        """Load existing entries from disk."""
        if os.path.isfile(self.log_path):
            try:
                with open(self.log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in data.get('entries', []):
                    self.entries.append(FeedbackEntry(**item))
            except (json.JSONDecodeError, OSError, TypeError):
                pass

    def _save(self) -> None:
        """Persist entries to disk."""
        data = {
            'version': '1.0',
            'entry_count': len(self.entries),
            'entries': [e.to_dict() for e in self.entries],
        }
        try:
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.warning("Failed to save feedback log: %s", exc)

    def report(self, category: str, description: str,
               source_file: str = '', severity: str = 'warning',
               auto: bool = False) -> FeedbackEntry:
        """Add a new feedback entry."""
        entry = FeedbackEntry(
            timestamp=datetime.now().isoformat(),
            category=category,
            description=description,
            source_file=source_file,
            severity=severity,
            auto_generated=auto,
        )
        self.entries.append(entry)
        self._save()
        return entry

    def report_dax_leak(self, expression: str, source_file: str = '') -> FeedbackEntry:
        """Shortcut to report a DAX leak."""
        return self.report(
            'dax_leak',
            f'Unconverted Qlik function in DAX: {expression[:200]}',
            source_file=source_file,
            severity='error',
            auto=True,
        )

    def report_visual_mismatch(self, visual_type: str,
                                source_file: str = '') -> FeedbackEntry:
        """Shortcut to report a visual type mismatch."""
        return self.report(
            'visual_mismatch',
            f'No mapping for visual type: {visual_type}',
            source_file=source_file,
            severity='warning',
            auto=True,
        )

    def resolve(self, index: int) -> bool:
        """Mark an entry as resolved."""
        if 0 <= index < len(self.entries):
            self.entries[index].resolved = True
            self._save()
            return True
        return False

    def summary(self) -> Dict[str, Any]:
        """Return a summary of the feedback log."""
        total = len(self.entries)
        resolved = sum(1 for e in self.entries if e.resolved)
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for e in self.entries:
            by_category[e.category] = by_category.get(e.category, 0) + 1
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        return {
            'total': total,
            'resolved': resolved,
            'open': total - resolved,
            'by_category': by_category,
            'by_severity': by_severity,
        }

    def generate_dashboard_html(self) -> str:
        """Generate a simple HTML dashboard of feedback status."""
        summary = self.summary()
        entries_html = []
        for i, e in enumerate(self.entries):
            status = '✅' if e.resolved else '❌'
            esc_desc = (e.description.replace('&', '&amp;')
                        .replace('<', '&lt;').replace('>', '&gt;'))
            entries_html.append(
                f'<tr><td>{i}</td><td>{status}</td><td>{e.severity}</td>'
                f'<td>{e.category}</td><td>{esc_desc}</td>'
                f'<td>{e.timestamp}</td></tr>'
            )
        rows = '\n'.join(entries_html) or '<tr><td colspan="6">No entries</td></tr>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Feedback Dashboard</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 2rem; background: #fafafa; }}
  .stats {{ display: flex; gap: 2rem; margin-bottom: 2rem; }}
  .stat {{ background: white; padding: 1rem 2rem; border-radius: 8px;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); text-align: center; }}
  .stat .number {{ font-size: 2rem; font-weight: bold; color: #0078d4; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }}
  th {{ background: #f3f3f3; text-align: left; padding: 0.8rem 1rem;
        border-bottom: 2px solid #ddd; }}
  td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #eee; }}
</style>
</head>
<body>
<h1>Migration Feedback Dashboard</h1>
<div class="stats">
  <div class="stat"><div class="number">{summary['total']}</div><div>Total</div></div>
  <div class="stat"><div class="number">{summary['open']}</div><div>Open</div></div>
  <div class="stat"><div class="number">{summary['resolved']}</div><div>Resolved</div></div>
</div>
<table>
  <thead><tr><th>#</th><th>Status</th><th>Severity</th><th>Category</th>
  <th>Description</th><th>Timestamp</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>"""
