#!/usr/bin/env python3
"""Generate Vercel-compatible JSON snapshot of pipeline data."""
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.schema import get_db

conn = get_db()

lead_cols = ['id', 'business_name', 'category', 'city', 'state', 'address', 'phone', 'website', 'has_website', 'source', 'created_at']
analysis_cols = ['id', 'lead_id', 'status', 'google_maps_found', 'facebook_url', 'facebook_active', 'review_count', 'avg_rating', 'last_review_date', 'other_socials', 'is_active', 'lead_score', 'notes', 'analyzed_at', 'email_found', 'email', 'website_emails', 'website_pages_scraped']
pitch_cols = ['id', 'lead_id', 'analysis_id', 'pitch_text', 'pitch_type', 'status', 'sent_at', 'reply_at', 'reply_text', 'created_at']
stat_cols = ['id', 'stat_name', 'stat_value', 'updated_at']

def rows_to_dicts(rows, cols):
    return [dict(zip(cols, r)) for r in rows]

all_leads = conn.execute("SELECT * FROM leads ORDER BY id").fetchall()
all_analyses = conn.execute("SELECT * FROM lead_analyses").fetchall()
all_pitches = conn.execute("SELECT * FROM pitches").fetchall()
all_stats = conn.execute("SELECT * FROM pipeline_stats").fetchall()

leads_list = rows_to_dicts(all_leads, lead_cols)
analyses_list = rows_to_dicts(all_analyses, analysis_cols)
pitches_list = rows_to_dicts(all_pitches, pitch_cols)
stats_list = rows_to_dicts(all_stats, stat_cols)

# Merge analysis score into lead dicts for convenience
lead_map = {l['id']: l for l in leads_list}
for a in analyses_list:
    lid = a['lead_id']
    if lid in lead_map:
        lead_map[lid]['score'] = a['lead_score']
        lead_map[lid]['email'] = a['email']
        lead_map[lid]['email_found'] = a['email_found']
        lead_map[lid]['facebook_url'] = a['facebook_url']
        lead_map[lid]['facebook_active'] = a['facebook_active']
        lead_map[lid]['review_count'] = a['review_count']
        lead_map[lid]['avg_rating'] = a['avg_rating']
        lead_map[lid]['notes'] = a['notes']

hot = len([l for l in leads_list if l.get('score') == 'hot'])
warm = len([l for l in leads_list if l.get('score') == 'warm'])
cold = len([l for l in leads_list if l.get('score') == 'cold'])

snapshot = {
    "generated_at": datetime.now().isoformat(),
    "total_leads": len(leads_list),
    "total_analyses": len(analyses_list),
    "total_pitches": len(pitches_list),
    "hot": hot,
    "warm": warm,
    "cold": cold,
    "leads": leads_list,
    "analyses": analyses_list,
    "pitches": pitches_list[:100],
    "stats": stats_list,
}

out = Path(__file__).parent.parent / "api" / "data.json"
out.write_text(json.dumps(snapshot, indent=2, default=str))
size_mb = out.stat().st_size / 1024 / 1024
print(f"✅ Snapshot saved: {out} ({size_mb:.1f} MB)")
print(f"   Leads: {len(leads_list)}, Analyses: {len(analyses_list)}, Pitches: {min(100, len(pitches_list))}")
print(f"   Hot: {hot} | Warm: {warm} | Cold: {cold}")
conn.close()
