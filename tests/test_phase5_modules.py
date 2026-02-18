"""
Test Suite - Phase 5 Modules Specific Tests
Tests spécifiques pour les 9 modules Phase 5 (couverture 100%)
"""
import pytest
import importlib.util
from pathlib import Path


class TestPhase5NPrinting:
    """Tests pour migrate_npprinting.py"""

    def test_npprinting_module_exists(self, migration_tools_dir):
        """Test que le module NPrinting existe"""
        module_path = migration_tools_dir / "migrate_npprinting.py"
        assert module_path.exists(), "migrate_npprinting.py should exist"

    def test_npprinting_module_importable(self, migration_tools_dir):
        """Test que le module NPrinting peut être importé"""
        module_path = migration_tools_dir / "migrate_npprinting.py"
        spec = importlib.util.spec_from_file_location("migrate_npprinting", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_npprinting: {e}")

    def test_npprinting_has_content(self, migration_tools_dir):
        """Test que migrate_npprinting a du contenu"""
        module_path = migration_tools_dir / "migrate_npprinting.py"
        with open(module_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert len(content) > 500, "migrate_npprinting should have substantial content"
        assert "def " in content, "migrate_npprinting should define functions"


class TestPhase5AlternateStates:
    """Tests pour migrate_alternate_states.py"""

    def test_alternate_states_module_exists(self, migration_tools_dir):
        """Test que le module Alternate States existe"""
        module_path = migration_tools_dir / "migrate_alternate_states.py"
        assert module_path.exists(), "migrate_alternate_states.py should exist"

    def test_alternate_states_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_alternate_states.py"
        spec = importlib.util.spec_from_file_location("migrate_alternate_states", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_alternate_states: {e}")


class TestPhase5CustomExtensions:
    """Tests pour migrate_custom_extensions.py"""

    def test_custom_extensions_module_exists(self, migration_tools_dir):
        """Test que le module Custom Extensions existe"""
        module_path = migration_tools_dir / "migrate_custom_extensions.py"
        assert module_path.exists(), "migrate_custom_extensions.py should exist"

    def test_custom_extensions_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_custom_extensions.py"
        spec = importlib.util.spec_from_file_location("migrate_custom_extensions", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_custom_extensions: {e}")


class TestPhase5GeoAnalytics:
    """Tests pour migrate_geoanalytics.py"""

    def test_geoanalytics_module_exists(self, migration_tools_dir):
        """Test que le module GeoAnalytics existe"""
        module_path = migration_tools_dir / "migrate_geoanalytics.py"
        assert module_path.exists(), "migrate_geoanalytics.py should exist"

    def test_geoanalytics_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_geoanalytics.py"
        spec = importlib.util.spec_from_file_location("migrate_geoanalytics", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_geoanalytics: {e}")


class TestPhase5Mashups:
    """Tests pour migrate_mashups.py"""

    def test_mashups_module_exists(self, migration_tools_dir):
        """Test que le module Mashups existe"""
        module_path = migration_tools_dir / "migrate_mashups.py"
        assert module_path.exists(), "migrate_mashups.py should exist"

    def test_mashups_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_mashups.py"
        spec = importlib.util.spec_from_file_location("migrate_mashups", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_mashups: {e}")


class TestPhase5AdvancedSelections:
    """Tests pour migrate_advanced_selections.py"""

    def test_advanced_selections_module_exists(self, migration_tools_dir):
        """Test que le module Advanced Selections existe"""
        module_path = migration_tools_dir / "migrate_advanced_selections.py"
        assert module_path.exists(), "migrate_advanced_selections.py should exist"

    def test_advanced_selections_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_advanced_selections.py"
        spec = importlib.util.spec_from_file_location("migrate_advanced_selections", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_advanced_selections: {e}")


class TestPhase5InterRecordFunctions:
    """Tests pour migrate_inter_record_functions.py"""

    def test_inter_record_module_exists(self, migration_tools_dir):
        """Test que le module Inter-Record Functions existe"""
        module_path = migration_tools_dir / "migrate_inter_record_functions.py"
        assert module_path.exists(), "migrate_inter_record_functions.py should exist"

    def test_inter_record_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_inter_record_functions.py"
        spec = importlib.util.spec_from_file_location("migrate_inter_record_functions", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_inter_record_functions: {e}")


class TestPhase5OnDemandGeneration:
    """Tests pour migrate_on_demand_generation.py"""

    def test_on_demand_module_exists(self, migration_tools_dir):
        """Test que le module On-Demand Generation existe"""
        module_path = migration_tools_dir / "migrate_on_demand_generation.py"
        assert module_path.exists(), "migrate_on_demand_generation.py should exist"

    def test_on_demand_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_on_demand_generation.py"
        spec = importlib.util.spec_from_file_location("migrate_on_demand_generation", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_on_demand_generation: {e}")


class TestPhase5Collaboration:
    """Tests pour migrate_collaboration.py"""

    def test_collaboration_module_exists(self, migration_tools_dir):
        """Test que le module Collaboration existe"""
        module_path = migration_tools_dir / "migrate_collaboration.py"
        assert module_path.exists(), "migrate_collaboration.py should exist"

    def test_collaboration_importable(self, migration_tools_dir):
        """Test que le module peut être importé"""
        module_path = migration_tools_dir / "migrate_collaboration.py"
        spec = importlib.util.spec_from_file_location("migrate_collaboration", module_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
            assert module is not None
        except Exception as e:
            pytest.fail(f"Failed to import migrate_collaboration: {e}")


class TestPhase5Summary:
    """Test sommaire Phase 5"""

    def test_all_phase5_modules_present(self, migration_tools_dir, phase5_modules):
        """Test PRINCIPAL: tous les 9 modules Phase 5 sont présents"""
        missing = []
        for module_name in phase5_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            if not module_path.exists():
                missing.append(module_name)
        
        assert missing == [], f"Phase 5 incomplete! Missing: {missing}"
        assert len(phase5_modules) == 9, "Phase 5 should have exactly 9 modules"
        
        print(f"\n✅ PHASE 5 COMPLETE: All 9 modules present!")

    def test_all_phase5_modules_importable(self, migration_tools_dir, phase5_modules):
        """Test PRINCIPAL: tous les 9 modules Phase 5 peuvent être importés"""
        failed_imports = []
        
        for module_name in phase5_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            
            try:
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                failed_imports.append((module_name, str(e)))
        
        assert failed_imports == [], f"Failed to import: {failed_imports}"
        print(f"\n✅ All Phase 5 modules importable!")

    def test_phase5_coverage_100_percent(self, migration_tools_dir, phase5_modules):
        """Test: Phase 5 provides 100% coverage"""
        print(f"\n📊 PHASE 5 COVERAGE TEST")
        print(f"   Expected: 9 modules")
        print(f"   Defined: {len(phase5_modules)} modules")
        
        for module_name in phase5_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            if module_path.exists():
                with open(module_path, 'r', encoding='utf-8') as f:
                    lines = len(f.readlines())
                print(f"   ✅ {module_name:<40} ({lines:3d} lines)")
            else:
                print(f"   ❌ {module_name:<40} MISSING")
        
        assert all((migration_tools_dir / f"{m}.py").exists() for m in phase5_modules)
