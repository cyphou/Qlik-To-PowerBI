"""
Multi-Tenant Deployment — deploy a shared semantic model to N workspaces
with per-tenant connection string overrides and RLS role mappings.

Usage (CLI)::

    python migrate.py --shared-model wb1.twbx wb2.twbx \\
        --multi-tenant tenants.json --deploy-bundle WORKSPACE_ID

Usage (programmatic)::

    from powerbi_import.deploy.multi_tenant import (
        MultiTenantConfig, deploy_multi_tenant,
    )

    config = MultiTenantConfig.load("tenants.json")
    results = deploy_multi_tenant(model_dir, config)

Config file format::

    {
        "tenants": [
            {
                "name": "Contoso",
                "workspace_id": "aaaa-bbbb-cccc",
                "connection_overrides": {
                    "${TENANT_SERVER}": "contoso-sql.database.windows.net",
                    "${TENANT_DATABASE}": "contoso_sales"
                },
                "rls_mappings": {
                    "RegionManager": ["user1@contoso.com", "user2@contoso.com"]
                }
            }
        ]
    }
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TenantConfig:
    """Configuration for a single tenant deployment."""
    name: str
    workspace_id: str
    connection_overrides: Dict[str, str] = field(default_factory=dict)
    rls_mappings: Dict[str, List[str]] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Return validation errors (empty list if valid)."""
        errors = []
        if not self.name:
            errors.append("Tenant name is required")
        if not self.workspace_id:
            errors.append(f"Tenant '{self.name}': workspace_id is required")
        if not re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            self.workspace_id, re.IGNORECASE,
        ):
            errors.append(
                f"Tenant '{self.name}': workspace_id '{self.workspace_id}' "
                "is not a valid GUID"
            )
        return errors


