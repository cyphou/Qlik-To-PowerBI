"""Governance engine — naming conventions, PII detection, audit trail, sensitivity labels.

Sprint 99 — Enterprise governance framework for migration artifacts.

Classes:
    GovernanceEngine: configurable governance checks with warn/enforce modes.
    AuditTrail: append-only JSONL migration audit log.

Usage:
    engine = GovernanceEngine(config)
    report = engine.check(tmdl_data)
    engine.apply_renames(tmdl_data)  # only in enforce mode
"""

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── PII detection patterns ────────────────────────────────────────────────────
# Each pattern: (name, compiled_regex, data_classification_value)
_PII_PATTERNS = [
    ("email", re.compile(r"\bemail|e[-_]?mail\b", re.IGNORECASE), "email"),
    ("ssn", re.compile(r"\bssn|social.?security|sin\b", re.IGNORECASE), "ssn"),
    ("phone", re.compile(r"\bphone|mobile|cell.?phone|telephone|fax\b", re.IGNORECASE), "phone"),
    ("name_personal", re.compile(r"\b(?:first|last|middle|full).?name|surname|given.?name\b", re.IGNORECASE), "name"),
    ("address", re.compile(r"\baddress|street|zip.?code|postal.?code|city|state\b", re.IGNORECASE), "address"),
    ("dob", re.compile(r"\b(?:date.?of.?birth|dob|birth.?date|birthday)\b", re.IGNORECASE), "dateOfBirth"),
    ("credit_card", re.compile(r"\bcredit.?card|card.?number|ccn|pan\b", re.IGNORECASE), "creditCard"),
    ("ip_address", re.compile(r"\bip.?address|ip_addr|ipv[46]\b", re.IGNORECASE), "ipAddress"),
    ("passport", re.compile(r"\bpassport|visa.?number\b", re.IGNORECASE), "passport"),
    ("national_id", re.compile(r"\bnational.?id|id.?number|driver.?licen[cs]e\b", re.IGNORECASE), "nationalId"),
]

# ── Default governance configuration ──────────────────────────────────────────
DEFAULT_GOVERNANCE_CONFIG = {
    "mode": "warn",              # "warn" | "enforce"
    "naming": {
        "measure_prefix": "",         # e.g. "m_" — empty = no enforcement
        "column_style": "",           # "snake_case" | "camelCase" | "PascalCase" | ""
        "table_style": "",            # "PascalCase" | "snake_case" | ""
        "max_name_length": 0,         # 0 = no limit
    },
    "pii_detection": True,
    "sensitivity_mapping": {
        # Qlik project permission → PBI sensitivity label
        "Viewer": "General",
        "Interactor": "General",
        "Editor": "Confidential",
        "Project Leader": "Highly Confidential",
    },
    "audit_trail": True,
    "audit_log_path": "migration_audit.jsonl",
}


# ── Naming style helpers ──────────────────────────────────────────────────────

def _is_snake_case(name):
    """Check if name matches snake_case (lowercase with underscores)."""
    return bool(re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$', name))


def _is_camel_case(name):
    """Check if name matches camelCase."""
    return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name))


def _is_pascal_case(name):
    """Check if name matches PascalCase."""
    return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))


def _to_snake_case(name):
    """Convert name to snake_case."""
    s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return re.sub(r'[\s\-]+', '_', s2).lower()


def _to_camel_case(name):
    """Convert name to camelCase."""
    parts = re.split(r'[\s_\-]+', name)
    if not parts:
        return name
    return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])


def _to_pascal_case(name):
    """Convert name to PascalCase."""
    parts = re.split(r'[\s_\-]+', name)
    return ''.join(p.capitalize() for p in parts)


_STYLE_CHECKER = {
    "snake_case": _is_snake_case,
    "camelCase": _is_camel_case,
    "PascalCase": _is_pascal_case,
}

