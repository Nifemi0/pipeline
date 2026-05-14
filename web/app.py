"""
Sales Agent — SaaS Dashboard (Flask)
Modern B2B lead-gen dashboard for blue-collar businesses.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.schema import get_db

app = Flask(__name__)
BASE_DIR = Path(__file__).parent

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Pipeline — Lead Gen Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,400&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0b0d12;
  --surface: #12151c;
  --surface-2: #181c26;
  --border: #1e2230;
  --border-light: #282d3d;
  --fg: #e8edf5;
  --fg-2: #c8cedb;
  --fg-muted: #8892a4;
  --fg-dim: #5a6378;
  --accent: #e8a838;
  --accent-hover: #f0b848;
  --accent-dim: rgba(232,168,56,0.12);
  --accent-glow: rgba(232,168,56,0.06);
  --teal: #2dd4bf;
  --teal-dim: rgba(45,212,191,0.1);
  --green: #22c55e;
  --green-dim: rgba(34,197,94,0.1);
  --yellow: #eab308;
  --orange: #f97316;
  --red: #ef4444;
  --radius: 12px;
  --radius-sm: 8px;
  --shadow: 0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.2);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.5);
}
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  background: var(--bg); color: var(--fg);
  font-family: 'DM Sans', -apple-system, sans-serif;
  font-size: 15px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  min-height: 100dvh; overflow-x: hidden;
}
a { color: var(--accent); text-decoration: none; }

/* ─── LAYOUT ─── */
.app-wrap { display: flex; min-height: 100dvh; }

/* ─── SIDEBAR ─── */
.sidebar {
  width: 240px; flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 24px 16px;
  display: flex; flex-direction: column;
  position: fixed; top: 0; left: 0; bottom: 0;
  z-index: 100;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.sidebar-brand {
  font-family: 'Fraunces', serif;
  font-size: 22px; font-weight: 600;
  color: var(--fg);
  margin-bottom: 32px;
  display: flex; align-items: center; gap: 10px;
}
.sidebar-brand span { color: var(--accent); }
.sidebar-nav { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.sidebar-nav a {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; border-radius: var(--radius-sm);
  color: var(--fg-muted); font-size: 14px; font-weight: 500;
  transition: all 0.15s; text-decoration: none;
}
.sidebar-nav a .nav-icon { width: 20px; text-align: center; font-size: 16px; }
.sidebar-nav a:hover { color: var(--fg); background: var(--surface-2); }
.sidebar-nav a.active {
  color: var(--accent); background: var(--accent-dim);
  box-shadow: inset 0 0 0 1px var(--accent-dim);
}
.sidebar-nav a.active .nav-icon { color: var(--accent); }
.sidebar-section-label {
  font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--fg-dim);
  padding: 20px 14px 6px;
}
.sidebar-footer {
  border-top: 1px solid var(--border);
  padding-top: 16px; margin-top: auto;
  font-size: 12px; color: var(--fg-dim);
}

/* ─── MOBILE BOTTOM NAV ─── */
.mobile-nav {
  display: none;
  position: fixed; bottom: 0; left: 0; right: 0;
  background: var(--surface);
  border-top: 1px solid var(--border);
  z-index: 100;
  padding: 4px 0 env(safe-area-inset-bottom, 4px) 0;
  justify-content: space-around;
}
.mobile-nav a {
  display: flex; flex-direction: column; align-items: center;
  gap: 2px; padding: 6px 10px; font-size: 10px; font-weight: 500;
  color: var(--fg-dim); text-decoration: none;
  border-radius: var(--radius-sm);
  transition: all 0.15s;
  flex: 1; max-width: 80px;
}
.mobile-nav a .nav-icon { font-size: 20px; }
.mobile-nav a.active { color: var(--accent); }
.mobile-nav a.active .nav-icon { color: var(--accent); }
.mobile-header {
  display: none;
  align-items: center; justify-content: space-between;
  padding: 16px 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 50;
}
.mobile-header .brand {
  font-family: 'Fraunces', serif;
  font-size: 18px; font-weight: 600;
}
.mobile-header .brand span { color: var(--accent); }
.mobile-header .menu-btn {
  background: none; border: none; color: var(--fg);
  font-size: 24px; cursor: pointer;
  width: 36px; height: 36px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
}
.mobile-header .menu-btn:active { background: var(--surface-2); }

/* ─── MAIN CONTENT ─── */
.main-content {
  margin-left: 240px;
  flex: 1; min-height: 100dvh;
  padding: 32px 40px 40px;
  max-width: 1200px;
}
.page-title {
  font-family: 'Fraunces', serif;
  font-size: 28px; font-weight: 600;
  margin-bottom: 4px;
}
.page-subtitle {
  color: var(--fg-muted);
  font-size: 14px;
  margin-bottom: 28px;
}

/* ─── STATS ROW ─── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  transition: all 0.2s;
}
.stat-card:hover {
  border-color: var(--border-light);
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}
.stat-card .stat-icon { font-size: 20px; margin-bottom: 8px; }
.stat-card .stat-value {
  font-family: 'Fraunces', serif;
  font-size: 32px; font-weight: 600;
  line-height: 1.1;
  margin-bottom: 2px;
}
.stat-card .stat-label {
  font-size: 13px; color: var(--fg-muted);
  font-weight: 400;
}
.stat-card.accent .stat-value { color: var(--accent); }
.stat-card.teal .stat-value { color: var(--teal); }
.stat-card.green .stat-value { color: var(--green); }
.stat-card.orange .stat-value { color: var(--orange); }

/* ─── SECTION HEADER ─── */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap; gap: 12px;
}
.section-title {
  font-family: 'Fraunces', serif;
  font-size: 20px; font-weight: 600;
}

/* ─── ACTIONS ─── */
.action-bar {
  display: flex; gap: 10px; align-items: center;
  flex-wrap: wrap;
}
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-sm);
  font-family: 'DM Sans', sans-serif;
  font-size: 14px; font-weight: 600;
  border: none; cursor: pointer;
  transition: all 0.15s;
  text-decoration: none;
  white-space: nowrap;
}
.btn-primary {
  background: var(--accent); color: #0b0d12;
}
.btn-primary:hover { background: var(--accent-hover); }
.btn-primary:active { transform: scale(0.97); }
.btn-secondary {
  background: var(--surface); color: var(--fg);
  border: 1px solid var(--border);
}
.btn-secondary:hover { border-color: var(--border-light); background: var(--surface-2); }
.btn-ghost {
  background: transparent; color: var(--fg-muted);
  padding: 10px 14px;
}
.btn-ghost:hover { color: var(--fg); background: var(--surface); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none !important; }

.run-status {
  font-size: 13px; padding: 8px 14px;
  border-radius: var(--radius-sm);
  max-width: 400px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.run-status.done { background: var(--green-dim); color: var(--green); }
.run-status.error { background: rgba(239,68,68,0.1); color: var(--red); }
.run-status.running { background: var(--accent-dim); color: var(--accent); }

/* ─── TABLE ─── */
.table-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: 24px;
}
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th {
  text-align: left; padding: 12px 16px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
  text-transform: uppercase; color: var(--fg-dim);
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
td {
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  color: var(--fg-2);
  vertical-align: middle;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255,255,255,0.015); }
.table-empty {
  padding: 40px; text-align: center;
  color: var(--fg-dim); font-size: 14px;
}

/* ─── BADGES / TAGS ─── */
.badge {
  display: inline-flex; align-items: center;
  padding: 3px 10px; border-radius: 100px;
  font-size: 12px; font-weight: 600;
  gap: 4px;
}
.badge-hot {
  background: var(--green-dim); color: var(--green);
}
.badge-warm {
  background: rgba(234,179,8,0.1); color: var(--yellow);
}
.badge-cold {
  background: rgba(100,116,139,0.12); color: var(--fg-muted);
}
.badge-yes {
  background: var(--green-dim); color: var(--green);
  font-size: 11px; padding: 2px 8px;
}
.badge-no {
  background: rgba(239,68,68,0.08); color: var(--red);
  font-size: 11px; padding: 2px 8px;
}
.badge-category {
  background: rgba(232,168,56,0.08);
  color: var(--accent);
  font-size: 11px; font-weight: 500;
  padding: 2px 8px; border-radius: 100px;
}
.badge-status {
  background: var(--surface-2);
  color: var(--fg-muted);
  font-size: 11px; font-weight: 500;
  padding: 2px 8px; border-radius: 100px;
}
.badge-dot {
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
}
.badge-dot.green { background: var(--green); }
.badge-dot.yellow { background: var(--yellow); }
.badge-dot.red { background: var(--red); }
.badge-dot.gray { background: var(--fg-dim); }

/* ─── PITCH PREVIEW ─── */
.pitch-text {
  font-size: 13px; line-height: 1.6; color: var(--fg-2);
  max-width: 480px;
}
.pitch-text .dim { color: var(--fg-dim); font-style: italic; }

/* ─── MOBILE OVERLAY ─── */
.sidebar-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.6);
  z-index: 99;
}
.sidebar-overlay.open { display: block; }

/* ─── RESPONSIVE ─── */
@media (max-width: 1024px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .sidebar { display: none; }
  .mobile-nav { display: flex; }
  .mobile-header { display: flex; }
  .main-content {
    margin-left: 0;
    padding: 16px 16px 80px;
  }
  .sidebar.open {
    display: flex;
    transform: translateX(0);
  }
  .page-title { font-size: 24px; }
  .stats-row { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .stat-card { padding: 14px 16px; }
  .stat-card .stat-value { font-size: 26px; }
  .section-header { flex-direction: column; align-items: flex-start; }
  .action-bar { width: 100%; }
  .btn { flex: 1; justify-content: center; font-size: 13px; padding: 10px 12px; }
  th, td { padding: 8px 12px; font-size: 12px; }
}
@media (max-width: 480px) {
  .stats-row { grid-template-columns: 1fr 1fr; gap: 8px; }
  .stat-card .stat-value { font-size: 22px; }
}

/* ─── ANIMATIONS ─── */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.animate-in { animation: fadeUp 0.4s ease-out both; }
.delay-1 { animation-delay: 0.05s; }
.delay-2 { animation-delay: 0.1s; }
.delay-3 { animation-delay: 0.15s; }
.delay-4 { animation-delay: 0.2s; }
</style>
</head>
<body>

<!-- SIDEBAR OVERLAY (mobile) -->
<div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

<!-- SIDEBAR -->
<aside class="sidebar" id="sidebar">
  <div class="sidebar-brand">
    <span>◆</span> Pipeline
  </div>
  <nav class="sidebar-nav">
    <div class="sidebar-section-label">Dashboard</div>
    <a href="/" class="{{ 'active' if page == 'overview' else '' }}">
      <span class="nav-icon">◇</span> Overview
    </a>
    <a href="/leads" class="{{ 'active' if page == 'leads' else '' }}">
      <span class="nav-icon">⊞</span> Leads
    </a>
    <a href="/analyses" class="{{ 'active' if page == 'analyses' else '' }}">
      <span class="nav-icon">◎</span> Analyses
    </a>
    <a href="/pitches" class="{{ 'active' if page == 'pitches' else '' }}">
      <span class="nav-icon">⊡</span> Pitches
    </a>
  </nav>
  <div class="sidebar-footer">
    Pipeline v1.0 &middot; Auto-refresh 15s
  </div>
</aside>

<!-- MOBILE HEADER -->
<div class="mobile-header">
  <div class="brand"><span>◆</span> Pipeline</div>
  <button class="menu-btn" onclick="toggleSidebar()" aria-label="Menu">☰</button>
</div>

<!-- MAIN -->
<main class="main-content">

  {% if page == 'overview' %}
  <div class="animate-in">
    <h1 class="page-title">Dashboard</h1>
    <p class="page-subtitle">Your lead generation pipeline at a glance</p>

    <div class="stats-row">
      <div class="stat-card accent animate-in delay-1">
        <div class="stat-icon">◇</div>
        <div class="stat-value">{{ stats.total_leads }}</div>
        <div class="stat-label">Total Leads</div>
      </div>
      <div class="stat-card teal animate-in delay-2">
        <div class="stat-icon">◎</div>
        <div class="stat-value">{{ stats.analyzed }}</div>
        <div class="stat-label">Analyzed</div>
      </div>
      <div class="stat-card green animate-in delay-3">
        <div class="stat-icon">⊡</div>
        <div class="stat-value">{{ stats.pitched }}</div>
        <div class="stat-label">Pitches Ready</div>
      </div>
      <div class="stat-card orange animate-in delay-4">
        <div class="stat-icon">🔥</div>
        <div class="stat-value">{{ stats.hot }}</div>
        <div class="stat-label">Hot Leads</div>
      </div>
    </div>

    <div class="section-header">
      <h2 class="section-title">Today</h2>
    </div>
    <div class="stats-row" style="grid-template-columns: repeat(3,1fr)">
      <div class="stat-card">
        <div class="stat-value" style="font-size:24px">{{ today.leads_scouted }}</div>
        <div class="stat-label">Scouted</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="font-size:24px">{{ today.leads_analyzed }}</div>
        <div class="stat-label">Analyzed</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="font-size:24px">{{ today.pitches_generated }}</div>
        <div class="stat-label">Pitches Written</div>
      </div>
    </div>

    <div class="section-header" style="margin-top:8px">
      <h2 class="section-title">Actions</h2>
      <div class="action-bar">
        <form method="POST" action="/run" style="display:inline">
          <button type="submit" class="btn btn-primary" onclick="this.disabled=true;this.textContent='▶ Running...'">▶ Run All</button>
        </form>
        <form method="POST" action="/run/scout" style="display:inline">
          <button type="submit" class="btn btn-secondary" onclick="this.disabled=true;this.textContent='◐ Scouting...'">◐ Scout Only</button>
        </form>
      </div>
    </div>
    {% if run_status %}
    <div class="run-status {{ run_status }}">Last run: {{ run_result }}</div>
    {% endif %}

    <div class="section-header" style="margin-top:28px">
      <h2 class="section-title">Recent Leads</h2>
      <a href="/leads" style="font-size:13px;font-weight:500">View all →</a>
    </div>
    <div class="table-wrap">
      <div class="table-scroll">
        <table>
          <thead><tr><th>Business</th><th>Category</th><th>Location</th><th>Website</th></tr></thead>
          <tbody>
            {% for l in recent_leads %}
            <tr>
              <td style="font-weight:500">{{ l.business_name }}</td>
              <td><span class="badge-category">{{ l.category }}</span></td>
              <td style="color:var(--fg-muted)">{{ l.city }}, {{ l.state }}</td>
              <td><span class="badge {{ 'badge-yes' if l.has_website else 'badge-no' }}">{{ 'Has site' if l.has_website else 'No site' }}</span></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  {% elif page == 'leads' %}
  <div class="animate-in">
    <div class="section-header">
      <div>
        <h1 class="page-title">Leads</h1>
        <p class="page-subtitle">{{ leads|length }} businesses found</p>
      </div>
      <form method="POST" action="/run/scout" style="display:inline">
        <button type="submit" class="btn btn-secondary" onclick="this.disabled=true;this.textContent='◐ Scouting...'">◐ Scout New</button>
      </form>
    </div>
    <div class="table-wrap">
      <div class="table-scroll">
        <table>
          <thead><tr><th>Business</th><th>Category</th><th>Location</th><th>Phone</th><th>Site</th><th>Source</th><th>Date</th></tr></thead>
          <tbody>
            {% for l in leads %}
            <tr>
              <td style="font-weight:500">{{ l.business_name }}</td>
              <td><span class="badge-category">{{ l.category }}</span></td>
              <td style="color:var(--fg-muted)">{{ l.city }}, {{ l.state }}</td>
              <td style="color:var(--fg-muted);font-size:13px">{{ l.phone or '—' }}</td>
              <td><span class="badge {{ 'badge-yes' if l.has_website else 'badge-no' }}">{{ 'YES' if l.has_website else 'NO' }}</span></td>
              <td style="color:var(--fg-dim);font-size:12px">{{ l.source }}</td>
              <td style="color:var(--fg-dim);font-size:12px">{{ l.created_at[:10] }}</td>
            </tr>
            {% endfor %}
            {% if not leads %}
            <tr><td colspan="7" class="table-empty">No leads yet. Run the pipeline to find some.</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  {% elif page == 'analyses' %}
  <div class="animate-in">
    <div class="section-header">
      <div>
        <h1 class="page-title">Analyses</h1>
        <p class="page-subtitle">{{ analyses|length }} leads analyzed</p>
      </div>
    </div>
    <div class="table-wrap">
      <div class="table-scroll">
        <table>
          <thead><tr><th>Business</th><th>Score</th><th>Rating</th><th>Reviews</th><th>Facebook</th><th>Active</th><th>Notes</th></tr></thead>
          <tbody>
            {% for a in analyses %}
            <tr>
              <td style="font-weight:500">{{ a.business_name }}</td>
              <td><span class="badge badge-{{ a.lead_score }}">{{ a.lead_score }}</span></td>
              <td>{{ '⭐ %.1f'|format(a.avg_rating) if a.avg_rating > 0 else '—' }}</td>
              <td>{{ a.review_count or 0 }}</td>
              <td><span class="badge {{ 'badge-yes' if a.facebook_found else 'badge-no' }}">{{ 'Found' if a.facebook_found else 'None' }}</span></td>
              <td><span class="badge {{ 'badge-yes' if a.is_active else 'badge-no' }}">{{ 'Active' if a.is_active else 'Inactive' }}</span></td>
              <td style="color:var(--fg-dim);font-size:13px">{{ a.notes or '—' }}</td>
            </tr>
            {% endfor %}
            {% if not analyses %}
            <tr><td colspan="7" class="table-empty">No analyses yet. Run the pipeline to score leads.</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  {% elif page == 'pitches' %}
  <div class="animate-in">
    <div class="section-header">
      <div>
        <h1 class="page-title">Pitches</h1>
        <p class="page-subtitle">{{ pitches|length }} personalized pitches generated</p>
      </div>
    </div>
    <div class="table-wrap">
      <div class="table-scroll">
        <table>
          <thead><tr><th>Business</th><th>Score</th><th>Status</th><th>Pitch Preview</th><th>Date</th></tr></thead>
          <tbody>
            {% for p in pitches %}
            <tr>
              <td style="font-weight:500">{{ p.business_name }}</td>
              <td><span class="badge badge-{{ p.lead_score }}">{{ p.lead_score }}</span></td>
              <td><span class="badge-status">{{ p.status }}</span></td>
              <td><div class="pitch-text">{{ p.pitch_text[:120] }}<span class="dim">{% if p.pitch_text|length > 120 %}…{% endif %}</span></div></td>
              <td style="color:var(--fg-dim);font-size:12px;white-space:nowrap">{{ p.created_at[:10] }}</td>
            </tr>
            {% endfor %}
            {% if not pitches %}
            <tr><td colspan="5" class="table-empty">No pitches yet. Analyze some leads first.</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
  {% endif %}

</main>

<!-- MOBILE BOTTOM NAV -->
<nav class="mobile-nav">
  <a href="/" class="{{ 'active' if page == 'overview' else '' }}">
    <span class="nav-icon">◇</span> Home
  </a>
  <a href="/leads" class="{{ 'active' if page == 'leads' else '' }}">
    <span class="nav-icon">⊞</span> Leads
  </a>
  <a href="/analyses" class="{{ 'active' if page == 'analyses' else '' }}">
    <span class="nav-icon">◎</span> Analyze
  </a>
  <a href="/pitches" class="{{ 'active' if page == 'pitches' else '' }}">
    <span class="nav-icon">⊡</span> Pitches
  </a>
</nav>

<script>
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('open');
}
// Auto-refresh
setTimeout(() => window.location.reload(), 15000);
</script>
</body>
</html>
"""


