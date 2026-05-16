"""
Firecrawl Scraper — Firecrawl-powered web scraping for Apex agents.
Replaces raw requests + BeautifulSoup with Firecrawl's clean API.

Benefits over raw scraping:
- No IP bans (Firecrawl rotates proxies)
- JS-rendered pages work (handles React/Vue sites)
- Clean markdown output (less parsing, fewer tokens)
- Single call per page (no 13-step sequential fetches)
- Built-in rate limiting
"""

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

# ─── CLIENT ───────────────────────────────────────────────────────────────────

_firecrawl_app = None

def get_client():
    """Get or create Firecrawl client singleton."""
    global _firecrawl_app
    if _firecrawl_app is None:
        if not FIRECRAWL_API_KEY:
            return None
        from firecrawl import FirecrawlApp
        _firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    return _firecrawl_app


def check_credits():
    """Check remaining Firecrawl credits."""
    app = get_client()
    if not app:
        return None
    try:
        usage = app.get_credit_usage()
        return usage
    except Exception as e:
        print(f"  ⚠️ Firecrawl credit check failed: {e}")
        return None


# ─── DOMAIN HELPERS ──────────────────────────────────────────────────────────

DIRECTORY_DOMAINS = {
    "yellowpages.com", "superpages.com", "allbiz.com", "bbb.org",
    "yelp.com", "hvacfirms.com", "buildzoom.com", "manta.com",
    "localsearch.com", "merchantcircle.com", "cylex.us.com",
    "hotfrog.com", "citysearch.com", "kudzu.com", "angieslist.com",
    "angi.com", "homeadvisor.com", "porch.com", "thumbtack.com",
    "houzz.com", "linkedin.com", "facebook.com",
}

SKIP_EMAIL_DOMAINS = {
    "google.com", "facebook.com", "example.com", "sentry.io",
    "wixpress.com", "gmail.com", "yahoo.com", "hotmail.com",
    "outlook.com", "aol.com", "mail.com", "protonmail.com",
    "zoho.com", "icloud.com",
}


