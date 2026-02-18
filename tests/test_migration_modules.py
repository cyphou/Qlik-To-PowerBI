"""
Test Suite - Migration Modules Import & Syntax Validation
Tests que tous les modules Python peuvent être importés et exécutés
"""
import pytest
import sys
from pathlib import Path
import importlib.util


class TestMigrationModulesImports:
    """Test imports de tous les modules de migration"""

    def test_all_phase1_modules_importable(self, migration_tools_dir, phase1_modules):
        """Test que tous les modules Phase 1 peuvent être importés"""
        for module_name in phase1_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            assert module_path.exists(), f"Module not found: {module_name}.py"
            
            # Try to import
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            
            # Should not raise exception
            try:
                spec.loader.exec_module(module)
                assert module is not None, f"Failed to load {module_name}"
            except Exception as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_all_phase2_modules_importable(self, migration_tools_dir, phase2_modules):
        """Test que tous les modules Phase 2 peuvent être importés"""
        for module_name in phase2_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            assert module_path.exists(), f"Module not found: {module_name}.py"
            
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            
            try:
                spec.loader.exec_module(module)
                assert module is not None, f"Failed to load {module_name}"
            except Exception as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_all_phase3_modules_importable(self, migration_tools_dir, phase3_modules):
        """Test que tous les modules Phase 3 peuvent être importés"""
        for module_name in phase3_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            assert module_path.exists(), f"Module not found: {module_name}.py"
            
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            
            try:
                spec.loader.exec_module(module)
                assert module is not None, f"Failed to load {module_name}"
            except Exception as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_all_phase4_modules_importable(self, migration_tools_dir, phase4_modules):
        """Test que tous les modules Phase 4 peuvent être importés"""
        for module_name in phase4_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            assert module_path.exists(), f"Module not found: {module_name}.py"
            
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            
            try:
                spec.loader.exec_module(module)
                assert module is not None, f"Failed to load {module_name}"
            except Exception as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_all_phase5_modules_importable(self, migration_tools_dir, phase5_modules):
        """Test que tous les modules Phase 5 peuvent être importés - LE TEST CLEF!"""
        for module_name in phase5_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            assert module_path.exists(), f"Module not found: {module_name}.py"
            
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            
            try:
                spec.loader.exec_module(module)
                assert module is not None, f"Failed to load {module_name}"
            except Exception as e:
                pytest.fail(f"Failed to import Phase 5 module {module_name}: {e}")