_STYLE_CONVERTER = {
    "snake_case": _to_snake_case,
    "camelCase": _to_camel_case,
    "PascalCase": _to_pascal_case,
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class GovernanceIssue:
    """A single governance check result."""
    category: str       # "naming" | "pii" | "sensitivity"
    severity: str       # "info" | "warn" | "fail"
    artifact_type: str  # "table" | "column" | "measure"
    artifact_name: str
    message: str
    recommendation: str = ""
    auto_fix: str = ""  # suggested rename or annotation


@dataclass
class GovernanceReport:
    """Aggregated governance check results."""
    timestamp: str = ""
    mode: str = "warn"
    issues: list = field(default_factory=list)
    classifications: dict = field(default_factory=dict)  # col → classification
    renames: dict = field(default_factory=dict)           # old_name → new_name
    sensitivity_label: str = ""

    @property
    def issue_count(self):
        return len(self.issues)

    @property
    def warn_count(self):
        return sum(1 for i in self.issues if i.severity == "warn")

    @property
    def fail_count(self):
        return sum(1 for i in self.issues if i.severity == "fail")

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "issue_count": self.issue_count,
            "warn_count": self.warn_count,
            "fail_count": self.fail_count,
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity,
                    "artifact_type": i.artifact_type,
                    "artifact_name": i.artifact_name,
                    "message": i.message,
                    "recommendation": i.recommendation,
                }
                for i in self.issues
            ],
            "classifications": self.classifications,
            "sensitivity_label": self.sensitivity_label,
        }


# ── GovernanceEngine ──────────────────────────────────────────────────────────

