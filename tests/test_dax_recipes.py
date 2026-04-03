"""Tests for powerbi_import.dax_recipes — industry KPI measure templates."""

import unittest

from powerbi_import.dax_recipes import (
    get_industry_recipes,
    list_industries,
    get_all_recipes,
    apply_recipes,
    recipes_to_marketplace_format,
)


class TestGetIndustryRecipes(unittest.TestCase):
    """Test recipe retrieval per industry."""

    def test_healthcare_returns_6_recipes(self):
        recipes = get_industry_recipes("healthcare")
        self.assertEqual(len(recipes), 6)

    def test_finance_returns_8_recipes(self):
        recipes = get_industry_recipes("finance")
        self.assertEqual(len(recipes), 8)

    def test_retail_returns_7_recipes(self):
        recipes = get_industry_recipes("retail")
        self.assertEqual(len(recipes), 7)

    def test_unknown_industry_returns_empty(self):
        recipes = get_industry_recipes("unknown")
        self.assertEqual(recipes, [])

    def test_case_insensitive_lookup(self):
        recipes = get_industry_recipes("Healthcare")
        self.assertEqual(len(recipes), 6)

    def test_recipes_have_required_keys(self):
        for industry in list_industries():
            for recipe in get_industry_recipes(industry):
                self.assertIn("name", recipe)
                self.assertIn("dax", recipe)
                self.assertIn("tags", recipe)

    def test_returns_copy_not_reference(self):
        r1 = get_industry_recipes("healthcare")
        r2 = get_industry_recipes("healthcare")
        r1.append({"name": "extra"})
        self.assertNotEqual(len(r1), len(r2))


class TestListIndustries(unittest.TestCase):
    def test_returns_three_industries(self):
        industries = list_industries()
        self.assertEqual(set(industries), {"healthcare", "finance", "retail"})


class TestGetAllRecipes(unittest.TestCase):
    def test_total_count(self):
        all_recipes = get_all_recipes()
        self.assertEqual(len(all_recipes), 6 + 8 + 7)  # 21

    def test_all_have_dax(self):
        for recipe in get_all_recipes():
            self.assertTrue(recipe["dax"], f"Recipe {recipe['name']} has no DAX")


class TestApplyRecipes(unittest.TestCase):
    """Test recipe application to measures dict."""

    def test_inject_new_measures(self):
        measures = {"Existing": "SUM('T'[X])"}
        recipes = [{"name": "New KPI", "dax": "AVERAGE('T'[Y])"}]
        changes = apply_recipes(measures, recipes)
        self.assertIn("New KPI", measures)
        self.assertEqual(changes["New KPI"]["action"], "injected")

    def test_skip_existing_when_no_overwrite(self):
        measures = {"Revenue": "SUM('T'[Rev])"}
        recipes = [{"name": "Revenue", "dax": "REPLACED FORMULA"}]
        changes = apply_recipes(measures, recipes, overwrite=False)
        self.assertEqual(measures["Revenue"], "SUM('T'[Rev])")
        self.assertEqual(changes["Revenue"]["action"], "skipped")

    def test_overwrite_existing(self):
        measures = {"Revenue": "SUM('T'[Rev])"}
        recipes = [{"name": "Revenue", "dax": "NEW FORMULA"}]
        changes = apply_recipes(measures, recipes, overwrite=True)
        self.assertEqual(measures["Revenue"], "NEW FORMULA")
        self.assertEqual(changes["Revenue"]["action"], "injected")

    def test_regex_replacement(self):
        measures = {"M1": "SUM('OldTable'[Col])"}
        recipes = [{"name": "rename", "match": r"OldTable", "replacement": "NewTable"}]
        changes = apply_recipes(measures, recipes)
        self.assertIn("NewTable", measures["M1"])
        self.assertEqual(changes["M1"]["action"], "replaced")

    def test_empty_recipes_no_change(self):
        measures = {"A": "SUM('T'[X])"}
        changes = apply_recipes(measures, [])
        self.assertEqual(changes, {})
        self.assertEqual(len(measures), 1)


class TestRecipesToMarketplaceFormat(unittest.TestCase):
    def test_healthcare_marketplace_format(self):
        patterns = recipes_to_marketplace_format("healthcare")
        self.assertEqual(len(patterns), 6)
        for p in patterns:
            self.assertIn("metadata", p)
            self.assertIn("payload", p)
            self.assertIn("name", p["metadata"])
            self.assertEqual(p["metadata"]["category"], "dax_recipe")

    def test_unknown_industry_empty(self):
        patterns = recipes_to_marketplace_format("unknown")
        self.assertEqual(patterns, [])


if __name__ == "__main__":
    unittest.main()
