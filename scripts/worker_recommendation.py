"""
Worker Recommendation Engine for Qlik-to-Power BI Migration

Recommends optimal worker count and parallelization strategy based on portfolio metrics.
"""

import json
import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from powerbi_import.app_profiler import AppProfile, AppTier


@dataclass
class WorkerRecommendation:
    """Recommended worker allocation."""
    recommended_worker_count: int
    max_parallel_workers: int
    sequential_apps: List[str]
    parallel_batches: List[List[str]]
    estimated_total_time_minutes: float
    estimated_sequential_time_minutes: float
    speedup_factor: float
    rationale: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommended_worker_count": self.recommended_worker_count,
            "max_parallel_workers": self.max_parallel_workers,
            "sequential_apps": self.sequential_apps,
            "parallel_batches": self.parallel_batches,
            "estimated_total_time_minutes": self.estimated_total_time_minutes,
            "estimated_sequential_time_minutes": self.estimated_sequential_time_minutes,
            "speedup_factor": self.speedup_factor,
            "rationale": self.rationale
        }


class WorkerRecommender:
    """Recommends worker allocation strategy."""
    
    # System resource limits
    MAX_WORKERS = 16  # Max parallel workers to recommend
    MIN_WORKERS = 1
    
    # Per-tier worker recommendations
    TIER_WORKER_LIMITS = {
        AppTier.SMALL: 4,   # Can safely run 4 small apps in parallel
        AppTier.MEDIUM: 2,  # Medium apps limited to 2 parallel
        AppTier.LARGE: 1    # Large apps should run sequentially
    }
    
    # Memory/CPU estimates per tier (MB RAM)
    TIER_MEMORY_ESTIMATES = {
        AppTier.SMALL: 2000,     # ~2GB per small app
        AppTier.MEDIUM: 5000,    # ~5GB per medium app
        AppTier.LARGE: 15000     # ~15GB per large app
    }
    
    # Target processing time per worker (seconds)
    TARGET_WORKER_TIME_SECONDS = 600  # 10 minutes per worker
    
    def __init__(self, available_memory_gb: float = 32, available_cpus: int = 8):
        """
        Initialize worker recommender.
        
        Args:
            available_memory_gb: Available system memory in GB
            available_cpus: Available CPU cores
        """
        self.available_memory_gb = available_memory_gb
        self.available_memory_mb = available_memory_gb * 1024
        self.available_cpus = available_cpus
        self.logger = logging.getLogger(__name__)
    
    def recommend(self, profiles: List[AppProfile]) -> WorkerRecommendation:
        """
        Recommend worker allocation for a portfolio.
        
        Args:
            profiles: List of app profiles
        
        Returns:
            WorkerRecommendation with strategy
        """
        if not profiles:
            return self._create_minimal_recommendation()
        
        # Calculate total workload
        total_duration_seconds = sum(p.estimated_total_seconds for p in profiles)
        sequential_time_minutes = total_duration_seconds / 60
        
        # Determine optimal worker count
        worker_count = self._calculate_worker_count(profiles)
        worker_count = max(self.MIN_WORKERS, min(worker_count, self.MAX_WORKERS))
        
        # Create parallelization strategy
        parallel_batches = self._create_parallel_batches(profiles, worker_count)
        sequential_apps = self._identify_sequential_apps(profiles)
        
        # Estimate total time with workers
        estimated_total_time = self._estimate_parallel_time(
            parallel_batches,
            sequential_apps,
            profiles
        )
        estimated_total_minutes = estimated_total_time / 60
        
        speedup_factor = sequential_time_minutes / estimated_total_minutes if estimated_total_minutes > 0 else 1.0
        
        rationale = self._generate_rationale(
            worker_count,
            profiles,
            parallel_batches,
            sequential_apps
        )
        
        return WorkerRecommendation(
            recommended_worker_count=worker_count,
            max_parallel_workers=len(parallel_batches) if parallel_batches else 1,
            sequential_apps=sequential_apps,
            parallel_batches=[[p.app_id for p in batch] for batch in parallel_batches],
            estimated_total_time_minutes=estimated_total_minutes,
            estimated_sequential_time_minutes=sequential_time_minutes,
            speedup_factor=speedup_factor,
            rationale=rationale
        )
    
    def _calculate_worker_count(self, profiles: List[AppProfile]) -> int:
        """Calculate optimal worker count based on workload."""
        # Approach: workers = (total_duration / target_time_per_worker) + 1
        total_duration = sum(p.estimated_total_seconds for p in profiles)
        base_workers = int(total_duration / self.TARGET_WORKER_TIME_SECONDS) + 1
        
        # Limit by memory availability
        total_memory_needed = sum(
            self.TIER_MEMORY_ESTIMATES.get(p.tier, 5000) for p in profiles
        )
        memory_limited_workers = int(self.available_memory_mb / (total_memory_needed / len(profiles)))
        memory_limited_workers = max(1, memory_limited_workers)
        
        # Limit by CPU cores
        cpu_limited_workers = max(1, self.available_cpus // 2)  # Reserve half CPU for other work
        
        # Take most restrictive limit
        recommended = min(base_workers, memory_limited_workers, cpu_limited_workers)
        
        self.logger.info(
            f"Worker calculation: base={base_workers}, "
            f"memory_limited={memory_limited_workers}, "
            f"cpu_limited={cpu_limited_workers}, "
            f"recommended={recommended}"
        )
        
        return recommended
    
    def _create_parallel_batches(
        self,
        profiles: List[AppProfile],
        worker_count: int
    ) -> List[List[AppProfile]]:
        """Create parallel batches respecting tier constraints."""
        # Sort by tier (LARGE first, then MEDIUM, then SMALL)
        tier_order = {AppTier.LARGE: 0, AppTier.MEDIUM: 1, AppTier.SMALL: 2}
        sorted_profiles = sorted(profiles, key=lambda p: tier_order[p.tier])
        
        batches: List[List[AppProfile]] = []
        current_batch: List[AppProfile] = []
        current_batch_memory = 0
        
        for profile in sorted_profiles:
            tier_memory = self.TIER_MEMORY_ESTIMATES.get(profile.tier, 5000)
            
            # Large apps always in their own batch
            if profile.tier == AppTier.LARGE:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_memory = 0
                batches.append([profile])
            
            # Check if we can add to current batch
            elif current_batch_memory + tier_memory < self.available_memory_mb * 0.5:  # Use max 50% memory
                current_batch.append(profile)
                current_batch_memory += tier_memory
            
            # Start new batch if needed
            else:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [profile]
                current_batch_memory = tier_memory
        
        # Add remaining batch
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _identify_sequential_apps(self, profiles: List[AppProfile]) -> List[str]:
        """Identify apps that must run sequentially (large or complex)."""
        sequential = []
        for profile in profiles:
            if profile.tier == AppTier.LARGE:
                sequential.append(profile.app_id)
            elif profile.script_lines > 10000:  # Very complex script
                sequential.append(profile.app_id)
        return sequential
    
    def _estimate_parallel_time(
        self,
        parallel_batches: List[List[AppProfile]],
        sequential_apps: List[str],
        profiles_dict: Dict[str, AppProfile]
    ) -> float:
        """Estimate total time with parallelization."""
        if isinstance(profiles_dict, list):
            profiles_dict = {p.app_id: p for p in profiles_dict}
        
        total_time = 0.0
        
        # Sequential apps take full time
        for app_id in sequential_apps:
            if app_id in profiles_dict:
                total_time += profiles_dict[app_id].estimated_total_seconds
        
        # Parallel batches: max(batch) time per batch
        for batch in parallel_batches:
            batch_time = max(
                (profiles_dict.get(app_id) or next((p for p in profiles_dict.values()), None)).estimated_total_seconds
                for app_id in batch
                if app_id in profiles_dict
            )
            total_time += batch_time
        
        return total_time
    
    def _generate_rationale(
        self,
        worker_count: int,
        profiles: List[AppProfile],
        parallel_batches: List[List[AppProfile]],
        sequential_apps: List[str]
    ) -> str:
        """Generate human-readable explanation."""
        rationale_parts = [
            f"Recommended {worker_count} workers based on portfolio metrics."
        ]
        
        # Tier breakdown
        tier_counts = {}
        for p in profiles:
            tier_counts[p.tier] = tier_counts.get(p.tier, 0) + 1
        
        if tier_counts:
            tiers_str = ", ".join(
                f"{count} {tier.value}-tier"
                for tier, count in sorted(tier_counts.items())
            )
            rationale_parts.append(f"Portfolio: {tiers_str}")
        
        # Sequential apps
        if sequential_apps:
            rationale_parts.append(
                f"{len(sequential_apps)} large/complex apps will run sequentially."
            )
        
        # Memory constraint
        rationale_parts.append(
            f"Memory available: {self.available_memory_gb}GB, "
            f"CPUs available: {self.available_cpus}."
        )
        
        return " ".join(rationale_parts)
    
    def _create_minimal_recommendation(self) -> WorkerRecommendation:
        """Create default recommendation for empty portfolio."""
        return WorkerRecommendation(
            recommended_worker_count=1,
            max_parallel_workers=1,
            sequential_apps=[],
            parallel_batches=[],
            estimated_total_time_minutes=0,
            estimated_sequential_time_minutes=0,
            speedup_factor=1.0,
            rationale="No apps to process."
        )


# Example usage
if __name__ == "__main__":
    # Create sample profiles
    profiles = [
        AppProfile(
            app_id="app_1", qvf_file_size_mb=10, table_count=50, column_count=2000,
            measure_count=20, dimension_count=15, sheet_count=5, visual_count=20,
            variable_count=5, script_lines=1000, tier=AppTier.SMALL,
            estimated_extraction_seconds=30, estimated_generation_seconds=45,
            estimated_validation_seconds=15, estimated_total_seconds=90
        ),
        AppProfile(
            app_id="app_2", qvf_file_size_mb=50, table_count=200, column_count=10000,
            measure_count=100, dimension_count=50, sheet_count=10, visual_count=50,
            variable_count=20, script_lines=5000, tier=AppTier.MEDIUM,
            estimated_extraction_seconds=120, estimated_generation_seconds=180,
            estimated_validation_seconds=60, estimated_total_seconds=360
        ),
    ]
    
    recommender = WorkerRecommender(available_memory_gb=32, available_cpus=8)
    recommendation = recommender.recommend(profiles)
    
    print(json.dumps(recommendation.to_dict(), indent=2))
