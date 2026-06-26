"""
Migration report generator.

Produces a structured JSON report listing every converted item with
its conversion status (exact, approximate, placeholder, unsupported).

Usage:
    report = MigrationReport("Superstore_Sales")
    report.add_item("calculation", "Profit Ratio", "exact", dax="DIVIDE([Profit],[Sales])")
    report.add_item("calculation", "MAKEPOINT field", "unsupported", note="No DAX spatial equivalent")
    report.save("artifacts/powerbi_projects/reports/")
"""

import json
import os
import re
from datetime import datetime


# ── Patterns that indicate approximate / placeholder / unsupported conversions ──

# DAX comments left by dax_converter for unsupported functions
_UNSUPPORTED_PATTERNS = [
    (re.compile(r'/\*\s*MAKEPOINT', re.IGNORECASE), 'MAKEPOINT (no DAX spatial equivalent)'),
    (re.compile(r'/\*\s*SCRIPT_(BOOL|INT|REAL|STR)', re.IGNORECASE), 'Analytics extension (SCRIPT_*)'),
    (re.compile(r'/\*\s*CORR.*no direct DAX', re.IGNORECASE), 'CORR (no direct DAX equivalent)'),
    (re.compile(r'/\*\s*COVAR.*no direct DAX', re.IGNORECASE), 'COVAR (no direct DAX equivalent)'),
]

_APPROXIMATE_PATTERNS = [
    (re.compile(r'/\*.*approximate\s*\*/', re.IGNORECASE), 'Approximate DAX conversion'),
    (re.compile(r'/\*.*manual conversion needed', re.IGNORECASE), 'Manual conversion needed'),
    (re.compile(r'/\*.*placeholder', re.IGNORECASE), 'Placeholder formula'),
]

# Source functions that should not appear in DAX output
_SOURCE_LEAK_PATTERNS = [
    re.compile(r'\bCOUNTD\s*\(', re.IGNORECASE),
    re.compile(r'\bZN\s*\(', re.IGNORECASE),
    re.compile(r'\bIFNULL\s*\(', re.IGNORECASE),
    re.compile(r'\bATTR\s*\(', re.IGNORECASE),
    re.compile(r'\bDATETRUNC\s*\(', re.IGNORECASE),
    re.compile(r'\bDATEPART\s*\(', re.IGNORECASE),
]


