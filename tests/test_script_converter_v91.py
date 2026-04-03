"""Tests for v9.1 load script converter enhancements in qlik_export.qlik_script_converter.

Covers:
- MAPPING LOAD → M lookup table with Key/Value rename
- ApplyMap('MapName', Field, Default) → try/otherwise M expression
- CROSSTABLE(Attr, Data, N) LOAD ... → Table.UnpivotOtherColumns
- GENERIC LOAD Key, Attr, Value FROM ... → Table.Pivot
- HIERARCHY(NodeID, ParentID, ...) → Self-join with path construction
- INTERVALMATCH(DateField) LOAD Start, End FROM ... → range match
"""

import unittest
from qlik_export.qlik_script_converter import (
    QlikScriptToPowerQueryConverter,
)


# ═══════════════════════════════════════════════════════════════
#  MAPPING LOAD → lookup table with Key/Value rename
# ═══════════════════════════════════════════════════════════════

class TestMappingLoad(unittest.TestCase):
    def test_basic_mapping_load(self):
        script = (
            "StatusMap:\n"
            "MAPPING LOAD StatusCode, StatusDesc\n"
            "FROM [data/statuses.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("StatusMap", result)
        self.assertIn("Mapping table", result)
        self.assertIn("Csv.Document", result)
        self.assertIn("RenamedCols", result)
        self.assertIn('"Key"', result)
        self.assertIn('"Value"', result)

    def test_mapping_load_key_value_rename(self):
        script = (
            "RegionMap:\n"
            "MAPPING LOAD RegionID, RegionName\n"
            "FROM [regions.xlsx];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        # Should rename original columns to Key/Value
        self.assertIn('"RegionID"', result)
        self.assertIn('"RegionName"', result)
        self.assertIn("Table.RenameColumns", result)

    def test_mapping_load_excel_source(self):
        script = (
            "ProdMap:\n"
            "MAPPING LOAD ProdCode, ProdName\n"
            "FROM [products.xlsx];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Excel.Workbook", result)

    def test_mapping_load_csv_source(self):
        script = (
            "CityMap:\n"
            "MAPPING LOAD CityCode, CityName\n"
            "FROM [cities.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Csv.Document", result)

    def test_mapping_load_usage_comment(self):
        script = (
            "LookupMap:\n"
            "MAPPING LOAD ID, Name\n"
            "FROM [lookup.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        # Should include a usage hint comment
        self.assertIn("Usage:", result)
        self.assertIn("try", result)
        self.assertIn("otherwise", result)


# ═══════════════════════════════════════════════════════════════
#  ApplyMap → try/otherwise M expression
# ═══════════════════════════════════════════════════════════════

class TestApplyMap(unittest.TestCase):
    def test_applymap_function_conversion(self):
        expr = "ApplyMap('StatusMap', [StatusCode], 'Unknown')"
        result = QlikScriptToPowerQueryConverter.convert_qlik_function(expr)
        self.assertIn("try", result)
        self.assertIn("otherwise", result)
        self.assertIn("StatusMap", result)
        self.assertIn("StatusCode", result)

    def test_applymap_with_default(self):
        expr = "ApplyMap('RegionLookup', Region, 'N/A')"
        result = QlikScriptToPowerQueryConverter.convert_qlik_function(expr)
        self.assertIn("try", result)
        self.assertIn("otherwise", result)

    def test_applymap_without_default(self):
        expr = "ApplyMap('CatMap', Category)"
        result = QlikScriptToPowerQueryConverter.convert_qlik_function(expr)
        self.assertIn("try", result)
        self.assertIn("otherwise", result)
        self.assertIn("null", result)

    def test_applymap_key_value_structure(self):
        expr = "ApplyMap('MyMap', [Field], 'default')"
        result = QlikScriptToPowerQueryConverter.convert_qlik_function(expr)
        self.assertIn("[Key=", result)
        self.assertIn("[Value]", result)

    def test_applymap_in_load_script(self):
        script = (
            "Result:\n"
            "LOAD *, ApplyMap('StatusMap', StatusCode, 'Unknown') as StatusName\n"
            "FROM [data.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("try", result)
        self.assertIn("StatusMap", result)


# ═══════════════════════════════════════════════════════════════
#  CROSSTABLE → Table.UnpivotOtherColumns
# ═══════════════════════════════════════════════════════════════

class TestCrosstable(unittest.TestCase):
    def test_basic_crosstable(self):
        script = (
            "Sales:\n"
            "CROSSTABLE(Month, Amount, 1)\n"
            "LOAD Product, Jan, Feb, Mar\n"
            "FROM [sales.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Unpivot", result)
        self.assertIn("Table.UnpivotOtherColumns", result)
        self.assertIn('"Month"', result)
        self.assertIn('"Amount"', result)

    def test_crosstable_qualifier_column(self):
        script = (
            "Data:\n"
            "CROSSTABLE(Attribute, Value, 1)\n"
            "LOAD Region, Q1, Q2, Q3, Q4\n"
            "FROM [quarterly.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        # First column (Region) should be preserved
        self.assertIn('"Region"', result)

    def test_crosstable_csv_source(self):
        script = (
            "Metrics:\n"
            "CROSSTABLE(Year, Sales, 1)\n"
            "LOAD Product, 2020, 2021, 2022\n"
            "FROM [metrics.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Csv.Document", result)

    def test_crosstable_excel_source(self):
        script = (
            "Report:\n"
            "CROSSTABLE(Period, Val, 1)\n"
            "LOAD Item, P1, P2\n"
            "FROM [report.xlsx];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Excel.Workbook", result)

    def test_crosstable_comment_header(self):
        script = (
            "CT:\n"
            "CROSSTABLE(Attr, Data, 1)\n"
            "LOAD Key, A, B, C\n"
            "FROM [ct.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("CROSSTABLE", result)


# ═══════════════════════════════════════════════════════════════
#  GENERIC LOAD → Table.Pivot
# ═══════════════════════════════════════════════════════════════

class TestGenericLoad(unittest.TestCase):
    def test_basic_generic(self):
        script = (
            "DeviceData:\n"
            "GENERIC LOAD DeviceID, AttributeName, AttributeValue\n"
            "FROM [device_attrs.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Table.Pivot", result)
        self.assertIn("DeviceData", result)

    def test_generic_pivot_columns(self):
        script = (
            "Sensors:\n"
            "GENERIC LOAD SensorId, Metric, Reading\n"
            "FROM [sensors.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn('"Metric"', result)
        self.assertIn('"Reading"', result)

    def test_generic_list_distinct(self):
        script = (
            "Props:\n"
            "GENERIC LOAD ID, PropName, PropVal\n"
            "FROM [props.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("List.Distinct", result)

    def test_generic_comment(self):
        script = (
            "T:\n"
            "GENERIC LOAD K, A, V\n"
            "FROM [t.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("GENERIC LOAD", result)


# ═══════════════════════════════════════════════════════════════
#  HIERARCHY → Self-join with path construction
# ═══════════════════════════════════════════════════════════════

class TestHierarchy(unittest.TestCase):
    def test_basic_hierarchy(self):
        script = (
            "OrgChart:\n"
            "LOAD EmployeeID, ManagerID, EmployeeName\n"
            "FROM [employees.csv];\n"
            "\n"
            "HIERARCHY(EmployeeID, ManagerID, EmployeeName, HierName, PathName)\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("HIERARCHY", result)
        self.assertIn("Table.NestedJoin", result)
        self.assertIn("EmployeeID", result)
        self.assertIn("ManagerID", result)

    def test_hierarchy_path_construction(self):
        script = "HIERARCHY(NodeID, ParentID, NodeLabel, HierLabel, FullPath)\n"
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("FullPath", result)
        self.assertIn("Text.Combine", result)

    def test_hierarchy_default_separator(self):
        script = "HIERARCHY(ID, PID, Name, HName, Path)\n"
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        # Default separator is /
        self.assertIn("/", result)

    def test_hierarchy_custom_separator(self):
        script = "HIERARCHY(ID, PID, Name, HName, Path, '|')\n"
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("|", result)

    def test_hierarchy_self_join(self):
        script = "HIERARCHY(NodeID, ParentID, NodeName, HierName, PathName)\n"
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("NestedJoin", result)
        self.assertIn("LeftOuter", result)

    def test_hierarchy_grandparent_expansion(self):
        script = "HIERARCHY(ID, PID, Name, HN, Path)\n"
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("GrandParent", result)
        self.assertIn("ParentData", result)


# ═══════════════════════════════════════════════════════════════
#  INTERVALMATCH → range match
# ═══════════════════════════════════════════════════════════════

class TestIntervalMatch(unittest.TestCase):
    def test_basic_intervalmatch(self):
        script = (
            "INTERVALMATCH(OrderDate)\n"
            "LOAD StartDate, EndDate\n"
            "FROM [periods.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("INTERVALMATCH", result)
        self.assertIn("OrderDate", result)
        self.assertIn("StartDate", result)
        self.assertIn("EndDate", result)

    def test_intervalmatch_range_filter(self):
        script = (
            "INTERVALMATCH(TransDate)\n"
            "LOAD FromDate, ToDate\n"
            "FROM [ranges.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Table.SelectRows", result)
        self.assertIn("<=", result)
        self.assertIn(">=", result)

    def test_intervalmatch_expand(self):
        script = (
            "INTERVALMATCH(EventDate)\n"
            "LOAD LowDate, HighDate\n"
            "FROM [intervals.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Table.ExpandTableColumn", result)

    def test_intervalmatch_extra_fields(self):
        script = (
            "INTERVALMATCH(Date)\n"
            "LOAD StartDate, EndDate, RateType\n"
            "FROM [rates.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("RateType", result)

    def test_intervalmatch_resident_source(self):
        script = (
            "INTERVALMATCH(OrderDate)\n"
            "LOAD LowDate, HighDate\n"
            "RESIDENT IntervalTable;\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("IntervalTable", result)

    def test_intervalmatch_csv_source(self):
        script = (
            "INTERVALMATCH(Date)\n"
            "LOAD Start, End\n"
            "FROM [dates.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIn("Csv.Document", result)


# ═══════════════════════════════════════════════════════════════
#  Edge cases and combined scenarios
# ═══════════════════════════════════════════════════════════════

class TestScriptConverterEdgeCases(unittest.TestCase):
    def test_empty_script(self):
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery("")
        self.assertIsNotNone(result)

    def test_script_with_variables(self):
        script = (
            "SET vYear = 2024;\n"
            "LET vThreshold = 100;\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIsNotNone(result)

    def test_script_with_qualify(self):
        script = (
            "QUALIFY *;\n"
            "UNQUALIFY *;\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        self.assertIsNotNone(result)

    def test_script_with_mixed_constructs(self):
        script = (
            "SET vYear = 2024;\n"
            "\n"
            "StatusMap:\n"
            "MAPPING LOAD Code, Desc\n"
            "FROM [statuses.csv];\n"
            "\n"
            "Sales:\n"
            "LOAD Product, Amount\n"
            "FROM [sales.csv];\n"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        # Should have mapping table output
        self.assertIn("StatusMap", result)
        self.assertIn("Mapping table", result)


if __name__ == "__main__":
    unittest.main()
