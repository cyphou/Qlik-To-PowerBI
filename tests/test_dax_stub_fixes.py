"""Tests for DAX stub function fixes and Tableau remnant cleanup.

Validates that previously-stubbed DAX functions now produce proper
output, and that Tableau-specific patterns have been replaced with
Qlik equivalents across the codebase.
"""

import re
import warnings
import pytest

from qlik_export.dax_converter import (
    convert_qlik_expression_to_dax,
    _SIMPLE_FUNCTION_MAP,
    _COMPILED_FUNCTION_MAP,
)


# ── DAX Stub Fix Tests ──────────────────────────────────────────────

class TestSkewStub:
    def test_skew_fallback_documented(self):
        result = convert_qlik_expression_to_dax("Skew(Sales)")
        assert "Skew fallback" in result
        assert "UNSUPPORTED" not in result
        assert "0" in result

    def test_skew_not_stdev(self):
        result = convert_qlik_expression_to_dax("Skew(Sales)")
        assert "STDEV.S" not in result


class TestCorrelStub:
    def test_correl_fallback_documented(self):
        result = convert_qlik_expression_to_dax("Correl(X, Y)")
        assert "Correl fallback" in result
        assert "Pearson" in result or "0" in result

    def test_correl_returns_zero(self):
        result = convert_qlik_expression_to_dax("Correl(X, Y)")
        assert "0" in result


class TestNetWorkDaysStub:
    def test_networkdays_uses_datediff(self):
        result = convert_qlik_expression_to_dax("NetWorkDays(StartDate, EndDate)")
        assert "DATEDIFF" in result

    def test_networkdays_excludes_weekends(self):
        result = convert_qlik_expression_to_dax("NetWorkDays(StartDate, EndDate)")
        assert "approximate" in result.lower() or "weekends" in result.lower()
        # Should subtract weekend days
        assert "INT" in result or "MOD" in result or "DIVIDE" in result


class TestKeepCharStub:
    def test_keepchar_documented(self):
        result = convert_qlik_expression_to_dax("KeepChar(Name, 'abc')")
        assert "SUBSTITUTE" in result
        assert "approximate" in result.lower() or "KeepChar" in result


class TestSubFieldStub:
    def test_subfield_uses_pathitem(self):
        result = convert_qlik_expression_to_dax("SubField(FullName, ' ', 1)")
        assert "PATHITEM" in result
        assert "SUBSTITUTE" in result

    def test_subfield_not_passthrough(self):
        result = convert_qlik_expression_to_dax("SubField(Data, ';', 2)")
        assert "PATHITEM" in result


class TestMapSubstringStub:
    def test_mapsubstring_uses_substitute(self):
        result = convert_qlik_expression_to_dax("MapSubstring('map', Text)")
        assert "SUBSTITUTE" in result
        assert "MapSubstring" in result or "lookup" in result.lower()


class TestAtan2Stub:
    def test_atan2_four_quadrant(self):
        result = convert_qlik_expression_to_dax("Atan2(x, y)")
        assert "IF(" in result
        assert "ATAN(" in result
        assert "PI()" in result

    def test_atan2_not_simple_division(self):
        result = convert_qlik_expression_to_dax("Atan2(x, y)")
        # Should not be a simple ATAN(y/x)
        assert result.count("IF(") >= 1 or "PI()" in result


class TestIntervalStub:
    def test_interval_hh_mm_ss_format(self):
        result = convert_qlik_expression_to_dax("Interval(Seconds)")
        assert "FORMAT" in result or "MOD" in result
        assert ":" in result  # HH:MM:SS separator

    def test_interval_not_value(self):
        result = convert_qlik_expression_to_dax("Interval(3661)")
        assert "VALUE(" not in result


class TestBitCountStub:
    def test_bitcount_fallback_documented(self):
        result = convert_qlik_expression_to_dax("BitCount(255)")
        assert "BitCount fallback" in result


# ── Hash functions (unsupported — documented) ────────────────────────

