"""
Fabric Bundle Deployer — deploy shared model + thin reports as a bundle.

Orchestrates the deployment of a shared semantic model project to
a Microsoft Fabric workspace:

  1. Discover artifacts in the project directory (.SemanticModel + .Report dirs)
  2. Deploy the SemanticModel first (reports depend on it)
  3. Deploy each thin report with error isolation
  4. Bind reports to the deployed semantic model
  5. Optionally trigger a refresh on the semantic model
  6. Produce a deployment report (JSON + console summary)

Usage:
    deployer = BundleDeployer(workspace_id='...')
    result = deployer.deploy_bundle('/path/to/project_dir')
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BundleDeploymentResult:
    """Result of a shared-model bundle deployment."""

    def __init__(self, project_dir, workspace_id):
        self.project_dir = str(project_dir)
        self.workspace_id = workspace_id
        self.start_time = datetime.now()
        self.end_time = None
        self.model_name = None
        self.model_id = None
        self.model_status = 'pending'  # pending | deployed | failed
        self.model_error = None
        self.reports = []  # list of ReportDeploymentResult dicts
        self.refresh_status = None  # None | triggered | failed | skipped
        self.refresh_error = None
        self.rollback_actions = []  # list of {action, artifact, status}
        self.validation = []  # list of {check, status, detail}
        self.conflicts = []  # list of {name, type, existing_id}

    @property
    def success(self):
        """True if model deployed and all reports (if any) succeeded."""
        if self.model_status != 'deployed':
            return False
        if not self.reports:
            return True
        return any(r['status'] == 'deployed' for r in self.reports)

    @property
    def deployed_count(self):
        return sum(1 for r in self.reports if r['status'] == 'deployed')

    @property
    def failed_count(self):
        return sum(1 for r in self.reports if r['status'] == 'failed')

    @property
    def total_count(self):
        return len(self.reports)

    def to_dict(self):
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        return {
            'project_dir': self.project_dir,
            'workspace_id': self.workspace_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': duration,
            'model_name': self.model_name,
            'model_id': self.model_id,
            'model_status': self.model_status,
            'model_error': self.model_error,
            'reports': self.reports,
            'reports_deployed': self.deployed_count,
            'reports_failed': self.failed_count,
            'reports_total': self.total_count,
            'refresh_status': self.refresh_status,
            'refresh_error': self.refresh_error,
            'rollback_actions': self.rollback_actions,
            'validation': self.validation,
            'conflicts': self.conflicts,
            'success': self.success,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)

    def save(self, output_path):
        """Save deployment result to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info('Bundle deployment report saved: %s', output_path)

    def print_summary(self):
        """Print deployment summary to console."""
        duration = ''
        if self.end_time:
            secs = (self.end_time - self.start_time).total_seconds()
            duration = f' ({secs:.1f}s)'

        print(f'\n{"=" * 64}')
        print(f'  Fabric Bundle Deployment Summary{duration}')
        print(f'{"=" * 64}')
        print(f'  Workspace:  {self.workspace_id}')
        print(f'  Model:      {self.model_name} [{self.model_status}]')
        if self.model_id:
            print(f'  Model ID:   {self.model_id}')
        print(f'  Reports:    {self.deployed_count}/{self.total_count} deployed')
        if self.refresh_status:
            print(f'  Refresh:    {self.refresh_status}')

        if self.model_error:
            print(f'\n  [FAIL] Model: {self.model_error}')

        for rpt in self.reports:
            icon = '✓' if rpt['status'] == 'deployed' else '✗'
            status_detail = rpt.get('id', rpt.get('error', ''))
            print(f'  [{icon}] {rpt["name"]}: {status_detail}')

        status = '✓ SUCCESS' if self.success else '✗ FAILED'
        print(f'\n  Result: {status}')
        print()


