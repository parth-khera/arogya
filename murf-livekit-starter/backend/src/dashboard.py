"""
Aarogya escalation dashboard — minimal FastAPI app.

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
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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
  p.sub {{ color: #94a3b8; margin-top: 0; margin-bottom: 24px; }}
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
</style>
</head>
<body>
<h1>🏥 Aarogya — Open Escalations</h1>
<p class="sub">Refresh to update &nbsp;·&nbsp; {count} open request(s)</p>
{table}
</body>
</html>"""

_ROW = """<tr>
  <td class="ref">{ref_id}</td>
  <td>{caller_name}</td>
  <td><span class="badge {urgency_cls}">{urgency}</span></td>
  <td>{reason}</td>
  <td style="max-width:320px">{summary}</td>
  <td style="color:#94a3b8;font-size:12px">{created_at}</td>
</tr>"""


@app.get("/", response_class=HTMLResponse)
def index():
    rows = db.list_escalations("open")
    if not rows:
        table = '<p class="empty">No open escalations 🎉</p>'
    else:
        trs = "".join(_ROW.format(
            ref_id=r["ref_id"],
            caller_name=r["caller_name"] or "—",
            urgency=r["urgency"].upper(),
            urgency_cls=r["urgency"].lower(),
            reason=r["reason"].replace("_", " ").title(),
            summary=r["summary"][:200],
            created_at=r["created_at"][:19].replace("T", " "),
        ) for r in rows)
        table = f"""<table>
<thead><tr>
  <th>Ref ID</th><th>Caller</th><th>Urgency</th>
  <th>Reason</th><th>Summary</th><th>Created</th>
</tr></thead>
<tbody>{trs}</tbody>
</table>"""
    return _HTML.format(count=len(rows), table=table)


@app.get("/api/escalations")
def api_escalations(status: str = "open"):
    return db.list_escalations(status)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
