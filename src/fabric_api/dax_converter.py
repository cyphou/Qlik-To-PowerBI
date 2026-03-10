"""Backward-compatibility shim -- deprecated.

Import directly from qlik_export.dax_converter instead.
"""
import os
import sys
import warnings

warnings.warn(
    "fabric_api.dax_converter is deprecated. "
    "Import from qlik_export.dax_converter instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from qlik_export.dax_converter import *  # noqa: F401,F403