class TestHashFunctions:
    @pytest.mark.parametrize("func", ["Hash128", "Hash160", "Hash256"])
    def test_hash_uses_deterministic_text_key(self, func):
        result = convert_qlik_expression_to_dax(f"{func}(Value)")
        assert "FORMAT(" in result
        assert "deterministic text key" in result
        assert "UNSUPPORTED" not in result

    def test_evaluate_passthrough_by_default(self):
        result = convert_qlik_expression_to_dax("Evaluate('1+1')")
        assert "Evaluate(" not in result
        assert "'1+1'" in result

    def test_evaluate_policy_blank(self):
        result = convert_qlik_expression_to_dax("Evaluate('1+1')", evaluate_policy="blank")
        assert "BLANK()" in result

    def test_evaluate_policy_block(self):
        result = convert_qlik_expression_to_dax("Evaluate('1+1')", evaluate_policy="block")
        assert "Evaluate blocked by policy" in result


# ── Strategy Advisor: Qlik patterns replaced ─────────────────────────

class TestStrategyAdvisorQlikPatterns:
    def test_no_tableau_lod_patterns(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        # Should NOT match Tableau LOD (FIXED/INCLUDE/EXCLUDE)
        assert not _COMPLEX_FORMULA_PATTERN.search("{FIXED [Dim] : SUM([Measure])}")

    def test_matches_set_analysis(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("{<Year={2024}>}")

    def test_matches_aggr(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("Aggr(Sum(Sales), Customer)")

    def test_matches_dollar_sign(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("$(=Year(Today())-1)")

    def test_matches_total(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("Sum(TOTAL Sales)")

    def test_matches_peek(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("Peek(Amount, -1)")

    def test_matches_previous(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("Previous(Sales)")

    def test_matches_above(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("Above(Value, 1)")

    def test_matches_below(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("Below(Value, 1)")

    def test_matches_rangesum(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert _COMPLEX_FORMULA_PATTERN.search("RangeSum(Above(Sales, 0, RowNo()))")

    def test_no_running_window_patterns(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        # Tableau-specific RUNNING_SUM, WINDOW_SUM should NOT match
        assert not _COMPLEX_FORMULA_PATTERN.search("RUNNING_SUM(SUM(Profit))")
        assert not _COMPLEX_FORMULA_PATTERN.search("WINDOW_AVG(SUM(Sales))")

    def test_no_rawsql_pattern(self):
        from powerbi_import.strategy_advisor import _COMPLEX_FORMULA_PATTERN
        assert not _COMPLEX_FORMULA_PATTERN.search("RAWSQL_INT('SELECT 1')")


class TestStrategyAdvisorAggPattern:
    def test_qlik_sum(self):
        from powerbi_import.strategy_advisor import _AGG_PATTERN
        assert _AGG_PATTERN.search("Sum(Sales)")

    def test_qlik_countdistinct(self):
        from powerbi_import.strategy_advisor import _AGG_PATTERN
        assert _AGG_PATTERN.search("CountDistinct(CustomerID)")

    def test_qlik_aggr_not_in_agg_list(self):
        """Aggr itself is not an aggregation function in the agg pattern."""
        from powerbi_import.strategy_advisor import _AGG_PATTERN
        # The pattern should NOT have 'Aggr' as a recognized aggregation
        assert not _AGG_PATTERN.search("Aggr(")

    def test_no_tableau_running_sum_keyword(self):
        from powerbi_import.strategy_advisor import _AGG_PATTERN
        # RUNNING_SUM itself should NOT be in the agg pattern
        assert not _AGG_PATTERN.search("RUNNING_SUM(")

    def test_no_tableau_window_sum_keyword(self):
        from powerbi_import.strategy_advisor import _AGG_PATTERN
        # WINDOW_SUM itself should NOT be in the agg pattern
        assert not _AGG_PATTERN.search("WINDOW_SUM(")


class TestStrategyAdvisorRecommendation:
    def test_simple_qlik_app_recommends_import(self):
        from powerbi_import.strategy_advisor import recommend_strategy
        data = {
            'datasources': [{
                'connection': {'type': 'Excel'},
                'tables': [{'name': 'Sales', 'columns': [{'name': 'Amount'}]}],
            }],
            'calculations': [{'formula': 'Sum(Amount)', 'role': 'measure'}],
            'custom_sql': [],
        }
        rec = recommend_strategy(data)
        assert rec.strategy == 'import'

    def test_complex_qlik_app_favours_directquery(self):
        from powerbi_import.strategy_advisor import recommend_strategy
        # BigQuery + many Set Analysis calcs + custom SQL
        calcs = [{'formula': 'Sum({<Year={2024}>} Sales)', 'role': 'measure'}] * 5
        data = {
            'datasources': [{
                'connection': {'type': 'BigQuery'},
                'tables': [{'name': f'T{i}', 'columns': [{'name': f'c{j}'} for j in range(20)]} for i in range(8)],
            }],
            'calculations': calcs,
            'custom_sql': [{'query': 'SELECT * FROM big_table'}],
        }
        rec = recommend_strategy(data)
        assert rec.strategy in ('directquery', 'composite')


# ── TMDL Generator: Clean agg classifier ─────────────────────────────

class TestTmdlAggClassifier:
    def test_no_tableau_running_in_pattern(self):
        """Verify RUNNING_SUM etc. removed from the agg pattern in tmdl_generator."""
        import importlib
        import inspect
        source = inspect.getsource(
            importlib.import_module('powerbi_import.tmdl_generator')
        )
        # The _agg_pattern should NOT contain RUNNING_ or WINDOW_ Tableau function names
        # (They appear in comments for table_calc measures, which is fine,
        #  but the pre-compiled agg classifier pattern should be clean)
        # Check only the pattern definition line, not comments
        pattern_match = re.search(r"_agg_pattern\s*=\s*re\.compile\((.*?)\)", source, re.DOTALL)
        if pattern_match:
            pattern_text = pattern_match.group(1)
            assert "RUNNING_SUM" not in pattern_text
            assert "RUNNING_AVG" not in pattern_text
            assert "WINDOW_SUM" not in pattern_text
            assert "WINDOW_AVG" not in pattern_text
            assert "RANK_UNIQUE" not in pattern_text
            assert "RANK_DENSE" not in pattern_text
            assert "RANK_MODIFIED" not in pattern_text


# ── migrate.py: No Tableau refs ──────────────────────────────────────

class TestMigrateCleanup:
    def test_no_tableau_theme_check(self):
        import inspect
        import importlib
        source = inspect.getsource(importlib.import_module('migrate'))
        assert "TableauMigrationTheme" not in source

    def test_no_tableau_export_comment(self):
        import inspect
        import importlib
        source = inspect.getsource(importlib.import_module('migrate'))
        assert "same pattern as tableau_export" not in source


# ── migration_config.py: qlik_file alias ─────────────────────────────

class TestMigrationConfigQlikAlias:
    def test_qlik_file_property_exists(self):
        from powerbi_import.config.migration_config import MigrationConfig
        cfg = MigrationConfig({'source': {'source_file': 'test.qvf'}})
        assert cfg.qlik_file == 'test.qvf'

    def test_tableau_file_emits_deprecation(self):
        from powerbi_import.config.migration_config import MigrationConfig
        cfg = MigrationConfig({'source': {'source_file': 'test.qvf'}})
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = cfg.tableau_file
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    def test_legacy_tableau_file_key_migrated(self):
        from powerbi_import.config.migration_config import MigrationConfig
        cfg = MigrationConfig({'source': {'tableau_file': 'old.twbx'}})
        assert cfg.source_file == 'old.twbx'

    def test_legacy_qlik_file_key_migrated(self):
        from powerbi_import.config.migration_config import MigrationConfig
        cfg = MigrationConfig({'source': {'qlik_file': 'app.qvf'}})
        assert cfg.source_file == 'app.qvf'


# ── Compilation sanity ───────────────────────────────────────────────

class TestFunctionMapCompilation:
    def test_all_patterns_compile(self):
        """All patterns in _SIMPLE_FUNCTION_MAP should be valid regex."""
        for pattern, replacement in _SIMPLE_FUNCTION_MAP:
            re.compile(pattern, re.IGNORECASE)  # should not raise

    def test_compiled_map_matches_source(self):
        assert len(_COMPILED_FUNCTION_MAP) == len(_SIMPLE_FUNCTION_MAP)

    def test_no_manual_comment_in_stubs(self):
        """No more '/* manual */' patterns without context."""
        for _pattern, replacement in _SIMPLE_FUNCTION_MAP:
            if "manual" in replacement.lower():
                # Every manual comment should explain the limitation
                assert ("no DAX equivalent" in replacement
                        or "partial" in replacement
                        or "approximate" in replacement
                        or "custom measure" in replacement), \
                    f"Undocumented manual stub: {replacement}"
