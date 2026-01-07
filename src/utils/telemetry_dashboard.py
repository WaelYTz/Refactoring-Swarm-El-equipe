"""
Telemetry Dashboard for Refactoring Swarm

This script analyzes the experiment_data.json log file to provide insights
into agent behavior, performance metrics, and system statistics.

Usage:
    python src/utils/telemetry_dashboard.py
    python src/utils/telemetry_dashboard.py --export report.html
"""

import json
import os
import sys
from datetime import datetime
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logger import LOG_FILE, ActionType


class TelemetryDashboard:
    """
    Analyzes and visualizes telemetry data from experiment logs.
    """
    
    def __init__(self, log_file: str = LOG_FILE):
        """
        Initialize the dashboard with log file path.
        
        Args:
            log_file: Path to the experiment_data.json file
        """
        self.log_file = log_file
        self.data: List[Dict[str, Any]] = []
        self.load_data()
    
    def load_data(self) -> None:
        """Load and parse the log file."""
        if not os.path.exists(self.log_file):
            print(f"⚠️  Log file not found: {self.log_file}")
            print("   No telemetry data available yet.")
            return
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    self.data = json.loads(content)
                else:
                    print("⚠️  Log file is empty.")
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing log file: {e}")
            sys.exit(1)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Calculate summary statistics.
        
        Returns:
            Dictionary containing summary statistics
        """
        if not self.data:
            return {}
        
        total_entries = len(self.data)
        
        # Count by agent
        agents = Counter(entry.get("agent", "Unknown") for entry in self.data)
        
        # Count by action type
        actions = Counter(entry.get("action", "Unknown") for entry in self.data)
        
        # Count by status
        statuses = Counter(entry.get("status", "Unknown") for entry in self.data)
        
        # Count by model
        models = Counter(entry.get("model", "Unknown") for entry in self.data)
        
        # Time range
        timestamps = []
        for entry in self.data:
            if "timestamp" in entry:
                try:
                    timestamps.append(datetime.fromisoformat(entry["timestamp"]))
                except ValueError:
                    pass
        
        time_range = None
        if timestamps:
            time_range = {
                "start": min(timestamps).isoformat(),
                "end": max(timestamps).isoformat(),
                "duration_seconds": (max(timestamps) - min(timestamps)).total_seconds()
            }
        
        return {
            "total_entries": total_entries,
            "agents": dict(agents),
            "actions": dict(actions),
            "statuses": dict(statuses),
            "models": dict(models),
            "time_range": time_range
        }
    
    def get_agent_performance(self) -> Dict[str, Dict[str, Any]]:
        """
        Analyze performance metrics per agent.
        
        Returns:
            Dictionary of agent performance metrics
        """
        agent_stats = defaultdict(lambda: {
            "total_actions": 0,
            "successes": 0,
            "failures": 0,
            "action_types": Counter(),
            "models_used": Counter()
        })
        
        for entry in self.data:
            agent = entry.get("agent", "Unknown")
            status = entry.get("status", "Unknown")
            action = entry.get("action", "Unknown")
            model = entry.get("model", "Unknown")
            
            agent_stats[agent]["total_actions"] += 1
            
            if status == "SUCCESS":
                agent_stats[agent]["successes"] += 1
            elif status == "FAILURE":
                agent_stats[agent]["failures"] += 1
            
            agent_stats[agent]["action_types"][action] += 1
            agent_stats[agent]["models_used"][model] += 1
        
        # Convert Counters to dicts and calculate success rate
        for agent in agent_stats:
            agent_stats[agent]["action_types"] = dict(agent_stats[agent]["action_types"])
            agent_stats[agent]["models_used"] = dict(agent_stats[agent]["models_used"])
            
            total = agent_stats[agent]["total_actions"]
            successes = agent_stats[agent]["successes"]
            agent_stats[agent]["success_rate"] = (successes / total * 100) if total > 0 else 0
        
        return dict(agent_stats)
    
    def validate_data_quality(self) -> Dict[str, Any]:
        """
        Validate data quality according to TP requirements.
        
        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []
        
        if not self.data:
            issues.append("No data in log file")
            return {"valid": False, "issues": issues, "warnings": warnings}
        
        # Check for required fields
        required_fields = ["id", "timestamp", "agent", "model", "action", "details", "status"]
        
        for i, entry in enumerate(self.data):
            for field in required_fields:
                if field not in entry:
                    issues.append(f"Entry {i} missing required field: {field}")
        
        # Check for unique IDs
        ids = [entry.get("id") for entry in self.data]
        if len(ids) != len(set(ids)):
            issues.append("Duplicate IDs found in log entries")
        
        # Check LLM actions have prompts
        llm_actions = [ActionType.ANALYSIS.value, ActionType.GENERATION.value, 
                       ActionType.DEBUG.value, ActionType.FIX.value]
        
        for i, entry in enumerate(self.data):
            action = entry.get("action")
            if action in llm_actions:
                details = entry.get("details", {})
                
                if "input_prompt" not in details:
                    issues.append(f"Entry {i} (action={action}) missing 'input_prompt'")
                elif not details["input_prompt"]:
                    warnings.append(f"Entry {i} has empty 'input_prompt'")
                
                if "output_response" not in details:
                    issues.append(f"Entry {i} (action={action}) missing 'output_response'")
                elif not details["output_response"]:
                    warnings.append(f"Entry {i} has empty 'output_response'")
        
        # Check chronological order
        timestamps = []
        for entry in self.data:
            if "timestamp" in entry:
                try:
                    timestamps.append(datetime.fromisoformat(entry["timestamp"]))
                except ValueError:
                    issues.append(f"Invalid timestamp format: {entry['timestamp']}")
        
        if timestamps:
            for i in range(len(timestamps) - 1):
                if timestamps[i] > timestamps[i + 1]:
                    warnings.append("Log entries are not in chronological order")
                    break
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "total_entries": len(self.data),
            "entries_with_prompts": sum(
                1 for e in self.data 
                if "input_prompt" in e.get("details", {}) 
                and "output_response" in e.get("details", {})
            )
        }
    
    def print_dashboard(self) -> None:
        """Print formatted dashboard to console."""
        print("\n" + "="*70)
        print("📊 REFACTORING SWARM - TELEMETRY DASHBOARD")
        print("="*70 + "\n")
        
        if not self.data:
            print("⚠️  No telemetry data available.")
            print(f"   Expected log file: {self.log_file}")
            return
        
        # Summary Stats
        print("📈 SUMMARY STATISTICS")
        print("-" * 70)
        stats = self.get_summary_stats()
        print(f"Total Log Entries: {stats['total_entries']}")
        
        if stats.get("time_range"):
            tr = stats["time_range"]
            print(f"Time Range: {tr['start']} to {tr['end']}")
            print(f"Duration: {tr['duration_seconds']:.1f} seconds")
        
        print(f"\nAgents Active: {len(stats['agents'])}")
        for agent, count in stats['agents'].items():
            print(f"  • {agent}: {count} actions")
        
        print(f"\nAction Types:")
        for action, count in stats['actions'].items():
            print(f"  • {action}: {count} times")
        
        print(f"\nModels Used:")
        for model, count in stats['models'].items():
            print(f"  • {model}: {count} times")
        
        print(f"\nStatus Distribution:")
        for status, count in stats['statuses'].items():
            print(f"  • {status}: {count}")
        
        # Agent Performance
        print("\n" + "="*70)
        print("🤖 AGENT PERFORMANCE")
        print("-" * 70)
        
        agent_perf = self.get_agent_performance()
        for agent, metrics in agent_perf.items():
            print(f"\n{agent}:")
            print(f"  Total Actions: {metrics['total_actions']}")
            print(f"  Success Rate: {metrics['success_rate']:.1f}%")
            print(f"  Successes: {metrics['successes']} | Failures: {metrics['failures']}")
            
            print(f"  Action Breakdown:")
            for action, count in metrics['action_types'].items():
                print(f"    - {action}: {count}")
        
        # Data Quality Validation
        print("\n" + "="*70)
        print("✅ DATA QUALITY VALIDATION")
        print("-" * 70)
        
        validation = self.validate_data_quality()
        
        if validation["valid"]:
            print("✅ All validation checks PASSED!")
        else:
            print("❌ Validation FAILED!")
        
        print(f"\nTotal Entries: {validation['total_entries']}")
        print(f"Entries with Prompts: {validation['entries_with_prompts']}")
        
        if validation["issues"]:
            print(f"\n❌ Issues Found ({len(validation['issues'])}):")
            for issue in validation["issues"][:10]:  # Show first 10
                print(f"  • {issue}")
            if len(validation["issues"]) > 10:
                print(f"  ... and {len(validation['issues']) - 10} more")
        
        if validation["warnings"]:
            print(f"\n⚠️  Warnings ({len(validation['warnings'])}):")
            for warning in validation["warnings"][:5]:  # Show first 5
                print(f"  • {warning}")
            if len(validation["warnings"]) > 5:
                print(f"  ... and {len(validation['warnings']) - 5} more")
        
        print("\n" + "="*70 + "\n")
    
    def export_html_report(self, output_file: str = "telemetry_report.html") -> None:
        """
        Export dashboard as HTML report.
        
        Args:
            output_file: Path to output HTML file
        """
        stats = self.get_summary_stats()
        agent_perf = self.get_agent_performance()
        validation = self.validate_data_quality()
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Refactoring Swarm - Telemetry Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric {{
            display: inline-block;
            background: #f0f0f0;
            padding: 15px;
            margin: 10px;
            border-radius: 5px;
            min-width: 150px;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .metric-label {{
            color: #666;
            margin-top: 5px;
        }}
        .success {{ color: #28a745; }}
        .failure {{ color: #dc3545; }}
        .warning {{ color: #ffc107; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #667eea;
            color: white;
        }}
        .status-badge {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-failure {{ background: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Refactoring Swarm - Telemetry Report</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
    
    <div class="section">
        <h2>Summary Statistics</h2>
        <div class="metric">
            <div class="metric-value">{stats.get('total_entries', 0)}</div>
            <div class="metric-label">Total Entries</div>
        </div>
        <div class="metric">
            <div class="metric-value">{len(stats.get('agents', {}))}</div>
            <div class="metric-label">Active Agents</div>
        </div>
        <div class="metric">
            <div class="metric-value">{len(stats.get('models', {}))}</div>
            <div class="metric-label">Models Used</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Agent Performance</h2>
        <table>
            <tr>
                <th>Agent</th>
                <th>Actions</th>
                <th>Success Rate</th>
                <th>Status</th>
            </tr>
"""
        
        for agent, metrics in agent_perf.items():
            success_rate = metrics['success_rate']
            status_class = 'badge-success' if success_rate >= 80 else 'badge-failure'
            html += f"""
            <tr>
                <td><strong>{agent}</strong></td>
                <td>{metrics['total_actions']}</td>
                <td>{success_rate:.1f}%</td>
                <td>
                    <span class="status-badge {status_class}">
                        {metrics['successes']} ✓ / {metrics['failures']} ✗
                    </span>
                </td>
            </tr>
"""
        
        html += """
        </table>
    </div>
    
    <div class="section">
        <h2>Data Quality Validation</h2>
"""
        
        if validation['valid']:
            html += '<p class="success">✅ All validation checks PASSED!</p>'
        else:
            html += '<p class="failure">❌ Validation FAILED!</p>'
        
        html += f"""
        <p><strong>Total Entries:</strong> {validation['total_entries']}</p>
        <p><strong>Entries with Prompts:</strong> {validation['entries_with_prompts']}</p>
"""
        
        if validation['issues']:
            html += '<h3 class="failure">Issues:</h3><ul>'
            for issue in validation['issues']:
                html += f'<li>{issue}</li>'
            html += '</ul>'
        
        if validation['warnings']:
            html += '<h3 class="warning">Warnings:</h3><ul>'
            for warning in validation['warnings']:
                html += f'<li>{warning}</li>'
            html += '</ul>'
        
        html += """
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ HTML report exported to: {output_file}")


def main():
    """Main entry point for the telemetry dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze telemetry data from Refactoring Swarm experiments"
    )
    parser.add_argument(
        "--export",
        type=str,
        metavar="FILE",
        help="Export dashboard as HTML report to specified file"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=LOG_FILE,
        help=f"Path to log file (default: {LOG_FILE})"
    )
    
    args = parser.parse_args()
    
    # Create dashboard
    dashboard = TelemetryDashboard(log_file=args.log_file)
    
    # Print to console
    dashboard.print_dashboard()
    
    # Export HTML if requested
    if args.export:
        dashboard.export_html_report(args.export)


if __name__ == "__main__":
    main()
