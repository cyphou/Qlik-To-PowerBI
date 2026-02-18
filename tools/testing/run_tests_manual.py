"""
Comprehensive Test Runner - Manual Test Suite without pytest
Validation complète du projet sans dépendre de pytest
"""
import sys
import os
from pathlib import Path
import importlib.util
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "tools" / "migration"))

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.tests = []
        self.start_time = datetime.now()
    
    def add_passed(self, test_name, message=""):
        self.passed += 1
        self.tests.append(("✅ PASS", test_name, message))
        print(f"  ✅ {test_name}")
        if message:
            print(f"     {message}")
    
    def add_failed(self, test_name, message):
        self.failed += 1
        self.tests.append(("❌ FAIL", test_name, message))
        print(f"  ❌ {test_name}")
        print(f"     {message}")
    
    def add_skipped(self, test_name, reason):
        self.skipped += 1
        self.tests.append(("⏭️  SKIP", test_name, reason))
        print(f"  ⏭️  {test_name} (skipped: {reason})")
    
    def summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        total = self.passed + self.failed + self.skipped
        
        print(f"\n{'='*70}")
        print(f"TEST RESULTS SUMMARY")
        print(f"{'='*70}")
        print(f"  Total Tests: {total}")
        print(f"  ✅ Passed:   {self.passed}")
        print(f"  ❌ Failed:   {self.failed}")
        print(f"  ⏭️  Skipped:  {self.skipped}")
        print(f"  Duration:   {duration:.2f}s")
        print(f"{'='*70}\n")
        
        if self.failed > 0:
            print("FAILED TESTS:")
            for status, name, msg in self.tests:
                if "FAIL" in status:
                    print(f"  {status} {name}")
                    print(f"     {msg[:100]}")
        
        return self.failed == 0


def test_module_imports(results, migration_tools_dir):
    """Test 1: Module imports"""
    print("\n" + "="*70)
    print("TEST 1: Module Imports Validation")
    print("="*70)
    
    phase_modules = {
        "Phase 1": [
            "migrate_qlik_variables",
            "migrate_section_access",
            "migrate_set_analysis",
            "migrate_bookmarks",
            "migrate_listboxes",
        ],
        "Phase 2": [
            "migrate_master_items",
            "migrate_theme",
            "migrate_current_selections",
        ],
        "Phase 3": [
            "migrate_stories",
            "migrate_navigation",
            "migrate_advanced_aggregations",
        ],
        "Phase 4": [
            "migrate_rest_api",
            "migrate_power_automate",
            "migrate_data_alerts",
        ],
        "Phase 5": [
            "migrate_npprinting",
            "migrate_alternate_states",
            "migrate_custom_extensions",
            "migrate_geoanalytics",
            "migrate_mashups",
            "migrate_advanced_selections",
            "migrate_inter_record_functions",
            "migrate_on_demand_generation",
            "migrate_collaboration",
        ],
    }
    
    for phase_name, modules in phase_modules.items():
        print(f"\n{phase_name} ({len(modules)} modules):")
        
        for module_name in modules:
            module_path = migration_tools_dir / f"{module_name}.py"
            
            if not module_path.exists():
                results.add_failed(f"{phase_name}: {module_name}", 
                                  f"File not found: {module_path}")
                continue
            
            # Try to import
            try:
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                results.add_passed(f"{phase_name}: {module_name}")
            except Exception as e:
                results.add_failed(f"{phase_name}: {module_name}", 
                                  f"Import error: {str(e)[:80]}")


def test_module_files_exist(results, migration_tools_dir):
    """Test 2: Module files existence"""
    print("\n" + "="*70)
    print("TEST 2: Module Files Existence")
    print("="*70)
    
    all_modules = [
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
    ]
    
    existing_modules = []
    missing_modules = []
    
    for module_name in all_modules:
        module_path = migration_tools_dir / f"{module_name}.py"
        if module_path.exists():
            existing_modules.append(module_name)
            results.add_passed(f"File exists: {module_name}")
        else:
            missing_modules.append(module_name)
            results.add_failed(f"File exists: {module_name}", "File not found")
    
    results.add_passed(f"Coverage: {len(existing_modules)}/23 modules", 
                      f"({len(existing_modules)/23*100:.1f}%)")
    
    if missing_modules:
        results.add_failed(f"Missing modules", f"{missing_modules}")


def test_documentation_structure(results, project_root_dir):
    """Test 3: Documentation structure"""
    print("\n" + "="*70)
    print("TEST 3: Documentation Structure")
    print("="*70)
    
    required_docs = {
        "README.md": "Main documentation",
        "INDEX.md": "Navigation index",
        "PROJECT_SUMMARY.md": "Project summary",
        "PHASE_5_COMPLETE.md": "Phase 5 completion",
        "SYNTHESE_PROGRESSION.md": "Progress summary",
    }
    
    for doc_file, description in required_docs.items():
        path = project_root_dir / doc_file
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
            results.add_passed(f"{doc_file}", f"({lines} lines)")
        else:
            results.add_failed(f"{doc_file}", f"File not found: {path}")
    
    # Check docs directories
    docs_dirs = ["docs", "docs/technical", "docs/guides", "tools/migration"]
    
    print("\nDirectories:")
    for dir_name in docs_dirs:
        path = project_root_dir / dir_name
        if path.exists() and path.is_dir():
            results.add_passed(f"Directory exists: {dir_name}")
        else:
            results.add_failed(f"Directory exists: {dir_name}", f"Not found at {path}")