def is_directory_url(url):
    """Check if a URL points to a directory/aggregator site."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain in DIRECTORY_DOMAINS or any(d in domain for d in DIRECTORY_DOMAINS)
    except:
        return True


def normalize_url(url):
    """Normalize URL — add scheme if missing."""
    url = url.strip().strip('"').strip("'")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


# ─── SIGNAL EXTRACTION ───────────────────────────────────────────────────────

def extract_emails(text):
    """Extract business emails from text."""
    emails = set()
    for match in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        email = match.group().strip().lower()
        domain = email.split("@")[-1]

        # Skip common non-business domains
        if domain in SKIP_EMAIL_DOMAINS:
            continue
        if any(skip in domain for skip in SKIP_EMAIL_DOMAINS):
            continue
        if any(x in email for x in ["sentry", "tracking", "noreply", "no-reply"]):
            continue
        if domain.count(".") < 1:
            continue

        emails.add(email)

    return list(emails)


def extract_social_urls(links):
    """Extract social media URLs from a list of links."""
    social = {"facebook": "", "instagram": "", "twitter": ""}
    for link in links:
        href = link.lower() if isinstance(link, str) else str(link)
        if "facebook.com/" in href and not any(x in href for x in ["/sharer", "/tr", "/plugins"]):
            social["facebook"] = link
        elif "instagram.com/" in href and "/p/" not in href:
            social["instagram"] = link
        elif "twitter.com/" in href or "x.com/" in href:
            if not any(x in href for x in ["/sharer", "/intent", "share"]):
                social["twitter"] = link
    return social


# ─── FIRECRAWL SCRAPE ────────────────────────────────────────────────────────

def scrape_website(website_url, max_pages=3):
    """
    Scrape a business website using Firecrawl.

    Returns:
        dict with: markdown, emails, social_links, title, description,
                   links, has_real_website, error
    """
    result = {
        "success": False,
        "markdown": "",
        "html": "",
        "emails": [],
        "social": {"facebook": "", "instagram": "", "twitter": ""},
        "title": "",
        "description": "",
        "links": [],
        "has_real_website": False,
        "error": "",
    }

    if not website_url:
        return result

    app = get_client()
    if not app:
        result["error"] = "No Firecrawl API key"
        return result

    url = normalize_url(website_url)

    # Skip directory sites
    if is_directory_url(url):
        result["error"] = "Directory site, skipping"
        return result

    try:
        doc = app.scrape(
            url,
            formats=["markdown", "links", "rawHtml"],
            only_main_content=False,
            timeout=15000,
        )

        if not doc or not doc.markdown:
            result["error"] = "Empty response"
            return result

        result["success"] = True
        result["has_real_website"] = True
        result["markdown"] = doc.markdown or ""
        result["html"] = doc.raw_html or ""
        result["title"] = doc.metadata.title if doc.metadata else ""
        result["description"] = doc.metadata.description if doc.metadata else ""

        # Extract links
        if doc.links:
            result["links"] = doc.links

        # Extract emails from markdown
        emails = extract_emails(doc.markdown)
        if doc.raw_html:
            emails.extend(extract_emails(doc.raw_html))
        result["emails"] = list(set(emails))

        # Extract social from links
        if doc.links:
            result["social"] = extract_social_urls(doc.links)

        return result

    except Exception as e:
        result["error"] = str(e)[:120]
        return result


def search_business(business_name, city, state):
    """
    Search the web for a business using Firecrawl web search.
    Returns structured results that can be used to find emails, Facebook, etc.
    """
    app = get_client()
    if not app:
        return {"results": [], "error": "No Firecrawl API key"}

    query = f"{business_name} {city} {state}"

    try:
        results = app.search(query, params={"limit": 5})
        return {"results": results, "error": ""}
    except Exception as e:
        return {"results": [], "error": str(e)[:120]}


# ─── COMPREHENSIVE LEAD ANALYSIS ─────────────────────────────────────────────

def analyze_lead_website(lead):
    """
    Complete website analysis for a lead using Firecrawl.
    Returns structured signals dict compatible with analyst.py.

    This replaces scrape_website_for_signals() which made 13 sequential HTTP requests.
    Now it's 1 Firecrawl call.
    """
    website_url = lead.get("website", "")

    signals = {
        "has_website": bool(website_url),
        "has_phone": bool(lead.get("phone")),
        "has_address": bool(lead.get("address")),
        "has_email": False,
        "email": "",
        "facebook_found": False,
        "facebook_url": "",
        "instagram_url": "",
        "twitter_url": "",
        "gbp_found": False,
        "has_any_online_signal": bool(lead.get("phone")),
        "emails": [],
        "pages_scraped": 0,
        "website_title": "",
        "website_description": "",
    }

    if not website_url:
        return signals, 0

    # Single Firecrawl scrape call
    scrape_result = scrape_website(website_url)

    if not scrape_result["success"]:
        return signals, 0

    signals["has_website"] = True
    signals["has_any_online_signal"] = True
    signals["pages_scraped"] = 1
    signals["website_title"] = scrape_result["title"]
    signals["website_description"] = scrape_result["description"]

    # Emails
    if scrape_result["emails"]:
        signals["has_email"] = True
        biz_emails = [e for e in scrape_result["emails"] if "gmail.com" not in e]
        signals["email"] = (biz_emails or scrape_result["emails"])[0]
        signals["emails"] = scrape_result["emails"]

    # Social
    social = scrape_result["social"]
    if social["facebook"]:
        signals["facebook_found"] = True
        signals["facebook_url"] = social["facebook"]
    if social["instagram"]:
        signals["instagram_url"] = social["instagram"]
    if social["twitter"]:
        signals["twitter_url"] = social["twitter"]

    return signals, 1  # pages_scraped = 1 (one Firecrawl call)

