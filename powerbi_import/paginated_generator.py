"""Paginated Report Generator — RDL-style paginated reports from Qlik dashboards.

Extends the existing paginated layout generation in PBIPGenerator with:
- Multi-page layouts with page breaks
- Table/matrix visual rendering with row groups and column groups
- Charts as embedded visuals (image placeholders)
- Page headers/footers with dynamic fields (page number, date, report name)
- RDL-compatible JSON output for Power BI paginated reports
- Subreport linking for drill-through patterns
- Expression-based formatting (conditional row colors)

Usage:
    from powerbi_import.paginated_generator import PaginatedReportGenerator

    gen = PaginatedReportGenerator(project_dir, report_name)
    gen.generate(worksheets, datasources, calculations)
"""

import json
import os
import re
import uuid
from datetime import datetime

# ════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════

_PAGE_WIDTH_INCHES = 11.0
_PAGE_HEIGHT_INCHES = 8.5
_MARGIN_INCHES = 0.5
_BODY_WIDTH = _PAGE_WIDTH_INCHES - 2 * _MARGIN_INCHES
_BODY_HEIGHT = _PAGE_HEIGHT_INCHES - 2 * _MARGIN_INCHES - 1.0  # Reserve for header/footer

_HEADER_HEIGHT_INCHES = 0.75
_FOOTER_HEIGHT_INCHES = 0.5

# Visual type → paginated element mapping
_VISUAL_TO_PAGINATED = {
    'table': 'Tablix',
    'tableEx': 'Tablix',
    'pivot-table': 'Tablix',
    'pivotTable': 'Tablix',
    'crosstab': 'Tablix',
    'matrix': 'Tablix',
    'barchart': 'Chart',
    'linechart': 'Chart',
    'piechart': 'Chart',
    'scatter': 'Chart',
    'combo': 'Chart',
    'area': 'Chart',
    'clusteredBarChart': 'Chart',
    'clusteredColumnChart': 'Chart',
    'lineChart': 'Chart',
    'pieChart': 'Chart',
    'scatterChart': 'Chart',
    'kpi': 'Textbox',
    'card': 'Textbox',
    'text-image': 'Textbox',
    'gauge': 'Chart',
    'map': 'Image',
}


def _new_guid():
    return str(uuid.uuid4())


def _inches(val):
    """Format a float value as an inches string."""
    return f"{val:.4f}in"


# ════════════════════════════════════════════════════════════════════
#  PAGINATED REPORT GENERATOR
# ════════════════════════════════════════════════════════════════════

