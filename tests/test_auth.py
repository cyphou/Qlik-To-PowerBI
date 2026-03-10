"""Tests for authentication module."""
import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path


from powerbi_import.deploy.auth import FabricAuthenticator


def _fake_settings(**overrides):
    """Return a mock settings object."""
    s = MagicMock()
    s.fabric_tenant_id = overrides.get("fabric_tenant_id", "tenant-id")
    s.fabric_client_id = overrides.get("fabric_client_id", "client-id")
    s.fabric_client_secret = overrides.get("fabric_client_secret", "secret")
    return s


class TestFabricAuthenticator:
    """Test FabricAuthenticator class."""

    @patch("powerbi_import.deploy.auth.ClientSecretCredential")
    @patch("powerbi_import.deploy.auth.get_settings")
    def test_init_service_principal(self, mock_get_settings, mock_credential):
        """Test initialization with Service Principal."""
        mock_get_settings.return_value = _fake_settings()

        auth = FabricAuthenticator(use_managed_identity=False)

        assert auth.use_managed_identity is False
        mock_credential.assert_called_once()

    @patch("powerbi_import.deploy.auth.DefaultAzureCredential")
    @patch("powerbi_import.deploy.auth.get_settings")
    def test_init_managed_identity(self, mock_get_settings, mock_credential):
        """Test initialization with Managed Identity."""
        mock_get_settings.return_value = _fake_settings()

        auth = FabricAuthenticator(use_managed_identity=True)

        assert auth.use_managed_identity is True
        mock_credential.assert_called_once()

    @patch("powerbi_import.deploy.auth.ClientSecretCredential")
    @patch("powerbi_import.deploy.auth.get_settings")
    def test_get_token(self, mock_get_settings, mock_cred_class):
        """Test token acquisition."""
        mock_get_settings.return_value = _fake_settings()

        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "test-token-123"
        mock_cred.get_token.return_value = mock_token
        mock_cred_class.return_value = mock_cred

        auth = FabricAuthenticator()
        token = auth.get_token()

        assert token == "test-token-123"
        mock_cred.get_token.assert_called_once()

    @patch("powerbi_import.deploy.auth.ClientSecretCredential")
    @patch("powerbi_import.deploy.auth.get_settings")
    def test_get_headers(self, mock_get_settings, mock_cred_class):
        """Test header generation."""
        mock_get_settings.return_value = _fake_settings()

        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "test-token"
        mock_cred.get_token.return_value = mock_token
        mock_cred_class.return_value = mock_cred

        auth = FabricAuthenticator()
        headers = auth.get_headers()

        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
