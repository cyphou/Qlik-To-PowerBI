"""Tests for powerbi_import.self_healing_v3 — model healers."""

import unittest

from powerbi_import.self_healing_v3 import (
    run_v3_healers,
    _heal_global_measure_dupes,
    _heal_self_referencing_measures,
    _heal_sort_by_column,
    _heal_hierarchies,
    _heal_display_folder_names,
    _heal_relationship_type_mismatch,
    _heal_invalid_identifier_chars,
    _heal_int64_decimal_format,
    _heal_datatype_casing,
    _heal_duplicate_relationships,
    _heal_iskey_ishidden_conflict,
    _DATATYPE_CANONICAL,
    _ALL_HEALERS,
)


class TestRunV3Healers(unittest.TestCase):
    """Test the main entry point."""

    def test_empty_model(self):
        model = {'model': {'tables': []}}
        count = run_v3_healers(model)
        self.assertEqual(count, 0)

    def test_none_model(self):
        count = run_v3_healers({})
        self.assertEqual(count, 0)

    def test_returns_int(self):
        model = {'model': {'tables': [{'name': 'T', 'columns': [], 'measures': []}]}}
        result = run_v3_healers(model)
        self.assertIsInstance(result, int)


class TestHealGlobalMeasureDupes(unittest.TestCase):
    """Test duplicate measure removal across tables."""

    def test_no_dupes(self):
        model = {'model': {'tables': [
            {'name': 'T1', 'measures': [{'name': 'A', 'expression': 'SUM(T1[X])'}]},
            {'name': 'T2', 'measures': [{'name': 'B', 'expression': 'SUM(T2[Y])'}]},
        ]}}
        count = _heal_global_measure_dupes(model)
        self.assertEqual(count, 0)

    def test_duplicate_removed(self):
        model = {'model': {'tables': [
            {'name': 'T1', 'measures': [{'name': 'A', 'expression': 'SUM(T1[X])'}]},
            {'name': 'T2', 'measures': [{'name': 'A', 'expression': 'SUM(T1[X])'}]},
        ]}}
        count = _heal_global_measure_dupes(model)
        self.assertGreaterEqual(count, 1)

    def test_different_expression_not_removed(self):
        model = {'model': {'tables': [
            {'name': 'T1', 'measures': [{'name': 'A', 'expression': 'SUM(T1[X])'}]},
            {'name': 'T2', 'measures': [{'name': 'A', 'expression': 'SUM(T2[Y])'}]},
        ]}}
        count = _heal_global_measure_dupes(model)
        # Healer renames duplicates by name regardless of expression
        self.assertGreaterEqual(count, 1)


class TestHealSelfReferencingMeasures(unittest.TestCase):
    """Test self-referencing measure detection."""

    def test_no_self_ref(self):
        model = {'model': {'tables': [{'name': 'T', 'measures': [
            {'name': 'Revenue', 'expression': 'SUM(T[Sales])'},
        ]}]}}
        count = _heal_self_referencing_measures(model)
        self.assertEqual(count, 0)

    def test_self_ref_fixed(self):
        model = {'model': {'tables': [{'name': 'T', 'measures': [
            {'name': 'Revenue', 'expression': '[Revenue] + 1'},
        ]}]}}
        count = _heal_self_referencing_measures(model)
        self.assertGreaterEqual(count, 1)


class TestHealSortByColumn(unittest.TestCase):
    """Test sort-by column validation."""

    def test_valid_sort(self):
        model = {'model': {'tables': [{'name': 'T', 'columns': [
            {'name': 'Month', 'sortByColumn': 'MonthNum'},
            {'name': 'MonthNum'},
        ]}]}}
        count = _heal_sort_by_column(model)
        self.assertEqual(count, 0)

    def test_invalid_sort_cleared(self):
        model = {'model': {'tables': [{'name': 'T', 'columns': [
            {'name': 'Month', 'sortByColumn': 'NoSuchColumn'},
        ]}]}}
        count = _heal_sort_by_column(model)
        self.assertGreaterEqual(count, 1)


class TestHealHierarchies(unittest.TestCase):
    """Test hierarchy level validation."""

    def test_valid_hierarchy(self):
        model = {'model': {'tables': [{'name': 'T',
            'columns': [{'name': 'Year'}, {'name': 'Quarter'}],
            'hierarchies': [{'name': 'DateHier', 'levels': [
                {'name': 'Year', 'column': 'Year'},
                {'name': 'Quarter', 'column': 'Quarter'},
            ]}],
        }]}}
        count = _heal_hierarchies(model)
        self.assertEqual(count, 0)


