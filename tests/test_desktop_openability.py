from pathlib import Path

from tools.testing.desktop_openability import (
    ProjectExpectation,
    RuntimeObservation,
    evaluate_runtime,
    inspect_project,
)


def _project(tmp_path: Path, *, calculated_bridge: bool = False) -> Path:
    pbip = tmp_path / "Sample.pbip"
    pbip.write_text("{}", encoding="utf-8")
    definition = tmp_path / "Sample.SemanticModel" / "definition"
    tables = definition / "tables"
    tables.mkdir(parents=True)
    (tables / "Fact.tmdl").write_text(
        "table Fact\n"
        "\tcolumn Key\n"
        "\t\tdataType: int64\n"
        "\tpartition Fact = m\n",
        encoding="utf-8",
    )
    bridge_partition = "calculated" if calculated_bridge else "m"
    (tables / "Bridge.tmdl").write_text(
        "table Bridge\n"
        "\tcolumn Key\n"
        "\t\tdataType: int64\n"
        f"\tpartition Bridge = {bridge_partition}\n",
        encoding="utf-8",
    )
    (definition / "relationships.tmdl").write_text(
        "relationship rel-1\n"
        "\tfromColumn: Fact.Key\n"
        "\ttoColumn: Bridge.Key\n",
        encoding="utf-8",
    )
    return pbip


def test_inspect_project_counts_tmdl_model(tmp_path):
    expected = inspect_project(_project(tmp_path))

    assert expected.project_name == "Sample"
    assert expected.table_count == 2
    assert expected.relationship_count == 1
    assert expected.statically_safe


def test_inspect_project_rejects_calculated_relationship_endpoint(tmp_path):
    expected = inspect_project(_project(tmp_path, calculated_bridge=True))

    assert expected.calculated_tables == ["Bridge"]
    assert expected.calculated_relationship_endpoints == ["Bridge.Key"]
    assert not expected.statically_safe


def test_evaluate_runtime_accepts_exact_live_model():
    expected = ProjectExpectation(
        pbip_path="Sample.pbip",
        project_name="Sample",
        semantic_model_dir="Sample.SemanticModel",
        table_count=2,
        relationship_count=1,
    )
    runtime = RuntimeObservation(
        status="model_loaded",
        process_responding=True,
        title="Sample",
        visible_windows=["Sample"],
        port=51000,
        table_count=2,
        relationship_count=1,
    )

    assert evaluate_runtime(expected, runtime) == []


def test_evaluate_runtime_rejects_partial_model_and_error_dialog():
    expected = ProjectExpectation(
        pbip_path="Sample.pbip",
        project_name="Sample",
        semantic_model_dir="Sample.SemanticModel",
        table_count=2,
        relationship_count=1,
    )
    runtime = RuntimeObservation(
        status="model_loaded",
        process_responding=True,
        title="Sample",
        visible_windows=["Sample", "Unable to open document"],
        port=51000,
        table_count=1,
        relationship_count=0,
    )

    issues = evaluate_runtime(expected, runtime)

    assert any("unexpected visible Desktop windows" in issue for issue in issues)
    assert any("live table count" in issue for issue in issues)
    assert any("live relationship count" in issue for issue in issues)