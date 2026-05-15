"""
Pipeline Dashboard — Vercel Serverless Function
Serves static data snapshot (no database dependency)
"""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template_string

HERE = Path(__file__).parent

# Load snapshot
def load_data():
    path = HERE / "data.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"stats": {}, "hot_leads": [], "recent": []}

app = Flask(__name__)

TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pipeline — Lead Gen Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,400&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0f0f13; --card: #1a1a24; --border: #2a2a3a;
  --text: #e4e4ec; --muted: #7a7a8a; --accent: #d4a843;
  --green: #34d399; --red: #f87171; --cyan: #22d3ee;
}
body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); padding: 1.5rem; max-width: 1100px; margin: 0 auto; }
h1 { font-family: 'Fraunces', serif; font-size: 1.6rem; font-weight: 700; margin-bottom: 0.25rem; color: var(--accent); }
.subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 2rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }
.card h3 { font-family: 'Fraunces', serif; font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
.stat-value { font-family: 'Fraunces', serif; font-size: 2.2rem; font-weight: 700; }
.gold { color: var(--accent); } .green { color: var(--green); } .red { color: var(--red); } .cyan { color: var(--cyan); }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th { text-align: left; color: var(--muted); font-weight: 500; padding: 0.75rem 0.5rem; border-bottom: 1px solid var(--border); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
td { padding: 0.6rem 0.5rem; border-bottom: 1px solid var(--border); }
.badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.7rem; font-weight: 600; }
.badge-hot { background: rgba(52, 211, 153, 0.15); color: var(--green); }
.badge-warm { background: rgba(212, 168, 67, 0.15); color: var(--accent); }
.badge-cold { background: rgba(248, 113, 113, 0.15); color: var(--red); }
.updated { text-align: center; color: var(--muted); font-size: 0.75rem; margin-top: 2rem; }
.repo-link { text-align: center; margin-top: 0.5rem; }
.repo-link a { color: var(--accent); font-size: 0.8rem; text-decoration: none; }
.repo-link a:hover { text-decoration: underline; }
@media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; } }
</style>
</head>
<body>
  <h1>🪠 Pipeline</h1>
  <div class="subtitle">Multi-Agent Sales Assistant — Automated Lead Research & Pitch Generation</div>

  <div class="grid">
    <div class="card"><h3>Total Leads</h3><div class="stat-value" id="total">—</div></div>
    <div class="card"><h3>Analyzed</h3><div class="stat-value gold" id="analyzed">—</div></div>
    <div class="card"><h3>🔥 Hot Leads</h3><div class="stat-value green" id="hot">—</div></div>
    <div class="card"><h3>Pitches</h3><div class="stat-value cyan" id="pitches">—</div></div>
  </div>

  <div class="card" style="margin-bottom:2rem">
    <h3>🔥 Top Hot Leads (by reviews)</h3>
    <div style="overflow-x:auto"><table>
      <thead><tr>
        <th>Business</th><th>City</th><th>Rating</th><th>Reviews</th><th>Reason</th>
      </tr></thead>
      <tbody id="hot-list"></tbody>
    </table></div>
  </div>

  <div class="card">
    <h3>📋 Recent Analyses</h3>
    <div style="overflow-x:auto"><table>
      <thead><tr>
        <th>Business</th><th>Score</th><th>Rating</th><th>Reviews</th><th>Time</th>
      </tr></thead>
      <tbody id="recent-list"></tbody>
    </table></div>
  </div>

  <div class="updated" id="updated"></div>
  <div class="repo-link"><a href="https://github.com/Nifemi0/pipeline">github.com/Nifemi0/pipeline</a></div>

<script>
fetch('/api/data')
  .then(r => r.json())
  .then(d => {
    document.getElementById('total').textContent = d.stats.total_leads?.toLocaleString() || 0;
    document.getElementById('analyzed').textContent = d.stats.analyzed?.toLocaleString() || 0;
    document.getElementById('hot').textContent = d.stats.hot || 0;
    document.getElementById('pitches').textContent = d.stats.pitches || 0;

    const hotBody = document.getElementById('hot-list');
    (d.hot_leads || []).forEach(l => {
      const r = document.createElement('tr');
      const stars = l.avg_rating ? '\u2605'.repeat(Math.round(l.avg_rating)) + ' ' + l.avg_rating.toFixed(1) : '\u2014';
      r.innerHTML = '<td>' + (l.business_name||'') + '</td><td>' + (l.city||'') + ', ' + (l.state||'') + '</td><td>' + stars + '</td><td>' + (l.review_count||0) + '</td><td>' + (l.reason||'') + '</td>';
      hotBody.appendChild(r);
    });

    const recentBody = document.getElementById('recent-list');
    (d.recent || []).forEach(l => {
      const r = document.createElement('tr');
      const badge = 'badge-' + (l.lead_score||'cold');
      const time = l.analyzed_at ? l.analyzed_at.slice(0,10) : '';
      r.innerHTML = '<td>' + (l.business_name||'') + '</td><td><span class="badge ' + badge + '">' + (l.lead_score||'') + '</span></td><td>' + (l.avg_rating||'\u2014') + '</td><td>' + (l.review_count||0) + '</td><td>' + time + '</td>';
      recentBody.appendChild(r);
    });

    if (d.updated_at) document.getElementById('updated').textContent = 'Updated: ' + d.updated_at;
  }).catch(e => {
    document.querySelectorAll('.stat-value').forEach(el => el.textContent = '\u2014');
  });
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(TEMPLATE)

@app.route("/api/stats")
def api_stats():
    data = load_data()
    return jsonify(data["stats"])

@app.route("/api/data")
def api_data():
    return jsonify(load_data())
