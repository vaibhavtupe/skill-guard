"""HTML formatter for monitor reports."""

from __future__ import annotations

from skill_guard.models import MonitorReport


def format_as_html(report: MonitorReport) -> str:
    """Render monitor report as standalone HTML."""
    rows = []
    for status in report.skills:
        state_class = (
            "healthy"
            if status.healthy and status.stage != "degraded"
            else ("degraded" if status.stage == "degraded" else "failing")
        )
        findings = "<br>".join(status.findings) if status.findings else "None"
        rows.append(
            "<tr>"
            f"<td>{status.skill_name}</td>"
            f"<td class='{state_class}'>{status.stage}</td>"
            f"<td class='{state_class}'>{'yes' if status.healthy else 'no'}</td>"
            f"<td>{findings}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>skill-guard monitor report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .card {{ padding: 16px; border-radius: 10px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .healthy-card {{ border-left: 6px solid #16a34a; }}
    .degraded-card {{ border-left: 6px solid #ca8a04; }}
    .failing-card {{ border-left: 6px solid #dc2626; }}
    .muted {{ color: #475569; font-size: 14px; margin-bottom: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
    th {{ background: #f1f5f9; }}
    .healthy {{ color: #166534; font-weight: 600; }}
    .degraded {{ color: #854d0e; font-weight: 600; }}
    .failing {{ color: #991b1b; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>skill-guard monitor report</h1>
  <p class="muted">Generated at {report.generated_at.isoformat()} | Runtime {report.run_time_seconds:.2f}s</p>
  <div class="cards">
    <div class="card healthy-card"><h3>Healthy</h3><p>{report.healthy}</p></div>
    <div class="card degraded-card"><h3>Degraded</h3><p>{report.degraded}</p></div>
    <div class="card failing-card"><h3>Failing</h3><p>{report.failing}</p></div>
  </div>
  <table>
    <thead>
      <tr><th>Skill</th><th>Stage</th><th>Healthy</th><th>Findings</th></tr>
    </thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
