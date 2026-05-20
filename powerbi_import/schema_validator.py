"""PBI Desktop schema validator.

Validates generated PBIR v4.0 JSON artifacts against the structural rules
that Power BI Desktop enforces. Checks ``$schema`` URLs, field types,
value constraints, nested structures, visual type membership, and
auto-repairs common issues.

Zero external dependencies.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

EXPECTED_SCHEMAS = {
    'report': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/2.0.0/schema.json',
    'page': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json',
    'visual': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json',
    'bookmark': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/2.1.0/schema.json',
    'pages_metadata': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json',
    'version': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json',
    'definition_pbir': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json',
}

_ACCEPTABLE_VERSIONS = {
    'report': {'2.0.0'},
    'page': {'2.0.0', '2.1.0'},
    'visual': {'2.5.0', '2.7.0'},
    'bookmark': {'1.1.0', '2.1.0'},
    'pages_metadata': {'1.0.0'},
    'version': {'1.0.0'},
    'definition_pbir': {'2.0.0'},
}

KNOWN_VISUAL_TYPES: Set[str] = {
    'actionButton', 'areaChart', 'barChart', 'basicShape',
    'boxAndWhisker', 'card', 'cardVisual', 'clusteredBarChart',
    'clusteredColumnChart', 'columnChart', 'comboChart',
    'decompositionTree', 'donutChart', 'filledMap', 'funnel',
    'gauge', 'hundredPercentStackedBarChart',
    'hundredPercentStackedColumnChart', 'image', 'kpi',
    'lineChart', 'lineClusteredColumnComboChart',
    'lineStackedColumnComboChart', 'map', 'matrix',
    'multiRowCard', 'pieChart', 'pivotTable', 'ribbonChart',
    'scatterChart', 'scriptVisual', 'shape', 'shapeMap',
    'slicer', 'stackedAreaChart', 'stackedBarChart',
    'stackedColumnChart', 'table', 'tableEx', 'textbox',
    'treemap', 'waterfallChart', 'wordCloud',
    'ViolinPlot1.0.0', 'ParallelCoordinates1.0.0',
    'sankeyDiagram',
}

KNOWN_PAGE_TYPES = {'', 'Tooltip', 'Drillthrough'}


@dataclass
class SchemaIssue:
    """Single schema validation issue."""
    severity: str
    path: str
    message: str
    repaired: bool = False

    def __repr__(self) -> str:
        tag = ' [repaired]' if self.repaired else ''
        return f'{self.severity.upper()}: {self.path}: {self.message}{tag}'


@dataclass
class SchemaResult:
    """Result of validating one artifact."""
    artifact_type: str
    file_path: str = ''
    issues: List[SchemaIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(i.severity != 'error' or i.repaired for i in self.issues)

    @property
    def errors(self) -> List[SchemaIssue]:
        return [i for i in self.issues if i.severity == 'error']

    @property
    def warnings(self) -> List[SchemaIssue]:
        return [i for i in self.issues if i.severity == 'warning']

    @property
    def repairs(self) -> List[SchemaIssue]:
        return [i for i in self.issues if i.repaired]

    def to_dict(self) -> dict:
        return {
            'artifact_type': self.artifact_type,
            'file_path': self.file_path,
            'ok': self.ok,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'repair_count': len(self.repairs),
            'issues': [
                {'severity': i.severity, 'path': i.path,
                 'message': i.message, 'repaired': i.repaired}
                for i in self.issues
            ],
        }


def _schema_version(url: str) -> Optional[str]:
    if not url:
        return None
    parts = url.rstrip('/').split('/')
    for i, p in enumerate(parts):
        if p == 'schema.json' and i >= 1:
            return parts[i - 1]
    return None


def _schema_family(url: str) -> Optional[str]:
    if not url:
        return None
    low = url.lower()
    if 'visualcontainer' in low:
        return 'visual'
    if 'pagemetadata' in low or 'pagesmetadata' in low:
        return 'pages_metadata'
    if 'versionmetadata' in low:
        return 'version'
    if 'definitionproperties' in low:
        return 'definition_pbir'
    if 'bookmark' in low:
        return 'bookmark'
    if '/page/' in low:
        return 'page'
    if '/report/' in low and 'page' not in low:
        return 'report'
    return None


def _coerce_number(obj: dict, key: str, issues: List[SchemaIssue],
                   path: str) -> None:
    val = obj.get(key)
    if isinstance(val, str):
        try:
            obj[key] = int(val) if '.' not in val else float(val)
            issues.append(SchemaIssue(
                'warning', f'{path}.{key}',
                f'Coerced string "{val}" to number {obj[key]}',
                repaired=True,
            ))
        except ValueError:
            issues.append(SchemaIssue(
                'error', f'{path}.{key}',
                f'Expected number, got non-numeric string "{val}"',
            ))
    elif val is not None and not isinstance(val, (int, float)):
        issues.append(SchemaIssue(
            'error', f'{path}.{key}',
            f'Expected number, got {type(val).__name__}',
        ))


def _validate_schema_url(data: dict, artifact_type: str,
                         issues: List[SchemaIssue]) -> None:
    url = data.get('$schema', '')
    if not url:
        issues.append(SchemaIssue('error', '$schema', 'Missing $schema URL'))
        return

    family = _schema_family(url)
    if family and family != artifact_type:
        issues.append(SchemaIssue(
            'error', '$schema',
            f'Schema family mismatch: expected {artifact_type}, got {family}',
        ))

    version = _schema_version(url)
    acceptable = _ACCEPTABLE_VERSIONS.get(artifact_type, set())
    if version and acceptable and version not in acceptable:
        issues.append(SchemaIssue(
            'warning', '$schema',
            f'Schema version {version} not in accepted set {acceptable}',
        ))


def _validate_position(data: dict, issues: List[SchemaIssue]) -> None:
    pos = data.get('position')
    if pos is None:
        return
    if not isinstance(pos, dict):
        issues.append(SchemaIssue('error', 'position',
                                  'position must be an object'))
        return
    for key in ('x', 'y', 'z', 'height', 'width'):
        _coerce_number(pos, key, issues, 'position')
    for dim in ('height', 'width'):
        val = pos.get(dim)
        if isinstance(val, (int, float)) and val < 0:
            issues.append(SchemaIssue(
                'error', f'position.{dim}',
                f'{dim} must be non-negative, got {val}',
            ))
    _coerce_number(pos, 'tabOrder', issues, 'position')


def _validate_visual(data: dict, issues: List[SchemaIssue]) -> None:
    _validate_schema_url(data, 'visual', issues)
    _validate_position(data, issues)

    vis = data.get('visual')
    if vis is None:
        return
    if not isinstance(vis, dict):
        issues.append(SchemaIssue('error', 'visual',
                                  'visual must be an object'))
        return

    vtype = vis.get('visualType')
    if vtype and vtype not in KNOWN_VISUAL_TYPES:
        issues.append(SchemaIssue(
            'warning', 'visual.visualType',
            f'Unknown visual type: {vtype}',
        ))

    query = vis.get('query')
    if query is not None:
        if not isinstance(query, dict):
            issues.append(SchemaIssue('error', 'visual.query',
                                      'query must be an object'))
        else:
            qs = query.get('queryState')
            if qs is not None and not isinstance(qs, dict):
                issues.append(SchemaIssue('error', 'visual.query.queryState',
                                          'queryState must be an object'))


def _validate_page(data: dict, issues: List[SchemaIssue]) -> None:
    _validate_schema_url(data, 'page', issues)

    if not data.get('name'):
        issues.append(SchemaIssue('error', 'name', 'Page name is required'))
    if not data.get('displayName'):
        issues.append(SchemaIssue('error', 'displayName',
                                  'Page displayName is required'))

    for key in ('width', 'height'):
        _coerce_number(data, key, issues, '')
        val = data.get(key)
        if isinstance(val, (int, float)) and val <= 0:
            issues.append(SchemaIssue('error', key,
                                      f'{key} must be positive, got {val}'))

    pt = data.get('pageType', '')
    if pt and pt not in KNOWN_PAGE_TYPES:
        issues.append(SchemaIssue(
            'warning', 'pageType', f'Unknown pageType: {pt}',
        ))


def _validate_report(data: dict, issues: List[SchemaIssue]) -> None:
    _validate_schema_url(data, 'report', issues)

    tc = data.get('themeCollection')
    if tc is not None:
        if not isinstance(tc, dict):
            issues.append(SchemaIssue('error', 'themeCollection',
                                      'themeCollection must be an object'))
        else:
            bt = tc.get('baseTheme')
            if bt is not None:
                if not isinstance(bt, dict):
                    issues.append(SchemaIssue(
                        'error', 'themeCollection.baseTheme',
                        'baseTheme must be an object'))
                elif not bt.get('name'):
                    issues.append(SchemaIssue(
                        'warning', 'themeCollection.baseTheme.name',
                        'baseTheme name is empty'))

    settings = data.get('settings')
    if settings is not None and not isinstance(settings, dict):
        issues.append(SchemaIssue('error', 'settings',
                                  'settings must be an object'))

    fc = data.get('filterConfig')
    if fc is not None:
        if not isinstance(fc, dict):
            issues.append(SchemaIssue('error', 'filterConfig',
                                      'filterConfig must be an object'))
        else:
            filters = fc.get('filters')
            if filters is not None and not isinstance(filters, list):
                issues.append(SchemaIssue('error', 'filterConfig.filters',
                                          'filters must be a list'))


def _validate_bookmark(data: dict, issues: List[SchemaIssue]) -> None:
    _validate_schema_url(data, 'bookmark', issues)

    if not data.get('name'):
        issues.append(SchemaIssue('error', 'name',
                                  'Bookmark name is required'))
    if not data.get('displayName'):
        issues.append(SchemaIssue('warning', 'displayName',
                                  'Bookmark displayName is empty'))

    es = data.get('explorationState')
    if es is not None:
        if not isinstance(es, dict):
            issues.append(SchemaIssue('error', 'explorationState',
                                      'explorationState must be an object'))
        else:
            if not es.get('activeSection'):
                issues.append(SchemaIssue(
                    'warning', 'explorationState.activeSection',
                    'activeSection is empty'))


def _validate_pages_metadata(data: dict, issues: List[SchemaIssue]) -> None:
    _validate_schema_url(data, 'pages_metadata', issues)

    po = data.get('pageOrder')
    if po is None:
        issues.append(SchemaIssue('error', 'pageOrder',
                                  'pageOrder is required'))
    elif not isinstance(po, list):
        issues.append(SchemaIssue('error', 'pageOrder',
                                  'pageOrder must be a list'))
    else:
        if len(po) != len(set(po)):
            issues.append(SchemaIssue('warning', 'pageOrder',
                                      'Duplicate entries in pageOrder'))


def _validate_version(data: dict, issues: List[SchemaIssue]) -> None:
    _validate_schema_url(data, 'version', issues)


def _validate_definition_pbir(data: dict, issues: List[SchemaIssue]) -> None:
    _validate_schema_url(data, 'definition_pbir', issues)

    ds = data.get('datasetReference')
    if ds is not None and not isinstance(ds, dict):
        issues.append(SchemaIssue('error', 'datasetReference',
                                  'datasetReference must be an object'))


_VALIDATORS = {
    'visual': _validate_visual,
    'page': _validate_page,
    'report': _validate_report,
    'bookmark': _validate_bookmark,
    'pages_metadata': _validate_pages_metadata,
    'version': _validate_version,
    'definition_pbir': _validate_definition_pbir,
}


def validate_artifact(json_data: Any, artifact_type: str,
                      file_path: str = '') -> SchemaResult:
    """Validate a parsed JSON artifact against PBI Desktop schema rules."""
    result = SchemaResult(artifact_type=artifact_type, file_path=file_path)
    if json_data is None or not isinstance(json_data, dict):
        result.issues.append(SchemaIssue('error', '',
                                          'Artifact is not a JSON object'))
        return result

    validator_fn = _VALIDATORS.get(artifact_type)
    if validator_fn is None:
        result.issues.append(SchemaIssue(
            'warning', '',
            f'No schema validator for artifact type: {artifact_type}',
        ))
        return result

    validator_fn(json_data, result.issues)
    return result


def detect_artifact_type(json_data: dict) -> Optional[str]:
    """Infer artifact type from ``$schema`` URL."""
    url = json_data.get('$schema', '') if isinstance(json_data, dict) else ''
    return _schema_family(url)


def validate_report_dir(definition_dir: str) -> List[SchemaResult]:
    """Walk a PBIR ``definition/`` directory and validate all JSON artifacts."""
    results: List[SchemaResult] = []
    if not os.path.isdir(definition_dir):
        r = SchemaResult(artifact_type='directory', file_path=definition_dir)
        r.issues.append(SchemaIssue('error', '',
                                     'Directory does not exist'))
        results.append(r)
        return results

    for dirpath, _dirnames, filenames in os.walk(definition_dir):
        for fname in filenames:
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                r = SchemaResult(artifact_type='unknown', file_path=fpath)
                r.issues.append(SchemaIssue('error', '',
                                             f'Failed to load: {exc}'))
                results.append(r)
                continue

            atype = detect_artifact_type(data)
            if atype is None:
                continue

            result = validate_artifact(data, atype, file_path=fpath)
            results.append(result)

    return results
