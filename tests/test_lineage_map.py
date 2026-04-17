"""Tests for powerbi_import.lineage_map — source-to-target provenance tracking."""

import json
import os
import tempfile
import unittest

from powerbi_import.lineage_map import LineageEntry, LineageMap, build_lineage_map


class TestLineageEntry(unittest.TestCase):
    """Unit tests for LineageEntry data class."""

    def test_basic_to_dict(self):
        entry = LineageEntry("measure", "Sales", "dax_measure", "Sales")
        d = entry.to_dict()
        self.assertEqual(d["source_type"], "measure")
        self.assertEqual(d["source_name"], "Sales")
        self.assertEqual(d["target_type"], "dax_measure")
        self.assertEqual(d["target_name"], "Sales")
        self.assertEqual(d["status"], "exact")

    def test_optional_fields_excluded_when_empty(self):
        entry = LineageEntry("measure", "M", "dax_measure", "M")
        d = entry.to_dict()
        self.assertNotIn("source_expression", d)
        self.assertNotIn("target_expression", d)
        self.assertNotIn("notes", d)

    def test_optional_fields_included_when_set(self):
        entry = LineageEntry(
            "measure", "M", "dax_measure", "M",
            source_expression="Sum(Sales)",
            target_expression="SUM('Table'[Sales])",
            notes="auto-converted",
        )
        d = entry.to_dict()
        self.assertEqual(d["source_expression"], "Sum(Sales)")
        self.assertEqual(d["target_expression"], "SUM('Table'[Sales])")
        self.assertEqual(d["notes"], "auto-converted")

    def test_status_values(self):
        for status in ("exact", "approximate", "unsupported"):
            entry = LineageEntry("x", "y", "a", "b", status=status)
            self.assertEqual(entry.to_dict()["status"], status)


class TestLineageMap(unittest.TestCase):
    """Unit tests for LineageMap collection and export."""

    def test_add_and_count(self):
        lm = LineageMap("TestApp")
        lm.add("measure", "M1", "dax_measure", "M1")
        lm.add("dimension", "D1", "column", "D1")
        self.assertEqual(len(lm.entries), 2)

    def test_add_datasource(self):
        lm = LineageMap()
        lm.add_datasource("Orders", "Orders")
        self.assertEqual(lm.entries[0].source_type, "datasource")
        self.assertEqual(lm.entries[0].target_type, "table")

    def test_add_measure(self):
        lm = LineageMap()
        lm.add_measure("Revenue", "Revenue", qlik_expr="Sum(Amount)", dax_expr="SUM('T'[Amount])")
        e = lm.entries[0]
        self.assertEqual(e.source_type, "measure")
        self.assertEqual(e.target_type, "dax_measure")
        self.assertEqual(e.source_expression, "Sum(Amount)")
        self.assertEqual(e.target_expression, "SUM('T'[Amount])")

    def test_add_dimension(self):
        lm = LineageMap()
        lm.add_dimension("Region", "Region", target_type="column")
        self.assertEqual(lm.entries[0].target_type, "column")

    def test_add_dimension_hierarchy(self):
        lm = LineageMap()
        lm.add_dimension("DateHier", "DateHier", target_type="hierarchy")
        self.assertEqual(lm.entries[0].target_type, "hierarchy")

    def test_add_variable(self):
        lm = LineageMap()
        lm.add_variable("vThreshold", "vThreshold")
        self.assertEqual(lm.entries[0].source_type, "variable")
        self.assertEqual(lm.entries[0].target_type, "parameter")

    def test_add_visual(self):
        lm = LineageMap()
        lm.add_visual("Sales Chart", "barchart → visual")
        self.assertEqual(lm.entries[0].source_type, "visualization")
        self.assertEqual(lm.entries[0].target_type, "visual")

    def test_add_sheet(self):
        lm = LineageMap()
        lm.add_sheet("Dashboard", "Dashboard")
        self.assertEqual(lm.entries[0].source_type, "sheet")
        self.assertEqual(lm.entries[0].target_type, "report_page")

    def test_add_association(self):
        lm = LineageMap()
        lm.add_association("Orders.ID → Customers.ID", "Orders.ID → Customers.ID")
        self.assertEqual(lm.entries[0].source_type, "association")
        self.assertEqual(lm.entries[0].target_type, "relationship")

    def test_add_bookmark(self):
        lm = LineageMap()
        lm.add_bookmark("BM1", "BM1")
        self.assertEqual(lm.entries[0].source_type, "bookmark")
        self.assertEqual(lm.entries[0].target_type, "pbi_bookmark")

    def test_to_dict_structure(self):
        lm = LineageMap("App1")
        lm.add_datasource("T1", "T1")
        lm.add_measure("M1", "M1")
        d = lm.to_dict()
        self.assertEqual(d["app_name"], "App1")
        self.assertEqual(d["total_entries"], 2)
        self.assertIn("datasource", d["by_source_type"])
        self.assertIn("measure", d["by_source_type"])
        self.assertEqual(len(d["entries"]), 2)

    def test_save_creates_file(self):
        lm = LineageMap("SaveTest")
        lm.add_datasource("T1", "T1")
        with tempfile.TemporaryDirectory() as td:
            path = lm.save(td)
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(path.endswith("lineage_map.json"))
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["app_name"], "SaveTest")
            self.assertEqual(data["total_entries"], 1)

    def test_save_creates_subdirectory(self):
        lm = LineageMap("SubDirTest")
        with tempfile.TemporaryDirectory() as td:
            sub = os.path.join(td, "nested", "dir")
            path = lm.save(sub)
            self.assertTrue(os.path.isfile(path))


