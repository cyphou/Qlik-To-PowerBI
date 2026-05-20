"""Auto-rollback and recovery engine.

Severity-based quality gate that runs after generation + QA suite.
Inspects validation results, schema checks, cross-artifact issues, and
repair counts to decide whether to ship, quarantine, or rollback.

Severity ladder:
    INFO     → log only, ship normally
    WARNING  → record in RecoveryReport, ship anyway
    ERROR    → move output to ``_FAILED/`` with ``triage.html``
    CRITICAL → rollback (restore from backup or delete)
"""

import json
import logging
import os
import shutil
import zipfile
from datetime import datetime

logger = logging.getLogger('qlik_to_powerbi.rollback')


class Severity:
    """Severity levels for migration quality gate."""
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'

    _ORDER = {INFO: 0, WARNING: 1, ERROR: 2, CRITICAL: 3}

    @classmethod
    def worse(cls, a, b):
        return a if cls._ORDER.get(a, 0) >= cls._ORDER.get(b, 0) else b

    @classmethod
    def level(cls, sev):
        return cls._ORDER.get(sev, 0)


class Verdict:
    """Result of the rollback engine evaluation."""
    EXIT_CLEAN = 0
    EXIT_WARNINGS = 1
    EXIT_ERRORS = 2
    EXIT_CRITICAL = 3

    _SEV_TO_EXIT = {
        Severity.INFO: EXIT_CLEAN,
        Severity.WARNING: EXIT_WARNINGS,
        Severity.ERROR: EXIT_ERRORS,
        Severity.CRITICAL: EXIT_CRITICAL,
    }

    def __init__(self, severity, issues, message=''):
        self.severity = severity
        self.issues = issues
        self.message = message or self._build_message()
        self.exit_code = self._SEV_TO_EXIT.get(severity, 0)
        self.timestamp = datetime.now().isoformat()

    def _build_message(self):
        counts = {}
        for sev, _src, _msg in self.issues:
            counts[sev] = counts.get(sev, 0) + 1
        parts = []
        for sev in (Severity.CRITICAL, Severity.ERROR, Severity.WARNING, Severity.INFO):
            if counts.get(sev, 0):
                parts.append(f"{counts[sev]} {sev}")
        return f"Quality gate: {', '.join(parts)}" if parts else "Quality gate: clean"

    @property
    def should_ship(self):
        return self.severity in (Severity.INFO, Severity.WARNING)

    @property
    def should_quarantine(self):
        return self.severity == Severity.ERROR

    @property
    def should_rollback(self):
        return self.severity == Severity.CRITICAL

    def to_dict(self):
        return {
            'severity': self.severity,
            'exit_code': self.exit_code,
            'message': self.message,
            'timestamp': self.timestamp,
            'issue_count': len(self.issues),
            'issues': [
                {'severity': s, 'source': src, 'message': msg}
                for s, src, msg in self.issues
            ],
        }