class GovernanceEngine:
    """Configurable governance checks for migration artifacts.

    Config structure (in config.json under "governance" key):
        {
            "mode": "warn",  # or "enforce"
            "naming": {
                "measure_prefix": "m_",
                "column_style": "snake_case",
                "table_style": "PascalCase",
                "max_name_length": 128
            },
            "pii_detection": true,
            "sensitivity_mapping": { ... },
            "audit_trail": true,
            "audit_log_path": "migration_audit.jsonl"
        }
    """

    def __init__(self, config=None):
        self.config = dict(DEFAULT_GOVERNANCE_CONFIG)
        if config:
            # Deep merge
            for k, v in config.items():
                if isinstance(v, dict) and isinstance(self.config.get(k), dict):
                    self.config[k] = {**self.config[k], **v}
                else:
                    self.config[k] = v
        self.mode = self.config.get("mode", "warn")

    def check(self, tmdl_tables, worksheets=None):
        """Run all governance checks on TMDL table data.

        Args:
            tmdl_tables: list of table dicts (from TMDL generator or extracted data)
                         each with 'name', 'columns' (list), 'measures' (list)
            worksheets: optional list of worksheet dicts (for sensitivity analysis)

        Returns:
            GovernanceReport with all issues found.
        """
        report = GovernanceReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=self.mode,
        )

        naming_cfg = self.config.get("naming", {})

        for table in (tmdl_tables or []):
            table_name = table.get("name", "")

            # ── Table naming check ──
            table_style = naming_cfg.get("table_style", "")
            if table_style and table_name:
                checker = _STYLE_CHECKER.get(table_style)
                if checker and not checker(table_name):
                    converter = _STYLE_CONVERTER.get(table_style)
                    suggested = converter(table_name) if converter else ""
                    issue = GovernanceIssue(
                        category="naming",
                        severity="fail" if self.mode == "enforce" else "warn",
                        artifact_type="table",
                        artifact_name=table_name,
                        message=f"Table '{table_name}' does not match {table_style} convention.",
                        recommendation=f"Rename to '{suggested}'." if suggested else "",
                        auto_fix=suggested,
                    )
                    report.issues.append(issue)
                    if suggested:
                        report.renames[table_name] = suggested

            # ── Column checks ──
            for col in table.get("columns", []):
                col_name = col if isinstance(col, str) else col.get("name", "")
                if not col_name:
                    continue
                self._check_column_naming(col_name, table_name, naming_cfg, report)
                if self.config.get("pii_detection", True):
                    self._check_pii(col_name, table_name, report)

            # ── Measure checks ──
            for meas in table.get("measures", []):
                meas_name = meas if isinstance(meas, str) else meas.get("name", "")
                if not meas_name:
                    continue
                self._check_measure_naming(meas_name, table_name, naming_cfg, report)

            # ── Max name length ──
            max_len = naming_cfg.get("max_name_length", 0)
            if max_len > 0:
                self._check_name_length(table, max_len, report)

        return report

    def _check_column_naming(self, col_name, table_name, naming_cfg, report):
        """Check column naming convention."""
        col_style = naming_cfg.get("column_style", "")
        if not col_style:
            return
        checker = _STYLE_CHECKER.get(col_style)
        if checker and not checker(col_name):
            converter = _STYLE_CONVERTER.get(col_style)
            suggested = converter(col_name) if converter else ""
            report.issues.append(GovernanceIssue(
                category="naming",
                severity="fail" if self.mode == "enforce" else "warn",
                artifact_type="column",
                artifact_name=f"{table_name}.{col_name}",
                message=f"Column '{col_name}' does not match {col_style} convention.",
                recommendation=f"Rename to '{suggested}'." if suggested else "",
                auto_fix=suggested,
            ))

    def _check_measure_naming(self, meas_name, table_name, naming_cfg, report):
        """Check measure naming convention (prefix enforcement)."""
        prefix = naming_cfg.get("measure_prefix", "")
        if not prefix:
            return
        if not meas_name.startswith(prefix):
            suggested = prefix + meas_name
            report.issues.append(GovernanceIssue(
                category="naming",
                severity="fail" if self.mode == "enforce" else "warn",
                artifact_type="measure",
                artifact_name=f"{table_name}.{meas_name}",
                message=f"Measure '{meas_name}' missing required prefix '{prefix}'.",
                recommendation=f"Rename to '{suggested}'.",
                auto_fix=suggested,
            ))

    def _check_pii(self, col_name, table_name, report):
        """Scan column name for PII patterns and classify."""
        for pattern_name, regex, classification in _PII_PATTERNS:
            if regex.search(col_name):
                full_name = f"{table_name}.{col_name}"
                report.classifications[full_name] = classification
                report.issues.append(GovernanceIssue(
                    category="pii",
                    severity="warn",
                    artifact_type="column",
                    artifact_name=full_name,
                    message=f"Column '{col_name}' matches PII pattern '{pattern_name}' → classified as '{classification}'.",
                    recommendation=f"Add dataClassification annotation: {classification}",
                ))
                break  # first match wins

    def _check_name_length(self, table, max_len, report):
        """Check all names in a table against max length."""
        table_name = table.get("name", "")
        all_names = [table_name]
        for col in table.get("columns", []):
            all_names.append(col if isinstance(col, str) else col.get("name", ""))
        for meas in table.get("measures", []):
            all_names.append(meas if isinstance(meas, str) else meas.get("name", ""))

        for name in all_names:
            if name and len(name) > max_len:
                report.issues.append(GovernanceIssue(
                    category="naming",
                    severity="warn",
                    artifact_type="name",
                    artifact_name=name,
                    message=f"Name '{name}' exceeds max length ({len(name)} > {max_len}).",
                    recommendation=f"Shorten to {max_len} characters.",
                ))

    def apply_renames(self, tmdl_tables, report):
        """Apply auto-fix renames from a governance report to TMDL tables.

        Only applies in 'enforce' mode. Handles table, column, and measure renames.
        Returns the number of renames applied.
        """
        if self.mode != "enforce":
            return 0

        rename_count = 0
        prefix = self.config.get("naming", {}).get("measure_prefix", "")

        # Build column rename map from issues: "Table.OldCol" → "NewCol"
        col_rename_map = {}
        for issue in report.issues:
            if issue.auto_fix and issue.artifact_type == "column":
                col_rename_map[issue.artifact_name] = issue.auto_fix

        for table in (tmdl_tables or []):
            table_name = table.get("name", "")
            # Table rename
            if table_name in report.renames:
                table["name"] = report.renames[table_name]
                rename_count += 1

            # Column renames (from naming convention issues)
            for col in table.get("columns", []):
                if isinstance(col, dict):
                    col_name = col.get("name", "")
                    full_name = f"{table_name}.{col_name}"
                    if full_name in col_rename_map:
                        col["name"] = col_rename_map[full_name]
                        rename_count += 1

            # Measure prefix
            if prefix:
                for meas in table.get("measures", []):
                    if isinstance(meas, dict):
                        meas_name = meas.get("name", "")
                        if meas_name and not meas_name.startswith(prefix):
                            meas["name"] = prefix + meas_name
                            rename_count += 1

        return rename_count

    def apply_classifications(self, tmdl_tables, report):
        """Add dataClassification annotations to columns identified as PII.

        Returns the number of annotations added.
        """
        count = 0
        for table in (tmdl_tables or []):
            table_name = table.get("name", "")
            for col in table.get("columns", []):
                if isinstance(col, dict):
                    col_name = col.get("name", "")
                    full_name = f"{table_name}.{col_name}"
                    classification = report.classifications.get(full_name)
                    if classification:
                        col.setdefault("annotations", []).append({
                            "name": "dataClassification",
                            "value": classification,
                        })
                        count += 1
        return count

    def map_sensitivity_label(self, Qlik_permissions=None):
        """Map Qlik project permissions to PBI sensitivity label.

        Args:
            Qlik_permissions: list of permission strings from Qlik project

        Returns:
            Highest applicable PBI sensitivity label string.
        """
        mapping = self.config.get("sensitivity_mapping", {})
        if not Qlik_permissions or not mapping:
            return "General"

        # Map each permission and take the highest sensitivity
        label_order = ["General", "Confidential", "Highly Confidential"]
        highest = "General"
        for perm in Qlik_permissions:
            label = mapping.get(perm, "General")
            if label in label_order:
                idx = label_order.index(label)
                if idx > label_order.index(highest):
                    highest = label
        return highest


