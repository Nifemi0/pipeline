#!/usr/bin/env python3
"""
Analyst Agent — Agent 2 of the Sales Agent Pipeline
Multi-signal lead scoring: website email extraction, Facebook presence,
Google Maps, phone, address. Completely search-engine-independent.
"""
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the website detector for Option D — auto-detect websites if not recorded
try:
    from agents.website_detector import detect_website
    _HAS_DETECTOR = True
except ImportError:
    _HAS_DETECTOR = False

from data.schema import get_db, init_db, update_stat

# ─── ENV LOADER ──────────────────────────────────────────────────────────────
def load_dotenv():
    if os.environ.get("GEMINI_API_KEY"):
        return
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

MIN_DELAY = 1.0
MAX_DELAY = 2.5

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_user_agent():
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    return random.choice(agents)

session = requests.Session()
session.headers.update({
    "User-Agent": get_user_agent(),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

DIRECTORY_DOMAINS = {
    "yellowpages.com", "superpages.com", "allbiz.com", "bbb.org",
    "yelp.com", "hvacfirms.com", "buildzoom.com", "manta.com",
    "localsearch.com", "merchantcircle.com", "cylex.us.com",
    "hotfrog.com", "citysearch.com", "kudzu.com", "angieslist.com",
    "angi.com", "homeadvisor.com", "porch.com", "thumbtack.com",
    "houzz.com", "linkedin.com", "facebook.com", "twitter.com",
    "instagram.com", "pinterest.com",
}

SKIP_EMAIL_DOMAINS = {
    "google.com", "facebook.com", "example.com", "domain.com",
    "sentry.io", "wixpress.com", "gmail.com", "yahoo.com",
    "hotmail.com", "outlook.com", "aol.com", "mail.com",
    "protonmail.com", "zoho.com",
}

# ─── WEBSITE EMAIL SCRAPER ───────────────────────────────────────────────────

def is_directory_url(url):
    """Check if a URL points to a directory site (not a real business website)."""
    try:
        domain = urlparse(url).netloc.lower()
        # Remove www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain in DIRECTORY_DOMAINS or any(d in domain for d in DIRECTORY_DOMAINS)
    except:
        return True  # Can't parse = assume directory

def normalize_url(url):
    """Normalize URL — add scheme if missing."""
    url = url.strip().strip('"').strip("'")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url

def fetch_page(url, timeout=10):
    """Fetch a page and return BeautifulSoup object."""
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 500:
            return BeautifulSoup(resp.text, 'html.parser')
    except:
        pass
    return None

def extract_emails_from_soup(soup):
    """Extract real business emails from BeautifulSoup object."""
    emails = set()
    text = soup.get_text()
    
    for match in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        email = match.group().strip().lower()
        domain = email.split("@")[-1]
        
        # Skip common non-business domains
        if domain in SKIP_EMAIL_DOMAINS:
            continue
        if any(skip in domain for skip in SKIP_EMAIL_DOMAINS):
            continue
        
        # Skip sentry/tracking emails
        if any(x in email for x in ["sentry", "tracking", "noreply", "no-reply"]):
            continue
        
        # Must have a proper domain (not just a TLD)
        if domain.count(".") < 1:
            continue
            
        emails.add(email)
    
    return list(emails)

def extract_social_from_soup(soup):
    """Extract social media links from page."""
    social = {"facebook": "", "instagram": "", "twitter": ""}
    
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        
        if "facebook.com/" in href and "/tr" not in href and "/sharer" not in href:
            social["facebook"] = a["href"]
        elif "instagram.com/" in href and "/p/" not in href and "/sharer" not in href:
            social["instagram"] = a["href"]
        elif "twitter.com/" in href or "x.com/" in href:
            clean = a["href"]
            if not any(x in clean for x in ["/sharer", "/intent", "share"]):
                social["twitter"] = a["href"]
    
    return social

def scrape_website_for_signals(website_url, business_name):
    """
    Scrape a business website for email addresses and social media links.
    Tries homepage + /contact + /about pages.
    """
    result = {
        "emails": [],
        "facebook_url": "",
        "instagram_url": "",
        "twitter_url": "",
        "has_real_website": False,
        "pages_scraped": 0,
    }
    
    url = normalize_url(website_url)
    
    # Skip directory sites
    if is_directory_url(url):
        return result
    
    result["has_real_website"] = True
    
    # Build page paths to try
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    paths = ["", "/contact", "/contact-us", "/about", "/about-us", "/about-us/",
             "/contact-us/", "/contacts", "/reach-us", "/get-in-touch",
             "/contact/", "/about/", "/connect", "/support"]
    
    seen_emails = set()
    
    for path in paths:
        target = urljoin(base, path) if path else url
        
        soup = fetch_page(target, timeout=8)
        if not soup:
            continue
        
        result["pages_scraped"] += 1
        
        # Extract emails
        emails = extract_emails_from_soup(soup)
        for e in emails:
            if e not in seen_emails:
                seen_emails.add(e)
                result["emails"].append(e)
        
        # Extract social from homepage
        if path == "" or not result["facebook_url"]:
            social = extract_social_from_soup(soup)
            if social["facebook"] and not result["facebook_url"]:
                result["facebook_url"] = social["facebook"]
            if social["instagram"] and not result["instagram_url"]:
                result["instagram_url"] = social["instagram"]
        
        # If we already have emails and this is deeper, we can stop
        if len(result["emails"]) >= 3 and path:
            break
        
        time.sleep(random.uniform(0.3, 0.8))
    
    return result

# ─── FACEBOOK DIRECT SEARCH (Fallback) ──────────────────────────────────────

def try_facebook_direct_search(business_name, city, state):
    """
    Try to find a Facebook page by constructing a direct search URL.
    This may or may not work depending on Facebook's anti-bot measures.
    """
    try:
        query = f"{business_name} {city} {state}"
        fb_url = "https://www.facebook.com/search/pages/"
        resp = requests.get(
            fb_url,
            params={"q": query},
            headers={"User-Agent": get_user_agent(), "Accept-Language": "en-US,en;q=0.9"},
            timeout=8,
            allow_redirects=True
        )
        
        if resp.status_code == 200 and len(resp.text) > 10000:
            # Look for business page URLs in the response
            page_urls = re.findall(
                r'https://(?:www\.)?facebook\.com/[a-zA-Z0-9.]+(?:/|(?=\s|"|<))(?![^"]*(?:/tr|/sharer|/plugins|/dialog))',
                resp.text
            )
            # Filter out non-page URLs
            real_pages = []
            for u in page_urls:
                path = urlparse(u).path.strip("/")
                if path and not any(x in path for x in ["search", "pages/create", "login", "help"]):
                    real_pages.append(u)
            
            if real_pages:
                return {"found": True, "url": real_pages[0]}
        
        return {"found": False, "url": ""}
    except:
        return {"found": False, "url": ""}

# ─── SIGNAL COLLECTION ───────────────────────────────────────────────────────

def has_website_signal(lead):
    """Check if lead already has a website recorded."""
    return bool(lead.get("website")) or lead.get("has_website") == 1

def collect_signals(lead):
    """
    Collect all available signals for a lead using IP-independent methods.
    No search engine calls — only direct website scraping and existing data.
    """
    business_name = lead.get("business_name", "")
    city = lead.get("city", "")
    state = lead.get("state", "")
    website_url = lead.get("website", "")
    
    signals = {
        "has_website": has_website_signal(lead),
        "has_phone": bool(lead.get("phone")),
        "has_address": bool(lead.get("address")),
        "has_email": False,
        "email": "",
        "facebook_found": False,
        "facebook_url": "",
        "gbp_found": False,
        "has_any_online_signal": False,
    }
    
    # ─── Signal 1: Website scraping for email + social ───
    if website_url:
        site_data = scrape_website_for_signals(website_url, business_name)
        
        if site_data["has_real_website"]:
            signals["has_website"] = True
            signals["has_any_online_signal"] = True
        
        if site_data["emails"]:
            signals["has_email"] = True
            # Pick the most business-like email (not gmail if alternatives exist)
            biz_emails = [e for e in site_data["emails"] if "gmail.com" not in e]
            signals["email"] = (biz_emails or site_data["emails"])[0]
        
        if site_data["facebook_url"]:
            signals["facebook_found"] = True
            signals["facebook_url"] = site_data["facebook_url"]
    
    # ─── Signal 2: Try direct Facebook search (fallback) ───
    if not signals["facebook_found"] and business_name and city:
        fb = try_facebook_direct_search(business_name, city, state)
        signals["facebook_found"] = fb["found"]
        signals["facebook_url"] = fb["url"]
        if fb["found"]:
            signals["has_any_online_signal"] = True
    
    # ─── Signal 3: Any website at all is a positive signal ───
    if signals["has_website"]:
        signals["has_any_online_signal"] = True
    
    return signals, site_data.get("pages_scraped", 0) if website_url else 0


# ─── AI SCORING ──────────────────────────────────────────────────────────────

def score_lead_with_gemini(business_name, category, city, signals):
    """Score lead using Gemini with multi-signal data."""
    if not GEMINI_API_KEY:
        return rule_based_score(signals)

    prompt = f"""Analyze this US blue-collar business lead for a website-building sales pitch.
Score based on: how likely they are to want/need a website and how reachable they are.

BUSINESS: {business_name}
CATEGORY: {category}
LOCATION: {city}

SIGNALS:
- Has website: {signals.get('has_website', 'unknown')}
- Has phone: {signals.get('has_phone', 'unknown')}
- Has email: {signals.get('has_email', False)}
- Email address: {signals.get('email', 'not found')}
- Facebook page: {signals.get('facebook_found', False)}
- Active contact info: {signals.get('has_phone', False) or signals.get('has_email', False)}

SCORING RULES:
- HOT: Active business, NO website, has phone AND (email OR Facebook). Prime target — they exist, they're reachable, they need a site.
- WARM: Active business, NO website, but limited reachability (phone only, or just Facebook). Still worth pursuing.
- COLD: Cannot verify business is active, OR they already have a website, OR appears permanently closed.

Respond with ONLY valid JSON:
{{"score": "hot/warm/cold", "reason": "one-sentence explanation", "confidence": 0.0-1.0}}"""

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

    return rule_based_score(signals)


def rule_based_score(signals):
    """Rule-based scoring using all non-Yelp signals."""
    has_website = signals.get("has_website", False)
    has_phone = signals.get("has_phone", False)
    has_email = signals.get("has_email", False)
    has_fb = signals.get("facebook_found", False)

    # If already has a website — not a target
    if has_website:
        return {"score": "cold", "reason": "Business already has a website", "confidence": 0.9}

    # Count engagement signals
    signals_count = sum([has_phone, has_email, has_fb])

    # HOT: Active, no website, multiple reachability signals
    if signals_count >= 2 and has_phone:
        return {"score": "hot", "reason": f"Active business, no website, {signals_count} contact channels", "confidence": 0.85}

    if signals_count >= 2:
        return {"score": "hot", "reason": f"No website, strong online presence ({signals_count} signals)", "confidence": 0.75}

    # WARM: Some signal but limited reachability
    if has_phone or has_email or has_fb:
        return {"score": "warm", "reason": "Active but limited online presence", "confidence": 0.55}

    # COLD: No signals found
    return {"score": "cold", "reason": "Could not verify business online", "confidence": 0.3}


# ─── MAIN ANALYST RUN ────────────────────────────────────────────────────────

def analyst_run(limit=10):
    """Take pending leads and research each using multi-signal approach."""
    init_db()
    conn = get_db()
    # Keep sqlite3.Row row_factory from get_db()

    # Ensure email columns exist (migration for existing DBs)
    for col in ["email_found", "email"]:
        try:
            conn.execute(f"ALTER TABLE lead_analyses ADD COLUMN {col} TEXT DEFAULT ''")
        except:
            pass
    for col in ["website_emails", "website_pages_scraped"]:
        try:
            conn.execute(f"ALTER TABLE lead_analyses ADD COLUMN {col} TEXT DEFAULT ''")
        except:
            pass
    conn.commit()

    leads = conn.execute("""
        SELECT l.* FROM leads l
        LEFT JOIN lead_analyses la ON l.id = la.lead_id
        WHERE la.id IS NULL
        LIMIT ?
    """, (limit,)).fetchall()

    if not leads:
        print("🤖 Analyst Agent — No pending leads to analyze")
        return {"analyzed": 0}

    print(f"🤖 Analyst Agent — Researching {len(leads)} leads (website scraper + signals)")
    analyzed = 0

    for row in leads:
        lead = dict(row)
        name = lead.get("business_name", "Unknown")
        city = lead.get("city", "")
        state = lead.get("state", "")
        category = lead.get("category", "")
        website = lead.get("website", "")

        # Option D: Auto-detect website if none recorded
        if not website and _HAS_DETECTOR:
            detected_url = detect_website(name, city, delay=0)
            if detected_url:
                website = detected_url
                # Save it back to the DB so future runs don't re-check
                conn.execute("UPDATE leads SET website = ? WHERE id = ?", (website, lead["id"]))
                conn.commit()
                print(f"  🌐 Detected: {website}")

        print(f"  🔍 {name} ({city}, {state})...", end=" ", flush=True)

        # Collect signals — no search engines, only direct website scraping
        signals, pages_scraped = collect_signals(lead)

        # Score with Gemini
        score = score_lead_with_gemini(name, category, city, signals)

        email_addr = signals["email"]
        fb_url = signals["facebook_url"]

        # Build other_socials JSON
        other_socials = {}
        if fb_url:
            other_socials["facebook"] = fb_url
        if email_addr:
            other_socials["email"] = email_addr
        if signals.get("instagram_url"):
            other_socials["instagram"] = signals["instagram_url"]
        if signals.get("twitter_url"):
            other_socials["twitter"] = signals["twitter_url"]

        # Save analysis
        conn.execute("""
            INSERT INTO lead_analyses
            (lead_id, status, google_maps_found, facebook_url, facebook_active,
             email_found, email, review_count, avg_rating, is_active, lead_score, notes,
             other_socials, website_emails, website_pages_scraped, analyzed_at)
            VALUES (?, 'completed', ?, ?, ?,
                    ?, ?, 0, 0, 1, ?, ?,
                    ?, ?, ?, datetime('now'))
        """, (
            lead["id"],
            0,  # google_maps_found — set to 0 since we don't have Maps API
            fb_url,
            1 if signals["facebook_found"] else 0,
            1 if signals["has_email"] else 0,
            email_addr,
            score.get("score", "cold"),
            score.get("reason", ""),
            json.dumps(other_socials),
            json.dumps({"emails_found": signals.get("emails", [])}) if signals.get("emails") else "",
            pages_scraped,
        ))
        conn.commit()
        analyzed += 1

        score_label = score.get("score", "?")
        signals_str = []
        if signals["has_website"]: signals_str.append("site")
        if signals["has_phone"]: signals_str.append("phone")
        if signals["facebook_found"]: signals_str.append("fb")
        if signals["has_email"]:
            signals_str.append(f"📧")
        
        print(f"{score_label} ({', '.join(signals_str) if signals_str else 'no signals'})")

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    update_stat(conn, "leads_analyzed", analyzed)
    conn.close()

    print(f"\n📊 Analyst Report: {analyzed} leads analyzed (search-engine-free)")
    return {"analyzed": analyzed}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyst Agent — Multi-signal lead scoring")
    parser.add_argument("--limit", type=int, default=10, help="Leads to analyze")
    args = parser.parse_args()
    analyst_run(limit=args.limit)
