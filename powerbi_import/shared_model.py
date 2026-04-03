"""
Shared Semantic Model — Core Merge Engine.

Merges multiple Qlik app extractions into a single unified
semantic model, enabling the Power BI "thin report" pattern where
N reports reference one shared semantic model.

Pipeline:
    1. Build table fingerprints (connection + physical name)
    2. Detect merge candidates (tables appearing in multiple apps)
    3. Merge tables (column union), measures, relationships, parameters, RLS
    4. Return a single merged converted_objects dict

Usage (programmatic)::

    from powerbi_import.shared_model import assess_merge, merge_semantic_models

    assessment = assess_merge(all_extracted, app_names)
    merged = merge_semantic_models(all_extracted, assessment, "SharedModel")

Usage (CLI)::

    python migrate.py --shared-model wb1.qvf wb2.qvf --model-name "Sales Analytics"
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  Data classes
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TableFingerprint:
    """Uniquely identifies a physical table across apps."""
    connection_type: str
    server: str
    database: str
    schema: str
    table_name: str

    def fingerprint(self) -> str:
        """Normalized hash key for matching."""
        raw = '\x00'.join([
            self.connection_type.lower().strip(),
            self.server.lower().strip(),
            self.database.lower().strip(),
            self.schema.lower().strip(),
            self.table_name.lower().strip(),
        ])
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

    def __eq__(self, other):
        if not isinstance(other, TableFingerprint):
            return NotImplemented
        return self.fingerprint() == other.fingerprint()

    def __hash__(self):
        return hash(self.fingerprint())


@dataclass
class MergeCandidate:
    """A table that appears in multiple apps."""
    fingerprint: TableFingerprint
    table_name: str
    sources: List[Tuple[str, dict, dict]]  # [(app_name, table_dict, connection_dict)]
    column_overlap: float = 0.0
    conflicts: List[str] = field(default_factory=list)


@dataclass
class MeasureConflict:
    """A measure with the same name but different DAX across apps."""
    name: str
    table: str
    variants: Dict[str, str]  # {app_name: formula}


@dataclass
class MergeAssessment:
    """Complete analysis of merge feasibility."""
    apps: List[str]
    merge_candidates: List[MergeCandidate] = field(default_factory=list)
    unique_tables: Dict[str, List[str]] = field(default_factory=dict)
    measure_conflicts: List[MeasureConflict] = field(default_factory=list)
    measure_duplicates_removed: int = 0
    relationship_duplicates_removed: int = 0
    parameter_conflicts: List[dict] = field(default_factory=list)
    parameter_duplicates_removed: int = 0
    rls_conflicts: List[dict] = field(default_factory=list)
    total_tables: int = 0
    unique_table_count: int = 0
    merge_score: int = 0
    recommendation: str = "separate"
    # Tables unique to one app but linked (via relationships or shared columns)
    linked_unique_tables: Dict[str, List[str]] = field(default_factory=dict)
    # Tables with no links to any other table in the merged model
    isolated_tables: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "apps": self.apps,
            "total_tables": self.total_tables,
            "unique_table_count": self.unique_table_count,
            "tables_saved": self.total_tables - self.unique_table_count,
            "merge_candidates": [
                {
                    "table_name": mc.table_name,
                    "apps": [s[0] for s in mc.sources],
                    "column_overlap": round(mc.column_overlap, 2),
                    "conflicts": mc.conflicts,
                }
                for mc in self.merge_candidates
            ],
            "unique_tables": self.unique_tables,
            "measure_conflicts": [
                {"name": mc.name, "table": mc.table, "variants": mc.variants}
                for mc in self.measure_conflicts
            ],
            "measure_duplicates_removed": self.measure_duplicates_removed,
            "relationship_duplicates_removed": self.relationship_duplicates_removed,
            "parameter_conflicts": self.parameter_conflicts,
            "parameter_duplicates_removed": self.parameter_duplicates_removed,
            "rls_conflicts": self.rls_conflicts,
            "merge_score": self.merge_score,
            "recommendation": self.recommendation,
            "linked_unique_tables": self.linked_unique_tables,
            "isolated_tables": self.isolated_tables,
        }


@dataclass
class MergeManifest:
    """Tracks merge provenance for incremental add/remove workflows.

    Written to ``merge_manifest.json`` after a merge completes, enabling
    subsequent ``--add-to-model`` and ``--remove-from-model`` operations
    without re-extracting all original apps.
    """
    model_name: str
    apps: List[dict] = field(default_factory=list)
    # app entry: {"name", "path", "hash", "tables", "measures", "exclusive_tables"}
    table_fingerprints: Dict[str, str] = field(default_factory=dict)
    # {table_name: fingerprint_hex}
    artifact_counts: dict = field(default_factory=dict)
    # {"tables", "measures", "relationships", "rls_roles", "parameters"}
    merge_config_snapshot: dict = field(default_factory=dict)
    validation_score: int = 0
    merge_score: int = 0
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "model_name": self.model_name,
            "apps": self.apps,
            "table_fingerprints": self.table_fingerprints,
            "artifact_counts": self.artifact_counts,
            "merge_config_snapshot": self.merge_config_snapshot,
            "validation_score": self.validation_score,
            "merge_score": self.merge_score,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MergeManifest':
        return cls(
            model_name=data.get("model_name", ""),
            apps=data.get("apps", []),
            table_fingerprints=data.get("table_fingerprints", {}),
            artifact_counts=data.get("artifact_counts", {}),
            merge_config_snapshot=data.get("merge_config_snapshot", {}),
            validation_score=data.get("validation_score", 0),
            merge_score=data.get("merge_score", 0),
            timestamp=data.get("timestamp", ""),
        )

    def save(self, output_dir: str) -> str:
        """Write merge_manifest.json to *output_dir*. Returns file path."""
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "merge_manifest.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    @classmethod
    def load(cls, path: str) -> 'MergeManifest':
        """Load manifest from a JSON file or directory containing one."""
        if os.path.isdir(path):
            path = os.path.join(path, "merge_manifest.json")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def find_app(self, name: str) -> Optional[dict]:
        """Find a app entry by name (case-insensitive)."""
        lower = name.lower()
        for wb in self.apps:
            if wb.get("name", "").lower() == lower:
                return wb
        return None

    def exclusive_tables(self, app_name: str) -> List[str]:
        """Tables contributed solely by *app_name*."""
        wb = self.find_app(app_name)
        if not wb:
            return []
        return list(wb.get("exclusive_tables", []))


def build_merge_manifest(model_name: str,
                         all_extracted: List[dict],
                         app_names: List[str],
                         app_paths: Optional[List[str]],
                         merged: dict,
                         assessment: 'MergeAssessment',
                         validation_score: int = 0,
                         merge_config: Optional[dict] = None) -> MergeManifest:
    """Build a :class:`MergeManifest` from merge results.

    Args:
        model_name: Name of the shared semantic model.
        all_extracted: Per-app converted_objects list.
        app_names: Parallel list of app names.
        app_paths: Parallel list of app file paths (may be ``None``).
        merged: The merged ``converted_objects`` dict.
        assessment: The :class:`MergeAssessment`.
        validation_score: 0–100 from post-merge validation.
        merge_config: Optional merge config dict snapshot.

    Returns:
        A populated :class:`MergeManifest`.
    """
    # Collect per-app info
    wb_entries = []
    # Build set of shared table names (appear in >1 app)
    all_wb_tables: Dict[str, List[str]] = {}  # table_name -> [wb_names]
    for wb_name, extracted in zip(app_names, all_extracted):
        fps = build_table_fingerprints(extracted.get('datasources', []))
        for tname in fps:
            all_wb_tables.setdefault(tname, []).append(wb_name)

    shared_table_names = {t for t, wbs in all_wb_tables.items() if len(wbs) > 1}

    for idx, (wb_name, extracted) in enumerate(zip(app_names, all_extracted)):
        fps = build_table_fingerprints(extracted.get('datasources', []))
        wb_tables = list(fps.keys())
        exclusive = [t for t in wb_tables if t not in shared_table_names]

        # Count measures from this app's calculations
        wb_measures = [
            c for c in extracted.get('calculations', [])
            if c.get('_classification') == 'measure' or c.get('role') == 'measure'
        ]

        wb_path = ""
        if app_paths and idx < len(app_paths):
            wb_path = app_paths[idx]
        file_hash = _file_hash(wb_path) if wb_path and os.path.isfile(wb_path) else ""

        wb_entries.append({
            "name": wb_name,
            "path": wb_path,
            "hash": file_hash,
            "tables": wb_tables,
            "measures": [c.get('caption', c.get('name', '')) for c in wb_measures],
            "exclusive_tables": exclusive,
        })

    # Build table fingerprint map from merged datasources
    fp_map = {}
    for ds in merged.get('datasources', []):
        fps = build_table_fingerprints([ds])
        for tname, (fp, _, _) in fps.items():
            fp_map[tname] = fp.fingerprint()

    # Count artifacts in merged model
    merged_ds = merged.get('datasources', [{}])[0] if merged.get('datasources') else {}
    counts = {
        "tables": len(merged_ds.get('tables', [])),
        "measures": len([c for c in merged.get('calculations', [])
                        if c.get('_classification') == 'measure' or c.get('role') == 'measure']),
        "relationships": len(merged_ds.get('relationships', [])),
        "rls_roles": len(merged.get('user_filters', [])),
        "parameters": len(merged.get('parameters', [])),
    }

    return MergeManifest(
        model_name=model_name,
        apps=wb_entries,
        table_fingerprints=fp_map,
        artifact_counts=counts,
        merge_config_snapshot=merge_config or {},
        validation_score=validation_score,
        merge_score=assessment.merge_score,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _file_hash(path: str) -> str:
    """SHA-256 hash of a file (first 16 hex chars)."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return ""


# ═══════════════════════════════════════════════════════════════════
#  Table fingerprinting
# ═══════════════════════════════════════════════════════════════════

_SCHEMA_PATTERN = re.compile(r'^\[?([^\]]*)\]?\.\[?([^\]]*)\]?$')


def _parse_table_name(raw_name: str) -> Tuple[str, str]:
    """Parse '[schema].[table]' or 'table' into (schema, table)."""
    m = _SCHEMA_PATTERN.match(raw_name.strip())
    if m:
        return m.group(1), m.group(2)
    # No schema prefix
    clean = raw_name.strip().strip('[]')
    return 'dbo', clean


def build_table_fingerprints(datasources: list) -> Dict[str, Tuple[TableFingerprint, dict, dict]]:
    """Build fingerprints for all tables in a app's datasources.

    Handles both physical tables (connection+schema+name) and custom SQL
    tables (connection+normalized SQL hash).

    Returns:
        {physical_table_name: (fingerprint, table_dict, connection_dict)}
    """
    result = {}
    for ds in datasources:
        conn = ds.get('connection', {})
        conn_type = conn.get('type', 'unknown')
        details = conn.get('details', {})
        server = details.get('server', details.get('host', ''))
        database = details.get('database', details.get('db', ''))

        for table in ds.get('tables', []):
            ttype = table.get('type', 'table')
            raw_name = table.get('name', '')

            # Custom SQL tables: fingerprint by normalized SQL hash
            sql = table.get('custom_sql', table.get('query', ''))
            if sql:
                sql_hash = _hash_sql(sql)
                fp = TableFingerprint(
                    connection_type=conn_type,
                    server=server,
                    database=database,
                    schema='_custom_sql',
                    table_name=sql_hash,
                )
                result[raw_name] = (fp, table, conn)
                continue

            if ttype != 'table':
                continue
            schema, tname = _parse_table_name(raw_name)
            fp = TableFingerprint(
                connection_type=conn_type,
                server=server,
                database=database,
                schema=schema,
                table_name=tname,
            )
            result[raw_name] = (fp, table, conn)
    return result


# ═══════════════════════════════════════════════════════════════════
#  Column overlap
# ═══════════════════════════════════════════════════════════════════

def compute_column_overlap(table_a: dict, table_b: dict) -> float:
    """Compute Jaccard similarity of column names between two tables.

    Returns:
        Float 0.0–1.0 representing column name overlap.
    """
    cols_a = {c.get('name', '').lower() for c in table_a.get('columns', [])}
    cols_b = {c.get('name', '').lower() for c in table_b.get('columns', [])}

    if not cols_a and not cols_b:
        return 0.0

    intersection = cols_a & cols_b
    union = cols_a | cols_b

    if not union:
        return 0.0

    return len(intersection) / len(union)


# ═══════════════════════════════════════════════════════════════════
#  Merge assessment
# ═══════════════════════════════════════════════════════════════════

def assess_merge(all_extracted: List[dict],
                 app_names: List[str]) -> MergeAssessment:
    """Analyze multiple extracted app datasets for merge potential.

    Args:
        all_extracted: List of converted_objects dicts (one per app)
        app_names: List of app names (parallel with all_extracted)

    Returns:
        MergeAssessment with full analysis.
    """
    assessment = MergeAssessment(apps=list(app_names))

    # 1. Build fingerprints for all tables in all apps
    # fingerprint_hash → [(app_name, table_dict, connection_dict, raw_table_name)]
    fp_map: Dict[str, list] = {}
    all_table_count = 0

    for wb_name, extracted in zip(app_names, all_extracted):
        datasources = extracted.get('datasources', [])
        fps = build_table_fingerprints(datasources)
        for raw_name, (fp, table, conn) in fps.items():
            all_table_count += 1
            fp_hash = fp.fingerprint()
            if fp_hash not in fp_map:
                fp_map[fp_hash] = []
            fp_map[fp_hash].append((wb_name, table, conn, raw_name, fp))

    assessment.total_tables = all_table_count

    # 2. Identify merge candidates (tables appearing in 2+ apps)
    seen_tables = set()
    unique_per_app: Dict[str, List[str]] = {wb: [] for wb in app_names}

    for fp_hash, entries in fp_map.items():
        unique_wbs = {e[0] for e in entries}
        table_name = entries[0][3]  # raw_name from first entry
        fp = entries[0][4]

        if len(unique_wbs) >= 2:
            # Compute column overlap (pairwise — use first pair)
            overlap = 1.0
            if len(entries) >= 2:
                overlap = compute_column_overlap(entries[0][1], entries[1][1])

            # Check for column type conflicts
            conflicts = _detect_column_conflicts(entries)

            candidate = MergeCandidate(
                fingerprint=fp,
                table_name=table_name,
                sources=[(e[0], e[1], e[2]) for e in entries],
                column_overlap=overlap,
                conflicts=conflicts,
            )
            assessment.merge_candidates.append(candidate)
            seen_tables.add(fp_hash)
        else:
            # Unique to one app
            wb_name = entries[0][0]
            unique_per_app[wb_name].append(table_name)

    assessment.unique_tables = {
        wb: tables for wb, tables in unique_per_app.items() if tables
    }
    assessment.unique_table_count = (
        len(assessment.merge_candidates) +
        sum(len(v) for v in assessment.unique_tables.values())
    )

    # 3. Detect measure conflicts
    measure_conflicts, measure_dupes = _detect_measure_conflicts(all_extracted, app_names)
    assessment.measure_conflicts = measure_conflicts
    assessment.measure_duplicates_removed = measure_dupes

    # 4. Detect relationship duplicates
    assessment.relationship_duplicates_removed = _count_relationship_duplicates(
        all_extracted
    )

    # 5. Detect parameter conflicts
    param_conflicts, param_dupes = _detect_parameter_conflicts(all_extracted, app_names)
    assessment.parameter_conflicts = param_conflicts
    assessment.parameter_duplicates_removed = param_dupes

    # 5b. Classify unique tables as linked vs isolated
    _classify_unique_tables(assessment, all_extracted, app_names, fp_map)

    # 6. Calculate merge score
    assessment.merge_score = calculate_merge_score(assessment)

    # 7. Set recommendation
    if assessment.merge_score >= 60:
        assessment.recommendation = "merge"
    elif assessment.merge_score >= 30:
        assessment.recommendation = "partial"
    else:
        assessment.recommendation = "separate"

    return assessment


