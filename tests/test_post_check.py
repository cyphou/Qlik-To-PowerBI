"""Tests for post-migration validation in powerbi_import.validator."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from powerbi_import.validator import ArtifactValidator


def _make_project(root, name="TestApp", *, tables=None, model_refs=None,
                  report_pages=None, extras=None):
    """Create a minimal .pbip project structure for testing.

    Args:
        root: base temp directory
        name: project name
        tables: list of (table_name, columns, measures) tuples
        model_refs: list of table names for model.tmdl ref entries
        report_pages: list of (page_name, visuals) where visuals is list of dicts
        extras: dict of relative paths -> content to create extra files
    """
    proj = Path(root) / name
    proj.mkdir(parents=True, exist_ok=True)

    # .pbip file
    (proj / f"{name}.pbip").write_text(
        json.dumps({"version": "1.0", "artifacts": []}), encoding="utf-8"
    )

    # SemanticModel
    sm = proj / f"{name}.SemanticModel"
    sm.mkdir(exist_ok=True)
    defn = sm / "definition"
    defn.mkdir(exist_ok=True)

    # definition.pbism
    (sm / "definition.pbism").write_text(
        json.dumps({"version": "1.0"}), encoding="utf-8"
    )

    # model.tmdl
    model_lines = ["model Model"]
    if model_refs:
        for t in model_refs:
            model_lines.append(f"\tref table '{t}'")
    (defn / "model.tmdl").write_text("\n".join(model_lines), encoding="utf-8")

    # tables
    tbl_dir = defn / "tables"
    tbl_dir.mkdir(exist_ok=True)
    for tbl_name, cols, measures in (tables or []):
        lines = [f"table '{tbl_name}'"]
        for col in cols:
            lines.append(f"\tcolumn '{col}'")
            lines.append(f"\t\tdataType: string")
            lines.append(f"\t\tsourceColumn: {col}")
        for m_name, m_expr in measures:
            lines.append(f"\tmeasure '{m_name}' = {m_expr}")
        (tbl_dir / f"{tbl_name}.tmdl").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    # Report
    report = proj / f"{name}.Report"
    report.mkdir(exist_ok=True)
    rep_def = report / "definition"
    rep_def.mkdir(exist_ok=True)

    # definition.pbir
    (rep_def / "definition.pbir").write_text(
        json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
            "datasetReference": {"byPath": {"path": f"../{name}.SemanticModel"}},
        }),
        encoding="utf-8",
    )

    # report.json
    (rep_def / "report.json").write_text(
        json.dumps({"config": "{}"}), encoding="utf-8"
    )

    # Pages
    if report_pages:
        pages_dir = rep_def / "pages"
        pages_dir.mkdir(exist_ok=True)
        for page_name, visuals in report_pages:
            page_dir = pages_dir / page_name
            page_dir.mkdir(exist_ok=True)
            (page_dir / "page.json").write_text(
                json.dumps({"displayName": page_name}), encoding="utf-8"
            )
            if visuals:
                vis_dir = page_dir / "visuals"
                vis_dir.mkdir(exist_ok=True)
                for i, vdef in enumerate(visuals):
                    v_dir = vis_dir / f"visual_{i}"
                    v_dir.mkdir(exist_ok=True)
                    (v_dir / "visual.json").write_text(
                        json.dumps(vdef), encoding="utf-8"
                    )

    # Extra files
    if extras:
        for rel_path, content in extras.items():
            fp = proj / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")

    return proj


class TestValidateFileStructure(unittest.TestCase):
    """Tests for ArtifactValidator.validate_file_structure()."""

    def test_complete_structure_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
                extras={
                    "App.SemanticModel/.platform": '{"config":"fabric"}',
                    "App.SemanticModel/definition/database.tmdl": "database\n",
                    "App.SemanticModel/definition/expressions.tmdl": "expression\n",
                    "App.Report/.platform": '{"config":"fabric"}',
                    "App.Report/definition/version.json": '{"version":"4.0"}',
                },
            )
            errors, warnings = ArtifactValidator.validate_file_structure(proj)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_missing_pbism_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(tmp, "App", tables=[("T", ["c"], [])])
            # Remove definition.pbism
            (proj / "App.SemanticModel" / "definition.pbism").unlink()
            errors, warnings = ArtifactValidator.validate_file_structure(proj)
            self.assertTrue(any("definition.pbism" in e for e in errors))

    def test_missing_platform_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(tmp, "App", tables=[("T", ["c"], [])])
            errors, warnings = ArtifactValidator.validate_file_structure(proj)
            self.assertTrue(any(".platform" in w for w in warnings))

    def test_missing_database_tmdl_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(tmp, "App", tables=[("T", ["c"], [])])
            errors, warnings = ArtifactValidator.validate_file_structure(proj)
            self.assertTrue(any("database.tmdl" in w for w in warnings))

    def test_missing_expressions_tmdl_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(tmp, "App", tables=[("T", ["c"], [])])
            errors, warnings = ArtifactValidator.validate_file_structure(proj)
            self.assertTrue(any("expressions.tmdl" in w for w in warnings))


class TestValidateVisualCompleteness(unittest.TestCase):
    """Tests for ArtifactValidator.validate_visual_completeness()."""

    def test_visual_with_projections_ok(self):
        visuals = [{
            "visual": {
                "visualType": "clusteredBarChart",
                "projections": {"Values": [{"queryRef": "Sum"}]},
            }
        }]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("T", ["c"], [])],
                report_pages=[("Page1", visuals)],
            )
            errors, warnings = ArtifactValidator.validate_visual_completeness(proj)
            self.assertEqual(errors, [])
            # No warning about missing data bindings
            self.assertFalse(any("no data bindings" in w for w in warnings))

    def test_visual_without_bindings_warns(self):
        visuals = [{
            "visual": {
                "visualType": "clusteredBarChart",
            }
        }]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("T", ["c"], [])],
                report_pages=[("Page1", visuals)],
            )
            errors, warnings = ArtifactValidator.validate_visual_completeness(proj)
            self.assertTrue(any("no data bindings" in w for w in warnings))

    def test_visual_with_nested_query_state_ok(self):
        visuals = [{
            "visual": {
                "visualType": "clusteredBarChart",
                "query": {
                    "queryState": {
                        "Category": {
                            "projections": [{"queryRef": "Sales.Category"}]
                        },
                        "Y": {
                            "projections": [{"queryRef": "Sales.Amount"}]
                        },
                    }
                },
            }
        }]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Category", "Amount"], [])],
                report_pages=[("Page1", visuals)],
            )
            errors, warnings = ArtifactValidator.validate_visual_completeness(proj)
            self.assertEqual(errors, [])
            self.assertFalse(any("no data bindings" in w for w in warnings))

    def test_textbox_skipped(self):
        visuals = [{"visual": {"visualType": "textbox"}}]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("T", ["c"], [])],
                report_pages=[("Page1", visuals)],
            )
            errors, warnings = ArtifactValidator.validate_visual_completeness(proj)
            self.assertFalse(any("no data bindings" in w for w in warnings))

    def test_empty_page_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("T", ["c"], [])],
                report_pages=[("EmptyPage", [])],
            )
            # Create visuals dir but leave it empty
            vis_dir = proj / "App.Report" / "definition" / "pages" / "EmptyPage" / "visuals"
            vis_dir.mkdir(parents=True, exist_ok=True)
            errors, warnings = ArtifactValidator.validate_visual_completeness(proj)
            self.assertTrue(any("no visuals" in w for w in warnings))


class TestValidateVisualModelRefs(unittest.TestCase):
    """Tests for ArtifactValidator.validate_visual_model_refs()."""

    def test_valid_refs_no_warnings(self):
        visuals = [{
            "visual": {
                "visualType": "clusteredBarChart",
                "projections": {
                    "Values": [{"queryRef": "Sum"}],
                },
            },
            "query": {
                "Columns": [{
                    "Column": {
                        "Entity": "Sales",
                        "Property": "Amount",
                    }
                }]
            },
        }]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
                report_pages=[("Page1", visuals)],
            )
            warnings = ArtifactValidator.validate_visual_model_refs(proj)
            self.assertEqual(warnings, [])

    def test_unknown_table_warns(self):
        visuals = [{
            "visual": {"visualType": "chart"},
            "query": {
                "Columns": [{
                    "Column": {
                        "Entity": "NonExistent",
                        "Property": "Col",
                    }
                }]
            },
        }]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
                report_pages=[("Page1", visuals)],
            )
            warnings = ArtifactValidator.validate_visual_model_refs(proj)
            self.assertTrue(any("NonExistent" in w for w in warnings))

    def test_unknown_field_warns(self):
        visuals = [{
            "visual": {"visualType": "chart"},
            "query": {
                "Columns": [{
                    "Column": {
                        "Entity": "Sales",
                        "Property": "DoesNotExist",
                    }
                }]
            },
        }]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
                report_pages=[("Page1", visuals)],
            )
            warnings = ArtifactValidator.validate_visual_model_refs(proj)
            self.assertTrue(any("DoesNotExist" in w for w in warnings))


class TestAutoRebindUnboundVisuals(unittest.TestCase):
    """Tests for ArtifactValidator.auto_rebind_unbound_visuals()."""

    def test_auto_rebind_injects_query_state(self):
        visuals = [{
            "visual": {
                "visualType": "clusteredBarChart",
            }
        }]
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Category", "Amount"], [("Total", "SUM([Amount])")])],
                model_refs=["Sales"],
                report_pages=[("Page1", visuals)],
            )
            fixes = ArtifactValidator.auto_rebind_unbound_visuals(proj)
            self.assertGreaterEqual(fixes, 1)

            errors, warnings = ArtifactValidator.validate_visual_completeness(proj)
            self.assertEqual(errors, [])
            self.assertFalse(any("no data bindings" in w for w in warnings))


class TestValidateTmdlIntegrity(unittest.TestCase):
    """Tests for ArtifactValidator.validate_tmdl_integrity()."""

    def test_clean_model_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount", "Qty"], [("Total", "SUM([Amount])")])],
                model_refs=["Sales"],
            )
            errors, warnings = ArtifactValidator.validate_tmdl_integrity(proj)
            self.assertEqual(errors, [])

    def test_duplicate_column_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
            )
            # Manually add duplicate column
            tmdl = proj / "App.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
            content = tmdl.read_text(encoding="utf-8")
            content += "\n\tcolumn 'Amount'\n\t\tdataType: string\n"
            tmdl.write_text(content, encoding="utf-8")
            errors, warnings = ArtifactValidator.validate_tmdl_integrity(proj)
            self.assertTrue(any("Duplicate column" in e and "Amount" in e for e in errors))

    def test_duplicate_measure_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [("Total", "SUM([Amount])")])],
                model_refs=["Sales"],
            )
            tmdl = proj / "App.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
            content = tmdl.read_text(encoding="utf-8")
            content += "\n\tmeasure 'Total' = SUM([Amount])\n"
            tmdl.write_text(content, encoding="utf-8")
            errors, warnings = ArtifactValidator.validate_tmdl_integrity(proj)
            self.assertTrue(any("Duplicate measure" in e and "Total" in e for e in errors))

    def test_relationship_unknown_table_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
                extras={
                    "App.SemanticModel/definition/relationships.tmdl":
                        "relationship rel1\n\tfromTable: 'GhostTable'\n\ttoTable: 'Sales'\n",
                },
            )
            errors, warnings = ArtifactValidator.validate_tmdl_integrity(proj)
            self.assertTrue(any("GhostTable" in e for e in errors))

    def test_missing_ref_table_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create table file without corresponding ref in model.tmdl
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], []), ("Products", ["Name"], [])],
                model_refs=["Sales"],  # Missing Products
            )
            errors, warnings = ArtifactValidator.validate_tmdl_integrity(proj)
            self.assertTrue(any("Products" in w and "ref table" in w for w in warnings))


class TestPostCheck(unittest.TestCase):
    """Tests for ArtifactValidator.post_check() orchestrator."""

    def test_post_check_returns_checks_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [("Total", "SUM([Amount])")])],
                model_refs=["Sales"],
            )
            result = ArtifactValidator.post_check(proj)
            self.assertIn("checks", result)
            self.assertIn("standard_validation", result["checks"])
            self.assertIn("file_structure", result["checks"])
            self.assertIn("visual_completeness", result["checks"])
            self.assertIn("visual_model_refs", result["checks"])
            self.assertIn("tmdl_integrity", result["checks"])

    def test_post_check_valid_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
                extras={
                    "App.SemanticModel/.platform": "{}",
                    "App.SemanticModel/definition/database.tmdl": "database\n",
                    "App.SemanticModel/definition/expressions.tmdl": "expression\n",
                    "App.Report/.platform": "{}",
                    "App.Report/definition/version.json": '{"version":"4.0"}',
                },
            )
            result = ArtifactValidator.post_check(proj)
            self.assertTrue(result["valid"])
            self.assertEqual(result["errors"], [])

    def test_post_check_aggregates_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
                extras={
                    "App.SemanticModel/definition/relationships.tmdl":
                        "relationship r\n\tfromTable: 'Ghost'\n\ttoTable: 'Sales'\n",
                },
            )
            result = ArtifactValidator.post_check(proj)
            # Should have the relationship error from tmdl_integrity
            self.assertTrue(any("Ghost" in e for e in result["errors"]))
            self.assertFalse(result["checks"]["tmdl_integrity"])

    def test_post_check_has_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = _make_project(
                tmp, "App",
                tables=[("Sales", ["Amount"], [])],
                model_refs=["Sales"],
            )
            result = ArtifactValidator.post_check(proj)
            # Should have warnings about missing .platform, database.tmdl, etc.
            self.assertGreater(len(result["warnings"]), 0)


class TestQaPipelineGovernance(unittest.TestCase):
    """Tests that qa_pipeline governance step uses GovernanceEngine correctly."""

    def test_qa_pipeline_imports_governance_engine(self):
        """Verify the import path is GovernanceEngine, not GovernanceAuditor."""
        from powerbi_import import qa_pipeline
        import inspect
        source = inspect.getsource(qa_pipeline)
        self.assertIn("GovernanceEngine", source)
        self.assertNotIn("GovernanceAuditor", source)


class TestTimeIntelligenceIntegration(unittest.TestCase):
    """Test time intelligence measure generation from dax_optimizer."""

    def test_generates_ytd_py_yoy(self):
        from powerbi_import.dax_optimizer import generate_time_intelligence_measures
        measures = [
            {'name': 'Total Sales', 'expression': 'SUM([Amount])'},
        ]
        ti = generate_time_intelligence_measures(measures)
        names = [m['name'] for m in ti]
        self.assertIn('Total Sales YTD', names)
        self.assertIn('Total Sales PY', names)
        self.assertIn('Total Sales YoY %', names)

    def test_skips_non_aggregate_measures(self):
        from powerbi_import.dax_optimizer import generate_time_intelligence_measures
        measures = [
            {'name': 'Status', 'expression': 'IF([Flag], "Yes", "No")'},
        ]
        ti = generate_time_intelligence_measures(measures)
        self.assertEqual(ti, [])

    def test_display_folder_set(self):
        from powerbi_import.dax_optimizer import generate_time_intelligence_measures
        measures = [
            {'name': 'Revenue', 'expression': 'SUM([Revenue])'},
        ]
        ti = generate_time_intelligence_measures(measures)
        for m in ti:
            self.assertEqual(m['displayFolder'], 'Time Intelligence')


class TestSLATracker(unittest.TestCase):
    """Test SLATracker basic functionality."""

    def test_compliant_result(self):
        from powerbi_import.sla_tracker import SLATracker
        tracker = SLATracker({'max_migration_seconds': 600, 'min_fidelity_score': 50,
                              'require_validation_pass': False})
        tracker.start('app1')
        result = tracker.record_result('app1', fidelity=80.0, validation_passed=True)
        self.assertTrue(result.compliant)

    def test_fidelity_breach(self):
        from powerbi_import.sla_tracker import SLATracker
        tracker = SLATracker({'max_migration_seconds': 600, 'min_fidelity_score': 90,
                              'require_validation_pass': False})
        tracker.start('app1')
        result = tracker.record_result('app1', fidelity=50.0, validation_passed=True)
        self.assertFalse(result.fidelity_compliant)
        self.assertTrue(any('fidelity' in b.lower() for b in result.breaches))


if __name__ == "__main__":
    unittest.main()
