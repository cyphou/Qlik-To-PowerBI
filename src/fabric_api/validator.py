"""Artifact validator module."""
import json
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class ArtifactValidator:
    """Validate Fabric artifact definitions."""

    REQUIRED_DATASET_FIELDS = {'displayName', 'type', 'definition'}
    REQUIRED_REPORT_FIELDS = {'displayName', 'type', 'definition'}
    
    VALID_ARTIFACT_TYPES = {
        'Dataset',
        'Dataflow',
        'Report',
        'Notebook',
        'Lakehouse',
        'Warehouse',
        'Pipeline'
    }

    @staticmethod
    def validate_artifact(artifact_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate an artifact JSON file.

        Args:
            artifact_path: Path to artifact JSON file

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        try:
            # Check file exists
            if not artifact_path.exists():
                return False, [f'File not found: {artifact_path}']

            # Load JSON
            with open(artifact_path, 'r') as f:
                artifact = json.load(f)

            # Validate structure
            if not isinstance(artifact, dict):
                errors.append('Artifact must be a JSON object')

            # Validate required fields
            artifact_type = artifact.get('type')
            if not artifact_type:
                errors.append('Missing required field: type')
            elif artifact_type not in ArtifactValidator.VALID_ARTIFACT_TYPES:
                errors.append(f'Invalid artifact type: {artifact_type}')

            if not artifact.get('displayName'):
                errors.append('Missing required field: displayName')

            if not artifact.get('definition'):
                errors.append('Missing required field: definition')

            return len(errors) == 0, errors

        except json.JSONDecodeError as e:
            return False, [f'Invalid JSON: {str(e)}']
        except Exception as e:
            return False, [f'Validation error: {str(e)}']

    @staticmethod
    def validate_directory(artifacts_dir: Path) -> Dict[str, Tuple[bool, List[str]]]:
        """
        Validate all artifacts in directory.

        Args:
            artifacts_dir: Directory containing artifact JSON files

        Returns:
            Dictionary mapping file names to validation results
        """
        results = {}

        for artifact_file in artifacts_dir.glob('*.json'):
            is_valid, errors = ArtifactValidator.validate_artifact(artifact_file)
            results[artifact_file.name] = (is_valid, errors)

            status = '✓' if is_valid else '✗'
            logger.info(f'{status} {artifact_file.name}')

            if errors:
                for error in errors:
                    logger.warning(f'  - {error}')

        return results