# ── AuditTrail ────────────────────────────────────────────────────────────────

class AuditTrail:
    """Append-only JSONL migration audit log.

    Each entry records who migrated what, when, source hash, output hash,
    deployment target, and governance report summary.
    """

    def __init__(self, log_path="migration_audit.jsonl"):
        self.log_path = log_path
        self._entries = []

    def record(self, *, source_file="", output_dir="", app_name="",
               user="", source_hash="", output_hash="",
               deploy_target="", governance_summary=None, extra=None):
        """Record a migration event."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user or os.environ.get("USERNAME", os.environ.get("USER", "")),
            "app": app_name,
            "source_file": os.path.basename(source_file) if source_file else "",
            "source_hash": source_hash,
            "output_dir": output_dir,
            "output_hash": output_hash,
            "deploy_target": deploy_target,
        }
        if governance_summary:
            entry["governance"] = governance_summary
        if extra:
            entry.update(extra)
        self._entries.append(entry)
        return entry

    def save(self):
        """Append all buffered entries to the JSONL log file."""
        if not self._entries:
            return 0
        count = 0
        with open(self.log_path, 'a', encoding='utf-8') as f:
            for entry in self._entries:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                count += 1
        saved = len(self._entries)
        self._entries.clear()
        return saved

    def read(self, limit=100):
        """Read the most recent entries from the log file."""
        if not os.path.exists(self.log_path):
            return []
        entries = []
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:]

    @staticmethod
    def compute_file_hash(filepath):
        """Compute SHA-256 hash of a file for audit purposes."""
        if not filepath or not os.path.isfile(filepath):
            return ""
        try:
            h = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()
        except (IOError, OSError):
            return ""

    @staticmethod
    def compute_dir_hash(dirpath):
        """Compute a combined SHA-256 hash of all files in a directory."""
        if not dirpath or not os.path.isdir(dirpath):
            return ""
        h = hashlib.sha256()
        for root, _dirs, files in sorted(os.walk(dirpath)):
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                with open(fpath, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        h.update(chunk)
        return h.hexdigest()


def run_governance(tmdl_tables, config=None, worksheets=None,
                   Qlik_permissions=None):
    """Convenience function: create engine, run checks, return report.

    Args:
        tmdl_tables: list of table dicts with 'name', 'columns', 'measures'
        config: governance config dict (or None for defaults)
        worksheets: optional worksheet data for sensitivity analysis
        Qlik_permissions: optional Qlik project permissions list

    Returns:
        GovernanceReport
    """
    engine = GovernanceEngine(config)
    report = engine.check(tmdl_tables, worksheets)

    # Sensitivity label
    if Qlik_permissions:
        report.sensitivity_label = engine.map_sensitivity_label(Qlik_permissions)

    # Apply auto-fixes in enforce mode
    if engine.mode == "enforce":
        engine.apply_renames(tmdl_tables, report)
        engine.apply_classifications(tmdl_tables, report)

    # Always apply classifications (annotations are informational)
    elif engine.config.get("pii_detection", True):
        engine.apply_classifications(tmdl_tables, report)

    return report


# ── Sprint 124: Endorsement Classification ────────────────────────────────────

# Sensitivity patterns: (name, regex, label)
_SENSITIVITY_PATTERNS = [
    # Confidential — PII and personal data
    ("email", re.compile(r"\bemail|e[-_]?mail\b", re.IGNORECASE), "Confidential"),
    ("ssn", re.compile(r"\bssn|social.?security|sin\b", re.IGNORECASE), "Highly Confidential"),
    ("phone", re.compile(r"\bphone|mobile|cell.?phone|telephone|fax\b", re.IGNORECASE), "Confidential"),
    ("personal_name", re.compile(r"\b(?:first|last|middle|full).?name|surname|given.?name\b", re.IGNORECASE), "Confidential"),
    ("address", re.compile(r"\baddress|street|zip.?code|postal.?code\b", re.IGNORECASE), "Confidential"),
    ("dob", re.compile(r"\b(?:date.?of.?birth|dob|birth.?date|birthday)\b", re.IGNORECASE), "Highly Confidential"),
    ("credit_card", re.compile(r"\bcredit.?card|card.?number|ccn|pan\b", re.IGNORECASE), "Highly Confidential"),
    ("passport", re.compile(r"\bpassport|visa.?number\b", re.IGNORECASE), "Highly Confidential"),
    # Internal — financial data
    ("salary", re.compile(r"\bsalary|wage|compensation|bonus|payroll\b", re.IGNORECASE), "Internal"),
    ("revenue", re.compile(r"\brevenue|profit|margin|cost|budget|expense\b", re.IGNORECASE), "Internal"),
    ("price", re.compile(r"\bprice|discount|markup|wholesale\b", re.IGNORECASE), "Internal"),
]


def classify_endorsement(fidelity_score, approximation_count=0, validation_errors=0):
    """Classify migration artifact for PBI endorsement.

    Args:
        fidelity_score: Migration fidelity percentage (0–100)
        approximation_count: Number of approximated DAX formulas
        validation_errors: Number of TMDL validation errors

    Returns:
        dict with 'endorsement' ('certified'|'promoted'|'none'),
        'reason', and 'confidence' (0–100)
    """
    if validation_errors > 0:
        return {
            'endorsement': 'none',
            'reason': f'{validation_errors} validation error(s) — fix before endorsement',
            'confidence': max(0, fidelity_score - validation_errors * 10),
        }

    if fidelity_score >= 100 and approximation_count == 0:
        return {
            'endorsement': 'certified',
            'reason': 'Perfect fidelity, no approximations',
            'confidence': 100,
        }

    if fidelity_score >= 90 and approximation_count <= 5:
        return {
            'endorsement': 'promoted',
            'reason': f'{fidelity_score}% fidelity, {approximation_count} approximation(s)',
            'confidence': fidelity_score,
        }

    return {
        'endorsement': 'none',
        'reason': f'{fidelity_score}% fidelity, {approximation_count} approximation(s) — manual review needed',
        'confidence': fidelity_score,
    }


def infer_sensitivity_labels(tmdl_tables):
    """Scan all column names and infer sensitivity labels.

    Returns:
        list of dicts: [{'table': str, 'column': str, 'label': str, 'pattern': str}]
    """
    results = []
    for table in (tmdl_tables or []):
        table_name = table.get('name', '')
        for col in table.get('columns', []):
            col_name = col if isinstance(col, str) else col.get('name', '')
            for pattern_name, regex, label in _SENSITIVITY_PATTERNS:
                if regex.search(col_name):
                    results.append({
                        'table': table_name,
                        'column': col_name,
                        'label': label,
                        'pattern': pattern_name,
                    })
                    break
    return results


def generate_endorsement_report(migration_metadata, tmdl_tables=None):
    """Generate endorsement + sensitivity report for a migration.

    Args:
        migration_metadata: dict with 'fidelity_score', 'approximation_count',
                           'validation_errors' (from migration_report.py)
        tmdl_tables: optional tables for sensitivity inference

    Returns:
        dict: Combined endorsement + sensitivity report
    """
    fidelity = migration_metadata.get('fidelity_score', 100)
    approx = migration_metadata.get('approximation_count', 0)
    val_errors = migration_metadata.get('validation_errors', 0)

    endorsement = classify_endorsement(fidelity, approx, val_errors)

    report = {
        'endorsement': endorsement,
        'sensitivity_labels': [],
        'summary': {
            'fidelity_score': fidelity,
            'approximation_count': approx,
            'validation_errors': val_errors,
        },
    }

    if tmdl_tables:
        report['sensitivity_labels'] = infer_sensitivity_labels(tmdl_tables)
        # Determine overall label from highest
        label_order = ['General', 'Internal', 'Confidential', 'Highly Confidential']
        highest = 'General'
        for sl in report['sensitivity_labels']:
            lbl = sl.get('label', 'General')
            if lbl in label_order and label_order.index(lbl) > label_order.index(highest):
                highest = lbl
        report['overall_sensitivity'] = highest

    return report
