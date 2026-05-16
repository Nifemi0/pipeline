#!/usr/bin/env python3
"""
Dump SQLite DB to Vercel-compatible JSON snapshot.
Run this before `vercel --prod` to refresh the static data.
"""
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent.parent
DB_PATH = HERE / "data" / "sales_agent.db"
DATA_OUT = HERE / "api" / "data.json"

def dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}

def dump():
    if not DB_PATH.exists():
        print(f"❌ DB not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = dict_factory

    # Leads
    leads = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    for l in leads:
        for k, v in l.items():
            if isinstance(v, bytes):
                l[k] = v.decode("utf-8", errors="replace")

    # Analyses
    analyses = conn.execute("SELECT * FROM lead_analyses ORDER BY id DESC").fetchall()
    for a in analyses:
        for k, v in a.items():
            if isinstance(v, bytes):
                a[k] = v.decode("utf-8", errors="replace")

    # Pitches
    pitches = conn.execute("SELECT * FROM pitches ORDER BY id DESC").fetchall()
    for p in pitches:
        for k, v in p.items():
            if isinstance(v, bytes):
                p[k] = v.decode("utf-8", errors="replace")

    # Daily stats
    stats = conn.execute("SELECT * FROM pipeline_stats ORDER BY date DESC").fetchall()

    conn.close()

    # Build snapshot
    snapshot = {
        "leads": leads,
        "analyses": analyses,
        "pitches": pitches,
        "stats": stats,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }

    DATA_OUT.write_text(json.dumps(snapshot, indent=2, default=str))
    print(f"✅ Dumped {len(leads)} leads, {len(analyses)} analyses, {len(pitches)} pitches")
    print(f"   → {DATA_OUT} ({DATA_OUT.stat().st_size / 1024:.0f} KB)")

if __name__ == "__main__":
    dump()
