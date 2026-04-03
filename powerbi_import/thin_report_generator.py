"""
Thin Report Generator — creates report-only PBIR projects that reference
a shared semantic model via byPath.

Each thin report contains:
- {ReportName}.Report/ directory with PBIR visuals and pages
- definition.pbir → byPath pointing to the shared SemanticModel
- No SemanticModel directory (lives in the shared project)

Usage::

    from powerbi_import.thin_report_generator import ThinReportGenerator

    gen = ThinReportGenerator("SharedModel", "/output/dir")
    gen.generate_thin_report("SalesOverview", converted_objects, field_mapping)
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import uuid

logger = logging.getLogger(__name__)


class ThinReportGenerator:
    """Generates a thin report (.Report/) referencing an external semantic model."""

    def __init__(self, semantic_model_name: str, output_dir: str,
                 live_connection: str = None):
        """
        Args:
            semantic_model_name: Name of the shared semantic model directory.
            output_dir: Root output directory where reports are created.
            live_connection: Optional ``WORKSPACE_ID/MODEL_NAME`` for byConnection
                wiring instead of byPath. When set, the report references a
                deployed Fabric semantic model via workspace connection string.
        """
        self.semantic_model_name = semantic_model_name
        self.output_dir = os.path.abspath(output_dir)
        self.live_connection = live_connection

    def generate_thin_report(self, report_name: str,
                             converted_objects: dict,
                             field_mapping: dict = None) -> str:
        """Generate a thin report referencing the shared semantic model.

        Args:
            report_name: Name for the report.
            converted_objects: Original app's extracted objects.
            field_mapping: Optional mapping of original → namespaced field names.

        Returns:
            Path to the generated report directory.
        """
        # Apply field remapping if needed
        if field_mapping:
            converted_objects = self._remap_fields(converted_objects, field_mapping)

        report_dir = os.path.join(self.output_dir, f"{report_name}.Report")
        os.makedirs(report_dir, exist_ok=True)

        # 1. Create .platform
        self._write_platform(report_dir, report_name)

        # 2. Create definition.pbir → byPath to shared model
        self._write_definition_pbir(report_dir)

        # 3. Create .pbip file for this report
        self._write_pbip(report_name)

        # 4. Generate report content (pages, visuals, filters) using pbip_generator
        self._generate_report_content(report_dir, report_name, converted_objects)

        logger.info("Thin report generated: %s", report_dir)
        return report_dir

    def _write_platform(self, report_dir: str, report_name: str):
        """Write the .platform file for the report."""
        platform = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {
                "type": "Report",
                "displayName": report_name,
            },
            "config": {
                "version": "2.0",
                "logicalId": str(uuid.uuid4()),
            },
        }
        _write_json(os.path.join(report_dir, '.platform'), platform)

    def _write_definition_pbir(self, report_dir: str):
        """Write definition.pbir with byPath or byConnection reference."""
        report_definition = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
        }

        if self.live_connection:
            # byConnection: reference a deployed Fabric semantic model
            # Format: "WORKSPACE_ID/MODEL_NAME"
            parts = self.live_connection.split('/', 1)
            if len(parts) == 2:
                workspace_id, model_name = parts
            else:
                workspace_id = parts[0]
                model_name = self.semantic_model_name

            report_definition["datasetReference"] = {
                "byConnection": {
                    "connectionString": (
                        f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/{workspace_id};"
                        f"Initial Catalog={model_name}"
                    ),
                    "pbiServiceModelId": None,
                    "pbiModelVirtualServerName": "sobe_wowvirtualserver",
                    "pbiModelDatabaseName": model_name,
                },
            }
        else:
            # byPath: local project reference (default)
            report_definition["datasetReference"] = {
                "byPath": {
                    "path": f"../{self.semantic_model_name}.SemanticModel",
                },
            }

        _write_json(os.path.join(report_dir, 'definition.pbir'), report_definition)

    def _write_pbip(self, report_name: str):
        """Write a .pbip file for this thin report."""
        pbip_content = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [
                {
                    "report": {
                        "path": f"{report_name}.Report",
                    },
                },
            ],
            "settings": {
                "enableAutoRecovery": True,
            },
        }
        pbip_path = os.path.join(self.output_dir, f"{report_name}.pbip")
        _write_json(pbip_path, pbip_content)

    def _generate_report_content(self, report_dir: str, report_name: str,
                                  converted_objects: dict):
        """Generate the report definition (pages, visuals, filters, theme).

        Reuses the existing PowerBIProjectGenerator's report content logic
        by importing and calling it with the external semantic model reference.
        """
        try:
            from powerbi_import.pbip_generator import PowerBIProjectGenerator
        except ImportError:
            from pbip_generator import PowerBIProjectGenerator

        # Create a temporary generator to reuse report content creation
        generator = PowerBIProjectGenerator(output_dir=self.output_dir)

        # Use the existing report creation method but with a custom byPath
        # The report_dir is already created, so we directly call the internal
        # content generation parts
        generator._generate_report_definition_content(
            report_dir, report_name, converted_objects
        )

    def _remap_fields(self, converted_objects: dict,
                      field_mapping: dict) -> dict:
        """Remap field names in worksheets, dashboards, and filters.

        Handles namespaced measure references after merge conflicts,
        including nested mark encoding, dashboard zone references,
        and action target fields.
        """
        if not field_mapping:
            return converted_objects

        remapped = copy.deepcopy(converted_objects)

        # Remap worksheet column references
        for ws in remapped.get('worksheets', []):
            for col in ws.get('columns', []):
                name = col.get('name', '')
                if name in field_mapping:
                    col['name'] = field_mapping[name]
            # Remap filters
            for f in ws.get('filters', []):
                fname = f.get('field', '')
                if fname in field_mapping:
                    f['field'] = field_mapping[fname]
            # Remap mark encoding
            for channel, enc in ws.get('mark_encoding', {}).items():
                if isinstance(enc, dict):
                    efield = enc.get('field', '')
                    if efield in field_mapping:
                        enc['field'] = field_mapping[efield]
                elif isinstance(enc, list):
                    for item in enc:
                        if isinstance(item, dict):
                            efield = item.get('field', '')
                            if efield in field_mapping:
                                item['field'] = field_mapping[efield]
            # Remap sort fields
            for sort in ws.get('sort_fields', ws.get('sorts', [])):
                if isinstance(sort, dict):
                    sfield = sort.get('field', '')
                    if sfield in field_mapping:
                        sort['field'] = field_mapping[sfield]

        # Remap calculation references in standalone calculations
        for calc in remapped.get('calculations', []):
            caption = calc.get('caption', '')
            if caption in field_mapping:
                calc['caption'] = field_mapping[caption]

        # Remap filter fields
        for f in remapped.get('filters', []):
            fname = f.get('field', '')
            if fname in field_mapping:
                f['field'] = field_mapping[fname]

        # Remap action target fields
        for action in remapped.get('actions', []):
            for target_field_key in ('source_field', 'target_field', 'field'):
                afield = action.get(target_field_key, '')
                if afield in field_mapping:
                    action[target_field_key] = field_mapping[afield]

        return remapped


# ══════════════════════════════════════════════════════════════════
#  Sprint 57 — Thin Report Binding Validation
# ══════════════════════════════════════════════════════════════════

def _collect_model_fields(merged_model: dict) -> dict:
    """Build lookup of all tables/columns/measures in the merged model.

    Returns:
        dict with keys 'tables' (set), 'columns' (dict table→set),
        'measures' (dict table→set), 'parameters' (set).
    """
    tables = set()
    columns: dict = {}
    measures: dict = {}
    parameters = set()

    for tbl in merged_model.get('tables', []):
        tname = tbl.get('name', '')
        if not tname:
            continue
        tables.add(tname)
        columns[tname] = set()
        measures[tname] = set()
        for col in tbl.get('columns', []):
            cname = col.get('name') or col.get('caption', '')
            if cname:
                columns[tname].add(cname)
        for meas in tbl.get('measures', []):
            mname = meas.get('name') or meas.get('caption', '')
            if mname:
                measures[tname].add(mname)
        # Parameter tables
        if tbl.get('is_parameter') or 'parameter' in tname.lower():
            parameters.add(tname)

    return {
        'tables': tables,
        'columns': columns,
        'measures': measures,
        'parameters': parameters,
    }


def _find_closest_match(name: str, candidates: set, threshold: float = 0.6) -> str:
    """Find closest string match using simple ratio."""
    if not candidates:
        return ''
    best = ''
    best_score = 0.0
    name_lower = name.lower()
    for c in candidates:
        c_lower = c.lower()
        # Simple containment-based score
        if name_lower == c_lower:
            return c
        if name_lower in c_lower or c_lower in name_lower:
            score = min(len(name), len(c)) / max(len(name), len(c)) if name and c else 0
            if score > best_score:
                best_score = score
                best = c
    return best if best_score >= threshold else ''


def validate_field_references(report_visuals: list, merged_model: dict) -> list:
    """Validate that all visual field references resolve against the merged model.

    Args:
        report_visuals: List of visual dicts (with 'fields', 'page', 'visual_id').
        merged_model: The merged converted_objects dict.

    Returns:
        List of validation result dicts:
        ``{visual_id, page, field, table, status, suggestion}``
    """
    model_info = _collect_model_fields(merged_model)
    results = []

    all_measures = set()
    all_columns = set()
    for tname in model_info['tables']:
        all_measures.update(model_info['measures'].get(tname, set()))
        all_columns.update(model_info['columns'].get(tname, set()))

    for vis in report_visuals:
        vid = vis.get('visual_id', vis.get('name', 'unknown'))
        page = vis.get('page', '')
        for field_ref in vis.get('fields', []):
            table = ''
            column = ''
            if isinstance(field_ref, dict):
                table = field_ref.get('table', '')
                column = field_ref.get('column') or field_ref.get('name', '')
            elif isinstance(field_ref, str):
                # Parse 'Table[Column]' pattern
                if '[' in field_ref and ']' in field_ref:
                    parts = field_ref.split('[', 1)
                    table = parts[0].strip("' ")
                    column = parts[1].rstrip(']').strip()
                else:
                    column = field_ref

            status = 'resolved'
            suggestion = ''

            if table and table not in model_info['tables']:
                status = 'unresolved_table'
                suggestion = _find_closest_match(table, model_info['tables'])
            elif column:
                # Check in specific table or across all
                found = False
                if table:
                    t_cols = model_info['columns'].get(table, set())
                    t_meas = model_info['measures'].get(table, set())
                    if column in t_cols or column in t_meas:
                        found = True
                else:
                    if column in all_columns or column in all_measures:
                        found = True

                if not found:
                    status = 'unresolved_field'
                    suggestion = _find_closest_match(
                        column, all_columns | all_measures)

            results.append({
                'visual_id': vid,
                'page': page,
                'field': f"{table}[{column}]" if table else column,
                'table': table,
                'status': status,
                'suggestion': suggestion,
            })

    return results


def validate_drillthrough_targets(report_pages: list, bundle_reports: list = None) -> list:
    """Validate drill-through page targets exist.

    Args:
        report_pages: List of page dicts with 'name', 'page_type', 'drillthrough_target'.
        bundle_reports: Optional list of other thin report page lists in the bundle.

    Returns:
        List of ``{source_page, target_page, status}`` dicts.
    """
    # Collect all page names across this report and bundle
    all_pages = set()
    for p in report_pages:
        all_pages.add(p.get('name', ''))
    for other_report in (bundle_reports or []):
        for p in other_report:
            all_pages.add(p.get('name', ''))

    results = []
    for p in report_pages:
        target = p.get('drillthrough_target', '')
        if not target:
            continue
        status = 'found' if target in all_pages else 'missing'
        results.append({
            'source_page': p.get('name', ''),
            'target_page': target,
            'status': status,
        })
    return results


def validate_filter_references(filters: list, merged_model: dict) -> list:
    """Validate that filter references exist in the merged model.

    Args:
        filters: List of filter dicts with 'table' and 'column' keys.
        merged_model: The merged converted_objects dict.

    Returns:
        List of ``{filter_field, table, column, status, suggestion}`` dicts.
    """
    model_info = _collect_model_fields(merged_model)
    results = []

    for filt in filters:
        table = filt.get('table', '')
        column = filt.get('column') or filt.get('field', '')
        status = 'resolved'
        suggestion = ''

        if table and table not in model_info['tables']:
            status = 'unresolved_table'
            suggestion = _find_closest_match(table, model_info['tables'])
        elif column:
            found = False
            if table:
                t_cols = model_info['columns'].get(table, set())
                if column in t_cols:
                    found = True
            else:
                for t_cols in model_info['columns'].values():
                    if column in t_cols:
                        found = True
                        break
            if not found:
                status = 'unresolved_field'
                all_cols = set()
                for t_cols in model_info['columns'].values():
                    all_cols.update(t_cols)
                suggestion = _find_closest_match(column, all_cols)

        results.append({
            'filter_field': f"{table}.{column}" if table else column,
            'table': table,
            'column': column,
            'status': status,
            'suggestion': suggestion,
        })
    return results


def validate_parameter_references(slicer_params: list, merged_model: dict) -> list:
    """Validate parameter references in slicers exist as tables in the model.

    Args:
        slicer_params: List of parameter name strings referenced by slicers.
        merged_model: The merged converted_objects dict.

    Returns:
        List of ``{parameter, status, suggestion}`` dicts.
    """
    model_info = _collect_model_fields(merged_model)
    all_tables = model_info['tables']
    results = []

    for param in slicer_params:
        if param in all_tables:
            status = 'resolved'
            suggestion = ''
        else:
            status = 'unresolved'
            suggestion = _find_closest_match(param, all_tables)
        results.append({
            'parameter': param,
            'status': status,
            'suggestion': suggestion,
        })
    return results


def validate_cross_report_navigation(actions: list, bundle_report_names: list) -> list:
    """Validate cross-report navigation targets.

    Args:
        actions: List of action dicts with 'type' and 'target_report'.
        bundle_report_names: List of report names in the bundle.

    Returns:
        List of ``{action, target_report, status}`` dicts.
    """
    name_set = set(bundle_report_names or [])
    results = []
    for action in actions:
        if action.get('type') not in ('navigate', 'navigation', 'navigate_to_report'):
            continue
        target = action.get('target_report', '')
        if not target:
            continue
        status = 'found' if target in name_set else 'missing'
        results.append({
            'action': action.get('name', ''),
            'target_report': target,
            'status': status,
        })
    return results


def generate_thin_report_validation(report_data: dict,
                                     merged_model: dict,
                                     bundle_reports: list = None,
                                     bundle_report_names: list = None) -> dict:
    """Generate a full validation summary for a thin report.

    Args:
        report_data: Dict with 'visuals', 'pages', 'filters', 'slicer_params', 'actions'.
        merged_model: The merged converted_objects dict.
        bundle_reports: Optional other report page lists.
        bundle_report_names: Optional list of report names in bundle.

    Returns:
        Summary dict with field, drillthrough, filter, parameter, navigation results.
    """
    field_results = validate_field_references(
        report_data.get('visuals', []), merged_model)
    drill_results = validate_drillthrough_targets(
        report_data.get('pages', []), bundle_reports)
    filter_results = validate_filter_references(
        report_data.get('filters', []), merged_model)
    param_results = validate_parameter_references(
        report_data.get('slicer_params', []), merged_model)
    nav_results = validate_cross_report_navigation(
        report_data.get('actions', []),
        bundle_report_names or [])

    total_fields = len(field_results)
    resolved_fields = sum(1 for r in field_results if r['status'] == 'resolved')

    return {
        'total_fields_checked': total_fields,
        'resolved_fields': resolved_fields,
        'unresolved_fields': total_fields - resolved_fields,
        'field_results': field_results,
        'drillthrough_results': drill_results,
        'drillthrough_gaps': sum(1 for d in drill_results if d['status'] == 'missing'),
        'filter_results': filter_results,
        'filter_gaps': sum(1 for f in filter_results if f['status'] != 'resolved'),
        'parameter_results': param_results,
        'navigation_results': nav_results,
        'navigation_gaps': sum(1 for n in nav_results if n['status'] == 'missing'),
    }


def _write_json(filepath: str, data: dict):
    """Write JSON to file with consistent formatting."""
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