def _detect_column_conflicts(entries: list) -> List[str]:
    """Detect column type mismatches across app instances of the same table."""
    conflicts = []
    # Build col_name → {wb_name: datatype}
    col_types: Dict[str, Dict[str, str]] = {}
    for wb_name, table, _conn, _raw, _fp in entries:
        for col in table.get('columns', []):
            cname = col.get('name', '')
            dtype = col.get('datatype', 'string')
            if cname not in col_types:
                col_types[cname] = {}
            col_types[cname][wb_name] = dtype

    for cname, wb_types in col_types.items():
        unique_types = set(wb_types.values())
        if len(unique_types) > 1:
            conflicts.append(
                f"Column '{cname}': type mismatch — " +
                ", ".join(f"{wb}={dt}" for wb, dt in wb_types.items())
            )

    return conflicts


def _detect_measure_conflicts(
    all_extracted: List[dict], app_names: List[str]
) -> Tuple[List[MeasureConflict], int]:
    """Detect measure conflicts and count deduplicatable measures."""
    # measure_key (name, datasource) → {wb_name: formula}
    measure_map: Dict[Tuple[str, str], Dict[str, str]] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        for ds in extracted.get('datasources', []):
            ds_name = ds.get('name', '')
            for calc in ds.get('calculations', []):
                role = calc.get('role', 'measure')
                if role != 'measure':
                    continue
                caption = calc.get('caption', calc.get('name', ''))
                formula = calc.get('formula', '').strip()
                key = caption
                if key not in measure_map:
                    measure_map[key] = {}
                measure_map[key][wb_name] = formula

        # Also check standalone calculations
        for calc in extracted.get('calculations', []):
            role = calc.get('role', 'measure')
            if role != 'measure':
                continue
            caption = calc.get('caption', calc.get('name', ''))
            formula = calc.get('formula', '').strip()
            key = caption
            if key not in measure_map:
                measure_map[key] = {}
            measure_map[key][wb_name] = formula

    conflicts = []
    duplicates = 0

    for name, wb_formulas in measure_map.items():
        if len(wb_formulas) <= 1:
            continue
        unique_formulas = set(wb_formulas.values())
        if len(unique_formulas) == 1:
            duplicates += 1
        else:
            conflicts.append(MeasureConflict(
                name=name, table='', variants=wb_formulas
            ))

    return conflicts, duplicates


def _count_relationship_duplicates(all_extracted: List[dict]) -> int:
    """Count relationship definitions that appear in multiple apps."""
    rel_keys = set()
    duplicates = 0
    for extracted in all_extracted:
        for ds in extracted.get('datasources', []):
            for rel in ds.get('relationships', []):
                key = _relationship_key(rel)
                if key in rel_keys:
                    duplicates += 1
                else:
                    rel_keys.add(key)
    return duplicates


def _relationship_key(rel: dict) -> Tuple[str, str, str, str]:
    """Deduplicate key for a relationship."""
    # Handle different relationship formats
    if 'left' in rel:
        return (
            rel['left'].get('table', '').lower(),
            rel['left'].get('column', '').lower(),
            rel['right'].get('table', '').lower(),
            rel['right'].get('column', '').lower(),
        )
    return (
        rel.get('from_table', '').lower(),
        rel.get('from_column', '').lower(),
        rel.get('to_table', '').lower(),
        rel.get('to_column', '').lower(),
    )


# ═══════════════════════════════════════════════════════════════════
#  Post-merge safety validation (Sprint 55)
# ═══════════════════════════════════════════════════════════════════

# Column type compatibility matrix: (from_type, to_type) → level
# Levels: "ok" (safe promotion), "warn" (lossy), "error" (incompatible)
_TYPE_COMPAT: Dict[Tuple[str, str], str] = {}

_TYPE_NAMES = ['boolean', 'integer', 'int64', 'real', 'double', 'decimal',
               'currency', 'datetime', 'string']

# Build compatibility — wider type absorbs narrower
_SAFE_PROMOTIONS = {
    ('boolean', 'integer'), ('boolean', 'int64'), ('boolean', 'real'),
    ('boolean', 'double'), ('boolean', 'decimal'), ('boolean', 'currency'),
    ('boolean', 'string'),
    ('integer', 'int64'), ('integer', 'real'), ('integer', 'double'),
    ('integer', 'decimal'), ('integer', 'currency'), ('integer', 'string'),
    ('int64', 'real'), ('int64', 'double'), ('int64', 'decimal'),
    ('int64', 'currency'), ('int64', 'string'),
    ('real', 'double'), ('real', 'decimal'), ('real', 'string'),
    ('double', 'decimal'), ('double', 'string'),
    ('decimal', 'string'), ('currency', 'string'),
    ('currency', 'real'), ('currency', 'double'), ('currency', 'decimal'),
    ('datetime', 'string'),
}

for _a in _TYPE_NAMES:
    _TYPE_COMPAT[(_a, _a)] = 'ok'
for _pair in _SAFE_PROMOTIONS:
    _TYPE_COMPAT[_pair] = 'ok'
    _TYPE_COMPAT[(_pair[1], _pair[0])] = 'ok'  # reverse is also ok (wider wins)

_WARN_PROMOTIONS = {
    ('string', 'integer'), ('string', 'int64'), ('string', 'real'),
    ('string', 'double'), ('string', 'decimal'), ('string', 'boolean'),
    ('string', 'currency'),
}
for _pair in _WARN_PROMOTIONS:
    key = (_pair[0], _pair[1])
    rev = (_pair[1], _pair[0])
    if key not in _TYPE_COMPAT:
        _TYPE_COMPAT[key] = 'warn'
    if rev not in _TYPE_COMPAT:
        _TYPE_COMPAT[rev] = 'warn'

_ERROR_PROMOTIONS = {
    ('datetime', 'boolean'), ('datetime', 'integer'), ('datetime', 'int64'),
    ('datetime', 'real'), ('datetime', 'double'), ('datetime', 'decimal'),
    ('datetime', 'currency'),
}
for _pair in _ERROR_PROMOTIONS:
    key = (_pair[0], _pair[1])
    rev = (_pair[1], _pair[0])
    if key not in _TYPE_COMPAT:
        _TYPE_COMPAT[key] = 'error'
    if rev not in _TYPE_COMPAT:
        _TYPE_COMPAT[rev] = 'error'


def check_type_compatibility(type_a: str, type_b: str) -> str:
    """Check compatibility between two column types.

    Returns:
        'ok', 'warn', or 'error'.
    """
    a = type_a.lower().strip()
    b = type_b.lower().strip()
    if a == b:
        return 'ok'
    return _TYPE_COMPAT.get((a, b), 'warn')


def detect_merge_cycles(merged: dict) -> List[List[str]]:
    """Detect circular relationships in merged model using iterative DFS.

    Args:
        merged: The merged converted_objects dict.

    Returns:
        List of cycles, each cycle is a list of table names forming the loop.
    """
    # Build directed graph from relationships
    graph: Dict[str, set] = {}
    for ds in merged.get('datasources', []):
        for rel in ds.get('relationships', []):
            if 'left' in rel:
                from_t = rel['left'].get('table', '')
                to_t = rel['right'].get('table', '')
            else:
                from_t = rel.get('from_table', '')
                to_t = rel.get('to_table', '')
            if from_t and to_t:
                graph.setdefault(from_t, set()).add(to_t)

    # Iterative DFS with explicit stack
    cycles: List[List[str]] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {n: WHITE for n in graph}
    # Also include nodes that are only targets
    for targets in list(graph.values()):
        for t in targets:
            if t not in color:
                color[t] = WHITE

    parent: Dict[str, Optional[str]] = {}

    for start in list(color.keys()):
        if color[start] != WHITE:
            continue
        stack = [(start, False)]  # (node, backtrack_flag)
        while stack:
            node, backtrack = stack.pop()
            if backtrack:
                color[node] = BLACK
                continue
            if color[node] == GRAY:
                continue
            color[node] = GRAY
            stack.append((node, True))  # schedule backtrack
            for neighbor in graph.get(node, set()):
                if color.get(neighbor) == GRAY:
                    # Found cycle — reconstruct path
                    cycle = [neighbor]
                    cur = node
                    while cur != neighbor:
                        cycle.append(cur)
                        cur = parent.get(cur, neighbor)
                    cycle.append(neighbor)
                    cycle.reverse()
                    cycles.append(cycle)
                elif color.get(neighbor, WHITE) == WHITE:
                    parent[neighbor] = node
                    stack.append((neighbor, False))

    return cycles


def detect_type_conflicts(merged: dict) -> List[dict]:
    """Detect column type conflicts across merged tables.

    Compares each table's columns against the type compatibility matrix.
    Only relevant for tables that were merged (have columns from multiple
    apps, tracked via _merge_columns_into).

    Returns:
        List of {table, column, types, level} dicts.
    """
    warnings = []
    for ds in merged.get('datasources', []):
        for table in ds.get('tables', []):
            table_name = table.get('name', '')
            type_history = table.get('_column_type_history', {})
            for col_name, types in type_history.items():
                if len(types) < 2:
                    continue
                unique_types = list(set(types))
                if len(unique_types) < 2:
                    continue
                # Check worst compatibility across all pairs
                worst = 'ok'
                for i in range(len(unique_types)):
                    for j in range(i + 1, len(unique_types)):
                        level = check_type_compatibility(
                            unique_types[i], unique_types[j]
                        )
                        if level == 'error':
                            worst = 'error'
                        elif level == 'warn' and worst != 'error':
                            worst = 'warn'
                if worst != 'ok':
                    warnings.append({
                        'table': table_name,
                        'column': col_name,
                        'types': unique_types,
                        'level': worst,
                    })
    return warnings


# Regex to extract 'Table'[Column] references from DAX
_RE_DAX_TABLE_COL = re.compile(
    r"'([^']+)'\[([^\]]+)\]"
)
# Regex to extract bare [Column] references
_RE_DAX_BARE_COL = re.compile(
    r"(?<!')\[([^\]]+)\]"
)


def validate_merged_dax_references(merged: dict) -> List[dict]:
    """Scan all measures and calc columns for unresolved 'Table'[Column] refs.

    Args:
        merged: The merged converted_objects dict.

    Returns:
        List of {source, source_type, ref, table, column, status, suggestion} dicts.
    """
    # Build inventory of tables and columns
    table_names: set = set()
    table_columns: Dict[str, set] = {}
    for ds in merged.get('datasources', []):
        for table in ds.get('tables', []):
            tname = table.get('name', '')
            table_names.add(tname)
            cols = {c.get('name', '') for c in table.get('columns', [])}
            table_columns[tname] = cols

    # Also add parameter tables from merged parameters
    for param in merged.get('parameters', []):
        pname = param.get('caption', param.get('name', ''))
        if pname:
            table_names.add(pname)

    errors: List[dict] = []

    # Scan calculations (measures + calc columns)
    for calc in merged.get('calculations', []):
        formula = calc.get('dax_formula', calc.get('formula', ''))
        if not formula:
            continue
        calc_name = calc.get('caption', calc.get('name', ''))
        calc_type = calc.get('classification', 'measure')

        for match in _RE_DAX_TABLE_COL.finditer(formula):
            ref_table = match.group(1)
            ref_col = match.group(2)
            status = 'ok'
            suggestion = None

            if ref_table not in table_names:
                status = 'error_table'
                suggestion = _find_closest(ref_table, table_names)
            elif ref_col not in table_columns.get(ref_table, set()):
                status = 'error_column'
                suggestion = _find_closest(
                    ref_col, table_columns.get(ref_table, set())
                )

            if status != 'ok':
                errors.append({
                    'source': calc_name,
                    'source_type': calc_type,
                    'ref': f"'{ref_table}'[{ref_col}]",
                    'table': ref_table,
                    'column': ref_col,
                    'status': status,
                    'suggestion': suggestion,
                })

    return errors


