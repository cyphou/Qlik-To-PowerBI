"""Backward-compatibility shim -- deprecated.

Import directly from powerbi_import.deploy.deployer instead.
"""
import os
import sys
import warnings

warnings.warn(
    "fabric_api.deployer is deprecated. "
    "Import from powerbi_import.deploy.deployer instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from powerbi_import.deploy.deployer import *  # noqa: F401,F403
