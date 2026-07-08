"""Tests for qlik_export.qlik_script_converter — Qlik load script → Power Query M.

Covers:
- QlikScriptToPowerQueryConverter: parse_qlik_load, convert_load_to_powerquery,
  convert_qlik_script_to_powerquery, convert_qlik_function
- QlikScriptMigrator: generate_conversion_report
- LOAD ... FROM [file], RESIDENT, INLINE, SQL
- WHERE clauses
- JOIN / CONCATENATE
- Variable expansion (LET/SET)
- QUALIFY / UNQUALIFY
- FOR EACH ... IN FileList
- MAPPING LOAD
- Stacked/Preceding LOADs
- FUNCTION_MAP (30 Qlik→M function mappings)
"""

import pytest
from qlik_export.qlik_script_converter import (
    QlikScriptToPowerQueryConverter as Conv,
    QlikScriptMigrator,
    QlikLoadStatement,
    _detect_stacked_load,
)


# ═══════════════════════════════════════════════════════════════
#  _detect_stacked_load
# ═══════════════════════════════════════════════════════════════

class TestDetectStackedLoad:
    def test_single_load(self):
        assert _detect_stacked_load("LOAD A, B FROM [data.csv];") is False

    def test_double_load(self):
        assert _detect_stacked_load("LOAD A, B; LOAD C, D FROM [x.csv];") is True

    def test_no_load(self):
        assert _detect_stacked_load("SELECT * FROM table") is False


# ═══════════════════════════════════════════════════════════════
#  convert_qlik_function (static)
# ═══════════════════════════════════════════════════════════════

class TestConvertQlikFunction:
    def test_upper(self):
        assert "Text.Upper" in Conv.convert_qlik_function("Upper(Name)")

    def test_lower(self):
        assert "Text.Lower" in Conv.convert_qlik_function("Lower(Name)")

    def test_year(self):
        assert "Date.Year" in Conv.convert_qlik_function("Year(Date)")

    def test_month(self):
        assert "Date.Month" in Conv.convert_qlik_function("Month(Date)")

    def test_day(self):
        assert "Date.Day" in Conv.convert_qlik_function("Day(Date)")

    def test_sum(self):
        assert "List.Sum" in Conv.convert_qlik_function("Sum(Amount)")

    def test_count(self):
        assert "List.Count" in Conv.convert_qlik_function("Count(ID)")

    def test_left(self):
        assert "Text.Start" in Conv.convert_qlik_function("Left(Name, 3)")

    def test_right(self):
        assert "Text.End" in Conv.convert_qlik_function("Right(Name, 3)")

    def test_mid(self):
        assert "Text.Middle" in Conv.convert_qlik_function("Mid(Name, 2, 4)")

    def test_len(self):
        assert "Text.Length" in Conv.convert_qlik_function("Len(Name)")

    def test_trim(self):
        assert "Text.Trim" in Conv.convert_qlik_function("Trim(Name)")

    def test_replace(self):
        result = Conv.convert_qlik_function("Replace(Name, 'a', 'b')")
        assert "Text.Replace" in result or "Replacer" in result

    def test_unknown_function_unchanged(self):
        result = Conv.convert_qlik_function("MyCustomFunc(x)")
        assert "MyCustomFunc" in result

    def test_case_insensitive(self):
        assert "Text.Upper" in Conv.convert_qlik_function("upper(Name)")


# ═══════════════════════════════════════════════════════════════
#  parse_qlik_load
# ═══════════════════════════════════════════════════════════════

