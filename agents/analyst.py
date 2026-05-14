#!/usr/bin/env python3
"""
Analyst Agent — Agent 2 of the Sales Agent Pipeline
Takes raw leads, researches them via Yelp Fusion API, scores lead quality.
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

# ─── ENV LOADER ──────────────────────────────────────────────────────────────
def load_dotenv():
    """Load .env file from project root if env vars not already set."""
    if os.environ.get("YELP_API_KEY"):
        return  # already set
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("'\"")
            os.environ.setdefault(key, val)

load_dotenv()

# ─── CONFIG ───────────────────────────────────────────────────────────────────

MIN_DELAY = 0.5
MAX_DELAY = 1.5

YELP_API_KEY = os.environ.get("YELP_API_KEY", "")
YELP_CLIENT_ID = os.environ.get("YELP_CLIENT_ID", "")
YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"

# Gemini API for smart analysis
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# High-value trades we care about
TRADE_CATEGORIES = [
    "plumbing", "electricians", "roofing", "hvac", "masonry", "concrete",
    "landscaping", "paving", "fencing", "gutters", "painters",
    "drywall", "contractors", "handyman", "carpenters", "flooring",
    "siding", "windows", "doors", "remodeling"
]


# ─── YELP FUSION API ─────────────────────────────────────────────────────────

def search_yelp(business_name, city, state):
    """
    Research a lead using Yelp Fusion API.
    Returns real ratings, review counts, open/closed status.
    """
    if not YELP_API_KEY:
        print("⚠️  No YELP_API_KEY set — falling back")
        return search_maps_scrape(business_name, city, state)

    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}

    # Try exact business name match first
    query = f"{business_name} {city} {state}"
    params = {
        "term": business_name,
        "location": f"{city}, {state}",
        "limit": 3,
    }

    try:
        resp = requests.get(
            YELP_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=10
        )

        if resp.status_code == 401:
            print("⚠️  Yelp API auth failed — check API key")
            return search_maps_scrape(business_name, city, state)

        if resp.status_code != 200:
            print(f"⚠️  Yelp returned {resp.status_code}")
            return search_maps_scrape(business_name, city, state)

        data = resp.json()
        businesses = data.get("businesses", [])
        if not businesses:
            return {
                "found": False,
                "source": "yelp",
                "rating": 0,
                "review_count": 0,
                "is_active": None,
                "website": "",
                "phone": "",
                "address": "",
                "yelp_url": "",
            }

        # Pick best match — prefer exact name match
        best = None
        for biz in businesses:
            name = biz.get("name", "").lower()
            if business_name.lower() in name or name in business_name.lower():
                best = biz
                break

        if not best:
            best = businesses[0]  # closest match

        return {
            "found": True,
            "source": "yelp",
            "name": best.get("name", business_name),
            "rating": best.get("rating", 0),
            "review_count": best.get("review_count", 0),
            "is_active": not best.get("is_closed", True),
            "is_closed": best.get("is_closed", False),
            "website": best.get("url", ""),  # Yelp business page URL
            "phone": best.get("phone", ""),
            "address": ", ".join(best.get("location", {}).get("display_address", [])),
            "yelp_url": best.get("url", ""),
            "categories": [c["title"] for c in best.get("categories", [])],
            "price": best.get("price", ""),
        }

    except requests.exceptions.Timeout:
        print("⏱️  Yelp timeout")
        return search_maps_scrape(business_name, city, state)
    except Exception as e:
        print(f"⚠️  Yelp error: {e}")
        return search_maps_scrape(business_name, city, state)


# ─── FALLBACK: WEB SCRAPE ────────────────────────────────────────────────────

def get_user_agent():
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    return random.choice(agents)


def search_maps_scrape(business_name, city, state):
    """Fallback web scrape when Yelp is unavailable."""
    query = f"{business_name} {city} {state}"
    headers = {"User-Agent": get_user_agent(), "Accept-Language": "en-US,en;q=0.9"}

    # Google check
    try:
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=en"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            text = resp.text.lower()
            permanently_closed = "permanently closed" in text
            return {
                "found": True,
                "source": "web_check",
                "rating": 0,
                "review_count": 0,
                "is_active": not permanently_closed,
                "website": "",
                "phone": "",
                "address": "",
                "yelp_url": "",
            }
    except:
        pass

    # DuckDuckGo fallback
    try:
        ddg_url = f"https://lite.duckduckgo.com/lite/?q={requests.utils.quote(query)}"
        resp = requests.get(ddg_url, headers=headers, timeout=8)
        if resp.status_code == 200:
            return {
                "found": True,
                "source": "ddg_check",
                "rating": 0,
                "review_count": 0,
                "is_active": True,
                "website": "",
                "phone": "",
                "address": "",
                "yelp_url": "",
            }
    except:
        pass

    return {
        "found": True,
        "source": "yellowpages",
        "rating": 0,
        "review_count": 0,
        "is_active": True,
        "website": "",
        "phone": "",
        "address": "",
        "yelp_url": "",
    }


# ─── FACEBOOK CHECK ──────────────────────────────────────────────────────────

def check_facebook(business_name, city, state):
    """Search for a business Facebook page."""
    query = f"{business_name} {city} facebook".replace(" ", "+")
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": get_user_agent()}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        fb_pattern = r'https?://(?:www\.)?(?:facebook\.com|fb\.com)/(?:pages/)?[^"\'<>\s]+'
        matches = re.findall(fb_pattern, resp.text)
        if matches:
            fb_url = matches[0].split("?")[0]
            return {"found": True, "url": fb_url, "source": "google_search"}
        return {"found": False, "source": "google_search"}
    except:
        return None


# ─── AI SCORING ──────────────────────────────────────────────────────────────

def score_lead_with_gemini(business_name, category, city, yelp_info, fb_info):
    """Score lead using Gemini, fallback to rule-based."""
    if not GEMINI_API_KEY:
        return rule_based_score(yelp_info, fb_info)

    rating = yelp_info.get('rating', 0) if yelp_info else 0
    reviews = yelp_info.get('review_count', 0) if yelp_info else 0
    active = yelp_info.get('is_active', True) if yelp_info else True

    prompt = f"""Analyze this business lead for a website-building sales pitch:

