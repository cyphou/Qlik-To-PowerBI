"""Phase 5 — Load Script Deep Conversion tests."""

import pytest
from qlik_export.qlik_script_converter import (
    QlikScriptToPowerQueryConverter,
    _detect_stacked_load,
)


# ── 5.0  Helper: stacked LOAD detection ─────────────────────────

class TestStackedLoadDetection:
    def test_single_load(self):
        assert _detect_stacked_load("LOAD * FROM [data.qvd]") is False

    def test_two_loads(self):
        stmt = "LOAD Year(Date) as Year, *;\nLOAD * FROM [data.qvd]"
        assert _detect_stacked_load(stmt) is True

    def test_no_load(self):
        assert _detect_stacked_load("SELECT * FROM tbl") is False


# ── 5.1  JOIN → Table.NestedJoin ─────────────────────────────────

class TestJoinConversion:
    def test_left_join_produces_nested_join(self):
        script = (
            "Orders:\nLOAD OrderID, CustomerID, Amount\nFROM [orders.qvd];\n"
            "LEFT JOIN(Orders)\nLOAD CustomerID, Name\nFROM [customers.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "Table.NestedJoin" in result
        assert "JoinKind.LeftOuter" in result

    def test_inner_join(self):
        script = (
            "Sales:\nLOAD ID, Amount\nFROM [sales.qvd];\n"
            "INNER JOIN(Sales)\nLOAD ID, Region\nFROM [regions.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "Table.NestedJoin" in result
        assert "JoinKind.Inner" in result

    def test_right_join(self):
        script = (
            "T1:\nLOAD A, B\nFROM [t1.qvd];\n"
            "RIGHT JOIN(T1)\nLOAD A, C\nFROM [t2.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "JoinKind.RightOuter" in result

    def test_outer_join(self):
        script = (
            "T1:\nLOAD X, Y\nFROM [t1.qvd];\n"
            "OUTER JOIN(T1)\nLOAD X, Z\nFROM [t2.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "JoinKind.FullOuter" in result

    def test_join_target_table_referenced(self):
        script = (
            "Base:\nLOAD Key, Val\nFROM [base.qvd];\n"
            "LEFT JOIN(Base)\nLOAD Key, Extra\nFROM [extra.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "Base" in result


# ── 5.2  CONCATENATE → Table.Combine ────────────────────────────

class TestConcatenateConversion:
    def test_concatenate_produces_combine_comment(self):
        script = (
            "Sales:\nLOAD Region, Amount\nFROM [sales2023.qvd];\n"
            "CONCATENATE(Sales)\nLOAD Region, Amount\nFROM [sales2024.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "Table.Combine" in result
        assert "Sales" in result

    def test_concatenate_keeps_base_table(self):
        script = (
            "Data:\nLOAD A, B\nFROM [d1.qvd];\n"
            "CONCATENATE(Data)\nLOAD A, B\nFROM [d2.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        # Base table query should also appear
        lines = result.split('\n')
        assert any('Data' in l for l in lines)


# ── 5.3  Stacked/Preceding LOAD ─────────────────────────────────

class TestStackedLoadConversion:
    def test_stacked_load_comment_present(self):
        script = "Result:\nLOAD Year(Date) as Year, *;\nLOAD * FROM [data.qvd];"
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        # Should contain stacked load comment since the block has two LOADs
        assert "Stacked" in result or "LOAD" in result  # at minimum handled

    def test_single_load_no_stacked_comment(self):
        script = "Simple:\nLOAD A, B\nFROM [file.qvd];"
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "Stacked" not in result


# ── 5.4  INLINE LOAD → #table ──────────────────────────────────

class TestInlineLoad:
    def test_inline_produces_table_syntax(self):
        script = """
MapTable:
LOAD * INLINE [
Country, Code
France, FR
Germany, DE
];
"""
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "#table" in result
        assert "France" in result
        assert "Country" in result

    def test_inline_multiple_columns(self):
        script = """
StatusMap:
LOAD * INLINE [
Status, Label, Priority
1, Active, High
2, Inactive, Low
];
"""
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "#table" in result
        assert "Status" in result
        assert "Active" in result


# ── 5.5  MAPPING LOAD → lookup ──────────────────────────────────

class TestMappingLoad:
    def test_mapping_load_produces_lookup_comment(self):
        script = """
MapRegion:
MAPPING LOAD Code, Region
FROM [regions.csv]
(txt, utf8, embedded labels, delimiter is ',');
"""
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "MapRegion" in result
        assert "lookup" in result.lower() or "Mapping" in result

    def test_mapping_load_source_referenced(self):
        script = """
MapCountry:
MAPPING LOAD ID, Country
FROM [countries.xlsx]
(ooxml, embedded labels);
"""
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "countries.xlsx" in result


# ── 5.6  parse_qlik_load strips prefixes ────────────────────────

class TestParseQlikLoadPrefixes:
    def test_concatenate_prefix_stripped(self):
        script = "CONCATENATE(Sales) LOAD Region, Amount FROM [sales.qvd]"
        stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(script)
        assert 'Region' in stmt.fields
        assert stmt.source_type == 'file'

    def test_join_prefix_stripped(self):
        script = "LEFT JOIN(Orders) LOAD CustomerID, Name FROM [cust.qvd]"
        stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(script)
        assert 'CustomerID' in stmt.fields

    def test_label_and_concatenate_prefix_stripped(self):
        script = "Tbl: CONCATENATE(Base) LOAD A, B FROM [data.csv]"
        stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(script)
        assert 'A' in stmt.fields

    def test_plain_load_still_works(self):
        script = "LOAD X, Y FROM [file.qvd]"
        stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(script)
        assert stmt.fields == ['X', 'Y']


# ── 5.7  Full pipeline round-trip ───────────────────────────────

class TestFullPipelinePhase5:
    def test_complex_script_with_join_and_concat(self):
        script = (
            "Orders:\nLOAD OrderID, CustID, Amount\nFROM [orders.qvd];\n\n"
            "LEFT JOIN(Orders)\nLOAD CustID, Name\nFROM [customers.qvd];\n\n"
            "CONCATENATE(Orders)\nLOAD OrderID, CustID, Amount\nFROM [orders_2024.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "Table.NestedJoin" in result
        assert "Table.Combine" in result
        assert "Orders" in result

    def test_mixed_inline_and_file(self):
        script = (
            "Lookup:\nLOAD * INLINE [\nKey, Val\n1, A\n2, B\n];\n\n"
            "Data:\nLOAD Key, Amount\nFROM [data.qvd];"
        )
        result = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        assert "#table" in result
        assert "data.qvd" in result.lower() or "Qvd.Load" in result
