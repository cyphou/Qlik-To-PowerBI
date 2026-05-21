"""PDF renderer — generates migration summary reports as PDF.

Uses stdlib only: builds an HTML report and provides a method to
convert it to PDF via an external tool (weasyprint, wkhtmltopdf) if
available, otherwise saves as HTML.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger('qlik_to_powerbi.pdf_renderer')

__all__ = ['PdfRenderer', 'render_migration_pdf']


class PdfRenderer:
    """Renders migration report data as a PDF-ready HTML document."""

    def __init__(self, app_name: str = '', output_dir: str = '.'):
        self.app_name = app_name
        self.output_dir = output_dir

    def _build_html(self, report_data: Dict[str, Any],
                    qa_data: Optional[Dict] = None,
                    lineage_data: Optional[Dict] = None) -> str:
        """Build a print-optimized HTML document."""
        try:
            from powerbi_import.html_template import (
                html_open, html_close, section_open, section_close,
                data_table, stat_card, stat_grid, fidelity_bar, esc,
            )
        except ImportError:
            from html_template import (
                html_open, html_close, section_open, section_close,
                data_table, stat_card, stat_grid, fidelity_bar, esc,
            )

        title = f'Migration Report: {self.app_name}'
        html = html_open(title, subtitle='Qlik → Power BI Migration Summary')

        # Add print styles
        html += '<style>@media print { .no-print { display: none; } body { font-size: 10pt; } }</style>'

        # Executive summary
        summary = report_data.get('summary', {})
        cards = [
            {'value': summary.get('total', 0), 'label': 'Total Items'},
            {'value': summary.get('exact', 0), 'label': 'Exact Match'},
            {'value': summary.get('approximate', 0), 'label': 'Approximate'},
            {'value': summary.get('unsupported', 0), 'label': 'Unsupported'},
        ]
        html += stat_grid(cards)

        # Fidelity score
        total = summary.get('total', 1) or 1
        exact = summary.get('exact', 0)
        pct = round(exact * 100 / total)
        html += section_open('Fidelity', 'Migration Fidelity')
        html += fidelity_bar(pct)
        html += section_close()

        # Items detail
        items = report_data.get('items', [])
        if items:
            html += section_open('Items', 'Migration Items')
            headers = ['Item', 'Type', 'Status', 'Notes']
            rows = []
            for item in items[:100]:
                rows.append([
                    esc(item.get('name', '')),
                    esc(item.get('type', '')),
                    esc(item.get('status', '')),
                    esc(item.get('notes', '')[:80]),
                ])
            html += data_table(headers, rows)
            html += section_close()

        # QA results
        if qa_data:
            html += section_open('QA', 'QA Pipeline Results')
            qa_summary = qa_data.get('summary', {})
            qa_cards = [
                {'value': qa_summary.get('total_checks', 0), 'label': 'Checks'},
                {'value': qa_summary.get('passed', 0), 'label': 'Passed'},
                {'value': qa_summary.get('autofixed', 0), 'label': 'Auto-fixed'},
                {'value': qa_summary.get('remaining', 0), 'label': 'Remaining'},
            ]
            html += stat_grid(qa_cards)
            html += section_close()

        # Lineage summary
        if lineage_data:
            html += section_open('Lineage', 'Lineage Summary')
            html += f'<p>Nodes: {lineage_data.get("node_count", 0)}, '
            html += f'Edges: {lineage_data.get("edge_count", 0)}</p>'
            html += section_close()

        html += html_close()
        return html

    def render_html(self, report_data: Dict[str, Any],
                    qa_data: Optional[Dict] = None,
                    lineage_data: Optional[Dict] = None) -> str:
        """Render to HTML file. Returns the output path."""
        html = self._build_html(report_data, qa_data, lineage_data)
        os.makedirs(self.output_dir, exist_ok=True)
        filename = f'{self.app_name or "migration"}_report.html'
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("HTML report saved to %s", output_path)
        return output_path

    def render_pdf(self, report_data: Dict[str, Any],
                   qa_data: Optional[Dict] = None,
                   lineage_data: Optional[Dict] = None) -> str:
        """Render to PDF if weasyprint available, else HTML fallback."""
        html = self._build_html(report_data, qa_data, lineage_data)
        os.makedirs(self.output_dir, exist_ok=True)

        try:
            import weasyprint  # type: ignore[import-untyped]
            filename = f'{self.app_name or "migration"}_report.pdf'
            output_path = os.path.join(self.output_dir, filename)
            doc = weasyprint.HTML(string=html)
            doc.write_pdf(output_path)
            logger.info("PDF report saved to %s", output_path)
            return output_path
        except ImportError:
            logger.warning("weasyprint not available; falling back to HTML output")
            return self.render_html(report_data, qa_data, lineage_data)


def render_migration_pdf(app_name: str, output_dir: str,
                         report_data: Dict[str, Any],
                         qa_data: Optional[Dict] = None,
                         lineage_data: Optional[Dict] = None) -> str:
    """Convenience function to render a migration PDF."""
    renderer = PdfRenderer(app_name=app_name, output_dir=output_dir)
    return renderer.render_pdf(report_data, qa_data, lineage_data)
