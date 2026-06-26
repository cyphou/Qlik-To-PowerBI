"""Tests for powerbi_import.migration_report — MigrationReport class.

Covers:
- add_item (valid/invalid status, optional fields)
- _classify_dax (unsupported, approximate, source-leak, exact, skipped)
- add_calculations (DAX lookup cascade, 4 strategies)
- add_visuals, add_parameters, add_relationships, add_hierarchies
- add_sets, add_groups, add_bins, add_stories
- add_user_filters, add_datasources
- get_summary (fidelity scoring, cache invalidation)
- save (creates dir, JSON file), to_dict
"""

import json
import os
import pytest
from powerbi_import.migration_report import MigrationReport


# ═══════════════════════════════════════════════════════════════
#  add_item basics
# ═══════════════════════════════════════════════════════════════

class TestAddItem:
    def test_valid_status(self):
        r = MigrationReport("test")
        r.add_item("calculation", "Profit", "exact", dax="SUM('T'[Profit])")
        assert len(r.items) == 1
        assert r.items[0]["status"] == "exact"
        assert r.items[0]["dax"] == "SUM('T'[Profit])"

    def test_all_statuses(self):
        r = MigrationReport("test")
        for s in ("exact", "approximate", "placeholder", "unsupported", "skipped"):
            r.add_item("x", f"item_{s}", s)
        assert len(r.items) == 5

    def test_invalid_status_raises(self):
        r = MigrationReport("test")
        with pytest.raises(ValueError, match="Invalid status"):
            r.add_item("calculation", "X", "bad_status")

    def test_optional_fields_omitted(self):
        r = MigrationReport("test")
        r.add_item("visual", "Sheet1", "exact")
        assert "dax" not in r.items[0]
        assert "note" not in r.items[0]
        assert "source_formula" not in r.items[0]

    def test_optional_fields_present(self):
        r = MigrationReport("test")
        r.add_item("calculation", "Profit", "exact",
                    dax="SUM(X)", note="good", source_formula="Sum(X)")
        assert r.items[0]["dax"] == "SUM(X)"
        assert r.items[0]["note"] == "good"
        assert r.items[0]["source_formula"] == "Sum(X)"


# ═══════════════════════════════════════════════════════════════
#  _classify_dax
# ═══════════════════════════════════════════════════════════════

class TestClassifyDax:
    def test_none_returns_skipped(self):
        assert MigrationReport._classify_dax(None) == "skipped"

    def test_empty_returns_skipped(self):
        assert MigrationReport._classify_dax("") == "skipped"

    def test_clean_dax_exact(self):
        assert MigrationReport._classify_dax("SUM('Sales'[Amount])") == "exact"

    def test_unsupported_makepoint(self):
        assert MigrationReport._classify_dax("/* MAKEPOINT unsupported */") == "unsupported"

    def test_unsupported_script(self):
        assert MigrationReport._classify_dax("/* SCRIPT_REAL ... */") == "unsupported"

    def test_approximate_placeholder(self):
        assert MigrationReport._classify_dax("/* placeholder */ SUM(X)") == "approximate"

    def test_approximate_manual(self):
        assert MigrationReport._classify_dax("/* manual conversion needed */ X") == "approximate"

    def test_source_leak_countd(self):
        assert MigrationReport._classify_dax("COUNTD(X)") == "approximate"

    def test_source_leak_zn(self):
        assert MigrationReport._classify_dax("ZN([Sales])") == "approximate"

    def test_source_leak_ifnull(self):
        assert MigrationReport._classify_dax("IFNULL(X, 0)") == "approximate"

    def test_unsupported_beats_approximate(self):
        # Unsupported patterns have higher priority
        dax = "/* MAKEPOINT unsupported */ /* placeholder */ X"
        assert MigrationReport._classify_dax(dax) == "unsupported"


# ═══════════════════════════════════════════════════════════════
#  add_calculations
# ═══════════════════════════════════════════════════════════════

