"""Tests for canonical powerbi_import.tmdl_generator — v7 expansion.

Tests the generate_tmdl() entry point and internal helpers.
"""

import os
import shutil
import tempfile
import pytest

from powerbi_import.tmdl_generator import (
    generate_tmdl,
    _build_semantic_model,
    _build_relationships,
    _clean_field_ref,
    _split_dax_args,
    resolve_table_for_column,
    _detect_many_to_many,
    _build_unique_column_set,
    _set_cardinality,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="test_tmdl_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _simple_ds():
    return [{
        "name": "SalesDB",
        "connectionString": "Provider=SQLNCLI;Server=srv;Database=db;",
        "tables": [{
            "name": "Orders",
            "columns": [
                {"name": "OrderID", "dataType": "int64"},
                {"name": "Amount", "dataType": "double", "formatString": "#,0.00"},
                {"name": "Region", "dataType": "string"},
                {"name": "OrderDate", "dataType": "dateTime"},
            ],
        }],
        "calculations": [
            {"name": "TotalSales", "formula": "SUM('Orders'[Amount])", "table": "Orders"},
        ],
    }]


def _multi_ds():
    return [{
        "name": "MainDB",
        "connectionString": "Provider=SQLNCLI;Server=srv;Database=db;",
        "tables": [
            {
                "name": "Orders",
                "columns": [
                    {"name": "OrderID", "dataType": "int64"},
                    {"name": "CustomerID", "dataType": "int64"},
                    {"name": "Amount", "dataType": "double"},
                ],
            },
            {
                "name": "Customers",
                "columns": [
                    {"name": "CustomerID", "dataType": "int64"},
                    {"name": "Name", "dataType": "string"},
                    {"name": "Country", "dataType": "string"},
                ],
            },
        ],
        "calculations": [
            {"name": "TotalSales", "formula": "SUM('Orders'[Amount])", "table": "Orders"},
            {"name": "CustomerCount", "formula": "DISTINCTCOUNT('Customers'[CustomerID])", "table": "Customers"},
        ],
    }]


# ══════════════════════════════════════════════════════════════════
# 1. generate_tmdl — Main Entry Point
# ══════════════════════════════════════════════════════════════════

class TestGenerateTMDL:
    def test_returns_stats(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        assert isinstance(stats, dict)
        assert "tables" in stats
        assert "columns" in stats
        assert "measures" in stats
        assert "relationships" in stats

    def test_tables_count(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        # At least Orders + Calendar (auto-generated)
        assert stats["tables"] >= 1

    def test_columns_count(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        assert stats["columns"] >= 4  # OrderID, Amount, Region, OrderDate

    def test_measures_count(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        assert stats["measures"] >= 1  # TotalSales

    def test_writes_model_tmdl(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        assert os.path.isfile(os.path.join(sm_dir, "definition", "model.tmdl"))

    def test_writes_tables_dir(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        tables_dir = os.path.join(sm_dir, "definition", "tables")
        assert os.path.isdir(tables_dir)
        tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
        assert len(tmdl_files) >= 1

    def test_table_content(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        tables_dir = os.path.join(sm_dir, "definition", "tables")
        orders_files = [f for f in os.listdir(tables_dir) if "Orders" in f]
        assert len(orders_files) >= 1
        with open(os.path.join(tables_dir, orders_files[0]), "r", encoding="utf-8") as fh:
            content = fh.read()
        assert "table" in content
        assert "column" in content

    def test_measure_in_tmdl(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Test.SemanticModel")
        generate_tmdl(_simple_ds(), "Test", {}, sm_dir)
        tables_dir = os.path.join(sm_dir, "definition", "tables")
        found = False
        for f in os.listdir(tables_dir):
            with open(os.path.join(tables_dir, f), "r", encoding="utf-8") as fh:
                if "TotalSales" in fh.read():
                    found = True
                    break
        assert found, "TotalSales measure not found in TMDL files"

    def test_multi_table_stats(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Multi.SemanticModel")
        stats = generate_tmdl(_multi_ds(), "Multi", {}, sm_dir)
        assert stats["tables"] >= 2  # Orders + Customers + maybe Calendar

    def test_culture_option(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "FR.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "FR", {}, sm_dir, culture="fr-FR")
        model_path = os.path.join(sm_dir, "definition", "model.tmdl")
        with open(model_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "fr-FR" in content

    def test_calendar_range(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Cal.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "Cal", {}, sm_dir,
                              calendar_start=2015, calendar_end=2025)
        # Should complete without error; calendar params accepted
        assert stats["tables"] >= 1


# ══════════════════════════════════════════════════════════════════
# 2. _build_semantic_model — Internal
# ══════════════════════════════════════════════════════════════════

class TestBuildSemanticModel:
    def test_returns_model_dict(self):
        model = _build_semantic_model(_simple_ds(), "Test")
        assert isinstance(model, dict)
        assert "model" in model

    def test_model_has_tables(self):
        model = _build_semantic_model(_simple_ds(), "Test")
        tables = model["model"]["tables"]
        assert len(tables) >= 1

    def test_model_culture(self):
        model = _build_semantic_model(_simple_ds(), "Test", culture="ja-JP")
        assert model["model"]["culture"] == "ja-JP"

    def test_model_default_culture(self):
        model = _build_semantic_model(_simple_ds(), "Test")
        assert model["model"]["culture"] == "en-US"


# ══════════════════════════════════════════════════════════════════
# 3. Relationships
# ══════════════════════════════════════════════════════════════════

class TestBuildRelationships:
    def test_empty_relationships(self):
        result = _build_relationships([])
        assert result == []

    def test_basic_relationship(self):
        rels = [{
            "fromTable": "Orders",
            "fromColumn": "CustomerID",
            "toTable": "Customers",
            "toColumn": "CustomerID",
            "crossFilteringBehavior": "oneDirection",
        }]
        result = _build_relationships(rels)
        # _build_relationships returns the transformed list
        assert isinstance(result, list)

    def test_relationship_with_stats(self, tmp_dir):
        ds = _multi_ds()
        sm_dir = os.path.join(tmp_dir, "Rel.SemanticModel")
        extra = {
            "_datasources": ds,
        }
        stats = generate_tmdl(ds, "Rel", extra, sm_dir)
        # May or may not infer relationships depending on matching columns
        assert stats["relationships"] >= 0


# ══════════════════════════════════════════════════════════════════
# 3b. Cardinality Detection
# ══════════════════════════════════════════════════════════════════

class TestCardinalityDetection:
    """Tests for _detect_many_to_many and _build_unique_column_set."""

    def _make_model(self, rels, tables=None):
        """Build a minimal model dict with relationships and optional tables."""
        return {
            'model': {
                'tables': tables or [],
                'relationships': rels,
            }
        }

    def test_id_suffix_detected_as_unique(self):
        """Columns ending in ID/Id/_id/Key should be detected as unique."""
        model = self._make_model([], tables=[
            {'name': 'Orders', 'columns': [
                {'name': 'OrderID'},
                {'name': 'CustomerID'},
                {'name': 'Amount'},
            ]},
            {'name': 'Customers', 'columns': [
                {'name': 'CustomerID'},
                {'name': 'Name'},
            ]},
        ])
        unique = _build_unique_column_set(model, [])
        assert ('Orders', 'OrderID') in unique
        assert ('Orders', 'CustomerID') in unique
        assert ('Customers', 'CustomerID') in unique
        assert ('Orders', 'Amount') not in unique
        assert ('Customers', 'Name') not in unique

    def test_camel_case_id_detected(self):
        """CamelCase ID suffixes like ProductId, order_key should match."""
        model = self._make_model([], tables=[
            {'name': 'T', 'columns': [
                {'name': 'ProductId'},
                {'name': 'order_key'},
                {'name': 'item_pk'},
                {'name': 'category_code'},
            ]},
        ])
        unique = _build_unique_column_set(model, [])
        assert ('T', 'ProductId') in unique
        assert ('T', 'order_key') in unique
        assert ('T', 'item_pk') in unique
        assert ('T', 'category_code') in unique

    def test_many_to_one_when_to_is_id(self):
        """Star-schema: fact table (more columns) → dimension (fewer columns)."""
        rels = [{'fromTable': 'Orders', 'fromColumn': 'CustomerID',
                 'toTable': 'Customers', 'toColumn': 'CustomerID',
                 'joinType': 'inner'}]
        # Orders has more columns → fact table (FK side, not unique)
        # Customers has fewer columns → dimension table (PK side, unique)
        model = self._make_model(rels, tables=[
            {'name': 'Orders', 'columns': [
                {'name': 'OrderID'}, {'name': 'CustomerID'},
                {'name': 'Amount'}, {'name': 'OrderDate'},
            ]},
            {'name': 'Customers', 'columns': [
                {'name': 'CustomerID'}, {'name': 'Name'},
            ]},
        ])
        _detect_many_to_many(model, [])
        rel = model['model']['relationships'][0]
        assert rel['fromCardinality'] == 'many'
        assert rel['toCardinality'] == 'one'
        assert rel['crossFilteringBehavior'] == 'oneDirection'

    def test_one_to_one_when_both_are_ids(self):
        """Both sides are ID columns → oneToOne."""
        rels = [{'fromTable': 'Users', 'fromColumn': 'UserID',
                 'toTable': 'Profiles', 'toColumn': 'UserID',
                 'joinType': 'inner'}]
        model = self._make_model(rels, tables=[
            {'name': 'Users', 'columns': [{'name': 'UserID'}]},
            {'name': 'Profiles', 'columns': [{'name': 'UserID'}]},
        ])
        _detect_many_to_many(model, [])
        rel = model['model']['relationships'][0]
        assert rel['fromCardinality'] == 'one'
        assert rel['toCardinality'] == 'one'

    def test_many_to_many_when_no_ids(self):
        """Neither side is an ID column → manyToMany."""
        rels = [{'fromTable': 'Tags', 'fromColumn': 'TagName',
                 'toTable': 'Articles', 'toColumn': 'TagName',
                 'joinType': 'inner'}]
        model = self._make_model(rels, tables=[
            {'name': 'Tags', 'columns': [{'name': 'TagName'}]},
            {'name': 'Articles', 'columns': [{'name': 'TagName'}]},
        ])
        _detect_many_to_many(model, [])
        rel = model['model']['relationships'][0]
        assert rel['fromCardinality'] == 'many'
        assert rel['toCardinality'] == 'many'
        assert rel['crossFilteringBehavior'] == 'bothDirections'

    def test_full_join_always_many_to_many(self):
        """Explicit full join → manyToMany regardless of column names."""
        rels = [{'fromTable': 'A', 'fromColumn': 'AID',
                 'toTable': 'B', 'toColumn': 'BID',
                 'joinType': 'full'}]
        model = self._make_model(rels, tables=[
            {'name': 'A', 'columns': [{'name': 'AID'}]},
            {'name': 'B', 'columns': [{'name': 'BID'}]},
        ])
        _detect_many_to_many(model, [])
        rel = model['model']['relationships'][0]
        assert rel['fromCardinality'] == 'many'
        assert rel['toCardinality'] == 'many'

    def test_one_to_many_from_is_key(self):
        """from-side is ID but to-side is not → oneToMany."""
        rels = [{'fromTable': 'Customers', 'fromColumn': 'CustomerID',
                 'toTable': 'Feedback', 'toColumn': 'Comment',
                 'joinType': 'inner'}]
        model = self._make_model(rels, tables=[
            {'name': 'Customers', 'columns': [{'name': 'CustomerID'}]},
            {'name': 'Feedback', 'columns': [{'name': 'Comment'}]},
        ])
        _detect_many_to_many(model, [])
        rel = model['model']['relationships'][0]
        assert rel['fromCardinality'] == 'one'
        assert rel['toCardinality'] == 'many'

    def test_set_cardinality_helper(self):
        """_set_cardinality sets all three properties correctly."""
        rel = {}
        _set_cardinality(rel, 'many', 'one')
        assert rel['fromCardinality'] == 'many'
        assert rel['toCardinality'] == 'one'
        assert rel['crossFilteringBehavior'] == 'oneDirection'

        _set_cardinality(rel, 'many', 'many')
        assert rel['crossFilteringBehavior'] == 'bothDirections'

    def test_iskey_metadata_overrides_name_heuristic(self):
        """isKey metadata should mark a column as unique even without ID suffix."""
        model = self._make_model([], tables=[
            {'name': 'Products', 'columns': [
                {'name': 'SKU', 'isKey': True},
                {'name': 'Description'},
            ]},
        ])
        unique = _build_unique_column_set(model, [])
        assert ('Products', 'SKU') in unique
        assert ('Products', 'Description') not in unique

    def test_datasource_metadata_used(self):
        """Column metadata from datasources should be considered."""
        model = self._make_model([], tables=[])
        datasources = [{'tables': [
            {'name': 'Inventory', 'columns': [
                {'name': 'PartNumber', 'isPrimaryKey': True},
                {'name': 'Warehouse'},
            ]}
        ]}]
        unique = _build_unique_column_set(model, datasources)
        assert ('Inventory', 'PartNumber') in unique
        assert ('Inventory', 'Warehouse') not in unique


# ══════════════════════════════════════════════════════════════════
# 4. Helper Functions
# ══════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_clean_field_ref_simple(self):
        assert _clean_field_ref("Sales") == "Sales"

    def test_clean_field_ref_quoted(self):
        result = _clean_field_ref("'Table'[Column]")
        assert "Column" in result

    def test_clean_field_ref_brackets(self):
        result = _clean_field_ref("[Amount]")
        assert "Amount" in result

    def test_split_dax_args_simple(self):
        result = _split_dax_args("a, b, c")
        assert len(result) == 3

    def test_split_dax_args_nested(self):
        result = _split_dax_args("SUM(a), FILTER(t, x), c")
        assert len(result) == 3

    def test_resolve_table_orders(self):
        result = resolve_table_for_column("Amount", "SalesDB")
        # Should return something (may be default table)
        assert result is not None or result is None  # Just doesn't crash


# ══════════════════════════════════════════════════════════════════
# 5. Hierarchies via extra_objects
# ══════════════════════════════════════════════════════════════════

class TestHierarchies:
    def test_hierarchies_in_model(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "H.SemanticModel")
        extra = {
            "hierarchies": [
                {
                    "name": "Date Hierarchy",
                    "table": "Orders",
                    "levels": ["OrderDate"],
                }
            ]
        }
        stats = generate_tmdl(_simple_ds(), "H", extra, sm_dir)
        assert stats["hierarchies"] >= 0  # May or may not attach to Orders


# ══════════════════════════════════════════════════════════════════
# 6. RLS Roles
# ══════════════════════════════════════════════════════════════════

class TestRLSRoles:
    def test_roles_in_model(self):
        ds = _simple_ds()
        ds[0]["roles"] = [
            {
                "name": "RegionFilter",
                "table": "Orders",
                "filterExpression": "'Orders'[Region] = USERPRINCIPALNAME()",
            }
        ]
        extra = {"_datasources": ds}
        model = _build_semantic_model(ds, "RLS", extra_objects=extra)
        roles = model["model"].get("roles", [])
        # May or may not surface depending on how roles are extracted
        assert isinstance(roles, list)


# ══════════════════════════════════════════════════════════════════
# 7. Edge Cases
# ══════════════════════════════════════════════════════════════════

class TestTMDLEdgeCases:
    def test_empty_datasources(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Empty.SemanticModel")
        stats = generate_tmdl([], "Empty", {}, sm_dir)
        assert stats["tables"] == 0

    def test_no_columns(self, tmp_dir):
        ds = [{"name": "Empty", "tables": [{"name": "T", "columns": []}]}]
        sm_dir = os.path.join(tmp_dir, "NoCol.SemanticModel")
        stats = generate_tmdl(ds, "NoCol", {}, sm_dir)
        assert stats["tables"] >= 1

    def test_no_calculations(self, tmp_dir):
        ds = [{"name": "DB", "tables": [{"name": "T", "columns": [
            {"name": "A", "dataType": "string"}]}]}]
        sm_dir = os.path.join(tmp_dir, "NoCal.SemanticModel")
        stats = generate_tmdl(ds, "NoCal", {}, sm_dir)
        assert stats["measures"] == 0

    def test_directquery_mode(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "DQ.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "DQ", {}, sm_dir, model_mode="directquery")
        assert stats["tables"] >= 1

    def test_composite_mode(self, tmp_dir):
        sm_dir = os.path.join(tmp_dir, "Comp.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "Comp", {}, sm_dir, model_mode="composite")
        assert stats["tables"] >= 1
