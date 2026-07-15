"""Tests for DAX validation comment/string handling."""

from powerbi_import.dax_validator import validate_dax_expression
from powerbi_import.validator import ArtifactValidator


def test_validate_dax_ignores_block_comments_for_parentheses():
    formula = (
        "CALCULATE(COUNT('T'[Id]))\n"
        "/* legacy calc with extra close\n"
        "CALCULATE(COUNT('T'[Id])))\n"
        "*/"
    )
    issues = ArtifactValidator.validate_dax_formula(formula, context="measure X")
    assert not any("Unmatched closing parenthesis" in i for i in issues)


def test_validate_dax_ignores_source_leaks_inside_comments():
    formula = "[A] + 1 /* COUNTD([X]) */"
    issues = ArtifactValidator.validate_dax_formula(formula)
    assert not any("Source function leak" in i for i in issues)


def test_validate_dax_ignores_parentheses_inside_string_literals():
    formula = 'IF([Flag] = 1, "(", ")")'
    issues = ArtifactValidator.validate_dax_formula(formula)
    assert not any("Unmatched" in i for i in issues)


def test_openability_dax_allows_apostrophe_inside_column_identifier():
    formula = (
        "CALCULATE(COUNT('Table36'[Id]), "
        "'Table36'[Date d'analyse approfondie] = 1)"
    )

    assert validate_dax_expression(formula) == []


def test_openability_dax_does_not_treat_measure_name_as_qlik_function():
    formula = "DIVIDE([Year To Date] - [Previous Year], [Previous Year], 0)"

    assert validate_dax_expression(formula) == []


def test_openability_dax_still_rejects_qlik_function_call():
    assert 'unconverted Qlik function token detected in DAX output' in (
        validate_dax_expression('Previous([Sales])')
    )
