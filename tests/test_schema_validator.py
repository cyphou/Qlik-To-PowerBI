"""Tests for powerbi_import.schema_validator — PBIR v4.0 JSON validation."""

import json
import os
import tempfile
import unittest

from powerbi_import.schema_validator import (
    SchemaIssue,
    SchemaResult,
    validate_artifact,
    detect_artifact_type,
    validate_report_dir,
    KNOWN_VISUAL_TYPES,
    EXPECTED_SCHEMAS,
)


class TestSchemaIssue(unittest.TestCase):
    def test_repr_normal(self):
        issue = SchemaIssue('error', '$schema', 'Missing URL')
        self.assertIn('ERROR', repr(issue))
        self.assertIn('Missing URL', repr(issue))

    def test_repr_repaired(self):
        issue = SchemaIssue('warning', 'pos.x', 'Coerced', repaired=True)
        self.assertIn('[repaired]', repr(issue))


class TestSchemaResult(unittest.TestCase):
    def test_ok_when_no_issues(self):
        r = SchemaResult(artifact_type='visual')
        self.assertTrue(r.ok)

    def test_ok_when_only_warnings(self):
        r = SchemaResult(artifact_type='visual')
        r.issues.append(SchemaIssue('warning', 'x', 'minor'))
        self.assertTrue(r.ok)

    def test_not_ok_when_error(self):
        r = SchemaResult(artifact_type='visual')
        r.issues.append(SchemaIssue('error', 'x', 'bad'))
        self.assertFalse(r.ok)

    def test_ok_when_error_repaired(self):
        r = SchemaResult(artifact_type='visual')
        r.issues.append(SchemaIssue('error', 'x', 'fixed', repaired=True))
        self.assertTrue(r.ok)

    def test_to_dict(self):
        r = SchemaResult(artifact_type='page', file_path='test.json')
        r.issues.append(SchemaIssue('warning', 'name', 'empty'))
        d = r.to_dict()
        self.assertEqual(d['artifact_type'], 'page')
        self.assertEqual(d['warning_count'], 1)
        self.assertTrue(d['ok'])


class TestDetectArtifactType(unittest.TestCase):
    def test_visual(self):
        data = {'$schema': EXPECTED_SCHEMAS['visual']}
        self.assertEqual(detect_artifact_type(data), 'visual')

    def test_page(self):
        data = {'$schema': EXPECTED_SCHEMAS['page']}
        self.assertEqual(detect_artifact_type(data), 'page')

    def test_report(self):
        data = {'$schema': EXPECTED_SCHEMAS['report']}
        self.assertEqual(detect_artifact_type(data), 'report')

    def test_bookmark(self):
        data = {'$schema': EXPECTED_SCHEMAS['bookmark']}
        self.assertEqual(detect_artifact_type(data), 'bookmark')

    def test_unknown(self):
        self.assertIsNone(detect_artifact_type({'$schema': 'https://example.com/unknown.json'}))

    def test_no_schema(self):
        self.assertIsNone(detect_artifact_type({}))


class TestValidateVisual(unittest.TestCase):
    def test_valid_visual(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['visual'],
            'position': {'x': 0, 'y': 0, 'z': 0, 'width': 400, 'height': 300},
            'visual': {'visualType': 'barChart'},
        }
        r = validate_artifact(data, 'visual')
        self.assertTrue(r.ok)

    def test_missing_schema(self):
        r = validate_artifact({}, 'visual')
        errors = [i for i in r.issues if i.severity == 'error']
        self.assertTrue(any('$schema' in i.path for i in errors))

    def test_negative_dimension(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['visual'],
            'position': {'x': 0, 'y': 0, 'width': -10, 'height': 300},
        }
        r = validate_artifact(data, 'visual')
        self.assertFalse(r.ok)

    def test_string_position_coerced(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['visual'],
            'position': {'x': '10', 'y': '20', 'width': '400', 'height': '300'},
        }
        r = validate_artifact(data, 'visual')
        self.assertTrue(r.ok)
        self.assertTrue(any(i.repaired for i in r.issues))

    def test_unknown_visual_type_warning(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['visual'],
            'visual': {'visualType': 'totallyNewVisual'},
        }
        r = validate_artifact(data, 'visual')
        self.assertTrue(any('Unknown visual type' in i.message for i in r.issues))


class TestValidatePage(unittest.TestCase):
    def test_valid_page(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['page'],
            'name': 'page1',
            'displayName': 'Page 1',
            'width': 1280,
            'height': 720,
        }
        r = validate_artifact(data, 'page')
        self.assertTrue(r.ok)

    def test_missing_name(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['page'],
            'name': '',
            'displayName': 'Page 1',
        }
        r = validate_artifact(data, 'page')
        self.assertFalse(r.ok)


class TestValidateReport(unittest.TestCase):
    def test_valid_report(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['report'],
            'themeCollection': {'baseTheme': {'name': 'CY24SU06'}},
        }
        r = validate_artifact(data, 'report')
        self.assertTrue(r.ok)

    def test_invalid_filter_config(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['report'],
            'filterConfig': 'not_an_object',
        }
        r = validate_artifact(data, 'report')
        self.assertFalse(r.ok)


class TestValidateBookmark(unittest.TestCase):
    def test_valid_bookmark(self):
        data = {
            '$schema': EXPECTED_SCHEMAS['bookmark'],
            'name': 'bm1',
            'displayName': 'Bookmark 1',
        }
        r = validate_artifact(data, 'bookmark')
        self.assertTrue(r.ok)

    def test_missing_name(self):
        data = {'$schema': EXPECTED_SCHEMAS['bookmark']}
        r = validate_artifact(data, 'bookmark')
        self.assertFalse(r.ok)


class TestValidateReportDir(unittest.TestCase):
    def test_nonexistent_dir(self):
        results = validate_report_dir('/nonexistent/path')
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].ok)

    def test_valid_dir(self):
        with tempfile.TemporaryDirectory() as td:
            visual_data = {
                '$schema': EXPECTED_SCHEMAS['visual'],
                'position': {'x': 0, 'y': 0, 'width': 400, 'height': 300},
                'visual': {'visualType': 'barChart'},
            }
            with open(os.path.join(td, 'visual.json'), 'w') as f:
                json.dump(visual_data, f)
            results = validate_report_dir(td)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].ok)

    def test_invalid_json_file(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, 'bad.json'), 'w') as f:
                f.write('not valid json')
            results = validate_report_dir(td)
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0].ok)


class TestValidateArtifactEdgeCases(unittest.TestCase):
    def test_none_data(self):
        r = validate_artifact(None, 'visual')
        self.assertFalse(r.ok)

    def test_unknown_type(self):
        r = validate_artifact({'$schema': 'x'}, 'unknown_type')
        self.assertTrue(any('No schema validator' in i.message for i in r.issues))


if __name__ == '__main__':
    unittest.main()
