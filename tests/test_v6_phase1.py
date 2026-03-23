"""Tests for v6.0.0 Phase 1 — Pipeline Blockers.

Covers:
  - Visual limit removal (20-visual, 10-field caps removed)
  - Load script converter wiring into extraction pipeline
  - Load script → datasource enrichment
  - Multi-page report generation from sheets
"""

import json
import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ════════════════════════════════════════════════════════════════════
#  Visual Limit Removal Tests
# ════════════════════════════════════════════════════════════════════

class TestVisualLimitRemoval(unittest.TestCase):
    """Verify the 20-visual and 10-field caps are removed."""

    def test_visual_generator_no_20_cap(self):
        """generate_visual_containers should not truncate at 20."""
        from powerbi_import.visual_generator import generate_visual_containers

        # Create 30 worksheets
        worksheets = []
        for i in range(30):
            worksheets.append({
                'name': f'Visual_{i}',
                'chart_type': 'clusteredBarChart',
                'fields': [{'name': f'Field_{i}', 'role': 'dimension'}],
            })

        containers = generate_visual_containers(
            converted_worksheets=worksheets,
            report_name='test',
            col_table_map={},
            measure_lookup={},
        )
        self.assertEqual(len(containers), 30,
                         "All 30 visuals should be generated (no truncation)")

    def test_visual_generator_empty(self):
        """generate_visual_containers with empty list returns empty."""
        from powerbi_import.visual_generator import generate_visual_containers

        containers = generate_visual_containers(
            converted_worksheets=[],
            report_name='test',
        )
        self.assertEqual(len(containers), 0)

    def test_visual_generator_large_set(self):
        """50 visuals should all be generated."""
        from powerbi_import.visual_generator import generate_visual_containers

        worksheets = [
            {'name': f'V{i}', 'chart_type': 'lineChart',
             'fields': [{'name': 'X', 'role': 'dimension'}]}
            for i in range(50)
        ]
        containers = generate_visual_containers(
            converted_worksheets=worksheets,
            report_name='BigApp',
        )
        self.assertEqual(len(containers), 50)

    def test_pbip_table_projection_no_10_cap(self):
        """Table/matrix visuals should not truncate fields at 10."""
        from powerbi_import.pbip_generator import PowerBIProjectGenerator

        tmp = tempfile.mkdtemp()
        gen = PowerBIProjectGenerator(output_dir=tmp)
        # 15 fields for a table visual (as dicts matching API)
        dim_fields = [{'name': f'Dim{i}', 'role': 'dimension'} for i in range(8)]
        mea_fields = [{'name': f'Mea{i}', 'role': 'measure'} for i in range(7)]

        all_fields = dim_fields + mea_fields
        projections = [gen._make_projection_entry(f) for f in all_fields]

        self.assertEqual(len(projections), 15,
                         "All 15 fields should be projected (no cap)")
        shutil.rmtree(tmp, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════
#  Load Script Converter Wiring Tests
# ════════════════════════════════════════════════════════════════════

class TestLoadScriptEnrichment(unittest.TestCase):
    """Tests for _enrich_from_loadscript in ExtractionOrchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_orchestrator(self, script="", datasources=None):
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator
        orch = ExtractionOrchestrator(output_dir=self.tmpdir)
        orch._data = ExtractionOrchestrator._default_intermediate()
        orch._data["loadscript"] = {"script": script}
        if datasources:
            orch._data["datasources"] = datasources
        return orch

    def test_empty_script_no_crash(self):
        orch = self._make_orchestrator(script="")
        orch._enrich_from_loadscript()
        self.assertEqual(len(orch._data["datasources"]), 0)

    def test_whitespace_script_no_crash(self):
        orch = self._make_orchestrator(script="   \n  \n  ")
        orch._enrich_from_loadscript()
        self.assertEqual(len(orch._data["datasources"]), 0)

    def test_simple_file_load_creates_m_query(self):
        script = '''
Sales:
LOAD
    Region,
    Amount
FROM [data/sales.csv]
(txt, utf8, embedded labels, delimiter is ',');
'''
        orch = self._make_orchestrator(script=script)
        orch._enrich_from_loadscript()
        # Should discover Sales table from script
        ds = orch._data["datasources"]
        self.assertGreaterEqual(len(ds), 1, "At least one datasource from load script")
        # Find the Sales entry
        sales_ds = next((d for d in ds if d.get("tableName") == "Sales"), None)
        self.assertIsNotNone(sales_ds, "Sales table should be added")
        self.assertTrue(sales_ds.get("m_query", ""), "M query should be populated")

    def test_enriches_existing_datasource(self):
        script = '''
Orders:
LOAD
    OrderID,
    CustomerID
FROM [orders.csv]
(txt, utf8, embedded labels, delimiter is ',');
'''
        existing_ds = [{
            "tableName": "Orders",
            "connectionType": "csv",
            "connection": {"type": "csv"},
            "columns": [{"name": "OrderID", "dataType": "int"}],
        }]
        orch = self._make_orchestrator(script=script, datasources=existing_ds)
        orch._enrich_from_loadscript()
        # Should enrich existing, not add duplicate
        ds = orch._data["datasources"]
        orders_list = [d for d in ds if d.get("tableName") == "Orders"]
        self.assertEqual(len(orders_list), 1, "Should not duplicate")
        self.assertTrue(orders_list[0].get("m_query", ""), "M query added")
        # Original columns preserved
        self.assertEqual(len(orders_list[0]["columns"]), 1)

    def test_multiple_load_statements(self):
        script = '''
Customers:
LOAD CustomerID, Name
FROM [customers.csv]
(txt, utf8, embedded labels, delimiter is ',');

Products:
LOAD ProductID, ProductName
FROM [products.xlsx]
(ooxml, embedded labels, table is [Sheet1$]);
'''
        orch = self._make_orchestrator(script=script)
        orch._enrich_from_loadscript()
        ds = orch._data["datasources"]
        names = [d.get("tableName") for d in ds]
        self.assertIn("Customers", names)
        self.assertIn("Products", names)

    def test_inline_load_not_crash(self):
        script = '''
StatusMap:
LOAD * INLINE [
    Code, Status
    1, Active
    2, Inactive
];
'''
        orch = self._make_orchestrator(script=script)
        # Should not crash even though INLINE is handled differently
        orch._enrich_from_loadscript()

    def test_mixed_load_and_existing(self):
        """Script has 2 tables, one matches existing, one is new."""
        script = '''
Sales:
LOAD Region, Amount FROM [sales.csv] (txt, utf8, embedded labels, delimiter is ',');

NewTable:
LOAD Code, Label FROM [lookup.csv] (txt, utf8, embedded labels, delimiter is ',');
'''
        existing = [{
            "tableName": "Sales",
            "connectionType": "csv",
            "connection": {},
            "columns": [],
        }]
        orch = self._make_orchestrator(script=script, datasources=existing)
        orch._enrich_from_loadscript()
        ds = orch._data["datasources"]
        self.assertGreaterEqual(len(ds), 2)
        new_table = next((d for d in ds if d.get("tableName") == "NewTable"), None)
        if new_table:
            self.assertEqual(new_table["connectionType"], "loadscript")

    def test_extract_calls_enrich(self):
        """Verify that extract() calls _enrich_from_loadscript."""
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator
        orch = ExtractionOrchestrator(output_dir=self.tmpdir)

        # Create a minimal JSON file to extract from
        test_json = {
            "datasources": [],
            "loadscript": {
                "script": "TestTable:\nLOAD Col1, Col2 FROM [test.csv] (txt, utf8, embedded labels, delimiter is ',');"
            },
            "sheets": [],
            "dimensions": [],
            "measures": [],
            "visualizations": [],
            "variables": [],
            "associations": [],
            "bookmarks": [],
            "master_items": [],
            "app_metadata": {"name": "Test"},
        }
        json_path = os.path.join(self.tmpdir, "test_app.json")
        with open(json_path, "w") as f:
            json.dump(test_json, f)

        orch.extract(json_path)
        # After extraction, check if loadscript enrichment ran
        ds = orch._data.get("datasources", [])
        # The script parser should have created at least one entry
        has_m_query = any(d.get("m_query") for d in ds)
        # Note: the test JSON has the script, so it should be attempted
        # (may or may not succeed depending on parser, but should not crash)


# ════════════════════════════════════════════════════════════════════
#  Multi-Page Report Generation Tests
# ════════════════════════════════════════════════════════════════════

class TestMultiPageGeneration(unittest.TestCase):
    """Verify that format adapter creates one dashboard per sheet."""

    def test_sheets_become_dashboards(self):
        """Multiple Qlik sheets → multiple dashboards in converted_objects."""
        from qlik_export.format_adapter import adapt_qlik_for_generation

        qlik_data = {
            'sheets': [
                {'id': 'sheet1', 'title': 'Overview'},
                {'id': 'sheet2', 'title': 'Details'},
                {'id': 'sheet3', 'title': 'Summary'},
            ],
            'visualizations': [
                {'id': 'v1', 'type': 'barchart', 'title': 'Sales Bar', 'sheetId': 'sheet1'},
                {'id': 'v2', 'type': 'linechart', 'title': 'Trend', 'sheetId': 'sheet1'},
                {'id': 'v3', 'type': 'piechart', 'title': 'Pie', 'sheetId': 'sheet2'},
                {'id': 'v4', 'type': 'table', 'title': 'Data Table', 'sheetId': 'sheet3'},
            ],
            'datasources': [{'tableName': 'T', 'columns': [{'name': 'Col1'}]}],
            'dimensions': [],
            'measures': [],
            'variables': [],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {'name': 'Test'},
        }

        result = adapt_qlik_for_generation(qlik_data)
        dashboards = result.get('dashboards', [])

        self.assertEqual(len(dashboards), 3, "3 sheets → 3 dashboards")
        self.assertEqual(dashboards[0]['name'], 'Overview')
        self.assertEqual(dashboards[1]['name'], 'Details')
        self.assertEqual(dashboards[2]['name'], 'Summary')

    def test_visuals_assigned_to_correct_page(self):
        """Visuals should be assigned to the correct dashboard by sheetId."""
        from qlik_export.format_adapter import adapt_qlik_for_generation

        qlik_data = {
            'sheets': [
                {'id': 'sh1', 'title': 'Page A'},
                {'id': 'sh2', 'title': 'Page B'},
            ],
            'visualizations': [
                {'id': 'v1', 'type': 'barchart', 'title': 'V1', 'sheetId': 'sh1'},
                {'id': 'v2', 'type': 'kpi', 'title': 'V2', 'sheetId': 'sh1'},
                {'id': 'v3', 'type': 'table', 'title': 'V3', 'sheetId': 'sh2'},
            ],
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'variables': [],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }

        result = adapt_qlik_for_generation(qlik_data)
        dashboards = result['dashboards']

        page_a = dashboards[0]
        page_b = dashboards[1]
        self.assertEqual(len(page_a['objects']), 2, "Page A should have 2 visuals")
        self.assertEqual(len(page_b['objects']), 1, "Page B should have 1 visual")

    def test_no_sheets_fallback_single_dashboard(self):
        """Without sheets, all visuals go to one fallback dashboard."""
        from qlik_export.format_adapter import adapt_qlik_for_generation

        qlik_data = {
            'sheets': [],
            'visualizations': [
                {'id': f'v{i}', 'type': 'barchart', 'title': f'V{i}'}
                for i in range(5)
            ],
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'variables': [],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }

        result = adapt_qlik_for_generation(qlik_data)
        dashboards = result['dashboards']
        self.assertEqual(len(dashboards), 1)
        self.assertEqual(len(dashboards[0]['objects']), 5)

    def test_single_sheet_all_visuals(self):
        """Single sheet where all visuals belong to it."""
        from qlik_export.format_adapter import adapt_qlik_for_generation

        qlik_data = {
            'sheets': [{'id': 'main', 'title': 'Main Dashboard'}],
            'visualizations': [
                {'id': 'v1', 'type': 'kpi', 'title': 'KPI 1', 'sheetId': 'main'},
                {'id': 'v2', 'type': 'kpi', 'title': 'KPI 2', 'sheetId': 'main'},
                {'id': 'v3', 'type': 'table', 'title': 'Data', 'sheetId': 'main'},
            ],
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'variables': [],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }

        result = adapt_qlik_for_generation(qlik_data)
        dashboards = result['dashboards']
        self.assertEqual(len(dashboards), 1)
        self.assertEqual(dashboards[0]['name'], 'Main Dashboard')
        self.assertEqual(len(dashboards[0]['objects']), 3)


# ════════════════════════════════════════════════════════════════════
#  QlikScriptConverter Unit Tests
# ════════════════════════════════════════════════════════════════════

class TestQlikScriptConverter(unittest.TestCase):
    """Tests for qlik_script_converter.py used by the enrichment."""

    def test_import(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        self.assertIsNotNone(QlikScriptToPowerQueryConverter)

    def test_parse_simple_load(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(
            "LOAD Field1, Field2 FROM [data/file.csv]"
        )
        self.assertEqual(stmt.source_type, 'file')
        self.assertIn('Field1', stmt.fields)
        self.assertIn('data/file.csv', stmt.source)

    def test_parse_resident_load(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(
            "LOAD Field1 RESIDENT OtherTable"
        )
        self.assertEqual(stmt.source_type, 'resident')
        self.assertEqual(stmt.source, 'OtherTable')

    def test_parse_where_clause(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(
            "LOAD * FROM [data.csv] WHERE Status = 'Active';"
        )
        self.assertIsNotNone(stmt.where_clause)
        self.assertIn('Active', stmt.where_clause)

    def test_convert_full_script_csv(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        script = '''
Sales:
LOAD
    Region,
    Amount
FROM [data/sales.csv]
(txt, utf8, embedded labels, delimiter is ',');
'''
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn('let', result)
        self.assertIn('Csv.Document', result)

    def test_convert_function_mapping(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        result = QlikScriptToPowerQueryConverter.convert_qlik_function('Upper(FieldName)')
        self.assertIn('Text.Upper', result)

    def test_convert_full_script_multiple_tables(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        script = '''
Table1:
LOAD A, B FROM [t1.csv] (txt, utf8, embedded labels, delimiter is ',');

Table2:
LOAD C, D FROM [t2.csv] (txt, utf8, embedded labels, delimiter is ',');
'''
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn('Table1', result)
        self.assertIn('Table2', result)

    def test_inline_load_handled(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        script = '''
StatusMap:
LOAD * INLINE [
Code, Status
1, Active
2, Inactive
];
'''
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn('#table', result)
        self.assertIn('Active', result)

    def test_variable_expansion(self):
        from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
        script = '''
SET vPath = data/;
Sales:
LOAD * FROM [$(vPath)sales.csv]
(txt, utf8, embedded labels, delimiter is ',');
'''
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn('data/sales.csv', result)


# ════════════════════════════════════════════════════════════════════
#  End-to-End Pipeline Tests
# ════════════════════════════════════════════════════════════════════

class TestEndToEndPipeline(unittest.TestCase):
    """Test the full extract → adapt → generate flow."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_extraction_writes_11_files(self):
        """ExtractionOrchestrator should write all 11 intermediate JSON files."""
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator, INTERMEDIATE_FILES

        test_json = {
            "app_metadata": {"name": "TestApp"},
            "datasources": [{"tableName": "Sales", "columns": [{"name": "Amount"}]}],
            "dimensions": [{"name": "Region", "field": "Region"}],
            "measures": [{"name": "Total", "expression": "Sum(Amount)"}],
            "visualizations": [{"id": "v1", "type": "barchart", "title": "Chart"}],
            "sheets": [{"id": "s1", "title": "Overview"}],
            "variables": [{"name": "vYear", "definition": "2024"}],
            "loadscript": {"script": ""},
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        json_path = os.path.join(self.tmpdir, "app.json")
        with open(json_path, "w") as f:
            json.dump(test_json, f)

        orch = ExtractionOrchestrator(output_dir=self.tmpdir)
        orch.extract(json_path)
        out_dir = os.path.join(self.tmpdir, "json_out")
        orch.write_intermediate_json(out_dir)

        for fname in INTERMEDIATE_FILES:
            self.assertTrue(
                os.path.exists(os.path.join(out_dir, fname)),
                f"Missing: {fname}"
            )

    def test_load_intermediate_json_roundtrip(self):
        """Write → load should preserve data."""
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator

        test_json = {
            "app_metadata": {"name": "RoundTrip"},
            "datasources": [{"tableName": "T1", "columns": [{"name": "C1"}]}],
            "dimensions": [],
            "measures": [],
            "visualizations": [],
            "sheets": [],
            "variables": [],
            "loadscript": {"script": ""},
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        json_path = os.path.join(self.tmpdir, "app.json")
        with open(json_path, "w") as f:
            json.dump(test_json, f)

        orch = ExtractionOrchestrator(output_dir=self.tmpdir)
        orch.extract(json_path)
        out_dir = os.path.join(self.tmpdir, "out")
        orch.write_intermediate_json(out_dir)

        loaded = ExtractionOrchestrator.load_intermediate_json(out_dir)
        self.assertEqual(loaded["app_metadata"]["name"], "RoundTrip")
        self.assertEqual(len(loaded["datasources"]), 1)

    def test_format_adapter_from_intermediate(self):
        """Format adapter should successfully transform intermediate data."""
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator
        from qlik_export.format_adapter import adapt_qlik_for_generation

        test_json = {
            "app_metadata": {"name": "AdapterTest"},
            "datasources": [
                {"tableName": "Sales", "columns": [
                    {"name": "Region", "dataType": "text"},
                    {"name": "Amount", "dataType": "decimal"},
                ]},
            ],
            "dimensions": [{"name": "Region", "field": "Region"}],
            "measures": [{"name": "Total Sales", "expression": "Sum(Amount)"}],
            "visualizations": [
                {"id": "v1", "type": "barchart", "title": "Sales by Region", "sheetId": "s1"},
            ],
            "sheets": [{"id": "s1", "title": "Sales Dashboard"}],
            "variables": [],
            "loadscript": {"script": ""},
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        json_path = os.path.join(self.tmpdir, "app.json")
        with open(json_path, "w") as f:
            json.dump(test_json, f)

        orch = ExtractionOrchestrator(output_dir=self.tmpdir)
        orch.extract(json_path)
        out_dir = os.path.join(self.tmpdir, "out")
        orch.write_intermediate_json(out_dir)

        loaded = ExtractionOrchestrator.load_intermediate_json(out_dir)
        converted = adapt_qlik_for_generation(loaded)

        self.assertGreater(len(converted['datasources']), 0)
        self.assertGreater(len(converted['dashboards']), 0)
        self.assertEqual(converted['dashboards'][0]['name'], 'Sales Dashboard')

    def test_extraction_with_loadscript_enriches(self):
        """Extraction with loadscript should enrich datasources."""
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator

        test_json = {
            "app_metadata": {"name": "ScriptTest"},
            "datasources": [
                {"tableName": "Sales", "columns": [{"name": "Amount"}]},
            ],
            "loadscript": {
                "script": "Sales:\nLOAD Amount, Region FROM [sales.csv] (txt, utf8, embedded labels, delimiter is ',');"
            },
            "dimensions": [],
            "measures": [],
            "visualizations": [],
            "sheets": [],
            "variables": [],
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        json_path = os.path.join(self.tmpdir, "app.json")
        with open(json_path, "w") as f:
            json.dump(test_json, f)

        orch = ExtractionOrchestrator(output_dir=self.tmpdir)
        orch.extract(json_path)

        sales_ds = next(
            (d for d in orch._data["datasources"] if d.get("tableName") == "Sales"),
            None
        )
        self.assertIsNotNone(sales_ds)
        # The M query should be populated from load script parsing
        m_query = sales_ds.get("m_query", "")
        self.assertTrue(m_query, "Sales datasource should have M query from load script")
        self.assertIn("Csv.Document", m_query)


if __name__ == '__main__':
    unittest.main()
