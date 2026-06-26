"""
Gate Report Generator for Quality Gate Results

Produces detailed remediation reports from gate failures.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from powerbi_import.quality_gates import GatePass


class GateReportGenerator:
    """Generates comprehensive gate reports."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_remediation_report(self, gate_pass: GatePass, output_path: str) -> None:
        """Generate detailed remediation report."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Sort checks by severity
        failed_checks = [c for c in gate_pass.check_results if not c.passed]
        critical = [c for c in failed_checks if c.severity.value == "critical"]
        high = [c for c in failed_checks if c.severity.value == "high"]
        medium = [c for c in failed_checks if c.severity.value == "medium"]
        
        report = {
            "app_id": gate_pass.app_id,
            "environment": gate_pass.environment.value,
            "status": "PASS" if gate_pass.overall_passed else "FAIL",
            "summary": {
                "total_checks": len(gate_pass.check_results),
                "passed": sum(1 for c in gate_pass.check_results if c.passed),
                "failed": len(failed_checks),
                "critical": len(critical),
                "high": len(high),
                "medium": len(medium)
            },
            "critical_issues": [
                {
                    "check": c.check_name,
                    "message": c.message,
                    "remediation": c.remediation,
                    "estimated_effort": "1-2 hours"
                }
                for c in critical
            ],
            "high_priority_issues": [
                {
                    "check": c.check_name,
                    "message": c.message,
                    "remediation": c.remediation
                }
                for c in high
            ],
            "next_steps": self._generate_next_steps(gate_pass)
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"Saved remediation report to {output_path}")
    
    def _generate_next_steps(self, gate_pass: GatePass) -> List[str]:
        """Generate prioritized remediation steps."""
        steps = []
        
        for check in gate_pass.check_results:
            if not check.passed and check.remediation:
                steps.append(f"- {check.check_name}: {check.remediation}")
        
        return steps if steps else ["No remediation required."]


if __name__ == "__main__":
    pass
