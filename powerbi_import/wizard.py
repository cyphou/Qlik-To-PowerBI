"""Interactive CLI migration wizard.

Walks the user through the migration process with prompts for
each option, automatically detecting available workbooks and
providing sensible defaults.

Usage::

    python -m powerbi_import.wizard
    # or
    python migrate.py --wizard
"""

import os
import sys
import glob


def _input(prompt, default=None):
    """Read input with a default value."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    try:
        value = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value or default


def _yes_no(prompt, default=True):
    """Ask a yes/no question."""
    suffix = " [Y/n]" if default else " [y/N]"
    answer = _input(prompt + suffix, 'y' if default else 'n')
    return answer.lower() in ('y', 'yes', '1', 'true')


def _choose(prompt, options, default=0):
    """Present numbered options and return the chosen index."""
    print(f"\n  {prompt}")
    for i, opt in enumerate(options):
        marker = " *" if i == default else ""
        print(f"    {i + 1}. {opt}{marker}")
    while True:
        raw = _input(f"  Choice (1-{len(options)})", str(default + 1))
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}")


def run_wizard():
    """Run the interactive migration wizard.

    Returns:
        dict: Configuration dict ready to pass to the migration pipeline.
    """
    print()
    print("=" * 60)
    print("  Qlik → Power BI  Migration Wizard")
    print("=" * 60)
    print()

    config = {}

    # ── Step 1: Source file ──
    print("─── Step 1: Source Workbook ───")

    # Auto-detect workbooks in current dir
    found = []
    for ext in ('*.qvf', '*.json'):
        found.extend(glob.glob(ext))
        found.extend(glob.glob(os.path.join('examples', '**', ext), recursive=True))
    found = sorted(set(found))

    if found:
        print(f"\n  Found {len(found)} workbook(s):")
        for i, f in enumerate(found[:20]):
            print(f"    {i + 1}. {f}")
        if len(found) > 20:
            print(f"    ... and {len(found) - 20} more")

        use_found = _yes_no("\n  Use one of these?")
        if use_found and found:
            idx = _choose("Select workbook:", found[:20])
            config['source_file'] = found[idx]
        else:
            config['source_file'] = _input("  Path to Qlik app (.qvf) or JSON export")
    else:
        config['source_file'] = _input("  Path to Qlik app (.qvf) or JSON export")

    if not config['source_file'] or not os.path.isfile(config['source_file']):
        print(f"\n  Error: File not found: {config.get('source_file')}")
        return None

    # ── Step 2: Prep flow ──
    print("\n─── Step 2: Qlik Data Load Script (Optional) ───")
    has_prep = _yes_no("  Do you have a Qlik data load script to merge?", default=False)
    if has_prep:
        config['prep'] = _input("  Path to load script (.qvs)")
    else:
        config['prep'] = None

    # ── Step 3: Output ──
    print("\n─── Step 3: Output Options ───")
    config['output_dir'] = _input("  Output directory", 'artifacts/powerbi_projects')

    format_opts = ['Full .pbip project', 'TMDL only (semantic model)', 'PBIR only (report)']
    fmt_idx = _choose("Output format:", format_opts, default=0)
    config['output_format'] = ['pbip', 'tmdl', 'pbir'][fmt_idx]

    # ── Step 4: Model mode ──
    print("\n─── Step 4: Semantic Model Mode ───")
    mode_opts = ['Import (fastest queries, data cached)', 
                 'DirectQuery (live queries, always fresh)',
                 'Composite (mix of import + DQ)']
    mode_idx = _choose("Model mode:", mode_opts, default=0)
    config['mode'] = ['import', 'directquery', 'composite'][mode_idx]

    # ── Step 5: Calendar ──
    print("\n─── Step 5: Calendar Table ───")
    auto_cal = _yes_no("  Auto-generate Calendar date table?")
    if auto_cal:
        config['calendar_start'] = int(_input("  Start year", '2020'))
        config['calendar_end'] = int(_input("  End year", '2030'))
    else:
        config['calendar_start'] = None
        config['calendar_end'] = None

    # ── Step 6: Culture ──
    print("\n─── Step 6: Locale / Culture ───")
    config['culture'] = _input("  Culture (e.g., en-US, fr-FR, de-DE)", 'en-US')

    # ── Step 7: Extras ──
    print("\n─── Step 7: Additional Options ───")
    config['paginated'] = _yes_no("  Generate paginated report?", default=False)
    config['rollback'] = _yes_no("  Backup existing project before overwrite?", default=True)
    config['verbose'] = _yes_no("  Enable verbose logging?", default=False)
    config['assess'] = _yes_no("  Run pre-migration assessment first?", default=True)

    # ── Summary ──
    print("\n" + "=" * 60)
    print("  Migration Configuration Summary")
    print("=" * 60)
    print(f"  Source:       {config['source_file']}")
    if config.get('prep'):
        print(f"  Prep flow:    {config['prep']}")
    print(f"  Output dir:   {config['output_dir']}")
    print(f"  Format:       {config['output_format']}")
    print(f"  Mode:         {config['mode']}")
    if config.get('calendar_start'):
        print(f"  Calendar:     {config['calendar_start']}-{config['calendar_end']}")
    print(f"  Culture:      {config['culture']}")
    print(f"  Paginated:    {'Yes' if config['paginated'] else 'No'}")
    print(f"  Rollback:     {'Yes' if config['rollback'] else 'No'}")
    print(f"  Assessment:   {'Yes' if config['assess'] else 'No'}")
    print()

    proceed = _yes_no("  Proceed with migration?")
    if not proceed:
        print("  Migration cancelled.")
        return None

    return config


def wizard_to_args(config):
    """Convert wizard config dict to argparse-compatible namespace.

    Returns:
        argparse.Namespace: Ready to pass to main() internals.
    """
    import argparse
    args = argparse.Namespace(
        tableau_file=config['source_file'],
        prep=config.get('prep'),
        output_dir=config.get('output_dir'),
        output_format=config.get('output_format', 'pbip'),
        mode=config.get('mode', 'import'),
        calendar_start=config.get('calendar_start'),
        calendar_end=config.get('calendar_end'),
        culture=config.get('culture'),
        paginated=config.get('paginated', False),
        rollback=config.get('rollback', False),
        verbose=config.get('verbose', False),
        assess=config.get('assess', False),
        batch=None,
        batch_config=None,
        dry_run=False,
        skip_extraction=False,
        skip_conversion=False,
        log_file=None,
        config=None,
        incremental=None,
        telemetry=False,
    )
    return args


def main():
    """Entry point for standalone wizard usage."""
    config = run_wizard()
    if config is None:
        return
    # Import and run migration with wizard config
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from migrate import main as migrate_main
    args = wizard_to_args(config)
    sys.argv = ['migrate.py', config['source_file']]  # Reset argv
    # Patch argparse to return our args
    import argparse
    original_parse = argparse.ArgumentParser.parse_args
    argparse.ArgumentParser.parse_args = lambda self, a=None, n=None: args
    try:
        migrate_main()
    finally:
        argparse.ArgumentParser.parse_args = original_parse


if __name__ == '__main__':
    main()