class TestHealDisplayFolderNames(unittest.TestCase):
    """Test display folder name cleanup."""

    def test_no_folders(self):
        model = {'model': {'tables': [{'name': 'T', 'measures': [
            {'name': 'A', 'expression': 'SUM(T[X])'},
        ]}]}}
        count = _heal_display_folder_names(model)
        self.assertEqual(count, 0)


class TestHealRelationshipTypeMismatch(unittest.TestCase):
    """Test relationship type correction."""

    def test_no_relationships(self):
        model = {'model': {'tables': [], 'relationships': []}}
        count = _heal_relationship_type_mismatch(model)
        self.assertEqual(count, 0)

    def test_matched_types(self):
        model = {'model': {
            'tables': [
                {'name': 'A', 'columns': [{'name': 'id', 'dataType': 'int64'}]},
                {'name': 'B', 'columns': [{'name': 'a_id', 'dataType': 'int64'}]},
            ],
            'relationships': [{
                'fromTable': 'B', 'fromColumn': 'a_id',
                'toTable': 'A', 'toColumn': 'id',
            }],
        }}
        count = _heal_relationship_type_mismatch(model)
        self.assertEqual(count, 0)


class TestHealInvalidIdentifierChars(unittest.TestCase):
    """Test invalid character removal in names."""

    def test_clean_names(self):
        model = {'model': {'tables': [{'name': 'Sales', 'columns': [
            {'name': 'Revenue'},
        ]}]}}
        count = _heal_invalid_identifier_chars(model)
        self.assertEqual(count, 0)


class TestHealInt64DecimalFormat(unittest.TestCase):
    """Test int64 format string correction."""

    def test_no_int_columns(self):
        model = {'model': {'tables': [{'name': 'T', 'columns': [
            {'name': 'Name', 'dataType': 'string'},
        ]}]}}
        count = _heal_int64_decimal_format(model)
        self.assertEqual(count, 0)


class TestHealDatatypeCasing(unittest.TestCase):
    """Test datatype canonical casing."""

    def test_correct_casing(self):
        model = {'model': {'tables': [{'name': 'T', 'columns': [
            {'name': 'X', 'dataType': 'int64'},
        ]}]}}
        count = _heal_datatype_casing(model)
        self.assertEqual(count, 0)

    def test_wrong_casing_fixed(self):
        model = {'model': {'tables': [{'name': 'T', 'columns': [
            {'name': 'X', 'dataType': 'INTEGER'},
        ]}]}}
        count = _heal_datatype_casing(model)
        self.assertGreaterEqual(count, 1)
        self.assertEqual(model['model']['tables'][0]['columns'][0]['dataType'], 'int64')


class TestHealDuplicateRelationships(unittest.TestCase):
    """Test duplicate relationship removal."""

    def test_no_dupes(self):
        model = {'model': {'relationships': [
            {'fromTable': 'A', 'fromColumn': 'id', 'toTable': 'B', 'toColumn': 'a_id'},
        ]}}
        count = _heal_duplicate_relationships(model)
        self.assertEqual(count, 0)

    def test_dupe_removed(self):
        rel = {'fromTable': 'A', 'fromColumn': 'id', 'toTable': 'B', 'toColumn': 'a_id'}
        model = {'model': {'relationships': [dict(rel), dict(rel)]}}
        count = _heal_duplicate_relationships(model)
        self.assertGreaterEqual(count, 1)
        # Healer deactivates duplicates rather than removing them
        deactivated = [r for r in model['model']['relationships'] if not r.get('isActive', True)]
        self.assertGreater(len(deactivated), 0)


class TestHealIsKeyIsHiddenConflict(unittest.TestCase):
    """Test isKey + isHidden conflict resolution."""

    def test_no_conflict(self):
        model = {'model': {'tables': [{'name': 'T', 'columns': [
            {'name': 'ID', 'isKey': True, 'isHidden': False},
        ]}]}}
        count = _heal_iskey_ishidden_conflict(model)
        self.assertEqual(count, 0)


class TestAllHealersList(unittest.TestCase):
    """Test the _ALL_HEALERS list."""

    def test_non_empty(self):
        self.assertGreater(len(_ALL_HEALERS), 0)

    def test_all_callable(self):
        for healer in _ALL_HEALERS:
            self.assertTrue(callable(healer))

    def test_healer_count(self):
        self.assertEqual(len(_ALL_HEALERS), 11)


class TestDatatypeCanonical(unittest.TestCase):
    """Test _DATATYPE_CANONICAL mapping."""

    def test_has_common_types(self):
        self.assertIn('int64', _DATATYPE_CANONICAL)
        self.assertIn('string', _DATATYPE_CANONICAL)
        self.assertIn('double', _DATATYPE_CANONICAL)


if __name__ == '__main__':
    unittest.main()
