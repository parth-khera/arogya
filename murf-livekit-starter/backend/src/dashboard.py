"""
Aarogya dashboard — FastAPI app.
Run:  uv run python src/dashboard.py
Open: http://localhost:8080
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.local")

import db
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

app = FastAPI(title="Aarogya Dashboard")

# ── Analytics SPA ─────────────────────────────────────────────────────────────
ANALYTICS_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aarogya — Analytics</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js" defer></script>
<script>
  tailwind.config = {
    darkMode: 'class',
    theme: { extend: { colors: {
      brand: '#f97316',
      surface: '#1e293b',
      base: '#0f172a',
    }}}
  }
</script>
<style>
  [x-cloak] { display: none !important; }
  .pulse-dot { animation: pulse 2s cubic-bezier(0.4,0,0.6,1) infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  .fade-in { animation: fadeIn .4s ease; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:none} }
  ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background:#0f172a; }
  ::-webkit-scrollbar-thumb { background:#334155; border-radius:3px; }
</style>
</head>
<body class="bg-base text-slate-200 min-h-screen font-sans" x-data="dashboard()" x-init="init()">

<!-- ── Navbar ── -->
<nav class="border-b border-slate-800 px-6 py-3 flex items-center justify-between sticky top-0 bg-base/90 backdrop-blur z-10">
  <div class="flex items-center gap-3">
    <span class="text-2xl">🏥</span>
    <span class="font-bold text-lg text-brand">Aarogya</span>
    <span class="text-slate-500 text-sm hidden sm:block">Voice Health Assistant</span>
  </div>
  <div class="flex items-center gap-6 text-sm">
    <a href="/analytics" class="text-brand font-semibold border-b-2 border-brand pb-0.5">Analytics</a>
    <a href="/" class="text-slate-400 hover:text-white transition-colors">Escalations</a>
    <a href="/api/calls" class="text-slate-400 hover:text-white transition-colors">API</a>
    <div class="flex items-center gap-1.5 text-slate-400 text-xs">
      <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-dot"></span>
      <span x-text="lastUpdated">—</span>
    </div>
  </div>
</nav>

<!-- ── Main ── -->
<main class="max-w-7xl mx-auto px-6 py-8">

  <!-- Header -->
  <div class="mb-8">
    <h1 class="text-3xl font-bold text-white">Call Analytics</h1>
    <p class="text-slate-400 mt-1 text-sm">Real-time performance overview · auto-refreshes every 10s</p>
  </div>

  <!-- ── Stat Cards ── -->
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
    <div class="bg-surface rounded-2xl p-6 border border-slate-700/50 fade-in">
      <p class="text-slate-400 text-xs uppercase tracking-widest mb-2">Total Calls</p>
      <p class="text-4xl font-bold text-brand" x-text="stats.total">—</p>
      <p class="text-slate-500 text-xs mt-2">all time</p>
    </div>
    <div class="bg-surface rounded-2xl p-6 border border-slate-700/50 fade-in">
      <p class="text-slate-400 text-xs uppercase tracking-widest mb-2">Successful</p>
      <p class="text-4xl font-bold text-emerald-400" x-text="stats.successful">—</p>
      <p class="text-slate-500 text-xs mt-2">guidance given</p>
    </div>
    <div class="bg-surface rounded-2xl p-6 border border-slate-700/50 fade-in">
      <p class="text-slate-400 text-xs uppercase tracking-widest mb-2">Failed</p>
      <p class="text-4xl font-bold text-rose-400" x-text="stats.failed">—</p>
      <p class="text-slate-500 text-xs mt-2">no outcome reached</p>
    </div>
    <div class="bg-surface rounded-2xl p-6 border border-slate-700/50 fade-in">
      <p class="text-slate-400 text-xs uppercase tracking-widest mb-2">Success Rate</p>
      <p class="text-4xl font-bold text-sky-400" x-text="rate + '%'">—</p>
      <div class="mt-3 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div class="h-full bg-sky-400 rounded-full transition-all duration-700" :style="'width:' + rate + '%'"></div>
      </div>
    </div>
  </div>

  <!-- ── Charts Row ── -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

    <!-- Donut chart -->
    <div class="bg-surface rounded-2xl p-6 border border-slate-700/50">
      <h2 class="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">Outcome Breakdown</h2>
      <div class="flex items-center justify-center" style="height:220px">
        <canvas id="donutChart"></canvas>
      </div>
    </div>

    <!-- Bar chart — calls per day -->
    <div class="bg-surface rounded-2xl p-6 border border-slate-700/50">
      <h2 class="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">Calls Over Time</h2>
      <div style="height:220px">
        <canvas id="barChart"></canvas>
      </div>
    </div>

  </div>

  <!-- ── Recent Calls Table ── -->
  <div class="bg-surface rounded-2xl border border-slate-700/50 overflow-hidden">
    <div class="px-6 py-4 border-b border-slate-700/50 flex items-center justify-between">
      <h2 class="text-sm font-semibold text-slate-300 uppercase tracking-widest">Recent Calls</h2>
      <span class="text-xs text-slate-500">last 20</span>
    </div>

    <!-- Filter tabs -->
    <div class="px-6 pt-3 flex gap-2">
      <template x-for="tab in ['all','success','failed']">
        <button
          @click="filter = tab"
          :class="filter === tab
            ? 'bg-brand text-white'
            : 'bg-slate-800 text-slate-400 hover:text-white'"
          class="px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize"
          x-text="tab">
        </button>
      </template>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-xs text-slate-500 uppercase tracking-wider border-b border-slate-700/50">
            <th class="px-6 py-3">Call ID</th>
            <th class="px-6 py-3">Started</th>
            <th class="px-6 py-3">Duration</th>
            <th class="px-6 py-3">Outcome</th>
            <th class="px-6 py-3">Failure Type</th>
          </tr>
        </thead>
        <tbody>
          <template x-if="filteredCalls.length === 0">
            <tr><td colspan="5" class="px-6 py-12 text-center text-slate-500">No calls yet</td></tr>
          </template>
          <template x-for="call in filteredCalls" :key="call.call_id">
            <tr class="border-b border-slate-800 hover:bg-slate-800/40 transition-colors fade-in">
              <td class="px-6 py-3 font-mono text-xs text-slate-500" x-text="call.call_id.slice(0,8) + '…'"></td>
              <td class="px-6 py-3 text-slate-300 text-xs" x-text="call.started_at ? call.started_at.slice(0,19).replace('T',' ') : '—'"></td>
              <td class="px-6 py-3 text-slate-300" x-text="(call.duration_sec || 0) + 's'"></td>
              <td class="px-6 py-3">
                <span
                  :class="call.outcome === 'success'
                    ? 'bg-emerald-900/60 text-emerald-400 border border-emerald-700/50'
                    : 'bg-rose-900/60 text-rose-400 border border-rose-700/50'"
                  class="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase"
                  x-text="call.outcome">
                </span>
              </td>
              <td class="px-6 py-3 text-slate-500 text-xs" x-text="call.failure_type || '—'"></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>

</main>

<script>
function dashboard() {
  return {
    stats: { total: 0, successful: 0, failed: 0, recent: [] },
    filter: 'all',
    lastUpdated: '—',
    donutChart: null,
    barChart: null,

    get rate() {
      return this.stats.total ? Math.round(this.stats.successful / this.stats.total * 100) : 0;
    },

    get filteredCalls() {
      if (this.filter === 'all') return this.stats.recent;
      return this.stats.recent.filter(c => c.outcome === this.filter);
    },

    async fetchStats() {
      try {
        const res = await fetch('/api/calls');
        this.stats = await res.json();
        this.lastUpdated = new Date().toLocaleTimeString();
        this.updateCharts();
      } catch(e) { console.error(e); }
    },

    updateCharts() {
      const s = this.stats.successful, f = this.stats.failed;

      // Donut
      if (this.donutChart) {
        this.donutChart.data.datasets[0].data = [s, f];
        this.donutChart.update('active');
      }

      // Bar — group recent calls by date
      const byDate = {};
      (this.stats.recent || []).forEach(c => {
        const d = (c.started_at || '').slice(0, 10);
        if (!d) return;
        if (!byDate[d]) byDate[d] = { success: 0, failed: 0 };
        byDate[d][c.outcome === 'success' ? 'success' : 'failed']++;
      });
      const labels = Object.keys(byDate).sort();
      if (this.barChart) {
        this.barChart.data.labels = labels;
        this.barChart.data.datasets[0].data = labels.map(d => byDate[d].success);
        this.barChart.data.datasets[1].data = labels.map(d => byDate[d].failed);
        this.barChart.update('active');
      }
    },

    initCharts() {
      const donutCtx = document.getElementById('donutChart').getContext('2d');
      this.donutChart = new Chart(donutCtx, {
        type: 'doughnut',
        data: {
          labels: ['Successful', 'Failed'],
          datasets: [{ data: [0, 0],
            backgroundColor: ['#34d399', '#f87171'],
            borderColor: ['#059669', '#dc2626'],
            borderWidth: 1, hoverOffset: 6 }]
        },
        options: {
          cutout: '72%', responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 12 }, padding: 16 } },
            tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed}` } }
          }
        }
      });

      const barCtx = document.getElementById('barChart').getContext('2d');
      this.barChart = new Chart(barCtx, {
        type: 'bar',
        data: {
          labels: [],
          datasets: [
            { label: 'Successful', data: [], backgroundColor: '#34d39966', borderColor: '#34d399', borderWidth: 1.5, borderRadius: 4 },
            { label: 'Failed',     data: [], backgroundColor: '#f8717166', borderColor: '#f87171', borderWidth: 1.5, borderRadius: 4 }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            x: { stacked: false, grid: { color: '#1e293b' }, ticks: { color: '#64748b', font: { size: 11 } } },
            y: { beginAtZero: true, grid: { color: '#1e293b' }, ticks: { color: '#64748b', stepSize: 1 } }
          },
          plugins: { legend: { labels: { color: '#94a3b8', font: { size: 12 } } } }
        }
      });
    },

    init() {
      this.initCharts();
      this.fetchStats();
      setInterval(() => this.fetchStats(), 10000);
    }
  }
}
</script>
</body>
</html>"""

