"""
Test Suite - Documentation Validation
Updated for v2.0 project structure.
"""
import pytest
from pathlib import Path


class TestDocumentationStructure:
    """Test the docs directory tree."""

    def test_readme_exists(self, project_root_dir):
        assert (project_root_dir / "README.md").exists()

    def test_docs_directories_structure(self, project_root_dir):
        for d in ["docs", "docs/technical", "docs/guides", "docs/reports"]:
            p = project_root_dir / d
            assert p.exists() and p.is_dir(), f"{d} should exist as directory"

    def test_qlik_objects_coverage_exists(self, project_root_dir):
        assert (project_root_dir / "docs" / "technical" / "QLIK_OBJECTS_COVERAGE.md").exists()

    def test_technical_docs_exist(self, project_root_dir):
        technical = project_root_dir / "docs" / "technical"
        assert technical.exists()
        md_files = list(technical.glob("*.md"))
        assert len(md_files) >= 3, f"docs/technical/ should have >= 3 .md files, found {len(md_files)}"


class TestDocumentationContent:
    """Test content quality."""

    def test_readme_mentions_tmdl(self, project_root_dir):
        content = (project_root_dir / "README.md").read_text("utf-8")
        assert "TMDL" in content, "README should mention TMDL format"

    def test_readme_mentions_pbip(self, project_root_dir):
        content = (project_root_dir / "README.md").read_text("utf-8")
        assert ".pbip" in content, "README should mention .pbip format"

    def test_readme_has_key_sections(self, project_root_dir):
        content = (project_root_dir / "README.md").read_text("utf-8")
        expected = ["Quick Start", "Installation", "Testing", "Documentation"]
        found = sum(1 for s in expected if s in content)
        assert found >= 3, f"README should have at least 3 major sections, found {found}"

    def test_qlik_coverage_shows_100_percent(self, project_root_dir):
        coverage = project_root_dir / "docs" / "technical" / "QLIK_OBJECTS_COVERAGE.md"
        if not coverage.exists():
            pytest.skip("QLIK_OBJECTS_COVERAGE.md not found")
        content = coverage.read_text("utf-8")
        assert "100%" in content, "Coverage file should show 100%"


class TestDocumentationMetrics:
    """Test documentation quantity."""

    def test_total_documentation_size(self, project_root_dir):
        total_lines = 0
        md_files = []
        readme = project_root_dir / "README.md"
        if readme.exists():
            lines = len(readme.read_text("utf-8").splitlines())
            total_lines += lines
            md_files.append((readme.name, lines))
        for folder in ["docs/technical", "docs/guides", "docs/reports"]:
            for md in (project_root_dir / folder).glob("*.md"):
                lines = len(md.read_text("utf-8").splitlines())
                total_lines += lines
                md_files.append((md.name, lines))
        assert total_lines > 3000, f"Should have at least 3000 lines of docs, found {total_lines}"

    def test_guides_exist(self, project_root_dir):
        guides = list((project_root_dir / "docs" / "guides").glob("*.md"))
        assert len(guides) >= 3, f"Should have at least 3 guide files, found {len(guides)}"


class TestModuleDocumentation:

    def test_migration_tools_readme_exists(self, project_root_dir):
        assert (project_root_dir / "tools" / "migration" / "README.md").exists()


class TestPhase5Documentation:
    """Phase 5 — English docs, API reference, updated stats."""

    def test_quick_start_english(self, project_root_dir):
        f = project_root_dir / "docs" / "guides" / "QUICK_START.md"
        assert f.exists(), "English QUICK_START.md should exist"
        content = f.read_text("utf-8")
        assert "migrate.py" in content
        assert ".pbip" in content

    def test_migration_guide_english(self, project_root_dir):
        f = project_root_dir / "docs" / "guides" / "MIGRATION_GUIDE.md"
        assert f.exists(), "English MIGRATION_GUIDE.md should exist"
        content = f.read_text("utf-8")
        assert "DAX" in content
        assert "TMDL" in content
        assert "--json" in content

    def test_deployment_guide(self, project_root_dir):
        f = project_root_dir / "docs" / "guides" / "DEPLOYMENT_GUIDE.md"
        assert f.exists(), "DEPLOYMENT_GUIDE.md should exist"
        content = f.read_text("utf-8")
        assert "Fabric" in content or "Azure" in content

    def test_plugin_development_guide(self, project_root_dir):
        f = project_root_dir / "docs" / "guides" / "PLUGIN_DEVELOPMENT.md"
        assert f.exists(), "PLUGIN_DEVELOPMENT.md should exist"
        content = f.read_text("utf-8")
        assert "PluginBase" in content or "plugin" in content.lower()
        assert "transform_dax" in content

    def test_api_reference(self, project_root_dir):
        f = project_root_dir / "docs" / "API_REFERENCE.md"
        assert f.exists(), "API_REFERENCE.md should exist"
        content = f.read_text("utf-8")
        assert "convert_qlik_expression_to_dax" in content
        assert "PowerBIProjectGenerator" in content
        assert "PluginManager" in content

    def test_readme_updated_test_count(self, project_root_dir):
        content = (project_root_dir / "README.md").read_text("utf-8")
        assert "2%2C000" in content or "2,000" in content, "README should have updated test count (2,000+)"

    def test_readme_updated_version(self, project_root_dir):
        content = (project_root_dir / "README.md").read_text("utf-8")
        assert "10.0.0" in content, "README should reference v10.0.0"

    def test_copilot_instructions_updated(self, project_root_dir):
        f = project_root_dir / ".github" / "copilot-instructions.md"
        assert f.exists()
        content = f.read_text("utf-8")
        assert "2,213" in content or "2213" in content, "copilot-instructions should have updated test count"
        assert "10.0.0" in content

    def test_faq_has_v8_entries(self, project_root_dir):
        content = (project_root_dir / "docs" / "FAQ.md").read_text("utf-8")
        assert "--json" in content, "FAQ should document --json"
        assert "plugin" in content.lower(), "FAQ should document plugins"


class TestPhase6Housekeeping:
    """Phase 6 — Version bump, CI, dead code docs."""

    def test_version_8_in_qlik_export(self):
        import qlik_export
        assert qlik_export.__version__ == '8.0.0'

    def test_version_9_in_powerbi_import(self):
        import powerbi_import
        assert powerbi_import.__version__ == '9.0.0'

    def test_fabric_api_deprecation_readme(self, project_root_dir):
        f = project_root_dir / "src" / "fabric_api" / "README.md"
        assert f.exists(), "fabric_api should have deprecation README"
        content = f.read_text("utf-8")
        assert "DEPRECATED" in content

    def test_ci_workflow_has_coverage(self, project_root_dir):
        f = project_root_dir / ".github" / "workflows" / "ci.yml"
        assert f.exists()
        content = f.read_text("utf-8")
        assert "coverage" in content.lower()

    def test_ci_workflow_has_ruff(self, project_root_dir):
        f = project_root_dir / ".github" / "workflows" / "ci.yml"
        content = f.read_text("utf-8")
        assert "ruff" in content

    def test_changelog_has_v8(self, project_root_dir):
        content = (project_root_dir / "CHANGELOG.md").read_text("utf-8")
        assert "v8.0.0" in content
        assert "Plugin" in content

    def test_pyproject_version_9(self, project_root_dir):
        content = (project_root_dir / "pyproject.toml").read_text("utf-8")
        assert '10.0.0' in content
