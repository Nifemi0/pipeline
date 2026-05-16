#!/usr/bin/env python3
"""
Writer Agent — Agent 3 of the Sales Agent Pipeline
Generates personalized pitches using Google Gemini AI.
Now featuring business website research for hyper-personalized outreach.

Integrates with Google Gemini Challenge ($5K prize).
Prizes: Best use of Gemini — 1st: $5,000, 2nd: $3,000, 3rd: $2,000
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

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.schema import get_db, init_db, update_stat

# Load .env
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")  # Flash = speed, Pro = depth

# Website research timeout
WEBSITE_TIMEOUT = 4  # Quick grab or skip

# ─── GEMINI CLIENT ────────────────────────────────────────────────────────────

def get_gemini_client():
    """Initialise the Google GenAI client."""
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client
    except ImportError:
        print("  ⚠️  google-genai not installed. Run: pip3 install google-genai")
        return None
    except Exception as e:
        print(f"  ⚠️  Gemini client error: {e}")
        return None


def gemini_generate(prompt, model=None, temperature=0.7, max_tokens=300):
    """
    Generate text using Google Gemini via the official SDK.
    Returns the generated text or None on failure.
    """
    model = model or GEMINI_MODEL
    client = get_gemini_client()
    if not client:
        return None

    try:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "top_p": 0.95,
            }
        )
        text = resp.text.strip()
        return text
    except Exception as e:
        print(f"  ⚠️  Gemini API error: {e}")
        return None


# ─── WEBSITE RESEARCH ────────────────────────────────────────────────────────

def fetch_website_text(business_name, website_url=None):
    """
    Try website research only if a real URL exists.
    """
    if not website_url or website_url in ("", "N/A", "None"):
        return None

    # Strip protocol and build clean URL
    url = website_url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    try:
        resp = requests.get(
            url,
            timeout=(2, WEBSITE_TIMEOUT),  # connect timeout, read timeout
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None

        html = resp.text.lower()

        # Extract useful snippets
        extracted = []

        # Title
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            extracted.append(f"Title: {title_match.group(1).strip()[:120]}")

        # Meta description
        desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
        if desc_match:
            extracted.append(f"Tagline: {desc_match.group(1).strip()[:200]}")

        # H1 headings
        h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE)
        if h1s:
            extracted.append(f"Headings: {' | '.join(h.strip()[:60] for h in h1s[:3])}")

        # Detect services/products
        service_keywords = ["service", "offer", "we do", "solutions", "products", "expertise"]
        found_services = []
        for kw in service_keywords:
            matches = re.findall(rf'(?:{kw})[^.]*\.', html[:5000])
            if matches:
                found_services.extend(m.strip()[:100] for m in matches[:2])
        if found_services:
            extracted.append(f"Services: {' | '.join(found_services[:3])}")

        # Location detection
        city_match = re.search(r'<span[^>]*itemprop=["\']addressLocality["\'][^>]*>(.*?)</span>', html, re.IGNORECASE)
        if city_match:
            extracted.append(f"Location: {city_match.group(1).strip()}")
        else:
            # Try generic city patterns in text
            locations = re.findall(r'(?:serving|located in|based in|in the)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', html[:3000])
            if locations:
                extracted.append(f"Location mention: {locations[0]}")

        if extracted:
            return "\n".join(extracted[:6])
        return None

    except requests.Timeout:
        return None
    except Exception:
        return None


# ─── PITCH GENERATION ────────────────────────────────────────────────────────

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


def generate_pitch(lead_name, category, city, state, lead_score, lead_score_num=None, website_url=None, fb_url=None):
    """
    Generate a personalized pitch using Google Gemini.
    First tries to research the business website for context.
    Falls back to template if Gemini is unavailable.

    Returns: (pitch_text, model_used)
    """
    # Try website research
    website_context = fetch_website_text(lead_name, website_url)
    if website_context:
        print(f"  🌐 Website found — extracting context...")

    # Attempt Gemini generation
    prompt = build_gemini_prompt(lead_name, category, city, state, lead_score, website_context, fb_url)

    pitch = gemini_generate(prompt, temperature=0.8, max_tokens=350)
    if pitch:
        # Clean up
        pitch = pitch.strip("\"' ")
        return pitch, "gemini-2.5-flash"

    # Fallback: try with a simpler prompt
    simple_prompt = (
        f"Write a 2-sentence pitch for a {category} business called '{lead_name}' in {city}, {state}. "
        f"Offer a free website demo. No pricing. Professional, short, direct."
    )
    pitch = gemini_generate(simple_prompt, temperature=0.7, max_tokens=200)
    if pitch:
        return pitch.strip("\"' "), "gemini-2.5-flash"

    # Final fallback to template
    return template_pitch(lead_name, category, city, lead_score, fb_url), "template"


def build_gemini_prompt(lead_name, category, city, state, lead_score, website_context=None, fb_url=None):
    """Build an detailed prompt with website context for the Gemini model."""
    prompt = f"""You are a world-class B2B sales copywriter. Your job is to write ONE short, punchy cold outreach message.

