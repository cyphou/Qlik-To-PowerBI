"""
Power BI Service Workspace Deployer.

Orchestrates the deployment of migrated .pbip projects to a
Power BI Service workspace:

  1. Package .pbip → .pbix (via PBIXPackager)
  2. Upload .pbix to workspace (via PBIServiceClient)
  3. Wait for import completion
  4. Optionally trigger dataset refresh
  5. Check deployment status

Usage:
    deployer = PBIWorkspaceDeployer(workspace_id='...')
    result = deployer.deploy_project('/path/to/project_dir')
"""

import logging
import os
import time
import tempfile

logger = logging.getLogger(__name__)


class DeploymentResult:
    """Result of a single project deployment."""

    def __init__(self, project_name, status='pending', import_id=None,
                 dataset_id=None, report_id=None, error=None):
        self.project_name = project_name
        self.status = status  # 'pending', 'publishing', 'succeeded', 'failed'
        self.import_id = import_id
        self.dataset_id = dataset_id
        self.report_id = report_id
        self.error = error

    def to_dict(self):
        return {
            'project_name': self.project_name,
            'status': self.status,
            'import_id': self.import_id,
            'dataset_id': self.dataset_id,
            'report_id': self.report_id,
            'error': self.error,
        }


class PBIWorkspaceDeployer:
    """Deploy .pbip projects to a Power BI Service workspace."""

    def __init__(self, workspace_id, client=None, tenant_id=None,
                 client_id=None, client_secret=None,
                 use_managed_identity=False):
        """Initialize deployer.

        Args:
            workspace_id: Target Power BI workspace/group ID.
            client: Pre-configured PBIServiceClient (optional).
            tenant_id: Azure AD tenant ID (if no client).
            client_id: Azure AD app ID (if no client).
            client_secret: Client secret (if no client).
            use_managed_identity: Use managed identity (if no client).
        """
        self.workspace_id = workspace_id

        if client:
            self.client = client
        else:
            from .pbi_client import PBIServiceClient
            self.client = PBIServiceClient(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                use_managed_identity=use_managed_identity,
            )

    def deploy_project(self, project_dir, dataset_name=None,
                       overwrite=True, refresh=False,
                       max_wait_seconds=300, poll_interval=5):
        """Deploy a .pbip project to the workspace.

        Args:
            project_dir: Path to .pbip project directory.
            dataset_name: Override dataset name (defaults to project name).
            overwrite: Overwrite existing dataset/report if found.
            refresh: Trigger dataset refresh after successful import.
            max_wait_seconds: Maximum time to wait for import completion.
            poll_interval: Polling interval in seconds.

        Returns:
            DeploymentResult: Outcome of the deployment.
        """
        from .pbix_packager import PBIXPackager

        project_dir = os.path.abspath(project_dir)
        project_name = dataset_name or os.path.basename(project_dir)
        result = DeploymentResult(project_name=project_name)

        # Step 1: Package .pbip → .pbix
        try:
            packager = PBIXPackager()
            pbix_path = os.path.join(
                tempfile.gettempdir(), f'{project_name}.pbix'
            )
            packager.package(project_dir, pbix_path)
            logger.info(f'Packaged {project_dir} → {pbix_path}')
        except Exception as e:
            result.status = 'failed'
            result.error = f'Packaging failed: {e}'
            logger.error(result.error)
            return result

        # Step 2: Upload .pbix to workspace
        try:
            import_resp = self.client.import_pbix(
                workspace_id=self.workspace_id,
                pbix_path=pbix_path,
                dataset_name=project_name,
                overwrite=overwrite,
            )
            result.import_id = import_resp.get('id')
            result.status = 'publishing'
            logger.info(f'Import started: id={result.import_id}')
        except Exception as e:
            result.status = 'failed'
            result.error = f'Upload failed: {e}'
            logger.error(result.error)
            return result
        finally:
            # Clean up temp .pbix
            try:
                os.remove(pbix_path)
            except OSError:
                pass

        # Step 3: Wait for import to complete
        if result.import_id:
            result = self._wait_for_import(result, max_wait_seconds, poll_interval)

        # Step 4: Trigger refresh if requested
        if refresh and result.status == 'succeeded' and result.dataset_id:
            try:
                self.client.refresh_dataset(self.workspace_id, result.dataset_id)
                logger.info(f'Refresh triggered for dataset {result.dataset_id}')
            except Exception as e:
                logger.warning(f'Refresh failed (non-fatal): {e}')

        return result

    def _wait_for_import(self, result, max_wait_seconds, poll_interval):
        """Poll import status until complete or timeout.

        Args:
            result: DeploymentResult with import_id set.
            max_wait_seconds: Maximum wait time.
            poll_interval: Seconds between polls.

        Returns:
            DeploymentResult: Updated with final status.
        """
        elapsed = 0
        while elapsed < max_wait_seconds:
            try:
                status = self.client.get_import_status(
                    self.workspace_id, result.import_id
                )
                state = status.get('importState', '')
                logger.debug(f'Import state: {state} ({elapsed}s)')

                if state == 'Succeeded':
                    result.status = 'succeeded'
                    # Extract dataset and report IDs
                    datasets = status.get('datasets', [])
                    if datasets:
                        result.dataset_id = datasets[0].get('id')
                    reports = status.get('reports', [])
                    if reports:
                        result.report_id = reports[0].get('id')
                    logger.info(
                        f'Import succeeded: dataset={result.dataset_id}, '
                        f'report={result.report_id}'
                    )
                    return result

                elif state == 'Failed':
                    result.status = 'failed'
                    result.error = status.get('error', {}).get(
                        'message', 'Import failed — no details'
                    )
                    logger.error(f'Import failed: {result.error}')
                    return result

            except Exception as e:
                logger.warning(f'Status check error: {e}')

            time.sleep(poll_interval)
            elapsed += poll_interval

        result.status = 'failed'
        result.error = f'Import timed out after {max_wait_seconds}s'
        logger.error(result.error)
        return result

    def deploy_batch(self, projects_dir, overwrite=True, refresh=False):
        """Deploy all .pbip projects under a directory.

        Args:
            projects_dir: Root directory containing .pbip project folders.
            overwrite: Overwrite existing items.
            refresh: Trigger refresh after each import.

        Returns:
            list[DeploymentResult]: Results for each project.
        """
        from .pbix_packager import PBIXPackager

        packager = PBIXPackager()
        project_dirs = packager.find_pbip_projects(projects_dir)

        if not project_dirs:
            logger.warning(f'No .pbip projects found under {projects_dir}')
            return []

        logger.info(f'Found {len(project_dirs)} projects to deploy')
        results = []
        for pdir in project_dirs:
            result = self.deploy_project(
                pdir, overwrite=overwrite, refresh=refresh
            )
            results.append(result)

        succeeded = sum(1 for r in results if r.status == 'succeeded')
        failed = sum(1 for r in results if r.status == 'failed')
        logger.info(f'Batch deploy: {succeeded} succeeded, {failed} failed')
        return results

    def validate_deployment(self, dataset_id):
        """Post-deployment validation — check dataset loads and report renders.

        Args:
            dataset_id: Dataset ID in the workspace.

        Returns:
            dict: Validation result with status and details.
        """
        validation = {'dataset_id': dataset_id, 'checks': []}

        # Check 1: Dataset exists and is queryable
        try:
            datasets = self.client.list_datasets(self.workspace_id)
            found = any(d.get('id') == dataset_id for d in datasets)
            validation['checks'].append({
                'check': 'dataset_exists',
                'passed': found,
            })
        except Exception as e:
            logger.debug('Dataset existence check failed: %s', e)
            validation['checks'].append({
                'check': 'dataset_exists',
                'passed': False,
                'error': str(e),
            })

        # Check 2: Refresh history (latest refresh status)
        try:
            history = self.client.get_refresh_history(
                self.workspace_id, dataset_id
            )
            if history:
                latest = history[0]
                status = latest.get('status', 'Unknown')
                validation['checks'].append({
                    'check': 'latest_refresh',
                    'passed': status == 'Completed',
                    'status': status,
                })
            else:
                validation['checks'].append({
                    'check': 'latest_refresh',
                    'passed': True,
                    'status': 'NoRefreshHistory',
                })
        except Exception as e:
            logger.debug('Refresh history check failed: %s', e)
            validation['checks'].append({
                'check': 'latest_refresh',
                'passed': False,
                'error': str(e),
            })

        all_passed = all(c['passed'] for c in validation['checks'])
        validation['overall'] = 'passed' if all_passed else 'failed'
        return validation

    def deploy_refresh_schedule(self, dataset_id, refresh_config):
        """Deploy a refresh schedule to a PBI dataset.

        Uses the Power BI REST API to configure scheduled refresh.

        Args:
            dataset_id: Dataset ID in the workspace.
            refresh_config: dict from refresh_generator.generate_refresh_config()
                with keys: enabled, frequency, times, days, localTimeZoneId, notifyOption.

        Returns:
            dict: {status, dataset_id, notes}.
        """
        if not refresh_config or not refresh_config.get('enabled'):
            logger.info('Refresh schedule not enabled — skipping.')
            return {
                'status': 'skipped',
                'dataset_id': dataset_id,
                'notes': refresh_config.get('notes', []),
            }

        # Build PBI refresh schedule payload
        schedule = {
            'value': {
                'enabled': True,
                'notifyOption': refresh_config.get(
                    'notifyOption', 'MailOnFailure'
                ),
                'localTimeZoneId': refresh_config.get(
                    'localTimeZoneId', 'UTC'
                ),
                'times': refresh_config.get('times', ['06:00']),
            }
        }
        if refresh_config.get('days'):
            schedule['value']['days'] = refresh_config['days']

        try:
            url = (
                f'groups/{self.workspace_id}/datasets/{dataset_id}'
                f'/refreshSchedule'
            )
            from .pbi_client import PBI_API_BASE
            self.client._request('PATCH', f'{PBI_API_BASE}/{url}', data=schedule)
            logger.info(
                'Refresh schedule deployed for dataset %s', dataset_id
            )
            return {
                'status': 'succeeded',
                'dataset_id': dataset_id,
                'notes': refresh_config.get('notes', []),
            }
        except Exception as e:
            logger.error('Failed to deploy refresh schedule: %s', e)
            return {
                'status': 'failed',
                'dataset_id': dataset_id,
                'error': str(e),
                'notes': refresh_config.get('notes', []),
            }

    # ── Sprint 89: Sync deployment ─────────────────────────────────────────

    def deploy_sync(self, project_dir, previous_dir=None, refresh=False):
        """Incremental sync deployment: detect changes, deploy only if modified.

        Args:
            project_dir: Path to the new .pbip project.
            previous_dir: Path to the previously deployed project (for diff).
            refresh: Whether to trigger a refresh after deploy.

        Returns:
            dict with sync result: {status, changes, deployment}.
        """
        from powerbi_import.incremental import IncrementalDiffGenerator

        result = {'status': 'no_changes', 'changes': None, 'deployment': None}

        if previous_dir and os.path.isdir(previous_dir):
            diff = IncrementalDiffGenerator.generate_incremental_update(
                previous_dir, project_dir
            )
            result['changes'] = diff
            if not diff.get('has_changes'):
                logger.info('No changes detected — skipping deployment.')
                return result
        else:
            logger.info('No previous project for diff — full deployment.')

        deploy_result = self.deploy_project(
            project_dir, overwrite=True, refresh=refresh
        )
        result['status'] = deploy_result.status
        result['deployment'] = deploy_result
        return result

    # ── Sprint 100: Rolling deployment ──────────────────────────────────────

    def deploy_rolling(self, project_dir, dataset_name=None,
                       max_wait_seconds=300, poll_interval=5):
        """Blue/green rolling deployment with automatic rollback.

        Strategy:
          1. Deploy the new dataset (canary) alongside the existing one.
          2. Trigger a refresh on the new dataset.
          3. Validate the refresh succeeded.
          4. If validation passes → overwrite the production dataset.
          5. If validation fails → roll back (remove canary, keep existing).

        Args:
            project_dir: Path to .pbip project directory.
            dataset_name: Target dataset name (defaults to project folder name).
            max_wait_seconds: Max time to wait for import + refresh.
            poll_interval: Seconds between status polls.

        Returns:
            dict: {status, phase, canary_id, production_id, error, validation}.
        """
        project_dir = os.path.abspath(project_dir)
        name = dataset_name or os.path.basename(project_dir)
        canary_name = f"{name}__canary"

        result = {
            'status': 'pending',
            'phase': 'init',
            'canary_id': None,
            'production_id': None,
            'error': None,
            'validation': None,
            'rolled_back': False,
        }

        # Phase 1: Deploy canary (new version) without overwriting production
        result['phase'] = 'canary_deploy'
        logger.info("Rolling deploy phase 1: deploying canary '%s'", canary_name)
        canary_result = self.deploy_project(
            project_dir,
            dataset_name=canary_name,
            overwrite=True,
            refresh=False,
            max_wait_seconds=max_wait_seconds,
            poll_interval=poll_interval,
        )

        if canary_result.status != 'succeeded':
            result['status'] = 'failed'
            result['error'] = f"Canary deploy failed: {canary_result.error}"
            logger.error(result['error'])
            return result

        result['canary_id'] = canary_result.dataset_id

        # Phase 2: Trigger refresh on canary
        result['phase'] = 'canary_refresh'
        logger.info("Rolling deploy phase 2: refreshing canary dataset %s",
                     canary_result.dataset_id)
        try:
            self.client.refresh_dataset(
                self.workspace_id, canary_result.dataset_id
            )
            # Wait for refresh to complete
            refresh_ok = self._wait_for_refresh(
                canary_result.dataset_id,
                max_wait_seconds=max_wait_seconds,
                poll_interval=poll_interval,
            )
        except Exception as e:
            refresh_ok = False
            logger.warning("Canary refresh error: %s", e)

        # Phase 3: Validate
        result['phase'] = 'validation'
        validation = self.validate_deployment(canary_result.dataset_id)
        result['validation'] = validation

        if not refresh_ok or validation.get('overall') != 'passed':
            # Rollback: remove canary
            result['phase'] = 'rollback'
            result['status'] = 'rolled_back'
            result['rolled_back'] = True
            result['error'] = "Canary validation failed — rolling back"
            logger.warning(result['error'])
            self._cleanup_dataset(canary_result.dataset_id, canary_name)
            return result

        # Phase 4: Promote canary → production (overwrite the real name)
        result['phase'] = 'promote'
        logger.info("Rolling deploy phase 4: promoting canary to '%s'", name)
        prod_result = self.deploy_project(
            project_dir,
            dataset_name=name,
            overwrite=True,
            refresh=True,
            max_wait_seconds=max_wait_seconds,
            poll_interval=poll_interval,
        )

        if prod_result.status == 'succeeded':
            result['status'] = 'succeeded'
            result['production_id'] = prod_result.dataset_id
            result['phase'] = 'complete'
            # Remove canary
            self._cleanup_dataset(canary_result.dataset_id, canary_name)
            logger.info("Rolling deploy succeeded: production=%s",
                        prod_result.dataset_id)
        else:
            result['status'] = 'failed'
            result['error'] = f"Production deploy failed: {prod_result.error}"
            result['phase'] = 'promote_failed'
            logger.error(result['error'])

        return result

    def _wait_for_refresh(self, dataset_id, max_wait_seconds=300,
                          poll_interval=10):
        """Wait for the latest dataset refresh to complete.

        Returns:
            True if refresh completed successfully, False otherwise.
        """
        elapsed = 0
        while elapsed < max_wait_seconds:
            try:
                history = self.client.get_refresh_history(
                    self.workspace_id, dataset_id
                )
                if history:
                    latest = history[0]
                    status = latest.get('status', '')
                    if status == 'Completed':
                        return True
                    elif status == 'Failed':
                        logger.warning("Refresh failed for dataset %s",
                                       dataset_id)
                        return False
            except Exception as e:
                logger.debug("Refresh status check error: %s", e)
            time.sleep(poll_interval)
            elapsed += poll_interval

        logger.warning("Refresh timed out after %ds for dataset %s",
                       max_wait_seconds, dataset_id)
        return False

    def _cleanup_dataset(self, dataset_id, dataset_name):
        """Best-effort removal of a dataset (canary cleanup)."""
        try:
            self.client.delete_dataset(self.workspace_id, dataset_id)
            logger.info("Cleaned up dataset '%s' (%s)", dataset_name,
                        dataset_id)
        except Exception as e:
            logger.debug("Could not remove dataset '%s': %s",
                         dataset_name, e)
