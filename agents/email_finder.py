#!/usr/bin/env python3
"""
Test the website email scraper on existing leads with real websites.
Re-analyzes them and reports what emails/Facebook pages were found.
"""
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.schema import get_db

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})

DIRECTORY_DOMAINS = {
    "yellowpages.com", "superpages.com", "allbiz.com", "bbb.org",
    "yelp.com", "localsearch.com", "rotorooter.com",
}

SKIP_EMAIL_DOMAINS = {
    "google.com", "facebook.com", "example.com", "sentry.io",
    "wixpress.com", "gmail.com", "yahoo.com", "hotmail.com",
    "outlook.com", "aol.com",
}

def is_directory(url):
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain in DIRECTORY_DOMAINS
    except:
        return True

def normalize_url(url):
    url = url.strip().strip('"').strip("'")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url

def fetch_soup(url, timeout=8):
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 500:
            return BeautifulSoup(resp.text, 'html.parser')
    except:
        pass
    return None

def get_emails(soup):
    emails = set()
    text = soup.get_text()
    for match in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        e = match.group().strip().lower()
        domain = e.split("@")[-1]
        if domain in SKIP_EMAIL_DOMAINS or any(d in domain for d in SKIP_EMAIL_DOMAINS):
            continue
        if any(x in e for x in ["sentry", "noreply", "no-reply", "tracking"]):
            continue
        emails.add(e)
    return list(emails)

def get_social(soup):
    social = {"facebook": "", "instagram": "", "twitter": ""}
    for a in soup.find_all("a", href=True):
        h = a["href"].lower()
        if "facebook.com/" in h and "/tr" not in h and "/sharer" not in h:
            social["facebook"] = a["href"]
        elif "instagram.com/" in h and "/p/" not in h:
            social["instagram"] = a["href"]
    return social

def scrape_website(url, max_depth=2):
    """Scrape a business website for emails and social links."""
    result = {"emails": [], "facebook": "", "instagram": "", "pages_scraped": 0}
    url = normalize_url(url)
    if is_directory(url):
        return result
    
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    paths_to_try = ["", "/contact", "/contact-us", "/about", "/about-us"]
    seen = set()
    
    for path in paths_to_try:
        target = urljoin(base, path) if path else url
        if target in seen:
            continue
        seen.add(target)
        
        soup = fetch_soup(target)
        if not soup:
            continue
        
        result["pages_scraped"] += 1
        
        for e in get_emails(soup):
            if e not in result["emails"]:
                result["emails"].append(e)
        
        social = get_social(soup)
        if social["facebook"] and not result["facebook"]:
            result["facebook"] = social["facebook"]
        if social["instagram"] and not result["instagram"]:
            result["instagram"] = social["instagram"]
        
        if result["emails"] and path:
            break
        
        time.sleep(random.uniform(0.3, 0.7))
    
    return result


# ── MAIN ────────────────────────────────────────────────────────────────────

conn = get_db()

# Get analyzed leads with real websites
rows = conn.execute("""
    SELECT l.id, l.business_name, l.city, l.state, l.website,
           la.id as analysis_id, la.email_found, la.email as current_email,
           la.facebook_active, la.facebook_url
    FROM leads l
    JOIN lead_analyses la ON l.id = la.lead_id
    WHERE l.website IS NOT NULL AND l.website != ''
    AND la.email_found = 0
    AND l.website NOT LIKE '%yellowpages%'
    AND l.website NOT LIKE '%localsearch%'
    AND l.website NOT LIKE '%rotorooter%'
    AND l.website NOT LIKE '%bbb.org%'
    AND l.website NOT LIKE '%wixsite%'
    LIMIT 15
""").fetchall()

print(f"Testing {len(rows)} leads with real websites...\n")

found_count = 0
for r in rows:
    name = r["business_name"]
    url = r["website"]
    
    print(f"  {name}: {url}")
    
    data = scrape_website(url)
    
    if data["emails"]:
        biz_only = [e for e in data["emails"] if "gmail.com" not in e and "yahoo.com" not in e]
        primary = (biz_only or data["emails"])[0]
        print(f"    ✅ Email FOUND: {primary}" + (f" (+{len(data['emails'])-1} more)" if len(data['emails']) > 1 else ""))
        found_count += 1
        
        # Update the DB
        other_socials = {}
        if data["facebook"]:
            other_socials["facebook"] = data["facebook"]
        if primary:
            other_socials["email"] = primary
        
        conn.execute("""
            UPDATE lead_analyses 
            SET email_found = 1, email = ?, facebook_url = ?,
                facebook_active = ?, other_socials = ?
            WHERE id = ?
        """, (
            primary,
            data.get("facebook", ""),
            1 if data.get("facebook") else 0,
            json.dumps(other_socials) if other_socials else "",
            r["analysis_id"]
        ))
        conn.commit()
    else:
        print(f"    ❌ No email found ({data['pages_scraped']} pages checked)")
    
    if data["facebook"]:
        print(f"    📘 Facebook: {data['facebook']}")
    
    print(f"    Pages scraped: {data['pages_scraped']}")
    print()
    
    time.sleep(random.uniform(0.5, 1.5))

print(f"\n=== RESULTS: {found_count}/{len(rows)} leads had emails ===")
conn.close()
