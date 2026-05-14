#!/usr/bin/env python3
"""
Scout Agent — Agent 1 of the Sales Agent Pipeline
Scrapes Yellowpages for blue-collar businesses without websites.
Outputs leads directly to the shared SQLite database.
"""

import csv
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Add parent to path for schema import
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.schema import get_db, init_db, insert_lead, update_stat

# ─── CONFIG ───────────────────────────────────────────────────────────────────

BLUE_COLLAR_CATEGORIES = [
    "plumber", "electrician", "roofer", "roofing contractor",
    "landscaper", "painter", "hvac contractor", "general contractor",
    "handyman", "carpenter", "masonry contractor", "drywall contractor",
    "flooring contractor", "concrete contractor", "fencing contractor",
    "deck builder", "pool cleaning", "pest control", "tree service",
    "locksmith", "mover", "appliance repair", "auto repair",
    "auto body shop", "tire dealer", "car wash",
]

PRIME_CITIES = [
    ("New York", "NY"), ("Los Angeles", "CA"), ("San Francisco", "CA"),
    ("San Jose", "CA"), ("Miami", "FL"), ("Boston", "MA"),
    ("Washington", "DC"), ("Seattle", "WA"), ("Chicago", "IL"),
    ("Dallas", "TX"), ("Austin", "TX"), ("Denver", "CO"),
    ("Atlanta", "GA"), ("San Diego", "CA"), ("Scottsdale", "AZ"),
    ("Nashville", "TN"), ("Portland", "OR"), ("Charlotte", "NC"),
    ("Brooklyn", "NY"), ("Houston", "TX"), ("Minneapolis", "MN"),
    ("Tampa", "FL"), ("Oakland", "CA"), ("Scottsdale", "AZ"),
]

DIRECTORY_PLACEHOLDERS = [
    "localsearch.com", "merchantcircle.com", "superpages.com",
    "whitepages.com", "citysearch.com", "yellowpages.com",
    "dexknows.com", "bbb.org", "manta.com", "hotfrog.com",
    "chamberofcommerce.com",
]

# Rate limiting
MIN_DELAY = 1.5
MAX_DELAY = 3.0


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_user_agent():
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    return random.choice(agents)


def is_real_website(url):
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower()
    return not any(p in url_lower for p in DIRECTORY_PLACEHOLDERS)


# ─── SCRAPER ──────────────────────────────────────────────────────────────────

def scrape_yellowpages(category, city, state, page=1):
    """Search Yellowpages, return list of business dicts."""
    query = category.replace(" ", "+")
    geo = f"{city.replace(' ', '+')}%2C+{state}"
    url = f"https://www.yellowpages.com/search?search_terms={query}&geo_location_terms={geo}&page={page}"
    
    headers = {
        "User-Agent": get_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  [WARN] HTTP {resp.status_code} for {category} in {city},{state} (page {page})")
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select("div.result")
        if not results:
            return []
        
        businesses = []
        for result in results:
            try:
                name_el = result.select_one("a.business-name")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue
                
                # Website
                website_el = result.select_one("a.track-visit-website")
                website = ""
                if website_el:
                    website = website_el.get("href", "")
                    if website and not website.startswith("http"):
                        website = "https://" + website
                
                # Phone
                phone_el = result.select_one("div.phone")
                phone = phone_el.get_text(strip=True) if phone_el else ""
                
                # Address
                addr_el = result.select_one("div.street-address")
                address = addr_el.get_text(strip=True) if addr_el else ""
                
                businesses.append({
                    "name": name,
                    "phone": phone,
                    "address": address,
                    "website": website,
                    "has_website": is_real_website(website),
                    "category": category,
                    "city": city,
                    "state": state,
                })
            except Exception as e:
                continue
        
        return businesses
    
    except requests.exceptions.Timeout:
        print(f"  [TIMEOUT] {category} in {city},{state}")
        return []
    except Exception as e:
        print(f"  [ERROR] {e}")
        return []


def scout_run(categories=None, cities=None, pages=1, max_leads=None):
    """
    Main scout run — scrape leads and save to database.
    
    Args:
        categories: List of categories (default: all blue collar)
        cities: List of (city, state) tuples
        pages: Number of pages to scrape per category/city
        max_leads: Max leads to collect (None = unlimited)
    """
    categories = categories or BLUE_COLLAR_CATEGORIES
    cities = cities or PRIME_CITIES
    
    print(f"🤖 Scout Agent — Starting hunt")
    print(f"   Categories: {len(categories)}")
    print(f"   Cities: {len(cities)}")
    print(f"   Pages per search: {pages}")
    print()
    
    init_db()
    conn = get_db()
    total_found = 0
    total_no_website = 0
    
    for category in categories:
        for city, state in cities:
            if max_leads and total_found >= max_leads:
                print(f"\n✅ Reached max leads ({max_leads}), stopping.")
                break
            
            no_website = 0
            for page in range(1, pages + 1):
                print(f"  🔍 {category} in {city}, {state} (page {page})...", end=" ", flush=True)
                
                businesses = scrape_yellowpages(category, city, state, page)
                if not businesses:
                    print("0 results")
                    break
                
                print(f"{len(businesses)} found", end="", flush=True)
                
                for biz in businesses:
                    lead_id = insert_lead(
                        conn,
                        business_name=biz["name"],
                        category=biz["category"],
                        city=biz["city"],
                        state=biz["state"],
                        address=biz["address"],
                        phone=biz["phone"],
                        website=biz["website"],
                        has_website=1 if biz["has_website"] else 0,
                        source="yellowpages"
                    )
                    if lead_id:
                        total_found += 1
                        if not biz["has_website"]:
                            no_website += 1
                            total_no_website += 1
                
                conn.commit()
                print(f", {no_website} no-site")
                
                # Rate limiting
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)
            
            if max_leads and total_found >= max_leads:
                break
        if max_leads and total_found >= max_leads:
            break
    
    # Update daily stats
    update_stat(conn, "leads_scouted", total_found)
    conn.close()
    
    print(f"\n📊 Scout Report:")
    print(f"   Total leads found: {total_found}")
    print(f"   No website leads: {total_no_website}")
    print(f"   Hit rate: {total_no_website/max(total_found,1)*100:.0f}%")
    
    return {"total": total_found, "no_website": total_no_website}


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scout Agent — Find leads")
    parser.add_argument("--categories", nargs="+", help="Categories to search")
    parser.add_argument("--cities", nargs="+", help="Cities (format: City,State)")
    parser.add_argument("--pages", type=int, default=1, help="Pages per search")
    parser.add_argument("--max", type=int, help="Max leads")
    args = parser.parse_args()
    
    cats = args.categories or BLUE_COLLAR_CATEGORIES
    cities = []
    if args.cities:
        for c in args.cities:
            parts = c.split(",")
            if len(parts) == 2:
                cities.append((parts[0].strip(), parts[1].strip()))
    cities = cities or PRIME_CITIES
    
    scout_run(categories=cats, cities=cities, pages=args.pages, max_leads=args.max)
