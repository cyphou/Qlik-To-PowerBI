"""Tests for parenthesis normalization in Qlik-to-DAX conversion."""

from qlik_export.dax_converter import convert_qlik_expression_to_dax


def test_convert_strips_unmatched_closing_parenthesis():
    expr = "Count({<A={'x'}>} ID))"
    dax = convert_qlik_expression_to_dax(expr, table_name="RecoveredModel")
    assert dax.count("(") == dax.count(")")


def test_convert_appends_missing_closing_parenthesis():
    expr = "Sum(Amount"
    dax = convert_qlik_expression_to_dax(expr, table_name="RecoveredModel")
    assert dax.count("(") == dax.count(")")
