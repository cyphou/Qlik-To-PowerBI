"""Regression tests for recovered fallback M query generation."""

from qlik_export.m_query_generator import _gen_m_sample


def test_recovered_fallback_generates_minimal_safe_query():
    ds = {
        "tableName": "RecoveredModel",
        "connection": {"type": "recovered"},
        "isRecoveredFallback": True,
        "columns": [
            {"name": "D\u00e9lai de traitement de la FEI - moins de 2 jours"},
            {"name": "=if([x]='y',1,0)"},
        ],
    }

    query = _gen_m_sample(ds)

    assert "__SyntheticKey" in query
    assert "#table(type table [__SyntheticKey = Int64.Type], {})" in query
    assert '#"Base Type" = Table.TransformColumnTypes(' in query
    assert '#"Changed Type" = Table.TransformColumnTypes(' not in query
    assert "=if([x]='y',1,0)" not in query
    assert "D\u00e9lai" not in query
