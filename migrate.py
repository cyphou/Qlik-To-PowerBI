"""
Main script for Qlik to Power BI migration

Pipeline:
1. Extract objects from the Qlik file (.qvf or .json export)
2. Generate the Power BI project (.pbip) with TMDL model
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def print_header(text):
    """Print a formatted header."""
    print()
    print("=" * 80)
    print(text.center(80))
    print("=" * 80)
    print()


def print_step(step_num, total_steps, text):
    """Print a step indicator."""
    print(f"\n[Step {step_num}/{total_steps}] {text}")
    print("-" * 80)


def run_extraction(qlik_file, output_dir):
    """Run Qlik extraction → intermediate JSON files."""
    print_step(1, 2, "QLIK OBJECTS EXTRACTION")

    if not os.path.exists(qlik_file):
        print(f"Error: Qlik file not found: {qlik_file}")
        return False

    print(f"Source file: {qlik_file}")

    try:
        from fabric_api.extraction_orchestrator import ExtractionOrchestrator

        orchestrator = ExtractionOrchestrator(qlik_file, output_dir)
        json_dir = orchestrator.extract_all()

        print(f"\n✓ Extraction completed — intermediate JSON in {json_dir}")
        return True

    except Exception as e:
        print(f"\nError during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_generation(json_dir, output_dir, report_name):
    """Generate Power BI project (.pbip) from extracted JSON."""
    print_step(2, 2, "POWER BI PROJECT GENERATION")

    try:
        from fabric_api.tmdl_generator import TMDLGenerator
        from fabric_api.extraction_orchestrator import load_intermediate_json

        data = load_intermediate_json(json_dir)
        print(f"  Loaded intermediate JSON: {len(data)} object types")

        generator = TMDLGenerator()

        project_dir = Path(output_dir) / report_name
        project_dir.mkdir(parents=True, exist_ok=True)

        pbip_path = generator.create_pbi_project(
            output_dir=project_dir,
            report_name=report_name,
            bim_model=data.get("bim_model"),
            power_query_script=data.get("power_query_script"),
            visualizations=data.get("visualizations"),
            dimensions=data.get("dimensions"),
            measures=data.get("measures"),
        )

        print(f"\n✓ Power BI project generated: {pbip_path}")
        return True

    except Exception as e:
        print(f"\nError during generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate a Qlik Sense application to a Power BI project (.pbip)"
    )

    parser.add_argument(
        "qlik_file",
        help="Path to the Qlik file (.qvf or .json export)",
    )

    parser.add_argument(
        "--output-dir",
        default="output/migrated",
        help="Output directory for generated project (default: output/migrated)",
    )

    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction step (reuse existing intermediate JSON files)",
    )

    args = parser.parse_args()

    print_header("QLIK TO POWER BI MIGRATION")
    print(f"Source file: {args.qlik_file}")
    print(f"Output dir:  {args.output_dir}")
    print()

    start_time = datetime.now()
    results = {}

    # Determine report name from source file
    source_basename = os.path.splitext(os.path.basename(args.qlik_file))[0]
    json_dir = os.path.join(args.output_dir, source_basename, "_extracted")

    # Step 1: Extraction
    if not args.skip_extraction:
        results["extraction"] = run_extraction(args.qlik_file, json_dir)
        if not results["extraction"]:
            print("\nMigration aborted due to extraction failure")
            return 1
    else:
        print("\nExtraction skipped (using existing intermediate JSON)")
        results["extraction"] = True

    # Step 2: Generate .pbip project
    results["generation"] = run_generation(json_dir, args.output_dir, source_basename)

    # Final report
    duration = datetime.now() - start_time
    print_header("MIGRATION RESULT")
    print(f"Duration: {duration}")
    print()

    for step_name, success in [
        ("Qlik Extraction", results.get("extraction", False)),
        ("Power BI Generation", results.get("generation", False)),
    ]:
        status = "✓ Success" if success else "✗ Failed"
        print(f"  {step_name:<30} {status}")

    all_success = all(results.values())

    if all_success:
        print("\nMigration completed successfully!")
        print("\nNext steps:")
        print(f"  1. Open the .pbip file in {args.output_dir}/{source_basename}/")
        print("  2. Enable Developer Mode in Power BI Desktop → Options → Preview features")
        print("  3. Configure data sources in Power Query Editor")
        print("  4. Verify DAX measures and calculated columns")
    else:
        print("\nMigration completed with errors")

    return 0 if all_success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
