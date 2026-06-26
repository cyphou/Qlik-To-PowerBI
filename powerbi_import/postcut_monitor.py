"""
Post-Cutover Monitor for Qlik-to-Power BI Migration

Validates production health and user adoption 24–72 hours after deployment.
Generates alerts and remediation recommendations.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum


class HealthStatus(Enum):
    """Health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass
class HealthMetric:
    """Single health metric."""
    name: str
    current_value: float
    baseline_value: float
    threshold_warning: float
    threshold_critical: float
    unit: str
    status: HealthStatus
    trend: str  # "improving" | "stable" | "degrading"


class PostcutoverMonitor:
    """Monitors post-cutover health."""
    
    # Thresholds
    THRESHOLDS = {
        "refresh_success_rate": {"warning": 95, "critical": 90},
        "error_rate": {"warning": 1, "critical": 5},
        "response_time_avg_ms": {"warning": 2000, "critical": 5000},
        "dataset_size_mb": {"warning": 110, "critical": 150},  # % of baseline
        "user_adoption_percent": {"warning": 50, "critical": 25},
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def check_refresh_health(self, metrics: Dict) -> HealthMetric:
        """Check refresh job health."""
        success_rate = metrics.get("refresh_success_rate", 100)
        baseline = 100
        
        if success_rate >= self.THRESHOLDS["refresh_success_rate"]["warning"]:
            status = HealthStatus.HEALTHY
        elif success_rate >= self.THRESHOLDS["refresh_success_rate"]["critical"]:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.CRITICAL
        
        return HealthMetric(
            name="Refresh Success Rate",
            current_value=success_rate,
            baseline_value=baseline,
            threshold_warning=self.THRESHOLDS["refresh_success_rate"]["warning"],
            threshold_critical=self.THRESHOLDS["refresh_success_rate"]["critical"],
            unit="%",
            status=status,
            trend=metrics.get("refresh_trend", "stable")
        )
    
    def check_error_health(self, metrics: Dict) -> HealthMetric:
        """Check error rate health."""
        error_rate = metrics.get("error_rate", 0)
        baseline = 0.5  # Expected 0.5% baseline error rate
        
        if error_rate <= self.THRESHOLDS["error_rate"]["warning"]:
            status = HealthStatus.HEALTHY
        elif error_rate <= self.THRESHOLDS["error_rate"]["critical"]:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.CRITICAL
        
        return HealthMetric(
            name="Error Rate",
            current_value=error_rate,
            baseline_value=baseline,
            threshold_warning=self.THRESHOLDS["error_rate"]["warning"],
            threshold_critical=self.THRESHOLDS["error_rate"]["critical"],
            unit="%",
            status=status,
            trend=metrics.get("error_trend", "stable")
        )
    
    def check_response_time(self, metrics: Dict) -> HealthMetric:
        """Check response time health."""
        response_time = metrics.get("response_time_avg_ms", 1500)
        baseline = 1500
        
        if response_time <= self.THRESHOLDS["response_time_avg_ms"]["warning"]:
            status = HealthStatus.HEALTHY
        elif response_time <= self.THRESHOLDS["response_time_avg_ms"]["critical"]:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.CRITICAL
        
        return HealthMetric(
            name="Response Time (avg)",
            current_value=response_time,
            baseline_value=baseline,
            threshold_warning=self.THRESHOLDS["response_time_avg_ms"]["warning"],
            threshold_critical=self.THRESHOLDS["response_time_avg_ms"]["critical"],
            unit="ms",
            status=status,
            trend=metrics.get("response_time_trend", "stable")
        )
    
    def check_dataset_size(self, metrics: Dict) -> HealthMetric:
        """Check dataset size health."""
        current_size = metrics.get("dataset_size_mb", 500)
        baseline_size = metrics.get("baseline_dataset_size_mb", 500)
        size_percent = (current_size / baseline_size * 100) if baseline_size else 100
        
        if size_percent <= self.THRESHOLDS["dataset_size_mb"]["warning"]:
            status = HealthStatus.HEALTHY
        elif size_percent <= self.THRESHOLDS["dataset_size_mb"]["critical"]:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.CRITICAL
        
        return HealthMetric(
            name="Dataset Size",
            current_value=size_percent,
            baseline_value=100,
            threshold_warning=self.THRESHOLDS["dataset_size_mb"]["warning"],
            threshold_critical=self.THRESHOLDS["dataset_size_mb"]["critical"],
            unit="% of baseline",
            status=status,
            trend=metrics.get("dataset_size_trend", "stable")
        )
    
    def check_user_adoption(self, metrics: Dict) -> HealthMetric:
        """Check user adoption health."""
        adoption = metrics.get("user_adoption_percent", 50)
        baseline = 0  # Starting at 0% at deployment
        
        if adoption >= 75:
            status = HealthStatus.HEALTHY
        elif adoption >= self.THRESHOLDS["user_adoption_percent"]["warning"]:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.CRITICAL
        
        return HealthMetric(
            name="User Adoption",
            current_value=adoption,
            baseline_value=baseline,
            threshold_warning=self.THRESHOLDS["user_adoption_percent"]["warning"],
            threshold_critical=self.THRESHOLDS["user_adoption_percent"]["critical"],
            unit="%",
            status=status,
            trend=metrics.get("adoption_trend", "improving")
        )
    
    def generate_report(self, metrics: Dict) -> Dict:
        """Generate comprehensive health report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "hours_since_deployment": metrics.get("hours_since_deployment", 24),
            "overall_status": HealthStatus.HEALTHY.value,
            "metrics": []
        }
        
        # Check all metrics
        health_checks = [
            self.check_refresh_health(metrics),
            self.check_error_health(metrics),
            self.check_response_time(metrics),
            self.check_dataset_size(metrics),
            self.check_user_adoption(metrics)
        ]
        
        # Determine overall status
        statuses = [check.status for check in health_checks]
        if any(s == HealthStatus.CRITICAL for s in statuses):
            report["overall_status"] = HealthStatus.CRITICAL.value
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            report["overall_status"] = HealthStatus.DEGRADED.value
        
        # Add metrics to report
        for check in health_checks:
            report["metrics"].append({
                "name": check.name,
                "current": check.current_value,
                "baseline": check.baseline_value,
                "unit": check.unit,
                "status": check.status.value,
                "trend": check.trend,
                "threshold_warning": check.threshold_warning,
                "threshold_critical": check.threshold_critical
            })
        
        # Generate recommendations
        report["recommendations"] = self._generate_recommendations(health_checks, metrics)
        
        return report
    
    def _generate_recommendations(self, health_checks: List[HealthMetric], metrics: Dict) -> List[str]:
        """Generate remediation recommendations."""
        recommendations = []
        
        for check in health_checks:
            if check.status == HealthStatus.CRITICAL:
                if "Refresh" in check.name and check.current_value < check.threshold_critical:
                    recommendations.append(
                        f"🔴 CRITICAL: Refresh success rate {check.current_value}% is below threshold. "
                        "Check dataset refresh logs and connection credentials."
                    )
                
                if "Error Rate" in check.name:
                    recommendations.append(
                        f"🔴 CRITICAL: Error rate {check.current_value}% is elevated. "
                        "Review Application Insights logs and check for data issues."
                    )
                
                if "Response Time" in check.name:
                    recommendations.append(
                        f"🔴 CRITICAL: Response time {check.current_value}ms is too slow. "
                        "Consider scaling capacity or optimizing DAX queries."
                    )
                
                if "Dataset Size" in check.name:
                    recommendations.append(
                        f"🔴 CRITICAL: Dataset size grew to {check.current_value}% of baseline. "
                        "Investigate unnecessary columns or aggregations."
                    )
            
            elif check.status == HealthStatus.DEGRADED:
                if "User Adoption" in check.name:
                    recommendations.append(
                        f"⚠️ WARNING: User adoption is only {check.current_value}%. "
                        "Send reminder emails and offer training sessions."
                    )
                
                if "Response Time" in check.name:
                    recommendations.append(
                        f"⚠️ WARNING: Response time {check.current_value}ms is slightly elevated. "
                        "Monitor trends; escalate if continues to increase."
                    )
        
        if not recommendations:
            recommendations.append("✅ No critical issues detected. Continue monitoring.")
        
        return recommendations
    
    def generate_html_report(self, report: Dict, output_path: str) -> None:
        """Generate HTML health report."""
        status_color = {
            "healthy": "#4caf50",
            "degraded": "#ff9800",
            "critical": "#f44336"
        }
        
        color = status_color.get(report["overall_status"], "#999")
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Post-Cutover Health Report</title>
    <style>
        body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
        .header {{ background: {color}; color: white; padding: 20px; border-radius: 5px; }}
        .metric {{ margin: 15px 0; padding: 10px; background: white; border-radius: 5px; }}
        .recommendation {{ margin: 10px 0; padding: 10px; border-left: 4px solid #666; }}
        .critical {{ border-left-color: #f44336; background: #ffebee; }}
        .warning {{ border-left-color: #ff9800; background: #fff3e0; }}
        .info {{ border-left-color: #4caf50; background: #e8f5e9; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Post-Cutover Health Report</h1>
        <p>Status: {report["overall_status"].upper()}</p>
        <p>Generated: {report["timestamp"]}</p>
        <p>Hours since deployment: {report["hours_since_deployment"]}</p>
    </div>
    
    <h2>Metrics Summary</h2>
"""
        
        for metric in report["metrics"]:
            html += f"""
    <div class="metric">
        <h3>{metric["name"]}</h3>
        <p>Current: {metric["current"]}{metric["unit"]}</p>
        <p>Baseline: {metric["baseline"]}{metric["unit"]}</p>
        <p>Status: <strong>{metric["status"].upper()}</strong></p>
        <p>Trend: {metric["trend"]}</p>
    </div>
"""
        
        html += "<h2>Recommendations</h2>"
        
        for rec in report["recommendations"]:
            css_class = "info"
            if "CRITICAL" in rec:
                css_class = "critical"
            elif "WARNING" in rec:
                css_class = "warning"
            
            html += f'<div class="recommendation {css_class}">{rec}</div>'
        
        html += "</body></html>"
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        self.logger.info(f"Saved HTML report to {output_path}")


# Example usage
if __name__ == "__main__":
    monitor = PostcutoverMonitor()
    
    metrics = {
        "refresh_success_rate": 98,
        "refresh_trend": "stable",
        "error_rate": 0.8,
        "error_trend": "stable",
        "response_time_avg_ms": 1800,
        "response_time_trend": "stable",
        "dataset_size_mb": 550,
        "baseline_dataset_size_mb": 500,
        "dataset_size_trend": "stable",
        "user_adoption_percent": 65,
        "adoption_trend": "improving",
        "hours_since_deployment": 24
    }
    
    report = monitor.generate_report(metrics)
    print(json.dumps(report, indent=2))
    
    monitor.generate_html_report(report, "output/postcut_health_report.html")