def validate_dax_relationship_functions(merged: dict) -> List[dict]:
    """Verify RELATED() / LOOKUPVALUE() usage matches relationship cardinality.

    RELATED() requires a manyToOne relationship on the referenced path.
    LOOKUPVALUE() is used for manyToMany.

    Returns:
        List of {source, function, ref_table, ref_column, expected, actual, status}.
    """
    # Build relationship cardinality map: (from_table, to_table) -> cardinality
    cardinality_map: Dict[Tuple[str, str], str] = {}
    # Also build reverse map for RELATED lookups
    for ds in merged.get('datasources', []):
        for rel in ds.get('relationships', []):
            if 'left' in rel:
                ft = rel['left'].get('table', '')
                tt = rel['right'].get('table', '')
            else:
                ft = rel.get('from_table', '')
                tt = rel.get('to_table', '')
            card = rel.get('cardinality', 'manyToOne')
            if ft and tt:
                cardinality_map[(ft, tt)] = card
                cardinality_map[(tt, ft)] = card

    mismatches: List[dict] = []

    _RE_RELATED = re.compile(r"RELATED\s*\(\s*'([^']+)'\[([^\]]+)\]")
    _RE_LOOKUPVALUE = re.compile(
        r"LOOKUPVALUE\s*\(\s*'([^']+)'\[([^\]]+)\]"
    )

    for calc in merged.get('calculations', []):
        formula = calc.get('dax_formula', calc.get('formula', ''))
        if not formula:
            continue
        calc_name = calc.get('caption', calc.get('name', ''))

        # Check RELATED() calls — should be manyToOne
        for m in _RE_RELATED.finditer(formula):
            ref_table = m.group(1)
            ref_col = m.group(2)
            # Find if any relationship path exists to ref_table
            related_cards = [
                v for (k, v) in cardinality_map.items()
                if k[1] == ref_table
            ]
            if not related_cards:
                mismatches.append({
                    'source': calc_name,
                    'function': 'RELATED',
                    'ref_table': ref_table,
                    'ref_column': ref_col,
                    'expected': 'manyToOne',
                    'actual': 'no_relationship',
                    'status': 'error',
                })
            elif all(c == 'manyToMany' for c in related_cards):
                mismatches.append({
                    'source': calc_name,
                    'function': 'RELATED',
                    'ref_table': ref_table,
                    'ref_column': ref_col,
                    'expected': 'manyToOne',
                    'actual': 'manyToMany',
                    'status': 'warning',
                })

        # Check LOOKUPVALUE() calls — used when manyToMany
        for m in _RE_LOOKUPVALUE.finditer(formula):
            ref_table = m.group(1)
            ref_col = m.group(2)
            related_cards = [
                v for (k, v) in cardinality_map.items()
                if k[1] == ref_table
            ]
            if related_cards and all(c == 'manyToOne' for c in related_cards):
                mismatches.append({
                    'source': calc_name,
                    'function': 'LOOKUPVALUE',
                    'ref_table': ref_table,
                    'ref_column': ref_col,
                    'expected': 'manyToMany',
                    'actual': 'manyToOne',
                    'status': 'info',
                })

    return mismatches


def generate_merge_validation_report(merged: dict) -> dict:
    """Run all post-merge safety checks and produce a summary report.

    Returns:
        {
            'cycles': [...],
            'type_warnings': [...],
            'dax_errors': [...],
            'cardinality_mismatches': [...],
            'counts': {cycles, type_errors, type_warnings, dax_errors, cardinality},
            'score': int (0-100, higher is better),
            'passed': bool,
        }
    """
    cycles = detect_merge_cycles(merged)
    type_warnings = detect_type_conflicts(merged)
    dax_errors = validate_merged_dax_references(merged)
    cardinality = validate_dax_relationship_functions(merged)

    # Counts
    n_cycles = len(cycles)
    n_type_errors = sum(1 for w in type_warnings if w['level'] == 'error')
    n_type_warns = sum(1 for w in type_warnings if w['level'] == 'warn')
    n_dax_errors = len(dax_errors)
    n_card = sum(1 for c in cardinality if c['status'] in ('error', 'warning'))

    # Score: start at 100, deduct for issues
    score = 100
    score -= n_cycles * 25  # cycles are critical
    score -= n_type_errors * 15
    score -= n_type_warns * 5
    score -= n_dax_errors * 10
    score -= n_card * 5
    score = max(0, score)

    passed = n_cycles == 0 and n_type_errors == 0

    return {
        'cycles': cycles,
        'type_warnings': type_warnings,
        'dax_errors': dax_errors,
        'cardinality_mismatches': cardinality,
        'counts': {
            'cycles': n_cycles,
            'type_errors': n_type_errors,
            'type_warnings': n_type_warns,
            'dax_errors': n_dax_errors,
            'cardinality_mismatches': n_card,
        },
        'score': score,
        'passed': passed,
    }


