#!/usr/bin/env python3
"""
Orchestrator Agent — Multi-Agent Sales Pipeline Coordinator
Runs the full pipeline: Scout → Analyst → Writer
Generates daily Telegram reports.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from data.schema import get_db, init_db, get_daily_stats

from agents.scout import scout_run
from agents.analyst import analyst_run
from agents.writer import writer_run

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_HOME_CHANNEL", "")

PROJECT_DIR = Path(__file__).parent


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(message):
    """Send a message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram not configured — skipping notification")
        print(message)
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        if resp.status_code == 200:
            print("  ✅ Telegram notification sent")
        else:
            print(f"  [WARN] Telegram error: {resp.text[:100]}")
    except Exception as e:
        print(f"  [WARN] Telegram send failed: {e}")


# ─── PIPELINE ─────────────────────────────────────────────────────────────────

def run_pipeline(scout_limit=None, analyst_limit=10, writer_limit=10):
    """
    Run the full sales agent pipeline.
    
    1. Scout → scrape Yellowpages for new leads
    2. Analyst → research each lead
    3. Writer → generate personalized pitches
    4. Report → send Telegram summary
    """
    start = time.time()
    print("=" * 50)
    print("🚀 SALES AGENT PIPELINE — FULL RUN")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print()
    
    # ─── Step 1: Scout ──────────────────────────────────────────────────
    print("─── STEP 1: SCOUT ───")
    scout_result = scout_run(max_leads=scout_limit)
    print()
    
    # ─── Step 2: Analyze ────────────────────────────────────────────────
    print("─── STEP 2: ANALYST ───")
    analyst_result = analyst_run(limit=analyst_limit)
    print()
    
    # ─── Step 3: Write ──────────────────────────────────────────────────
    print("─── STEP 3: WRITER ───")
    writer_result = writer_run(limit=writer_limit)
    print()
    
    # ─── Summary ────────────────────────────────────────────────────────
    elapsed = time.time() - start
    print("─" * 50)
    print(f"⏱️  Pipeline complete in {elapsed:.0f}s")
    print()
    
    # Build report
    conn = get_db()
    stats = get_daily_stats(conn)
    
    total_leads = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
    analyzed = conn.execute("SELECT COUNT(*) as c FROM lead_analyses").fetchone()["c"]
    pitched = conn.execute("SELECT COUNT(*) as c FROM pitches").fetchone()["c"]
    
    hot = conn.execute(
        "SELECT COUNT(*) as c FROM lead_analyses WHERE lead_score = 'hot'"
    ).fetchone()["c"]
    warm = conn.execute(
        "SELECT COUNT(*) as c FROM lead_analyses WHERE lead_score = 'warm'"
    ).fetchone()["c"]
    
    conn.close()
    
    report = (
        f"<b>🤖 Sales Agent — Daily Report</b>\n\n"
        f"<b>Today's Pipeline:</b>\n"
        f"🕵️ Scouted: {stats['leads_scouted']} new leads\n"
        f"🔍 Analyzed: {stats['leads_analyzed']} leads\n"
        f"✍️ Pitches written: {stats['pitches_generated']}\n\n"
        f"<b>All-Time Totals:</b>\n"
        f"📦 Total leads: {total_leads}\n"
        f"🔬 Analyzed: {analyzed}\n"
        f"📝 Pitched: {pitched}\n"
        f"🔥 Hot leads: {hot}\n"
        f"👍 Warm leads: {warm}\n\n"
        f"⏱️ Run time: {elapsed:.0f}s"
    )
    
    print(report)
    send_telegram(report)
    
    return {
        "scout": scout_result,
        "analyst": analyst_result,
        "writer": writer_result,
        "elapsed": elapsed
    }


def quick_scout(limit=30):
    """Quick scout-only run for testing."""
    start = time.time()
    result = scout_run(max_leads=limit)
    elapsed = time.time() - start
    
    msg = (
        f"<b>🕵️ Scout Quick Run</b>\n"
        f"Found: {result['total']} leads\n"
        f"No-website: {result['no_website']}\n"
        f"⏱️ {elapsed:.0f}s"
    )
    print(msg)
    send_telegram(msg)
    return result


def check_inbox():
    """Check for replies (placeholder — real email/Telegram integration later)."""
    conn = get_db()
    
    # Count pending pitches needing follow-up
    pending = conn.execute(
        "SELECT COUNT(*) as c FROM pitches WHERE status = 'sent'"
    ).fetchone()["c"]
    
    old_pending = conn.execute(
        """SELECT COUNT(*) as c FROM pitches
           WHERE status = 'sent' AND sent_at < datetime('now', '-3 days')"""
    ).fetchone()["c"]
    
    conn.close()
    
    if old_pending > 0:
        msg = (
            f"<b>📬 Follow-up Reminder</b>\n"
            f"{old_pending} pitches sent 3+ days ago with no reply.\n"
            f"Time to send follow-ups!"
        )
        print(msg)
        send_telegram(msg)
    
    return {"pending": pending, "needs_followup": old_pending}


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sales Agent Orchestrator")
    parser.add_argument("--mode", choices=["full", "scout", "analyze", "write", "check"],
                        default="full", help="Pipeline mode")
    parser.add_argument("--scout-limit", type=int, help="Max leads for scout")
    parser.add_argument("--analyst-limit", type=int, default=10)
    parser.add_argument("--writer-limit", type=int, default=10)
    args = parser.parse_args()
    
    init_db()
    
    if args.mode == "full":
        run_pipeline(
            scout_limit=args.scout_limit,
            analyst_limit=args.analyst_limit,
            writer_limit=args.writer_limit
        )
    elif args.mode == "scout":
        quick_scout(limit=args.scout_limit or 30)
    elif args.mode == "analyze":
        analyst_run(limit=args.analyst_limit)
    elif args.mode == "write":
        writer_run(limit=args.writer_limit)
    elif args.mode == "check":
        check_inbox()