class TestBuildLineageMap(unittest.TestCase):
    """Tests for the build_lineage_map factory function."""

    def _make_qlik_data(self, **kwargs):
        defaults = {
            "datasources": [],
            "measures": [],
            "dimensions": [],
            "variables": [],
            "visualizations": [],
            "sheets": [],
            "associations": [],
            "bookmarks": [],
        }
        defaults.update(kwargs)
        return defaults

    def test_empty_data(self):
        lm = build_lineage_map("Empty", self._make_qlik_data())
        self.assertEqual(lm.app_name, "Empty")
        self.assertEqual(len(lm.entries), 0)

    def test_datasources(self):
        data = self._make_qlik_data(datasources=[
            {"name": "Orders"},
            {"tableName": "Products"},
        ])
        lm = build_lineage_map("DS", data)
        ds_entries = [e for e in lm.entries if e.source_type == "datasource"]
        self.assertEqual(len(ds_entries), 2)

    def test_measures(self):
        data = self._make_qlik_data(measures=[
            {"name": "Revenue", "expression": "Sum(Amount)"},
            {"label": "Count", "expression": "Count(ID)"},
        ])
        lm = build_lineage_map("Meas", data)
        m_entries = [e for e in lm.entries if e.source_type == "measure"]
        self.assertEqual(len(m_entries), 2)
        self.assertEqual(m_entries[0].source_expression, "Sum(Amount)")

    def test_measures_with_calc_map(self):
        data = self._make_qlik_data(measures=[
            {"name": "Revenue", "expression": "Sum(Amount)"},
        ])
        calc_map = {"Revenue": "SUM('Sales'[Amount])"}
        lm = build_lineage_map("CalcMap", data, calc_map=calc_map)
        m = [e for e in lm.entries if e.source_type == "measure"][0]
        self.assertEqual(m.target_expression, "SUM('Sales'[Amount])")

    def test_dimensions_column(self):
        data = self._make_qlik_data(dimensions=[
            {"name": "Region", "field": "RegionField"},
        ])
        lm = build_lineage_map("Dim", data)
        d = lm.entries[0]
        self.assertEqual(d.target_type, "column")
        self.assertEqual(d.source_expression, "RegionField")

    def test_dimensions_drill_group(self):
        data = self._make_qlik_data(dimensions=[
            {"name": "DateDrill", "field": "Date", "type": "drill-group"},
        ])
        lm = build_lineage_map("Drill", data)
        self.assertEqual(lm.entries[0].target_type, "hierarchy")

    def test_dimensions_isDrillDown(self):
        data = self._make_qlik_data(dimensions=[
            {"name": "Geo", "field": "City", "isDrillDown": True},
        ])
        lm = build_lineage_map("DrillDown", data)
        self.assertEqual(lm.entries[0].target_type, "hierarchy")

    def test_variables_excluded_dollar(self):
        data = self._make_qlik_data(variables=[
            {"name": "vThreshold"},
            {"name": "$Hidden"},
        ])
        lm = build_lineage_map("Vars", data)
        v_entries = [e for e in lm.entries if e.source_type == "variable"]
        self.assertEqual(len(v_entries), 1)
        self.assertEqual(v_entries[0].source_name, "vThreshold")

    def test_visualizations(self):
        data = self._make_qlik_data(visualizations=[
            {"title": "Sales Chart", "type": "barchart"},
        ])
        lm = build_lineage_map("Viz", data)
        self.assertEqual(lm.entries[0].source_type, "visualization")
        self.assertIn("barchart", lm.entries[0].target_name)

    def test_sheets(self):
        data = self._make_qlik_data(sheets=[
            {"title": "Overview"},
            {"name": "Detail"},
        ])
        lm = build_lineage_map("Sheets", data)
        s = [e for e in lm.entries if e.source_type == "sheet"]
        self.assertEqual(len(s), 2)

    def test_associations(self):
        data = self._make_qlik_data(associations=[
            {"table1": "Orders", "table2": "Customers", "field": "CustID"},
        ])
        lm = build_lineage_map("Assoc", data)
        a = lm.entries[0]
        self.assertIn("Orders", a.source_name)
        self.assertIn("Customers", a.source_name)

    def test_bookmarks(self):
        data = self._make_qlik_data(bookmarks=[
            {"name": "BM1"},
            {"title": "BM2"},
        ])
        lm = build_lineage_map("Bookmarks", data)
        bm = [e for e in lm.entries if e.source_type == "bookmark"]
        self.assertEqual(len(bm), 2)

    def test_full_app(self):
        """Comprehensive test with all object types."""
        data = self._make_qlik_data(
            datasources=[{"name": "Sales"}, {"name": "Products"}],
            measures=[{"name": "Revenue", "expression": "Sum(Amount)"}],
            dimensions=[{"name": "Region", "field": "R"}],
            variables=[{"name": "vYear"}],
            visualizations=[{"title": "Chart", "type": "barchart"}],
            sheets=[{"title": "Dashboard"}],
            associations=[{"table1": "Sales", "table2": "Products", "field": "ProdID"}],
            bookmarks=[{"name": "DefaultView"}],
        )
        lm = build_lineage_map("FullApp", data)
        d = lm.to_dict()
        self.assertGreaterEqual(d["total_entries"], 8)
        self.assertGreaterEqual(len(d["by_source_type"]), 7)  # 7+ unique source types


if __name__ == "__main__":
    unittest.main()
