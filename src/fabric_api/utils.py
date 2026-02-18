"""Deployment utilities and helpers."""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DeploymentReport:
    """Generate deployment reports."""

    def __init__(self, workspace_id: str):
        """Initialize report."""
        self.workspace_id = workspace_id
        self.timestamp = datetime.now()
        self.results: List[Dict[str, Any]] = []

    def add_result(
        self,
        artifact_name: str,
        artifact_type: str,
        status: str,
        item_id: str = None,
        error: str = None
    ):
        """Add deployment result."""
        self.results.append({
            'timestamp': datetime.now().isoformat(),
            'artifact_name': artifact_name,
            'artifact_type': artifact_type,
            'status': status,
            'item_id': item_id,
            'error': error
        })

    def to_json(self) -> str:
        """Export as JSON."""
        return json.dumps({
            'workspace_id': self.workspace_id,
            'deployment_time': self.timestamp.isoformat(),
            'total_artifacts': len(self.results),
            'successful': sum(1 for r in self.results if r['status'] == 'success'),
            'failed': sum(1 for r in self.results if r['status'] == 'failed'),
            'results': self.results
        }, indent=2)

    def save(self, output_path: Path):
        """Save report to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(self.to_json())
        logger.info(f'Report saved: {output_path}')

    def print_summary(self):
        """Print summary to console."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r['status'] == 'success')
        failed = sum(1 for r in self.results if r['status'] == 'failed')

        print(f'\n=== Deployment Summary ===')
        print(f'Workspace: {self.workspace_id}')
        print(f'Time: {self.timestamp}')
        print(f'Total: {total} | Success: {successful} | Failed: {failed}')

        if failed > 0:
            print(f'\n=== Failed Artifacts ===')
            for result in self.results:
                if result['status'] == 'failed':
                    print(f"  ✗ {result['artifact_name']}: {result['error']}")


class ArtifactCache:
    """Simple cache for artifact metadata."""

    def __init__(self, cache_file: Path = None):
        """Initialize cache."""
        self.cache_file = cache_file or Path('.fabric_cache')
        self.cache: Dict[str, Dict] = {}
        self.load()

    def load(self):
        """Load cache from file."""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                self.cache = json.load(f)

    def save(self):
        """Save cache to file."""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2, default=str)

    def get(self, key: str) -> Dict:
        """Get cached item."""
        return self.cache.get(key)

    def set(self, key: str, value: Dict):
        """Set cached item."""
        self.cache[key] = value
        self.save()

    def clear(self):
        """Clear cache."""
        self.cache = {}
        self.save()
