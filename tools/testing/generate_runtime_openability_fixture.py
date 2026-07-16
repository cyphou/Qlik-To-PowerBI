#!/usr/bin/env python3
"""Generate a self-contained PBIP fixture for Desktop runtime openability checks.

The fixture uses an in-memory Power Query source (#table), so it does not depend
on external files, servers, or credentials.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fabric_api.tmdl_generator import TMDLGenerator


def generate_fixture(output_dir: Path, report_name: str = "runtime_fixture") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    model = {
        "name": report_name,
        "compatibilityLevel": 1600,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "tables": [
                {
                    "name": "FixtureTable",
                    "columns": [
                        {
                            "name": "Value",
                            "dataType": "double",
                            "sourceColumn": "Value",
                            "summarizeBy": "none",
                        }
                    ],
                    "partitions": [
                        {
                            "name": "FixtureTable",
                            "mode": "import",
                            "source": {
                                "type": "m",
                                "expression": (
                                    "let\n"
                                    "    Source = #table(type table [Value=number], {{1}, {2}, {3}})\n"
                                    "in\n"
                                    "    Source"
                                ),
                            },
                        }
                    ],
                }
            ],
            "relationships": [],
            "expressions": [],
            "annotations": [],
        },
    }

    generator = TMDLGenerator()
    pbip_path = generator.create_pbi_project(
        output_dir=output_dir,
        report_name=report_name,
        bim_model=model,
        visualizations=[],
        dimensions=[],
        measures=[],
        sheets=[],
        bookmarks=[],
    )
    return Path(pbip_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Directory where fixture project is written")
    parser.add_argument("--report-name", default="runtime_fixture", help="PBIP project/report name")
    args = parser.parse_args()

    pbip = generate_fixture(Path(args.output_dir), args.report_name)
    print(str(pbip))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
