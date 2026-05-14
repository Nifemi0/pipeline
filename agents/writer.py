#!/usr/bin/env python3
"""
Writer Agent — Agent 3 of the Sales Agent Pipeline
Generates personalized website-building pitches for verified leads.
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.schema import get_db, init_db, update_stat

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

PITCH_TEMPLATES = {
    "plumber": "Help customers find you when their pipes burst at 2AM — a website shows you're open.",
    "electrician": "When the power goes out, homeowners search Google. Make sure they find you.",
    "roofer": "Storm season means urgent roof repairs — a website captures that desperate search traffic.",
    "landscaper": "Your before/after photos are your best sales tool. Put them online.",
    "painter": "Show off your best paint jobs with a gallery. Let the work speak for itself.",
    "hvac contractor": "AC breaks in summer, heat goes out in winter — be the first result they see.",
    "general contractor": "Homeowners research extensively before hiring. Be where they look.",
    "handyman": "Small jobs add up. A simple site sends steady leads to your phone.",
    "concrete contractor": "Driveways, patios, foundations — show homeowners what's possible.",
    "tree service": "Storm damage means urgent calls. A website captures them 24/7.",
    "default": "Your customers are searching online. Make sure they find your business."
}


def generate_pitch(lead_name, category, city, state, lead_score, fb_url=None):
    """
    Generate a personalized pitch message using Gemini.
    Falls back to template-based pitch if no API key.
    """
    if not GEMINI_API_KEY:
        return template_pitch(lead_name, category, city, lead_score, fb_url)
    
    prompt = f"""You are a professional sales copywriter for a web design agency.
Write a short, personalized pitch message (max 3 sentences) for:

Business: {lead_name}
Category: {category}
Location: {city}, {state}
Lead Quality: {lead_score}
Facebook: {fb_url or 'Not found'}

The goal: Offer a free one-page website demo. No pricing in the pitch.
Tone: Professional, helpful, not pushy. Reference something specific about their business/location.
IMPORTANT: Do NOT mention pricing. Just offer a free demo.

Respond with ONLY the pitch text. No quotes, no labels."""

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            pitch = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Clean up
            pitch = pitch.strip("\"'")
            return pitch
    except:
        pass
    
    return template_pitch(lead_name, category, city, lead_score, fb_url)


def template_pitch(lead_name, category, city, lead_score, fb_url=None):
    """Template-based pitch when no AI available."""
    template = PITCH_TEMPLATES.get(category, PITCH_TEMPLATES["default"])
    
    base = f"Hi {lead_name}, I noticed your {category} business in {city}. {template}"
    closing = " I'd love to build you a free one-page website so your customers can find you online. Just say yes and I'll have a demo ready within 24 hours."
    
    if fb_url:
        personalization = f" Saw you on Facebook — a website would give you even more reach."
        return base + personalization + closing
    
    return base + closing


def writer_run(limit=10):
    """
    Generate pitches for analyzed leads that haven't been pitched yet.
    """
    init_db()
    conn = get_db()
    
    rows = conn.execute("""
        SELECT l.*, la.lead_score, la.facebook_url, la.is_active, la.id as analysis_id
        FROM leads l
        JOIN lead_analyses la ON l.id = la.lead_id
        LEFT JOIN pitches p ON l.id = p.lead_id
        WHERE p.id IS NULL AND la.is_active = 1
        LIMIT ?
    """, (limit,)).fetchall()
    
    if not rows:
        print("🤖 Writer Agent — No leads needing pitches")
        return {"pitches": 0}
    
    print(f"🤖 Writer Agent — Writing {len(rows)} personalized pitches")
    pitches_written = 0
    
    for row in rows:
        lead = dict(row)
        print(f"  ✍️ {lead['business_name']} ({lead['lead_score']})...", end=" ", flush=True)
        
        pitch = generate_pitch(
            lead["business_name"],
            lead["category"],
            lead["city"],
            lead["state"],
            lead["lead_score"],
            lead["facebook_url"]
        )
        
        conn.execute("""
            INSERT INTO pitches (lead_id, analysis_id, pitch_text, pitch_type, status)
            VALUES (?, ?, ?, 'initial', 'pending')
        """, (lead["id"], lead["analysis_id"], pitch))
        conn.commit()
        pitches_written += 1
        
        print("done")
        time.sleep(random.uniform(0.5, 1.0))
    
    update_stat(conn, "pitches_generated", pitches_written)
    conn.close()
    
    print(f"\n📊 Writer Report: {pitches_written} pitches written")
    return {"pitches": pitches_written}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Writer Agent — Generate pitches")
    parser.add_argument("--limit", type=int, default=10, help="Pitches to write")
    args = parser.parse_args()
    writer_run(limit=args.limit)