class TestAddCalculations:
    def test_empty_list(self):
        r = MigrationReport("test")
        r.add_calculations([], {})
        assert len(r.items) == 0

    def test_lookup_by_name(self):
        r = MigrationReport("test")
        calcs = [{"name": "Total", "caption": "Total Sales", "formula": "Sum(Sales)"}]
        calc_map = {"Total Sales": "SUM('T'[Sales])"}
        r.add_calculations(calcs, calc_map)
        assert r.items[0]["status"] == "exact"
        assert r.items[0]["dax"] == "SUM('T'[Sales])"

    def test_lookup_by_id(self):
        r = MigrationReport("test")
        calcs = [{"name": "[Total]", "caption": "My Total", "formula": "Sum(X)"}]
        calc_map = {"[Total]": "SUM('T'[X])"}
        r.add_calculations(calcs, calc_map)
        assert r.items[0]["status"] == "exact"

    def test_lookup_by_clean_id(self):
        r = MigrationReport("test")
        calcs = [{"name": "[Profit]", "formula": "Sum(P)"}]
        calc_map = {"Profit": "SUM('T'[P])"}
        r.add_calculations(calcs, calc_map)
        assert r.items[0]["status"] == "exact"

    def test_no_dax_skipped(self):
        r = MigrationReport("test")
        calcs = [{"name": "Missing", "formula": "Sum(?)"}]
        r.add_calculations(calcs, {})
        assert r.items[0]["status"] == "skipped"

    def test_unsupported_dax_classified(self):
        r = MigrationReport("test")
        calcs = [{"name": "Geo", "formula": "MAKEPOINT(lat,lon)"}]
        calc_map = {"Geo": "/* MAKEPOINT unsupported */"}
        r.add_calculations(calcs, calc_map)
        assert r.items[0]["status"] == "unsupported"


# ═══════════════════════════════════════════════════════════════
#  add_visuals
# ═══════════════════════════════════════════════════════════════

class TestAddVisuals:
    def test_exact_mapping(self):
        r = MigrationReport("test")
        ws = [{"name": "Sheet1", "mark_type": "bar"}]
        vmap = {"bar": "clusteredBarChart"}
        r.add_visuals(ws, vmap)
        assert r.items[0]["status"] == "exact"

    def test_fallback_to_tableex(self):
        r = MigrationReport("test")
        ws = [{"name": "Sheet1", "mark_type": "mekko"}]
        vmap = {"mekko": "tableEx"}
        r.add_visuals(ws, vmap)
        assert r.items[0]["status"] == "approximate"

    def test_no_mark_type(self):
        r = MigrationReport("test")
        ws = [{"name": "Sheet1"}]
        r.add_visuals(ws)
        assert len(r.items) == 1


# ═══════════════════════════════════════════════════════════════
#  Bulk add methods
# ═══════════════════════════════════════════════════════════════

class TestBulkAddMethods:
    def test_add_parameters(self):
        r = MigrationReport("test")
        r.add_parameters([{"name": "Year", "domain_type": "range"}])
        assert r.items[0]["category"] == "parameter"
        assert "domain=range" in r.items[0]["note"]

    def test_add_relationships(self):
        r = MigrationReport("test")
        r.add_relationships([{"fromTable": "Orders", "toTable": "Customers",
                              "cardinality": "manyToOne"}])
        assert "Orders → Customers" in r.items[0]["name"]
        assert r.items[0]["status"] == "exact"

    def test_add_hierarchies(self):
        r = MigrationReport("test")
        r.add_hierarchies([{"name": "DateHier", "levels": ["Year", "Month", "Day"]}])
        assert "3 levels" in r.items[0]["note"]

    def test_add_sets(self):
        r = MigrationReport("test")
        r.add_sets([{"name": "TopCustomers"}])
        assert r.items[0]["category"] == "set"

    def test_add_groups(self):
        r = MigrationReport("test")
        r.add_groups([{"name": "AgeGroup"}])
        assert r.items[0]["category"] == "group"

    def test_add_bins(self):
        r = MigrationReport("test")
        r.add_bins([{"name": "PriceBin"}])
        assert r.items[0]["category"] == "bin"

    def test_add_stories(self):
        r = MigrationReport("test")
        r.add_stories([{"name": "Q1 Review", "story_points": [1, 2, 3]}])
        assert "3 bookmark" in r.items[0]["note"]

    def test_add_datasources(self):
        r = MigrationReport("test")
        r.add_datasources([{
            "name": "MainDB",
            "connection": {"class": "SQL Server"},
            "tables": [{"name": "t1"}, {"name": "t2"}]
        }])
        assert r.items[0]["category"] == "datasource"
        assert "2 table" in r.items[0]["note"]

    def test_add_datasources_raw_schema(self):
        """Raw extracted schema (connectionType/tableName) resolves correctly."""
        r = MigrationReport("test")
        r.add_datasources([{
            "connectionType": "sqlserver",
            "tableName": "Orders",
            "columns": [{"name": "OrderID"}],
        }])
        item = r.items[0]
        assert item["name"] == "Orders"
        assert item["note"] == "SQL Server, 1 table(s)"

    def test_add_datasources_unknown_connector(self):
        """Unrecognised connector falls back to the raw value, not '?'."""
        r = MigrationReport("test")
        r.add_datasources([{"connectionType": "fancydb", "tableName": "X"}])
        assert "fancydb" in r.items[0]["note"]
        assert "?" not in r.items[0]["note"]


