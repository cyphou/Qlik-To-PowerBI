"""
Quality Gates System for Qlik-to-Power BI Migration

Implements Dev/Test/Prod validation gates to block low-quality deployments.
Provides comprehensive pre-deployment checks and compliance validation.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
from pathlib import Path


class GateEnvironment(Enum):
    """Deployment environment."""
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class GateSeverity(Enum):
    """Gate check severity."""
    CRITICAL = "critical"  # Always blocks
    HIGH = "high"  # Blocks prod, warning elsewhere
    MEDIUM = "medium"  # Warning, allow with approval
    LOW = "low"  # Info only


@dataclass
class GateCheckResult:
    """Result of a single gate check."""
    check_id: str
    check_name: str
    environment: GateEnvironment
    severity: GateSeverity
    passed: bool
    message: str
    remediation: Optional[str] = None


@dataclass
class GatePass:
    """Complete gate pass result."""
    app_id: str
    environment: GateEnvironment
    overall_passed: bool
    check_results: List[GateCheckResult] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    approval_required: bool = False
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "app_id": self.app_id,
            "environment": self.environment.value,
            "overall_passed": self.overall_passed,
            "check_count": len(self.check_results),
            "passed_checks": sum(1 for c in self.check_results if c.passed),
            "failed_checks": sum(1 for c in self.check_results if not c.passed),
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "approval_required": self.approval_required,
            "approved_by": self.approved_by,
            "details": [
                {
                    "check_id": c.check_id,
                    "check_name": c.check_name,
                    "severity": c.severity.value,
                    "passed": c.passed,
                    "message": c.message,
                    "remediation": c.remediation
                }
                for c in self.check_results
            ]
        }


class QualityGate:
    """Quality gate system with environment-specific rules."""
    
    # Gate thresholds per environment
    GATE_CONFIG = {
        GateEnvironment.DEV: {
            "min_fidelity": 70,
            "require_rls_audit": False,
            "require_rls_audit_profiles": [],
            "require_image_audit": False,
            "require_m_query_review": False,
            "allow_warnings": True
        },
        GateEnvironment.TEST: {
            "min_fidelity": 85,
            "require_rls_audit": True,
            "require_rls_audit_profiles": ["strict", "regulated"],
            "require_image_audit": False,
            "require_m_query_review": False,
            "allow_warnings": False
        },
        GateEnvironment.PROD: {
            "min_fidelity": 90,
            "require_rls_audit": True,
            "require_rls_audit_profiles": ["strict", "regulated"],
            "require_image_audit": True,
            "require_m_query_review": True,
            "allow_warnings": False
        }
    }
    
    def __init__(self):
        """Initialize quality gate."""
        self.logger = logging.getLogger(__name__)
        self.custom_checks: Dict[str, Callable] = {}
    
    def evaluate(
        self,
        app_id: str,
        environment: GateEnvironment,
        metrics: Dict
    ) -> GatePass:
        """
        Evaluate app against quality gate.
        
        Args:
            app_id: Application ID
            environment: Target environment (dev/test/prod)
            metrics: Metrics from migration (fidelity, validation results, etc.)
        
        Returns:
            GatePass with results
        """
        gate_pass = GatePass(
            app_id=app_id,
            environment=environment,
            overall_passed=True
        )
        
        config = self.GATE_CONFIG[environment]
        
        # Run all gate checks
        self._check_fidelity(gate_pass, metrics, config)
        self._check_errors(gate_pass, metrics, environment)
        self._check_security(gate_pass, metrics, config)
        self._check_artifacts(gate_pass, metrics, config)
        self._check_performance(gate_pass, metrics, environment)

        # Determine blocking severity by environment.
        if environment == GateEnvironment.DEV:
            blocking_severities = {GateSeverity.CRITICAL}
        else:
            blocking_severities = {GateSeverity.CRITICAL, GateSeverity.HIGH}

        blocking_failures = [
            c for c in gate_pass.check_results
            if not c.passed and c.severity in blocking_severities
        ]

        gate_pass.overall_passed = len(blocking_failures) == 0
        gate_pass.blocked_reasons = [c.message for c in blocking_failures]

        # Prod failures require explicit approval workflow.
        if environment == GateEnvironment.PROD and blocking_failures:
            gate_pass.approval_required = True
        
        self.logger.info(
            f"Gate evaluation for {app_id} ({environment.value}): "
            f"passed={gate_pass.overall_passed}, "
            f"warnings={len(gate_pass.warnings)}"
        )
        
        return gate_pass
    
    def _check_fidelity(
        self,
        gate_pass: GatePass,
        metrics: Dict,
        config: Dict
    ) -> None:
        """Check fidelity against minimum threshold."""
        fidelity = metrics.get("fidelity_score", 0)
        min_fidelity = config["min_fidelity"]
        
        passed = fidelity >= min_fidelity
        severity = GateSeverity.HIGH if not passed else GateSeverity.LOW
        
        result = GateCheckResult(
            check_id="fidelity",
            check_name="Fidelity Score",
            environment=gate_pass.environment,
            severity=severity,
            passed=passed,
            message=f"Fidelity score {fidelity}% {'meets' if passed else 'below'} "
                    f"threshold of {min_fidelity}%",
            remediation="Review and fix low-fidelity measures or calculations"
                        if not passed else None
        )
        gate_pass.check_results.append(result)
        
        if not passed:
            gate_pass.blocked_reasons.append(result.message)
    
    def _check_errors(
        self,
        gate_pass: GatePass,
        metrics: Dict,
        environment: GateEnvironment
    ) -> None:
        """Check for critical errors."""
        error_count = metrics.get("error_count", 0)
        
        # Critical errors always block
        passed = error_count == 0
        
        result = GateCheckResult(
            check_id="errors",
            check_name="Critical Errors",
            environment=environment,
            severity=GateSeverity.CRITICAL,
            passed=passed,
            message=f"Found {error_count} critical errors" if not passed else "No critical errors",
            remediation="Fix all critical errors before deployment" if not passed else None
        )
        gate_pass.check_results.append(result)
        
        if not passed:
            gate_pass.blocked_reasons.append(result.message)
    
    def _check_security(
        self,
        gate_pass: GatePass,
        metrics: Dict,
        config: Dict
    ) -> None:
        """Check security controls."""
        profile = str(metrics.get("migration_profile", "") or "").strip().lower()
        rls_profiles = {
            str(p).strip().lower()
            for p in config.get("require_rls_audit_profiles", [])
            if str(p).strip()
        }
        should_require_rls_audit = (
            config.get("require_rls_audit")
            and (not rls_profiles or not profile or profile in rls_profiles)
        )

        # RLS/OLS audit
        if should_require_rls_audit:
            rls_audited = metrics.get("rls_audit_passed", False)
            
            result = GateCheckResult(
                check_id="rls_audit",
                check_name="RLS Audit",
                environment=gate_pass.environment,
                severity=GateSeverity.HIGH,
                passed=rls_audited,
                message="RLS configuration audited and approved" if rls_audited 
                        else "RLS audit required before prod deployment",
                remediation="Run security audit checklist" if not rls_audited else None
            )
            gate_pass.check_results.append(result)
            
            if not rls_audited and gate_pass.environment == GateEnvironment.PROD:
                gate_pass.blocked_reasons.append(result.message)
        
        # PII detection
        pii_found = metrics.get("pii_fields_detected", 0) > 0
        pii_masked = metrics.get("pii_fields_masked", 0) == metrics.get("pii_fields_detected", 0)
        
        pii_passed = not pii_found or pii_masked
        
        result = GateCheckResult(
            check_id="pii_handling",
            check_name="PII Data Handling",
            environment=gate_pass.environment,
            severity=GateSeverity.CRITICAL if not pii_passed else GateSeverity.LOW,
            passed=pii_passed,
            message=f"PII detected: {metrics.get('pii_fields_detected', 0)}, "
                    f"masked: {metrics.get('pii_fields_masked', 0)}"
                    if pii_found else "No PII fields detected",
            remediation="Mask or exclude all PII before deployment" if not pii_passed else None
        )
        gate_pass.check_results.append(result)
        
        if not pii_passed:
            gate_pass.blocked_reasons.append(result.message)
    
    def _check_artifacts(
        self,
        gate_pass: GatePass,
        metrics: Dict,
        config: Dict
    ) -> None:
        """Check artifact completeness."""
        # Image audit
        if config.get("require_image_audit"):
            images_count = metrics.get("image_count", 0)
            images_reviewed = metrics.get("images_reviewed", True)
            
            passed = images_reviewed or images_count == 0
            
            result = GateCheckResult(
                check_id="images",
                check_name="Image Audit",
                environment=gate_pass.environment,
                severity=GateSeverity.MEDIUM,
                passed=passed,
                message=f"Found {images_count} images, review status: {images_reviewed}",
                remediation="Review and validate all embedded images" if not passed else None
            )
            gate_pass.check_results.append(result)
            
            if not passed:
                gate_pass.warnings.append(result.message)
        
        # M query review
        if config.get("require_m_query_review"):
            m_queries = metrics.get("m_query_count", 0)
            m_reviewed = metrics.get("m_queries_reviewed", True)
            
            passed = m_reviewed or m_queries == 0
            
            result = GateCheckResult(
                check_id="m_queries",
                check_name="Power Query M Review",
                environment=gate_pass.environment,
                severity=GateSeverity.MEDIUM,
                passed=passed,
                message=f"Found {m_queries} M scripts, review status: {m_reviewed}",
                remediation="Review M query logic for performance and correctness" if not passed else None
            )
            gate_pass.check_results.append(result)
            
            if not passed:
                gate_pass.warnings.append(result.message)
    
    def _check_performance(
        self,
        gate_pass: GatePass,
        metrics: Dict,
        environment: GateEnvironment
    ) -> None:
        """Check performance metrics."""
        # Measure count warnings
        measure_count = metrics.get("measure_count", 0)
        warning_threshold = 200  # Warn if >200 measures
        
        warning = measure_count > warning_threshold
        
        result = GateCheckResult(
            check_id="measure_count",
            check_name="Measure Count",
            environment=environment,
            severity=GateSeverity.LOW,
            passed=not warning,
            message=f"Found {measure_count} measures" +
                    (f" (over threshold of {warning_threshold})" if warning else ""),
            remediation="Consider consolidating or archiving unused measures" if warning else None
        )
        gate_pass.check_results.append(result)
        
        if warning:
            gate_pass.warnings.append(result.message)
    
    def register_custom_check(
        self,
        check_id: str,
        check_func: Callable[[Dict, GateEnvironment], GateCheckResult]
    ) -> None:
        """Register custom check function."""
        self.custom_checks[check_id] = check_func
        self.logger.info(f"Registered custom check: {check_id}")


class GateReportGenerator:
    """Generates gate pass reports."""
    
    def __init__(self):
        """Initialize reporter."""
        self.logger = logging.getLogger(__name__)
    
    def save_report(self, gate_pass: GatePass, output_path: str) -> None:
        """Save gate pass report to JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(gate_pass.to_dict(), f, indent=2)
        
        self.logger.info(f"Saved gate report to {output_path}")
    
    def generate_html_report(self, gate_pass: GatePass, output_path: str) -> None:
        """Generate HTML gate pass report."""
        status_color = "green" if gate_pass.overall_passed else "red"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset=\"utf-8\" />
            <title>Quality Gate Report - {gate_pass.app_id}</title>
            <style>
                body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
                .header {{ background: {status_color}; color: white; padding: 20px; border-radius: 5px; }}
                .check {{ margin: 10px 0; padding: 10px; border-left: 4px solid #ccc; }}
                .passed {{ border-color: green; }}
                .failed {{ border-color: red; }}
                .warning {{ border-color: orange; }}
                .check-name {{ font-weight: bold; }}
                .severity {{ display: inline-block; padding: 2px 5px; border-radius: 3px; font-size: 0.8em; }}
                .critical {{ background: #d32f2f; color: white; }}
                .high {{ background: #f57c00; color: white; }}
                .medium {{ background: #fbc02d; color: #333; }}
                .low {{ background: #4caf50; color: white; }}
                .remediation {{ font-size: 0.9em; color: #666; margin-top: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Quality Gate: {gate_pass.app_id}</h1>
                <p>Environment: {gate_pass.environment.value}</p>
                <p>Status: {'PASSED ✓' if gate_pass.overall_passed else 'FAILED ✗'}</p>
            </div>
            
            <h2>Summary</h2>
            <p>Passed: {sum(1 for c in gate_pass.check_results if c.passed)} / {len(gate_pass.check_results)}</p>
            
            <h2>Checks</h2>
        """
        
        for check in gate_pass.check_results:
            status_class = "passed" if check.passed else "failed"
            html += f"""
            <div class="check {status_class}">
                <div class="check-name">
                    {check.check_name}
                    <span class="severity {check.severity.value.lower()}">{check.severity.value}</span>
                </div>
                <p>{check.message}</p>
        """
            if check.remediation:
                html += f'<div class="remediation">Remediation: {check.remediation}</div>'
            html += "</div>"
        
        html += "</body></html>"
        
        output_path = Path(output_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        self.logger.info(f"Saved HTML gate report to {output_path}")


# Example usage
if __name__ == "__main__":
    gate = QualityGate()
    
    metrics = {
        "fidelity_score": 87,
        "error_count": 0,
        "rls_audit_passed": True,
        "pii_fields_detected": 2,
        "pii_fields_masked": 2,
        "image_count": 3,
        "images_reviewed": True,
        "m_query_count": 5,
        "m_queries_reviewed": True,
        "measure_count": 45
    }
    
    gate_pass = gate.evaluate("app_1", GateEnvironment.PROD, metrics)
    
    reporter = GateReportGenerator()
    reporter.save_report(gate_pass, "output/gate_pass_app_1.json")
    reporter.generate_html_report(gate_pass, "output/gate_pass_app_1.html")
    
    print(json.dumps(gate_pass.to_dict(), indent=2))
