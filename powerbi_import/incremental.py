"""
Incremental migration module — diff and merge Power BI projects.

Compares a previously generated (or manually edited) .pbip project with
a freshly generated one.  Manual edits in the existing project are detected
and preserved during re-migration by three-way merge:

  Base (first migration) --> Existing (user edits) --> Incoming (new migration)

Usage:
    from powerbi_import.incremental import IncrementalMerger
    report = IncrementalMerger.merge(existing_dir, incoming_dir, output_dir)
"""

import json
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class DiffEntry:
    """Represents a single change between two project trees."""

    __slots__ = ('path', 'kind', 'detail')

    ADDED = 'added'
    REMOVED = 'removed'
    MODIFIED = 'modified'
    UNCHANGED = 'unchanged'

    def __init__(self, path, kind, detail=''):
        self.path = path          # relative path inside project
        self.kind = kind          # added | removed | modified | unchanged
        self.detail = detail      # human-readable change description

    def __repr__(self):
        return f'DiffEntry({self.path!r}, {self.kind!r})'

    def to_dict(self):
        return {'path': self.path, 'kind': self.kind, 'detail': self.detail}


class IncrementalMerger:
    """Diff and merge Power BI .pbip projects for incremental migration."""

    # Files that should NEVER be overwritten (user owns them completely)
    USER_OWNED_FILES = {
        'staticResources',         # manually added images/resources
    }

    # JSON keys that indicate user customizations (preserve on merge)
    USER_EDITABLE_KEYS = {
        'displayName',             # renamed visuals/pages
        'title',                   # manually edited titles
        'description',             # user descriptions
        'background',              # custom backgrounds
        'foreground',              # custom foreground colors
        'wallpaper',               # custom wallpapers
    }

    @classmethod
    def diff_projects(cls, existing_dir, incoming_dir):
        """Compare two .pbip project trees and return a list of DiffEntries.

        Args:
            existing_dir: Path to the existing (potentially edited) project.
            incoming_dir: Path to the freshly generated project.

        Returns:
            list[DiffEntry]
        """
        existing_dir = Path(existing_dir)
        incoming_dir = Path(incoming_dir)
        diffs = []

        # Collect all relative paths
        existing_files = cls._collect_files(existing_dir)
        incoming_files = cls._collect_files(incoming_dir)

        all_paths = sorted(set(existing_files) | set(incoming_files))

        for rel_path in all_paths:
            ex_full = existing_dir / rel_path
            in_full = incoming_dir / rel_path

            if rel_path not in existing_files:
                diffs.append(DiffEntry(rel_path, DiffEntry.ADDED,
                                       'new file from re-migration'))
            elif rel_path not in incoming_files:
                diffs.append(DiffEntry(rel_path, DiffEntry.REMOVED,
                                       'file no longer generated'))
            else:
                # Both exist — compare content
                if cls._files_equal(ex_full, in_full):
                    diffs.append(DiffEntry(rel_path, DiffEntry.UNCHANGED))
                else:
                    detail = cls._describe_change(ex_full, in_full, rel_path)
                    diffs.append(DiffEntry(rel_path, DiffEntry.MODIFIED, detail))

        return diffs

    @classmethod
    def merge(cls, existing_dir, incoming_dir, output_dir=None):
        """Perform an incremental merge.

        * New files from ``incoming_dir`` are added.
        * Removed files are kept if they look user-created, otherwise removed.
        * Modified files are merged: user-editable JSON keys are preserved
          from ``existing_dir``; everything else comes from ``incoming_dir``.
        * Unchanged files are copied from ``existing_dir`` as-is.

        Args:
            existing_dir: Path to the existing project.
            incoming_dir: Path to the freshly generated project.
            output_dir: Optional separate output directory.  If *None*,
                the merge happens in-place into ``existing_dir``.

        Returns:
            dict with summary: ``{merged, added, removed, preserved, conflicts}``
        """
        existing_dir = Path(existing_dir)
        incoming_dir = Path(incoming_dir)
        target_dir = Path(output_dir) if output_dir else existing_dir

        if target_dir != existing_dir and target_dir != incoming_dir:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(existing_dir, target_dir)

        diffs = cls.diff_projects(existing_dir, incoming_dir)

        stats = {'merged': 0, 'added': 0, 'removed': 0,
                 'preserved': 0, 'conflicts': []}

        for entry in diffs:
            target_file = target_dir / entry.path
            incoming_file = incoming_dir / entry.path
            existing_file = existing_dir / entry.path

            if entry.kind == DiffEntry.ADDED:
                # New file from re-migration → copy in
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(incoming_file, target_file)
                stats['added'] += 1

            elif entry.kind == DiffEntry.REMOVED:
                # File no longer generated — check if user-owned
                if cls._is_user_owned(entry.path):
                    stats['preserved'] += 1
                    logger.info("Preserved user file: %s", entry.path)
                else:
                    if target_file.exists():
                        target_file.unlink()
                    stats['removed'] += 1

            elif entry.kind == DiffEntry.MODIFIED:
                # Merge JSON files; overwrite non-JSON
                target_file.parent.mkdir(parents=True, exist_ok=True)
                if entry.path.endswith('.json'):
                    merged, had_conflict = cls._merge_json(
                        existing_file, incoming_file, target_file
                    )
                    stats['merged'] += 1
                    if had_conflict:
                        stats['conflicts'].append(entry.path)
                else:
                    # Non-JSON (e.g. .tmdl) — take incoming
                    shutil.copy2(incoming_file, target_file)
                    stats['merged'] += 1

            # UNCHANGED → no action needed (already in target)

        # Write merge report
        report = {
            'timestamp': datetime.now().isoformat(),
            'existing_dir': str(existing_dir),
            'incoming_dir': str(incoming_dir),
            'output_dir': str(target_dir),
            'stats': {k: v if not isinstance(v, list) else len(v)
                      for k, v in stats.items()},
            'conflicts': stats['conflicts'],
            'diffs': [d.to_dict() for d in diffs if d.kind != DiffEntry.UNCHANGED],
        }
        report_path = target_dir / '.migration_merge_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info("Incremental merge: %d added, %d merged, %d removed, "
                     "%d preserved, %d conflicts",
                     stats['added'], stats['merged'], stats['removed'],
                     stats['preserved'], len(stats['conflicts']))

        return stats

    # ── Internal helpers ───────────────────────────────────────────

    @staticmethod
    def _collect_files(root):
        """Return set of relative file paths under *root*."""
        root = Path(root)
        result = set()
        if not root.exists():
            return result
        for path in root.rglob('*'):
            if path.is_file():
                result.add(str(path.relative_to(root)).replace('\\', '/'))
        return result

    @staticmethod
    def _files_equal(a, b):
        """Check if two files have identical content."""
        try:
            with open(a, 'rb') as fa, open(b, 'rb') as fb:
                return fa.read() == fb.read()
        except Exception:
            return False

    @classmethod
    def _describe_change(cls, existing_path, incoming_path, rel_path):
        """Generate a human-readable description of a file change."""
        if rel_path.endswith('.json'):
            try:
                with open(existing_path, 'r', encoding='utf-8') as f:
                    old = json.load(f)
                with open(incoming_path, 'r', encoding='utf-8') as f:
                    new = json.load(f)
                if isinstance(old, dict) and isinstance(new, dict):
                    added = set(new.keys()) - set(old.keys())
                    removed = set(old.keys()) - set(new.keys())
                    parts = []
                    if added:
                        parts.append(f'+{len(added)} keys')
                    if removed:
                        parts.append(f'-{len(removed)} keys')
                    changed = sum(1 for k in old.keys() & new.keys()
                                  if old[k] != new[k])
                    if changed:
                        parts.append(f'~{changed} keys changed')
                    return ', '.join(parts) if parts else 'content differs'
            except Exception:
                pass
        return 'content differs'

    @classmethod
    def _is_user_owned(cls, rel_path):
        """Check if a file path belongs to a user-owned area."""
        parts = rel_path.replace('\\', '/').split('/')
        for part in parts:
            if part in cls.USER_OWNED_FILES:
                return True
        return False

    @classmethod
    def _merge_json(cls, existing_path, incoming_path, target_path):
        """Merge two JSON files, preserving user-editable keys from existing.

        Returns:
            Tuple[bool, bool]: (merge_success, had_conflict)
        """
        had_conflict = False
        try:
            with open(existing_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            with open(incoming_path, 'r', encoding='utf-8') as f:
                incoming = json.load(f)
        except Exception:
            # Can't parse — take incoming
            shutil.copy2(incoming_path, target_path)
            return True, False

        if isinstance(existing, dict) and isinstance(incoming, dict):
            merged = dict(incoming)  # start with incoming
            for key in cls.USER_EDITABLE_KEYS:
                if key in existing and key not in incoming:
                    # User added something — preserve
                    merged[key] = existing[key]
                elif key in existing and key in incoming:
                    if existing[key] != incoming[key]:
                        # User customized this key — keep user version
                        merged[key] = existing[key]
                        had_conflict = True
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
        else:
            # Non-dict JSON — take incoming
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(incoming, f, indent=2, ensure_ascii=False)

        return True, had_conflict

    @classmethod
    def generate_diff_report(cls, existing_dir, incoming_dir):
        """Generate a human-readable diff report without performing a merge.

        Args:
            existing_dir: Path to existing project.
            incoming_dir: Path to incoming project.

        Returns:
            str: Formatted diff report.
        """
        diffs = cls.diff_projects(existing_dir, incoming_dir)

        lines = [
            f'Migration Diff Report',
            f'Existing: {existing_dir}',
            f'Incoming: {incoming_dir}',
            f'Generated: {datetime.now().isoformat()}',
            '',
        ]

        counts = {}
        for d in diffs:
            counts[d.kind] = counts.get(d.kind, 0) + 1

        lines.append(f'Summary: {len(diffs)} files compared')
        for kind in [DiffEntry.ADDED, DiffEntry.MODIFIED,
                     DiffEntry.REMOVED, DiffEntry.UNCHANGED]:
            lines.append(f'  {kind}: {counts.get(kind, 0)}')
        lines.append('')

        for d in diffs:
            if d.kind != DiffEntry.UNCHANGED:
                detail = f' ({d.detail})' if d.detail else ''
                lines.append(f'  [{d.kind.upper():>8}] {d.path}{detail}')

        return '\n'.join(lines)
