import csv
import json
import subprocess
import sys
import zipfile
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "build_wave_manifests.py"


def test_build_wave_manifests_from_csv(tmp_path: Path):
    csv_path = tmp_path / "portfolio.csv"
    out_dir = tmp_path / "manifests"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "app_id",
                "app_name",
                "source_path",
                "target_wave",
                "profile",
                "target_workspace",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "app_id": "APP-001",
                "app_name": "Sales",
                "source_path": "apps/sales.qvf",
                "target_wave": "Wave-0",
                "profile": "strict",
                "target_workspace": "SalesWs",
            }
        )
        writer.writerow(
            {
                "app_id": "APP-002",
                "app_name": "Finance",
                "source_path": "apps/finance.qvf",
                "target_wave": "Wave-1",
                "profile": "regulated",
                "target_workspace": "FinWs",
            }
        )

    cmd = [
        sys.executable,
        str(_script_path()),
        "--input",
        str(csv_path),
        "--output-dir",
        str(out_dir),
        "--output-root",
        "artifacts/powerbi_projects/migrated",
        "--include-profiles-template",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr

    all_manifest = json.loads((out_dir / "all_apps_manifest.json").read_text(encoding="utf-8"))
    wave0_manifest = json.loads((out_dir / "wave_Wave-0_manifest.json").read_text(encoding="utf-8"))
    wave1_manifest = json.loads((out_dir / "wave_Wave-1_manifest.json").read_text(encoding="utf-8"))

    assert len(all_manifest["entries"]) == 2
    assert len(wave0_manifest["entries"]) == 1
    assert len(wave1_manifest["entries"]) == 1
    assert "strict" in all_manifest["profiles"]
    assert wave0_manifest["entries"][0]["output_dir"].endswith("SalesWs")


def test_build_wave_manifests_auto_wave_json(tmp_path: Path):
    in_path = tmp_path / "portfolio.json"
    out_dir = tmp_path / "manifests"

    payload = {
        "apps": [
            {
                "app_name": "SimpleApp",
                "source_path": "apps/simple.qvf",
                "criticality": "low",
                "complexity_tier": "A",
            },
            {
                "app_name": "HardApp",
                "source_path": "apps/hard.qvf",
                "criticality": "high",
                "complexity_tier": "C",
                "custom_extensions": True,
            },
        ]
    }
    in_path.write_text(json.dumps(payload), encoding="utf-8")

    cmd = [
        sys.executable,
        str(_script_path()),
        "--input",
        str(in_path),
        "--output-dir",
        str(out_dir),
        "--auto-wave",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert (out_dir / "wave_Wave-0_manifest.json").exists()
    assert (out_dir / "wave_Wave-3_manifest.json").exists()


def test_build_wave_manifests_make_ready_filters_invalid_qvf(tmp_path: Path):
    csv_path = tmp_path / "portfolio.csv"
    out_dir = tmp_path / "manifests"

    valid_qvf = tmp_path / "valid.qvf"
    invalid_qvf = tmp_path / "invalid.qvf"

    with zipfile.ZipFile(valid_qvf, "w") as zf:
        zf.writestr("AppMetadata.xml", "<app></app>")
    invalid_qvf.write_bytes(b"not-a-zip")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["app_id", "app_name", "source_path", "target_wave", "profile"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "app_id": "APP-001",
                "app_name": "Valid",
                "source_path": str(valid_qvf),
                "target_wave": "Wave-0",
                "profile": "strict",
            }
        )
        writer.writerow(
            {
                "app_id": "APP-002",
                "app_name": "Invalid",
                "source_path": str(invalid_qvf),
                "target_wave": "Wave-0",
                "profile": "strict",
            }
        )

    cmd = [
        sys.executable,
        str(_script_path()),
        "--input",
        str(csv_path),
        "--output-dir",
        str(out_dir),
        "--make-ready",
        "--repo-root",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr

    ready_manifest = json.loads((out_dir / "wave_Wave-0_manifest_ready.json").read_text(encoding="utf-8"))
    ready_report = json.loads((out_dir / "wave_Wave-0_manifest_ready_report.json").read_text(encoding="utf-8"))

    assert len(ready_manifest["entries"]) == 1
    assert ready_report["ready_entries"] == 1
    assert any(i["reason"] == "invalid_qvf_not_zip" for i in ready_report["skipped"])


def test_build_wave_manifests_normalizes_output_dir_separators(tmp_path: Path):
    csv_path = tmp_path / "portfolio.csv"
    out_dir = tmp_path / "manifests"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "app_id",
                "app_name",
                "source_path",
                "target_wave",
                "profile",
                "target_workspace",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "app_id": "APP-100",
                "app_name": "Sales",
                "source_path": "apps/sales.qvf",
                "target_wave": "Wave-0",
                "profile": "strict",
                "target_workspace": "Wave0-Sales",
            }
        )

    cmd = [
        sys.executable,
        str(_script_path()),
        "--input",
        str(csv_path),
        "--output-dir",
        str(out_dir),
        "--output-root",
        "output\\waves\\enterprise_wave0\\staging",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    wave0_manifest = json.loads((out_dir / "wave_Wave-0_manifest.json").read_text(encoding="utf-8"))
    assert wave0_manifest["entries"][0]["output_dir"] == "output/waves/enterprise_wave0/staging/Wave0-Sales"
