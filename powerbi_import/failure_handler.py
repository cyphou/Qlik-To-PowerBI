"""
Failure Handler for Qlik-to-Power BI Multi-App Migration

Provides per-entry failure isolation, error classification, and recovery guidance.
Used by migrate.py with --continue-on-error flag.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from enum import Enum


class FailureSeverity(Enum):
    """Failure severity levels for remediation priority."""
    CRITICAL = "critical"      # Data loss, security breach
    HIGH = "high"              # Extraction/generation failure
    MEDIUM = "medium"          # Fidelity <70%, partial failure
    LOW = "low"                # Minor issues, workaround available


class FailurePhase(Enum):
    """Phase where failure occurred."""
    EXTRACTION = "extraction"
    GENERATION = "generation"
    VALIDATION = "validation"
    DEPLOYMENT = "deployment"


class FailureCode(Enum):
    """Standardized failure codes for classification."""
    # Extraction failures
    INVALID_QVF_FORMAT = "invalid_qvf_format"
    MISSING_DATASOURCE = "missing_datasource"
    UNSUPPORTED_CONNECTOR = "unsupported_connector"
    SCRIPT_PARSE_ERROR = "script_parse_error"
    
    # Generation failures
    UNSUPPORTED_FUNCTION = "unsupported_function"
    DAX_SYNTAX_ERROR = "dax_syntax_error"
    INVALID_RELATIONSHIP = "invalid_relationship"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    
    # Validation failures
    FIDELITY_THRESHOLD_FAILED = "fidelity_threshold_failed"
    CROSS_PLATFORM_MISMATCH = "cross_platform_mismatch"
    SECURITY_AUDIT_FAILED = "security_audit_failed"
    
    # Deployment failures
    PERMISSION_DENIED = "permission_denied"
    WORKSPACE_CAPACITY_EXCEEDED = "workspace_capacity_exceeded"
    API_RATE_LIMIT = "api_rate_limit"


@dataclass
class RemediationAction:
    """Suggested remediation for a failure."""
    action: str
    priority: str  # "immediate", "high", "medium", "low"
    estimated_effort_minutes: int
    command: Optional[str] = None
    documentation_link: Optional[str] = None


@dataclass
class FailureRecord:
    """Record of a single app failure."""
    app_id: str
    failure_phase: FailurePhase
    failure_code: FailureCode
    severity: FailureSeverity
    error_message: str
    timestamp: str
    duration_seconds: float
    input_file: str
    log_file: str
    remediation_actions: List[RemediationAction]
    retry_count: int = 0
    last_retry_timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "app_id": self.app_id,
            "failure_phase": self.failure_phase.value,
            "failure_code": self.failure_code.value,
            "severity": self.severity.value,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "input_file": self.input_file,
            "log_file": self.log_file,
            "remediation_actions": [asdict(a) for a in self.remediation_actions],
            "retry_count": self.retry_count,
            "last_retry_timestamp": self.last_retry_timestamp
        }


class FailureHandler:
    """Manages per-entry failures and recovery."""
    
    def __init__(self, output_dir: str, continue_on_error: bool = False):
        """
        Initialize failure handler.
        
        Args:
            output_dir: Directory for failure reports and logs
            continue_on_error: If True, continue on failure instead of halting
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.continue_on_error = continue_on_error
        self.failures: List[FailureRecord] = []
        self.logger = logging.getLogger(__name__)
        
    def record_failure(
        self,
        app_id: str,
        phase: FailurePhase,
        code: FailureCode,
        severity: FailureSeverity,
        error_message: str,
        input_file: str,
        duration_seconds: float,
        log_file: str,
        remediation_actions: List[RemediationAction]
    ) -> FailureRecord:
        """Record a single app failure."""
        failure = FailureRecord(
            app_id=app_id,
            failure_phase=phase,
            failure_code=code,
            severity=severity,
            error_message=error_message,
            timestamp=datetime.utcnow().isoformat(),
            duration_seconds=duration_seconds,
            input_file=input_file,
            log_file=log_file,
            remediation_actions=remediation_actions,
        )
        self.failures.append(failure)
        self.logger.warning(f"[FAILURE] {app_id}: {code.value} ({severity.value}) - {error_message}")
        return failure
    
    def should_continue(self, severity: FailureSeverity) -> bool:
        """Determine if migration should continue after failure."""
        if not self.continue_on_error:
            return False
        
        # Always halt on critical failures
        if severity == FailureSeverity.CRITICAL:
            return False
        
        return True
    
    def get_remediation_actions(self, code: FailureCode) -> List[RemediationAction]:
        """Get recommended remediation actions for a failure code."""
        actions_map = {
            FailureCode.INVALID_QVF_FORMAT: [
                RemediationAction(
                    action="Validate QVF file is a valid ZIP container",
                    priority="immediate",
                    estimated_effort_minutes=10,
                    command="powershell '[System.IO.Compression.ZipFile]::OpenRead($file)'",
                    documentation_link="docs/guides/TROUBLESHOOTING.md#invalid-qvf"
                ),
                RemediationAction(
                    action="Re-export from Qlik or restore from backup",
                    priority="high",
                    estimated_effort_minutes=30
                )
            ],
            FailureCode.UNSUPPORTED_FUNCTION: [
                RemediationAction(
                    action="Review unsupported functions in error log",
                    priority="high",
                    estimated_effort_minutes=15,
                    documentation_link="docs/QLIK_TO_DAX_REFERENCE.md"
                ),
                RemediationAction(
                    action="Apply manual fix or workaround in Power BI Desktop",
                    priority="high",
                    estimated_effort_minutes=60
                )
            ],
            FailureCode.FIDELITY_THRESHOLD_FAILED: [
                RemediationAction(
                    action="Review fidelity report for problematic measures",
                    priority="medium",
                    estimated_effort_minutes=20,
                    command="code output/{app_id}_artifacts/fidelity_report.json"
                ),
                RemediationAction(
                    action="Rerun with --repair-strategies and --self-heal-v3",
                    priority="medium",
                    estimated_effort_minutes=5,
                    command="python migrate.py app.qvf --repair-strategies --self-heal-v3"
                )
            ],
            FailureCode.PERMISSION_DENIED: [
                RemediationAction(
                    action="Check Power BI workspace permissions",
                    priority="immediate",
                    estimated_effort_minutes=10
                ),
                RemediationAction(
                    action="Contact workspace_admin@company.com for access",
                    priority="high",
                    estimated_effort_minutes=60
                )
            ]
        }
        return actions_map.get(code, [
            RemediationAction(
                action="Review error log and investigate cause",
                priority="high",
                estimated_effort_minutes=30
            )
        ])
    
    def generate_failure_report(self, output_file: str = "failure_report.json"):
        """Generate JSON failure report."""
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_failures": len(self.failures),
            "by_severity": self._group_by_severity(),
            "by_phase": self._group_by_phase(),
            "failures": [f.to_dict() for f in self.failures]
        }
        
        report_path = self.output_dir / output_file
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return report_path
    
    def _group_by_severity(self) -> Dict[str, int]:
        """Count failures by severity."""
        by_severity = {s.value: 0 for s in FailureSeverity}
        for failure in self.failures:
            by_severity[failure.severity.value] += 1
        return by_severity
    
    def _group_by_phase(self) -> Dict[str, int]:
        """Count failures by phase."""
        by_phase = {p.value: 0 for p in FailurePhase}
        for failure in self.failures:
            by_phase[failure.failure_phase.value] += 1
        return by_phase
    
    def get_retry_candidates(self) -> List[str]:
        """Get list of failed apps that should be retried."""
        # Retry medium/low severity failures, skip critical/high
        return [
            f.app_id for f in self.failures
            if f.severity in [FailureSeverity.MEDIUM, FailureSeverity.LOW]
            and f.retry_count < 3
        ]
    
    def mark_retry(self, app_id: str):
        """Mark a failure as retried."""
        for failure in self.failures:
            if failure.app_id == app_id:
                failure.retry_count += 1
                failure.last_retry_timestamp = datetime.utcnow().isoformat()


# Pre-defined remediation chains for common failure patterns
REMEDIATION_CHAINS = {
    "low_fidelity": [
        "Review fidelity report (output/{app_id}_artifacts/fidelity_report.json)",
        "Identify problematic measures",
        "Rerun with --self-heal-v3",
        "If still <85%, manual adjustment required in Power BI Desktop"
    ],
    "extraction_failure": [
        "Validate QVF file (not corrupted)",
        "Check Qlik version compatibility",
        "Re-extract from Qlik source",
        "If issue persists, escalate to Qlik admin"
    ],
    "generation_failure": [
        "Review error log for unsupported functions",
        "Check DAX expressions for syntax errors",
        "Rerun with --repair-strategies",
        "Manual fix in Power BI Desktop if needed"
    ],
    "deployment_failure": [
        "Check Power BI workspace credentials",
        "Verify workspace has capacity",
        "Test connection to Power BI Service",
        "Contact Power BI admin if issue persists"
    ]
}


def create_failure_context(app_id: str, error: Exception) -> Dict[str, Any]:
    """Create context dict from exception for logging."""
    return {
        "app_id": app_id,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat()
    }
