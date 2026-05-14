#!/usr/bin/env python3
"""Run one analyst batch (50 leads) then generate pitches for them."""
import subprocess, sys
from pathlib import Path

BASE = Path(__file__).parent
batch_num = sys.argv[1] if len(sys.argv) > 1 else "?"
print(f"📦 Batch {batch_num}/9 — 50 leads → analyze + pitch")

# Step 1: Analyze 50 leads via Yelp
r = subprocess.run(
    ["python3", "agents/analyst.py", "--limit", "50"],
    cwd=BASE, capture_output=True, text=True, timeout=300
)
print(r.stdout)
if r.stderr:
    print(f"stderr: {r.stderr[:500]}")

if r.returncode != 0:
    print(f"❌ Batch {batch_num} analysis failed (exit {r.returncode})")
    sys.exit(r.returncode)

# Step 2: Generate pitches for newly analyzed leads
print(f"\n✍️  Generating pitches for batch {batch_num}...")
r2 = subprocess.run(
    ["python3", "agents/writer.py", "--limit", "50"],
    cwd=BASE, capture_output=True, text=True, timeout=300
)
print(r2.stdout)
if r2.stderr:
    print(f"stderr: {r2.stderr[:500]}")

if r2.returncode == 0:
    print(f"✅ Batch {batch_num} complete — analyzed + pitched")
else:
    print(f"⚠️  Batch {batch_num} analyzed OK, but writer had issues")

# Quick stats
import sqlite3
conn = sqlite3.connect(str(BASE / "data" / "sales_agent.db"))
remaining = conn.execute(
    "SELECT COUNT(*) FROM leads l LEFT JOIN lead_analyses la ON l.id = la.lead_id WHERE la.id IS NULL"
).fetchone()[0]
total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
hot = conn.execute("SELECT COUNT(*) FROM lead_analyses WHERE lead_score='hot'").fetchone()[0]
pitches = conn.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
conn.close()

print(f"📊 Progress: {total - remaining}/{total} analyzed | 🔥 {hot} hot | ✍️ {pitches} pitches")
if remaining > 0:
    print(f"⏳ ~{remaining // 450 + 1} days remaining at 450/day")