# ─── ROUTES ───────────────────────────────────────────────────────────────────


@app.route("/")
def overview():
    conn = get_db()
    
    total_leads = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
    analyzed = conn.execute("SELECT COUNT(*) as c FROM lead_analyses").fetchone()["c"]
    pitched = conn.execute("SELECT COUNT(*) as c FROM pitches").fetchone()["c"]
    hot = conn.execute("SELECT COUNT(*) as c FROM lead_analyses WHERE lead_score='hot'").fetchone()["c"]
    warm = conn.execute("SELECT COUNT(*) as c FROM lead_analyses WHERE lead_score='warm'").fetchone()["c"]
    cold = conn.execute("SELECT COUNT(*) as c FROM lead_analyses WHERE lead_score='cold'").fetchone()["c"]
    
    today_row = conn.execute(
        "SELECT * FROM pipeline_stats WHERE date = date('now')"
    ).fetchone()
    today = {
        "leads_scouted": today_row["leads_scouted"] if today_row else 0,
        "leads_analyzed": today_row["leads_analyzed"] if today_row else 0,
        "pitches_generated": today_row["pitches_generated"] if today_row else 0,
    }
    
    recent = conn.execute(
        "SELECT * FROM leads ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    
    conn.close()
    
    return render_template_string(
        TEMPLATE,
        page="overview",
        stats={"total_leads": total_leads, "analyzed": analyzed, "pitched": pitched,
               "hot": hot, "warm": warm, "cold": cold},
        today=today,
        recent_leads=[dict(r) for r in recent],
        run_status=request.args.get("status"),
        run_result=request.args.get("result", ""),
    )


@app.route("/leads")
def leads_page():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM leads ORDER BY created_at DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return render_template_string(TEMPLATE, page="leads", leads=[dict(r) for r in rows])


@app.route("/analyses")
def analyses_page():
    conn = get_db()
    rows = conn.execute("""
        SELECT l.business_name, la.* FROM lead_analyses la
        JOIN leads l ON la.lead_id = l.id
        ORDER BY la.analyzed_at DESC LIMIT 200
    """).fetchall()
    conn.close()
    analyses = []
    for r in rows:
        d = dict(r)
        d["facebook_found"] = 1 if d.get("facebook_url") else 0
        analyses.append(d)
    return render_template_string(TEMPLATE, page="analyses", analyses=analyses)


@app.route("/pitches")
def pitches_page():
    conn = get_db()
    rows = conn.execute("""
        SELECT l.business_name, la.lead_score, p.* FROM pitches p
        JOIN leads l ON p.lead_id = l.id
        JOIN lead_analyses la ON p.analysis_id = la.id
        ORDER BY p.created_at DESC LIMIT 200
    """).fetchall()
    conn.close()
    return render_template_string(TEMPLATE, page="pitches", pitches=[dict(r) for r in rows])


@app.route("/run", methods=["POST"])
def run_full():
    try:
        result = subprocess.run(
            [sys.executable, "orchestrator.py", "--mode", "full",
             "--scout-limit", "30", "--analyst-limit", "10", "--writer-limit", "10"],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR.parent)
        )
        status = "done" if result.returncode == 0 else "error"
        output = result.stdout[-300:] if result.stdout else result.stderr[-300:]
        output = output.replace("\n", " | ")[:200]
    except subprocess.TimeoutExpired:
        status = "error"
        output = "Pipeline timed out (120s)"
    except Exception as e:
        status = "error"
        output = str(e)[:200]
    
    return redirect(f"/?status={status}&result={output}")


@app.route("/run/scout", methods=["POST"])
def run_scout():
    try:
        result = subprocess.run(
            [sys.executable, "orchestrator.py", "--mode", "scout", "--scout-limit", "30"],
            capture_output=True, text=True, timeout=60,
            cwd=str(BASE_DIR.parent)
        )
        status = "done" if result.returncode == 0 else "error"
        output = result.stdout[-200:] if result.stdout else result.stderr[-200:]
        output = output.replace("\n", " | ")[:150]
    except Exception as e:
        status = "error"
        output = str(e)[:150]
    
    return redirect(f"/?status={status}&result={output}")


@app.route("/api/stats")
def api_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
    analyzed = conn.execute("SELECT COUNT(*) as c FROM lead_analyses").fetchone()["c"]
    pitched = conn.execute("SELECT COUNT(*) as c FROM pitches").fetchone()["c"]
    hot = conn.execute("SELECT COUNT(*) as c FROM lead_analyses WHERE lead_score='hot'").fetchone()["c"]
    conn.close()
    return jsonify({"total": total, "analyzed": analyzed, "pitched": pitched, "hot": hot})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
