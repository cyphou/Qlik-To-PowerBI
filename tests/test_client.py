"""Tests for Fabric API client."""
import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fabric_api.client import FabricClient


def _fake_settings(**overrides):
    defaults = {
        "fabric_api_base_url": "https://api.powerbi.com/v1.0",
        "fabric_workspace_id": "workspace-id",
        "retry_attempts": 3,
        "deployment_timeout": 300,
    }
    defaults.update(overrides)
    s = MagicMock(**defaults)
    return s


class TestFabricClient:
    """Test FabricClient class."""

    @patch("fabric_api.client.FabricAuthenticator")
    @patch("fabric_api.client.get_settings")
    def test_init(self, mock_get_settings, mock_auth):
        """Test client initialization."""
        mock_get_settings.return_value = _fake_settings()

        client = FabricClient()

        assert client.base_url == "https://api.powerbi.com/v1.0"
        assert client.workspace_id == "workspace-id"

    @patch("fabric_api.client.FabricAuthenticator")
    @patch("fabric_api.client.get_settings")
    def test_list_workspaces(self, mock_get_settings, mock_auth_class):
        """Test listing workspaces."""
        mock_get_settings.return_value = _fake_settings()

        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {"Authorization": "Bearer token"}
        mock_auth_class.return_value = mock_auth

        with patch.object(FabricClient, "_request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "value": [{"id": "1", "displayName": "Workspace 1"}]
            }
            mock_request.return_value = mock_response

            client = FabricClient(authenticator=mock_auth)
            result = client.list_workspaces()

            assert "value" in result
            assert len(result["value"]) == 1

    @patch("fabric_api.client.FabricAuthenticator")
    @patch("fabric_api.client.get_settings")
    def test_get_workspace(self, mock_get_settings, mock_auth_class):
        """Test getting workspace details."""
        mock_get_settings.return_value = _fake_settings()

        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {"Authorization": "Bearer token"}
        mock_auth_class.return_value = mock_auth

        with patch.object(FabricClient, "_request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "1", "displayName": "Workspace 1"}
            mock_request.return_value = mock_response

            client = FabricClient(authenticator=mock_auth)
            result = client.get_workspace("workspace-id")

            assert result["displayName"] == "Workspace 1"
