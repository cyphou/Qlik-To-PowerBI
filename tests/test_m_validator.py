import pytest

from powerbi_import.m_validator import validate_m_query
from powerbi_import.tmdl_generator import _safe_empty_m_query


def _query(expression):
    return (
        'let\n'
        f'    Added = Table.AddColumn(Source, "Value", each {expression})\n'
        'in\n'
        '    Added'
    )


@pytest.mark.parametrize(
    'expression',
    [
        "if([Flag] = 1, 'Oui', 'Non')",
        '= null("Date de cloture")',
        'text([Id])',
        'Exists("Id service")',
        '[Valide] = 1 AND [Id service] <> null',
        '*',
        '[[Calendar_Prec]]',
        '["Id FEI"]',
        'Date.From([TempDate], "YYYYMM")',
    ],
)
def test_rejects_desktop_invalid_generated_expressions(expression):
    assert validate_m_query(_query(expression))


def test_accepts_valid_m_conditional():
    query = _query('if [Flag] = 1 then "Oui" else "Non"')
    assert validate_m_query(query) == []


def test_safe_empty_query_preserves_names_and_types():
    query = _safe_empty_m_query([
        {'name': 'Id FEI', 'datatype': 'int64'},
        {'name': "Date d'analyse", 'datatype': 'date'},
        {'name': 'Horodatage', 'datatype': 'datetime'},
        {'name': 'Texte "public"', 'datatype': 'string'},
    ])

    assert '#"Id FEI" = number' in query
    assert '#"Date d\'analyse" = date' in query
    assert '#"Horodatage" = datetime' in query
    assert '#"Texte ""public""" = text' in query
    assert validate_m_query(query) == []


def test_rejects_qlik_alias_used_as_m_type_identifier():
    query = _query('"ID Utilisé Pour Lien" as HFEIF_ID_GRAVITE')

    issues = validate_m_query(query)

    assert any('invalid M type identifier' in issue for issue in issues)


def test_rejects_extended_type_value_inside_structured_type():
    query = 'let\n    Source = #table(type table [Id = Int64.Type], {})\nin\n    Source'

    issues = validate_m_query(query)

    assert any('inside type table declaration' in issue for issue in issues)