class MigrationReport:
    """Tracks per-item migration status and generates a structured report."""

    # Valid statuses
    EXACT = 'exact'
    APPROXIMATE = 'approximate'
    PLACEHOLDER = 'placeholder'
    UNSUPPORTED = 'unsupported'
    SKIPPED = 'skipped'

    _VALID_STATUSES = {EXACT, APPROXIMATE, PLACEHOLDER, UNSUPPORTED, SKIPPED}

    # Map raw connector keys → human-readable Power BI connector names
    _CONNECTOR_DISPLAY = {
        'sqlserver': 'SQL Server', 'sql_server': 'SQL Server', 'mssql': 'SQL Server',
        'azuresql': 'Azure SQL', 'azure_sql': 'Azure SQL', 'synapse': 'Azure Synapse',
        'postgresql': 'PostgreSQL', 'postgres': 'PostgreSQL',
        'oracle': 'Oracle', 'mysql': 'MySQL', 'mariadb': 'MariaDB',
        'csv': 'CSV', 'excel': 'Excel', 'xlsx': 'Excel',
        'snowflake': 'Snowflake', 'bigquery': 'BigQuery', 'redshift': 'Redshift',
        'databricks': 'Databricks', 'teradata': 'Teradata', 'sap_hana': 'SAP HANA',
        'saphana': 'SAP HANA', 'db2': 'DB2', 'vertica': 'Vertica', 'impala': 'Impala',
        'qvd': 'QVD', 'odbc': 'ODBC', 'oledb': 'OLE DB', 'odata': 'OData',
        'rest': 'REST', 'web': 'Web', 'json': 'JSON', 'xml': 'XML',
        'sharepoint': 'SharePoint', 'salesforce': 'Salesforce', 'mongodb': 'MongoDB',
        'cosmosdb': 'Cosmos DB', 'dataverse': 'Dataverse', 'loadscript': 'Load Script',
    }

    def __init__(self, report_name):
        self.report_name = report_name
        self.created_at = datetime.now().isoformat()
        self.items = []
        self._summary = None

    def add_item(self, category, name, status, *, dax=None, note=None,
                 source_formula=None):
        """Add a converted item to the report.

        Args:
            category: Object type (e.g. 'calculation', 'visual', 'relationship',
                      'parameter', 'set', 'group', 'bin', 'hierarchy',
                      'datasource', 'filter', 'rls_role', 'bookmark')
            name: Item name or identifier
            status: One of 'exact', 'approximate', 'placeholder', 'unsupported', 'skipped'
            dax: Optional generated DAX formula
            note: Optional human-readable note
            source_formula: Optional original source formula
        """
        if status not in self._VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'; must be one of {self._VALID_STATUSES}")

        entry = {
            'category': category,
            'name': name,
            'status': status,
        }
        if source_formula:
            entry['source_formula'] = source_formula
        if dax:
            entry['dax'] = dax
        if note:
            entry['note'] = note

        self.items.append(entry)
        self._summary = None  # Invalidate cached summary

    # ── Bulk convenience methods ─────────────────────────────────

    def add_calculations(self, calculations, calc_map):
        """Classify and add all calculations from the extraction.

        Args:
            calculations: List of calculation dicts from calculations.json
            calc_map: Dict mapping calculation ID/name → generated DAX formula
        """
        for calc in calculations:
            name = calc.get('caption') or calc.get('name', 'Unknown')
            source = calc.get('formula', '')
            calc_id = calc.get('name', name)
            # Clean version without brackets
            calc_id_clean = calc_id.replace('[', '').replace(']', '')

            # Try multiple lookup strategies for the DAX expression
            dax = (calc_map.get(calc_id) or
                   calc_map.get(name) or
                   calc_map.get(calc_id_clean) or
                   calc_map.get(name.replace('[', '').replace(']', '')) or
                   '')

            if not dax:
                self.add_item('calculation', name, self.SKIPPED,
                              source_formula=source,
                              note='No DAX output generated')
                continue

            status = self._classify_dax(dax)
            self.add_item('calculation', name, status,
                          source_formula=source, dax=dax)

    def add_visuals(self, worksheets, visual_type_map=None):
        """Add visual migration entries.

        Args:
            worksheets: List of worksheet dicts from worksheets.json
            visual_type_map: Optional dict of source_mark → pbi_visual used
        """
        for ws in worksheets:
            name = ws.get('name', 'Unknown')
            mark = ws.get('mark_type', ws.get('mark_encoding', {}).get('type', ''))
            if isinstance(mark, dict):
                mark = mark.get('type', '')

            # All mapped visuals are considered exact unless the mark type
            # falls back to the default "tableEx"
            mapped = (visual_type_map or {}).get(str(mark).lower(), 'tableEx')
            if str(mark).lower() and mapped == 'tableEx' and str(mark).lower() != 'automatic':
                status = self.APPROXIMATE
                note = f'Mark "{mark}" mapped to tableEx (fallback)'
            else:
                status = self.EXACT
                note = f'{mark} → {mapped}' if mark else None

            self.add_item('visual', name, status, note=note)

    def add_parameters(self, parameters):
        """Add parameter migration entries."""
        for p in parameters:
            name = p.get('name') or p.get('caption', 'Unknown')
            self.add_item('parameter', name, self.EXACT,
                          note=f"domain={p.get('domain_type', '?')}")

    def add_relationships(self, relationships):
        """Add relationship migration entries."""
        for rel in relationships:
            from_t = rel.get('fromTable', '?')
            to_t = rel.get('toTable', '?')
            name = f"{from_t} → {to_t}"
            card = rel.get('cardinality', '?')
            self.add_item('relationship', name, self.EXACT,
                          note=f"cardinality={card}")

    def add_hierarchies(self, hierarchies):
        """Add hierarchy migration entries."""
        for h in hierarchies:
            name = h.get('name', 'Unknown')
            levels = len(h.get('levels', []))
            self.add_item('hierarchy', name, self.EXACT,
                          note=f"{levels} levels")

    def add_sets(self, sets):
        """Add set migration entries."""
        for s in sets:
            name = s.get('name', 'Unknown')
            self.add_item('set', name, self.EXACT,
                          note='Boolean calculated column via IN')

    def add_groups(self, groups):
        """Add group migration entries."""
        for g in groups:
            name = g.get('name', 'Unknown')
            self.add_item('group', name, self.EXACT,
                          note='SWITCH calculated column')

    def add_bins(self, bins):
        """Add bin migration entries."""
        for b in bins:
            name = b.get('name', 'Unknown')
            self.add_item('bin', name, self.EXACT,
                          note='FLOOR calculated column')

    def add_stories(self, stories):
        """Add story → bookmark migration entries."""
        for s in stories:
            name = s.get('name') or s.get('caption', 'Unknown')
            points = len(s.get('story_points', []))
            self.add_item('bookmark', name, self.EXACT,
                          note=f"Converted to {points} bookmark(s)")

    def add_user_filters(self, user_filters):
        """Add RLS role migration entries.

        Classification logic:
        - user_filter with explicit user_mappings → EXACT (full DAX generated)
        - user_filter without mappings → EXACT (column = USERPRINCIPALNAME())
        - calculated_security with ISMEMBEROF → APPROXIMATE (needs Azure AD groups)
        - calculated_security with USERNAME/FULLNAME → EXACT (direct DAX mapping)
        """
        for uf in user_filters:
            name = uf.get('name') or uf.get('field', 'Unknown')
            uf_type = uf.get('type', 'user_filter')
            ismemberof_groups = uf.get('ismemberof_groups', [])
            functions_used = [f.upper() for f in uf.get('functions_used', [])]

            if uf_type == 'calculated_security' and ismemberof_groups:
                groups = ', '.join(ismemberof_groups)
                self.add_item('rls_role', name, self.APPROXIMATE,
                              note=f'ISMEMBEROF → RLS role (assign Azure AD group members: {groups})')
            elif uf_type == 'calculated_security':
                funcs = ', '.join(uf.get('functions_used', []))
                self.add_item('rls_role', name, self.EXACT,
                              note=f'Calculated security ({funcs}) → USERPRINCIPALNAME()')
            elif uf.get('user_mappings'):
                self.add_item('rls_role', name, self.EXACT,
                              note='User filter with explicit mappings → RLS role')
            else:
                self.add_item('rls_role', name, self.EXACT,
                              note='User filter → RLS role with USERPRINCIPALNAME()')

    def add_datasources(self, datasources):
        """Add datasource migration entries.

        Accepts both the raw extracted schema (flat ``connectionType`` /
        ``tableName`` keys, one entry per table) and the adapted schema
        (nested ``connection`` dict + ``tables`` list).
        """
        for ds in datasources:
            name = (ds.get('name') or ds.get('tableName')
                    or ds.get('caption') or 'Unknown')
            # Connection type can be a nested connection dict (adapted form)
            # or a flat connectionType/type key (raw extracted form).
            conn = ds.get('connection', {})
            if isinstance(conn, dict):
                raw_conn = (conn.get('class') or conn.get('type')
                            or ds.get('connectionType') or ds.get('type') or '')
            else:
                raw_conn = ds.get('connectionType') or ds.get('type') or ''
            conn_type = self._CONNECTOR_DISPLAY.get(
                str(raw_conn).lower(), raw_conn or 'Unknown')
            # Raw entries represent a single source table; adapted entries
            # carry an explicit 'tables' list.
            tables_list = ds.get('tables')
            if isinstance(tables_list, list) and tables_list:
                table_count = len(tables_list)
            elif ds.get('tableName') or ds.get('columns'):
                table_count = 1
            else:
                table_count = 0
            self.add_item('datasource', name, self.EXACT,
                          note=f"{conn_type}, {table_count} table(s)")

    # ── Classification helpers ───────────────────────────────────

    @classmethod
    def _classify_dax(cls, dax):
        """Classify a DAX formula's conversion fidelity.

        Returns one of: exact, approximate, placeholder, unsupported.
        """
        if not dax:
            return cls.SKIPPED

        # Check unsupported patterns first (highest severity)
        for pattern, _ in _UNSUPPORTED_PATTERNS:
            if pattern.search(dax):
                return cls.UNSUPPORTED

        # Check approximate patterns
        for pattern, _ in _APPROXIMATE_PATTERNS:
            if pattern.search(dax):
                return cls.APPROXIMATE

        # Check for leaked source functions
        for pattern in _SOURCE_LEAK_PATTERNS:
            if pattern.search(dax):
                return cls.APPROXIMATE

        return cls.EXACT

    # ── Summary computation ──────────────────────────────────────

    def get_summary(self):
        """Compute summary statistics from all tracked items."""
        if self._summary is not None:
            return self._summary

        by_status = {}
        by_category = {}

        for item in self.items:
            st = item['status']
            cat = item['category']

            by_status[st] = by_status.get(st, 0) + 1

            if cat not in by_category:
                by_category[cat] = {'total': 0}
            by_category[cat]['total'] += 1
            by_category[cat][st] = by_category[cat].get(st, 0) + 1

        total = len(self.items)
        exact = by_status.get(self.EXACT, 0)
        approx = by_status.get(self.APPROXIMATE, 0)
        placeholder = by_status.get(self.PLACEHOLDER, 0)
        unsupported = by_status.get(self.UNSUPPORTED, 0)
        skipped = by_status.get(self.SKIPPED, 0)

        # Fidelity score: exact=100%, approximate=50%, rest=0%
        if total > 0:
            fidelity = round((exact * 100 + approx * 50) / total, 1)
        else:
            fidelity = 100.0

        self._summary = {
            'total_items': total,
            'exact': exact,
            'approximate': approx,
            'placeholder': placeholder,
            'unsupported': unsupported,
            'skipped': skipped,
            'fidelity_score': fidelity,
            'by_category': by_category,
        }
        return self._summary

    # ── Serialisation ────────────────────────────────────────────

    def to_dict(self):
        """Return the full report as a dictionary."""
        return {
            'report_name': self.report_name,
            'created_at': self.created_at,
            'summary': self.get_summary(),
            'items': self.items,
        }

    def save(self, output_dir='artifacts/migration_reports'):
        """Save the report as a JSON file.

        Args:
            output_dir: Directory to write the report file.

        Returns:
            str: Path to the saved report file.
        """
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'migration_report_{self.report_name}_{ts}.json'
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        return filepath

    # ── Console output ───────────────────────────────────────────

    def print_summary(self):
        """Print a human-readable summary to the console."""
        s = self.get_summary()
        print()
        print('=' * 72)
        print(f'  MIGRATION REPORT: {self.report_name}')
        print('=' * 72)
        print(f'  Total items converted: {s["total_items"]}')
        print(f'  Fidelity score:        {s["fidelity_score"]}%')
        print()
        print(f'    Exact:        {s["exact"]:>4}')
        print(f'    Approximate:  {s["approximate"]:>4}')
        print(f'    Placeholder:  {s["placeholder"]:>4}')
        print(f'    Unsupported:  {s["unsupported"]:>4}')
        print(f'    Skipped:      {s["skipped"]:>4}')

        if s['by_category']:
            print()
            print('  By category:')
            for cat, counts in sorted(s['by_category'].items()):
                total = counts['total']
                exact = counts.get('exact', 0)
                pct = round(exact / total * 100) if total else 0
                print(f'    {cat:<20} {total:>4} items  ({pct}% exact)')

        # List unsupported items
        unsupported = [i for i in self.items if i['status'] == self.UNSUPPORTED]
        if unsupported:
            print()
            print(f'  Unsupported items ({len(unsupported)}):')
            for item in unsupported[:20]:
                note = f' — {item["note"]}' if item.get('note') else ''
                print(f'    [{item["category"]}] {item["name"]}{note}')
            if len(unsupported) > 20:
                print(f'    ... and {len(unsupported) - 20} more')

        # List approximate items
        approx = [i for i in self.items if i['status'] == self.APPROXIMATE]
        if approx:
            print()
            print(f'  Approximate conversions ({len(approx)}):')
            for item in approx[:20]:
                note = f' — {item["note"]}' if item.get('note') else ''
                print(f'    [{item["category"]}] {item["name"]}{note}')
            if len(approx) > 20:
                print(f'    ... and {len(approx) - 20} more')

        print()
        print('=' * 72)
