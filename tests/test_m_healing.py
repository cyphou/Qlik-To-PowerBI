"""Tests for powerbi_import.m_healing."""

import unittest

from powerbi_import.m_healing import (
    heal_balance_parens,
    heal_missing_in_clause,
    heal_m,
    heal_trailing_comma,
)


class TestMHealing(unittest.TestCase):
    def test_heal_balance_parens(self):
        m = "Text.Upper((\"abc\")"
        healed, action = heal_balance_parens(m)
        self.assertIsNotNone(action)
        self.assertEqual(healed, "Text.Upper((\"abc\"))")

    def test_heal_trailing_comma_before_in(self):
        m = "let\n    Source = #table(type table [A=number], {{1}}),\nin\n    Source"
        healed, action = heal_trailing_comma(m)
        self.assertIsNotNone(action)
        self.assertNotIn(",\nin", healed)

    def test_heal_m_composite(self):
        m = "let\n    Source = #table(type table [A=number], {{1}}),\nin\n    Source"
        report = heal_m(m)
        self.assertTrue(report.changed)
        self.assertGreaterEqual(len(report.actions), 1)

    def test_heal_missing_in_clause(self):
        m = "let\n    Source = #table(type table [A=number], {{1}})"
        healed, action = heal_missing_in_clause(m)
        self.assertIsNotNone(action)
        self.assertIn("\nin\n    Source", healed)

    def test_heal_m_missing_in_applies_only_aggressive(self):
        m = "let\n    Source = #table(type table [A=number], {{1}})"
        balanced = heal_m(m, rewrite_policy="balanced")
        aggressive = heal_m(m, rewrite_policy="aggressive")
        self.assertFalse(any(a.name == "missing_in_clause" for a in balanced.actions))
        self.assertTrue(any(a.name == "missing_in_clause" for a in aggressive.actions))


if __name__ == "__main__":
    unittest.main()