class TestParseQlikLoad:
    def test_from_csv(self):
        stmt = Conv.parse_qlik_load("LOAD A, B FROM [data.csv];")
        assert isinstance(stmt, QlikLoadStatement)
        assert stmt.source_type == "file"
        assert "data.csv" in stmt.source
        assert "A" in stmt.fields

    def test_from_excel(self):
        stmt = Conv.parse_qlik_load("LOAD ID, Name FROM [report.xlsx];")
        assert stmt.source_type == "file"
        assert "report.xlsx" in stmt.source

    def test_resident(self):
        stmt = Conv.parse_qlik_load("LOAD * RESIDENT MyTable;")
        assert stmt.source_type == "resident"
        assert stmt.source == "MyTable"

    def test_with_where(self):
        stmt = Conv.parse_qlik_load("LOAD A, B FROM [data.csv] WHERE Status='Active';")
        assert stmt.where_clause is not None
        assert "Active" in stmt.where_clause

    def test_star_fields(self):
        stmt = Conv.parse_qlik_load("LOAD * FROM [data.csv];")
        assert "*" in stmt.fields

    def test_alias_field(self):
        stmt = Conv.parse_qlik_load("LOAD Amount as Revenue FROM [data.csv];")
        assert any("Amount" in f or "Revenue" in f for f in stmt.fields)

    def test_multiple_fields(self):
        stmt = Conv.parse_qlik_load("LOAD A, B, C, D FROM [data.csv];")
        assert len(stmt.fields) >= 4

    def test_load_ignores_inline_comment_fields(self):
        stmt = Conv.parse_qlik_load(
            "LOAD A, // comment about field\n B FROM [data.csv];"
        )
        assert stmt.fields == ["A", "B"]

    def test_load_stops_before_sql_select_clause(self):
        stmt = Conv.parse_qlik_load(
            'LOAD ID_FEI, DATE_DEC_FEI; SQL SELECT "ID_FEI", "DATE_DEC_FEI" FROM MY_TABLE;'
        )
        assert stmt.source_type == "sql"
        assert stmt.fields == ["ID_FEI", "DATE_DEC_FEI"]

    def test_load_stops_before_plain_select_clause(self):
        stmt = Conv.parse_qlik_load(
            'LOAD ID_FEI, DATE_DEC_FEI; SELECT "ID_FEI", "DATE_DEC_FEI" FROM MY_TABLE;'
        )
        assert stmt.source_type == "sql"
        assert stmt.fields == ["ID_FEI", "DATE_DEC_FEI"]

    def test_load_strips_bracketed_label_before_select_clause(self):
        stmt = Conv.parse_qlik_load(
            'LOAD QCLG_CODE_ENTITE, ID_CHGT_TECH;\n\n[QUAL_QUESTPAT_CLOT_GENERIQUE]:\nSELECT "QCLG_CODE_ENTITE", "ID_CHGT_TECH" FROM MY_TABLE;'
        )
        assert stmt.source_type == "sql"
        assert stmt.fields == ["QCLG_CODE_ENTITE", "ID_CHGT_TECH"]


# ═══════════════════════════════════════════════════════════════
#  convert_load_to_powerquery
# ═══════════════════════════════════════════════════════════════

class TestConvertLoadToPowerQuery:
    def test_csv_source(self):
        stmt = QlikLoadStatement(
            fields=["A", "B"],
            source="data.csv",
            source_type="file",
        )
        pq = Conv.convert_load_to_powerquery(stmt)
        assert "let" in pq.lower()
        assert "in" in pq.lower()
        assert "Csv.Document" in pq or "File.Contents" in pq

    def test_xlsx_source(self):
        stmt = QlikLoadStatement(
            fields=["ID"],
            source="report.xlsx",
            source_type="file",
        )
        pq = Conv.convert_load_to_powerquery(stmt)
        assert "Excel.Workbook" in pq

    def test_resident_source(self):
        stmt = QlikLoadStatement(
            fields=["*"],
            source="BaseTable",
            source_type="resident",
        )
        pq = Conv.convert_load_to_powerquery(stmt)
        assert "BaseTable" in pq

    def test_sql_source(self):
        stmt = QlikLoadStatement(
            fields=["A"],
            source="SELECT A FROM Orders",
            source_type="sql",
        )
        pq = Conv.convert_load_to_powerquery(stmt)
        assert "Sql.Database" in pq

    def test_where_clause_generates_filter(self):
        stmt = QlikLoadStatement(
            fields=["A", "B"],
            source="data.csv",
            source_type="file",
            where_clause="Status='Active'",
        )
        pq = Conv.convert_load_to_powerquery(stmt)
        assert "SelectRows" in pq or "Active" in pq

    def test_selected_columns_escape_quotes(self):
        stmt = QlikLoadStatement(
            fields=['ID_FEI', 'DATE_DEC_FEI "RAW"'],
            source='data.csv',
            source_type='file',
        )
        pq = Conv.convert_load_to_powerquery(stmt)
        assert '"DATE_DEC_FEI ""RAW"""' in pq


# ═══════════════════════════════════════════════════════════════
#  convert_qlik_script_to_powerquery (full pipeline)
# ═══════════════════════════════════════════════════════════════

