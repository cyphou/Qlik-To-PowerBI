"""
Batch Runner for Qlik-to-Power BI Multi-App Migration

Manages checkpoint-based resumption, allowing interrupted migrations to resume from last successful checkpoint.
Used by migrate.py with --batch-manifest and --resume-from flags.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from enum import Enum


class CheckpointStatus(Enum):
    """Status of a checkpoint entry."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CheckpointEntry:
    """Single entry in a checkpoint file."""
    app_id: str
    source_path: str
    status: CheckpointStatus
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    output_dir: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "source_path": self.source_path,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "output_dir": self.output_dir
        }


@dataclass
class Checkpoint:
    """Checkpoint tracking for batch migration."""
    wave_id: str
    created_at: str
    manifest_file: str
    entries: List[CheckpointEntry]
    completed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    total_duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave_id": self.wave_id,
            "created_at": self.created_at,
            "manifest_file": self.manifest_file,
            "entries": [e.to_dict() for e in self.entries],
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "total_duration_seconds": self.total_duration_seconds
        }


class BatchRunner:
    """Manages checkpoint-based batch migration with resumption capability."""
    
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        """Initialize batch runner."""
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.current_checkpoint: Optional[Checkpoint] = None
    
    def create_checkpoint(
        self,
        wave_id: str,
        manifest_file: str,
        manifest_entries: List[Dict[str, Any]]
    ) -> Checkpoint:
        """Create new checkpoint from manifest entries."""
        checkpoint = Checkpoint(
            wave_id=wave_id,
            created_at=datetime.utcnow().isoformat(),
            manifest_file=manifest_file,
            entries=[
                CheckpointEntry(
                    app_id=entry.get("app_id"),
                    source_path=entry.get("source"),
                    status=CheckpointStatus.PENDING,
                    output_dir=entry.get("output_dir")
                )
                for entry in manifest_entries
            ]
        )
        self.current_checkpoint = checkpoint
        self._save_checkpoint(checkpoint)
        return checkpoint
    
    def load_checkpoint(self, checkpoint_file: str) -> Checkpoint:
        """Load checkpoint from file."""
        checkpoint_path = self.checkpoint_dir / checkpoint_file
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        with open(checkpoint_path, "r") as f:
            data = json.load(f)
        
        checkpoint = Checkpoint(
            wave_id=data["wave_id"],
            created_at=data["created_at"],
            manifest_file=data["manifest_file"],
            entries=[
                CheckpointEntry(
                    app_id=e["app_id"],
                    source_path=e["source_path"],
                    status=CheckpointStatus(e["status"]),
                    started_at=e.get("started_at"),
                    completed_at=e.get("completed_at"),
                    duration_seconds=e.get("duration_seconds"),
                    error_message=e.get("error_message"),
                    output_dir=e.get("output_dir")
                )
                for e in data["entries"]
            ],
            completed_count=data.get("completed_count", 0),
            failed_count=data.get("failed_count", 0),
            skipped_count=data.get("skipped_count", 0),
            total_duration_seconds=data.get("total_duration_seconds", 0.0)
        )
        self.current_checkpoint = checkpoint
        return checkpoint
    
    def get_pending_entries(self) -> List[CheckpointEntry]:
        """Get list of pending entries to process."""
        if not self.current_checkpoint:
            return []
        
        return [
            e for e in self.current_checkpoint.entries
            if e.status == CheckpointStatus.PENDING
        ]
    
    def mark_in_progress(self, app_id: str):
        """Mark entry as in-progress."""
        if not self.current_checkpoint:
            return
        
        for entry in self.current_checkpoint.entries:
            if entry.app_id == app_id:
                entry.status = CheckpointStatus.IN_PROGRESS
                entry.started_at = datetime.utcnow().isoformat()
                self._save_checkpoint(self.current_checkpoint)
                break
    
    def mark_completed(
        self,
        app_id: str,
        duration_seconds: float,
        output_dir: Optional[str] = None
    ):
        """Mark entry as completed."""
        if not self.current_checkpoint:
            return
        
        for entry in self.current_checkpoint.entries:
            if entry.app_id == app_id:
                entry.status = CheckpointStatus.COMPLETED
                entry.completed_at = datetime.utcnow().isoformat()
                entry.duration_seconds = duration_seconds
                entry.output_dir = output_dir
                
                # Update counters
                self.current_checkpoint.completed_count += 1
                self.current_checkpoint.total_duration_seconds += duration_seconds
                self._save_checkpoint(self.current_checkpoint)
                break
    
    def mark_failed(self, app_id: str, error_message: str):
        """Mark entry as failed."""
        if not self.current_checkpoint:
            return
        
        for entry in self.current_checkpoint.entries:
            if entry.app_id == app_id:
                entry.status = CheckpointStatus.FAILED
                entry.completed_at = datetime.utcnow().isoformat()
                entry.error_message = error_message
                
                # Update counters
                self.current_checkpoint.failed_count += 1
                self._save_checkpoint(self.current_checkpoint)
                break
    
    def mark_skipped(self, app_id: str, reason: str):
        """Mark entry as skipped."""
        if not self.current_checkpoint:
            return
        
        for entry in self.current_checkpoint.entries:
            if entry.app_id == app_id:
                entry.status = CheckpointStatus.SKIPPED
                entry.completed_at = datetime.utcnow().isoformat()
                entry.error_message = reason
                
                # Update counters
                self.current_checkpoint.skipped_count += 1
                self._save_checkpoint(self.current_checkpoint)
                break
    
    def get_summary(self) -> Dict[str, Any]:
        """Get checkpoint summary statistics."""
        if not self.current_checkpoint:
            return {}
        
        total = len(self.current_checkpoint.entries)
        completed = self.current_checkpoint.completed_count
        failed = self.current_checkpoint.failed_count
        skipped = self.current_checkpoint.skipped_count
        pending = total - completed - failed - skipped
        
        return {
            "wave_id": self.current_checkpoint.wave_id,
            "total_entries": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "pending": pending,
            "completion_percentage": (completed / total * 100) if total > 0 else 0,
            "total_duration_seconds": self.current_checkpoint.total_duration_seconds,
            "estimated_remaining_minutes": self._estimate_remaining_time()
        }
    
    def _estimate_remaining_time(self) -> float:
        """Estimate remaining time based on average duration."""
        if not self.current_checkpoint:
            return 0.0
        
        completed = self.current_checkpoint.completed_count
        if completed == 0:
            return 0.0
        
        avg_duration = self.current_checkpoint.total_duration_seconds / completed
        pending = len([e for e in self.current_checkpoint.entries if e.status == CheckpointStatus.PENDING])
        
        return (avg_duration * pending) / 60  # Return minutes
    
    def _save_checkpoint(self, checkpoint: Checkpoint):
        """Save checkpoint to file."""
        filename = f"{checkpoint.wave_id}_checkpoint.json"
        filepath = self.checkpoint_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        
        self.logger.info(f"Checkpoint saved: {filepath}")
    
    def generate_summary_report(self, output_file: str = "batch_summary.json"):
        """Generate summary report."""
        if not self.current_checkpoint:
            return None
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "checkpoint": self.current_checkpoint.to_dict(),
            "summary": self.get_summary()
        }
        
        # Save report
        report_path = self.checkpoint_dir / output_file
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return report_path
    
    def cleanup_checkpoint(self, checkpoint_file: str):
        """Delete checkpoint file after successful completion."""
        checkpoint_path = self.checkpoint_dir / checkpoint_file
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            self.logger.info(f"Checkpoint cleaned up: {checkpoint_path}")


# Example usage functions
def example_checkpoint_workflow():
    """Example of checkpoint-based batch migration workflow."""
    runner = BatchRunner()
    
    # Create checkpoint from manifest
    manifest_entries = [
        {"app_id": "app_1", "source": "app_1.qvf", "output_dir": "output/app_1_pbip"},
        {"app_id": "app_2", "source": "app_2.qvf", "output_dir": "output/app_2_pbip"},
    ]
    checkpoint = runner.create_checkpoint("Wave-0", "wave_manifest.json", manifest_entries)
    
    # Process entries
    for entry in runner.get_pending_entries():
        runner.mark_in_progress(entry.app_id)
        try:
            # Do migration work here
            duration = 120.0  # Simulated
            runner.mark_completed(entry.app_id, duration, entry.output_dir)
        except Exception as e:
            runner.mark_failed(entry.app_id, str(e))
    
    # Print summary
    print(json.dumps(runner.get_summary(), indent=2))


if __name__ == "__main__":
    example_checkpoint_workflow()
