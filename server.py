#!/usr/bin/env python3
"""
Pipeline Admin Server — serves admin dashboard + live API from SQLite
Run: python3 server.py
Tunnel: cloudflared tunnel --url http://localhost:5050
"""

import json
import os
import subprocess
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string

HERE = Path(__file__).parent
DB_PATH = HERE / "data" / "sales_agent.db"
TEMPLATE_PATH = HERE / "admin.html"
LANDING_PATH = HERE / "landing.html"

app = Flask(__name__)

# ─── DB HELPERS ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def db_rows(query, params=()):
    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_one(query, params=()):
    rows = db_rows(query, params)
    return rows[0] if rows else None

# ─── API ENDPOINTS ─────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    stats = db_one("""
        SELECT 
            (SELECT COUNT(*) FROM leads) as total_leads,
            (SELECT COUNT(*) FROM lead_analyses) as analyzed,
            (SELECT COUNT(*) FROM lead_analyses WHERE lead_score='hot') as hot,
            (SELECT COUNT(*) FROM lead_analyses WHERE lead_score='warm') as warm,
            (SELECT COUNT(*) FROM lead_analyses WHERE lead_score='cold') as cold,
            (SELECT COUNT(*) FROM pitches) as pitches,
            (SELECT COUNT(*) FROM pitches WHERE status='sent') as pitches_sent
    """)
    stats["remaining"] = stats["total_leads"] - stats["analyzed"]
    return jsonify(stats)

@app.route("/api/leads")
def api_leads():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    city = request.args.get("city", "")
    category = request.args.get("category", "")
    score = request.args.get("score", "")
    search = request.args.get("search", "")
    has_website = request.args.get("has_website", "")

    where = ["1=1"]
    params = []

    if city:
        where.append("l.city = ?")
        params.append(city)
    if category:
        where.append("l.category = ?")
        params.append(category)
    if score:
        where.append("la.lead_score = ?")
        params.append(score)
    if search:
        where.append("l.business_name LIKE ?")
        params.append(f"%{search}%")
    if has_website == "yes":
        where.append("(l.website IS NOT NULL AND l.website != '')")
    elif has_website == "no":
        where.append("(l.website IS NULL OR l.website = '')")

    where_clause = " AND ".join(where)

    total = db_one(f"""
        SELECT COUNT(*) as c FROM leads l
        LEFT JOIN lead_analyses la ON l.id = la.lead_id
        WHERE {where_clause}
    """, params)["c"]

    offset = (page - 1) * per_page
    leads = db_rows(f"""
        SELECT l.*, la.lead_score, la.avg_rating, la.review_count, la.is_active, 
               la.analyzed_at, la.email_found, la.email, la.facebook_url, la.notes
        FROM leads l
        LEFT JOIN lead_analyses la ON l.id = la.lead_id
        WHERE {where_clause}
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])

    return jsonify({
        "leads": leads,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page)
    })

@app.route("/api/leads/<int:lead_id>")
def api_lead_detail(lead_id):
    lead = db_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    
    analysis = db_one("SELECT * FROM lead_analyses WHERE lead_id = ?", (lead_id,))
    pitches = db_rows("SELECT * FROM pitches WHERE lead_id = ? ORDER BY created_at DESC", (lead_id,))
    
    return jsonify({
        "lead": lead,
        "analysis": analysis,
        "pitches": pitches
    })

