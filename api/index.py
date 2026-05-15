"""
Pipeline Dashboard — Vercel Serverless Function
Serves the full admin dashboard from static snapshot data.
Dynamic features (send, run agents) are read-only on Vercel.
"""
import json
import os
import re
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request

HERE = Path(__file__).parent

# Load snapshot
def load_data():
    path = HERE / "data.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"stats": {}, "hot_leads": [], "recent": [], "leads": [], "analyses": [], "pitches": []}

app = Flask(__name__)

# ─── SNAPSHOT API ────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    d = load_data()
    leads = d.get("leads", [])
    analyses = d.get("analyses", [])
    pitches = d.get("pitches", [])
    
    total = len(leads)
    analyzed = len(analyses)
    hot = sum(1 for a in analyses if a.get("lead_score") == "hot")
    warm = sum(1 for a in analyses if a.get("lead_score") == "warm")
    cold = sum(1 for a in analyses if a.get("lead_score") == "cold")
    sent = sum(1 for p in pitches if p.get("status") == "sent")
    
    return jsonify({
        "total_leads": total,
        "analyzed": analyzed,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "pitches": len(pitches),
        "pitches_sent": sent,
        "remaining": total - analyzed
    })

@app.route("/api/leads")
def api_leads():
    d = load_data()
    leads = d.get("leads", [])
    analyses = {a["lead_id"]: a for a in d.get("analyses", [])}
    
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    city = request.args.get("city", "")
    category = request.args.get("category", "")
    score = request.args.get("score", "")
    search = request.args.get("search", "")
    has_website = request.args.get("has_website", "")
    
    filtered = []
    for l in leads:
        a = analyses.get(l.get("id"))
        if city and l.get("city") != city: continue
        if category and l.get("category") != category: continue
        if score and (not a or a.get("lead_score") != score): continue
        if search and search.lower() not in (l.get("business_name","").lower()): continue
        if has_website == "yes" and not l.get("website"): continue
        if has_website == "no" and l.get("website"): continue
        merged = dict(l)
        if a:
            merged.update(a)
        filtered.append(merged)
    
    total = len(filtered)
    offset = (page - 1) * per_page
    page_leads = filtered[offset:offset + per_page]
    
    return jsonify({
        "leads": page_leads,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page)
    })

