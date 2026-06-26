"""
Wave Control Dashboard for Multi-Wave Migration Orchestration

Real-time visualization of wave status, bottlenecks, and decision points.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class WaveControlDashboard:
    """Generates wave control dashboard."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_dashboard(self, wave_status: Dict, output_path: str) -> None:
        """Generate wave control dashboard HTML."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Wave Control Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #1e1e1e; color: #ddd; }}
        .container {{ max-width: 1600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2d2d30; padding: 20px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #3e3e42; }}
        .header h1 {{ color: #4ec9b0; font-size: 2em; margin-bottom: 10px; }}
        .timestamp {{ color: #858585; font-size: 0.9em; }}
        
        .timeline {{ margin: 20px 0; }}
        .wave {{ background: #252526; border: 1px solid #3e3e42; border-radius: 5px; margin: 10px 0; padding: 15px; }}
        .wave.completed {{ border-color: #4ec9b0; }}
        .wave.in-progress {{ border-color: #dcdcaa; }}
        .wave.pending {{ border-color: #6a9955; }}
        .wave.failed {{ border-color: #f48771; }}
        
        .wave-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .wave-title {{ font-size: 1.2em; font-weight: bold; }}
        .wave-status {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 0.85em; }}
        .status-completed {{ background: #4ec9b0; color: #000; }}
        .status-in-progress {{ background: #dcdcaa; color: #000; }}
        .status-pending {{ background: #6a9955; color: #fff; }}
        .status-failed {{ background: #f48771; color: #000; }}
        
        .progress-bar {{ width: 100%; height: 25px; background: #3e3e42; border-radius: 3px; overflow: hidden; margin: 10px 0; }}
        .progress-fill {{ height: 100%; background: #4ec9b0; transition: width 0.3s; display: flex; align-items: center; justify-content: center; color: #000; font-size: 0.8em; font-weight: bold; }}
        
        .app-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin: 10px 0; }}
        .app-box {{ background: #3e3e42; padding: 10px; border-radius: 3px; font-size: 0.85em; }}
        .app-box.deployed {{ border: 2px solid #4ec9b0; }}
        .app-box.failed {{ border: 2px solid #f48771; }}
        
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }}
        .metric-card {{ background: #252526; padding: 15px; border-radius: 5px; border: 1px solid #3e3e42; }}
        .metric-value {{ font-size: 1.8em; font-weight: bold; color: #4ec9b0; }}
        .metric-label {{ color: #858585; font-size: 0.85em; margin-top: 5px; }}
        
        .issues {{ background: #252526; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #f48771; }}
        .issue-item {{ margin: 10px 0; padding: 10px; background: #2d2d30; border-radius: 3px; }}
        
        .controls {{ margin: 20px 0; display: flex; gap: 10px; }}
        button {{ padding: 10px 20px; background: #4ec9b0; color: #000; border: none; border-radius: 3px; cursor: pointer; font-weight: bold; }}
        button:hover {{ background: #5ed9c0; }}
        button.pause {{ background: #dcdcaa; }}
        button.rollback {{ background: #f48771; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Wave Control Dashboard</h1>
            <div class="timestamp">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value">{wave_status.get('total_apps', 0)}</div>
                <div class="metric-label">Total Applications</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{wave_status.get('deployed_count', 0)}</div>
                <div class="metric-label">Deployed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{wave_status.get('in_progress_count', 0)}</div>
                <div class="metric-label">In Progress</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{wave_status.get('failed_count', 0)}</div>
                <div class="metric-label">Failed</div>
            </div>
        </div>
"""
        
        # Wave timeline
        html += "<h2>Wave Timeline</h2><div class='timeline'>"
        
        for wave in wave_status.get('waves', []):
            status = wave.get('status', 'pending').lower()
            status_class = f"status-{status}"
            wave_class = f"wave {status}"
            
            deployed_apps = wave.get('deployed_apps', 0)
            total_apps = wave.get('total_apps', 0)
            progress = (deployed_apps / total_apps * 100) if total_apps > 0 else 0
            
            html += f"""
            <div class="{wave_class}">
                <div class="wave-header">
                    <div class="wave-title">{wave.get('name', 'Unknown')}</div>
                    <span class="wave-status {status_class}">{status.upper()}</span>
                </div>
                <p>Apps: {deployed_apps}/{total_apps} | Scheduled: {wave.get('scheduled_date', 'TBD')} | Duration: {wave.get('duration_minutes', 0)} min</p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {progress}%">{progress:.0f}%</div>
                </div>
"""
            
            if wave.get('apps'):
                html += "<div class='app-list'>"
                for app in wave['apps']:
                    app_status = app.get('status', 'pending')
                    app_class = f"app-box {app_status}"
                    html += f"<div class='{app_class}'>{app.get('name', 'App')}</div>"
                html += "</div>"
            
            html += "</div>"
        
        html += "</div>"
        
        # Issues section
        issues = wave_status.get('issues', [])
        if issues:
            html += "<div class='issues'><h3>⚠️ Current Issues</h3>"
            for issue in issues:
                severity = issue.get('severity', 'info').upper()
                html += f"<div class='issue-item'><strong>[{severity}]</strong> {issue.get('message', 'Unknown issue')}</div>"
            html += "</div>"
        
        html += f"""
        <div class="controls">
            <button>▶️ Start Next Wave</button>
            <button class="pause">⏸ Pause Current Wave</button>
            <button class="rollback">↩️ Rollback Last Wave</button>
        </div>
        
        <p style="margin-top: 20px; color: #858585; font-size: 0.9em;">
            Dashboard refreshes every 30 seconds. For urgent decisions, contact migration-commander@company.com
        </p>
    </div>
</body>
</html>"""
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        self.logger.info(f"Saved dashboard to {output_path}")


if __name__ == "__main__":
    dashboard = WaveControlDashboard()
    wave_status = {
        "total_apps": 50,
        "deployed_count": 15,
        "in_progress_count": 5,
        "failed_count": 0,
        "waves": [
            {
                "name": "Wave 1 - Pilot",
                "status": "completed",
                "scheduled_date": "2026-07-01",
                "total_apps": 5,
                "deployed_apps": 5,
                "duration_minutes": 180,
                "apps": [
                    {"name": "SalesApp", "status": "deployed"},
                    {"name": "HRApp", "status": "deployed"}
                ]
            },
            {
                "name": "Wave 2 - Enterprise",
                "status": "in-progress",
                "scheduled_date": "2026-07-04",
                "total_apps": 10,
                "deployed_apps": 7,
                "duration_minutes": 240,
                "apps": [
                    {"name": "FinanceApp", "status": "deployed"},
                    {"name": "InvoiceApp", "status": "deployed"}
                ]
            }
        ],
        "issues": [
            {
                "severity": "warning",
                "message": "Wave 2 running 30 minutes behind schedule"
            }
        ]
    }
    dashboard.generate_dashboard(wave_status, "output/wave_control_dashboard.html")
