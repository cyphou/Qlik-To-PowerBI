"""Report packager — bundles all migration artifacts into a ZIP.

Collects the generated .pbip project, intermediate JSON files,
reports (HTML/PDF/PPTX), lineage, and QA results into a single
distributable archive.
"""

from __future__ import annotations

import json
import logging
import os
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger('qlik_to_powerbi.report_packager')

__all__ = ['ReportPackager', 'package_migration']


class ReportPackager:
    """Packages migration artifacts into a distributable ZIP archive."""

    def __init__(self, app_name: str = '', output_dir: str = '.'):
        self.app_name = app_name
        self.output_dir = output_dir
        self._manifest: List[Dict[str, str]] = []

    def _add_to_manifest(self, arcname: str, description: str) -> None:
        self._manifest.append({
            'path': arcname,
            'description': description,
        })

    def package(self, *,
                project_dir: Optional[str] = None,
                json_dir: Optional[str] = None,
                reports: Optional[List[str]] = None,
                lineage_file: Optional[str] = None,
                qa_file: Optional[str] = None,
                cutover_file: Optional[str] = None,
                extra_files: Optional[List[str]] = None,
                include_manifest: bool = True) -> str:
        """Create a ZIP package of all migration artifacts.

        Args:
            project_dir: Path to the generated .pbip project directory.
            json_dir: Path to the intermediate JSON files directory.
            reports: List of report file paths (HTML/PDF/PPTX).
            lineage_file: Path to lineage JSON file.
            qa_file: Path to QA results JSON file.
            cutover_file: Path to cutover plan JSON/MD file.
            extra_files: Additional files to include.
            include_manifest: Whether to include a manifest.json.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{self.app_name or "migration"}_package_{timestamp}.zip'
        zip_path = os.path.join(self.output_dir, filename)

        self._manifest = []

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # .pbip project
            if project_dir and os.path.isdir(project_dir):
                self._add_dir_to_zip(zf, project_dir, 'pbip_project')
                self._add_to_manifest('pbip_project/', 'Generated Power BI project')

            # Intermediate JSON files
            if json_dir and os.path.isdir(json_dir):
                self._add_dir_to_zip(zf, json_dir, 'intermediate_json')
                self._add_to_manifest('intermediate_json/', 'Qlik extraction JSON files')

            # Reports
            for report_path in (reports or []):
                if os.path.isfile(report_path):
                    arcname = f'reports/{os.path.basename(report_path)}'
                    zf.write(report_path, arcname)
                    self._add_to_manifest(arcname, 'Migration report')

            # Lineage
            if lineage_file and os.path.isfile(lineage_file):
                arcname = f'lineage/{os.path.basename(lineage_file)}'
                zf.write(lineage_file, arcname)
                self._add_to_manifest(arcname, 'Full lineage map')

            # QA
            if qa_file and os.path.isfile(qa_file):
                arcname = f'qa/{os.path.basename(qa_file)}'
                zf.write(qa_file, arcname)
                self._add_to_manifest(arcname, 'QA pipeline results')

            # Cutover
            if cutover_file and os.path.isfile(cutover_file):
                arcname = f'cutover/{os.path.basename(cutover_file)}'
                zf.write(cutover_file, arcname)
                self._add_to_manifest(arcname, 'Cutover plan')

            # Extra files
            for extra in (extra_files or []):
                if os.path.isfile(extra):
                    arcname = f'extra/{os.path.basename(extra)}'
                    zf.write(extra, arcname)
                    self._add_to_manifest(arcname, 'Additional artifact')

            # Manifest
            if include_manifest:
                manifest = {
                    'app_name': self.app_name,
                    'created_at': datetime.now().isoformat(),
                    'tool': 'qlik-to-powerbi',
                    'files': self._manifest,
                }
                manifest_json = json.dumps(manifest, indent=2)
                zf.writestr('manifest.json', manifest_json)

        logger.info("Migration package saved to %s", zip_path)
        return zip_path

    def _add_dir_to_zip(self, zf: zipfile.ZipFile, src_dir: str,
                        arc_prefix: str) -> None:
        """Add all files from a directory to the ZIP."""
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, src_dir)
                arcname = os.path.join(arc_prefix, rel_path).replace('\\', '/')
                zf.write(full_path, arcname)


def package_migration(app_name: str, output_dir: str, **kwargs) -> str:
    """Convenience function to create a migration package."""
    packager = ReportPackager(app_name=app_name, output_dir=output_dir)
    return packager.package(**kwargs)