@app.route("/api/leads/<int:lead_id>")
def api_lead_detail(lead_id):
    d = load_data()
    lead = next((l for l in d.get("leads", []) if l.get("id") == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    analysis = next((a for a in d.get("analyses", []) if a.get("lead_id") == lead_id), None)
    pitches = [p for p in d.get("pitches", []) if p.get("lead_id") == lead_id]
    return jsonify({"lead": lead, "analysis": analysis, "pitches": pitches})

@app.route("/api/pitches")
def api_pitches():
    d = load_data()
    pitches = d.get("pitches", [])
    leads_map = {l["id"]: l for l in d.get("leads", [])}
    
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    
    filtered = []
    for p in pitches:
        if status and p.get("status") != status: continue
        l = leads_map.get(p.get("lead_id"))
        merged = dict(p)
        if l:
            merged["business_name"] = l.get("business_name", "")
            merged["city"] = l.get("city", "")
            merged["state"] = l.get("state", "")
            merged["phone"] = l.get("phone", "")
        filtered.append(merged)
    
    total = len(filtered)
    offset = (page - 1) * per_page
    page_pitches = filtered[offset:offset + per_page]
    
    return jsonify({
        "pitches": page_pitches,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page)
    })

@app.route("/api/pitches/<int:pitch_id>")
def api_pitch_detail(pitch_id):
    d = load_data()
    pitch = next((p for p in d.get("pitches", []) if p.get("id") == pitch_id), None)
    if not pitch:
        return jsonify({"error": "Pitch not found"}), 404
    l = next((l for l in d.get("leads", []) if l.get("id") == pitch.get("lead_id")), None)
    merged = dict(pitch)
    if l:
        merged["business_name"] = l.get("business_name", "")
        merged["phone"] = l.get("phone", "")
        merged["city"] = l.get("city", "")
        merged["state"] = l.get("state", "")
    return jsonify({"pitch": merged})

@app.route("/api/inbox")
def api_inbox():
    d = load_data()
    leads_map = {l["id"]: l for l in d.get("leads", [])}
    sent_pitches = [p for p in d.get("pitches", []) if p.get("status") == "sent"]
    
    conversations = {}
    for p in sent_pitches:
        lid = p.get("lead_id")
        l = leads_map.get(lid, {})
        if lid not in conversations:
            conversations[lid] = {
                "lead_id": lid,
                "business_name": l.get("business_name", "Unknown"),
                "phone": l.get("phone", "—"),
                "city": l.get("city", ""),
                "state": l.get("state", ""),
                "messages": [],
                "last_sent_at": p.get("sent_at", "")
            }
        conversations[lid]["messages"].append({
            "id": p["id"],
            "pitch_text": p["pitch_text"],
            "pitch_type": p.get("pitch_type", "initial"),
            "sent_at": p.get("sent_at", "")
        })
    sorted_convos = sorted(conversations.values(), key=lambda c: c["last_sent_at"] or "", reverse=True)
    return jsonify({"total_conversations": len(sorted_convos), "total_messages": len(sent_pitches), "conversations": sorted_convos})

@app.route("/api/filters")
def api_filters():
    d = load_data()
    cities = sorted(set(l.get("city") for l in d.get("leads", []) if l.get("city")))
    categories = sorted(set(l.get("category") for l in d.get("leads", []) if l.get("category")))
    return jsonify({"cities": cities, "categories": categories})

@app.route("/api/analytics")
def api_analytics():
    d = load_data()
    analyses = d.get("analyses", [])
    leads = d.get("leads", [])
    
    score_dist = {}
    for a in analyses:
        s = a.get("lead_score", "unknown")
        score_dist[s] = score_dist.get(s, 0) + 1
    score_dist = [{"lead_score": k, "count": v} for k, v in score_dist.items()]
    
    city_counts = {}
    for l in leads:
        c = l.get("city", "Unknown")
        city_counts[c] = city_counts.get(c, 0) + 1
    top_cities = sorted([{"city": k, "count": v} for k, v in city_counts.items()], key=lambda x: -x["count"])[:20]
    
    cat_counts = {}
    for l in leads:
        c = l.get("category", "Unknown")
        cat_counts[c] = cat_counts.get(c, 0) + 1
    top_categories = sorted([{"category": k, "count": v} for k, v in cat_counts.items()], key=lambda x: -x["count"])[:20]
    
    return jsonify({
        "score_distribution": score_dist,
        "top_cities": top_cities,
        "top_categories": top_categories,
        "daily_stats": d.get("stats", [])
    })

@app.route("/api/agents")
def api_agents():
    d = load_data()
    leads = d.get("leads", [])
    analyses = d.get("analyses", [])
    pitches = d.get("pitches", [])
    sent = sum(1 for p in pitches if p.get("status") == "sent")
    
    last_analysis = None
    if analyses:
        dates = [a.get("analyzed_at") for a in analyses if a.get("analyzed_at")]
        if dates:
            last_analysis = max(dates)
    
    last_pitch = None
    if pitches:
        dates = [p.get("created_at") for p in pitches if p.get("created_at")]
        if dates:
            last_pitch = max(dates)
    
    return jsonify({
        "agents": [
            {"name": "SCOUT", "status": "online", "last_run": "from snapshot", "today": 0, "total": len(leads)},
            {"name": "ANALYST", "status": "online", "last_run": (last_analysis[:16] if last_analysis else "—"), "today": 0, "total": len(analyses)},
            {"name": "WRITER", "status": "online", "last_run": (last_pitch[:16] if last_pitch else "—"), "today": 0, "total": len(pitches)},
            {"name": "DELIVERY", "status": "read-only", "last_run": "—", "today": 0, "total": sent}
        ]
    })

# Stub endpoints — show as read-only on Vercel
@app.route("/api/pitches/<int:pitch_id>/send", methods=["POST"])
def api_send_pitch_stub(pitch_id):
    return jsonify({"ok": False, "error": "Read-only snapshot. Use live server to send pitches."}), 400

@app.route("/api/pitches/send-batch", methods=["POST"])
def api_send_batch_stub():
    return jsonify({"ok": False, "error": "Read-only snapshot. Use live server to send pitches."}), 400

@app.route("/api/run/<agent>", methods=["POST"])
def api_run_agent_stub(agent):
    return jsonify({"ok": False, "error": f"Cannot run {agent} on read-only snapshot. Use live server."}), 400

# ─── REPORT ──────────────────────────────────────────────────────────────────

@app.route("/api/report")
def api_report():
    """Serve the technical report from the snapshot or markdown file."""
    report_path = HERE.parent / "TECHNICAL_REPORT.md"
    if not report_path.exists():
        return jsonify({"html": "<div class='empty-state'>Report not found</div>"})
    
    lines = report_path.read_text().split("\n")
    html_parts = []
    in_code = False
    code_buf = []
    
    def flush_code():
        nonlocal code_buf
        if code_buf:
            html_parts.append(f'<pre class="report-code"><code>{"\\n".join(code_buf)}</code></pre>')
            code_buf = []
    
    for line in lines:
        if line.startswith("```"):
            if in_code:
                flush_code(); in_code = False
            else:
                flush_code(); in_code = True
            continue
        if in_code:
            code_buf.append(line); continue
        if line.strip() in ("---", "___"):
            flush_code(); html_parts.append('<hr class="report-hr">'); continue
        if line.startswith("### "):
            html_parts.append(f'<h3 class="report-h3">{line[4:]}</h3>'); continue
        if line.startswith("## "):
            html_parts.append(f'<h2 class="report-h2">{line[3:]}</h2>'); continue
        if line.startswith("# "):
            html_parts.append(f'<h1 class="report-h1">{line[2:]}</h1>'); continue
        if line.startswith("> "):
            html_parts.append(f'<blockquote class="report-quote">{line[2:]}</blockquote>'); continue
        if line.startswith("- ") or line.startswith("* "):
            html_parts.append(f'<li class="report-li">{line[2:]}</li>'); continue
        if "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.replace("-","").replace(":","") == "" for c in cells): continue
            if not html_parts or not html_parts[-1].startswith("<table"):
                html_parts.append('<table class="report-table"><thead><tr>' + "".join(f"<th>{c}</th>" for c in cells) + '</tr></thead><tbody>')
            else:
                html_parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue
        if html_parts and html_parts[-1].startswith("<tr") and not line.strip():
            html_parts.append('</tbody></table>')
        line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" class="report-link">\1</a>', line)
        if not line.strip(): continue
        html_parts.append(f'<p class="report-p">{line}</p>')
    
    flush_code()
    if html_parts and html_parts[-1].startswith("<tr"):
        html_parts.append('</tbody></table>')
    return jsonify({"html": "".join(html_parts)})

# ─── PAGES ───────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    landing_path = HERE.parent / "landing.html"
    if landing_path.exists():
        return render_template_string(landing_path.read_text())
    return "landing.html not found", 500

@app.route("/dashboard")
@app.route("/<path:path>")
def admin_page(path=None):
    admin_path = HERE.parent / "admin.html"
    if admin_path.exists():
        return render_template_string(admin_path.read_text())
    return "admin.html not found", 500


# ─── WSGI ────────────────────────────────────────────────────────────────────

# Vercel expects a WSGI app
app = app
