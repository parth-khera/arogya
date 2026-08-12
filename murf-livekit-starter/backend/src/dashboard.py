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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
