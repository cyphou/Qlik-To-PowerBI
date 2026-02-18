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