Business: {business_name}
Category: {category}
Location: {city}
Yelp: rating={rating}/5, reviews={reviews}, active={active}
Facebook: found={fb_info.get('found') if fb_info else False}

Score this lead as hot/warm/cold based on:
- HOT: Active business, good reviews (4+★, 10+ reviews), likely needs/may want website
- WARM: Active but limited online presence (few or no reviews)
- COLD: Can't verify activity or seems inactive

Respond with ONLY JSON:
{{"score": "hot/warm/cold", "reason": "one-sentence explanation", "confidence": 0-1}}"""

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
    except:
        pass

    return rule_based_score(yelp_info, fb_info)


def rule_based_score(yelp_info, fb_info):
    """Rule-based scoring using Yelp + Facebook data."""
    fb_found = fb_info and fb_info.get("found")
    yelp_found = yelp_info and yelp_info.get("found") and yelp_info.get("source") in ("yelp",)

    if not yelp_found:
        if fb_found:
            return {"score": "warm", "reason": "Found on Facebook only", "confidence": 0.4}
        return {"score": "cold", "reason": "Could not verify business online", "confidence": 0.3}

    is_active = yelp_info.get("is_active", True)
    if is_active is False:
        return {"score": "cold", "reason": "Business is marked closed on Yelp", "confidence": 0.9}
    if is_active is None:
        return {"score": "cold", "reason": "Cannot confirm business is active", "confidence": 0.5}

    rating = yelp_info.get("rating", 0)
    reviews = yelp_info.get("review_count", 0)

    # HOT: Well-reviewed active business
    if rating >= 4.0 and reviews >= 5:
        return {"score": "hot", "reason": f"Well-reviewed on Yelp ({rating}/5, {reviews} reviews)", "confidence": 0.85}

    if reviews >= 20:
        return {"score": "hot", "reason": f"Strong Yelp presence ({reviews} reviews)", "confidence": 0.8}

    # WARM: Active with some presence
    if rating >= 3.0 and reviews > 0:
        return {"score": "warm", "reason": f"Active with Yelp presence ({rating}/5, {reviews} reviews)", "confidence": 0.65}

    if rating >= 3.0 or fb_found:
        return {"score": "warm", "reason": "Active business with some online footprint", "confidence": 0.55}

    # WARM: Found on Yelp (business exists)
    return {"score": "warm", "reason": "Verified active business", "confidence": 0.5}


# ─── MAIN ANALYST RUN ────────────────────────────────────────────────────────

def analyst_run(limit=10):
    """Take pending leads and research each via Yelp."""
    init_db()
    conn = get_db()

    leads = conn.execute("""
        SELECT l.* FROM leads l
        LEFT JOIN lead_analyses la ON l.id = la.lead_id
        WHERE la.id IS NULL
        LIMIT ?
    """, (limit,)).fetchall()

    if not leads:
        print("🤖 Analyst Agent — No pending leads to analyze")
        return {"analyzed": 0}

    print(f"🤖 Analyst Agent — Researching {len(leads)} leads via Yelp")
    analyzed = 0

    for row in leads:
        lead = dict(row)
        name = lead.get("business_name", "Unknown")
        city = lead.get("city", "")
        state = lead.get("state", "")
        category = lead.get("category", "")

        print(f"  🔍 {name} ({city}, {state})...", end=" ", flush=True)

        # Research via Yelp
        yelp_info = search_yelp(name, city, state)
        time.sleep(random.uniform(0.3, 0.8))

        # Facebook check
        fb_info = check_facebook(name, city, state)
        time.sleep(random.uniform(0.3, 0.5))

        # Score
        score = score_lead_with_gemini(name, category, city, yelp_info or {}, fb_info or {})

        # Build other_socials JSON
        other_socials = {}
        if yelp_info and yelp_info.get("yelp_url"):
            other_socials["yelp"] = yelp_info["yelp_url"]
        if yelp_info and yelp_info.get("website"):
            other_socials["yelp_page"] = yelp_info["website"]
        if yelp_info and yelp_info.get("categories"):
            other_socials["yelp_categories"] = yelp_info["categories"]
        if yelp_info and yelp_info.get("price"):
            other_socials["price"] = yelp_info["price"]

        rating = yelp_info.get("rating", 0) if yelp_info else 0
        reviews = yelp_info.get("review_count", 0) if yelp_info else 0
        is_active = yelp_info.get("is_active", True) if yelp_info else True

        # Save analysis
        conn.execute("""
            INSERT INTO lead_analyses
            (lead_id, status, google_maps_found, facebook_url, facebook_active,
             review_count, avg_rating, is_active, lead_score, notes,
             other_socials, analyzed_at)
            VALUES (?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            lead["id"],
            1 if yelp_info and yelp_info.get("found") else 0,
            fb_info.get("url", "") if fb_info and fb_info.get("found") else "",
            1 if fb_info and fb_info.get("found") else 0,
            reviews,
            rating,
            1 if is_active else 0,
            score.get("score", "cold"),
            score.get("reason", ""),
            json.dumps(other_socials)
        ))
        conn.commit()
        analyzed += 1

        score_label = score.get("score", "?")
        rating_str = f"{rating}★" if rating else "—"
        print(f"{score_label} ({rating_str}, {reviews} reviews)")

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    update_stat(conn, "leads_analyzed", analyzed)
    conn.close()

    print(f"\n📊 Analyst Report: {analyzed} leads analyzed via Yelp")
    return {"analyzed": analyzed}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyst Agent — Research leads via Yelp")
    parser.add_argument("--limit", type=int, default=10, help="Leads to analyze")
    args = parser.parse_args()
    analyst_run(limit=args.limit)
