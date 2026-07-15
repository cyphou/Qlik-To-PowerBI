"""Tests for powerbi_import.m_healing."""

import unittest

from powerbi_import.m_healing import (
    heal_balance_parens,
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


if __name__ == "__main__":
    unittest.main()
