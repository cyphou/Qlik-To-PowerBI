"""Backward-compatibility shim -- deprecated.

Import directly from powerbi_import.deploy.utils instead.
"""
import os
import sys
import warnings

warnings.warn(
    "fabric_api.utils is deprecated. "
    "Import from powerbi_import.deploy.utils instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from powerbi_import.deploy.utils import *  # noqa: F401,F403