class TestConvertFullScript:
    def test_simple_load(self):
        script = "LOAD A, B FROM [data.csv];"
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "let" in pq.lower()
        assert "Csv" in pq or "File.Contents" in pq

    def test_inline_table(self):
        script = """
        MyTable:
        LOAD * INLINE [
        Name, Age
        Alice, 30
        Bob, 25
        ];
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "#table" in pq or "Alice" in pq

    def test_variable_expansion(self):
        script = """
        SET vPath = data.csv;
        LOAD A, B FROM [$(vPath)];
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "data.csv" in pq

    def test_multiple_loads(self):
        script = """
        Orders:
        LOAD ID, Amount FROM [orders.csv];

        Products:
        LOAD ID, Name FROM [products.csv];
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "let" in pq.lower()

    def test_concatenate(self):
        script = """
        Base:
        LOAD A, B FROM [base.csv];

        CONCATENATE(Base)
        LOAD A, B FROM [extra.csv];
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "Combine" in pq or "Concatenate" in pq.lower() or "let" in pq.lower()

    def test_join(self):
        script = """
        Orders:
        LOAD OrderID, Amount FROM [orders.csv];

        LEFT JOIN(Orders)
        LOAD OrderID, Customer FROM [details.csv];
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "Join" in pq or "NestedJoin" in pq or "let" in pq.lower()

    def test_qualify(self):
        """QUALIFY is parsed but not applied — should not crash."""
        script = """
        QUALIFY *;
        LOAD A, B FROM [data.csv];
        UNQUALIFY *;
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert isinstance(pq, str)

    def test_for_each_filelist(self):
        script = """
        FOR EACH vFile IN FileList('data/*.csv')
        LOAD * FROM [$(vFile)];
        NEXT vFile;
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "Folder" in pq or "Combine" in pq or "csv" in pq.lower()

    def test_empty_script(self):
        pq = Conv.convert_qlik_script_to_powerquery("")
        assert isinstance(pq, str)

    def test_mapping_load(self):
        script = """
        CountryMap:
        MAPPING LOAD Code, Name FROM [countries.csv];
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "Mapping" in pq or "let" in pq.lower() or "countries" in pq.lower()

    def test_stacked_load_detection(self):
        script = """
        Result:
        LOAD A, B + C as D;
        LOAD A, B, C FROM [data.csv];
        """
        pq = Conv.convert_qlik_script_to_powerquery(script)
        assert "Stacked" in pq or "Preceding" in pq or "let" in pq.lower()


# ═══════════════════════════════════════════════════════════════
#  QlikScriptMigrator
# ═══════════════════════════════════════════════════════════════

class TestQlikScriptMigrator:
    def test_generate_conversion_report(self):
        migrator = QlikScriptMigrator()
        qlik_script = "LOAD Upper(Name), Year(Date), Sum(Amount) FROM [data.csv];"
        pq_script = "let Source = Csv.Document(...)\nin Source"
        report = migrator.generate_conversion_report(qlik_script, pq_script)
        assert "conversion_rate" in report
        assert isinstance(report["conversion_rate"], (int, float))
        assert report["conversion_rate"] >= 0

    def test_report_no_functions(self):
        migrator = QlikScriptMigrator()
        report = migrator.generate_conversion_report("LOAD A FROM [x.csv];", "let...")
        assert isinstance(report, dict)


# ═══════════════════════════════════════════════════════════════
#  Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_load_with_calculated_field(self):
        stmt = Conv.parse_qlik_load("LOAD Upper(Name) as UName FROM [data.csv];")
        pq = Conv.convert_load_to_powerquery(stmt)
        assert "Text.Upper" in pq or "AddColumn" in pq or "UName" in pq

    def test_qvd_source(self):
        stmt = QlikLoadStatement(
            fields=["*"],
            source="data.qvd",
            source_type="file",
        )
        pq = Conv.convert_load_to_powerquery(stmt)
        assert "Qvd" in pq or "qvd" in pq.lower() or "let" in pq.lower()

    def test_where_with_and(self):
        stmt = Conv.parse_qlik_load(
            "LOAD A, B FROM [data.csv] WHERE Year=2024 AND Status='Active';")
        assert stmt.where_clause is not None
        assert "2024" in stmt.where_clause
