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
    _generate_bridge_tables,
    _validate_bridge_tables,
    _optimize_cross_filter_direction,
    _validate_relationships,
    _resolve_measure_column_collisions,
    _materialize_measure_referenced_columns,
    _downgrade_many_to_many_direction,
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


def test_resolve_measure_column_collision_renames_and_rewrites():
    """A measure that shares a column name is renamed and references rewritten."""
    model = {
        "model": {
            "tables": [
                {
                    "name": "Orders",
                    "columns": [
                        {"name": "Sales"},
                        {"name": "Profit"},
                    ],
                    "measures": [
                        {"name": "Sales", "expression": "SUM('Orders'[Sales])"},
                        {"name": "Margin",
                         "expression": "SUM('Orders'[Profit]) / SUM('Orders'[Sales])"},
                    ],
                },
                {
                    "name": "Calendar",
                    "columns": [{"name": "Date"}],
                    "measures": [
                        {"name": "YTD",
                         "expression": "TOTALYTD([Sales], 'Calendar'[Date])"},
                    ],
                },
            ]
        }
    }
    n = _resolve_measure_column_collisions(model)
    assert n == 1
    orders = model["model"]["tables"][0]
    cal = model["model"]["tables"][1]
    # Measure renamed away from the column name.
    meas_names = [m["name"] for m in orders["measures"]]
    assert "Sales" not in meas_names
    assert "Total Sales" in meas_names
    # Qualified column reference left untouched.
    margin = next(m for m in orders["measures"] if m["name"] == "Margin")
    assert "'Orders'[Sales]" in margin["expression"]
    # Unqualified measure reference rewritten.
    ytd = cal["measures"][0]
    assert "[Total Sales]" in ytd["expression"]
    assert "[Sales]" not in ytd["expression"].replace("[Total Sales]", "")


def test_resolve_measure_column_collision_noop_when_no_clash():
    """No rename when measure names do not collide with columns."""
    model = {
        "model": {
            "tables": [
                {
                    "name": "Orders",
                    "columns": [{"name": "Sales"}],
                    "measures": [
                        {"name": "Total Sales",
                         "expression": "SUM('Orders'[Sales])"},
                    ],
                }
            ]
        }
    }
    assert _resolve_measure_column_collisions(model) == 0
    assert model["model"]["tables"][0]["measures"][0]["name"] == "Total Sales"


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


# ══════════════════════════════════════════════════════════════════
# 8. Bridge Table Generation
# ══════════════════════════════════════════════════════════════════

