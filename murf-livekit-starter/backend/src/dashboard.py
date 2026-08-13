"""
Aarogya escalation dashboard — FastAPI app.

Run:
    uv run python src/dashboard.py

Open: http://localhost:8080
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.local")

import db
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

app = FastAPI(title="Aarogya Escalations")

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aarogya — Escalations</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }}
  h1 {{ color: #f97316; margin-bottom: 4px; }}
  p.sub {{ color: #94a3b8; margin-top: 0; margin-bottom: 16px; }}
  nav a {{ color: #f97316; text-decoration: none; margin-right: 16px; font-size: 14px; }}
  nav a:hover {{ text-decoration: underline; }}
  nav {{ margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1e293b; padding: 10px 14px; text-align: left; font-size: 12px;
        text-transform: uppercase; letter-spacing: .05em; color: #94a3b8; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #1e293b; font-size: 14px; vertical-align: top; }}
  tr:hover td {{ background: #1e293b44; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px;
             font-weight: 600; text-transform: uppercase; }}
  .emergency {{ background: #7f1d1d; color: #fca5a5; }}
  .high      {{ background: #7c2d12; color: #fdba74; }}
  .medium    {{ background: #713f12; color: #fde68a; }}
  .low       {{ background: #14532d; color: #86efac; }}
  .ref {{ font-family: monospace; color: #f97316; }}
  .empty {{ text-align: center; padding: 48px; color: #475569; }}
  button {{ background: #166534; color: #86efac; border: none; padding: 4px 12px;
             border-radius: 6px; cursor: pointer; font-size: 12px; }}
  button:hover {{ background: #15803d; }}
</style>
</head>
<body>
<h1>🏥 Aarogya — Escalations</h1>
<p class="sub">{count} open · <a href="/resolved">view resolved</a></p>
<nav>
  <a href="/">Open</a>
  <a href="/resolved">Resolved</a>
  <a href="/analytics">Analytics</a>
  <a href="/api/escalations">JSON API</a>
</nav>
{table}
</body>
</html>"""

_ROW = """<tr>
  <td class="ref">{ref_id}</td>
  <td>{caller_name}</td>
  <td><span class="badge {urgency_cls}">{urgency}</span></td>
  <td>{reason}</td>
  <td style="max-width:240px">{summary}</td>
  <td style="color:#94a3b8;font-size:12px">{language}</td>
  <td style="color:#94a3b8;font-size:12px;max-width:160px">{agent_checked}</td>
  <td style="color:#94a3b8;font-size:12px">{created_at}</td>
  <td>{action}</td>
</tr>"""

_THEAD = """<table>
<thead><tr>
  <th>Ref ID</th><th>Caller</th><th>Urgency</th>
  <th>Reason</th><th>Summary</th><th>Language</th>
  <th>Agent Checked</th><th>Created</th><th></th>
</tr></thead>
<tbody>{rows}</tbody>
</table>"""

_RESOLVE_BTN = """<form method="post" action="/resolve/{ref_id}">
  <button type="submit">✓ Resolve</button>
</form>"""


def _render_rows(rows: list[dict], show_resolve: bool) -> str:
    trs = []
    for r in rows:
        action = _RESOLVE_BTN.format(ref_id=r["ref_id"]) if show_resolve else "—"
        trs.append(_ROW.format(
            ref_id=r["ref_id"],
            caller_name=r["caller_name"] or "—",
            urgency=r["urgency"].upper(),
            urgency_cls=r["urgency"].lower(),
            reason=r["reason"].replace("_", " ").title(),
            summary=(r["summary"] or "")[:200],
            language=r.get("language") or "—",
            agent_checked=(r.get("agent_checked") or "—")[:80],
            created_at=(r["created_at"] or "")[:19].replace("T", " "),
            action=action,
        ))
    return _THEAD.format(rows="".join(trs))


@app.get("/", response_class=HTMLResponse)
def index():
    rows = db.list_escalations("open")
    table = _render_rows(rows, show_resolve=True) if rows else '<p class="empty">No open escalations 🎉</p>'
    return _HTML.format(count=len(rows), table=table)


@app.get("/resolved", response_class=HTMLResponse)
def resolved():
    rows = db.list_escalations("resolved")
    table = _render_rows(rows, show_resolve=False) if rows else '<p class="empty">No resolved escalations yet.</p>'
    return _HTML.format(count=0, table=table).replace(
        f"{0} open", f"{len(rows)} resolved"
    )