# ── Escalations HTML ──────────────────────────────────────────────────────────
ESCALATIONS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aarogya — Escalations</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config = { darkMode: 'class', theme: { extend: { colors: { brand: '#f97316', surface: '#1e293b', base: '#0f172a' }}}}</script>
</head>
<body class="dark bg-base text-slate-200 min-h-screen font-sans">
<nav class="border-b border-slate-800 px-6 py-3 flex items-center justify-between sticky top-0 bg-base/90 backdrop-blur z-10">
  <div class="flex items-center gap-3">
    <span class="text-2xl">🏥</span>
    <span class="font-bold text-lg text-brand">Aarogya</span>
  </div>
  <div class="flex items-center gap-6 text-sm">
    <a href="/analytics" class="text-slate-400 hover:text-white transition-colors">Analytics</a>
    <a href="/" class="text-brand font-semibold border-b-2 border-brand pb-0.5">Escalations</a>
    <a href="/resolved" class="text-slate-400 hover:text-white transition-colors">Resolved</a>
  </div>
</nav>
<main class="max-w-7xl mx-auto px-6 py-8">
  <div class="mb-6 flex items-center justify-between">
    <div>
      <h1 class="text-3xl font-bold text-white">Open Escalations</h1>
      <p class="text-slate-400 mt-1 text-sm">{count} open · health worker action required</p>
    </div>
  </div>
  {table}
