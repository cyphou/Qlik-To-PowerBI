"""Tests for qlik_export.datasource_extractor — bridge/adapter module.

Covers:
- map_to_powerbi_type (17 type mappings + edge cases)
- convert_formula_to_dax (delegation to dax_converter)
- generate_power_query_m (delegation to m_query_generator)
- Deprecated aliases (DeprecationWarning)
"""

import warnings
import pytest
from qlik_export.datasource_extractor import (
    map_to_powerbi_type,
    map_qlik_to_powerbi_type,
    convert_formula_to_dax,
    convert_qlik_expression_to_dax,
    generate_power_query_m,
)


# ═══════════════════════════════════════════════════════════════
#  map_to_powerbi_type
# ═══════════════════════════════════════════════════════════════

class TestMapToPowerBiType:
    @pytest.mark.parametrize("qlik,expected", [
        ("text", "String"),
        ("string", "String"),
        ("num", "Double"),
        ("number", "Double"),
        ("numeric", "Double"),
        ("real", "Double"),
        ("integer", "Int64"),
        ("int", "Int64"),
        ("money", "Decimal"),
        ("currency", "Decimal"),
        ("date", "DateTime"),
        ("timestamp", "DateTime"),
        ("datetime", "DateTime"),
        ("time", "DateTime"),
        ("boolean", "Boolean"),
        ("dual", "String"),
    ])
    def test_known_types(self, qlik, expected):
        assert map_to_powerbi_type(qlik) == expected

    def test_unknown_type(self):
        assert map_to_powerbi_type("blob") == "String"

    def test_empty_string(self):
        assert map_to_powerbi_type("") == "String"

    def test_none(self):
        assert map_to_powerbi_type(None) == "String"

    def test_case_insensitive(self):
        # Should handle mixed case
        result = map_to_powerbi_type("TEXT")
        assert result == "String"

    def test_alias_same_result(self):
        assert map_qlik_to_powerbi_type("integer") == map_to_powerbi_type("integer")


# ═══════════════════════════════════════════════════════════════
#  convert_formula_to_dax
# ═══════════════════════════════════════════════════════════════

class TestConvertFormulaToDax:
    def test_simple_expression(self):
        result = convert_formula_to_dax("Sum(Amount)", "TotalAmount", "Sales")
        assert "SUM(" in result

    def test_empty_formula(self):
        result = convert_formula_to_dax("", "Col", "Table")
        assert result == ""

    def test_none_formula(self):
        result = convert_formula_to_dax(None, "Col", "Table")
        assert result == "" or result is None

    def test_whitespace_formula(self):
        result = convert_formula_to_dax("   ", "Col", "Table")
        assert isinstance(result, str)

    def test_with_calc_map(self):
        result = convert_formula_to_dax("Sum(Sales)", "Total", "T",
                                         calc_map={"Total": "SUM('T'[Sales])"})
        assert isinstance(result, str)

    def test_alias_same_result(self):
        r1 = convert_formula_to_dax("Sum(X)", "C", "T")
        r2 = convert_qlik_expression_to_dax("Sum(X)", "C", "T")
        assert r1 == r2


# ═══════════════════════════════════════════════════════════════
#  generate_power_query_m
# ═══════════════════════════════════════════════════════════════

class TestGeneratePowerQueryM:
    def test_csv_connection(self):
        conn = {"connectionType": "csv", "path": "data.csv"}
        result = generate_power_query_m(conn, {"name": "Orders", "columns": []})
        assert "let" in result.lower()

    def test_sql_server_connection(self):
        conn = {"connectionType": "sqlserver", "server": "srv", "database": "db"}
        result = generate_power_query_m(conn, {"name": "Orders", "columns": []})
        assert "Sql.Database" in result

    def test_table_as_string(self):
        conn = {"connectionType": "csv", "path": "data.csv"}
        result = generate_power_query_m(conn, "Orders")
        assert isinstance(result, str)

    def test_empty_connection(self):
        result = generate_power_query_m({}, {})
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════
#  Deprecated Aliases
# ═══════════════════════════════════════════════════════════════

class TestDeprecatedAliases:
    def test_map_tableau_warns(self):
        try:
            from qlik_export.datasource_extractor import map_tableau_to_powerbi_type
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                map_tableau_to_powerbi_type("text")
                assert any("deprecated" in str(warning.message).lower() or
                           "Deprecated" in str(warning.category.__name__)
                           for warning in w)
        except ImportError:
            pytest.skip("map_tableau_to_powerbi_type not available")

    def test_convert_tableau_warns(self):
        try:
            from qlik_export.datasource_extractor import convert_tableau_formula_to_dax
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                convert_tableau_formula_to_dax("Sum(X)", "C", "T")
                assert any("deprecated" in str(warning.message).lower() or
                           "Deprecated" in str(warning.category.__name__)
                           for warning in w)
        except ImportError:
            pytest.skip("convert_tableau_formula_to_dax not available")