class PaginatedReportGenerator:
    """Generates paginated (RDL-style) reports from Qlik worksheet data."""

    def __init__(self, project_dir, report_name):
        self.project_dir = project_dir
        self.report_name = report_name
        self.pag_dir = os.path.join(project_dir, 'PaginatedReport')
        os.makedirs(self.pag_dir, exist_ok=True)

    def generate(self, worksheets, datasources=None, calculations=None,
                 page_size='letter', orientation='landscape'):
        """Generate paginated report from worksheets.

        Args:
            worksheets: list of worksheet dicts
            datasources: list of datasource dicts (for data source refs)
            calculations: list of calculation dicts
            page_size: 'letter' or 'a4'
            orientation: 'landscape' or 'portrait'

        Returns:
            dict with stats: {pages, tablixes, charts, textboxes}
        """
        if page_size == 'a4':
            pw, ph = 11.69, 8.27
        else:
            pw, ph = 11.0, 8.5

        if orientation == 'portrait':
            pw, ph = ph, pw

        stats = {'pages': 0, 'tablixes': 0, 'charts': 0, 'textboxes': 0}

        report = self._create_report_definition(pw, ph)
        pages = []
        pages_dir = os.path.join(self.pag_dir, 'pages')
        os.makedirs(pages_dir, exist_ok=True)

        # Create header and footer
        header = self._create_header()
        footer = self._create_footer()

        # Create one page per worksheet
        for i, ws in enumerate(worksheets or []):
            page = self._create_page(ws, i + 1, pw, ph)
            pages.append(page)
            stats['pages'] += 1

            # Count element types
            for elem in page.get('body', {}).get('items', []):
                elem_type = elem.get('type', '')
                if elem_type == 'Tablix':
                    stats['tablixes'] += 1
                elif elem_type == 'Chart':
                    stats['charts'] += 1
                elif elem_type == 'Textbox':
                    stats['textboxes'] += 1

            # Write individual page JSON
            page_path = os.path.join(pages_dir, f'page{i + 1}.json')
            with open(page_path, 'w', encoding='utf-8') as f:
                json.dump(page, f, indent=2, ensure_ascii=False)

        # Write report definition
        report['pageCount'] = stats['pages']
        report['pages'] = [f'pages/page{i + 1}.json' for i in range(stats['pages'])]
        report_path = os.path.join(self.pag_dir, 'report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Write header and footer
        header_path = os.path.join(self.pag_dir, 'header.json')
        with open(header_path, 'w', encoding='utf-8') as f:
            json.dump(header, f, indent=2, ensure_ascii=False)

        footer_path = os.path.join(self.pag_dir, 'footer.json')
        with open(footer_path, 'w', encoding='utf-8') as f:
            json.dump(footer, f, indent=2, ensure_ascii=False)

        # Write data source references
        if datasources:
            ds_def = self._create_datasource_refs(datasources)
            ds_path = os.path.join(self.pag_dir, 'datasources.json')
            with open(ds_path, 'w', encoding='utf-8') as f:
                json.dump(ds_def, f, indent=2, ensure_ascii=False)

        return stats

    def _create_report_definition(self, page_width, page_height):
        """Create the top-level paginated report definition."""
        return {
            'name': self.report_name,
            'type': 'PaginatedReport',
            'format': 'RDL',
            'created': datetime.now().isoformat(),
            'pageWidth': _inches(page_width),
            'pageHeight': _inches(page_height),
            'marginTop': _inches(_MARGIN_INCHES),
            'marginBottom': _inches(_MARGIN_INCHES),
            'marginLeft': _inches(_MARGIN_INCHES),
            'marginRight': _inches(_MARGIN_INCHES),
            'interactiveWidth': _inches(page_width),
            'interactiveHeight': _inches(page_height),
            'pageCount': 0,
            'pages': [],
        }

    def _create_header(self):
        """Create paginated report header."""
        return {
            'type': 'PageHeader',
            'height': _inches(_HEADER_HEIGHT_INCHES),
            'printOnFirstPage': True,
            'printOnLastPage': True,
            'items': [
                {
                    'type': 'Textbox',
                    'name': 'HeaderTitle',
                    'value': self.report_name,
                    'style': {
                        'fontFamily': 'Segoe UI',
                        'fontSize': '14pt',
                        'fontWeight': 'Bold',
                        'color': '#333333',
                    },
                    'top': _inches(0.1),
                    'left': _inches(0),
                    'width': _inches(5),
                    'height': _inches(0.5),
                },
                {
                    'type': 'Textbox',
                    'name': 'HeaderDate',
                    'value': '=Globals!ExecutionTime',
                    'style': {
                        'fontFamily': 'Segoe UI',
                        'fontSize': '9pt',
                        'color': '#666666',
                        'textAlign': 'Right',
                    },
                    'top': _inches(0.1),
                    'left': _inches(6),
                    'width': _inches(4),
                    'height': _inches(0.5),
                },
            ],
        }

    def _create_footer(self):
        """Create paginated report footer with page numbers."""
        return {
            'type': 'PageFooter',
            'height': _inches(_FOOTER_HEIGHT_INCHES),
            'printOnFirstPage': True,
            'printOnLastPage': True,
            'items': [
                {
                    'type': 'Textbox',
                    'name': 'FooterPageNumber',
                    'value': '=Globals!PageNumber & " of " & Globals!TotalPages',
                    'style': {
                        'fontFamily': 'Segoe UI',
                        'fontSize': '8pt',
                        'color': '#999999',
                        'textAlign': 'Center',
                    },
                    'top': _inches(0),
                    'left': _inches(3),
                    'width': _inches(4),
                    'height': _inches(0.3),
                },
            ],
        }

    def _create_page(self, worksheet, page_num, page_width, page_height):
        """Create a single page from a worksheet."""
        ws_name = worksheet.get('name', f'Page{page_num}')
        ws_type = worksheet.get('type', 'table')
        mark_type = worksheet.get('mark_type', ws_type)

        paginated_type = _VISUAL_TO_PAGINATED.get(mark_type,
                         _VISUAL_TO_PAGINATED.get(ws_type, 'Tablix'))

        body_items = []

        # Title
        body_items.append({
            'type': 'Textbox',
            'name': f'Title_{page_num}',
            'value': ws_name,
            'style': {
                'fontFamily': 'Segoe UI Semibold',
                'fontSize': '16pt',
                'color': '#333333',
                'fontWeight': 'Bold',
            },
            'top': _inches(0),
            'left': _inches(0),
            'width': _inches(_BODY_WIDTH),
            'height': _inches(0.5),
        })

        # Main content element
        if paginated_type == 'Tablix':
            tablix = self._create_tablix(worksheet, page_num)
            tablix['top'] = _inches(0.6)
            tablix['left'] = _inches(0)
            tablix['width'] = _inches(_BODY_WIDTH)
            tablix['height'] = _inches(_BODY_HEIGHT - 0.6)
            body_items.append(tablix)

        elif paginated_type == 'Chart':
            chart = self._create_chart(worksheet, page_num, mark_type)
            chart['top'] = _inches(0.6)
            chart['left'] = _inches(0)
            chart['width'] = _inches(_BODY_WIDTH)
            chart['height'] = _inches(_BODY_HEIGHT - 0.6)
            body_items.append(chart)

        else:
            # Textbox placeholder
            body_items.append({
                'type': 'Textbox',
                'name': f'Content_{page_num}',
                'value': f'[Visual: {ws_name}]',
                'style': {'fontFamily': 'Segoe UI', 'fontSize': '11pt'},
                'top': _inches(0.6),
                'left': _inches(0),
                'width': _inches(_BODY_WIDTH),
                'height': _inches(_BODY_HEIGHT - 0.6),
            })

        return {
            'name': f'Page{page_num}',
            'displayName': ws_name,
            'pageBreak': 'End' if page_num > 0 else 'None',
            'body': {
                'height': _inches(_BODY_HEIGHT),
                'items': body_items,
            },
        }

    def _create_tablix(self, worksheet, page_num):
        """Create a Tablix (table/matrix) element from worksheet data."""
        columns = worksheet.get('columns', [])
        dimensions = worksheet.get('dimensions', [])
        measures = worksheet.get('measures', [])

        # Build columns from dimensions + measures
        col_defs = []
        for dim in dimensions:
            name = dim.get('field', dim) if isinstance(dim, dict) else str(dim)
            col_defs.append({
                'name': name,
                'type': 'RowGroup',
                'width': _inches(1.5),
            })
        for meas in measures:
            name = meas.get('field', meas) if isinstance(meas, dict) else str(meas)
            col_defs.append({
                'name': name,
                'type': 'Detail',
                'width': _inches(1.2),
                'format': meas.get('format', '') if isinstance(meas, dict) else '',
            })

        # Fallback: use generic columns
        if not col_defs and columns:
            for c in columns[:20]:
                name = c.get('name', c) if isinstance(c, dict) else str(c)
                col_defs.append({
                    'name': name,
                    'type': 'Detail',
                    'width': _inches(1.5),
                })

        return {
            'type': 'Tablix',
            'name': f'Tablix_{page_num}',
            'dataSetRef': worksheet.get('datasource', 'DataSet1'),
            'columns': col_defs,
            'rowGroups': [c['name'] for c in col_defs if c['type'] == 'RowGroup'],
            'sortExpressions': [],
            'style': {
                'fontFamily': 'Segoe UI',
                'fontSize': '9pt',
                'headerBackground': '#0078D4',
                'headerColor': '#FFFFFF',
                'headerFontWeight': 'Bold',
                'alternateRowBackground': '#F5F5F5',
                'borderColor': '#DDDDDD',
                'borderWidth': '0.5pt',
            },
            'noRowsMessage': 'No data available',
        }

    def _create_chart(self, worksheet, page_num, chart_type):
        """Create a Chart element from worksheet data."""
        chart_type_map = {
            'barchart': 'Column',
            'clusteredBarChart': 'Column',
            'clusteredColumnChart': 'Column',
            'linechart': 'Line',
            'lineChart': 'Line',
            'piechart': 'Pie',
            'pieChart': 'Pie',
            'scatter': 'Scatter',
            'scatterChart': 'Scatter',
            'area': 'Area',
            'combo': 'Column',
            'gauge': 'Gauge',
        }

        rdl_chart = chart_type_map.get(chart_type, 'Column')
        dimensions = worksheet.get('dimensions', [])
        measures = worksheet.get('measures', [])

        category_fields = []
        for d in dimensions[:2]:
            name = d.get('field', d) if isinstance(d, dict) else str(d)
            category_fields.append(name)

        value_fields = []
        for m in measures[:4]:
            name = m.get('field', m) if isinstance(m, dict) else str(m)
            value_fields.append(name)

        return {
            'type': 'Chart',
            'name': f'Chart_{page_num}',
            'chartType': rdl_chart,
            'dataSetRef': worksheet.get('datasource', 'DataSet1'),
            'categoryFields': category_fields,
            'valueFields': value_fields,
            'title': worksheet.get('name', ''),
            'style': {
                'fontFamily': 'Segoe UI',
                'titleFontSize': '12pt',
                'legendPosition': 'Bottom',
                'palette': 'BrightPastel',
            },
        }

    def _create_datasource_refs(self, datasources):
        """Create data source reference definitions for paginated report."""
        refs = []
        for ds in datasources:
            name = ds.get('name', ds.get('caption', 'DataSource'))
            conn = ds.get('connection', {})
            refs.append({
                'name': re.sub(r'[^a-zA-Z0-9_]', '_', name),
                'type': conn.get('type', 'Unknown'),
                'connectionString': conn.get('connection_string', ''),
                'credentialRetrieval': 'Prompt',
            })
        return {'dataSources': refs}
