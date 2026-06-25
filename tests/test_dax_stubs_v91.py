"""Tests for v9.1 DAX stub fixes in qlik_export.dax_converter.

Covers:
- _substitute_args() helper — split args by comma respecting parentheses
- Correl(X, Y) → Pearson formula with SUMX/AVERAGEX
- BitCount(N) → MOD/INT bit counting formula
- Atan2(X, Y) → 4-quadrant IF/PI formula
- NetWorkDays(D1, D2) → DATEDIFF-based working days
- SubField(S, D, N) → PATHITEM/SUBSTITUTE
- Interval(N) → FORMAT HH:MM:SS
- KeepChar(S, C) → documented approximation comment
- Skew(X) → deterministic fallback comment
- Hash128(X) → deterministic text key fallback
- Hash160(X) → deterministic text key fallback
- Hash256(X) → deterministic text key fallback
- Evaluate(X) → policy-based handling
- MonthName(D), QuarterName(D) — template arg substitution
- WeekStart(D), WeekEnd(D) — template arg substitution
- Mode(X) — fixed {0} reference
"""

import unittest
from qlik_export.dax_converter import (
    convert_qlik_expression_to_dax,
    _substitute_args,
    _split_top_level_args,
)


def dax(expr, table="Sales", **kw):
    """Shorthand for convert_qlik_expression_to_dax."""
    return convert_qlik_expression_to_dax(expr, table_name=table, **kw)


# ═══════════════════════════════════════════════════════════════
#  _substitute_args helper
# ═══════════════════════════════════════════════════════════════

class TestSubstituteArgs(unittest.TestCase):
    def test_single_arg(self):
        result = _substitute_args("UPPER({0})", ["[Name]"])
        self.assertEqual(result, "UPPER([Name])")

    def test_two_args(self):
        result = _substitute_args("DATEDIFF({0}, {1}, DAY)", ["[Start]", "[End]"])
        self.assertEqual(result, "DATEDIFF([Start], [End], DAY)")

    def test_three_args(self):
        result = _substitute_args("MID({0}, {1}, {2})", ["[Text]", "2", "5"])
        self.assertEqual(result, "MID([Text], 2, 5)")

    def test_repeated_placeholder(self):
        result = _substitute_args("{0} + {0}", ["[X]"])
        self.assertEqual(result, "[X] + [X]")

    def test_no_placeholders(self):
        result = _substitute_args("BLANK()", ["ignored"])
        self.assertEqual(result, "BLANK()")

    def test_empty_args(self):
        result = _substitute_args("{0}", [])
        self.assertEqual(result, "{0}")

    def test_arg_trimming(self):
        result = _substitute_args("{0}", ["  [Name]  "])
        self.assertEqual(result, "[Name]")


# ═══════════════════════════════════════════════════════════════
#  _split_top_level_args helper
# ═══════════════════════════════════════════════════════════════

class TestSplitTopLevelArgs(unittest.TestCase):
    def test_simple_two_args(self):
        result = _split_top_level_args("[X], [Y]")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].strip(), "[X]")
        self.assertEqual(result[1].strip(), "[Y]")

    def test_nested_parens(self):
        result = _split_top_level_args("SUM([X]), AVG([Y])")
        self.assertEqual(len(result), 2)
        self.assertIn("SUM([X])", result[0])
        self.assertIn("AVG([Y])", result[1])

    def test_nested_function_with_comma(self):
        result = _split_top_level_args("IF([X] > 0, [X], 0), [Y]")
        self.assertEqual(len(result), 2)
        self.assertIn("IF", result[0])
        self.assertEqual(result[1].strip(), "[Y]")

    def test_single_arg(self):
        result = _split_top_level_args("[Amount]")
        self.assertEqual(len(result), 1)

    def test_string_with_comma(self):
        result = _split_top_level_args('"hello, world", [X]')
        self.assertEqual(len(result), 2)
        self.assertIn("hello, world", result[0])


