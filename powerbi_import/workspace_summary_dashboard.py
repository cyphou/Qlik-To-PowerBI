"""
Workspace Summary Dashboard for Qlik-to-Power BI Migration

Generates HTML dashboard with migration metrics and quality overview.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class WorkspaceSummaryDashboard:
    """Generates HTML summary dashboard."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_dashboard(self, metrics: Dict, output_path: str) -> None:
        """Generate dashboard HTML."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Migration Summary - {metrics.get('workspace_name', 'Unknown')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f5f7fa; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 2em; margin-bottom: 10px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .metric {{ text-align: center; }}
        .metric-value {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
        .metric-label {{ color: #666; font-size: 0.9em; margin-top: 5px; }}
        .status {{ display: inline-block; padding: 5px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }}
        .status-pass {{ background: #4caf50; color: white; }}
        .status-warn {{ background: #ff9800; color: white; }}
        .status-fail {{ background: #f44336; color: white; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #667eea; color: white; }}
        .progress {{ width: 100%; height: 20px; background: #eee; border-radius: 10px; overflow: hidden; }}
        .progress-bar {{ height: 100%; background: #667eea; transition: width 0.3s; }}
        footer {{ text-align: center; color: #999; margin-top: 30px; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Migration Summary Dashboard</h1>
            <p>Workspace: {metrics.get('workspace_name', 'Unknown')} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="metric">
                    <div class="metric-value">{metrics.get('total_apps', 0)}</div>
                    <div class="metric-label">Total Applications</div>
                </div>
            </div>
            <div class="card">
                <div class="metric">
                    <div class="metric-value">{metrics.get('completed_apps', 0)}</div>
                    <div class="metric-label">Completed</div>
                    <div class="progress">
                        <div class="progress-bar" style="width: {(metrics.get('completed_apps', 0) / max(metrics.get('total_apps', 1), 1) * 100)}%"></div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="metric">
                    <div class="metric-value">{metrics.get('avg_fidelity', 0):.0f}%</div>
                    <div class="metric-label">Average Fidelity</div>
                </div>
            </div>
            <div class="card">
                <div class="metric">
                    <div class="metric-value">{metrics.get('total_errors', 0)}</div>
                    <div class="metric-label">Critical Errors</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Application Status</h2>
            <table>
                <tr>
                    <th>Application</th>
                    <th>Status</th>
                    <th>Fidelity</th>
                    <th>Tables</th>
                    <th>Measures</th>
                </tr>
        """
        
        for app in metrics.get('apps', []):
            status_class = 'status-pass' if app.get('passed') else 'status-fail'
            status_text = 'PASS' if app.get('passed') else 'FAIL'
            
            html += f"""
                <tr>
                    <td>{app.get('name', 'Unknown')}</td>
                    <td><span class="status {status_class}">{status_text}</span></td>
                    <td>{app.get('fidelity', 0):.0f}%</td>
                    <td>{app.get('table_count', 0)}</td>
                    <td>{app.get('measure_count', 0)}</td>
                </tr>
            """
        
        html += """
            </table>
        </div>
        
        <footer>
            <p>This dashboard is auto-generated. For detailed reports, see the output directory.</p>
        </footer>
    </div>
</body>
</html>"""
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        self.logger.info(f"Saved dashboard to {output_path}")


class GateReportAggregator:
    """Aggregates gate reports into portfolio view."""
    
    def aggregate(self, gate_reports: List[Dict]) -> Dict:
        """Aggregate multiple gate reports."""
        return {
            "total_apps": len(gate_reports),
            "passed_apps": sum(1 for r in gate_reports if r.get("overall_passed")),
            "failed_apps": sum(1 for r in gate_reports if not r.get("overall_passed")),
            "by_environment": {
                "dev": sum(1 for r in gate_reports if r.get("environment") == "dev"),
                "test": sum(1 for r in gate_reports if r.get("environment") == "test"),
                "prod": sum(1 for r in gate_reports if r.get("environment") == "prod")
            }
        }


if __name__ == "__main__":
    dashboard = WorkspaceSummaryDashboard()
    metrics = {
        "workspace_name": "Sales Analytics",
        "total_apps": 15,
        "completed_apps": 12,
        "avg_fidelity": 87.5,
        "total_errors": 2,
        "apps": [
            {"name": "SalesApp", "passed": True, "fidelity": 92, "table_count": 5, "measure_count": 20},
            {"name": "HRApp", "passed": False, "fidelity": 75, "table_count": 3, "measure_count": 10}
        ]
    }
    dashboard.generate_dashboard(metrics, "output/dashboard.html")