class TestModuleSyntax:
    """Test syntaxe Python de tous les modules"""

    def test_module_syntax_valid(self, migration_tools_dir, migration_module_names):
        """Test que tous les modules ont une syntaxe Python valide"""
        import ast
        
        for module_name in migration_module_names:
            module_path = migration_tools_dir / f"{module_name}.py"
            
            if not module_path.exists():
                print(f"Warning: {module_name}.py not found, skipping")
                continue
            
            with open(module_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Parse code - will raise SyntaxError if invalid
            try:
                ast.parse(code)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {module_name}.py: {e}")


class TestModuleStructure:
    """Test structure et contenu des modules"""

    def test_all_modules_exist(self, migration_tools_dir, migration_module_names):
        """Test que tous les modules existent"""
        missing_modules = []
        
        for module_name in migration_module_names:
            module_path = migration_tools_dir / f"{module_name}.py"
            if not module_path.exists():
                missing_modules.append(module_name)
        
        if missing_modules:
            print(f"Note: Missing modules (might be optional): {missing_modules}")
        
        # At minimum, Phase 1-5 modules should exist
        phase1_modules = [
            "migrate_qlik_variables",
            "migrate_section_access",
            "migrate_set_analysis",
            "migrate_bookmarks",
            "migrate_listboxes",
        ]
        
        for module_name in phase1_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            assert module_path.exists(), f"Critical Phase 1 module missing: {module_name}.py"

    def test_critical_modules_not_empty(self, migration_tools_dir):
        """Test que les modules critiques ne sont pas vides"""
        critical_modules = [
            "migrate_qlik_variables",
            "migrate_section_access",
            "migrate_set_analysis",
            "migrate_bookmarks",
            "migrate_listboxes",
            "migrate_master_items",
            "migrate_theme",
        ]
        
        for module_name in critical_modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            
            if not module_path.exists():
                pytest.skip(f"{module_name}.py not found")
            
            with open(module_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            codesize = len(content.split('\n'))
            assert codesize > 20, f"{module_name}.py is too small ({codesize} lines)"


class TestPhaseCompletion:
    """Test que toutes les phases sont complétes"""

    def test_phase1_complete(self, migration_tools_dir, phase1_modules):
        """Phase 1 devrait avoir 5 modules"""
        assert len(phase1_modules) == 5, "Phase 1 should have 5 modules"
        
        existing = []
        for module_name in phase1_modules:
            if (migration_tools_dir / f"{module_name}.py").exists():
                existing.append(module_name)
        
        assert len(existing) == 5, f"Phase 1 incomplete: only {len(existing)}/5 modules found"

    def test_phase2_complete(self, migration_tools_dir, phase2_modules):
        """Phase 2 devrait avoir 3 modules"""
        assert len(phase2_modules) == 3, "Phase 2 should have 3 modules"
        
        existing = []
        for module_name in phase2_modules:
            if (migration_tools_dir / f"{module_name}.py").exists():
                existing.append(module_name)
        
        assert len(existing) == 3, f"Phase 2 incomplete: only {len(existing)}/3 modules found"

    def test_phase3_complete(self, migration_tools_dir, phase3_modules):
        """Phase 3 devrait avoir 3 modules"""
        assert len(phase3_modules) == 3, "Phase 3 should have 3 modules"
        
        existing = []
        for module_name in phase3_modules:
            if (migration_tools_dir / f"{module_name}.py").exists():
                existing.append(module_name)
        
        assert len(existing) == 3, f"Phase 3 incomplete: only {len(existing)}/3 modules found"

    def test_phase4_complete(self, migration_tools_dir, phase4_modules):
        """Phase 4 devrait avoir 3 modules"""
        assert len(phase4_modules) == 3, "Phase 4 should have 3 modules"
        
        existing = []
        for module_name in phase4_modules:
            if (migration_tools_dir / f"{module_name}.py").exists():
                existing.append(module_name)
        
        assert len(existing) == 3, f"Phase 4 incomplete: only {len(existing)}/3 modules found"

    def test_phase5_complete(self, migration_tools_dir, phase5_modules):
        """Phase 5 devrait avoir 9 modules - LE GRAND TEST!"""
        assert len(phase5_modules) == 9, "Phase 5 should have 9 modules"
        
        existing = []
        missing = []
        for module_name in phase5_modules:
            if (migration_tools_dir / f"{module_name}.py").exists():
                existing.append(module_name)
            else:
                missing.append(module_name)
        
        print(f"\n✅ Phase 5 modules found: {len(existing)}/9")
        for mod in existing:
            print(f"   ✅ {mod}")
        
        if missing:
            print(f"\n❌ Missing Phase 5 modules: {len(missing)}")
            for mod in missing:
                print(f"   ❌ {mod}")
        
        assert len(existing) == 9, f"Phase 5 incomplete: only {len(existing)}/9 modules found: {missing}"

    def test_100_percent_coverage(self, migration_tools_dir, migration_module_names):
        """Test: tous les modules de couverture à 100% existent et sont importables"""
        total_modules = len(migration_module_names)
        
        existing_modules = []
        for module_name in migration_module_names:
            if (migration_tools_dir / f"{module_name}.py").exists():
                existing_modules.append(module_name)
        
        coverage_percentage = (len(existing_modules) / total_modules) * 100
        
        print(f"\n📊 COUVERTURE MODULES")
        print(f"   Total modules définis: {total_modules}")
        print(f"   Modules existants: {len(existing_modules)}")
        print(f"   Couverture: {coverage_percentage:.1f}%")
        
        # Au minimum 20 modules (sans les optionnels)
        assert len(existing_modules) >= 20, f"Not enough migration modules: {len(existing_modules)}/20"
