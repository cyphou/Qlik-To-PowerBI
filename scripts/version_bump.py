#!/usr/bin/env python
"""
Version Bump Script — Automates version number changes across project files.

Updates version strings in:
  - CHANGELOG.md (prepends new section)
  - README.md (badge or version mention)
  - migrate.py (__version__)
  - pyproject.toml / setup.cfg (if present)

Usage:
    python scripts/version_bump.py 3.6.0
    python scripts/version_bump.py 3.6.0 --dry-run
    python scripts/version_bump.py patch          # 3.5.0 → 3.5.1
    python scripts/version_bump.py minor          # 3.5.0 → 3.6.0
    python scripts/version_bump.py major          # 3.5.0 → 4.0.0
"""

import os
import re
import sys
import argparse
from datetime import datetime


# ── Paths relative to project root ──────────────────────────────────

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

VERSION_FILES = {
    'migrate.py': r"(__version__\s*=\s*['\"])([0-9]+\.[0-9]+\.[0-9]+)(['\"])",
    'CHANGELOG.md': None,  # Special handling
}


def _find_current_version():
    """Find current version from migrate.py or CHANGELOG.md."""
    # Try migrate.py first
    migrate_path = os.path.join(PROJECT_ROOT, 'migrate.py')
    if os.path.exists(migrate_path):
        with open(migrate_path, 'r', encoding='utf-8') as f:
            content = f.read()
        m = re.search(r'__version__\s*=\s*[\'"]([0-9]+\.[0-9]+\.[0-9]+)[\'"]', content)
        if m:
            return m.group(1)

    # Fallback to CHANGELOG.md
    changelog_path = os.path.join(PROJECT_ROOT, 'CHANGELOG.md')
    if os.path.exists(changelog_path):
        with open(changelog_path, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r'##\s+v?([0-9]+\.[0-9]+\.[0-9]+)', line)
                if m:
                    return m.group(1)

    return '0.0.0'


def _compute_next_version(current, bump_type):
    """Compute next version based on bump type."""
    parts = [int(x) for x in current.split('.')]
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {current}")

    major, minor, patch = parts

    if bump_type == 'major':
        return f'{major + 1}.0.0'
    elif bump_type == 'minor':
        return f'{major}.{minor + 1}.0'
    elif bump_type == 'patch':
        return f'{major}.{minor}.{patch + 1}'
    else:
        # Explicit version
        if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+$', bump_type):
            raise ValueError(f"Invalid version: {bump_type}. Use X.Y.Z or major/minor/patch")
        return bump_type


def _update_migrate_py(new_version, dry_run=False):
    """Update __version__ in migrate.py."""
    path = os.path.join(PROJECT_ROOT, 'migrate.py')
    if not os.path.exists(path):
        print(f"  [SKIP] {path} not found")
        return False

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r"(__version__\s*=\s*['\"])([0-9]+\.[0-9]+\.[0-9]+)(['\"])"
    if not re.search(pattern, content):
        print(f"  [SKIP] No __version__ found in migrate.py")
        return False

    new_content = re.sub(pattern, rf'\g<1>{new_version}\3', content)

    if dry_run:
        print(f"  [DRY-RUN] Would update migrate.py: __version__ = '{new_version}'")
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  [OK] Updated migrate.py: __version__ = '{new_version}'")
    return True


def _update_changelog(new_version, dry_run=False):
    """Prepend new version section to CHANGELOG.md."""
    path = os.path.join(PROJECT_ROOT, 'CHANGELOG.md')
    if not os.path.exists(path):
        print(f"  [SKIP] {path} not found")
        return False

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    month_year = datetime.now().strftime('%B %Y')
    new_section = f"\n## v{new_version} — {month_year}\n\n### Changes\n\n- \n\n"

    # Insert after the first "# Changelog" line
    if '# Changelog' in content:
        new_content = content.replace('# Changelog\n', f'# Changelog\n{new_section}', 1)
    else:
        new_content = f'# Changelog\n{new_section}{content}'

    if dry_run:
        print(f"  [DRY-RUN] Would prepend v{new_version} section to CHANGELOG.md")
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  [OK] Added v{new_version} section to CHANGELOG.md")
    return True


def _update_pyproject_toml(new_version, dry_run=False):
    """Update version in pyproject.toml if present."""
    path = os.path.join(PROJECT_ROOT, 'pyproject.toml')
    if not os.path.exists(path):
        return False

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(version\s*=\s*["\'])([0-9]+\.[0-9]+\.[0-9]+)(["\'])'
    if not re.search(pattern, content):
        return False

    new_content = re.sub(pattern, rf'\g<1>{new_version}\3', content)

    if dry_run:
        print(f"  [DRY-RUN] Would update pyproject.toml version to {new_version}")
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  [OK] Updated pyproject.toml version to {new_version}")
    return True


def bump_version(version_arg, dry_run=False):
    """Main version bump logic.
    
    Args:
        version_arg: 'major', 'minor', 'patch', or explicit 'X.Y.Z'
        dry_run: If True, only print what would change
    
    Returns:
        tuple: (old_version, new_version)
    """
    current = _find_current_version()
    new_version = _compute_next_version(current, version_arg)

    print(f"\nVersion bump: {current} → {new_version}")
    if dry_run:
        print("  (dry-run mode — no files will be changed)\n")
    else:
        print()

    _update_migrate_py(new_version, dry_run)
    _update_changelog(new_version, dry_run)
    _update_pyproject_toml(new_version, dry_run)

    print(f"\nDone. {'Would bump' if dry_run else 'Bumped'} {current} → {new_version}")
    return current, new_version


def main():
    parser = argparse.ArgumentParser(description='Bump project version')
    parser.add_argument('version', help="'major', 'minor', 'patch', or explicit 'X.Y.Z'")
    parser.add_argument('--dry-run', action='store_true', help='Show changes without writing')
    args = parser.parse_args()

    try:
        bump_version(args.version, dry_run=args.dry_run)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
