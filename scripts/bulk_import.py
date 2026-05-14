#!/usr/bin/env python3
"""
Bulk import all historical lead gen data into the sales-agent database.
Deduplicates by business_name + city.
"""

import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.schema import get_db, init_db, insert_lead

LEADS_DIR = Path(os.path.expanduser("~/.hermes/leads"))

def load_all_leads():
    """Load all leads from JSON files, deduplicated by name+city."""
    seen = set()
    leads = []
    files = sorted(glob.glob(str(LEADS_DIR / "leads_*.json")))
    
    for f in files:
        try:
            data = json.load(open(f))
            for item in data:
                name = (item.get("business_name") or item.get("name") or "").strip()
                city = (item.get("city") or "").strip()
                if not name or not city:
                    continue
                key = f"{name}|{city}"
                if key in seen:
                    continue
                seen.add(key)
                leads.append({
                    "business_name": name,
                    "category": (item.get("category") or item.get("category_name") or "general").strip(),
                    "city": city,
                    "state": (item.get("state") or item.get("region") or "").strip(),
                    "address": (item.get("address") or item.get("street") or "").strip(),
                    "phone": (item.get("phone") or item.get("phone_number") or "").strip(),
                    "website": (item.get("website") or "").strip(),
                    "has_website": 1 if (item.get("website") or item.get("has_website")) and item.get("website") != "None" else 0,
                    "source": item.get("source", "yellowpages"),
                })
        except Exception as e:
            print(f"  ⚠ Error reading {f}: {e}")
    
    return leads

def main():
    print("=" * 60)
    print("BULK IMPORT: Lead Gen Data → Sales Agent DB")
    print("=" * 60)
    
    # Init DB
    init_db()
    conn = get_db()
    
    # Load all leads
    print("\n📂 Loading leads from JSON files...")
    leads = load_all_leads()
    print(f"   Found {len(leads)} unique businesses across all files")
    
    # Count categories
    cats = {}
    for l in leads:
        cats[l["category"]] = cats.get(l["category"], 0) + 1
    
    print(f"\n📊 Categories:")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1])[:15]:
        print(f"   {cat}: {cnt}")
    
    # Insert all leads
    print(f"\n💾 Importing {len(leads)} leads into database...")
    imported = 0
    skipped = 0
    for i, lead in enumerate(leads):
        lid = insert_lead(
            conn,
            lead["business_name"],
            lead["category"],
            lead["city"],
            lead["state"],
            address=lead["address"],
            phone=lead["phone"],
            website=lead["website"],
            has_website=lead["has_website"],
            source=lead["source"],
        )
        if lid:
            imported += 1
        else:
            skipped += 1
        
        if (i+1) % 200 == 0:
            print(f"   ... {i+1}/{len(leads)} processed")
            conn.commit()
    
    conn.commit()
    
    # Final count
    total = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
    with_website = conn.execute("SELECT COUNT(*) as c FROM leads WHERE has_website=1").fetchone()["c"]
    no_website = conn.execute("SELECT COUNT(*) as c FROM leads WHERE has_website=0").fetchone()["c"]
    
    print(f"\n✅ IMPORT COMPLETE")
    print(f"   Imported: {imported}")
    print(f"   Skipped (duplicates): {skipped}")
    print(f"   Total in DB: {total}")
    print(f"   With website: {with_website}")
    print(f"   Without website: {no_website}")
    print(f"   → {no_website} leads ready for analysis!")
    
    conn.close()

if __name__ == "__main__":
    main()