# ═══════════════════════════════════════════════════════════════
#  add_user_filters
# ═══════════════════════════════════════════════════════════════

class TestAddUserFilters:
    def test_explicit_mappings(self):
        r = MigrationReport("test")
        r.add_user_filters([{"name": "Region", "user_mappings": {"alice": "West"}}])
        assert r.items[0]["status"] == "exact"

    def test_calculated_sec_ismemberof(self):
        r = MigrationReport("test")
        r.add_user_filters([{
            "name": "Region",
            "type": "calculated_security",
            "ismemberof_groups": ["Sales Team"],
            "functions_used": ["ISMEMBEROF"],
        }])
        assert r.items[0]["status"] == "approximate"

    def test_calculated_sec_username(self):
        r = MigrationReport("test")
        r.add_user_filters([{
            "name": "Region",
            "type": "calculated_security",
            "functions_used": ["USERNAME"],
        }])
        assert r.items[0]["status"] == "exact"

    def test_plain_user_filter(self):
        r = MigrationReport("test")
        r.add_user_filters([{"name": "Region"}])
        assert r.items[0]["status"] == "exact"
        assert "USERPRINCIPALNAME" in r.items[0]["note"]


# ═══════════════════════════════════════════════════════════════
#  get_summary & fidelity scoring
# ═══════════════════════════════════════════════════════════════

class TestGetSummary:
    def test_empty_report_fidelity_100(self):
        r = MigrationReport("test")
        s = r.get_summary()
        assert s["fidelity_score"] == 100.0
        assert s["total_items"] == 0

    def test_all_exact_fidelity_100(self):
        r = MigrationReport("test")
        for i in range(5):
            r.add_item("calc", f"c{i}", "exact")
        assert r.get_summary()["fidelity_score"] == 100.0

    def test_all_approximate_fidelity_50(self):
        r = MigrationReport("test")
        for i in range(4):
            r.add_item("calc", f"c{i}", "approximate")
        assert r.get_summary()["fidelity_score"] == 50.0

    def test_all_unsupported_fidelity_0(self):
        r = MigrationReport("test")
        for i in range(3):
            r.add_item("calc", f"c{i}", "unsupported")
        assert r.get_summary()["fidelity_score"] == 0.0

    def test_mixed_fidelity(self):
        r = MigrationReport("test")
        r.add_item("calc", "a", "exact")           # 100
        r.add_item("calc", "b", "approximate")     # 50
        # fidelity = (100 + 50) / 2 = 75.0
        assert r.get_summary()["fidelity_score"] == 75.0

    def test_by_category(self):
        r = MigrationReport("test")
        r.add_item("calculation", "a", "exact")
        r.add_item("visual", "b", "approximate")
        s = r.get_summary()
        assert "calculation" in s["by_category"]
        assert "visual" in s["by_category"]

    def test_cache_invalidation(self):
        r = MigrationReport("test")
        r.add_item("calc", "a", "exact")
        s1 = r.get_summary()
        assert s1["total_items"] == 1
        r.add_item("calc", "b", "unsupported")
        s2 = r.get_summary()
        assert s2["total_items"] == 2
        assert s2["fidelity_score"] < s1["fidelity_score"]


# ═══════════════════════════════════════════════════════════════
#  to_dict / save
# ═══════════════════════════════════════════════════════════════

class TestSerialisation:
    def test_to_dict_structure(self):
        r = MigrationReport("my_app")
        r.add_item("calc", "X", "exact", dax="SUM(X)")
        d = r.to_dict()
        assert d["report_name"] == "my_app"
        assert "summary" in d
        assert "items" in d
        assert len(d["items"]) == 1

    def test_save_creates_file(self, tmp_path):
        r = MigrationReport("save_test")
        r.add_item("calc", "Y", "exact")
        path = r.save(str(tmp_path))
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["report_name"] == "save_test"
        assert len(data["items"]) == 1

    def test_save_creates_directory(self, tmp_path):
        out = str(tmp_path / "nested" / "dir")
        r = MigrationReport("nested_test")
        path = r.save(out)
        assert os.path.exists(path)