class RollbackEngine:
    """Evaluates migration output quality and executes rollback decisions."""

    MAX_VALIDATION_ERRORS = 0
    MAX_SCHEMA_ERRORS = 0
    MAX_CROSS_ERRORS = 3
    MAX_REPAIRS_FOR_CRITICAL = 20

    def __init__(self, project_dir, source_basename, extract_dir=None):
        self.project_dir = project_dir
        self.source_basename = source_basename
        self.extract_dir = extract_dir
        self.issues = []

    def ingest_validation(self, val_result):
        """Ingest results from ArtifactValidator."""
        if not val_result:
            return
        for err in val_result.get('errors', []):
            self.issues.append((Severity.ERROR, 'validator', str(err)))
        for warn in val_result.get('warnings', []):
            self.issues.append((Severity.WARNING, 'validator', str(warn)))

    def ingest_schema_result(self, schema_results):
        """Ingest results from schema_validator."""
        if not schema_results:
            return
        for result in schema_results:
            items = result.get('issues', []) if isinstance(result, dict) else []
            if hasattr(result, 'issues'):
                items = result.issues
            for issue in items:
                if isinstance(issue, dict):
                    sev = issue.get('severity', 'warning')
                    msg = issue.get('message', str(issue))
                    path = issue.get('path', '')
                    repaired = issue.get('repaired', False)
                else:
                    sev = getattr(issue, 'severity', 'warning')
                    msg = getattr(issue, 'message', str(issue))
                    path = getattr(issue, 'path', '')
                    repaired = getattr(issue, 'repaired', False)

                if repaired:
                    self.issues.append((Severity.INFO, 'schema',
                                        f"[auto-repaired] {path}: {msg}"))
                elif sev == 'error':
                    self.issues.append((Severity.ERROR, 'schema',
                                        f"{path}: {msg}"))
                else:
                    self.issues.append((Severity.WARNING, 'schema',
                                        f"{path}: {msg}"))

    def ingest_cross_result(self, cross_result):
        """Ingest results from cross_validator."""
        if not cross_result:
            return
        issues_list = []
        if isinstance(cross_result, dict):
            issues_list = cross_result.get('issues', [])
        elif hasattr(cross_result, 'issues'):
            issues_list = cross_result.issues

        for issue in issues_list:
            if isinstance(issue, dict):
                sev = issue.get('severity', 'warning')
                msg = issue.get('message', str(issue))
            else:
                sev = getattr(issue, 'severity', 'warning')
                msg = getattr(issue, 'message', str(issue))

            mapped = Severity.ERROR if sev == 'error' else Severity.WARNING
            self.issues.append((mapped, 'cross_validator', str(msg)))

    def ingest_repairs(self, recovery_report):
        """Ingest repair actions from RecoveryReport."""
        if not recovery_report:
            return
        repairs = []
        if isinstance(recovery_report, dict):
            repairs = recovery_report.get('repairs', [])
        elif hasattr(recovery_report, 'repairs'):
            repairs = recovery_report.repairs

        for repair in repairs:
            if isinstance(repair, dict):
                sev = repair.get('severity', 'warning')
                desc = repair.get('description', '')
                cat = repair.get('category', '')
            else:
                sev = getattr(repair, 'severity', 'warning')
                desc = getattr(repair, 'description', '')
                cat = getattr(repair, 'category', '')

            if sev == 'error':
                self.issues.append((Severity.WARNING, f'repair:{cat}',
                                    f"[repaired] {desc}"))
            else:
                self.issues.append((Severity.INFO, f'repair:{cat}',
                                    f"[repaired] {desc}"))

    def ingest_qa_report(self, qa_path):
        """Ingest from an existing qa_report.json file."""
        if not qa_path or not os.path.isfile(qa_path):
            return
        try:
            with open(qa_path, 'r', encoding='utf-8') as f:
                qa = json.load(f)
            val = qa.get('validation')
            if val:
                for err in val.get('error_details', []):
                    self.issues.append((Severity.ERROR, 'qa:validator', str(err)))
                warn_count = val.get('warnings', 0)
                if warn_count > 0:
                    self.issues.append((
                        Severity.WARNING, 'qa:validator',
                        f"{warn_count} validation warnings"
                    ))
            auto_fix = qa.get('auto_fix')
            if auto_fix and auto_fix.get('total_repairs', 0) > 0:
                self.issues.append((
                    Severity.INFO, 'qa:autofix',
                    f"{auto_fix['total_repairs']} DAX leaks auto-repaired"
                ))
        except (json.JSONDecodeError, OSError):
            pass

    def evaluate(self):
        """Evaluate all ingested issues and return a Verdict."""
        if not self.issues:
            return Verdict(Severity.INFO, [], "Quality gate: clean — no issues found")

        worst = Severity.INFO
        error_count = 0
        for sev, _src, _msg in self.issues:
            worst = Severity.worse(worst, sev)
            if sev == Severity.ERROR:
                error_count += 1

        if error_count > self.MAX_REPAIRS_FOR_CRITICAL:
            worst = Severity.CRITICAL

        return Verdict(worst, list(self.issues))

    def execute(self, verdict, *, backup_dir=None, strict=False,
                source_file=None):
        """Execute the rollback decision."""
        result = {
            'action': 'ship',
            'triage_path': None,
            'exit_code': verdict.exit_code if strict else 0,
            'verdict': verdict.to_dict(),
        }

        if verdict.should_ship:
            logger.info("Quality gate PASSED: %s", verdict.message)
            result['action'] = 'ship'
            return result

        if verdict.should_quarantine:
            logger.warning("Quality gate QUARANTINE: %s", verdict.message)
            result['action'] = 'quarantine'
            triage_path = self._quarantine(verdict, source_file)
            result['triage_path'] = triage_path
            return result

        if verdict.should_rollback:
            logger.error("Quality gate ROLLBACK: %s", verdict.message)
            result['action'] = 'rollback'
            triage_path = self._rollback(verdict, backup_dir, source_file)
            result['triage_path'] = triage_path
            return result

        return result

    def _quarantine(self, verdict, source_file=None):
        parent = os.path.dirname(self.project_dir)
        failed_dir = os.path.join(parent, '_FAILED')
        os.makedirs(failed_dir, exist_ok=True)

        dest = os.path.join(failed_dir, self.source_basename)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        if os.path.isdir(self.project_dir):
            shutil.move(self.project_dir, dest)
            logger.info("Project quarantined to: %s", dest)

        triage_path = os.path.join(failed_dir,
                                    f'{self.source_basename}_triage.html')
        self._write_triage_html(triage_path, verdict)

        triage_json = os.path.join(failed_dir,
                                    f'{self.source_basename}_triage.json')
        self._write_triage_json(triage_json, verdict)

        return triage_path

    def _rollback(self, verdict, backup_dir=None, source_file=None):
        parent = os.path.dirname(self.project_dir)

        triage_zip = os.path.join(parent,
                                   f'{self.source_basename}_triage_package.zip')
        self._build_triage_package(triage_zip, verdict, source_file)

        if os.path.isdir(self.project_dir):
            shutil.rmtree(self.project_dir)
            logger.info("Rolled back: removed %s", self.project_dir)

        if backup_dir and os.path.isdir(backup_dir):
            shutil.copytree(backup_dir, self.project_dir)
            logger.info("Restored from backup: %s", backup_dir)

        return triage_zip

    def _build_triage_package(self, zip_path, verdict, source_file=None):
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('triage/verdict.json',
                            json.dumps(verdict.to_dict(), indent=2,
                                       ensure_ascii=False))

                extract_dir = self.extract_dir or os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'qlik_export'
                )
                if os.path.isdir(extract_dir):
                    for name in os.listdir(extract_dir):
                        if name.endswith('.json'):
                            full = os.path.join(extract_dir, name)
                            if os.path.isfile(full):
                                zf.write(full, f'triage/extraction/{name}')

                if os.path.isdir(self.project_dir):
                    for name in os.listdir(self.project_dir):
                        if name.endswith(('.json', '.html', '.log')):
                            full = os.path.join(self.project_dir, name)
                            if os.path.isfile(full):
                                zf.write(full, f'triage/output/{name}')

                if source_file:
                    zf.writestr('triage/source_info.json', json.dumps({
                        'source_file': os.path.basename(source_file),
                        'source_size_bytes': (os.path.getsize(source_file)
                                              if os.path.isfile(source_file) else 0),
                    }, indent=2))

                html_content = self._render_triage_html(verdict)
                zf.writestr('triage/triage.html', html_content)

            logger.info("Triage package created: %s", zip_path)
        except OSError as exc:
            logger.error("Failed to create triage package: %s", exc)

    def _write_triage_json(self, path, verdict):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(verdict.to_dict(), f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.warning("Failed to write triage JSON: %s", exc)

    def _write_triage_html(self, path, verdict):
        try:
            html = self._render_triage_html(verdict)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
        except OSError as exc:
            logger.warning("Failed to write triage HTML: %s", exc)

    def _render_triage_html(self, verdict):
        sev_colors = {
            Severity.INFO: '#0078d4',
            Severity.WARNING: '#ff8c00',
            Severity.ERROR: '#d13438',
            Severity.CRITICAL: '#a4262c',
        }
        sev_labels = {
            Severity.INFO: 'INFO',
            Severity.WARNING: 'WARNING',
            Severity.ERROR: 'ERROR — Quarantined',
            Severity.CRITICAL: 'CRITICAL — Rolled Back',
        }
        color = sev_colors.get(verdict.severity, '#666')
        label = sev_labels.get(verdict.severity, verdict.severity.upper())

        issues_html = []
        for sev, src, msg in verdict.issues:
            badge_color = sev_colors.get(sev, '#666')
            esc_msg = (msg.replace('&', '&amp;').replace('<', '&lt;')
                       .replace('>', '&gt;'))
            esc_src = (src.replace('&', '&amp;').replace('<', '&lt;')
                       .replace('>', '&gt;'))
            issues_html.append(
                f'<tr>'
                f'<td><span style="color:{badge_color};font-weight:bold">'
                f'{sev.upper()}</span></td>'
                f'<td>{esc_src}</td>'
                f'<td>{esc_msg}</td>'
                f'</tr>'
            )

        issues_table = ('\n'.join(issues_html) if issues_html
                        else '<tr><td colspan="3">No issues</td></tr>')

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Migration Triage — {self.source_basename}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 2rem; background: #fafafa; }}
  .header {{ background: linear-gradient(135deg, {color}, #333); color: white;
             padding: 1.5rem 2rem; border-radius: 8px; margin-bottom: 2rem; }}
  .header h1 {{ margin: 0; font-size: 1.5rem; }}
  .header .badge {{ background: rgba(255,255,255,0.2); padding: 0.3rem 0.8rem;
                    border-radius: 4px; font-weight: bold; margin-top: 0.5rem;
                    display: inline-block; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); border-radius: 8px;
           overflow: hidden; }}
  th {{ background: #f3f3f3; text-align: left; padding: 0.8rem 1rem;
        border-bottom: 2px solid #ddd; }}
  td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #eee; }}
  .summary {{ margin-bottom: 2rem; }}
  .timestamp {{ color: rgba(255,255,255,0.7); font-size: 0.85rem;
                margin-top: 0.5rem; }}
</style>
</head>
<body>
<div class="header">
  <h1>Migration Triage Report</h1>
  <div class="badge">{label}</div>
  <p class="timestamp">Source: {self.source_basename} | {verdict.timestamp}</p>
</div>
<div class="summary">
  <p><strong>{verdict.message}</strong></p>
  <p>Total issues: {len(verdict.issues)}</p>
</div>
<table>
  <thead><tr><th>Severity</th><th>Source</th><th>Details</th></tr></thead>
  <tbody>
    {issues_table}
  </tbody>
</table>
</body>
</html>"""
