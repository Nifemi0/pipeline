"""
Pipeline Dashboard — Vercel Serverless Function
Serves HTML directly + proxies API calls to the live backend server.
Full backend (send, inbox, controls) works through the tunnel proxy.
"""
import json
import os
import re
import requests as http_requests
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request, Response

# ─── LIVE BACKEND ────────────────────────────────────────────────────────────
# The cloudflared tunnel pointing to the Flask server with SQLite
# Update this if the tunnel URL changes
LIVE_API_BASE = "https://gem-stamps-watt-whale.trycloudflare.com"

HERE = Path(__file__).parent

# Load snapshot as fallback
def load_data():
    path = HERE / "data.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"stats": {}, "hot_leads": [], "recent": [], "leads": [], "analyses": [], "pitches": []}

app = Flask(__name__)


# ─── PROXY ALL /api/* TO THE LIVE SERVER ─────────────────────────────────────

@app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy_api(subpath):
    """Proxy any /api/* request to the live backend server."""
    target_url = f"{LIVE_API_BASE}/api/{subpath}"
    
    # Forward query params
    params = dict(request.args)
    
    # Forward request body for POST/PUT
    body = request.get_data()
    content_type = request.content_type or "application/json"
    
    # Forward headers (only safe ones — don't forward host/origin)
    headers = {
        "Accept": request.headers.get("Accept", "application/json"),
        "Content-Type": content_type,
        "User-Agent": "Pipeline-Vercel/1.0",
    }
    
    try:
        resp = http_requests.request(
            method=request.method,
            url=target_url,
            params=params,
            data=body,
            headers=headers,
            timeout=15,
        )
        # Return the live response as-is
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )
    except Exception as e:
        # Live server unreachable — fall back to snapshot data
        return fallback_api(subpath)


def fallback_api(subpath):
    """Fallback to snapshot data when the live server is down."""
    d = load_data()
    leads = d.get("leads", [])
    analyses_list = d.get("analyses", [])
    pitches_list = d.get("pitches", [])
    analyses_map = {a["lead_id"]: a for a in analyses_list}
    
    subpath = subpath.rstrip("/")
    
    # /api/stats
    if subpath == "stats":
        total = len(leads)
        analyzed = len(analyses_list)
        return jsonify({
            "total_leads": total,
            "analyzed": analyzed,
            "hot": sum(1 for a in analyses_list if a.get("lead_score") == "hot"),
            "warm": sum(1 for a in analyses_list if a.get("lead_score") == "warm"),
            "cold": sum(1 for a in analyses_list if a.get("lead_score") == "cold"),
            "pitches": len(pitches_list),
            "pitches_sent": sum(1 for p in pitches_list if p.get("status") == "sent"),
            "remaining": total - analyzed,
        })
    
    # /api/leads
    if subpath == "leads":
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        city = request.args.get("city", "")
        score = request.args.get("score", "")
        search = request.args.get("search", "")
        has_website = request.args.get("has_website", "")
        
        filtered = []
        for l in leads:
            a = analyses_map.get(l.get("id"))
            if city and l.get("city") != city: continue
            if score and (not a or a.get("lead_score") != score): continue
            if search and search.lower() not in (l.get("business_name","").lower()): continue
            if has_website == "yes" and not l.get("website"): continue
            if has_website == "no" and l.get("website"): continue
            merged = dict(l)
            if a: merged.update(a)
            filtered.append(merged)
        
        total = len(filtered)
        offset = (page - 1) * per_page
        return jsonify({
            "leads": filtered[offset:offset + per_page],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page)
        })
    
    # /api/leads/<id>
    lead_match = re.match(r"^leads/(\d+)$", subpath)
    if lead_match:
        lid = int(lead_match.group(1))
        lead = next((l for l in leads if l.get("id") == lid), None)
        if not lead: return jsonify({"error": "Not found"}), 404
        return jsonify({
            "lead": lead,
            "analysis": analyses_map.get(lid),
            "pitches": [p for p in pitches_list if p.get("lead_id") == lid]
        })
    
    # /api/pitches
    if subpath == "pitches":
        status = request.args.get("status", "")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        leads_map = {l["id"]: l for l in leads}
        
        filtered = []
        for p in pitches_list:
            if status and p.get("status") != status: continue
            l = leads_map.get(p.get("lead_id"))
            merged = dict(p)
            if l:
                merged.update({"business_name": l.get("business_name",""), "city": l.get("city",""), "state": l.get("state",""), "phone": l.get("phone","")})
            filtered.append(merged)
        
        total = len(filtered)
        offset = (page - 1) * per_page
        return jsonify({
            "pitches": filtered[offset:offset + per_page],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page)
        })
    
    # /api/inbox
    if subpath == "inbox":
        leads_map = {l["id"]: l for l in leads}
        sent = [p for p in pitches_list if p.get("status") == "sent"]
        convos = {}
        for p in sent:
            lid = p.get("lead_id")
            l = leads_map.get(lid, {})
            if lid not in convos:
                convos[lid] = {"lead_id": lid, "business_name": l.get("business_name","Unknown"), "phone": l.get("phone","—"), "messages": [], "last_sent_at": p.get("sent_at","")}
            convos[lid]["messages"].append({"id": p["id"], "pitch_text": p["pitch_text"], "pitch_type": p.get("pitch_type","initial"), "sent_at": p.get("sent_at","")})
        sorted_c = sorted(convos.values(), key=lambda c: c["last_sent_at"] or "", reverse=True)
        return jsonify({"total_conversations": len(sorted_c), "total_messages": len(sent), "conversations": sorted_c})
    
    # /api/filters
    if subpath == "filters":
        cities = sorted(set(l.get("city") for l in leads if l.get("city")))
        cats = sorted(set(l.get("category") for l in leads if l.get("category")))
        return jsonify({"cities": cities, "categories": cats})
    
    # /api/analytics
    if subpath == "analytics":
        score_dist = {}
        for a in analyses_list:
            s = a.get("lead_score", "unknown")
            score_dist[s] = score_dist.get(s, 0) + 1
        city_counts = {}
        for l in leads:
            c = l.get("city", "Unknown")
            city_counts[c] = city_counts.get(c, 0) + 1
        cat_counts = {}
        for l in leads:
            c = l.get("category", "Unknown")
            cat_counts[c] = cat_counts.get(c, 0) + 1
        return jsonify({
            "score_distribution": [{"lead_score": k, "count": v} for k, v in score_dist.items()],
            "top_cities": sorted([{"city": k, "count": v} for k, v in city_counts.items()], key=lambda x: -x["count"])[:20],
            "top_categories": sorted([{"category": k, "count": v} for k, v in cat_counts.items()], key=lambda x: -x["count"])[:20],
            "daily_stats": d.get("stats", []),
        })
    
    # /api/agents
    if subpath == "agents":
        dates_a = [a.get("analyzed_at") for a in analyses_list if a.get("analyzed_at")]
        dates_p = [p.get("created_at") for p in pitches_list if p.get("created_at")]
        return jsonify({"agents": [
            {"name": "SCOUT", "status": "offline", "last_run": "—", "today": 0, "total": len(leads)},
            {"name": "ANALYST", "status": "offline", "last_run": (max(dates_a)[:16] if dates_a else "—"), "today": 0, "total": len(analyses_list)},
            {"name": "WRITER", "status": "offline", "last_run": (max(dates_p)[:16] if dates_p else "—"), "today": 0, "total": len(pitches_list)},
            {"name": "DELIVERY", "status": "offline", "last_run": "—", "today": 0, "total": sum(1 for p in pitches_list if p.get("status") == "sent")}
        ]})
    
    # /api/report
    if subpath == "report":
        return api_report_internal()
    
    # /api/pitches/<id> — catch single pitch
    pitch_match = re.match(r"^pitches/(\d+)$", subpath)
    if pitch_match:
        pid = int(pitch_match.group(1))
        p = next((x for x in pitches_list if x.get("id") == pid), None)
        if not p: return jsonify({"error": "Not found"}), 404
        l = next((x for x in leads if x.get("id") == p.get("lead_id")), None)
        merged = dict(p)
        if l: merged.update({"business_name": l.get("business_name",""), "phone": l.get("phone",""), "city": l.get("city",""), "state": l.get("state","")})
        return jsonify({"pitch": merged})
    
    # Unknown API route
    return jsonify({"error": f"Unknown API route: {subpath}"}), 404