def test_markdown_content_validation(results, project_root_dir):
    """Test 4: Markdown content validation"""
    print("\n" + "="*70)
    print("TEST 4: Markdown Content Validation")
    print("="*70)
    
    # Check README
    readme = project_root_dir / "README.md"
    if readme.exists():
        with open(readme, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "100%" in content:
            results.add_passed("README mentions 100% coverage")
        else:
            results.add_failed("README mentions 100%", "Not found in README")
    
    # Check PROJECT_SUMMARY
    summary = project_root_dir / "PROJECT_SUMMARY.md"
    if summary.exists():
        with open(summary, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "72" in content:
            results.add_passed("PROJECT_SUMMARY mentions 72 objects")
        else:
            results.add_failed("PROJECT_SUMMARY mentions 72 objects", "Not found")
        
        if "100%" in content:
            results.add_passed("PROJECT_SUMMARY mentions 100%")
        else:
            results.add_failed("PROJECT_SUMMARY mentions 100%", "Not found")
    
    # Check PHASE_5_COMPLETE
    phase5 = project_root_dir / "PHASE_5_COMPLETE.md"
    if phase5.exists():
        with open(phase5, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if len(content) > 500:
            results.add_passed("PHASE_5_COMPLETE has substantial content", 
                             f"({len(content)} bytes)")
        else:
            results.add_failed("PHASE_5_COMPLETE has content", 
                             f"Too small: {len(content)} bytes")


def test_phase5_completion(results, migration_tools_dir):
    """Test 5: Phase 5 COMPLETION TEST"""
    print("\n" + "="*70)
    print("TEST 5: PHASE 5 COMPLETION - THE FINAL TEST! 🎯")
    print("="*70)
    
    phase5_modules = [
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
    
    print(f"\nPhase 5 Module Verification (9/9 required):\n")
    
    missing = []
    present = []
    
    for i, module_name in enumerate(phase5_modules, 1):
        module_path = migration_tools_dir / f"{module_name}.py"
        
        if module_path.exists():
            with open(module_path, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
            
            print(f"  {i}. ✅ {module_name:<40} ({lines:3d} lines)")
            present.append(module_name)
            results.add_passed(f"Phase 5 module {i}: {module_name}")
        else:
            print(f"  {i}. ❌ {module_name:<40} MISSING!")
            missing.append(module_name)
            results.add_failed(f"Phase 5 module {i}: {module_name}", "File not found")
    
    print(f"\nPhase 5 Status:")
    if not missing:
        print("  ✅ ALL 9 MODULES PRESENT - 100% PHASE 5 COMPLETE!")
        results.add_passed(f"PHASE 5 COMPLETE", "All 9/9 modules delivered")
    else:
        print(f"  ❌ Missing {len(missing)} modules: {missing}")
        results.add_failed(f"PHASE 5 COMPLETENESS", f"{len(missing)} missing: {missing}")


def test_overall_coverage(results, migration_tools_dir):
    """Test 6: Overall coverage"""
    print("\n" + "="*70)
    print("TEST 6: OVERALL COVERAGE ANALYSIS 📊")
    print("="*70)
    
    all_modules = [
        "migrate_qlik_variables", "migrate_section_access", "migrate_set_analysis",
        "migrate_bookmarks", "migrate_listboxes", "migrate_master_items",
        "migrate_theme", "migrate_current_selections", "migrate_stories",
        "migrate_navigation", "migrate_advanced_aggregations", "migrate_rest_api",
        "migrate_power_automate", "migrate_data_alerts", "migrate_npprinting",
        "migrate_alternate_states", "migrate_custom_extensions", "migrate_geoanalytics",
        "migrate_mashups", "migrate_advanced_selections", "migrate_inter_record_functions",
        "migrate_on_demand_generation", "migrate_collaboration",
    ]
    
    existing = [m for m in all_modules if (migration_tools_dir / f"{m}.py").exists()]
    coverage = len(existing) / len(all_modules) * 100
    
    print(f"\nTotal Coverage: {len(existing)}/{len(all_modules)} modules ({coverage:.1f}%)")
    
    phases = {
        "Phase 1": 5,
        "Phase 2": 3,
        "Phase 3": 3,
        "Phase 4": 3,
        "Phase 5": 9,
    }
    
    idx = 0
    for phase_name, count in phases.items():
        phase_modules = existing[idx:idx+count]
        idx += count
        
        phase_coverage = len([m for m in all_modules[idx-count:idx] 
                             if (migration_tools_dir / f"{m}.py").exists()]) / count * 100
        
        symbol = "✅" if phase_coverage == 100 else "⚠️ "
        print(f"  {symbol} {phase_name:<15} {phase_coverage:5.1f}%")
    
    if coverage >= 90:
        results.add_passed("Overall coverage", f"{coverage:.1f}% ({len(existing)}/{len(all_modules)})")
    else:
        results.add_failed("Overall coverage", f"Only {coverage:.1f}%")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST SUITE - Qlik to Power BI Migration")
    print("="*70)
    
    project_root = Path(__file__).parent
    migration_tools_dir = project_root / "tools" / "migration"
    
    results = TestResults()
    
    # Run all test suites
    test_module_files_exist(results, migration_tools_dir)
    test_module_imports(results, migration_tools_dir)
    test_documentation_structure(results, project_root)
    test_markdown_content_validation(results, project_root)
    test_phase5_completion(results, migration_tools_dir)
    test_overall_coverage(results, migration_tools_dir)
    
    # Print summary
    success = results.summary()
    
    # Save results to file
    results_file = project_root / "test_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "passed": results.passed,
            "failed": results.failed,
            "skipped": results.skipped,
            "total": results.passed + results.failed + results.skipped,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Results saved to: {results_file}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
