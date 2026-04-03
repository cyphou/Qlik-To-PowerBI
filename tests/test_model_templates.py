"""Tests for powerbi_import.model_templates — pre-built star schema skeletons."""

import unittest

from powerbi_import.model_templates import (
    get_template,
    list_templates,
    apply_template,
)


class TestGetTemplate(unittest.TestCase):
    """Test template retrieval."""

    def test_healthcare_template_valid(self):
        tpl = get_template("healthcare")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl["name"], "Healthcare")

    def test_finance_has_required_keys(self):
        tpl = get_template("finance")
        self.assertIn("tables", tpl)
        self.assertIn("relationships", tpl)
        self.assertIn("measures", tpl)
        self.assertIn("hierarchies", tpl)

    def test_retail_table_names(self):
        tpl = get_template("retail")
        names = {t["name"] for t in tpl["tables"]}
        self.assertIn("Sales", names)
        self.assertIn("Products", names)
        self.assertIn("Stores", names)
        self.assertIn("Customers", names)

    def test_unknown_returns_none(self):
        tpl = get_template("unknown")
        self.assertIsNone(tpl)

    def test_case_insensitive(self):
        tpl = get_template("Finance")
        self.assertIsNotNone(tpl)

    def test_returns_deep_copy(self):
        t1 = get_template("healthcare")
        t2 = get_template("healthcare")
        t1["tables"].clear()
        self.assertGreater(len(t2["tables"]), 0)


class TestListTemplates(unittest.TestCase):
    def test_returns_three(self):
        templates = list_templates()
        self.assertEqual(len(templates), 3)
        self.assertIn("healthcare", templates)
        self.assertIn("finance", templates)
        self.assertIn("retail", templates)


class TestApplyTemplate(unittest.TestCase):
    """Test template merging with existing tables."""

    def _make_table(self, name, columns):
        return {"name": name, "columns": [{"name": c} for c in columns]}

    def test_enrich_existing_table_with_missing_columns(self):
        tpl = get_template("retail")
        existing = [self._make_table("Sales", ["TransactionID", "Revenue"])]
        result = apply_template(tpl, existing)
        # Should have added columns not present in existing
        sales_table = [t for t in result["tables"] if t["name"] == "Sales"][0]
        col_names = {c["name"] for c in sales_table["columns"]}
        self.assertIn("ProductID", col_names)
        self.assertGreater(result["stats"]["columns_added"], 0)

    def test_adds_skeleton_tables(self):
        tpl = get_template("retail")
        existing = [self._make_table("Sales", ["TransactionID"])]
        result = apply_template(tpl, existing)
        table_names = {t["name"] for t in result["tables"]}
        self.assertIn("Products", table_names)
        self.assertGreater(result["stats"]["new_tables"], 0)

    def test_relationships_filtered_by_existing_tables(self):
        tpl = get_template("retail")
        # Only Sales and Products exist → relationship Sales→Products should be included
        existing = [
            self._make_table("Sales", ["ProductID"]),
            self._make_table("Products", ["ProductID"]),
        ]
        result = apply_template(tpl, existing)
        rel_from_tables = {r["from"].split(".")[0] for r in result["relationships"]}
        # All relationships should reference tables that exist
        table_names_lower = {t["name"].lower() for t in result["tables"]}
        for rel in result["relationships"]:
            from_t = rel["from"].split(".")[0].lower()
            to_t = rel["to"].split(".")[0].lower()
            self.assertIn(from_t, table_names_lower)
            self.assertIn(to_t, table_names_lower)

    def test_stats_returned(self):
        tpl = get_template("healthcare")
        existing = []
        result = apply_template(tpl, existing)
        stats = result["stats"]
        self.assertIn("new_tables", stats)
        self.assertIn("columns_added", stats)
        self.assertIn("measures_added", stats)
        self.assertIn("relationships_added", stats)
        self.assertIn("hierarchies_added", stats)
        self.assertEqual(stats["new_tables"], len(tpl["tables"]))

    def test_measures_always_added(self):
        tpl = get_template("finance")
        existing = []
        result = apply_template(tpl, existing)
        self.assertGreater(len(result["measures"]), 0)
        self.assertEqual(len(result["measures"]), len(tpl["measures"]))


if __name__ == "__main__":
    unittest.main()