# ═══════════════════════════════════════════════════════════════
#  Correl(X, Y) → Pearson formula
# ═══════════════════════════════════════════════════════════════

class TestCorrel(unittest.TestCase):
    def test_basic(self):
        result = dax("Correl([Sales], [Cost])")
        self.assertIn("DIVIDE", result)
        self.assertIn("SUMX", result)
        self.assertIn("AVERAGE", result)
        self.assertIn("[Sales]", result)
        self.assertIn("[Cost]", result)
        self.assertIn("SQRT", result)

    def test_pearson_structure(self):
        result = dax("Correl([X], [Y])")
        self.assertIn("pearson", result.lower())
        self.assertIn("fallback", result.lower())
        # Must have covariance / std dev structure
        self.assertIn("SUMX", result)
        self.assertIn("AVERAGE", result)


# ═══════════════════════════════════════════════════════════════
#  BitCount(N) → MOD/INT 8-bit approx
# ═══════════════════════════════════════════════════════════════

class TestBitCount(unittest.TestCase):
    def test_basic(self):
        result = dax("BitCount([Flags])")
        self.assertIn("MOD", result)
        self.assertIn("INT", result)
        self.assertIn("[Flags]", result)

    def test_eight_bits(self):
        result = dax("BitCount([N])")
        # 8 MOD( calls for 8-bit approximation + 1 MOD in the comment = 9 total,
        # or count MOD(INT which only appears in the formula body
        self.assertGreaterEqual(result.count("MOD(INT"), 8)

    def test_powers_of_two(self):
        result = dax("BitCount([N])")
        # Division by powers of 2: /2, /4, /8, /16, /32, /64, /128
        for divisor in [2, 4, 8, 16, 32, 64, 128]:
            self.assertIn(f"/ {divisor}", result)

    def test_comment_present(self):
        result = dax("BitCount([N])")
        self.assertIn("BitCount", result)
        self.assertIn("fallback", result.lower())


# ═══════════════════════════════════════════════════════════════
#  Atan2(X, Y) → 4-quadrant IF/PI formula
# ═══════════════════════════════════════════════════════════════

class TestAtan2(unittest.TestCase):
    def test_basic(self):
        result = dax("Atan2([X], [Y])")
        self.assertIn("IF", result)
        self.assertIn("ATAN", result)
        self.assertIn("PI()", result)
        self.assertIn("[X]", result)
        self.assertIn("[Y]", result)

    def test_four_quadrants(self):
        result = dax("Atan2([X], [Y])")
        # Should have multiple IF branches for quadrant handling
        self.assertGreaterEqual(result.count("IF"), 3)

    def test_pi_halves(self):
        result = dax("Atan2([X], [Y])")
        self.assertIn("PI()/2", result)
        self.assertIn("-PI()/2", result)


# ═══════════════════════════════════════════════════════════════
#  NetWorkDays(D1, D2) → DATEDIFF-based working days
# ═══════════════════════════════════════════════════════════════

class TestNetWorkDays(unittest.TestCase):
    def test_basic(self):
        result = dax("NetWorkDays([Start], [End])")
        self.assertIn("DATEDIFF", result)
        self.assertIn("[Start]", result)
        self.assertIn("[End]", result)
        self.assertIn("DAY", result)

    def test_weekend_subtraction(self):
        result = dax("NetWorkDays([D1], [D2])")
        # Should subtract 2 * INT(days / 7) for weekends
        self.assertIn("INT", result)
        self.assertIn("/ 7", result)

    def test_comment(self):
        result = dax("NetWorkDays([D1], [D2])")
        self.assertIn("NetWorkDays", result)
        self.assertIn("weekends", result)


# ═══════════════════════════════════════════════════════════════
#  SubField(S, D, N) → PATHITEM/SUBSTITUTE
# ═══════════════════════════════════════════════════════════════

