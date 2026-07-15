"""Guardrail tests for DAX-to-M conversion safety."""

from powerbi_import.tmdl_generator import _dax_to_m_expression


def test_dax_to_m_rejects_qlik_dollar_sign_variables():
    expr = "'CA Total Réel '&$(LastMonth)&'('&[Periode]&')'"
    assert _dax_to_m_expression(expr, "RecoveredModel") is None


def test_dax_to_m_rejects_single_quoted_literals():
    expr = "'texte non valide en M'"
    assert _dax_to_m_expression(expr, "RecoveredModel") is None


def test_dax_to_m_accepts_safe_column_comparison():
    expr = "[HFEIF_ID_FEI] > 0"
    assert _dax_to_m_expression(expr, "RecoveredModel") == "[HFEIF_ID_FEI] > 0"
