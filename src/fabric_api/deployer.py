"""Fabric artifact deployment module."""
import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from .client import FabricClient
from .auth import FabricAuthenticator

logger = logging.getLogger(__name__)


class ArtifactType:
    """Supported Fabric artifact types."""
    DATASET = 'Dataset'
    DATAFLOW = 'Dataflow'
    REPORT = 'Report'
    NOTEBOOK = 'Notebook'
    LAKEHOUSE = 'Lakehouse'
    WAREHOUSE = 'Warehouse'
    PIPELINE = 'Pipeline'


class FabricDeployer:
    """Deploy Fabric artifacts to workspace."""

    def __init__(self, client: Optional[FabricClient] = None):
        """
        Initialize Fabric Deployer.

        Args:
            client: FabricClient instance (creates default if None)
        """
        self.client = client or FabricClient()

    def deploy_dataset(
        self,
        workspace_id: str,
        dataset_name: str,
        dataset_config: Dict[str, Any],
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy a dataset to workspace.

        Args:
            workspace_id: Target workspace ID
            dataset_name: Name of the dataset
            dataset_config: Dataset configuration
            overwrite: Overwrite existing dataset

        Returns:
            Deployment result
        """
        logger.info(f'Deploying dataset: {dataset_name}')
        
        # Check if dataset exists
        existing = self._find_item(workspace_id, dataset_name, ArtifactType.DATASET)
        
        if existing and overwrite:
            logger.info(f'Overwriting existing dataset: {existing["id"]}')
            result = self.client.put(
                f'/workspaces/{workspace_id}/items/{existing["id"]}',
                data=dataset_config
            )
        else:
            result = self.client.post(
                f'/workspaces/{workspace_id}/items',
                data={
                    'displayName': dataset_name,
                    'type': ArtifactType.DATASET,
                    'definition': dataset_config
                }
            )
        
        logger.info(f'Dataset deployed successfully: {result.get("id")}')
        return result

    def deploy_report(
        self,
        workspace_id: str,
        report_name: str,
        report_config: Dict[str, Any],
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy a report to workspace.

        Args:
            workspace_id: Target workspace ID
            report_name: Name of the report
            report_config: Report configuration
            overwrite: Overwrite existing report

        Returns:
            Deployment result
        """
        logger.info(f'Deploying report: {report_name}')
        
        existing = self._find_item(workspace_id, report_name, ArtifactType.REPORT)
        
        if existing and overwrite:
            logger.info(f'Overwriting existing report: {existing["id"]}')
            result = self.client.put(
                f'/workspaces/{workspace_id}/items/{existing["id"]}',
                data=report_config
            )
        else:
            result = self.client.post(
                f'/workspaces/{workspace_id}/items',
                data={
                    'displayName': report_name,
                    'type': ArtifactType.REPORT,
                    'definition': report_config
                }
            )
        
        logger.info(f'Report deployed successfully: {result.get("id")}')
        return result

    def deploy_from_file(
        self,
        workspace_id: str,
        artifact_path: Path,
        artifact_type: str,
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy artifact from JSON file.

        Args:
            workspace_id: Target workspace ID
            artifact_path: Path to artifact JSON file
            artifact_type: Type of artifact (Dataset, Report, etc.)
            overwrite: Overwrite existing artifact

        Returns:
            Deployment result
        """
        logger.info(f'Loading artifact from: {artifact_path}')
        
        with open(artifact_path, 'r') as f:
            config = json.load(f)
        
        artifact_name = config.get('displayName') or artifact_path.stem
        
        if artifact_type == ArtifactType.DATASET:
            return self.deploy_dataset(workspace_id, artifact_name, config, overwrite)
        elif artifact_type == ArtifactType.REPORT:
            return self.deploy_report(workspace_id, artifact_name, config, overwrite)
        else:
            logger.error(f'Unsupported artifact type: {artifact_type}')
            raise ValueError(f'Unsupported artifact type: {artifact_type}')

    def deploy_artifacts_batch(
        self,
        workspace_id: str,
        artifacts_dir: Path,
        overwrite: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Deploy multiple artifacts from directory.

        Args:
            workspace_id: Target workspace ID
            artifacts_dir: Directory containing artifact JSON files
            overwrite: Overwrite existing artifacts

        Returns:
            List of deployment results
        """
        results = []
        
        # Infer artifact type from file naming convention or metadata
        for artifact_file in artifacts_dir.glob('*.json'):
            try:
                logger.info(f'Processing artifact: {artifact_file.name}')
                
                with open(artifact_file, 'r') as f:
                    config = json.load(f)
                
                artifact_type = config.get('type', ArtifactType.DATASET)
                result = self.deploy_from_file(
                    workspace_id,
                    artifact_file,
                    artifact_type,
                    overwrite
                )
                results.append({'file': str(artifact_file), 'result': result})
            except Exception as e:
                logger.error(f'Failed to deploy {artifact_file.name}: {str(e)}')
                results.append({'file': str(artifact_file), 'error': str(e)})
        
        return results

    def _find_item(
        self,
        workspace_id: str,
        item_name: str,
        item_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find item by name and type in workspace.

        Args:
            workspace_id: Workspace ID
            item_name: Item name
            item_type: Item type

        Returns:
            Item details if found, None otherwise
        """
        try:
            items = self.client.list_items(workspace_id, item_type)
            
            for item in items.get('value', []):
                if item.get('displayName') == item_name:
                    return item
            
            return None
        except Exception as e:
            logger.warning(f'Failed to search for item: {str(e)}')
            return None

    def get_deployment_status(self, workspace_id: str, item_id: str) -> Dict[str, Any]:
        """
        Get deployment or operation status.

        Args:
            workspace_id: Workspace ID
            item_id: Item ID

        Returns:
            Status information
        """
        return self.client.get(f'/workspaces/{workspace_id}/items/{item_id}')