class TestSubField(unittest.TestCase):
    def test_basic(self):
        result = dax("SubField([FullName], '-', 1)")
        self.assertIn("PATHITEM", result)
        self.assertIn("SUBSTITUTE", result)

    def test_delimiter_substitution(self):
        result = dax("SubField([Path], '/', 2)")
        self.assertIn("SUBSTITUTE", result)
        self.assertIn("'/'", result)
        self.assertIn('"|"', result)

    def test_index_arg(self):
        result = dax("SubField([Data], ',', 3)")
        self.assertIn("3", result)


# ═══════════════════════════════════════════════════════════════
#  Interval(N) → FORMAT HH:MM:SS
# ═══════════════════════════════════════════════════════════════

class TestInterval(unittest.TestCase):
    def test_basic(self):
        result = dax("Interval([Seconds])")
        self.assertIn("FORMAT", result)
        self.assertIn("[Seconds]", result)

    def test_hms_structure(self):
        result = dax("Interval([T])")
        # Should produce HH:MM:SS format using /3600 and MOD 60
        self.assertIn("3600", result)
        self.assertIn("60", result)
        self.assertIn('":"', result)

    def test_two_colon_separators(self):
        result = dax("Interval([T])")
        self.assertIn("&", result)  # String concatenation


# ═══════════════════════════════════════════════════════════════
#  Stub fallbacks and policy-driven handling
# ═══════════════════════════════════════════════════════════════

class TestUnsupportedStubs(unittest.TestCase):
    def test_keepchar(self):
        result = dax("KeepChar([Name], 'ABC')")
        self.assertIn("SUBSTITUTE", result)
        self.assertIn("KeepChar", result)

    def test_skew(self):
        result = dax("Skew([Values])")
        self.assertIn("Skew fallback", result)
        self.assertNotIn("UNSUPPORTED", result)

    def test_hash128(self):
        result = dax("Hash128([ID])")
        self.assertIn("Hash128 fallback", result)
        self.assertIn("FORMAT(", result)

    def test_hash160(self):
        result = dax("Hash160([ID])")
        self.assertIn("Hash160 fallback", result)
        self.assertIn("FORMAT(", result)

    def test_hash256(self):
        result = dax("Hash256([ID])")
        self.assertIn("Hash256 fallback", result)
        self.assertIn("FORMAT(", result)

    def test_evaluate(self):
        result = dax("Evaluate([Expr])")
        self.assertNotIn("Evaluate(", result)
        self.assertIn("[Expr]", result)

    def test_evaluate_block_policy(self):
        result = dax("Evaluate([Expr])", evaluate_policy="block")
        self.assertIn("BLANK()", result)
        self.assertIn("blocked by policy", result)

    def test_keepchar_preserves_first_arg(self):
        result = dax("KeepChar([Phone], '0123456789')")
        self.assertIn("[Phone]", result)

    def test_hash_preserves_first_arg(self):
        result = dax("Hash128([Email])")
        self.assertIn("[Email]", result)

    def test_evaluate_preserves_first_arg(self):
        result = dax("Evaluate([Formula])")
        self.assertIn("[Formula]", result)

    def test_skew_returns_zero(self):
        result = dax("Skew([Values])")
        # Skew template ends with " 0" as fallback value
        self.assertIn("0", result)


# ═══════════════════════════════════════════════════════════════
#  MonthName / QuarterName — template arg substitution
# ═══════════════════════════════════════════════════════════════

