"""Quick start examples for Fabric deployment."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from fabric_api import FabricClient, FabricDeployer, FabricAuthenticator


def example_1_list_workspaces():
    """Example: List all accessible workspaces."""
    print("\n=== Example 1: List Workspaces ===")
    
    client = FabricClient()
    workspaces = client.list_workspaces()
    
    print(f"Found {len(workspaces.get('value', []))} workspace(s):")
    for ws in workspaces.get('value', []):
        print(f"  - {ws['displayName']} (ID: {ws['id']})")


def example_2_deploy_single_dataset():
    """Example: Deploy a single dataset."""
    print("\n=== Example 2: Deploy Single Dataset ===")
    
    deployer = FabricDeployer()
    
    dataset_config = {
        "displayName": "Sales Data",
        "type": "Dataset",
        "definition": {
            "tables": [
                {
                    "name": "DimCustomer",
                    "columns": [
                        {"name": "CustomerID", "dataType": "Int64"},
                        {"name": "CustomerName", "dataType": "String"},
                        {"name": "Country", "dataType": "String"}
                    ]
                }
            ]
        }
    }
    
    result = deployer.deploy_dataset(
        workspace_id='your-workspace-id',
        dataset_name='Sales Data',
        dataset_config=dataset_config,
        overwrite=True
    )
    
    print(f"Dataset deployed: {result.get('id')}")


def example_3_batch_deploy_artifacts():
    """Example: Deploy all artifacts from directory."""
    print("\n=== Example 3: Batch Deploy Artifacts ===")
    
    deployer = FabricDeployer()
    artifacts_dir = Path(__file__).parent.parent / 'artifacts'
    
    results = deployer.deploy_artifacts_batch(
        workspace_id='your-workspace-id',
        artifacts_dir=artifacts_dir,
        overwrite=True
    )
    
    for result in results:
        if 'error' in result:
            print(f"❌ {result['file']}: {result['error']}")
        else:
            print(f"✓ {result['file']}: Deployed")


def example_4_list_workspace_items():
    """Example: List items in a workspace."""
    print("\n=== Example 4: List Workspace Items ===")
    
    client = FabricClient()
    
    # List all items
    all_items = client.list_items(workspace_id='your-workspace-id')
    print(f"\nAll items: {len(all_items.get('value', []))}")
    
    # List datasets only
    datasets = client.list_items(
        workspace_id='your-workspace-id',
        item_type='Dataset'
    )
    print(f"Datasets: {len(datasets.get('value', []))}")
    
    for dataset in datasets.get('value', []):
        print(f"  - {dataset['displayName']}")


def example_5_custom_authentication():
    """Example: Custom authentication setup."""
    print("\n=== Example 5: Custom Authentication ===")
    
    # Create custom authenticator
    auth = FabricAuthenticator(use_managed_identity=False)
    
    # Get headers for API calls
    headers = auth.get_headers()
    print(f"Auth headers configured: {list(headers.keys())}")
    
    # Create client with custom auth
    client = FabricClient(authenticator=auth)
    workspaces = client.list_workspaces()
    print(f"Successfully connected! Found {len(workspaces)} workspaces")


if __name__ == '__main__':
    print("Fabric Deployment Examples")
    print("=" * 50)
    
    # Uncomment the examples you want to run
    # example_1_list_workspaces()
    # example_2_deploy_single_dataset()
    # example_3_batch_deploy_artifacts()
    # example_4_list_workspace_items()
    # example_5_custom_authentication()
    
    print("\nNote: Update workspace IDs and credentials in .env before running")
    print("Then uncomment the example functions to run them")
