"""
App Profiler for Qlik-to-Power BI Migration

Classifies apps into performance tiers (S/M/L) based on structural complexity.
Used for capacity planning, worker allocation, and benchmarking.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional, List
from enum import Enum
from zipfile import ZipFile
from pathlib import Path


class AppTier(Enum):
    """Application size tier."""
    SMALL = "S"
    MEDIUM = "M"
    LARGE = "L"


@dataclass
class AppProfile:
    """Structural profile of a Qlik app."""
    app_id: str
    qvf_file_size_mb: float
    table_count: int
    column_count: int
    measure_count: int
    dimension_count: int
    sheet_count: int
    visual_count: int
    variable_count: int
    script_lines: int
    tier: AppTier
    estimated_extraction_seconds: float
    estimated_generation_seconds: float
    estimated_validation_seconds: float
    estimated_total_seconds: float
    
    def to_dict(self) -> Dict:
        return {
            "app_id": self.app_id,
            "qvf_file_size_mb": self.qvf_file_size_mb,
            "table_count": self.table_count,
            "column_count": self.column_count,
            "measure_count": self.measure_count,
            "dimension_count": self.dimension_count,
            "sheet_count": self.sheet_count,
            "visual_count": self.visual_count,
            "variable_count": self.variable_count,
            "script_lines": self.script_lines,
            "tier": self.tier.value,
            "estimated_extraction_seconds": self.estimated_extraction_seconds,
            "estimated_generation_seconds": self.estimated_generation_seconds,
            "estimated_validation_seconds": self.estimated_validation_seconds,
            "estimated_total_seconds": self.estimated_total_seconds
        }


class AppProfiler:
    """Analyzes Qlik apps to determine size tier and performance characteristics."""
    
    # Tier thresholds (based on typical production apps)
    TIER_THRESHOLDS = {
        AppTier.SMALL: {
            "table_count": (1, 100),
            "column_count": (1, 5000),
            "measure_count": (0, 50)
        },
        AppTier.MEDIUM: {
            "table_count": (100, 500),
            "column_count": (5000, 20000),
            "measure_count": (50, 300)
        },
        AppTier.LARGE: {
            "table_count": (500, float('inf')),
            "column_count": (20000, float('inf')),
            "measure_count": (300, float('inf'))
        }
    }
    
    # Estimated duration per operation by tier (seconds)
    DURATION_ESTIMATES = {
        AppTier.SMALL: {
            "extraction": 30,
            "generation": 45,
            "validation": 15
        },
        AppTier.MEDIUM: {
            "extraction": 120,
            "generation": 180,
            "validation": 60
        },
        AppTier.LARGE: {
            "extraction": 600,
            "generation": 900,
            "validation": 300
        }
    }
    
    def __init__(self):
        """Initialize app profiler."""
        self.logger = logging.getLogger(__name__)
    
    def profile_qvf(self, qvf_path: str, app_id: Optional[str] = None) -> AppProfile:
        """
        Analyze QVF file to create app profile.
        
        Args:
            qvf_path: Path to QVF file
            app_id: Optional app identifier (defaults to filename)
        
        Returns:
            AppProfile with size tier and estimates
        """
        qvf_path = Path(qvf_path)
        
        if not qvf_path.exists():
            raise FileNotFoundError(f"QVF file not found: {qvf_path}")
        
        app_id = app_id or qvf_path.stem
        qvf_size_mb = qvf_path.stat().st_size / (1024 * 1024)
        
        # Extract metadata from QVF
        try:
            metadata = self._extract_metadata(qvf_path)
        except Exception as e:
            self.logger.warning(f"Could not extract metadata from {qvf_path}: {e}")
            # Return minimal profile with estimates
            return self._create_minimal_profile(app_id, qvf_size_mb)
        
        # Determine tier
        tier = self._determine_tier(metadata)
        
        # Calculate estimates
        estimates = self.DURATION_ESTIMATES[tier]
        total_seconds = sum(estimates.values())
        
        profile = AppProfile(
            app_id=app_id,
            qvf_file_size_mb=qvf_size_mb,
            table_count=metadata.get("table_count", 0),
            column_count=metadata.get("column_count", 0),
            measure_count=metadata.get("measure_count", 0),
            dimension_count=metadata.get("dimension_count", 0),
            sheet_count=metadata.get("sheet_count", 0),
            visual_count=metadata.get("visual_count", 0),
            variable_count=metadata.get("variable_count", 0),
            script_lines=metadata.get("script_lines", 0),
            tier=tier,
            estimated_extraction_seconds=estimates["extraction"],
            estimated_generation_seconds=estimates["generation"],
            estimated_validation_seconds=estimates["validation"],
            estimated_total_seconds=total_seconds
        )
        
        self.logger.info(
            f"Profiled {app_id}: tier={tier.value}, "
            f"tables={profile.table_count}, "
            f"columns={profile.column_count}, "
            f"measures={profile.measure_count}, "
            f"est_total_sec={profile.estimated_total_seconds}"
        )
        
        return profile
    
    def _extract_metadata(self, qvf_path: Path) -> Dict:
        """Extract metadata from QVF file."""
        metadata = {
            "table_count": 0,
            "column_count": 0,
            "measure_count": 0,
            "dimension_count": 0,
            "sheet_count": 0,
            "visual_count": 0,
            "variable_count": 0,
            "script_lines": 0
        }
        
        try:
            with ZipFile(qvf_path, 'r') as qvf:
                # Look for manifest.json or workbook.json
                manifest_names = ["manifest.json", "workbook.json", "Manifest.json"]
                manifest_data = None
                
                for name in manifest_names:
                    if name in qvf.namelist():
                        with qvf.open(name) as f:
                            manifest_data = json.load(f)
                        break
                
                if manifest_data:
                    metadata = self._parse_manifest(manifest_data)
        except Exception as e:
            self.logger.debug(f"Error extracting metadata: {e}")
        
        return metadata
    
    def _parse_manifest(self, manifest_data: Dict) -> Dict:
        """Parse Qlik manifest JSON."""
        metadata = {
            "table_count": len(manifest_data.get("tables", [])),
            "column_count": sum(
                len(t.get("columns", [])) for t in manifest_data.get("tables", [])
            ),
            "measure_count": len(manifest_data.get("measures", [])),
            "dimension_count": len(manifest_data.get("dimensions", [])),
            "sheet_count": len(manifest_data.get("sheets", [])),
            "visual_count": sum(
                len(s.get("visuals", [])) for s in manifest_data.get("sheets", [])
            ),
            "variable_count": len(manifest_data.get("variables", [])),
            "script_lines": len(
                manifest_data.get("script", "").split("\n") if isinstance(
                    manifest_data.get("script"), str
                ) else 0
            )
        }
        return metadata
    
    def _create_minimal_profile(self, app_id: str, qvf_size_mb: float) -> AppProfile:
        """Create minimal profile based only on file size."""
        # Estimate based on file size: ~1MB per 50 tables on average
        est_table_count = max(1, int(qvf_size_mb * 50))
        tier = self._determine_tier({
            "table_count": est_table_count,
            "column_count": est_table_count * 50,
            "measure_count": est_table_count * 5
        })
        
        estimates = self.DURATION_ESTIMATES[tier]
        total_seconds = sum(estimates.values())
        
        return AppProfile(
            app_id=app_id,
            qvf_file_size_mb=qvf_size_mb,
            table_count=est_table_count,
            column_count=est_table_count * 50,
            measure_count=est_table_count * 5,
            dimension_count=0,
            sheet_count=0,
            visual_count=0,
            variable_count=0,
            script_lines=0,
            tier=tier,
            estimated_extraction_seconds=estimates["extraction"],
            estimated_generation_seconds=estimates["generation"],
            estimated_validation_seconds=estimates["validation"],
            estimated_total_seconds=total_seconds
        )
    
    def _determine_tier(self, metadata: Dict) -> AppTier:
        """Determine app tier based on metrics."""
        table_count = metadata.get("table_count", 0)
        column_count = metadata.get("column_count", 0)
        measure_count = metadata.get("measure_count", 0)
        
        # Score based on all three metrics
        scores = {}
        for tier, thresholds in self.TIER_THRESHOLDS.items():
            score = 0
            
            # Table count score
            t_range = thresholds.get("table_count", (0, float('inf')))
            if t_range[0] <= table_count <= t_range[1]:
                score += 3
            
            # Column count score
            c_range = thresholds.get("column_count", (0, float('inf')))
            if c_range[0] <= column_count <= c_range[1]:
                score += 3
            
            # Measure count score
            m_range = thresholds.get("measure_count", (0, float('inf')))
            if m_range[0] <= measure_count <= m_range[1]:
                score += 3
            
            scores[tier] = score
        
        # Return tier with highest score, default to MEDIUM
        tier = max(scores.items(), key=lambda x: x[1])[0]
        return tier if scores[tier] > 0 else AppTier.MEDIUM
    
    def profile_multiple(self, qvf_paths: List[str]) -> List[AppProfile]:
        """Profile multiple QVF files."""
        profiles = []
        for qvf_path in qvf_paths:
            try:
                profile = self.profile_qvf(qvf_path)
                profiles.append(profile)
            except Exception as e:
                self.logger.error(f"Error profiling {qvf_path}: {e}")
        return profiles
    
    def calculate_portfolio_stats(self, profiles: List[AppProfile]) -> Dict:
        """Calculate portfolio-wide statistics."""
        if not profiles:
            return {}
        
        tier_counts = {tier: 0 for tier in AppTier}
        total_tables = 0
        total_columns = 0
        total_measures = 0
        total_duration = 0.0
        
        for profile in profiles:
            tier_counts[profile.tier] += 1
            total_tables += profile.table_count
            total_columns += profile.column_count
            total_measures += profile.measure_count
            total_duration += profile.estimated_total_seconds
        
        return {
            "total_apps": len(profiles),
            "tier_distribution": {t.value: tier_counts[t] for t in AppTier},
            "total_tables": total_tables,
            "total_columns": total_columns,
            "total_measures": total_measures,
            "estimated_total_duration_hours": total_duration / 3600,
            "average_app_duration_seconds": total_duration / len(profiles) if profiles else 0
        }


# Example usage
if __name__ == "__main__":
    profiler = AppProfiler()
    
    # Profile a single app
    profile = profiler.profile_qvf("examples/qlik/sample_sales.qvf")
    print(json.dumps(profile.to_dict(), indent=2))