class TestMonthQuarterName(unittest.TestCase):
    def test_monthname_basic(self):
        result = dax("MonthName([OrderDate])")
        self.assertIn("FORMAT", result)
        self.assertIn("[OrderDate]", result)
        self.assertIn("MMMM", result)

    def test_monthname_expression_arg(self):
        result = dax("MonthName(Today())")
        r = result
        self.assertIn("FORMAT", r)
        self.assertIn("MMMM", r)

    def test_quartername_basic(self):
        result = dax("QuarterName([Date])")
        self.assertIn("FORMAT", result)
        self.assertIn("[Date]", result)
        self.assertIn("YYYY", result)

    def test_quartername_has_q_prefix(self):
        result = dax("QuarterName([Date])")
        self.assertIn("Q", result)

    def test_monthname_no_leftover_placeholder(self):
        result = dax("MonthName([D])")
        self.assertNotIn("{0}", result)

    def test_quartername_no_leftover_placeholder(self):
        result = dax("QuarterName([D])")
        self.assertNotIn("{0}", result)


# ═══════════════════════════════════════════════════════════════
#  WeekStart / WeekEnd — template arg substitution
# ═══════════════════════════════════════════════════════════════

class TestWeekStartEnd(unittest.TestCase):
    def test_weekstart_basic(self):
        result = dax("WeekStart([Date])")
        self.assertIn("DATE", result)
        self.assertIn("YEAR", result)
        self.assertIn("WEEKNUM", result)
        self.assertIn("[Date]", result)

    def test_weekend_basic(self):
        result = dax("WeekEnd([Date])")
        self.assertIn("DATE", result)
        self.assertIn("YEAR", result)
        self.assertIn("WEEKNUM", result)
        self.assertIn("[Date]", result)

    def test_weekstart_no_placeholder(self):
        result = dax("WeekStart([D])")
        self.assertNotIn("{0}", result)

    def test_weekend_no_placeholder(self):
        result = dax("WeekEnd([D])")
        self.assertNotIn("{0}", result)

    def test_weekstart_with_expression(self):
        result = dax("WeekStart(Today())")
        self.assertIn("TODAY()", result)
        self.assertNotIn("{0}", result)

    def test_weekend_with_expression(self):
        result = dax("WeekEnd(Today())")
        self.assertIn("TODAY()", result)
        self.assertNotIn("{0}", result)


# ═══════════════════════════════════════════════════════════════
#  Mode(X) — fixed {0} reference
# ═══════════════════════════════════════════════════════════════

class TestMode(unittest.TestCase):
    def test_basic(self):
        result = dax("Mode([Score])")
        self.assertIn("MINX", result)
        self.assertIn("TOPN", result)
        self.assertIn("[Score]", result)

    def test_no_leftover_placeholder(self):
        result = dax("Mode([Category])")
        self.assertNotIn("{0}", result)
        self.assertNotIn("{1}", result)

    def test_structure(self):
        result = dax("Mode([Val])")
        self.assertIn("ADDCOLUMNS", result)
        self.assertIn("VALUES", result)
        self.assertIn("COUNT", result)
        self.assertIn("@freq", result)


# ═══════════════════════════════════════════════════════════════
#  Combined / edge-case scenarios
# ═══════════════════════════════════════════════════════════════

class TestCombinedExpressions(unittest.TestCase):
    def test_monthname_in_larger_expression(self):
        result = dax("MonthName([Date]) & ' ' & Year([Date])")
        self.assertIn("FORMAT", result)
        self.assertIn("MMMM", result)
        self.assertIn("YEAR", result)

    def test_nested_function_as_arg(self):
        result = dax("WeekStart(Date(2024, 1, 15))")
        self.assertIn("DATE", result)
        self.assertNotIn("{0}", result)

    def test_interval_in_expression(self):
        result = dax("'Duration: ' & Interval([Sec])")
        self.assertIn("FORMAT", result)
        self.assertIn("3600", result)

    def test_bitcount_in_if(self):
        result = dax("If(BitCount([Mask]) > 3, 'Many', 'Few')")
        self.assertIn("IF", result)
        self.assertIn("MOD", result)

    def test_multiple_unsupported_in_one_expr(self):
        result = dax("Hash128([A]) & Hash256([B])")
        self.assertEqual(result.count("deterministic text key"), 2)
        self.assertNotIn("UNSUPPORTED", result)


if __name__ == "__main__":
    unittest.main()