@app.route("/api/pitches")
def api_pitches():
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    where = "1=1"
    params = []
    if status:
        where = "p.status = ?"
        params.append(status)

    total = db_one(f"SELECT COUNT(*) as c FROM pitches p WHERE {where}", params)["c"]
    offset = (page - 1) * per_page

    pitches = db_rows(f"""
        SELECT p.*, l.business_name, l.city, l.state
        FROM pitches p
        JOIN leads l ON p.lead_id = l.id
        WHERE {where}
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])

    return jsonify({
        "pitches": pitches,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page)
    })

@app.route("/api/analytics")
def api_analytics():
    score_dist = db_rows("""
        SELECT lead_score, COUNT(*) as count 
        FROM lead_analyses GROUP BY lead_score
    """)

    cities = db_rows("""
        SELECT city, COUNT(*) as count 
        FROM leads GROUP BY city ORDER BY count DESC LIMIT 20
    """)

    categories = db_rows("""
        SELECT category, COUNT(*) as count 
        FROM leads GROUP BY category ORDER BY count DESC LIMIT 20
    """)

    daily = db_rows("""
        SELECT date, leads_scouted, leads_analyzed, pitches_generated
        FROM pipeline_stats ORDER BY date DESC LIMIT 14
    """)

    return jsonify({
        "score_distribution": score_dist,
        "top_cities": cities,
        "top_categories": categories,
        "daily_stats": daily
    })

@app.route("/api/agents")
def api_agents():
    today = datetime.now().strftime("%Y-%m-%d")
    
    today_analyzed = db_one("""
        SELECT COUNT(*) as c FROM lead_analyses 
        WHERE date(analyzed_at) = ?
    """, (today,))["c"]
    
    today_pitches = db_one("""
        SELECT COUNT(*) as c FROM pitches 
        WHERE date(created_at) = ?
    """, (today,))["c"]
    
    total_leads = db_one("SELECT COUNT(*) as c FROM leads")["c"]
    total_analyzed = db_one("SELECT COUNT(*) as c FROM lead_analyses")["c"]
    total_pitches = db_one("SELECT COUNT(*) as c FROM pitches")["c"]
    total_sent = db_one("SELECT COUNT(*) as c FROM pitches WHERE status='sent'")["c"]

    # Last run times
    last_analysis = db_one("SELECT analyzed_at FROM lead_analyses ORDER BY analyzed_at DESC LIMIT 1")
    last_pitch = db_one("SELECT created_at FROM pitches ORDER BY created_at DESC LIMIT 1")

    return jsonify({
        "agents": [
            {"name": "SCOUT", "status": "online", "last_run": "06:00 UTC", "today": 0, "total": total_leads},
            {"name": "ANALYST", "status": "online", "last_run": (last_analysis["analyzed_at"][:16] if last_analysis and last_analysis["analyzed_at"] else "—"), "today": today_analyzed, "total": total_analyzed},
            {"name": "WRITER", "status": "online", "last_run": (last_pitch["created_at"][:16] if last_pitch and last_pitch["created_at"] else "—"), "today": today_pitches, "total": total_pitches},
            {"name": "DELIVERY", "status": "standby", "last_run": "—", "today": 0, "total": total_sent}
        ]
    })

@app.route("/api/filters")
def api_filters():
    cities = db_rows("SELECT DISTINCT city FROM leads ORDER BY city")
    categories = db_rows("SELECT DISTINCT category FROM leads ORDER BY category")
    return jsonify({
        "cities": [r["city"] for r in cities if r["city"]],
        "categories": [r["category"] for r in categories if r["category"]]
    })

# ─── SENDER (Sandbox SMS) ───────────────────────────────────────────────────────

from agents.sender import send_pitch, send_batch

@app.route("/api/inbox")
def api_inbox():
    """Get sent pitches grouped by business for SMS inbox view."""
    pitches = db_rows("""
        SELECT p.*, l.business_name, l.phone, l.city, l.state
        FROM pitches p
        JOIN leads l ON p.lead_id = l.id
        WHERE p.status = 'sent'
        ORDER BY p.sent_at DESC
        LIMIT 200
    """)
    # Group by lead_id
    conversations = {}
    for p in pitches:
        lid = p["lead_id"]
        if lid not in conversations:
            conversations[lid] = {
                "lead_id": lid,
                "business_name": p["business_name"],
                "phone": p["phone"] or "—",
                "city": p["city"],
                "state": p["state"],
                "messages": [],
                "last_sent_at": p["sent_at"]
            }
        conversations[lid]["messages"].append({
            "id": p["id"],
            "pitch_text": p["pitch_text"],
            "pitch_type": p["pitch_type"],
            "sent_at": p["sent_at"]
        })
    # Sort conversations by last sent (most recent first)
    sorted_convos = sorted(conversations.values(), key=lambda c: c["last_sent_at"] or "", reverse=True)
    return jsonify({
        "total_conversations": len(sorted_convos),
        "total_messages": len(pitches),
        "conversations": sorted_convos
    })


@app.route("/api/pitches/<int:pitch_id>/send", methods=["POST"])
def api_send_pitch(pitch_id):
    """Send a single pitch (sandbox SMS)."""
    result = send_pitch(pitch_id)
    status = 200 if result["ok"] else 400
    return jsonify(result), status


@app.route("/api/pitches/send-batch", methods=["POST"])
def api_send_pitch_batch():
    """Send multiple pitches (sandbox SMS)."""
    data = request.get_json(silent=True) or {}
    pitch_ids = data.get("pitch_ids", [])
    if not pitch_ids:
        return jsonify({"ok": False, "error": "No pitch_ids provided"}), 400
    result = send_batch(pitch_ids)
    return jsonify(result)


@app.route("/api/pitches/<int:pitch_id>")
def api_pitch_detail(pitch_id):
    """Get full pitch text with lead info."""
    pitch = db_one("""
        SELECT p.*, l.business_name, l.phone, l.city, l.state, l.category
        FROM pitches p
        JOIN leads l ON p.lead_id = l.id
        WHERE p.id = ?
    """, (pitch_id,))
    if not pitch:
        return jsonify({"error": "Pitch not found"}), 404
    return jsonify({"pitch": pitch})


@app.route("/api/report")
def api_report():
    """Serve the technical report as HTML."""
    report_path = HERE / "TECHNICAL_REPORT.md"
    if not report_path.exists():
        return jsonify({"html": "<div class='empty-state'>Report not found</div>"})
    
    lines = report_path.read_text().split("\n")
    html_parts = []
    in_code_block = False
    code_buffer = []
    
    def end_code_block():
        nonlocal code_buffer
        if code_buffer:
            html_parts.append(f'<pre class="report-code"><code>{"\\n".join(code_buffer)}</code></pre>')
            code_buffer = []
    
    for line in lines:
        # Code block toggle
        if line.startswith("```"):
            if in_code_block:
                end_code_block()
                in_code_block = False
            else:
                end_code_block()
                in_code_block = True
            continue
        
        if in_code_block:
            code_buffer.append(line)
            continue
        
        # Horizontal rule
        if line.strip() == "---" or line.strip() == "___":
            end_code_block()
            html_parts.append('<hr class="report-hr">')
            continue
        
        # Headers
        if line.startswith("### "):
            html_parts.append(f'<h3 class="report-h3">{line[4:]}</h3>')
            continue
        if line.startswith("## "):
            html_parts.append(f'<h2 class="report-h2">{line[3:]}</h2>')
            continue
        if line.startswith("# "):
            html_parts.append(f'<h1 class="report-h1">{line[2:]}</h1>')
            continue
        
        # Blockquote
        if line.startswith("> "):
            html_parts.append(f'<blockquote class="report-quote">{line[2:]}</blockquote>')
            continue
        
        # Unordered list
        if line.startswith("- ") or line.startswith("* "):
            html_parts.append(f'<li class="report-li">{line[2:]}</li>')
            continue
        
        # Table row
        if "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            # Skip separator rows (---|---|---)
            if all(c.replace("-", "").replace(":", "") == "" for c in cells):
                continue
            if not html_parts or not html_parts[-1].startswith("<table"):
                html_parts.append('<table class="report-table"><thead><tr>')
                for c in cells:
                    html_parts.append(f'<th>{c}</th>')
                html_parts.append('</tr></thead><tbody>')
            else:
                html_parts.append('<tr>')
                for c in cells:
                    html_parts.append(f'<td>{c}</td>')
                html_parts.append('</tr>')
            continue
        
        # Close any open table
        if html_parts and html_parts[-1].startswith("<tr") and not line.strip():
            html_parts.append('</tbody></table>')
        
        # Bold text inline
        def bold_repl(m):
            return f'<strong>{m.group(1)}</strong>'
        import re
        line = re.sub(r'\*\*(.*?)\*\*', bold_repl, line)
        
        # Links
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" class="report-link">\1</a>', line)
        
        # Empty line = paragraph break
        if not line.strip():
            continue
        
        # Regular paragraph
        html_parts.append(f'<p class="report-p">{line}</p>')
    
    end_code_block()
    # Close any open table
    if html_parts and html_parts[-1].startswith("<tr"):
        html_parts.append('</tbody></table>')
    
    html = "".join(html_parts)
    return jsonify({"html": html})


# ─── ADMIN ACTIONS ─────────────────────────────────────────────────────────────

@app.route("/api/run/<agent>", methods=["POST"])
def api_run_agent(agent):
    """Trigger an agent run."""
    if agent == "analyst":
        limit = request.args.get("limit", 10, type=int)
        result = subprocess.run(
            ["python3", "agents/analyst.py", "--limit", str(limit)],
            cwd=HERE, capture_output=True, text=True, timeout=300
        )
        return jsonify({"ok": True, "output": result.stdout[:500], "error": result.stderr[:200]})
    elif agent == "writer":
        limit = request.args.get("limit", 10, type=int)
        result = subprocess.run(
            ["python3", "agents/writer.py", "--limit", str(limit)],
            cwd=HERE, capture_output=True, text=True, timeout=300
        )
        return jsonify({"ok": True, "output": result.stdout[:500], "error": result.stderr[:200]})
    elif agent == "pipeline":
        result = subprocess.run(
            ["python3", "orchestrator.py", "--mode", "full", "--analyst-limit", "10", "--writer-limit", "10"],
            cwd=HERE, capture_output=True, text=True, timeout=600
        )
        return jsonify({"ok": True, "output": result.stdout[:500], "error": result.stderr[:200]})
    elif agent == "refresh-data":
        """Regenerate the api/data.json snapshot for Vercel deployment."""
        result = subprocess.run(
            ["python3", "scripts/snapshot.py"],
            cwd=HERE, capture_output=True, text=True, timeout=60
        )
        return jsonify({"ok": True, "output": result.stdout[:500] if result.stdout else "Snapshot refreshed"})
    return jsonify({"ok": False, "error": f"Unknown agent: {agent}"}), 400

# ─── ADMIN PAGE ────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    if LANDING_PATH.exists():
        return render_template_string(LANDING_PATH.read_text())
    return "landing.html not found", 500

@app.route("/dashboard")
@app.route("/<path:path>")
def admin_page(path=None):
    if TEMPLATE_PATH.exists():
        return render_template_string(TEMPLATE_PATH.read_text())
    return "admin.html not found", 500

# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
    print(f"🚀 Pipeline Admin Server → http://localhost:{port}")
    print(f"   Tunnel: cloudflared tunnel --url http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
