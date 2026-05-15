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
            (SELECT COUNT(*) FROM pitches) as pitches
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

    # Last run times
    last_analysis = db_one("SELECT analyzed_at FROM lead_analyses ORDER BY analyzed_at DESC LIMIT 1")
    last_pitch = db_one("SELECT created_at FROM pitches ORDER BY created_at DESC LIMIT 1")

    return jsonify({
        "agents": [
            {"name": "SCOUT", "status": "online", "last_run": "06:00 UTC", "today": 0, "total": total_leads},
            {"name": "ANALYST", "status": "online", "last_run": (last_analysis["analyzed_at"][:16] if last_analysis and last_analysis["analyzed_at"] else "—"), "today": today_analyzed, "total": total_analyzed},
            {"name": "WRITER", "status": "online", "last_run": (last_pitch["created_at"][:16] if last_pitch and last_pitch["created_at"] else "—"), "today": today_pitches, "total": total_pitches},
            {"name": "DELIVERY", "status": "standby", "last_run": "—", "today": 0, "total": 0}
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