BUSINESS: {lead_name}
CATEGORY: {category}
LOCATION: {city}, {state}
LEAD QUALITY: {lead_score}
"""

    if website_context:
        prompt += f"\nWEBSITE ANALYSIS:\n{website_context}\n"

    if fb_url:
        prompt += f"\nFACEBOOK: {fb_url} (they have a social presence but no website yet)\n"

    prompt += """
RULES:
- MAX 3 sentences. Short and scannable.
- Reference something SPECIFIC about this business or location (use the website analysis if available).
- Offer a free one-page website demo. NO pricing mentioned whatsoever.
- Tone: professional, helpful, confident. Not pushy, not salesy.
- Do NOT use fluff like "I hope this message finds you well" or "I was browsing your business".
- Write as if one professional texting another.

OUTPUT: ONLY the pitch text. No quotes, no labels, no subject line."""
    return prompt


def template_pitch(lead_name, category, city, lead_score, fb_url=None):
    """Template-based pitch when no AI available."""
    template = PITCH_TEMPLATES.get(category.lower(), PITCH_TEMPLATES["default"])

    base = f"Hi {lead_name}, I noticed your {category} business in {city}. {template}"
    closing = " I'd love to build you a free one-page website so your customers can find you online. Just say yes and I'll have a demo ready within 24 hours."

    if fb_url:
        personalization = f" Saw you on Facebook — a website would give you even more reach."
        return base + personalization + closing

    return base + closing


# ─── MAIN RUNNER ──────────────────────────────────────────────────────────────

def writer_run(limit=10):
    """
    Generate pitches for analyzed leads that haven't been pitched yet.
    Uses Google Gemini for AI-powered generation with website research.
    """
    init_db()
    conn = get_db()

    rows = conn.execute("""
        SELECT l.*, la.lead_score, la.facebook_url, l.website as website_url,
               la.is_active, la.id as analysis_id
        FROM leads l
        JOIN lead_analyses la ON l.id = la.lead_id
        LEFT JOIN pitches p ON l.id = p.lead_id
        WHERE p.id IS NULL AND la.is_active = 1
        ORDER BY CASE la.lead_score
            WHEN 'hot' THEN 100
            WHEN 'warm' THEN 60
            ELSE 20
        END DESC
        LIMIT ?
    """, (limit,)).fetchall()

    if not rows:
        print("📝 Writer Agent — No leads needing pitches")
        return {"pitches": 0, "gemini_used": 0, "template_used": 0}

    print(f"📝 Writer Agent — Generating {len(rows)} pitches (Gemini + website research)")
    pitches_written = 0
    gemini_count = 0
    template_count = 0

    for i, row in enumerate(rows):
        lead = dict(row)
        print(f"  [{i+1}/{len(rows)}] {lead['business_name']} (score: {lead['lead_score']})...", end=" ", flush=True)

        pitch, model_used = generate_pitch(
            lead["business_name"],
            lead["category"],
            lead["city"],
            lead["state"],
            lead["lead_score"],
            website_url=lead.get("website_url"),
            fb_url=lead.get("facebook_url"),
        )

        if model_used == "gemini-2.5-flash":
            gemini_count += 1
        else:
            template_count += 1

        conn.execute("""
            INSERT INTO pitches (lead_id, analysis_id, pitch_text, pitch_type, status)
            VALUES (?, ?, ?, 'initial', 'pending')
        """, (lead["id"], lead["analysis_id"], pitch))
        conn.commit()
        pitches_written += 1

        print(f"✓ ({model_used})")
        time.sleep(random.uniform(0.3, 0.8))

    update_stat(conn, "pitches_generated", pitches_written)
    conn.close()

    print(f"\n📊 Writer Report: {pitches_written} pitches | "
          f"{'🟢' if gemini_count > 0 else '🔴'} Gemini: {gemini_count} | "
          f"📋 Template: {template_count}")
    return {"pitches": pitches_written, "gemini_used": gemini_count, "template_used": template_count}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Writer Agent — Generate pitches via Gemini")
    parser.add_argument("--limit", type=int, default=10, help="Pitches to write")
    args = parser.parse_args()
    writer_run(limit=args.limit)
