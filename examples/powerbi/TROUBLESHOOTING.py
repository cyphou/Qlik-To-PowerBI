"""
Deployment troubleshooting guide.

Common issues and solutions:
"""

# Issue 1: Authentication Errors
"""
Error: Failed to acquire access token
Solution:
1. Verify FABRIC_TENANT_ID, FABRIC_CLIENT_ID, FABRIC_CLIENT_SECRET in .env
2. Ensure service principal has necessary permissions
3. Check if service principal is in the correct tenant
4. Validate credentials with Azure CLI:
   az login --service-principal -u <client-id> -p <client-secret> --tenant <tenant-id>
"""

# Issue 2: Workspace Not Found
"""
Error: Workspace ID not found or inaccessible
Solution:
1. Verify FABRIC_WORKSPACE_ID is correct
2. Check service principal has workspace access
3. Confirm workspace exists and is active
4. Use example_1_list_workspaces() to find valid IDs
"""

# Issue 3: Deployment Timeout
"""
Error: Request timeout after XXs
Solution:
1. Increase DEPLOYMENT_TIMEOUT in .env (e.g., to 600)
2. Check network connectivity
3. Verify Fabric API status
4. Try deploying smaller artifacts first
"""

# Issue 4: Rate Limiting (HTTP 429)
"""
Error: Too Many Requests
Solution:
1. Increase RETRY_DELAY in .env
2. Reduce number of concurrent deployments
3. Spread out deployments over time
4. Client automatically retries with exponential backoff
"""

# Issue 5: Invalid Artifact Format
"""
Error: Invalid artifact definition
Solution:
1. Validate JSON syntax in artifact files
2. Check required fields are present
3. Run artifact validator: ArtifactValidator.validate_directory()
4. Reference examples in artifacts/example_dataset.json
"""

# Issue 6: Permission Denied
"""
Error: HTTP 403 Forbidden
Solution:
1. Verify service principal has correct RBAC roles:
   - Power BI Service Admin (for workspace management)
   - Or appropriate workspace-level permissions
2. Check artifact type is supported
3. Verify no conflicts with existing items
"""

# Debugging Tips

# 1. Enable DEBUG logging
"""
Set LOG_LEVEL=DEBUG in .env to see detailed request/response info
"""

# 2. Check logs
"""
Logs are written to:
- Console (controlled by LOG_LEVEL)
- fabric-deployment.log (always INFO+ level)
"""

# 3. Test authentication separately
"""
from fabric_api import FabricAuthenticator
auth = FabricAuthenticator()
token = auth.get_token()  # This will raise if auth fails
"""

# 4. Validate environment
"""
python -c "from fabric_api.config.settings import get_settings; print(get_settings())"
"""

# 5. Test API connectivity
"""
from fabric_api import FabricClient
client = FabricClient()
workspaces = client.list_workspaces()
print(workspaces)
"""

# 6. Inspect artifact structure
"""
import json
with open('artifacts/example.json') as f:
    print(json.dumps(json.load(f), indent=2))
"""

# Common Error Messages Reference

error_codes = {
    400: "Bad Request - Invalid JSON or parameters",
    401: "Unauthorized - Authentication failed",
    403: "Forbidden - Insufficient permissions",
    404: "Not Found - Resource doesn't exist",
    409: "Conflict - Item already exists (use overwrite=True)",
    429: "Too Many Requests - Rate limited (wait and retry)",
    500: "Internal Server Error - API issue",
    503: "Service Unavailable - API maintenance",
}

print(__doc__)
