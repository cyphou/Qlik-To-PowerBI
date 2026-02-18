"""
Pytest Configuration & Fixtures
Tests pour la suite complète de migration Qlik → Power BI
"""
import sys
import os
from pathlib import Path

# Add project root + src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tools" / "migration"))

import pytest


@pytest.fixture(scope="session")
def project_root_dir():
    """Return project root directory"""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def migration_tools_dir(project_root_dir):
    """Return migration tools directory"""
    return project_root_dir / "tools" / "migration"


@pytest.fixture(scope="session")
def test_output_dir(project_root_dir):
    """Return test output directory"""
    test_dir = project_root_dir / "test_output"
    test_dir.mkdir(exist_ok=True)
    return test_dir


@pytest.fixture(scope="session")
def docs_output_dir(test_output_dir):
    """Return documentation output directory"""
    docs_dir = test_output_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    return docs_dir


@pytest.fixture(scope="session")
def migration_module_names():
    """Return list of all migration module names"""
    return [
        # Phase 1
        "migrate_qlik_variables",
        "migrate_section_access",
        "migrate_set_analysis",
        "migrate_bookmarks",
        "migrate_listboxes",
        # Phase 2
        "migrate_master_items",
        "migrate_theme",
        "migrate_current_selections",
        # Phase 3
        "migrate_stories",
        "migrate_navigation",
        "migrate_advanced_aggregations",
        # Phase 4
        "migrate_rest_api",
        "migrate_power_automate",
        "migrate_data_alerts",
        # Phase 5
        "migrate_npprinting",
        "migrate_alternate_states",
        "migrate_custom_extensions",
        "migrate_geoanalytics",
        "migrate_mashups",
        "migrate_advanced_selections",
        "migrate_inter_record_functions",
        "migrate_on_demand_generation",
        "migrate_collaboration",
        # Support modules
        "migrate_qlik_model",
        "migrate_qlik_scripts",
        "migrate_qvd",
        "migrate_qvf",
        "migrate_qlik_to_pbi",
    ]


@pytest.fixture(scope="session")
def phase1_modules():
    """Phase 1 - Critical modules"""
    return [
        "migrate_qlik_variables",
        "migrate_section_access",
        "migrate_set_analysis",
        "migrate_bookmarks",
        "migrate_listboxes",
    ]


@pytest.fixture(scope="session")
def phase2_modules():
    """Phase 2 - UX modules"""
    return [
        "migrate_master_items",
        "migrate_theme",
        "migrate_current_selections",
    ]


@pytest.fixture(scope="session")
def phase3_modules():
    """Phase 3 - Advanced modules"""
    return [
        "migrate_stories",
        "migrate_navigation",
        "migrate_advanced_aggregations",
    ]


@pytest.fixture(scope="session")
def phase4_modules():
    """Phase 4 - Connectivity modules"""
    return [
        "migrate_rest_api",
        "migrate_power_automate",
        "migrate_data_alerts",
    ]


@pytest.fixture(scope="session")
def phase5_modules():
    """Phase 5 - Complete coverage modules"""
    return [
        "migrate_npprinting",
        "migrate_alternate_states",
        "migrate_custom_extensions",
        "migrate_geoanalytics",
        "migrate_mashups",
        "migrate_advanced_selections",
        "migrate_inter_record_functions",
        "migrate_on_demand_generation",
        "migrate_collaboration",
    ]
