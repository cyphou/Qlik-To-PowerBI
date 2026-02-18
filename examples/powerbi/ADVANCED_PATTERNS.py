"""
Advanced usage patterns and best practices for Fabric deployment.
"""

# Pattern 1: Custom Deployment with Progress Tracking
"""
from fabric_api import FabricDeployer
from fabric_api.utils import DeploymentReport, ArtifactCache
from pathlib import Path
import json

deployer = FabricDeployer()
report = DeploymentReport(workspace_id='your-workspace-id')
cache = ArtifactCache()

artifacts_dir = Path('artifacts')
for artifact_file in artifacts_dir.glob('*.json'):
    try:
        with open(artifact_file) as f:
            config = json.load(f)
        
        result = deployer.deploy_dataset(
            workspace_id='your-workspace-id',
            dataset_name=config['displayName'],
            dataset_config=config
        )
        
        report.add_result(
            artifact_name=artifact_file.name,
            artifact_type='Dataset',
            status='success',
            item_id=result.get('id')
        )
        
        cache.set(artifact_file.name, result)
        
    except Exception as e:
        report.add_result(
            artifact_name=artifact_file.name,
            artifact_type='Dataset',
            status='failed',
            error=str(e)
        )

report.print_summary()
report.save(Path('deployment_report.json'))
"""

# Pattern 2: Validation Before Deployment
"""
from fabric_api.validator import ArtifactValidator
from pathlib import Path

artifacts_dir = Path('artifacts')

# Validate all artifacts
results = ArtifactValidator.validate_directory(artifacts_dir)

# Check for errors
invalid = {f: e for f, (v, e) in results.items() if not v}
if invalid:
    print(f'Cannot deploy: {list(invalid.keys())} have errors')
    exit(1)

# Safe to deploy
print('All artifacts validated ✓')
"""

# Pattern 3: Environment-Specific Deployment
"""
from fabric_api import FabricDeployer
from fabric_api.config.environments import EnvironmentConfig, EnvironmentType
from fabric_api.config.settings import get_settings
settings = get_settings()

# Apply production config
EnvironmentConfig.apply_config(EnvironmentType.PRODUCTION)

deployer = FabricDeployer()
# Will use production settings (higher timeouts, more retries, etc)
"""

# Pattern 4: Batch Deployment with Error Recovery
"""
import sys
from pathlib import Path
from fabric_api import FabricDeployer

deployer = FabricDeployer()
failed_artifacts = []

for artifact_file in Path('artifacts').glob('*.json'):
    try:
        deployer.deploy_from_file(
            workspace_id='your-workspace-id',
            artifact_path=artifact_file,
            artifact_type='Dataset',
            overwrite=True
        )
        print(f'✓ {artifact_file.name}')
    except Exception as e:
        print(f'✗ {artifact_file.name}: {e}')
        failed_artifacts.append((artifact_file.name, e))

if failed_artifacts:
    print(f'\\nFailed to deploy {len(failed_artifacts)} artifacts')
    sys.exit(1)
else:
    print('\\n✓ All artifacts deployed successfully')
"""

# Pattern 5: CI/CD Integration
"""
import os
import sys
from pathlib import Path

# Get environment from CI/CD
workspace_id = os.getenv('FABRIC_WORKSPACE_ID')
if not workspace_id:
    print('Error: FABRIC_WORKSPACE_ID not set')
    sys.exit(1)

from fabric_api import FabricDeployer
from fabric_api.utils import DeploymentReport

deployer = FabricDeployer()
report = DeploymentReport(workspace_id)

# Deploy and track
results = deployer.deploy_artifacts_batch(
    workspace_id=workspace_id,
    artifacts_dir=Path('artifacts'),
    overwrite=True
)

# Generate report for CI/CD
report.save(Path('deployment_report.json'))

# Exit with status
success_count = sum(1 for r in results if 'error' not in r)
total = len(results)
print(f'Deployment: {success_count}/{total} successful')
sys.exit(0 if success_count == total else 1)
"""

# Pattern 6: Authentication with Managed Identity
"""
from fabric_api import FabricDeployer, FabricAuthenticator

# Use Managed Identity (for Azure-hosted deployments)
auth = FabricAuthenticator(use_managed_identity=True)
deployer = FabricDeployer(client=None)  # Will use managed identity automatically

# No secrets needed - identity comes from Azure resource
"""

# Pattern 7: Custom Retry Logic
"""
import time
from requests.exceptions import RequestException
from fabric_api import FabricDeployer

deployer = FabricDeployer()

def deploy_with_custom_retry(artifact_config, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            result = deployer.deploy_dataset(
                workspace_id='your-workspace-id',
                dataset_name=artifact_config['displayName'],
                dataset_config=artifact_config
            )
            print(f'Deployed successfully on attempt {attempt}')
            return result
        except RequestException as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f'Attempt {attempt} failed, retrying in {wait_time}s...')
                time.sleep(wait_time)
            else:
                print(f'Failed after {max_retries} attempts')
                raise
"""

# Pattern 8: Monitor Deployment Status
"""
from fabric_api import FabricClient

client = FabricClient()

# Poll status until deployment completes
def wait_for_deployment(workspace_id, item_id, timeout=600):
    import time
    start = time.time()
    
    while time.time() - start < timeout:
        status = client.get(f'/workspaces/{workspace_id}/items/{item_id}')
        
        state = status.get('state', 'Unknown')
        if state == 'Success':
            return True
        elif state == 'Failed':
            raise Exception(f'Deployment failed: {status}')
        
        time.sleep(5)
    
    raise TimeoutError(f'Deployment timed out after {timeout}s')

# Usage
success = wait_for_deployment('workspace-id', 'item-id')
print('✓ Deployment complete')
"""

print(__doc__)
