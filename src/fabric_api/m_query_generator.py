"""Backward-compatibility shim -- deprecated.

Import directly from qlik_export.m_query_generator instead.
"""
import os
import sys
import warnings

warnings.warn(
    "fabric_api.m_query_generator is deprecated. "
    "Import from qlik_export.m_query_generator instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from qlik_export.m_query_generator import *  # noqa: F401,F403