# ─── REPORT ──────────────────────────────────────────────────────────────────

def api_report_internal():
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
            flush_code(); in_code = not in_code; continue
        if in_code: code_buf.append(line); continue
        if line.strip() in ("---", "___"): flush_code(); html_parts.append('<hr class="report-hr">'); continue
        if line.startswith("### "): html_parts.append(f'<h3 class="report-h3">{line[4:]}</h3>'); continue
        if line.startswith("## "): html_parts.append(f'<h2 class="report-h2">{line[3:]}</h2>'); continue
        if line.startswith("# "): html_parts.append(f'<h1 class="report-h1">{line[2:]}</h1>'); continue
        if line.startswith("> "): html_parts.append(f'<blockquote class="report-quote">{line[2:]}</blockquote>'); continue
        if line.startswith("- ") or line.startswith("* "): html_parts.append(f'<li class="report-li">{line[2:]}</li>'); continue
        if "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.replace("-","").replace(":","")=="" for c in cells): continue
            if not html_parts or not html_parts[-1].startswith("<table"):
                html_parts.append('<table class="report-table"><thead><tr>'+"".join(f"<th>{c}</th>" for c in cells)+'</tr></thead><tbody>')
            else:
                html_parts.append("<tr>"+"".join(f"<td>{c}</td>" for c in cells)+"</tr>")
            continue
        if html_parts and html_parts[-1].startswith("<tr") and not line.strip(): html_parts.append('</tbody></table>')
        line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" class="report-link">\1</a>', line)
        if not line.strip(): continue
        html_parts.append(f'<p class="report-p">{line}</p>')
    
    flush_code()
    if html_parts and html_parts[-1].startswith("<tr"): html_parts.append('</tbody></table>')
    return jsonify({"html": "".join(html_parts)})

@app.route("/api/report")
def api_report_route():
    return api_report_internal()


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

app = app