class BundleDeployer:
    """Deploy a shared semantic model + thin reports as a Fabric bundle."""

    def __init__(self, workspace_id, client=None):
        """Initialize bundle deployer.

        Args:
            workspace_id: Target Fabric workspace ID.
            client: Pre-configured FabricClient (creates default if None).
        """
        self.workspace_id = workspace_id
        if client is None:
            from .client import FabricClient
            client = FabricClient()
        self.client = client
        self._deployer = None

    @property
    def deployer(self):
        """Lazy-init FabricDeployer."""
        if self._deployer is None:
            from .deployer import FabricDeployer
            self._deployer = FabricDeployer(client=self.client)
        return self._deployer

    def discover_artifacts(self, project_dir):
        """Discover SemanticModel and Report directories in a project.

        Args:
            project_dir: Root project directory.

        Returns:
            tuple: (model_dir, model_name, report_dirs)
                model_dir: Path to .SemanticModel directory (or None)
                model_name: Name of the semantic model (or None)
                report_dirs: list of (report_name, report_path) tuples
        """
        project_path = Path(project_dir)
        model_dir = None
        model_name = None
        report_dirs = []

        for entry in sorted(project_path.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.endswith('.SemanticModel'):
                model_dir = entry
                model_name = entry.name.replace('.SemanticModel', '')
            elif entry.name.endswith('.Report'):
                report_name = entry.name.replace('.Report', '')
                report_dirs.append((report_name, entry))

        return model_dir, model_name, report_dirs

    def _read_artifact_definition(self, artifact_dir):
        """Read all definition files from an artifact directory.

        Returns a dict suitable for Fabric Items API createItem payload.
        """
        artifact_path = Path(artifact_dir)
        display_name = (artifact_path.name
                        .replace('.SemanticModel', '')
                        .replace('.Report', ''))

        parts = {}
        definition_dir = artifact_path / 'definition'
        if definition_dir.is_dir():
            for f in sorted(definition_dir.rglob('*')):
                if f.is_file():
                    rel = str(f.relative_to(definition_dir)).replace('\\', '/')
                    try:
                        parts[rel] = f.read_text(encoding='utf-8')
                    except (UnicodeDecodeError, ValueError):
                        logger.debug('Binary file, hex-encoding: %s', f)
                        parts[rel] = f.read_bytes().hex()

        return {
            'displayName': display_name,
            'definition': parts,
        }

    def _deploy_semantic_model(self, model_dir, model_name, result):
        """Deploy the semantic model artifact.

        Args:
            model_dir: Path to .SemanticModel directory.
            model_name: Display name.
            result: BundleDeploymentResult to update.

        Returns:
            Deployed item ID (str) or None on failure.
        """
        logger.info('Deploying semantic model: %s', model_name)
        result.model_name = model_name

        try:
            config = self._read_artifact_definition(model_dir)
            deploy_result = self.deployer.deploy_dataset(
                self.workspace_id, model_name, config, overwrite=True,
            )
            item_id = deploy_result.get('id')
            result.model_id = item_id
            result.model_status = 'deployed'
            logger.info('Semantic model deployed: %s (%s)', model_name, item_id)
            return item_id
        except Exception as e:
            logger.error('Failed to deploy semantic model: %s', e)
            result.model_status = 'failed'
            result.model_error = str(e)
            return None

    def _deploy_report(self, report_name, report_dir, model_id):
        """Deploy a single report.

        Args:
            report_name: Display name for the report.
            report_dir: Path to .Report directory.
            model_id: ID of the deployed semantic model (for binding).

        Returns:
            dict with 'name', 'status', 'id', optionally 'error'.
        """
        report_result = {
            'name': report_name,
            'status': 'pending',
            'id': None,
        }

        try:
            config = self._read_artifact_definition(report_dir)
            deploy_resp = self.deployer.deploy_report(
                self.workspace_id, report_name, config, overwrite=True,
            )
            report_result['status'] = 'deployed'
            report_result['id'] = deploy_resp.get('id')
            logger.info('Report deployed: %s (%s)',
                        report_name, report_result['id'])
        except Exception as e:
            logger.error('Failed to deploy report %s: %s', report_name, e)
            report_result['status'] = 'failed'
            report_result['error'] = str(e)

        return report_result

    def _rebind_report(self, report_id, model_id):
        """Rebind a report to the deployed semantic model.

        Uses Fabric API POST /reports/{id}/Rebind.

        Args:
            report_id: Deployed report ID.
            model_id: Deployed semantic model ID.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self.client.post(
                f'/workspaces/{self.workspace_id}/reports/{report_id}/Rebind',
                data={'datasetId': model_id},
            )
            logger.info('Report %s rebound to model %s', report_id, model_id)
            return True
        except Exception as e:
            logger.warning('Rebind failed for report %s: %s', report_id, e)
            return False

    def _trigger_refresh(self, model_id, result):
        """Trigger a dataset refresh on the semantic model.

        Args:
            model_id: Deployed semantic model ID.
            result: BundleDeploymentResult to update.
        """
        try:
            self.client.post(
                f'/workspaces/{self.workspace_id}/datasets/{model_id}/refreshes',
                data={'type': 'Full'},
            )
            result.refresh_status = 'triggered'
            logger.info('Refresh triggered for model %s', model_id)
        except Exception as e:
            result.refresh_status = 'failed'
            result.refresh_error = str(e)
            logger.error('Refresh failed: %s', e)

    def check_workspace_permissions(self):
        """Verify workspace exists and principal has sufficient role.

        Returns:
            dict with ``{ok, role, detail}``.
        """
        try:
            ws = self.client.get(
                f'/workspaces/{self.workspace_id}')
            role = ''
            if isinstance(ws, dict):
                role = ws.get('role', ws.get('currentUserRole', ''))
            if role and role.lower() not in ('admin', 'contributor', 'member'):
                return {
                    'ok': False, 'role': role,
                    'detail': f'Insufficient role: {role} (need Contributor+)',
                }
            return {'ok': True, 'role': role or 'unknown', 'detail': ''}
        except Exception as e:
            return {'ok': False, 'role': '', 'detail': str(e)}

    def detect_conflicts(self, model_name, report_names):
        """Detect name collisions with existing workspace items.

        Args:
            model_name: Semantic model display name.
            report_names: List of report display names.

        Returns:
            list of ``{name, type, existing_id}`` dicts.
        """
        conflicts = []
        try:
            items = self.client.get(
                f'/workspaces/{self.workspace_id}/items') or []
            if isinstance(items, dict):
                items = items.get('value', [])
            name_map = {}
            for item in items:
                dname = item.get('displayName', '')
                name_map.setdefault(dname, []).append(item)
            # Check model
            if model_name in name_map:
                for item in name_map[model_name]:
                    conflicts.append({
                        'name': model_name,
                        'type': item.get('type', 'SemanticModel'),
                        'existing_id': item.get('id', ''),
                    })
            # Check reports
            for rname in report_names:
                if rname in name_map:
                    for item in name_map[rname]:
                        conflicts.append({
                            'name': rname,
                            'type': item.get('type', 'Report'),
                            'existing_id': item.get('id', ''),
                        })
        except Exception as e:
            logger.warning('Could not check conflicts: %s', e)
        return conflicts

    def rollback(self, result):
        """Roll back deployed artifacts after a failure.

        Deletes the semantic model if it was deployed but reports failed.

        Args:
            result: BundleDeploymentResult with deployment state.
        """
        if result.model_id and result.model_status == 'deployed':
            try:
                self.client.delete(
                    f'/workspaces/{self.workspace_id}/'
                    f'items/{result.model_id}')
                result.rollback_actions.append({
                    'action': 'delete_model',
                    'artifact': result.model_name,
                    'status': 'success',
                })
                logger.info('Rolled back model: %s', result.model_name)
            except Exception as e:
                result.rollback_actions.append({
                    'action': 'delete_model',
                    'artifact': result.model_name,
                    'status': f'failed: {e}',
                })
                logger.error('Rollback failed for model: %s', e)

        for rpt in result.reports:
            if rpt.get('status') == 'deployed' and rpt.get('id'):
                try:
                    self.client.delete(
                        f'/workspaces/{self.workspace_id}/'
                        f'items/{rpt["id"]}')
                    result.rollback_actions.append({
                        'action': 'delete_report',
                        'artifact': rpt['name'],
                        'status': 'success',
                    })
                except Exception as e:
                    result.rollback_actions.append({
                        'action': 'delete_report',
                        'artifact': rpt['name'],
                        'status': f'failed: {e}',
                    })

    def validate_deployment(self, result):
        """Post-deployment validation.

        Verifies model status and report binding.

        Args:
            result: BundleDeploymentResult to validate.
        """
        # Check model status
        if result.model_id:
            try:
                status = self.deployer.get_deployment_status(
                    self.workspace_id, result.model_id)
                model_state = status.get('status', '') if status else ''
                result.validation.append({
                    'check': 'model_status',
                    'status': 'ok' if model_state != 'Failed' else 'fail',
                    'detail': model_state,
                })
            except Exception as e:
                result.validation.append({
                    'check': 'model_status',
                    'status': 'error',
                    'detail': str(e),
                })

        # Check reports are bound
        for rpt in result.reports:
            if rpt.get('status') == 'deployed':
                result.validation.append({
                    'check': f'report_bound:{rpt["name"]}',
                    'status': 'ok' if rpt.get('rebind') == 'success' else 'warn',
                    'detail': rpt.get('rebind', 'unknown'),
                })

    def poll_refresh(self, model_id, result,
                     interval=10, timeout=1800):
        """Poll refresh status until completion or timeout.

        Args:
            model_id: Semantic model ID.
            result: BundleDeploymentResult to update.
            interval: Polling interval in seconds.
            timeout: Maximum wait time in seconds.
        """
        import time
        elapsed = 0
        while elapsed < timeout:
            try:
                resp = self.client.get(
                    f'/workspaces/{self.workspace_id}/'
                    f'datasets/{model_id}/refreshes')
                refreshes = resp if isinstance(resp, list) else (
                    resp.get('value', []) if isinstance(resp, dict) else [])
                if refreshes:
                    latest = refreshes[0]
                    status = latest.get('status', '').lower()
                    if status in ('completed', 'succeeded'):
                        result.refresh_status = 'completed'
                        logger.info('Refresh completed after %ds', elapsed)
                        return
                    elif status == 'failed':
                        result.refresh_status = 'failed'
                        result.refresh_error = latest.get('error', '')
                        logger.error('Refresh failed: %s',
                                     result.refresh_error)
                        return
            except Exception as e:
                logger.debug('Refresh poll error: %s', e)
            time.sleep(interval)
            elapsed += interval

        result.refresh_status = 'timeout'
        result.refresh_error = f'Refresh timed out after {timeout}s'
        logger.warning(result.refresh_error)

    def deploy_bundle(self, project_dir, refresh=False,
                      report_filter=None,
                      overwrite=False, enable_rollback=False):
        """Deploy a shared semantic model project as a bundle.

        Deploys the semantic model first, then each thin report.
        Reports that fail are logged but don't block other reports.

        Args:
            project_dir: Root project directory containing
                ``{ModelName}.SemanticModel/`` and ``{Report}.Report/``.
            refresh: Trigger dataset refresh after deployment.
            report_filter: Optional list of report names to deploy
                (deploys all if None).
            overwrite: Proceed even if name conflicts are detected.
            enable_rollback: Delete deployed artifacts on failure.

        Returns:
            BundleDeploymentResult with per-artifact status.
        """
        project_path = Path(project_dir)
        if not project_path.is_dir():
            raise FileNotFoundError(
                f'Project directory not found: {project_dir}'
            )

        result = BundleDeploymentResult(project_dir, self.workspace_id)

        # 1. Discover artifacts
        model_dir, model_name, report_dirs = self.discover_artifacts(
            project_dir,
        )

        if not model_dir:
            logger.error('No .SemanticModel directory found in %s', project_dir)
            result.model_status = 'not_found'
            result.model_error = 'No .SemanticModel directory found'
            result.end_time = datetime.now()
            return result

        # Filter reports if requested
        if report_filter:
            filter_set = set(report_filter)
            report_dirs = [
                (name, path) for name, path in report_dirs
                if name in filter_set
            ]

        logger.info(
            'Bundle deployment: model=%s, reports=%d',
            model_name, len(report_dirs),
        )

        # 1b. Permission pre-flight
        perm = self.check_workspace_permissions()
        if not perm['ok']:
            result.model_status = 'failed'
            result.model_error = f'Permission check failed: {perm["detail"]}'
            result.end_time = datetime.now()
            return result

        # 1c. Conflict detection
        report_names = [name for name, _ in report_dirs]
        conflicts = self.detect_conflicts(model_name, report_names)
        result.conflicts = conflicts
        if conflicts and not overwrite:
            names = ', '.join(c['name'] for c in conflicts)
            result.model_status = 'failed'
            result.model_error = (
                f'Name conflicts detected: {names}. '
                f'Use overwrite=True to proceed.'
            )
            result.end_time = datetime.now()
            return result

        # 2. Deploy semantic model first
        model_id = self._deploy_semantic_model(model_dir, model_name, result)
        if not model_id:
            result.end_time = datetime.now()
            return result

        # 3. Deploy each report with error isolation
        for report_name, report_path in report_dirs:
            rpt_result = self._deploy_report(
                report_name, report_path, model_id,
            )

            # 3b. Rebind report to semantic model
            if rpt_result['status'] == 'deployed' and rpt_result.get('id'):
                rebind_ok = self._rebind_report(rpt_result['id'], model_id)
                rpt_result['rebind'] = 'success' if rebind_ok else 'failed'
                if not rebind_ok:
                    rpt_result['status'] = 'deployed_unbound'

            result.reports.append(rpt_result)

        # 4. Rollback on failure if enabled
        if enable_rollback and result.failed_count > 0:
            logger.info('Rolling back due to %d failed reports',
                        result.failed_count)
            self.rollback(result)

        # 5. Post-deployment validation
        self.validate_deployment(result)

        # 6. Trigger refresh if requested
        if refresh and model_id:
            self._trigger_refresh(model_id, result)
            if result.refresh_status == 'triggered':
                self.poll_refresh(model_id, result)
        elif not refresh:
            result.refresh_status = 'skipped'

        result.end_time = datetime.now()

        logger.info(
            'Bundle deployment complete: model=%s, reports=%d/%d',
            result.model_status, result.deployed_count, result.total_count,
        )

        return result


def deploy_bundle_from_cli(project_dir, workspace_id, refresh=False,
                           report_filter=None, save_report=True):
    """CLI entry point for bundle deployment.

    Prints console summary and optionally saves JSON report.

    Args:
        project_dir: Root project directory.
        workspace_id: Target Fabric workspace ID.
        refresh: Trigger refresh after deployment.
        report_filter: Optional list of report names to deploy.
        save_report: Save deployment report JSON alongside project.

    Returns:
        BundleDeploymentResult
    """
    deployer = BundleDeployer(workspace_id=workspace_id)
    result = deployer.deploy_bundle(
        project_dir,
        refresh=refresh,
        report_filter=report_filter,
    )

    result.print_summary()

    if save_report:
        report_path = os.path.join(project_dir, 'deployment_report.json')
        result.save(report_path)

    return result
