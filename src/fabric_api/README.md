# ⚠️ DEPRECATED — fabric_api

This package is a **backward-compatibility shim**. All new code should import from the canonical packages:

| Old import | New import |
|-----------|-----------|
| `from fabric_api.dax_converter import ...` | `from qlik_export.dax_converter import ...` |
| `from fabric_api.m_query_generator import ...` | `from qlik_export.m_query_generator import ...` |
| `from fabric_api.validator import ...` | `from powerbi_import.validator import ...` |
| `from fabric_api.deployer import ...` | `from powerbi_import.deploy.deployer import ...` |

## Files with unique code (not yet migrated)

- **`tmdl_generator.py`** — `TMDLGenerator` class (~900 lines). Use `powerbi_import.tmdl_generator` and `powerbi_import.pbip_generator` for new code.
- **`visual_generator.py`** — Visual generation helpers (~500 lines). Use `powerbi_import.visual_generator` for new code.

## All other files

Pure re-export shims that emit `DeprecationWarning` on import. Will be removed in a future version.