@app.post("/resolve/{ref_id}")
def resolve(ref_id: str):
    db.update_escalation_status(ref_id, "resolved")
    return RedirectResponse("/", status_code=303)


@app.get("/api/escalations")
def api_escalations(status: str = "open"):
    return db.list_escalations(status)


@app.get("/api/escalations/{ref_id}")
def api_escalation_detail(ref_id: str):
    esc = db.get_escalation(ref_id)
    if not esc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    return esc


_ANALYTICS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>Aarogya — Analytics</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }}
  h1 {{ color: #f97316; margin-bottom: 4px; }}
  p.sub {{ color: #94a3b8; margin-top: 0; margin-bottom: 16px; }}
  nav a {{ color: #f97316; text-decoration: none; margin-right: 16px; font-size: 14px; }}
  nav {{ margin-bottom: 24px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 24px 32px; min-width: 160px; text-align: center; }}
  .card .num {{ font-size: 48px; font-weight: 700; line-height: 1; }}
  .card .lbl {{ font-size: 13px; color: #94a3b8; margin-top: 6px; text-transform: uppercase; letter-spacing: .05em; }}
  .total   .num {{ color: #f97316; }}
  .success .num {{ color: #86efac; }}
  .failed  .num {{ color: #fca5a5; }}
  .rate    .num {{ color: #93c5fd; font-size: 36px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1e293b; padding: 10px 14px; text-align: left; font-size: 12px;
        text-transform: uppercase; letter-spacing: .05em; color: #94a3b8; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #1e293b; font-size: 13px; }}
  .ok  {{ color: #86efac; font-weight: 600; }}
  .bad {{ color: #fca5a5; font-weight: 600; }}
  .ft  {{ color: #94a3b8; font-size: 11px; }}
</style>
</head>
<body>
<h1>🏥 Aarogya — Call Analytics</h1>
<p class="sub">Auto-refreshes every 15 seconds</p>
<nav>
  <a href="/analytics">Analytics</a>
  <a href="/">Escalations</a>
  <a href="/api/calls">JSON API</a>
</nav>
<div class="cards">
  <div class="card total"><div class="num">{total}</div><div class="lbl">Total Calls</div></div>
  <div class="card success"><div class="num">{successful}</div><div class="lbl">Successful</div></div>
  <div class="card failed"><div class="num">{failed}</div><div class="lbl">Failed</div></div>
  <div class="card rate"><div class="num">{rate}%</div><div class="lbl">Success Rate</div></div>
</div>
<h2 style="color:#94a3b8;font-size:14px;text-transform:uppercase;letter-spacing:.05em">Recent Calls</h2>
{table}
</body>
</html>"""

_CALL_ROW = """<tr>
  <td style="font-family:monospace;font-size:11px;color:#64748b">{call_id}</td>
  <td style="font-size:11px;color:#64748b">{started_at}</td>
  <td>{duration_sec}s</td>
  <td class="{outcome_cls}">{outcome}</td>
  <td class="ft">{failure_type}</td>
</tr>"""


@app.get("/analytics", response_class=HTMLResponse)
def analytics():
    stats = db.get_call_stats()
    total = stats["total"]
    rate  = round(stats["successful"] / total * 100) if total else 0
    rows  = "".join(
        _CALL_ROW.format(
            call_id=r["call_id"][:8] + "…",
            started_at=(r["started_at"] or "")[:19].replace("T", " "),
            duration_sec=r["duration_sec"] or 0,
            outcome=r["outcome"].upper(),
            outcome_cls="ok" if r["outcome"] == "success" else "bad",
            failure_type=r.get("failure_type") or "—",
        )
        for r in stats["recent"]
    )
    table = (
        "<table><thead><tr>"
        "<th>Call ID</th><th>Started</th><th>Duration</th><th>Outcome</th><th>Failure Type</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
        if rows else "<p style='color:#475569'>No calls recorded yet.</p>"
    )
    return _ANALYTICS_HTML.format(
        total=total,
        successful=stats["successful"],
        failed=stats["failed"],
        rate=rate,
        table=table,
    )


@app.get("/api/calls")
def api_calls():
    return db.get_call_stats()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