def _find_closest(name: str, candidates: set) -> Optional[str]:
    """Find the closest match for *name* in *candidates* (Levenshtein-like)."""
    if not candidates:
        return None
    name_lower = name.lower()
    best = None
    best_score = 999
    for c in candidates:
        c_lower = c.lower()
        # Simple edit distance approximation: shared prefix + length diff
        common = 0
        for a, b in zip(name_lower, c_lower):
            if a == b:
                common += 1
            else:
                break
        dist = abs(len(name_lower) - len(c_lower)) + (max(len(name_lower), len(c_lower)) - common)
        if dist < best_score:
            best_score = dist
            best = c
    # Only suggest if reasonably close
    if best_score <= max(3, len(name) // 2):
        return best
    return None


def _detect_parameter_conflicts(
    all_extracted: List[dict], app_names: List[str]
) -> Tuple[List[dict], int]:
    """Detect parameter conflicts and count deduplicatable parameters."""
    param_map: Dict[str, Dict[str, dict]] = {}
    for wb_name, extracted in zip(app_names, all_extracted):
        for param in extracted.get('parameters', []):
            pname = param.get('name', param.get('caption', ''))
            if pname not in param_map:
                param_map[pname] = {}
            param_map[pname][wb_name] = param

    conflicts = []
    duplicates = 0

    for pname, wb_params in param_map.items():
        if len(wb_params) <= 1:
            continue
        # Compare domain_type and datatype
        signatures = set()
        for wb, p in wb_params.items():
            sig = (p.get('datatype', ''), p.get('domain_type', ''),
                   str(p.get('current_value', '')))
            signatures.add(sig)
        if len(signatures) == 1:
            duplicates += 1
        else:
            conflicts.append({
                "name": pname,
                "variants": {
                    wb: {
                        "datatype": p.get('datatype'),
                        "domain_type": p.get('domain_type'),
                        "current_value": p.get('current_value'),
                    }
                    for wb, p in wb_params.items()
                },
            })

    return conflicts, duplicates


# ═══════════════════════════════════════════════════════════════════
#  Table linkage classification
# ═══════════════════════════════════════════════════════════════════

def _classify_unique_tables(assessment: MergeAssessment,
                            all_extracted: List[dict],
                            app_names: List[str],
                            fp_map: Dict[str, list]):
    """Classify unique tables as linked (have relationships to other tables) or isolated.

    A unique table is "linked" if:
    - It participates in a relationship with another table in the merged model, OR
    - It shares column names with a shared (merge-candidate) table (suggesting a join key)

    A unique table is "isolated" if none of the above apply — meaning it has no
    connection to any other app's data and should NOT be included in the merged model.
    """
    # Build the set of all table names in the merged model (shared + unique)
    shared_table_names = set()
    for mc in assessment.merge_candidates:
        shared_table_names.add(_normalize_table_key(mc.table_name))

    # Collect all relationship endpoints from all apps
    all_rel_tables = set()  # normalized table names that appear in relationships
    rel_pairs = []  # (table_a, table_b) pairs
    for extracted in all_extracted:
        for ds in extracted.get('datasources', []):
            for rel in ds.get('relationships', []):
                if 'left' in rel:
                    t_a = _normalize_table_key(rel['left'].get('table', ''))
                    t_b = _normalize_table_key(rel['right'].get('table', ''))
                else:
                    t_a = _normalize_table_key(rel.get('from_table', ''))
                    t_b = _normalize_table_key(rel.get('to_table', ''))
                if t_a and t_b:
                    all_rel_tables.add(t_a)
                    all_rel_tables.add(t_b)
                    rel_pairs.append((t_a, t_b))

    # Collect column sets for shared tables (for column-name-based linkage detection)
    shared_columns = set()
    for mc in assessment.merge_candidates:
        for _wb_name, table, _conn in mc.sources:
            for col in table.get('columns', []):
                shared_columns.add(col.get('name', '').lower())

    # Classify each unique table
    linked: Dict[str, List[str]] = {}
    isolated: Dict[str, List[str]] = {}

    for wb_name, table_names in assessment.unique_tables.items():
        for tname in table_names:
            norm_key = _normalize_table_key(tname)
            is_linked = False

            # Check 1: Does this table participate in a relationship with another table?
            for t_a, t_b in rel_pairs:
                if t_a == norm_key and t_b != norm_key:
                    # The other table exists in the model (shared or from same app)
                    if t_b in shared_table_names:
                        is_linked = True
                        break
                elif t_b == norm_key and t_a != norm_key:
                    if t_a in shared_table_names:
                        is_linked = True
                        break

            # Check 2: Does this table share column names with any shared table?
            # (suggesting a potential join key like customer_id, order_id, etc.)
            if not is_linked:
                unique_cols = _get_table_columns(tname, wb_name, all_extracted, app_names)
                # Require at least one column name match AND the column looks like a key
                key_patterns = {'id', '_id', 'key', '_key', 'code', '_code', 'no', '_no', 'num'}
                for col in unique_cols:
                    col_lower = col.lower()
                    if col_lower in shared_columns:
                        # Check if it looks like a join key (word-boundary match)
                        if any(
                            col_lower == p
                            or col_lower.endswith(f'_{p}')
                            or col_lower.startswith(f'{p}_')
                            for p in key_patterns
                        ):
                            is_linked = True
                            break

            if is_linked:
                linked.setdefault(wb_name, []).append(tname)
            else:
                isolated.setdefault(wb_name, []).append(tname)

    assessment.linked_unique_tables = linked
    assessment.isolated_tables = isolated


def _normalize_table_key(name: str) -> str:
    """Normalize a table name for comparison."""
    # Strip schema prefix and brackets
    clean = name.strip().strip('[]')
    if '.' in clean:
        parts = clean.rsplit('.', 1)
        clean = parts[-1].strip('[]')
    return clean.lower()


def _get_table_columns(table_name: str, wb_name: str,
                       all_extracted: List[dict],
                       app_names: List[str]) -> List[str]:
    """Get column names for a specific table in a specific app."""
    idx = app_names.index(wb_name) if wb_name in app_names else -1
    if idx < 0:
        return []
    extracted = all_extracted[idx]
    norm_target = _normalize_table_key(table_name)
    for ds in extracted.get('datasources', []):
        for table in ds.get('tables', []):
            if _normalize_table_key(table.get('name', '')) == norm_target:
                return [c.get('name', '') for c in table.get('columns', [])]
    return []


# ═══════════════════════════════════════════════════════════════════
#  Merge score
# ═══════════════════════════════════════════════════════════════════

def calculate_merge_score(assessment: MergeAssessment) -> int:
    """Calculate a 0-100 merge score.

    Dimensions:
        - Table overlap ratio (0-40 points)
        - Column match quality (0-20 points)
        - Measure conflict ratio (0-20 points)
        - Connection homogeneity (0-20 points)
    """
    score = 0

    # 1. Table overlap (0-40)
    if assessment.total_tables > 0:
        tables_saved = assessment.total_tables - assessment.unique_table_count
        overlap_ratio = tables_saved / assessment.total_tables
        score += int(overlap_ratio * 40)

    # 2. Column match quality (0-20)
    if assessment.merge_candidates:
        avg_overlap = sum(
            mc.column_overlap for mc in assessment.merge_candidates
        ) / len(assessment.merge_candidates)
        score += int(avg_overlap * 20)

    # 3. Measure conflict ratio (0-20) — fewer conflicts = higher score
    total_measures = (
        assessment.measure_duplicates_removed + len(assessment.measure_conflicts)
    )
    if total_measures > 0:
        clean_ratio = assessment.measure_duplicates_removed / total_measures
        score += int(clean_ratio * 20)
    else:
        score += 20  # No measures = no conflicts

    # 4. Connection homogeneity (0-20)
    if assessment.merge_candidates:
        conn_types = set()
        for mc in assessment.merge_candidates:
            conn_types.add(mc.fingerprint.connection_type.lower())
        if len(conn_types) == 1:
            score += 20
        elif len(conn_types) == 2:
            score += 10
        else:
            score += 5

    return min(score, 100)


# ═══════════════════════════════════════════════════════════════════
#  Lineage extraction
# ═══════════════════════════════════════════════════════════════════

def extract_lineage(merged: dict) -> List[dict]:
    """Extract lineage metadata from a merged converted_objects dict.

    Returns a list of lineage records, each with:
        name, type, source_apps, merge_action
    """
    records: List[dict] = []

    # Tables
    for ds in merged.get('datasources', []):
        for table in ds.get('tables', []):
            records.append({
                'name': table.get('name', ''),
                'type': 'table',
                'source_apps': table.get('_source_apps', []),
                'merge_action': table.get('_merge_action', ''),
            })
        # Datasource-level calculations
        for calc in ds.get('calculations', []):
            records.append({
                'name': calc.get('caption', calc.get('name', '')),
                'type': 'ds_calculation',
                'source_apps': calc.get('_source_apps', []),
                'merge_action': calc.get('_merge_action', ''),
            })
        # Relationships
        for rel in ds.get('relationships', []):
            from_t = rel.get('from_table', '')
            to_t = rel.get('to_table', '')
            records.append({
                'name': f"{from_t} → {to_t}",
                'type': 'relationship',
                'source_apps': rel.get('_source_apps', []),
                'merge_action': rel.get('_merge_action', ''),
            })

    # Standalone calculations
    for calc in merged.get('calculations', []):
        records.append({
            'name': calc.get('caption', calc.get('name', '')),
            'type': 'calculation',
            'source_apps': calc.get('_source_apps', []),
            'merge_action': calc.get('_merge_action', ''),
        })

    # Parameters
    for param in merged.get('parameters', []):
        records.append({
            'name': param.get('name', param.get('caption', '')),
            'type': 'parameter',
            'source_apps': param.get('_source_apps', []),
            'merge_action': param.get('_merge_action', ''),
        })

    # Hierarchies
    for hier in merged.get('hierarchies', []):
        records.append({
            'name': hier.get('name', ''),
            'type': 'hierarchy',
            'source_apps': hier.get('_source_apps', []),
            'merge_action': hier.get('_merge_action', ''),
        })

    # Simple list-based artifacts
    for key in ('sets', 'groups', 'bins', 'user_filters', 'filters',
                'stories', 'actions', 'sort_orders', 'custom_sql'):
        for item in merged.get(key, []):
            records.append({
                'name': item.get('name', ''),
                'type': key.rstrip('s'),  # e.g., 'set', 'group'
                'source_apps': item.get('_source_apps', []),
                'merge_action': item.get('_merge_action', ''),
            })

    # Advanced artifacts
    for cg in merged.get('_calculation_groups', []):
        records.append({
            'name': cg.get('caption', ''),
            'type': 'calculation_group',
            'source_apps': cg.get('_source_apps', []),
            'merge_action': cg.get('_merge_action', ''),
        })

    for fp in merged.get('_field_parameters', []):
        records.append({
            'name': fp.get('caption', ''),
            'type': 'field_parameter',
            'source_apps': fp.get('_source_apps', []),
            'merge_action': fp.get('_merge_action', ''),
        })

    for persp in merged.get('_perspectives', []):
        records.append({
            'name': persp.get('name', ''),
            'type': 'perspective',
            'source_apps': persp.get('_source_apps', []),
            'merge_action': persp.get('_merge_action', ''),
        })

    for culture in merged.get('_cultures', []):
        records.append({
            'name': culture.get('locale', ''),
            'type': 'culture',
            'source_apps': culture.get('_source_apps', []),
            'merge_action': culture.get('_merge_action', ''),
        })

    for goal in merged.get('_goals', []):
        records.append({
            'name': goal.get('name', goal.get('metric_name', '')),
            'type': 'goal',
            'source_apps': goal.get('_source_apps', []),
            'merge_action': goal.get('_merge_action', ''),
        })

    return records


# ═══════════════════════════════════════════════════════════════════
#  Semantic model merging
# ═══════════════════════════════════════════════════════════════════

def merge_semantic_models(all_extracted: List[dict],
                          assessment: MergeAssessment,
                          model_name: str) -> dict:
    """Merge multiple app extractions into a single unified dataset.

    Returns:
        A single converted_objects dict with merged datasources, calculations,
        parameters, relationships, etc. suitable for tmdl_generator.generate_tmdl().
    """
    merged = {
        'datasources': [],
        'worksheets': [],
        'dashboards': [],
        'calculations': [],
        'parameters': [],
        'filters': [],
        'stories': [],
        'actions': [],
        'sets': [],
        'groups': [],
        'bins': [],
        'hierarchies': [],
        'sort_orders': [],
        'aliases': {},
        'custom_sql': [],
        'user_filters': [],
    }

    app_names = assessment.apps

    # 1. Merge datasources (table-level deduplication)
    merged_datasource = _merge_datasources(
        all_extracted, app_names, assessment
    )
    merged['datasources'] = [merged_datasource]

    # 2. Merge calculations with conflict resolution
    merged['calculations'] = _merge_calculations(
        all_extracted, app_names, assessment
    )

    # 3. Merge parameters
    merged['parameters'] = _merge_parameters(all_extracted, app_names)

    # 4. Merge remaining objects (union, deduplicated by name)
    for key in ('sets', 'groups', 'bins', 'sort_orders',
                'custom_sql', 'user_filters', 'filters', 'stories', 'actions'):
        merged[key] = _merge_list_by_name(all_extracted, key)

    # 4b. Merge hierarchies with level-aware deduplication
    merged['hierarchies'] = _merge_hierarchies(all_extracted, app_names)

    # 4c. Merge calculation groups
    merged['_calculation_groups'] = _merge_calculation_groups(
        all_extracted, app_names
    )

    # 4d. Merge field parameters
    merged['_field_parameters'] = _merge_field_parameters(
        all_extracted, app_names
    )

    # 4e. Merge perspectives
    merged['_perspectives'] = _merge_perspectives(all_extracted, app_names)

    # 4f. Merge cultures
    merged['_cultures'] = _merge_cultures(all_extracted, app_names)

    # 4g. Merge goals / pulse metrics
    merged['_goals'] = _merge_goals(all_extracted, app_names)

    # 5. Merge aliases
    for extracted in all_extracted:
        aliases = extracted.get('aliases', {})
        if isinstance(aliases, dict):
            merged['aliases'].update(aliases)

    # 6. Collect all worksheets and dashboards (kept per-app for thin reports)
    for extracted in all_extracted:
        merged['worksheets'].extend(extracted.get('worksheets', []))
        merged['dashboards'].extend(extracted.get('dashboards', []))

    return merged


def _merge_datasources(all_extracted: List[dict],
                       app_names: List[str],
                       assessment: MergeAssessment) -> dict:
    """Merge all datasources into a single unified datasource.

    Tables are deduplicated by fingerprint. Columns are unioned.
    Relationships are deduplicated.
    """
    merged_ds = {
        'name': 'SharedModel',
        'caption': 'Shared Semantic Model',
        'connection': {},
        'connection_map': {},
        'tables': [],
        'columns': [],
        'calculations': [],
        'relationships': [],
    }

    # Track which tables have been added (by fingerprint hash)
    added_tables: Dict[str, dict] = {}  # fp_hash → merged_table

    # Track relationships for deduplication
    rel_keys_seen = set()

    # Track datasource-level calculations for deduplication
    _ds_calc_seen = set()  # (caption, formula)

    # Build set of isolated table names (normalized) to skip
    _isolated_set = set()
    for _wb, tnames in assessment.isolated_tables.items():
        for t in tnames:
            _isolated_set.add(_normalize_table_key(t))

    for wb_name, extracted in zip(app_names, all_extracted):
        for ds in extracted.get('datasources', []):
            # Adopt connection info from first datasource
            if not merged_ds['connection']:
                merged_ds['connection'] = copy.deepcopy(ds.get('connection', {}))

            # Merge connection_map entries
            for k, v in ds.get('connection_map', {}).items():
                if k not in merged_ds['connection_map']:
                    merged_ds['connection_map'][k] = copy.deepcopy(v)

            # Process tables — skip isolated tables
            fps = build_table_fingerprints([ds])
            for raw_name, (fp, table, _conn) in fps.items():
                # Skip tables classified as isolated (no links to merged model)
                if _normalize_table_key(raw_name) in _isolated_set:
                    continue

                fp_hash = fp.fingerprint()
                if fp_hash in added_tables:
                    # Merge columns into existing table
                    _merge_columns_into(added_tables[fp_hash], table)
                    # Lineage: track additional source app
                    added_tables[fp_hash].setdefault('_source_apps', []).append(wb_name)
                    added_tables[fp_hash]['_merge_action'] = 'deduplicated'
                else:
                    # Add new table
                    merged_table = copy.deepcopy(table)
                    merged_table['_source_apps'] = [wb_name]
                    merged_table['_merge_action'] = 'unique'
                    added_tables[fp_hash] = merged_table
                    merged_ds['tables'].append(merged_table)

            # Merge relationships (deduplicate)
            for rel in ds.get('relationships', []):
                key = _relationship_key(rel)
                if key not in rel_keys_seen:
                    rel_keys_seen.add(key)
                    rel_copy = copy.deepcopy(rel)
                    rel_copy['_source_apps'] = [wb_name]
                    rel_copy['_merge_action'] = 'unique'
                    merged_ds['relationships'].append(rel_copy)
                else:
                    # Find existing and update lineage
                    for existing_rel in merged_ds['relationships']:
                        if _relationship_key(existing_rel) == key:
                            existing_rel.setdefault('_source_apps', []).append(wb_name)
                            existing_rel['_merge_action'] = 'deduplicated'
                            break

            # Merge datasource-level calculations (dedup + namespace conflicts)
            conflict_names = {mc.name for mc in assessment.measure_conflicts}
            for calc in ds.get('calculations', []):
                caption = calc.get('caption', calc.get('name', ''))
                formula = calc.get('formula', '').strip()
                role = calc.get('role', 'measure')

                if caption in conflict_names and role == 'measure':
                    # Namespace conflicting measure
                    namespaced = copy.deepcopy(calc)
                    new_caption = f"{caption} ({wb_name})"
                    namespaced['caption'] = new_caption
                    namespaced['_original_caption'] = caption
                    namespaced['_source_app'] = wb_name
                    namespaced['_source_apps'] = [wb_name]
                    namespaced['_merge_action'] = 'namespaced'
                    merged_ds['calculations'].append(namespaced)
                else:
                    # Deduplicate by (caption, formula)
                    dup_key = (caption, formula)
                    if dup_key not in _ds_calc_seen:
                        _ds_calc_seen.add(dup_key)
                        calc_copy = copy.deepcopy(calc)
                        calc_copy['_source_apps'] = [wb_name]
                        calc_copy['_merge_action'] = 'unique'
                        merged_ds['calculations'].append(calc_copy)
                    else:
                        # Track additional source on existing
                        for existing_calc in merged_ds['calculations']:
                            ec = existing_calc.get('caption', existing_calc.get('name', ''))
                            if ec == caption:
                                existing_calc.setdefault('_source_apps', []).append(wb_name)
                                existing_calc['_merge_action'] = 'deduplicated'
                                break

    return merged_ds


def _merge_columns_into(existing_table: dict, new_table: dict):
    """Merge columns from new_table into existing_table (union).

    Existing columns are kept. New columns not in existing are added.
    Type conflicts: wider type wins (string > real > integer).
    Tracks type history in ``_column_type_history`` for post-merge validation.
    """
    existing_cols = {c.get('name', '').lower(): c
                     for c in existing_table.get('columns', [])}

    # Ensure type history dict exists
    type_history = existing_table.setdefault('_column_type_history', {})

    # Seed type history from existing columns (first app)
    for col in existing_table.get('columns', []):
        cn = col.get('name', '').lower()
        if cn not in type_history:
            type_history[cn] = [col.get('datatype', 'string')]

    for col in new_table.get('columns', []):
        col_name = col.get('name', '').lower()
        new_type = col.get('datatype', 'string')
        if col_name in existing_cols:
            # Track type history for validation
            type_history.setdefault(col_name, []).append(new_type)
            # Resolve type conflicts — wider type wins
            existing_type = existing_cols[col_name].get('datatype', 'string')
            if _type_width(new_type) > _type_width(existing_type):
                existing_cols[col_name]['datatype'] = new_type
            # Merge metadata: unhide if unhidden in any app
            if not col.get('hidden', False):
                existing_cols[col_name]['hidden'] = False
            # Take first non-empty semantic_role
            if col.get('semantic_role') and not existing_cols[col_name].get('semantic_role'):
                existing_cols[col_name]['semantic_role'] = col['semantic_role']
            # Take first non-empty format
            if col.get('default_format') and not existing_cols[col_name].get('default_format'):
                existing_cols[col_name]['default_format'] = col['default_format']
        else:
            existing_table.setdefault('columns', []).append(copy.deepcopy(col))
            existing_cols[col_name] = existing_table['columns'][-1]


_TYPE_WIDTH = {
    'boolean': 1,
    'integer': 2,
    'real': 3,
    'currency': 3,
    'datetime': 4,
    'string': 5,
}


def _type_width(dtype: str) -> int:
    """Return a width score for type conflict resolution."""
    return _TYPE_WIDTH.get(dtype.lower(), 5)


def _merge_calculations(all_extracted: List[dict],
                         app_names: List[str],
                         assessment: MergeAssessment) -> list:
    """Merge calculations with conflict resolution.

    Same name + same formula → keep one.
    Same name + different formula → namespace with app suffix.
    """
    # Build conflict set for fast lookup
    conflict_names = {mc.name for mc in assessment.measure_conflicts}

    # Collect all calculations
    seen: Dict[str, Tuple[str, dict]] = {}  # caption → (formula, calc_dict)
    result = []

    for wb_name, extracted in zip(app_names, all_extracted):
        for calc in extracted.get('calculations', []):
            caption = calc.get('caption', calc.get('name', ''))
            formula = calc.get('formula', '').strip()

            if caption in conflict_names:
                # Namespace it
                namespaced = copy.deepcopy(calc)
                new_caption = f"{caption} ({wb_name})"
                namespaced['caption'] = new_caption
                namespaced['_original_caption'] = caption
                namespaced['_source_app'] = wb_name
                namespaced['_source_apps'] = [wb_name]
                namespaced['_merge_action'] = 'namespaced'
                result.append(namespaced)
            elif caption in seen:
                # Already seen — track source for lineage
                for existing in result:
                    if existing.get('caption', existing.get('name', '')) == caption:
                        existing.setdefault('_source_apps', []).append(wb_name)
                        existing['_merge_action'] = 'deduplicated'
                        break
            else:
                seen[caption] = (formula, calc)
                calc_copy = copy.deepcopy(calc)
                calc_copy['_source_apps'] = [wb_name]
                calc_copy['_merge_action'] = 'unique'
                result.append(calc_copy)

    return result


def _merge_parameters(all_extracted: List[dict],
                      app_names: List[str]) -> list:
    """Merge parameters. Same name+type+default → deduplicate. Conflicts → namespace."""
    param_map: Dict[str, List[Tuple[str, dict]]] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        for param in extracted.get('parameters', []):
            pname = param.get('name', param.get('caption', ''))
            if pname not in param_map:
                param_map[pname] = []
            param_map[pname].append((wb_name, param))

    result = []
    for pname, entries in param_map.items():
        if len(entries) == 1:
            p_copy = copy.deepcopy(entries[0][1])
            p_copy['_source_apps'] = [entries[0][0]]
            p_copy['_merge_action'] = 'unique'
            result.append(p_copy)
        else:
            # Check if all identical
            sigs = set()
            for wb, p in entries:
                sig = (p.get('datatype', ''), p.get('domain_type', ''),
                       str(p.get('current_value', '')))
                sigs.add(sig)
            if len(sigs) == 1:
                p_copy = copy.deepcopy(entries[0][1])
                p_copy['_source_apps'] = [wb for wb, _ in entries]
                p_copy['_merge_action'] = 'deduplicated'
                result.append(p_copy)
            else:
                # Namespace each
                for wb, p in entries:
                    namespaced = copy.deepcopy(p)
                    namespaced['name'] = f"{pname} ({wb})"
                    namespaced['caption'] = f"{pname} ({wb})"
                    namespaced['_source_app'] = wb
                    namespaced['_source_apps'] = [wb]
                    namespaced['_merge_action'] = 'namespaced'
                    result.append(namespaced)

    return result


def _merge_list_by_name(all_extracted: List[dict], key: str) -> list:
    """Merge a list-type object by deduplicating on 'name' field."""
    seen_names: Dict[str, dict] = {}  # name → item (for lineage tracking)
    result = []
    for idx, extracted in enumerate(all_extracted):
        items = extracted.get(key, [])
        if not isinstance(items, list):
            continue
        for item in items:
            name = item.get('name', '')
            if name and name in seen_names:
                # Track additional source
                seen_names[name].setdefault('_source_apps', []).append(f'wb_{idx}')
                seen_names[name]['_merge_action'] = 'deduplicated'
                continue
            item_copy = copy.deepcopy(item)
            item_copy['_source_apps'] = [f'wb_{idx}']
            item_copy['_merge_action'] = 'unique'
            if name:
                seen_names[name] = item_copy
            result.append(item_copy)
    return result


# ═══════════════════════════════════════════════════════════════════
#  Sprint 54 — Artifact-level merge functions
# ═══════════════════════════════════════════════════════════════════

def _merge_hierarchies(all_extracted: List[dict],
                       app_names: List[str]) -> list:
    """Merge hierarchies with level-aware deduplication.

    Same name + same levels → deduplicate.
    Same name + different levels → keep the one with more levels.
    Different names → keep all.
    Cross-app hierarchies on the same table are unioned.
    """
    # hierarchy name → (levels_tuple, hierarchy_dict, source_wb)
    seen: Dict[str, Tuple[tuple, dict, str]] = {}
    result = []

    for wb_name, extracted in zip(app_names, all_extracted):
        items = extracted.get('hierarchies', [])
        if not isinstance(items, list):
            continue
        for item in items:
            name = item.get('name', '')
            if not name:
                result.append(copy.deepcopy(item))
                continue

            levels = item.get('levels', [])
            levels_key = tuple(
                lv.get('name', lv.get('column', '')) for lv in levels
            )

            if name in seen:
                existing_levels_key, _existing_item, _existing_wb = seen[name]
                if levels_key == existing_levels_key:
                    # Identical → skip duplicate, track source
                    for r in result:
                        if r.get('name', '') == name:
                            r.setdefault('_source_apps', []).append(wb_name)
                            r['_merge_action'] = 'deduplicated'
                            break
                    continue
                if len(levels_key) > len(existing_levels_key):
                    # New one has more levels → replace
                    for i, r in enumerate(result):
                        if r.get('name', '') == name:
                            replacement = copy.deepcopy(item)
                            replacement['_source_apps'] = [
                                _existing_wb, wb_name]
                            replacement['_merge_action'] = 'deduplicated'
                            result[i] = replacement
                            break
                    seen[name] = (levels_key, item, wb_name)
                    logger.debug(
                        "Hierarchy '%s': replaced (%d levels from %s) with (%d levels from %s)",
                        name, len(existing_levels_key), _existing_wb,
                        len(levels_key), wb_name
                    )
                # else: existing has more or equal levels → keep existing
            else:
                seen[name] = (levels_key, item, wb_name)
                item_copy = copy.deepcopy(item)
                item_copy['_source_apps'] = [wb_name]
                item_copy['_merge_action'] = 'unique'
                result.append(item_copy)

    return result


def _calc_group_signature(cg: dict) -> Tuple[str, ...]:
    """Build a signature tuple for a calculation group's items."""
    items = cg.get('calculationItems', cg.get('calculation_items', []))
    return tuple(sorted(
        (it.get('name', ''), it.get('expression', ''))
        for it in items
    ))


def _merge_calculation_groups(all_extracted: List[dict],
                              app_names: List[str]) -> list:
    """Merge calculation groups across apps.

    Same name + same calculation items → deduplicate.
    Same name + different items → namespace as 'CalcGroup (app)'.
    Different names → keep all.

    Calculation groups are stored in parameters with domain_type='list'
    where values match measure names. This function collects them from
    extracted parameters and deduplicates.
    """
    # Collect calc-group-like parameters: name → [(wb, param_dict)]
    cg_map: Dict[str, List[Tuple[str, dict]]] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        for param in extracted.get('parameters', []):
            caption = param.get('caption', param.get('name', ''))
            domain_type = param.get('domain_type', '')
            datatype = param.get('datatype', 'string')
            allowable_values = param.get('allowable_values', [])

            if datatype != 'string' or domain_type != 'list' or not allowable_values:
                continue

            # Mark this as calc-group candidate — store with values
            values = [v.get('value', '') for v in allowable_values
                      if v.get('type') != 'range']
            if len(values) < 2:
                continue

            cg_entry = {
                'caption': caption,
                'calculationItems': [
                    {'name': v, 'expression': 'CALCULATE(SELECTEDMEASURE())'}
                    for v in values
                ],
                'values': values,
                '_source_app': wb_name,
            }

            if caption not in cg_map:
                cg_map[caption] = []
            cg_map[caption].append((wb_name, cg_entry))

    result = []
    for name, entries in cg_map.items():
        if len(entries) == 1:
            entry = entries[0][1]
            entry['_source_apps'] = [entries[0][0]]
            entry['_merge_action'] = 'unique'
            result.append(entry)
            continue

        # Compare signatures
        sigs = {}
        for wb, cg in entries:
            sig = _calc_group_signature(cg)
            sigs[wb] = sig

        unique_sigs = set(sigs.values())
        if len(unique_sigs) == 1:
            # All identical → deduplicate
            entry = entries[0][1]
            entry['_source_apps'] = [wb for wb, _ in entries]
            entry['_merge_action'] = 'deduplicated'
            result.append(entry)
        else:
            # Conflict → namespace each
            for wb, cg in entries:
                namespaced = copy.deepcopy(cg)
                namespaced['caption'] = f"{name} ({wb})"
                namespaced['_source_app'] = wb
                namespaced['_source_apps'] = [wb]
                namespaced['_merge_action'] = 'namespaced'
                result.append(namespaced)
                logger.info(
                    "Calculation group '%s' namespaced → '%s' (conflict)",
                    name, namespaced['caption']
                )

    return result


def _merge_field_parameters(all_extracted: List[dict],
                            app_names: List[str]) -> list:
    """Merge field parameters across apps.

    Same name + same column references → deduplicate.
    Same name + different columns → union column references.
    Different names → keep all.
    """
    fp_map: Dict[str, List[Tuple[str, dict]]] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        for param in extracted.get('parameters', []):
            caption = param.get('caption', param.get('name', ''))
            domain_type = param.get('domain_type', '')
            datatype = param.get('datatype', 'string')
            allowable_values = param.get('allowable_values', [])

            if datatype != 'string' or domain_type != 'list' or not allowable_values:
                continue

            values = [v.get('value', '') for v in allowable_values
                      if v.get('type') != 'range']
            if len(values) < 2:
                continue

            fp_entry = {
                'caption': caption,
                'values': values,
                '_source_app': wb_name,
            }

            if caption not in fp_map:
                fp_map[caption] = []
            fp_map[caption].append((wb_name, fp_entry))

    result = []
    for name, entries in fp_map.items():
        if len(entries) == 1:
            entry = entries[0][1]
            entry['_source_apps'] = [entries[0][0]]
            entry['_merge_action'] = 'unique'
            result.append(entry)
            continue

        # Compare value sets
        all_value_sets = [set(fp['values']) for _wb, fp in entries]
        if all(vs == all_value_sets[0] for vs in all_value_sets):
            # All identical → deduplicate
            entry = entries[0][1]
            entry['_source_apps'] = [wb for wb, _ in entries]
            entry['_merge_action'] = 'deduplicated'
            result.append(entry)
        else:
            # Union all values (deduplicated, order-preserved)
            seen_vals = set()
            unioned_values = []
            for _wb, fp in entries:
                for v in fp['values']:
                    if v not in seen_vals:
                        seen_vals.add(v)
                        unioned_values.append(v)
            merged_fp = copy.deepcopy(entries[0][1])
            merged_fp['values'] = unioned_values
            merged_fp['_merged_from'] = [wb for wb, _ in entries]
            merged_fp['_source_apps'] = [wb for wb, _ in entries]
            merged_fp['_merge_action'] = 'unioned'
            result.append(merged_fp)
            logger.info(
                "Field parameter '%s': unioned %d values from %d apps",
                name, len(unioned_values), len(entries)
            )

    return result


def _merge_perspectives(all_extracted: List[dict],
                        app_names: List[str]) -> list:
    """Merge perspectives across apps.

    Same name → union table references.
    Different names → keep all.
    """
    persp_map: Dict[str, List[Tuple[str, set]]] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        perspectives = extracted.get('_perspectives', [])
        if not perspectives:
            continue
        for persp in perspectives:
            name = persp.get('name', '')
            tables = set(persp.get('tables', []))
            if name not in persp_map:
                persp_map[name] = []
            persp_map[name].append((wb_name, tables))

    result = []
    for name, entries in persp_map.items():
        # Union all table references
        all_tables = set()
        for _wb, tables in entries:
            all_tables.update(tables)
        result.append({
            'name': name,
            'tables': sorted(all_tables),
            '_source_apps': [wb for wb, _ in entries],
            '_merge_action': 'deduplicated' if len(entries) > 1 else 'unique',
        })

    return result


def _merge_cultures(all_extracted: List[dict],
                    app_names: List[str]) -> list:
    """Merge culture/locale settings across apps.

    Same locale → merge translation entries (first-seen wins per key).
    Different locales → keep all.
    """
    culture_map: Dict[str, Dict[str, str]] = {}  # locale → {object_name: translation}
    culture_sources: Dict[str, List[str]] = {}  # locale → [app_names]

    for wb_name, extracted in zip(app_names, all_extracted):
        culture = extracted.get('culture', '')
        languages = extracted.get('_languages', '')
        cultures_data = extracted.get('_cultures', [])

        # Collect cultures from explicit data
        for c in cultures_data:
            locale = c.get('locale', '')
            translations = c.get('translations', {})
            if locale:
                if locale not in culture_map:
                    culture_map[locale] = {}
                culture_sources.setdefault(locale, []).append(wb_name)
                for key, val in translations.items():
                    if key not in culture_map[locale]:
                        culture_map[locale][key] = val

        # Collect from culture field
        if culture and culture != 'en-US':
            if culture not in culture_map:
                culture_map[culture] = {}
            culture_sources.setdefault(culture, []).append(wb_name)

        # Collect from languages field
        if languages:
            for lang in languages.split(','):
                lang = lang.strip()
                if lang:
                    if lang not in culture_map:
                        culture_map[lang] = {}
                    culture_sources.setdefault(lang, []).append(wb_name)

    result = []
    for locale, translations in culture_map.items():
        result.append({
            'locale': locale,
            'translations': translations,
            '_source_apps': culture_sources.get(locale, []),
            '_merge_action': 'deduplicated' if len(culture_sources.get(locale, [])) > 1 else 'unique',
        })

    return result


def _merge_goals(all_extracted: List[dict],
                 app_names: List[str]) -> list:
    """Merge goals/scorecard metrics across apps.

    Same metric name + same measure → deduplicate.
    Same metric name + different measure → namespace.
    Different names → keep all.
    """
    goal_map: Dict[str, List[Tuple[str, dict]]] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        goals = extracted.get('_goals', [])
        if not goals:
            continue
        for goal in goals:
            name = goal.get('name', goal.get('metric_name', ''))
            if not name:
                continue
            if name not in goal_map:
                goal_map[name] = []
            goal_map[name].append((wb_name, goal))

    result = []
    for name, entries in goal_map.items():
        if len(entries) == 1:
            g_copy = copy.deepcopy(entries[0][1])
            g_copy['_source_apps'] = [entries[0][0]]
            g_copy['_merge_action'] = 'unique'
            result.append(g_copy)
            continue

        # Compare measure references
        measures = {}
        for wb, goal in entries:
            measure = goal.get('measure', goal.get('measure_name', ''))
            measures[wb] = measure

        unique_measures = set(measures.values())
        if len(unique_measures) == 1:
            # Identical → deduplicate
            g_copy = copy.deepcopy(entries[0][1])
            g_copy['_source_apps'] = [wb for wb, _ in entries]
            g_copy['_merge_action'] = 'deduplicated'
            result.append(g_copy)
        else:
            # Conflict → namespace
            for wb, goal in entries:
                namespaced = copy.deepcopy(goal)
                namespaced['name'] = f"{name} ({wb})"
                namespaced['_source_app'] = wb
                namespaced['_source_apps'] = [wb]
                namespaced['_merge_action'] = 'namespaced'
                result.append(namespaced)
                logger.info(
                    "Goal '%s' namespaced → '%s' (different measures)",
                    name, namespaced['name']
                )

    return result


# ═══════════════════════════════════════════════════════════════════
#  Field remapping — for thin reports referencing namespaced measures
# ═══════════════════════════════════════════════════════════════════

def build_field_mapping(assessment: MergeAssessment,
                        app_name: str) -> Dict[str, str]:
    """Build a field name mapping for a specific app's thin report.

    Maps original measure names to their namespaced versions (if conflicts exist).

    Args:
        assessment: The merge assessment.
        app_name: Which app's report we're generating.

    Returns:
        {original_name: namespaced_name} — only for conflicting measures.
    """
    mapping = {}
    for conflict in assessment.measure_conflicts:
        if app_name in conflict.variants:
            mapping[conflict.name] = f"{conflict.name} ({app_name})"
    return mapping


# ═══════════════════════════════════════════════════════════════════
#  Visual field validation
# ═══════════════════════════════════════════════════════════════════

def validate_thin_report_fields(converted_objects: dict,
                                 merged: dict,
                                 field_mapping: dict = None) -> List[dict]:
    """Validate that all fields referenced by a thin report exist in the merged model.

    Checks worksheet columns, filters, mark encoding fields against the merged
    model's tables, columns, and measures.

    Args:
        converted_objects: The app's original extracted objects.
        merged: The merged converted_objects dict.
        field_mapping: Active field mapping (original → namespaced).

    Returns:
        List of validation issues: [{"field": str, "location": str, "issue": str}]
    """
    # Build set of available fields from merged model
    available = set()
    for ds in merged.get('datasources', []):
        for table in ds.get('tables', []):
            for col in table.get('columns', []):
                available.add(col.get('name', '').lower())
        for calc in ds.get('calculations', []):
            available.add(calc.get('caption', calc.get('name', '')).lower())

    for calc in merged.get('calculations', []):
        available.add(calc.get('caption', calc.get('name', '')).lower())

    for param in merged.get('parameters', []):
        available.add(param.get('name', param.get('caption', '')).lower())

    mapping = field_mapping or {}
    issues = []

    for ws in converted_objects.get('worksheets', []):
        ws_name = ws.get('name', 'unknown')

        # Check columns
        for col in ws.get('columns', []):
            field_name = col.get('name', '')
            mapped = mapping.get(field_name, field_name)
            if mapped.lower() not in available and field_name.lower() not in available:
                issues.append({
                    "field": field_name,
                    "location": f"worksheet '{ws_name}' columns",
                    "issue": "orphaned_field",
                })

        # Check filters
        for f in ws.get('filters', []):
            field_name = f.get('field', '')
            mapped = mapping.get(field_name, field_name)
            if field_name and mapped.lower() not in available and field_name.lower() not in available:
                issues.append({
                    "field": field_name,
                    "location": f"worksheet '{ws_name}' filters",
                    "issue": "orphaned_filter",
                })

        # Check mark encoding
        for channel, enc in ws.get('mark_encoding', {}).items():
            if isinstance(enc, dict):
                field_name = enc.get('field', '')
                mapped = mapping.get(field_name, field_name)
                if field_name and mapped.lower() not in available and field_name.lower() not in available:
                    issues.append({
                        "field": field_name,
                        "location": f"worksheet '{ws_name}' mark_encoding.{channel}",
                        "issue": "orphaned_encoding",
                    })

    return issues


# ═══════════════════════════════════════════════════════════════════
#  Column lineage tracking
# ═══════════════════════════════════════════════════════════════════

def build_column_lineage(all_extracted: List[dict],
                         app_names: List[str],
                         assessment: MergeAssessment) -> Dict[str, Dict[str, list]]:
    """Build lineage metadata showing which apps contributed each table/column.

    Returns:
        {table_name: {"source_apps": [str], "columns": {col_name: [source_wbs]}}}
    """
    lineage: Dict[str, Dict] = {}

    for mc in assessment.merge_candidates:
        table_name = mc.table_name
        source_wbs = [s[0] for s in mc.sources]
        col_sources: Dict[str, list] = {}

        for wb_name, table, _ in mc.sources:
            for col in table.get('columns', []):
                cname = col.get('name', '')
                if cname not in col_sources:
                    col_sources[cname] = []
                if wb_name not in col_sources[cname]:
                    col_sources[cname].append(wb_name)

        lineage[table_name] = {
            "source_apps": source_wbs,
            "columns": col_sources,
        }

    # Also capture unique tables
    for wb, tables in assessment.unique_tables.items():
        for tname in tables:
            lineage[tname] = {
                "source_apps": [wb],
                "columns": {},
            }
            # Find the table's columns
            for extracted in all_extracted:
                for ds in extracted.get('datasources', []):
                    for t in ds.get('tables', []):
                        if t.get('name', '') == tname:
                            for col in t.get('columns', []):
                                lineage[tname]["columns"][col.get('name', '')] = [wb]

    return lineage


def generate_lineage_annotations(lineage: Dict[str, Dict[str, list]]) -> Dict[str, str]:
    """Generate TMDL annotation strings for column lineage.

    Returns:
        {table_name: annotation_text} — ready to embed in TMDL table files.
    """
    annotations = {}
    for table_name, info in lineage.items():
        sources = info.get("source_apps", [])
        lines = [f"Source apps: {', '.join(sources)}"]
        col_info = info.get("columns", {})
        multi_source = [c for c, wbs in col_info.items() if len(wbs) > 1]
        single_source = [c for c, wbs in col_info.items() if len(wbs) == 1]
        if multi_source:
            lines.append(f"Shared columns ({len(multi_source)}): {', '.join(sorted(multi_source)[:10])}")
        if single_source:
            lines.append(f"Unique columns ({len(single_source)}): {', '.join(sorted(single_source)[:10])}")
        annotations[table_name] = " | ".join(lines)
    return annotations


# ═══════════════════════════════════════════════════════════════════
#  Measure expression risk analyzer
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MeasureRiskAssessment:
    """Risk analysis for a measure conflict."""
    measure_name: str
    risk_level: str   # "low", "medium", "high"
    reason: str
    variants: Dict[str, str]  # {wb_name: formula}
    aggregation_types: Dict[str, str]  # {wb_name: detected_agg}


# ═══════════════════════════════════════════════════════════════════
#  Sprint 51 — Merge extensions
# ═══════════════════════════════════════════════════════════════════

def _normalize_sql(sql: str) -> str:
    """Normalize SQL text for comparison (case-fold, collapse whitespace)."""
    if not sql:
        return ''
    normalized = re.sub(r'\s+', ' ', sql.strip().lower())
    # Remove trailing semicolons
    return normalized.rstrip(';').strip()


def _hash_sql(sql: str) -> str:
    """Hash normalized SQL text for fingerprint comparison."""
    return hashlib.sha256(_normalize_sql(sql).encode('utf-8')).hexdigest()[:16]


def build_custom_sql_fingerprints(
    datasources: list,
) -> Dict[str, Tuple[str, dict, dict]]:
    """Build fingerprints for custom SQL tables based on query text hash.

    Returns:
        {sql_hash: (sql_text, table_dict, connection_dict)}
    """
    result = {}
    for ds in datasources:
        conn = ds.get('connection', {})
        for table in ds.get('tables', []):
            sql = table.get('custom_sql', table.get('query', ''))
            if not sql:
                continue
            sql_hash = _hash_sql(sql)
            if sql_hash not in result:
                result[sql_hash] = (sql, table, conn)
    return result


def _normalize_table_name_fuzzy(name: str) -> str:
    """Normalize a table name for fuzzy matching.

    Strips schema prefix, removes brackets, folds case, removes
    common separators (underscore, hyphen, space).
    """
    # Strip schema prefix
    clean = name.strip().strip('[]')
    if '.' in clean:
        parts = clean.rsplit('.', 1)
        clean = parts[-1].strip('[]')
    # Case fold and remove separators
    clean = clean.lower().replace('_', '').replace('-', '').replace(' ', '')
    return clean


def fuzzy_table_match(name_a: str, name_b: str) -> float:
    """Compute fuzzy similarity between two table names.

    Uses normalized string comparison: exact match = 1.0, prefix/suffix
    overlap as secondary signal.

    Returns:
        Float 0.0–1.0 representing name similarity.
    """
    norm_a = _normalize_table_name_fuzzy(name_a)
    norm_b = _normalize_table_name_fuzzy(name_b)

    if not norm_a or not norm_b:
        return 0.0

    if norm_a == norm_b:
        return 1.0

    # Check containment
    if norm_a in norm_b or norm_b in norm_a:
        shorter = min(len(norm_a), len(norm_b))
        longer = max(len(norm_a), len(norm_b))
        return shorter / longer

    # Character-level Jaccard on bigrams
    def _bigrams(s):
        return set(s[i:i+2] for i in range(len(s) - 1)) if len(s) > 1 else {s}

    bg_a = _bigrams(norm_a)
    bg_b = _bigrams(norm_b)
    if not bg_a or not bg_b:
        return 0.0
    return len(bg_a & bg_b) / len(bg_a | bg_b)


def detect_rls_conflicts(
    all_extracted: List[dict],
    app_names: List[str],
) -> List[dict]:
    """Detect overlapping RLS roles across apps.

    When merging models, detects roles that target the same table but
    have different filter expressions.

    Returns:
        List of conflict dicts: [{table, role_name, variants: {wb: expression}}]
    """
    # role_key (table, role_name) → {wb: expression}
    role_map: Dict[Tuple[str, str], Dict[str, str]] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        for uf in extracted.get('user_filters', []):
            table = uf.get('table', uf.get('datasource', 'default')).lower()
            role_name = uf.get('name', uf.get('field', 'unknown'))
            expression = uf.get('formula', uf.get('values', ''))
            if isinstance(expression, list):
                expression = str(sorted(expression))
            key = (table, role_name)
            if key not in role_map:
                role_map[key] = {}
            role_map[key][wb_name] = str(expression)

    conflicts = []
    for (table, role_name), variants in role_map.items():
        if len(variants) <= 1:
            continue
        unique_expressions = set(variants.values())
        if len(unique_expressions) > 1:
            conflicts.append({
                'table': table,
                'role_name': role_name,
                'variants': variants,
            })

    return conflicts


def suggest_cross_app_relationships(
    merged: dict,
) -> List[dict]:
    """Suggest potential relationships between tables in a merged model.

    Scans all table column names for matching patterns (e.g., customer_id
    in different tables) and suggests relationships.

    Returns:
        List of suggestion dicts: [{from_table, from_column, to_table, to_column, confidence}]
    """
    tables = []
    for ds in merged.get('datasources', []):
        for table in ds.get('tables', []):
            tname = table.get('name', '')
            cols = {c.get('name', '').lower(): c for c in table.get('columns', [])}
            tables.append((tname, cols))

    # Build existing relationship set
    existing_rels = set()
    for ds in merged.get('datasources', []):
        for rel in ds.get('relationships', []):
            if 'left' in rel:
                existing_rels.add((
                    rel['left'].get('table', '').lower(),
                    rel['right'].get('table', '').lower(),
                ))
                existing_rels.add((
                    rel['right'].get('table', '').lower(),
                    rel['left'].get('table', '').lower(),
                ))
            else:
                existing_rels.add((
                    rel.get('from_table', '').lower(),
                    rel.get('to_table', '').lower(),
                ))
                existing_rels.add((
                    rel.get('to_table', '').lower(),
                    rel.get('from_table', '').lower(),
                ))

    suggestions = []
    key_suffixes = ('_id', '_key', '_code', 'id', 'key', 'code')

    for i, (t1_name, t1_cols) in enumerate(tables):
        for j, (t2_name, t2_cols) in enumerate(tables):
            if i >= j:
                continue
            if (t1_name.lower(), t2_name.lower()) in existing_rels:
                continue

            for col_name in t1_cols:
                if not any(col_name.endswith(s) for s in key_suffixes):
                    continue
                if col_name in t2_cols:
                    suggestions.append({
                        'from_table': t1_name,
                        'from_column': col_name,
                        'to_table': t2_name,
                        'to_column': col_name,
                        'confidence': 'high' if col_name.endswith('_id') else 'medium',
                    })

    return suggestions


def merge_preview(
    all_extracted: List[dict],
    app_names: List[str],
) -> dict:
    """Run a dry-run merge assessment and return detailed preview.

    Does not write any files — just reports what would happen.

    Returns:
        Dict with keys: assessment, suggestions, rls_conflicts, actions
    """
    assessment = assess_merge(all_extracted, app_names)

    # Detect RLS conflicts
    rls_conflicts = detect_rls_conflicts(all_extracted, app_names)

    # Build merged model in memory for relationship suggestions
    merged = merge_semantic_models(all_extracted, assessment, "PreviewModel")
    suggestions = suggest_cross_app_relationships(merged)

    # Build action log
    actions = []
    for mc in assessment.merge_candidates:
        actions.append({
            'action': 'merge_table',
            'table': mc.table_name,
            'sources': [s[0] for s in mc.sources],
            'overlap': round(mc.column_overlap, 2),
        })

    for conflict in assessment.measure_conflicts:
        for wb, formula in conflict.variants.items():
            actions.append({
                'action': 'namespace_measure',
                'measure': conflict.name,
                'app': wb,
                'new_name': f"{conflict.name} ({wb})",
            })

    for wb, tables in assessment.isolated_tables.items():
        for t in tables:
            actions.append({
                'action': 'skip_isolated_table',
                'table': t,
                'app': wb,
            })

    return {
        'assessment': assessment.to_dict(),
        'rls_conflicts': rls_conflicts,
        'relationship_suggestions': suggestions,
        'actions': actions,
        'total_actions': len(actions),
    }


def analyze_measure_risk(conflicts: List[MeasureConflict]) -> List[MeasureRiskAssessment]:
    """Analyze semantic risk of measure conflicts by parsing DAX patterns.

    A conflict where both formulas use the same aggregation on the same column
    is LOW risk (likely formatting/alias difference). A conflict using different
    aggregation functions (SUM vs COUNT) on different columns is HIGH risk.

    Returns:
        List of MeasureRiskAssessment for each conflict.
    """
    results = []
    for mc in conflicts:
        agg_types = {}
        columns_ref = {}
        for wb, formula in mc.variants.items():
            agg = _detect_aggregation(formula)
            agg_types[wb] = agg
            columns_ref[wb] = _extract_column_refs(formula)

        unique_aggs = set(agg_types.values()) - {'unknown'}
        unique_cols = set()
        for cols in columns_ref.values():
            unique_cols.update(cols)

        if len(unique_aggs) <= 1 and len(unique_cols) <= 1:
            risk = "low"
            reason = "Same aggregation pattern, likely formatting difference"
        elif len(unique_aggs) <= 1:
            risk = "medium"
            reason = f"Same aggregation ({', '.join(unique_aggs or {'?'})}), different columns"
        else:
            risk = "high"
            reason = f"Different aggregations: {', '.join(unique_aggs)}"

        results.append(MeasureRiskAssessment(
            measure_name=mc.name,
            risk_level=risk,
            reason=reason,
            variants=mc.variants,
            aggregation_types=agg_types,
        ))

    return results


_AGG_PATTERN = re.compile(
    r'\b(SUM|SUMX|COUNT|COUNTA|COUNTX|COUNTROWS|DISTINCTCOUNT|'
    r'AVERAGE|AVERAGEX|MIN|MINX|MAX|MAXX|'
    r'CALCULATE|CALCULATETABLE|MEDIAN|PERCENTILE)\s*\(',
    re.IGNORECASE,
)

_COL_REF_PATTERN = re.compile(r"\[([^\]]+)\]")


def _detect_aggregation(formula: str) -> str:
    """Detect the primary aggregation function in a DAX formula."""
    m = _AGG_PATTERN.search(formula)
    return m.group(1).upper() if m else 'unknown'


def _extract_column_refs(formula: str) -> List[str]:
    """Extract column references [ColumnName] from a DAX formula."""
    return _COL_REF_PATTERN.findall(formula)


# ═══════════════════════════════════════════════════════════════════
#  RLS role consolidation
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RLSConsolidation:
    """Analysis of RLS role consolidation across apps."""
    role_name: str
    source_apps: List[str]
    tables_affected: List[str]
    filter_expressions: Dict[str, str]  # {wb_name: dax_filter}
    action: str  # "keep", "merge", "namespace"
    merged_expression: Optional[str] = None


def consolidate_rls_roles(all_extracted: List[dict],
                          app_names: List[str],
                          strategy: str = "or") -> List[RLSConsolidation]:
    """Analyze and consolidate RLS roles across apps.

    Args:
        all_extracted: List of extracted data dicts.
        app_names: Corresponding app names.
        strategy: Predicate merge strategy - ``"and"`` (both must hold),
            ``"or"`` (either suffices), or ``"namespace"`` (keep separate).

    Rules:
    - Same role name + same filter expression → deduplicate (keep one)
    - Same role name + different table → keep both (different scope)
    - Same role name + same table + different filters → merge with strategy
    - Different role names → keep all

    Returns:
        List of RLSConsolidation recommendations.
    """
    # Collect all roles: role_name → [(wb_name, table, filter_expr)]
    role_map: Dict[str, list] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        for uf in extracted.get('user_filters', []):
            role_name = uf.get('name', uf.get('field', 'default'))
            table = uf.get('table', '')
            filter_expr = uf.get('filter_expression', uf.get('formula', ''))
            if role_name not in role_map:
                role_map[role_name] = []
            role_map[role_name].append((wb_name, table, filter_expr))

    results = []
    for role_name, entries in role_map.items():
        source_wbs = list(set(e[0] for e in entries))
        tables = list(set(e[1] for e in entries if e[1]))
        filters = {e[0]: e[2] for e in entries if e[2]}

        if len(source_wbs) == 1:
            results.append(RLSConsolidation(
                role_name=role_name,
                source_apps=source_wbs,
                tables_affected=tables,
                filter_expressions=filters,
                action="keep",
            ))
        else:
            unique_filters = set(filters.values())
            if len(unique_filters) <= 1:
                results.append(RLSConsolidation(
                    role_name=role_name,
                    source_apps=source_wbs,
                    tables_affected=tables,
                    filter_expressions=filters,
                    action="merge",
                    merged_expression=next(iter(unique_filters), None),
                ))
            elif strategy == "namespace":
                # Keep separate roles with app prefix
                for wb_name, expr in filters.items():
                    results.append(RLSConsolidation(
                        role_name=f"{role_name} ({wb_name})",
                        source_apps=[wb_name],
                        tables_affected=tables,
                        filter_expressions={wb_name: expr},
                        action="namespace",
                        merged_expression=expr,
                    ))
            else:
                # Merge with AND or OR
                joiner = " && " if strategy == "and" else " || "
                combined = joiner.join(
                    f"({expr})" for expr in unique_filters if expr
                )
                results.append(RLSConsolidation(
                    role_name=role_name,
                    source_apps=source_wbs,
                    tables_affected=tables,
                    filter_expressions=filters,
                    action="merge",
                    merged_expression=combined,
                ))

    return results


def merge_rls_roles(all_extracted: List[dict],
                    app_names: List[str]) -> List[dict]:
    """Merge RLS roles across apps with deduplication.

    Returns:
        Merged list of user_filter dicts ready for TMDL generation.
    """
    consolidations = consolidate_rls_roles(all_extracted, app_names)
    merged_roles = []
    seen_names = set()

    for cons in consolidations:
        if cons.role_name in seen_names:
            continue
        seen_names.add(cons.role_name)

        if cons.action == "keep":
            # Find original and keep it
            for wb_name, extracted in zip(app_names, all_extracted):
                for uf in extracted.get('user_filters', []):
                    rn = uf.get('name', uf.get('field', ''))
                    if rn == cons.role_name:
                        merged_roles.append(copy.deepcopy(uf))
                        break
                else:
                    continue
                break
        elif cons.action == "merge" and cons.merged_expression:
            # Create merged role
            role = {
                'name': cons.role_name,
                'table': cons.tables_affected[0] if cons.tables_affected else '',
                'filter_expression': cons.merged_expression,
                '_source_apps': cons.source_apps,
                '_consolidation': 'merged',
            }
            merged_roles.append(role)

    return merged_roles


def validate_rls_propagation(merged: dict) -> List[dict]:
    """Validate RLS roles have propagation paths to fact tables.

    For each RLS role's ``tablePermission`` target, verify the table
    exists in the model AND has a relationship path (direct or indirect)
    to at least one other table.

    Returns:
        List of ``{role, table, status, reason}`` dicts.
    """
    tables = {t.get('name', '') for t in merged.get('tables', []) if t.get('name')}
    rels = merged.get('relationships', [])
    # Build adjacency set for connected tables
    connected = set()
    for r in rels:
        ft = r.get('fromTable', '')
        tt = r.get('toTable', '')
        if ft:
            connected.add(ft)
        if tt:
            connected.add(tt)

    results = []
    for uf in merged.get('user_filters', []):
        role_name = uf.get('name', uf.get('field', 'unknown'))
        tbl = uf.get('table', '')
        if not tbl:
            results.append({
                'role': role_name, 'table': '', 'status': 'warning',
                'reason': 'No table specified for tablePermission',
            })
            continue
        if tbl not in tables:
            results.append({
                'role': role_name, 'table': tbl, 'status': 'error',
                'reason': f'Table "{tbl}" not found in model',
            })
        elif tbl not in connected:
            results.append({
                'role': role_name, 'table': tbl, 'status': 'warning',
                'reason': f'Table "{tbl}" is isolated (no relationships)',
            })
        else:
            results.append({
                'role': role_name, 'table': tbl, 'status': 'ok',
                'reason': '',
            })
    return results


def validate_rls_principals(merged: dict) -> List[dict]:
    """Detect conflicting principal format requirements across merged RLS.

    Parses ``USERPRINCIPALNAME()`` patterns to detect format conflicts
    (e.g., ``user@domain.com`` vs ``DOMAIN\\user``).

    Returns:
        List of ``{role, format_detected, expression}`` dicts.
    """
    results = []
    for uf in merged.get('user_filters', []):
        role_name = uf.get('name', uf.get('field', 'unknown'))
        expr = uf.get('filter_expression', uf.get('formula', ''))
        if not expr:
            continue
        fmt = 'unknown'
        if 'USERPRINCIPALNAME()' in expr.upper():
            fmt = 'UPN (user@domain.com)'
        elif 'USERNAME()' in expr.upper():
            fmt = 'USERNAME (DOMAIN\\user)'
        results.append({
            'role': role_name,
            'format_detected': fmt,
            'expression': expr[:100],
        })
    return results


def detect_isolated_tables(merged: dict) -> List[dict]:
    """Detect tables that have no relationships (isolated).

    Returns:
        List of ``{table, reason}`` dicts for tables with no
        relationship connections.
    """
    tables = [t.get('name', '') for t in merged.get('tables', []) if t.get('name')]
    rels = merged.get('relationships', [])
    connected = set()
    for r in rels:
        ft = r.get('fromTable', '')
        tt = r.get('toTable', '')
        if ft:
            connected.add(ft)
        if tt:
            connected.add(tt)

    isolated = []
    for tname in tables:
        if tname not in connected:
            isolated.append({
                'table': tname,
                'reason': f'Table "{tname}" has no relationships — may need manual wiring',
            })
            logger.warning("Isolated table detected: %s", tname)
    return isolated


# ═══════════════════════════════════════════════════════════════════
#  Cross-report navigation
# ═══════════════════════════════════════════════════════════════════

def build_cross_report_navigation(app_names: List[str],
                                   model_name: str) -> List[dict]:
    """Generate navigation button definitions for cross-report linking.

    Creates action button configs that allow users to navigate between
    sibling thin reports referencing the same shared semantic model.

    Args:
        app_names: Names of all thin reports.
        model_name: Name of the shared semantic model.

    Returns:
        List of navigation button definitions (one per report, containing
        links to all other reports).
    """
    nav_configs = []
    for current_wb in app_names:
        buttons = []
        for target_wb in app_names:
            if target_wb == current_wb:
                continue
            buttons.append({
                "label": target_wb,
                "target_report": f"{target_wb}.Report",
                "tooltip": f"Navigate to {target_wb}",
                "type": "navigation",
            })
        nav_configs.append({
            "report_name": current_wb,
            "model_name": model_name,
            "navigation_buttons": buttons,
        })
    return nav_configs


# ═══════════════════════════════════════════════════════════════════
#  TMDL reverse-engineering — load existing model from .tmdl files
# ═══════════════════════════════════════════════════════════════════

_UNQUOTE_RE = re.compile(r"^'((?:''|[^'])*)'$")


def _unquote_name(name: str) -> str:
    """Strip TMDL single-quote escaping: 'My Table' → My Table."""
    name = name.strip()
    m = _UNQUOTE_RE.match(name)
    if m:
        return m.group(1).replace("''", "'")
    return name


def _parse_tmdl_table(text: str) -> dict:
    """Parse a single ``table`` TMDL block into a dict.

    Returns a table dict compatible with the merged ``converted_objects``
    format used by ``tmdl_generator.generate_tmdl()``.
    """
    table = {"name": "", "columns": [], "measures": [], "partitions": [],
             "hierarchies": [], "annotations": []}

    lines = text.splitlines()
    if not lines:
        return table

    # First line: table 'Name' or table Name
    header = lines[0].strip()
    if header.startswith("table "):
        table["name"] = _unquote_name(header[6:].strip())

    i = 1
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ── measure ──
        if stripped.startswith("measure "):
            measure, i = _parse_tmdl_measure(lines, i)
            table["measures"].append(measure)
            continue

        # ── column ──
        if stripped.startswith("column "):
            column, i = _parse_tmdl_column(lines, i)
            table["columns"].append(column)
            continue

        # ── hierarchy ──
        if stripped.startswith("hierarchy "):
            hierarchy, i = _parse_tmdl_hierarchy(lines, i)
            table["hierarchies"].append(hierarchy)
            continue

        # ── partition ──
        if stripped.startswith("partition "):
            partition, i = _parse_tmdl_partition(lines, i)
            table["partitions"].append(partition)
            continue

        # ── annotation ──
        if stripped.startswith("annotation "):
            table["annotations"].append(stripped)

        i += 1

    return table


def _parse_tmdl_measure(lines: list, start: int) -> tuple:
    """Parse a measure block starting at *start*. Returns (measure_dict, next_index)."""
    header = lines[start].strip()
    # measure 'Name' = expression  OR  measure 'Name' = ```
    rest = header[len("measure "):].strip()

    # Find name vs expression split
    eq_pos = rest.find(" = ")
    if eq_pos >= 0:
        name = _unquote_name(rest[:eq_pos])
        expr_start = rest[eq_pos + 3:]
    else:
        name = _unquote_name(rest)
        expr_start = ""

    measure = {"name": name, "expression": "", "formatString": "",
               "displayFolder": "", "isHidden": False, "description": ""}

    # Handle multi-line expression (```)
    if expr_start.strip() == "```":
        expr_lines = []
        i = start + 1
        while i < len(lines):
            sl = lines[i].strip()
            if sl == "```":
                i += 1
                break
            expr_lines.append(sl)
            i += 1
        measure["expression"] = "\n".join(expr_lines)
    else:
        measure["expression"] = expr_start
        i = start + 1

    # Parse properties until next top-level item
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or _is_top_level(stripped):
            break
        if stripped.startswith("formatString:"):
            measure["formatString"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("displayFolder:"):
            measure["displayFolder"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("description:"):
            measure["description"] = stripped.split(":", 1)[1].strip()
        elif stripped == "isHidden":
            measure["isHidden"] = True
        i += 1

    return measure, i


def _parse_tmdl_column(lines: list, start: int) -> tuple:
    """Parse a column block. Returns (column_dict, next_index)."""
    header = lines[start].strip()
    rest = header[len("column "):].strip()

    eq_pos = rest.find(" = ")
    is_calculated = eq_pos >= 0
    if is_calculated:
        name = _unquote_name(rest[:eq_pos])
        expr_start = rest[eq_pos + 3:]
    else:
        name = _unquote_name(rest)
        expr_start = ""

    column = {"name": name, "dataType": "string", "sourceColumn": name,
              "isCalculated": is_calculated, "isHidden": False, "isKey": False,
              "dataCategory": "", "description": "", "displayFolder": "",
              "sortByColumn": "", "formatString": "", "summarizeBy": "none"}

    if is_calculated:
        if expr_start.strip() == "```":
            expr_lines = []
            i = start + 1
            while i < len(lines):
                sl = lines[i].strip()
                if sl == "```":
                    i += 1
                    break
                expr_lines.append(sl)
                i += 1
            column["expression"] = "\n".join(expr_lines)
        else:
            column["expression"] = expr_start
            i = start + 1
    else:
        i = start + 1

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or _is_top_level(stripped):
            break
        if stripped.startswith("dataType:"):
            column["dataType"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("sourceColumn:"):
            column["sourceColumn"] = _unquote_name(stripped.split(":", 1)[1].strip())
        elif stripped.startswith("formatString:"):
            column["formatString"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("summarizeBy:"):
            column["summarizeBy"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("dataCategory:"):
            column["dataCategory"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("displayFolder:"):
            column["displayFolder"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("description:"):
            column["description"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("sortByColumn:"):
            column["sortByColumn"] = _unquote_name(stripped.split(":", 1)[1].strip())
        elif stripped == "isHidden":
            column["isHidden"] = True
        elif stripped == "isKey":
            column["isKey"] = True
        i += 1

    return column, i


def _parse_tmdl_hierarchy(lines: list, start: int) -> tuple:
    """Parse a hierarchy block. Returns (hierarchy_dict, next_index)."""
    header = lines[start].strip()
    name = _unquote_name(header[len("hierarchy "):].strip())
    hierarchy = {"name": name, "levels": []}
    i = start + 1
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or _is_top_level(stripped):
            break
        if stripped.startswith("level "):
            level_name = _unquote_name(stripped[len("level "):].strip())
            level = {"name": level_name, "column": level_name}
            i += 1
            while i < len(lines):
                s2 = lines[i].strip()
                if not s2 or _is_top_level(s2) or s2.startswith("level "):
                    break
                if s2.startswith("column:"):
                    level["column"] = _unquote_name(s2.split(":", 1)[1].strip())
                i += 1
            hierarchy["levels"].append(level)
            continue
        i += 1
    return hierarchy, i


def _parse_tmdl_partition(lines: list, start: int) -> tuple:
    """Parse a partition block. Returns (partition_dict, next_index)."""
    header = lines[start].strip()
    name = _unquote_name(header[len("partition "):].strip())
    partition = {"name": name, "source": {"type": "m", "expression": ""}}
    i = start + 1
    expr_lines = []
    in_expression = False
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped and not in_expression:
            # Check if next non-blank is still partition content
            if i + 1 < len(lines) and _is_top_level(lines[i + 1].strip()):
                break
            if i + 1 >= len(lines):
                break
            i += 1
            continue
        if _is_top_level(stripped) and not in_expression:
            break
        if stripped.startswith("mode:"):
            partition.setdefault("mode", stripped.split(":", 1)[1].strip())
        elif stripped.startswith("source"):
            in_expression = False
        elif stripped.startswith("expression"):
            in_expression = True
            # Inline expression after =
            after_eq = stripped.split("=", 1)
            if len(after_eq) > 1 and after_eq[1].strip():
                if after_eq[1].strip() == "```":
                    i += 1
                    while i < len(lines):
                        sl = lines[i].strip()
                        if sl == "```":
                            i += 1
                            break
                        expr_lines.append(lines[i].rstrip())
                        i += 1
                    in_expression = False
                    continue
                else:
                    expr_lines.append(after_eq[1].strip())
        elif in_expression:
            if stripped == "```":
                in_expression = False
            else:
                expr_lines.append(lines[i].rstrip())
        i += 1
    if expr_lines:
        partition["source"]["expression"] = "\n".join(expr_lines)
    return partition, i


def _is_top_level(stripped: str) -> bool:
    """Check if a stripped line starts a new top-level TMDL element."""
    return (stripped.startswith("measure ") or
            stripped.startswith("column ") or
            stripped.startswith("hierarchy ") or
            stripped.startswith("partition ") or
            stripped.startswith("annotation ") or
            stripped.startswith("table ") or
            stripped.startswith("relationship ") or
            stripped.startswith("role "))


def _parse_tmdl_relationships(text: str) -> list:
    """Parse ``relationships.tmdl`` content into a list of relationship dicts."""
    relationships = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("relationship "):
            rel_id = stripped[len("relationship "):].strip()
            rel = {"name": rel_id, "fromTable": "", "fromColumn": "",
                   "toTable": "", "toColumn": "",
                   "fromCardinality": "many", "toCardinality": "one",
                   "crossFilteringBehavior": "oneDirection", "isActive": True}
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                if s.startswith("relationship "):
                    break
                if s.startswith("fromColumn:"):
                    parts = s.split(":", 1)[1].strip()
                    dot = parts.rfind(".")
                    if dot >= 0:
                        rel["fromTable"] = _unquote_name(parts[:dot])
                        rel["fromColumn"] = _unquote_name(parts[dot + 1:])
                    else:
                        rel["fromColumn"] = _unquote_name(parts)
                elif s.startswith("toColumn:"):
                    parts = s.split(":", 1)[1].strip()
                    dot = parts.rfind(".")
                    if dot >= 0:
                        rel["toTable"] = _unquote_name(parts[:dot])
                        rel["toColumn"] = _unquote_name(parts[dot + 1:])
                    else:
                        rel["toColumn"] = _unquote_name(parts)
                elif s.startswith("fromCardinality:"):
                    rel["fromCardinality"] = s.split(":", 1)[1].strip()
                elif s.startswith("toCardinality:"):
                    rel["toCardinality"] = s.split(":", 1)[1].strip()
                elif s.startswith("crossFilteringBehavior:"):
                    rel["crossFilteringBehavior"] = s.split(":", 1)[1].strip()
                elif s.startswith("isActive:"):
                    rel["isActive"] = s.split(":", 1)[1].strip().lower() != "false"
                i += 1
            relationships.append(rel)
            continue
        i += 1
    return relationships


def _parse_tmdl_roles(text: str) -> list:
    """Parse ``roles.tmdl`` content into a list of role dicts."""
    roles = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("role "):
            role_name = _unquote_name(stripped[len("role "):].strip())
            role = {"name": role_name, "modelPermission": "read",
                    "tablePermissions": [], "_migration_note": ""}
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                if s.startswith("role "):
                    break
                if s.startswith("modelPermission:"):
                    role["modelPermission"] = s.split(":", 1)[1].strip()
                elif s.startswith("annotation MigrationNote"):
                    val = s.split("=", 1)[1].strip().strip('"')
                    role["_migration_note"] = val
                elif s.startswith("tablePermission "):
                    tp_name = _unquote_name(s[len("tablePermission "):].strip())
                    tp = {"name": tp_name, "filterExpression": ""}
                    i += 1
                    while i < len(lines):
                        s2 = lines[i].strip()
                        if not s2:
                            i += 1
                            continue
                        if (s2.startswith("tablePermission ") or
                                s2.startswith("role ") or
                                s2.startswith("annotation ")):
                            break
                        if s2.startswith("filterExpression"):
                            eq = s2.split("=", 1)
                            if len(eq) > 1:
                                tp["filterExpression"] = eq[1].strip()
                        i += 1
                    role["tablePermissions"].append(tp)
                    continue
                i += 1
            roles.append(role)
            continue
        i += 1
    return roles


def load_existing_model(model_dir: str) -> dict:
    """Reverse-engineer an existing TMDL model directory into a
    ``converted_objects``-compatible dict.

    Reads ``.tmdl`` files from the SemanticModel definition directory
    (``tables/``, ``relationships.tmdl``, ``roles.tmdl``) and reconstructs
    the table/column/measure/relationship/parameter/RLS inventory.

    Args:
        model_dir: Path to the shared model output dir (contains
            ``<ModelName>.SemanticModel/definition/``), OR direct path to
            the ``definition/`` directory, OR path to the ``tables/``
            directory.

    Returns:
        A ``converted_objects``-compatible dict with ``datasources``,
        ``calculations``, ``parameters``, and ``user_filters``.
    """
    # Locate the definition directory
    def_dir = _find_definition_dir(model_dir)
    if not def_dir:
        logger.warning("Could not locate TMDL definition directory in %s", model_dir)
        return _empty_model()

    tables_dir = os.path.join(def_dir, "tables")
    tables = []
    if os.path.isdir(tables_dir):
        for fname in sorted(os.listdir(tables_dir)):
            if not fname.endswith(".tmdl"):
                continue
            fpath = os.path.join(tables_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            tbl = _parse_tmdl_table(content)
            if tbl.get("name"):
                tables.append(tbl)

    # Relationships
    relationships = []
    rels_path = os.path.join(def_dir, "relationships.tmdl")
    if os.path.isfile(rels_path):
        with open(rels_path, "r", encoding="utf-8") as f:
            relationships = _parse_tmdl_relationships(f.read())

    # Roles (RLS)
    roles = []
    roles_path = os.path.join(def_dir, "roles.tmdl")
    if os.path.isfile(roles_path):
        with open(roles_path, "r", encoding="utf-8") as f:
            roles = _parse_tmdl_roles(f.read())

    # Reconstruct converted_objects format
    # Build a single datasource with all tables + relationships
    ds = {
        "name": "SharedModel",
        "caption": "Shared Semantic Model",
        "connection": {},
        "tables": [],
        "columns": [],
        "relationships": relationships,
    }

    calculations = []
    for tbl in tables:
        # Physical table entry
        ds_table = {
            "name": tbl["name"],
            "type": "table",
            "columns": [],
        }
        for col in tbl.get("columns", []):
            ds_col = {
                "name": col["name"],
                "dataType": col.get("dataType", "string"),
                "table": tbl["name"],
            }
            ds_table["columns"].append(ds_col)

            if col.get("isCalculated") and col.get("expression"):
                calculations.append({
                    "name": f"[{col['name']}]",
                    "caption": col["name"],
                    "formula": col.get("expression", ""),
                    "table": tbl["name"],
                    "_classification": "calculated_column",
                    "role": "dimension",
                })

        ds["tables"].append(ds_table)

        # Measures → calculations
        for meas in tbl.get("measures", []):
            calculations.append({
                "name": f"[{meas['name']}]",
                "caption": meas["name"],
                "formula": meas.get("expression", ""),
                "table": tbl["name"],
                "_classification": "measure",
                "role": "measure",
            })

    # User filters from roles
    user_filters = []
    for role in roles:
        for tp in role.get("tablePermissions", []):
            user_filters.append({
                "name": role["name"],
                "table": tp.get("name", ""),
                "filter_expression": tp.get("filterExpression", ""),
            })

    return {
        "datasources": [ds] if ds["tables"] else [],
        "worksheets": [],
        "dashboards": [],
        "calculations": calculations,
        "parameters": [],
        "filters": [],
        "stories": [],
        "actions": [],
        "sets": [],
        "groups": [],
        "bins": [],
        "hierarchies": [],
        "sort_orders": [],
        "aliases": {},
        "custom_sql": [],
        "user_filters": user_filters,
    }


def _find_definition_dir(path: str) -> Optional[str]:
    """Locate the TMDL ``definition/`` directory from various starting points."""
    # Direct definition dir
    if os.path.basename(path) == "definition" and os.path.isdir(path):
        return path

    # Check for tables/ subdir (we're already in definition/)
    if os.path.isdir(os.path.join(path, "tables")):
        return path

    # Look for *.SemanticModel/definition/
    if os.path.isdir(path):
        for entry in os.listdir(path):
            if entry.endswith(".SemanticModel"):
                def_candidate = os.path.join(path, entry, "definition")
                if os.path.isdir(def_candidate):
                    return def_candidate

    # Try path/definition/
    def_candidate = os.path.join(path, "definition")
    if os.path.isdir(def_candidate):
        return def_candidate

    return None


# ═══════════════════════════════════════════════════════════════════
#  Incremental merge — add / remove app
# ═══════════════════════════════════════════════════════════════════

def add_to_model(model_dir: str,
                 new_extracted: dict,
                 new_app_name: str,
                 new_app_path: Optional[str] = None,
                 force: bool = False) -> dict:
    """Add a new app to an existing shared model.

    Loads the existing model from *model_dir* (via manifest + TMDL),
    performs an incremental merge with *new_extracted*, and returns
    the updated merged ``converted_objects`` plus an updated manifest.

    Args:
        model_dir: Path to the existing shared model output directory.
        new_extracted: ``converted_objects`` dict for the new app.
        new_app_name: Display name for the new app.
        new_app_path: Filesystem path to the new ``.qvf`` file.
        force: Merge even if score is low.

    Returns:
        Dict with ``merged``, ``manifest``, ``assessment``, ``validation``.
    """
    # Load existing manifest
    manifest = MergeManifest.load(model_dir)

    # Check for duplicate app
    if manifest.find_app(new_app_name) and not force:
        raise ValueError(
            f"app '{new_app_name}' already exists in the model. "
            f"Use force=True to re-add (will replace)."
        )

    # Load existing model from TMDL
    existing = load_existing_model(model_dir)

    # Combine existing + new for merge
    all_extracted = [existing, new_extracted]
    app_names = ["_existing_model_", new_app_name]

    assessment = assess_merge(all_extracted, app_names)

    if assessment.recommendation == "separate" and not force:
        return {
            "merged": None,
            "manifest": manifest,
            "assessment": assessment,
            "validation": None,
            "status": "rejected",
            "reason": f"Low merge score ({assessment.merge_score}). Use force=True.",
        }

    merged = merge_semantic_models(all_extracted, assessment, manifest.model_name)

    # Validation
    validation = generate_merge_validation_report(merged)

    # Update manifest
    # Remove existing entry if re-adding
    manifest.apps = [
        wb for wb in manifest.apps
        if wb.get("name", "").lower() != new_app_name.lower()
    ]

    # Build new app entry
    new_fps = build_table_fingerprints(new_extracted.get("datasources", []))
    new_tables = list(new_fps.keys())
    existing_table_names = set()
    for wb in manifest.apps:
        existing_table_names.update(wb.get("tables", []))
    exclusive = [t for t in new_tables if t not in existing_table_names]

    new_measures = [
        c.get("caption", c.get("name", ""))
        for c in new_extracted.get("calculations", [])
        if c.get("_classification") == "measure" or c.get("role") == "measure"
    ]

    file_hash = _file_hash(new_app_path) if new_app_path and os.path.isfile(new_app_path) else ""

    manifest.apps.append({
        "name": new_app_name,
        "path": new_app_path or "",
        "hash": file_hash,
        "tables": new_tables,
        "measures": new_measures,
        "exclusive_tables": exclusive,
    })

    # Update fingerprints and counts
    for ds in merged.get("datasources", []):
        fps = build_table_fingerprints([ds])
        for tname, (fp, _, _) in fps.items():
            manifest.table_fingerprints[tname] = fp.fingerprint()

    merged_ds = merged.get("datasources", [{}])[0] if merged.get("datasources") else {}
    manifest.artifact_counts = {
        "tables": len(merged_ds.get("tables", [])),
        "measures": len([c for c in merged.get("calculations", [])
                        if c.get("_classification") == "measure" or c.get("role") == "measure"]),
        "relationships": len(merged_ds.get("relationships", [])),
        "rls_roles": len(merged.get("user_filters", [])),
        "parameters": len(merged.get("parameters", [])),
    }
    manifest.validation_score = validation.get("score", 0)
    manifest.merge_score = assessment.merge_score
    manifest.timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "merged": merged,
        "manifest": manifest,
        "assessment": assessment,
        "validation": validation,
        "status": "added",
    }


def remove_from_model(model_dir: str,
                      app_name: str) -> dict:
    """Remove a app's exclusive artifacts from the shared model.

    Tables shared with other apps are NOT removed. Only tables,
    measures, and thin reports exclusively owned by *app_name*
    are cleaned up.

    Args:
        model_dir: Path to the existing shared model output directory.
        app_name: Name of the app to remove.

    Returns:
        Dict with ``manifest``, ``removed_tables``, ``removed_measures``,
        ``status``.
    """
    manifest = MergeManifest.load(model_dir)
    wb_entry = manifest.find_app(app_name)

    if not wb_entry:
        return {
            "manifest": manifest,
            "removed_tables": [],
            "removed_measures": [],
            "status": "not_found",
            "reason": f"app '{app_name}' not found in manifest.",
        }

    # Determine which tables are exclusive to this app
    other_tables = set()
    for wb in manifest.apps:
        if wb.get("name", "").lower() != app_name.lower():
            other_tables.update(wb.get("tables", []))

    wb_tables = set(wb_entry.get("tables", []))
    exclusive_tables = wb_tables - other_tables
    shared_tables = wb_tables & other_tables

    # Load existing model to rebuild without exclusive tables
    existing = load_existing_model(model_dir)

    # Remove exclusive tables from datasources
    removed_tables = []
    for ds in existing.get("datasources", []):
        original_tables = ds.get("tables", [])
        ds["tables"] = [
            t for t in original_tables
            if t.get("name") not in exclusive_tables
        ]
        removed_tables = [
            t.get("name") for t in original_tables
            if t.get("name") in exclusive_tables
        ]

        # Remove relationships involving removed tables
        ds["relationships"] = [
            r for r in ds.get("relationships", [])
            if r.get("fromTable") not in exclusive_tables
            and r.get("toTable") not in exclusive_tables
        ]

    # Remove measures from this app
    wb_measures = set(wb_entry.get("measures", []))
    removed_measures = []
    remaining_calcs = []
    for calc in existing.get("calculations", []):
        caption = calc.get("caption", calc.get("name", ""))
        if caption in wb_measures and calc.get("table") in exclusive_tables:
            removed_measures.append(caption)
        else:
            remaining_calcs.append(calc)
    existing["calculations"] = remaining_calcs

    # Update manifest
    manifest.apps = [
        wb for wb in manifest.apps
        if wb.get("name", "").lower() != app_name.lower()
    ]

    # Remove fingerprints for exclusive tables
    for tname in exclusive_tables:
        manifest.table_fingerprints.pop(tname, None)

    # Update artifact counts
    merged_ds = existing.get("datasources", [{}])[0] if existing.get("datasources") else {}
    manifest.artifact_counts = {
        "tables": len(merged_ds.get("tables", [])),
        "measures": len(remaining_calcs),
        "relationships": len(merged_ds.get("relationships", [])),
        "rls_roles": len(existing.get("user_filters", [])),
        "parameters": len(existing.get("parameters", [])),
    }
    manifest.timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "merged": existing,
        "manifest": manifest,
        "removed_tables": removed_tables,
        "removed_measures": removed_measures,
        "shared_tables_kept": list(shared_tables),
        "status": "removed",
    }


def _empty_model() -> dict:
    """Return an empty converted_objects dict."""
    return {
        "datasources": [], "worksheets": [], "dashboards": [],
        "calculations": [], "parameters": [], "filters": [],
        "stories": [], "actions": [], "sets": [], "groups": [],
        "bins": [], "hierarchies": [], "sort_orders": [],
        "aliases": {}, "custom_sql": [], "user_filters": [],
    }
