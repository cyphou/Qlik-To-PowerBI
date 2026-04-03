"""
Shared constants for Fabric artifact generators.

Centralises type maps, artifact lists, and regex patterns used by
lakehouse, dataflow, notebook, pipeline, and semantic model generators.
"""

from __future__ import annotations

import re

# ── Fabric artifact types ──────────────────────────────────────────

FABRIC_ARTIFACTS: list[str] = [
    'lakehouse', 'dataflow', 'notebook',
    'semanticmodel', 'pipeline',
]

# ── Qlik → Spark SQL type mapping ──────────────────────────────

SPARK_TYPE_MAP: dict[str, str] = {
    'string':     'STRING',
    'integer':    'INT',
    'int64':      'BIGINT',
    'real':       'DOUBLE',
    'double':     'DOUBLE',
    'number':     'DOUBLE',
    'boolean':    'BOOLEAN',
    'date':       'DATE',
    'datetime':   'TIMESTAMP',
    'time':       'STRING',
    'spatial':    'STRING',
    'binary':     'BINARY',
    'currency':   'DECIMAL(19,4)',
    'percentage': 'DOUBLE',
}


def map_to_spark_type(Qlik_type: str) -> str:
    """Map a Qlik data type string to the corresponding Spark SQL type."""
    return SPARK_TYPE_MAP.get(Qlik_type.lower(), 'STRING')


# ── PySpark StructType wrappers ────────────────────────────────────

PYSPARK_TYPE_MAP: dict[str, str] = {
    'string':     'StringType()',
    'integer':    'IntegerType()',
    'int64':      'LongType()',
    'real':       'DoubleType()',
    'double':     'DoubleType()',
    'number':     'DoubleType()',
    'boolean':    'BooleanType()',
    'date':       'DateType()',
    'datetime':   'TimestampType()',
    'time':       'StringType()',
    'spatial':    'StringType()',
    'binary':     'BinaryType()',
    'currency':   'DecimalType(19, 4)',
    'percentage': 'DoubleType()',
}

# ── Aggregation detection ──────────────────────────────────────────

AGG_PATTERN = re.compile(
    r'\b(SUM|COUNT|COUNTA|COUNTD|COUNTROWS|AVERAGE|AVG|MIN|MAX|MEDIAN|'
    r'STDEV|STDEVP|VAR|VARP|PERCENTILE|DISTINCTCOUNT|CALCULATE|'
    r'TOTALYTD|SAMEPERIODLASTYEAR|RANKX|SUMX|AVERAGEX|MINX|MAXX|COUNTX|'
    r'CORR|COVAR|COVARP|'
    r'RUNNING_SUM|RUNNING_AVG|RUNNING_COUNT|RUNNING_MAX|RUNNING_MIN|'
    r'WINDOW_SUM|WINDOW_AVG|WINDOW_MAX|WINDOW_MIN|WINDOW_COUNT|'
    r'WINDOW_MEDIAN|WINDOW_STDEV|WINDOW_STDEVP|WINDOW_VAR|WINDOW_VARP|'
    r'WINDOW_CORR|WINDOW_COVAR|WINDOW_COVARP|WINDOW_PERCENTILE|'
    r'RANK|RANK_UNIQUE|RANK_DENSE|RANK_MODIFIED|RANK_PERCENTILE|'
    r'ATTR|SELECTEDVALUE)\s*\(',
    re.IGNORECASE,
)