</main>
</body>
</html>"""

URGENCY_CLASSES = {
    "emergency": "bg-red-900/60 text-red-400 border border-red-700/50",
    "high":      "bg-orange-900/60 text-orange-400 border border-orange-700/50",
    "medium":    "bg-yellow-900/60 text-yellow-400 border border-yellow-700/50",
    "low":       "bg-emerald-900/60 text-emerald-400 border border-emerald-700/50",
}


def _escalation_table(rows: list[dict], show_resolve: bool) -> str:
    if not rows:
        return '<p class="text-center py-16 text-slate-500">No escalations 🎉</p>'

    trs = []
    for r in rows:
        urg = r["urgency"].lower()
        badge_cls = URGENCY_CLASSES.get(urg, "bg-slate-700 text-slate-300")
        action = (
            f'<form method="post" action="/resolve/{r["ref_id"]}">'
            f'<button class="px-3 py-1 rounded-lg bg-emerald-900/60 text-emerald-400 border border-emerald-700/50 text-xs font-semibold hover:bg-emerald-800 transition-colors">✓ Resolve</button>'
            f'</form>'
        ) if show_resolve else '<span class="text-slate-600 text-xs">resolved</span>'

        trs.append(f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/40 transition-colors">
          <td class="px-6 py-4 font-mono text-xs text-brand">{r['ref_id']}</td>
          <td class="px-6 py-4 text-sm">{r['caller_name'] or '—'}</td>
          <td class="px-6 py-4"><span class="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase {badge_cls}">{urg}</span></td>
          <td class="px-6 py-4 text-sm text-slate-300">{r['reason'].replace('_',' ').title()}</td>
          <td class="px-6 py-4 text-xs text-slate-400 max-w-xs truncate">{(r['summary'] or '')[:120]}</td>
          <td class="px-6 py-4 text-xs text-slate-500">{r.get('language') or '—'}</td>
          <td class="px-6 py-4 text-xs text-slate-500">{(r['created_at'] or '')[:19].replace('T',' ')}</td>
          <td class="px-6 py-4">{action}</td>
        </tr>""")

    header = """
    <div class="bg-surface rounded-2xl border border-slate-700/50 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-left text-xs text-slate-500 uppercase tracking-wider border-b border-slate-700/50">
            <th class="px-6 py-3">Ref ID</th><th class="px-6 py-3">Caller</th>
            <th class="px-6 py-3">Urgency</th><th class="px-6 py-3">Reason</th>
            <th class="px-6 py-3">Summary</th><th class="px-6 py-3">Language</th>
            <th class="px-6 py-3">Created</th><th class="px-6 py-3"></th>
          </tr></thead>
          <tbody>""" + "".join(trs) + """</tbody>
        </table>
      </div>
    </div>"""
    return header


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/analytics", response_class=HTMLResponse)
def analytics():
    return ANALYTICS_HTML


@app.get("/", response_class=HTMLResponse)
def index():
    rows = db.list_escalations("open")
    return ESCALATIONS_HTML.format(count=len(rows), table=_escalation_table(rows, True))


@app.get("/resolved", response_class=HTMLResponse)
def resolved():
    rows = db.list_escalations("resolved")
    html = ESCALATIONS_HTML.replace("Open Escalations", "Resolved Escalations")
    html = html.replace(f"{len(rows)} open · health worker action required", f"{len(rows)} resolved")
    return html.format(count=len(rows), table=_escalation_table(rows, False))


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
        raise HTTPException(status_code=404, detail="Not found")
    return esc


@app.get("/api/calls")
def api_calls():
    return db.get_call_stats()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