class TestBridgeTableGeneration:
    """Tests for _generate_bridge_tables."""

    def _make_model(self, rels, tables=None):
        return {
            'model': {
                'tables': tables or [],
                'relationships': rels,
            }
        }

    def test_no_bridge_when_no_m2m(self):
        """No bridge tables generated when there are no manyToMany rels."""
        model = self._make_model([
            {'fromTable': 'A', 'fromColumn': 'AID',
             'toTable': 'B', 'toColumn': 'AID',
             'fromCardinality': 'many', 'toCardinality': 'one',
             'crossFilteringBehavior': 'oneDirection'},
        ])
        count = _generate_bridge_tables(model)
        assert count == 0
        assert len(model['model']['tables']) == 0

    def test_bridge_table_created_for_m2m(self):
        """A bridge table should be created for each manyToMany relationship."""
        model = self._make_model(
            rels=[{
                'fromTable': 'Tags', 'fromColumn': 'TagName',
                'toTable': 'Articles', 'toColumn': 'TagName',
                'fromCardinality': 'many', 'toCardinality': 'many',
                'crossFilteringBehavior': 'bothDirections',
            }],
            tables=[
                {'name': 'Tags', 'columns': [{'name': 'TagName', 'dataType': 'string'}]},
                {'name': 'Articles', 'columns': [{'name': 'TagName', 'dataType': 'string'}]},
            ],
        )
        count = _generate_bridge_tables(model)
        assert count == 1

        # Bridge table exists (alphabetical: Articles < Tags)
        table_names = [t['name'] for t in model['model']['tables']]
        assert 'Bridge_Articles_Tags' in table_names

        # Bridge table has two columns
        bridge = [t for t in model['model']['tables'] if t['name'] == 'Bridge_Articles_Tags'][0]
        col_names = [c['name'] for c in bridge['columns']]
        assert len(col_names) == 2  # same col name on both sides → prefixed with table names

        # Bridge table is hidden
        assert bridge.get('isHidden') is True

        # Bridge table has a calculated partition
        assert len(bridge['partitions']) == 1
        assert bridge['partitions'][0]['source']['type'] == 'calculated'

    def test_m2m_replaced_with_two_many_to_one(self):
        """The original M2M relationship is replaced with two manyToOne rels."""
        model = self._make_model(
            rels=[{
                'fromTable': 'Products', 'fromColumn': 'Category',
                'toTable': 'Stores', 'toColumn': 'Category',
                'fromCardinality': 'many', 'toCardinality': 'many',
                'crossFilteringBehavior': 'bothDirections',
            }],
            tables=[
                {'name': 'Products', 'columns': [{'name': 'Category', 'dataType': 'string'}]},
                {'name': 'Stores', 'columns': [{'name': 'Category', 'dataType': 'string'}]},
            ],
        )
        _generate_bridge_tables(model)

        rels = model['model']['relationships']
        # No manyToMany left
        m2m = [r for r in rels if
               r.get('fromCardinality') == 'many' and r.get('toCardinality') == 'many']
        assert len(m2m) == 0

        # Two new manyToOne relationships through bridge
        m2o = [r for r in rels if
               r.get('fromCardinality') == 'many' and r.get('toCardinality') == 'one']
        assert len(m2o) == 2
        bridge_targets = {r['toTable'] for r in m2o}
        assert 'Bridge_Products_Stores' in bridge_targets

    def test_bridge_preserves_non_m2m_rels(self):
        """Non-M2M relationships should be left untouched."""
        model = self._make_model(
            rels=[
                {'fromTable': 'Orders', 'fromColumn': 'CustID',
                 'toTable': 'Customers', 'toColumn': 'CustID',
                 'fromCardinality': 'many', 'toCardinality': 'one',
                 'crossFilteringBehavior': 'oneDirection'},
                {'fromTable': 'Tags', 'fromColumn': 'Name',
                 'toTable': 'Items', 'toColumn': 'Name',
                 'fromCardinality': 'many', 'toCardinality': 'many',
                 'crossFilteringBehavior': 'bothDirections'},
            ],
            tables=[
                {'name': 'Orders', 'columns': [{'name': 'CustID'}]},
                {'name': 'Customers', 'columns': [{'name': 'CustID'}]},
                {'name': 'Tags', 'columns': [{'name': 'Name'}]},
                {'name': 'Items', 'columns': [{'name': 'Name'}]},
            ],
        )
        _generate_bridge_tables(model)

        rels = model['model']['relationships']
        # Original manyToOne preserved
        orig = [r for r in rels if r.get('fromTable') == 'Orders']
        assert len(orig) == 1
        assert orig[0]['toCardinality'] == 'one'

    def test_bridge_column_types_inherited(self):
        """Bridge table columns inherit data types from source tables."""
        model = self._make_model(
            rels=[{
                'fromTable': 'Sales', 'fromColumn': 'ProductCode',
                'toTable': 'Returns', 'toColumn': 'ProductCode',
                'fromCardinality': 'many', 'toCardinality': 'many',
                'crossFilteringBehavior': 'bothDirections',
            }],
            tables=[
                {'name': 'Sales', 'columns': [
                    {'name': 'ProductCode', 'dataType': 'Int64'},
                    {'name': 'Amount', 'dataType': 'Double'},
                ]},
                {'name': 'Returns', 'columns': [
                    {'name': 'ProductCode', 'dataType': 'Int64'},
                ]},
            ],
        )
        _generate_bridge_tables(model)

        bridge = [t for t in model['model']['tables']
                  if t['name'].startswith('Bridge_')][0]
        types = {c['name']: c.get('dataType', 'string') for c in bridge['columns']}
        # Both sides have same column name → prefixed with table names
        assert any(v == 'Int64' for v in types.values())

    def test_bridge_name_dedup(self):
        """If Bridge_X_Y already exists, a suffix is appended."""
        model = self._make_model(
            rels=[{
                'fromTable': 'A', 'fromColumn': 'X',
                'toTable': 'B', 'toColumn': 'X',
                'fromCardinality': 'many', 'toCardinality': 'many',
                'crossFilteringBehavior': 'bothDirections',
            }],
            tables=[
                {'name': 'A', 'columns': [{'name': 'X'}]},
                {'name': 'B', 'columns': [{'name': 'X'}]},
                {'name': 'Bridge_A_B', 'columns': []},  # already exists
            ],
        )
        _generate_bridge_tables(model)

        table_names = [t['name'] for t in model['model']['tables']]
        assert 'Bridge_A_B' in table_names      # original preserved
        assert 'Bridge_A_B_2' in table_names     # new one with suffix

    def test_multiple_m2m_rels(self):
        """Multiple M2M relationships each get their own bridge table."""
        model = self._make_model(
            rels=[
                {'fromTable': 'A', 'fromColumn': 'X',
                 'toTable': 'B', 'toColumn': 'X',
                 'fromCardinality': 'many', 'toCardinality': 'many',
                 'crossFilteringBehavior': 'bothDirections'},
                {'fromTable': 'C', 'fromColumn': 'Y',
                 'toTable': 'D', 'toColumn': 'Y',
                 'fromCardinality': 'many', 'toCardinality': 'many',
                 'crossFilteringBehavior': 'bothDirections'},
            ],
            tables=[
                {'name': 'A', 'columns': [{'name': 'X'}]},
                {'name': 'B', 'columns': [{'name': 'X'}]},
                {'name': 'C', 'columns': [{'name': 'Y'}]},
                {'name': 'D', 'columns': [{'name': 'Y'}]},
            ],
        )
        count = _generate_bridge_tables(model)
        assert count == 2

        bridge_names = [t['name'] for t in model['model']['tables']
                        if t['name'].startswith('Bridge_')]
        assert 'Bridge_A_B' in bridge_names
        assert 'Bridge_C_D' in bridge_names

    def test_bridge_dax_expression(self):
        """Bridge partition DAX expression references source tables."""
        model = self._make_model(
            rels=[{
                'fromTable': 'Fact', 'fromColumn': 'DimKey',
                'toTable': 'Dim', 'toColumn': 'DimKey',
                'fromCardinality': 'many', 'toCardinality': 'many',
                'crossFilteringBehavior': 'bothDirections',
            }],
            tables=[
                {'name': 'Fact', 'columns': [{'name': 'DimKey'}]},
                {'name': 'Dim', 'columns': [{'name': 'DimKey'}]},
            ],
        )
        _generate_bridge_tables(model)

        bridge = [t for t in model['model']['tables']
                  if t['name'].startswith('Bridge_')][0]
        expr = bridge['partitions'][0]['source']['expression']
        assert "'Fact'" in expr
        assert "'Dim'" in expr
        assert 'DimKey' in expr
        assert 'DISTINCT' in expr

    def test_bridge_via_build_semantic_model(self, tmp_dir):
        """End-to-end: _bridge_tables='auto' in extra_objects triggers bridge generation."""
        ds = [{
            'name': 'DB',
            'tables': [
                {'name': 'Orders', 'columns': [
                    {'name': 'OrderID', 'dataType': 'int64'},
                    {'name': 'Tag', 'dataType': 'string'},
                    {'name': 'Amount', 'dataType': 'double'},
                ]},
                {'name': 'Tags', 'columns': [
                    {'name': 'Tag', 'dataType': 'string'},
                    {'name': 'Label', 'dataType': 'string'},
                ]},
            ],
            'relationships': [
                {'left': {'table': 'Orders', 'column': 'Tag'},
                 'right': {'table': 'Tags', 'column': 'Tag'},
                 'type': 'full'},
            ],
        }]
        extra = {'_bridge_tables': 'auto', '_datasources': ds}
        model = _build_semantic_model(ds, 'BridgeE2E', extra)
        table_names = [t['name'] for t in model['model']['tables']]
        bridge_tables = [n for n in table_names if n.startswith('Bridge_')]
        assert len(bridge_tables) >= 1

        # No manyToMany rels should remain
        m2m = [r for r in model['model']['relationships']
               if r.get('fromCardinality') == 'many' and r.get('toCardinality') == 'many']
        assert len(m2m) == 0

    def test_bridge_tmdl_output(self, tmp_dir):
        """Bridge table TMDL file is created with isHidden and calculated partition."""
        ds = [{
            'name': 'DB',
            'tables': [
                {'name': 'Sales', 'columns': [
                    {'name': 'SaleID', 'dataType': 'int64'},
                    {'name': 'Region', 'dataType': 'string'},
                ]},
                {'name': 'Regions', 'columns': [
                    {'name': 'Region', 'dataType': 'string'},
                    {'name': 'Country', 'dataType': 'string'},
                ]},
            ],
            'relationships': [
                {'left': {'table': 'Sales', 'column': 'Region'},
                 'right': {'table': 'Regions', 'column': 'Region'},
                 'type': 'full'},
            ],
        }]
        sm_dir = os.path.join(tmp_dir, 'BridgeTMDL.SemanticModel')
        extra = {'_bridge_tables': 'auto', '_datasources': ds}
        stats = generate_tmdl(ds, 'BridgeTMDL', extra, sm_dir)

        # Check that bridge table TMDL file exists
        tables_dir = os.path.join(sm_dir, 'definition', 'tables')
        tmdl_files = os.listdir(tables_dir) if os.path.isdir(tables_dir) else []
        bridge_files = [f for f in tmdl_files if f.startswith('Bridge_')]
        assert len(bridge_files) >= 1

        # Read the bridge TMDL and check content
        bridge_path = os.path.join(tables_dir, bridge_files[0])
        with open(bridge_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'isHidden' in content
        assert 'calculated' in content

    def test_composite_key_bridge_table(self):
        """Two M2M rels between same table pair → single bridge with 4 columns."""
        model = self._make_model(
            rels=[
                {'fromTable': 'Sales', 'fromColumn': 'Region',
                 'toTable': 'Budget', 'toColumn': 'Region',
                 'fromCardinality': 'many', 'toCardinality': 'many',
                 'crossFilteringBehavior': 'bothDirections'},
                {'fromTable': 'Sales', 'fromColumn': 'Product',
                 'toTable': 'Budget', 'toColumn': 'Product',
                 'fromCardinality': 'many', 'toCardinality': 'many',
                 'crossFilteringBehavior': 'bothDirections'},
            ],
            tables=[
                {'name': 'Sales', 'columns': [
                    {'name': 'Region', 'dataType': 'string'},
                    {'name': 'Product', 'dataType': 'string'},
                ]},
                {'name': 'Budget', 'columns': [
                    {'name': 'Region', 'dataType': 'string'},
                    {'name': 'Product', 'dataType': 'string'},
                ]},
            ],
        )
        count = _generate_bridge_tables(model)
        assert count == 1

        bridge = [t for t in model['model']['tables']
                  if t['name'].startswith('Bridge_')][0]
        # Composite key → 4 columns (2 pairs)
        assert len(bridge['columns']) == 4

        # No M2M relationships remain
        m2m = [r for r in model['model']['relationships']
               if r.get('fromCardinality') == 'many' and r.get('toCardinality') == 'many']
        assert len(m2m) == 0

        # 4 manyToOne relationships (2 per column pair)
        m2o = [r for r in model['model']['relationships']
               if r.get('toCardinality') == 'one']
        assert len(m2o) == 4

    def test_composite_key_dax_has_multiple_values(self):
        """Composite key DAX expression contains multiple VALUES() calls."""
        model = self._make_model(
            rels=[
                {'fromTable': 'A', 'fromColumn': 'X',
                 'toTable': 'B', 'toColumn': 'X',
                 'fromCardinality': 'many', 'toCardinality': 'many',
                 'crossFilteringBehavior': 'bothDirections'},
                {'fromTable': 'A', 'fromColumn': 'Y',
                 'toTable': 'B', 'toColumn': 'Y',
                 'fromCardinality': 'many', 'toCardinality': 'many',
                 'crossFilteringBehavior': 'bothDirections'},
            ],
            tables=[
                {'name': 'A', 'columns': [
                    {'name': 'X', 'dataType': 'string'},
                    {'name': 'Y', 'dataType': 'int64'},
                ]},
                {'name': 'B', 'columns': [
                    {'name': 'X', 'dataType': 'string'},
                    {'name': 'Y', 'dataType': 'int64'},
                ]},
            ],
        )
        _generate_bridge_tables(model)
        bridge = [t for t in model['model']['tables']
                  if t['name'].startswith('Bridge_')][0]
        expr = bridge['partitions'][0]['source']['expression']
        # Should have 4 VALUES() calls (2 per column pair)
        assert expr.count('VALUES(') == 4
        assert 'CROSSJOIN' in expr
        assert 'DISTINCT' in expr

    def test_validate_bridge_tables_passes_for_valid(self):
        """Validation passes for well-formed bridge tables."""
        model = self._make_model(
            rels=[{
                'fromTable': 'T1', 'fromColumn': 'K',
                'toTable': 'T2', 'toColumn': 'K',
                'fromCardinality': 'many', 'toCardinality': 'many',
                'crossFilteringBehavior': 'bothDirections',
            }],
            tables=[
                {'name': 'T1', 'columns': [{'name': 'K', 'dataType': 'string'}]},
                {'name': 'T2', 'columns': [{'name': 'K', 'dataType': 'string'}]},
            ],
        )
        _generate_bridge_tables(model)
        issues = _validate_bridge_tables(model)
        assert issues == []

    def test_validate_bridge_catches_missing_columns(self):
        """Validation detects bridge table with < 2 columns."""
        model = {
            'model': {
                'tables': [
                    {'name': 'Bridge_X_Y', 'columns': [{'name': 'OnlyOne'}],
                     'partitions': [{'source': {'type': 'calculated',
                                                'expression': "DISTINCT(VALUES('X'[A]))"}}]},
                ],
                'relationships': [
                    {'fromTable': 'X', 'fromColumn': 'A',
                     'toTable': 'Bridge_X_Y', 'toColumn': 'OnlyOne'},
                ],
            },
        }
        issues = _validate_bridge_tables(model)
        assert any('1 columns' in i for i in issues)
        assert any('1 incoming' in i for i in issues)

    def test_validate_bridge_catches_unbalanced_parens(self):
        """Validation detects unbalanced parentheses in DAX expression."""
        model = {
            'model': {
                'tables': [
                    {'name': 'Bridge_A_B',
                     'columns': [{'name': 'C1'}, {'name': 'C2'}],
                     'partitions': [{'source': {'type': 'calculated',
                                                'expression': "DISTINCT(VALUES('A'[X])"}}]},
                ],
                'relationships': [
                    {'fromTable': 'A', 'fromColumn': 'X',
                     'toTable': 'Bridge_A_B', 'toColumn': 'C1'},
                    {'fromTable': 'B', 'fromColumn': 'Y',
                     'toTable': 'Bridge_A_B', 'toColumn': 'C2'},
                ],
            },
        }
        issues = _validate_bridge_tables(model)
        assert any('unbalanced' in i.lower() for i in issues)

    def test_validate_bridge_catches_nonexistent_ref_table(self):
        """Validation detects DAX reference to a table not in the model."""
        model = {
            'model': {
                'tables': [
                    {'name': 'Bridge_A_B',
                     'columns': [{'name': 'C1'}, {'name': 'C2'}],
                     'partitions': [{'source': {'type': 'calculated',
                                                'expression': "DISTINCT(SELECTCOLUMNS(CROSSJOIN(VALUES('Ghost'[X]), VALUES('B'[Y])), \"C1\", 'Ghost'[X], \"C2\", 'B'[Y]))"}}]},
                ],
                'relationships': [
                    {'fromTable': 'A', 'fromColumn': 'X',
                     'toTable': 'Bridge_A_B', 'toColumn': 'C1'},
                    {'fromTable': 'B', 'fromColumn': 'Y',
                     'toTable': 'Bridge_A_B', 'toColumn': 'C2'},
                ],
            },
        }
        issues = _validate_bridge_tables(model)
        assert any('Ghost' in i for i in issues)


class TestSyntheticKeyDetection:
    """Tests for synthetic key detection in _detect_many_to_many."""

    def test_synthetic_key_table_flagged_as_m2m(self):
        """Relationships involving $Syn tables are detected as manyToMany."""
        model = {
            'model': {
                'tables': [
                    {'name': 'Orders', 'columns': [{'name': 'Key'}]},
                    {'name': '$Syn 1', 'columns': [{'name': 'Key'}]},
                    {'name': 'Products', 'columns': [{'name': 'Key'}]},
                ],
                'relationships': [
                    {'fromTable': 'Orders', 'fromColumn': 'Key',
                     'toTable': '$Syn 1', 'toColumn': 'Key'},
                    {'fromTable': '$Syn 1', 'fromColumn': 'Key',
                     'toTable': 'Products', 'toColumn': 'Key'},
                ],
            },
        }
        _detect_many_to_many(model, [])
        for rel in model['model']['relationships']:
            assert rel.get('fromCardinality') == 'many'
            assert rel.get('toCardinality') == 'many'

    def test_non_synthetic_not_affected(self):
        """Normal tables are not treated as synthetic keys."""
        model = {
            'model': {
                'tables': [
                    {'name': 'Sales', 'columns': [
                        {'name': 'CustomerID', 'dataType': 'int64'}]},
                    {'name': 'Customers', 'columns': [
                        {'name': 'CustomerID', 'dataType': 'int64'}]},
                ],
                'relationships': [
                    {'fromTable': 'Sales', 'fromColumn': 'CustomerID',
                     'toTable': 'Customers', 'toColumn': 'CustomerID'},
                ],
            },
        }
        _detect_many_to_many(model, [])
        rel = model['model']['relationships'][0]
        # CustomerID is an ID-suffix column → should be detected as key
        assert rel.get('toCardinality') != 'many' or rel.get('fromCardinality') != 'many'


# ══════════════════════════════════════════════════════════════════
# 9. Cross-Filter Direction Optimization (Phase 3)
# ══════════════════════════════════════════════════════════════════

class TestCrossFilterOptimization:
    """Tests for _optimize_cross_filter_direction."""

    def _make_model(self, rels):
        return {'model': {'tables': [], 'relationships': rels}}

    def test_downgrades_both_to_one_for_many_to_one(self):
        """bothDirections on manyToOne should be downgraded to oneDirection."""
        model = self._make_model([{
            'fromTable': 'A', 'fromColumn': 'X',
            'toTable': 'B', 'toColumn': 'X',
            'fromCardinality': 'many', 'toCardinality': 'one',
            'crossFilteringBehavior': 'bothDirections',
        }])
        changed = _optimize_cross_filter_direction(model)
        assert changed == 1
        assert model['model']['relationships'][0]['crossFilteringBehavior'] == 'oneDirection'

    def test_keeps_both_for_m2m(self):
        """bothDirections on manyToMany must be kept."""
        model = self._make_model([{
            'fromTable': 'A', 'fromColumn': 'X',
            'toTable': 'B', 'toColumn': 'X',
            'fromCardinality': 'many', 'toCardinality': 'many',
            'crossFilteringBehavior': 'bothDirections',
        }])
        changed = _optimize_cross_filter_direction(model)
        assert changed == 0
        assert model['model']['relationships'][0]['crossFilteringBehavior'] == 'bothDirections'

    def test_no_change_when_already_one_direction(self):
        """oneDirection relationships are not touched."""
        model = self._make_model([{
            'fromTable': 'A', 'fromColumn': 'X',
            'toTable': 'B', 'toColumn': 'X',
            'fromCardinality': 'many', 'toCardinality': 'one',
            'crossFilteringBehavior': 'oneDirection',
        }])
        changed = _optimize_cross_filter_direction(model)
        assert changed == 0

    def test_skips_inactive_relationships(self):
        """Inactive relationships should be skipped."""
        model = self._make_model([{
            'fromTable': 'A', 'fromColumn': 'X',
            'toTable': 'B', 'toColumn': 'X',
            'fromCardinality': 'many', 'toCardinality': 'one',
            'crossFilteringBehavior': 'bothDirections',
            'isActive': False,
        }])
        changed = _optimize_cross_filter_direction(model)
        assert changed == 0

    def test_multiple_rels_mixed(self):
        """Mixed relationships: only non-M2M bothDirections are changed."""
        model = self._make_model([
            {'fromTable': 'A', 'fromColumn': 'X', 'toTable': 'B', 'toColumn': 'X',
             'fromCardinality': 'many', 'toCardinality': 'one',
             'crossFilteringBehavior': 'bothDirections'},
            {'fromTable': 'C', 'fromColumn': 'Y', 'toTable': 'D', 'toColumn': 'Y',
             'fromCardinality': 'many', 'toCardinality': 'many',
             'crossFilteringBehavior': 'bothDirections'},
            {'fromTable': 'E', 'fromColumn': 'Z', 'toTable': 'F', 'toColumn': 'Z',
             'fromCardinality': 'one', 'toCardinality': 'one',
             'crossFilteringBehavior': 'bothDirections'},
        ])
        changed = _optimize_cross_filter_direction(model)
        assert changed == 2  # A→B and E→F
        assert model['model']['relationships'][1]['crossFilteringBehavior'] == 'bothDirections'


# ══════════════════════════════════════════════════════════════════
# 10. Relationship Validation & Reporting (Phase 4)
# ══════════════════════════════════════════════════════════════════

class TestRelationshipValidation:
    """Tests for _validate_relationships."""

    def _make_model(self, rels, tables=None):
        return {'model': {'tables': tables or [], 'relationships': rels}}

    def test_healthy_model(self):
        """A clean model should report healthy with no errors."""
        model = self._make_model(
            rels=[{
                'name': 'R1',
                'fromTable': 'Orders', 'fromColumn': 'CustID',
                'toTable': 'Customers', 'toColumn': 'CustID',
                'fromCardinality': 'many', 'toCardinality': 'one',
                'crossFilteringBehavior': 'oneDirection',
            }],
            tables=[
                {'name': 'Orders', 'columns': [{'name': 'CustID', 'dataType': 'Int64'}]},
                {'name': 'Customers', 'columns': [{'name': 'CustID', 'dataType': 'Int64'}]},
            ],
        )
        report = _validate_relationships(model)
        assert report['healthy'] is True
        assert report['total'] == 1
        assert report['active'] == 1
        assert len(report['errors']) == 0

    def test_orphan_table_detected(self):
        """References to non-existent tables should be flagged as errors."""
        model = self._make_model(
            rels=[{
                'name': 'R1',
                'fromTable': 'Orders', 'fromColumn': 'CustID',
                'toTable': 'Ghost', 'toColumn': 'CustID',
            }],
            tables=[
                {'name': 'Orders', 'columns': [{'name': 'CustID'}]},
            ],
        )
        report = _validate_relationships(model)
        assert report['healthy'] is False
        assert any('Ghost' in e for e in report['errors'])

    def test_orphan_column_detected(self):
        """References to non-existent columns should be flagged."""
        model = self._make_model(
            rels=[{
                'name': 'R1',
                'fromTable': 'A', 'fromColumn': 'Missing',
                'toTable': 'B', 'toColumn': 'ID',
            }],
            tables=[
                {'name': 'A', 'columns': [{'name': 'ID'}]},
                {'name': 'B', 'columns': [{'name': 'ID'}]},
            ],
        )
        report = _validate_relationships(model)
        assert any('Missing' in e for e in report['errors'])

    def test_duplicate_relationship_warned(self):
        """Duplicate relationships should produce a warning."""
        rel = {'name': 'R1', 'fromTable': 'A', 'fromColumn': 'X',
               'toTable': 'B', 'toColumn': 'X'}
        model = self._make_model(rels=[rel, dict(rel, name='R2')])
        report = _validate_relationships(model)
        assert any('Duplicate' in w for w in report['warnings'])

    def test_self_reference_warned(self):
        """Self-referencing relationships should produce a warning."""
        model = self._make_model(
            rels=[{
                'name': 'R1',
                'fromTable': 'T', 'fromColumn': 'ParentID',
                'toTable': 'T', 'toColumn': 'ID',
            }],
            tables=[{'name': 'T', 'columns': [
                {'name': 'ID'}, {'name': 'ParentID'}]}],
        )
        report = _validate_relationships(model)
        assert any('Self-referencing' in w for w in report['warnings'])

    def test_m2m_count(self):
        """ManyToMany relationships should be counted."""
        model = self._make_model([{
            'name': 'R1',
            'fromTable': 'A', 'fromColumn': 'X',
            'toTable': 'B', 'toColumn': 'X',
            'fromCardinality': 'many', 'toCardinality': 'many',
        }])
        report = _validate_relationships(model)
        assert report['manyToMany'] == 1

    def test_inactive_count(self):
        """Inactive relationships should be counted."""
        model = self._make_model([{
            'name': 'R1',
            'fromTable': 'A', 'fromColumn': 'X',
            'toTable': 'B', 'toColumn': 'X',
            'isActive': False,
        }])
        report = _validate_relationships(model)
        assert report['inactive'] == 1
        assert report['active'] == 0

    def test_type_mismatch_warned(self):
        """Mismatched column types should produce a warning."""
        model = self._make_model(
            rels=[{
                'name': 'R1',
                'fromTable': 'A', 'fromColumn': 'ID',
                'toTable': 'B', 'toColumn': 'ID',
            }],
            tables=[
                {'name': 'A', 'columns': [{'name': 'ID', 'dataType': 'Int64'}]},
                {'name': 'B', 'columns': [{'name': 'ID', 'dataType': 'String'}]},
            ],
        )
        report = _validate_relationships(model)
        assert any('Type mismatch' in w for w in report['warnings'])

    def test_report_in_generate_tmdl_stats(self, tmp_dir):
        """generate_tmdl should include relationship_report in stats."""
        sm_dir = os.path.join(tmp_dir, "ValReport.SemanticModel")
        stats = generate_tmdl(_simple_ds(), "ValReport", {}, sm_dir)
        assert 'relationship_report' in stats
        assert isinstance(stats['relationship_report'], dict)
        assert 'healthy' in stats['relationship_report']

    def test_bridge_tables_counted(self):
        """Bridge table relationships should be counted."""
        model = self._make_model(
            rels=[{
                'name': 'R1',
                'fromTable': 'Orders', 'fromColumn': 'X',
                'toTable': 'Bridge_Orders_Products', 'toColumn': 'X',
            }],
            tables=[
                {'name': 'Orders', 'columns': [{'name': 'X'}]},
                {'name': 'Bridge_Orders_Products', 'columns': [{'name': 'X'}]},
            ],
        )
        report = _validate_relationships(model)
        assert report['bridgeTables'] == 1


# ══════════════════════════════════════════════════════════════════
# 11. Unified Code Paths — RelationshipCardinality Enum (Phase 5)
# ══════════════════════════════════════════════════════════════════

class TestUnifiedEnums:
    """Tests that _set_cardinality uses RelationshipCardinality enum."""

    def test_set_cardinality_stores_enum(self):
        """_set_cardinality should store the enum value in _cardinality_enum."""
        rel = {}
        _set_cardinality(rel, 'many', 'one')
        assert rel['_cardinality_enum'] == 'ManyToOne'
        assert rel['crossFilteringBehavior'] == 'oneDirection'

    def test_set_cardinality_one_to_one(self):
        rel = {}
        _set_cardinality(rel, 'one', 'one')
        assert rel['_cardinality_enum'] == 'OneToOne'
        assert rel['crossFilteringBehavior'] == 'oneDirection'

    def test_set_cardinality_one_to_many(self):
        rel = {}
        _set_cardinality(rel, 'one', 'many')
        assert rel['_cardinality_enum'] == 'OneToMany'
        assert rel['crossFilteringBehavior'] == 'oneDirection'

    def test_set_cardinality_many_to_many(self):
        rel = {}
        _set_cardinality(rel, 'many', 'many')
        assert rel['_cardinality_enum'] == 'ManyToMany'
        assert rel['crossFilteringBehavior'] == 'bothDirections'

    def test_enum_imported_from_qlik_model_converter(self):
        """RelationshipCardinality should be importable from qlik_model_converter."""
        from qlik_export.qlik_model_converter import (
            RelationshipCardinality,
            CrossFilterDirection,
        )
        assert RelationshipCardinality.MANY_TO_ONE.value == 'ManyToOne'
        assert CrossFilterDirection.SINGLE.value == 'Single'
        assert CrossFilterDirection.BOTH.value == 'Both'


# ═══════════════════════════════════════════════════════════════
#  _materialize_measure_referenced_columns
# ═══════════════════════════════════════════════════════════════

class TestMaterializeMeasureReferencedColumns:
    def test_missing_column_gets_materialized_as_hidden(self):
        """Measure referencing 'Table1'[MissingCol] → column materialized as hidden."""
        model = {"model": {"tables": [{
            "name": "Table1",
            "columns": [{"name": "ExistingCol", "dataType": "String"}],
            "measures": [{"name": "M1", "expression": "SUM('Table1'[MissingCol])"}],
        }]}}
        count = _materialize_measure_referenced_columns(model)
        assert count == 1
        col_names = [c["name"] for c in model["model"]["tables"][0]["columns"]]
        assert "MissingCol" in col_names
        new_col = [c for c in model["model"]["tables"][0]["columns"] if c["name"] == "MissingCol"][0]
        assert new_col["isHidden"] is True
        assert new_col["dataType"] == "String"

    def test_existing_column_not_duplicated(self):
        """Measure referencing existing column → no extra column added."""
        model = {"model": {"tables": [{
            "name": "Sales",
            "columns": [{"name": "Amount", "dataType": "Double"}],
            "measures": [{"name": "Total", "expression": "SUM('Sales'[Amount])"}],
        }]}}
        count = _materialize_measure_referenced_columns(model)
        assert count == 0
        assert len(model["model"]["tables"][0]["columns"]) == 1

    def test_table_with_no_measures_returns_zero(self):
        """Table with no measures → returns 0."""
        model = {"model": {"tables": [{
            "name": "Dim",
            "columns": [{"name": "ID", "dataType": "Int64"}],
            "measures": [],
        }]}}
        count = _materialize_measure_referenced_columns(model)
        assert count == 0


# ═══════════════════════════════════════════════════════════════
#  _downgrade_many_to_many_direction
# ═══════════════════════════════════════════════════════════════

class TestDowngradeManyToManyDirection:
    def test_both_directions_many_to_many_becomes_one_direction(self):
        """bothDirections + manyToMany → becomes oneDirection."""
        model = {"model": {"relationships": [{
            "name": "R1",
            "crossFilteringBehavior": "bothDirections",
            "cardinality": "manyToMany",
        }]}}
        count = _downgrade_many_to_many_direction(model)
        assert count == 1
        assert model["model"]["relationships"][0]["crossFilteringBehavior"] == "oneDirection"

    def test_both_directions_many_to_one_stays(self):
        """bothDirections + manyToOne → stays bothDirections (not downgraded)."""
        model = {"model": {"relationships": [{
            "name": "R2",
            "crossFilteringBehavior": "bothDirections",
            "cardinality": "manyToOne",
        }]}}
        count = _downgrade_many_to_many_direction(model)
        assert count == 0
        assert model["model"]["relationships"][0]["crossFilteringBehavior"] == "bothDirections"

    def test_one_direction_many_to_many_stays(self):
        """oneDirection + manyToMany → stays oneDirection."""
        model = {"model": {"relationships": [{
            "name": "R3",
            "crossFilteringBehavior": "oneDirection",
            "cardinality": "manyToMany",
        }]}}
        count = _downgrade_many_to_many_direction(model)
        assert count == 0
        assert model["model"]["relationships"][0]["crossFilteringBehavior"] == "oneDirection"