@dataclass
class MultiTenantConfig:
    """Multi-tenant deployment configuration."""
    tenants: List[TenantConfig] = field(default_factory=list)

    def validate(self) -> List[str]:
        """Return all validation errors across tenants."""
        errors = []
        if not self.tenants:
            errors.append("No tenants configured")
            return errors
        seen_names = set()
        seen_workspaces = set()
        for tenant in self.tenants:
            errors.extend(tenant.validate())
            if tenant.name in seen_names:
                errors.append(f"Duplicate tenant name: '{tenant.name}'")
            seen_names.add(tenant.name)
            if tenant.workspace_id in seen_workspaces:
                errors.append(
                    f"Duplicate workspace_id: '{tenant.workspace_id}' "
                    f"(tenant '{tenant.name}')"
                )
            seen_workspaces.add(tenant.workspace_id)
        return errors

    @staticmethod
    def load(path: str) -> 'MultiTenantConfig':
        """Load configuration from a JSON file with validation."""
        resolved = os.path.realpath(path)
        if not os.path.exists(resolved):
            raise FileNotFoundError(f"Config file not found: {resolved}")

        with open(resolved, 'r', encoding='utf-8') as f:
            raw = f.read()

        # Size limit: reject unreasonably large config files (>1 MB)
        if len(raw) > 1_048_576:
            raise ValueError("Config file exceeds 1 MB size limit")

        data = json.loads(raw)

        # Validate structure
        if not isinstance(data, dict):
            raise ValueError("Config must be a JSON object with a 'tenants' array")
        if 'tenants' not in data:
            raise ValueError("Config must contain a 'tenants' key")
        if not isinstance(data['tenants'], list):
            raise ValueError("'tenants' must be a JSON array")

        tenants = []
        for t in data['tenants']:
            if not isinstance(t, dict):
                raise ValueError("Each tenant must be a JSON object")
            tenants.append(TenantConfig(
                name=t.get('name', ''),
                workspace_id=t.get('workspace_id', ''),
                connection_overrides=t.get('connection_overrides', {}),
                rls_mappings=t.get('rls_mappings', {}),
            ))
        return MultiTenantConfig(tenants=tenants)

    def save(self, path: str):
        """Save configuration to a JSON file."""
        data = {
            'tenants': [
                {
                    'name': t.name,
                    'workspace_id': t.workspace_id,
                    'connection_overrides': t.connection_overrides,
                    'rls_mappings': t.rls_mappings,
                }
                for t in self.tenants
            ]
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


def _apply_connection_overrides(model_dir: str, overrides: Dict[str, str],
                                output_dir: str):
    """Copy model_dir to output_dir with template substitution in M partitions.

    Replaces ``${TENANT_SERVER}``, ``${TENANT_DATABASE}``, etc. in all ``.tmdl``
    and ``.m`` files.

    Security: Only recognized ``${...}`` placeholders are substituted.
    Replacement values are validated to prevent injection.
    """
    import shutil

    if os.path.abspath(model_dir) != os.path.abspath(output_dir):
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        shutil.copytree(model_dir, output_dir)

    if not overrides:
        return

    # Security: validate placeholder names follow expected pattern
    _PLACEHOLDER_RE = re.compile(r'^\$\{[A-Z_][A-Z0-9_]*\}$')
    for placeholder, value in overrides.items():
        if not _PLACEHOLDER_RE.match(placeholder):
            logger.warning(
                "Skipping invalid placeholder '%s' — must match ${UPPER_NAME}",
                placeholder,
            )
            continue
        # Block null bytes and control characters in values
        if '\x00' in value or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
            raise ValueError(
                f"Override value for '{placeholder}' contains "
                "null bytes or control characters"
            )

    # Walk all text files and apply substitution
    for root, _dirs, files in os.walk(output_dir):
        for fname in files:
            if not fname.endswith(('.tmdl', '.m', '.json', '.pbir')):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except (UnicodeDecodeError, OSError):
                continue

            original = content
            for placeholder, value in overrides.items():
                if not _PLACEHOLDER_RE.match(placeholder):
                    continue
                # Context-aware escaping based on file type
                if fname.endswith('.json'):
                    safe_value = value.replace('\\', '\\\\').replace('"', '\\"')
                elif fname.endswith('.m'):
                    safe_value = value.replace('"', '""')
                elif fname.endswith('.tmdl'):
                    safe_value = value.replace("'", "''")
                else:
                    safe_value = value
                content = content.replace(placeholder, safe_value)

            if content != original:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.debug(
                    "Applied %d overrides in %s",
                    sum(1 for p in overrides if p in original),
                    fpath,
                )


@dataclass
class TenantDeploymentResult:
    """Result of deploying to a single tenant."""
    tenant_name: str
    workspace_id: str
    success: bool = False
    model_id: str = ''
    report_count: int = 0
    error: str = ''

    def to_dict(self) -> dict:
        return {
            'tenant_name': self.tenant_name,
            'workspace_id': self.workspace_id,
            'success': self.success,
            'model_id': self.model_id,
            'report_count': self.report_count,
            'error': self.error,
        }


@dataclass
class MultiTenantDeploymentResult:
    """Aggregate result across all tenants."""
    results: List[TenantDeploymentResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def total_count(self) -> int:
        return len(self.results)

    def to_dict(self) -> dict:
        return {
            'total': self.total_count,
            'succeeded': self.success_count,
            'failed': self.failed_count,
            'tenants': [r.to_dict() for r in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def save(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    def print_summary(self):
        print(f"\n  Multi-Tenant Deployment: {self.success_count}/{self.total_count} succeeded")
        for r in self.results:
            status = "OK" if r.success else f"FAILED ({r.error})"
            print(f"    {r.tenant_name}: {status}")


def deploy_multi_tenant(
    model_dir: str,
    config: MultiTenantConfig,
    refresh: bool = False,
    overwrite: bool = False,
) -> MultiTenantDeploymentResult:
    """Deploy a shared semantic model to multiple tenant workspaces.

    For each tenant:
        1. Copy model to a temp directory
        2. Apply connection string overrides (template substitution)
        3. Deploy via BundleDeployer to the tenant's workspace
        4. Record result

    Args:
        model_dir: Path to the shared model output directory.
        config: Multi-tenant configuration.
        refresh: Whether to trigger a refresh after deployment.
        overwrite: Whether to overwrite existing artifacts.

    Returns:
        Aggregate deployment result.
    """
    import tempfile
    import shutil

    # Validate config first
    errors = config.validate()
    if errors:
        result = MultiTenantDeploymentResult()
        for err in errors:
            logger.error("Config validation: %s", err)
        return result

    aggregate = MultiTenantDeploymentResult()

    for tenant in config.tenants:
        tenant_result = TenantDeploymentResult(
            tenant_name=tenant.name,
            workspace_id=tenant.workspace_id,
        )

        temp_dir = None
        try:
            # Create tenant-specific copy with overrides
            temp_dir = tempfile.mkdtemp(prefix=f'tenant_{tenant.name}_')
            tenant_model_dir = os.path.join(temp_dir, os.path.basename(model_dir))
            _apply_connection_overrides(model_dir, tenant.connection_overrides,
                                        tenant_model_dir)

            # Deploy
            try:
                from .bundle_deployer import BundleDeployer
            except ImportError:
                from powerbi_import.deploy.bundle_deployer import BundleDeployer

            deployer = BundleDeployer(workspace_id=tenant.workspace_id)
            bundle_result = deployer.deploy_bundle(
                project_dir=tenant_model_dir,
                refresh=refresh,
                overwrite=overwrite,
            )

            tenant_result.success = bundle_result.success
            tenant_result.model_id = bundle_result.model_id or ''
            tenant_result.report_count = bundle_result.deployed_count

            if not bundle_result.success:
                tenant_result.error = bundle_result.model_error or 'Deployment failed'

            logger.info(
                "Tenant '%s': %s (model=%s, reports=%d)",
                tenant.name,
                'OK' if tenant_result.success else 'FAILED',
                tenant_result.model_id,
                tenant_result.report_count,
            )

        except Exception as e:
            tenant_result.error = str(e)
            logger.error("Tenant '%s' deployment failed: %s", tenant.name, e)

        finally:
            # Clean up temp dir
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

        aggregate.results.append(tenant_result)

    return aggregate
