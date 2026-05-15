#!/usr/bin/env python3
"""
Sandbox SMS Sender — simulates sending pitches via SMS.
Marks pitches as 'sent' in the database. No real SMS sent.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent.parent
DB_PATH = HERE / "data" / "sales_agent.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def send_pitch(pitch_id: int) -> dict:
    """Mark a single pitch as sent (sandbox). Returns result dict."""
    conn = get_conn()
    try:
        pitch = conn.execute(
            "SELECT p.*, l.business_name, l.phone FROM pitches p JOIN leads l ON p.lead_id = l.id WHERE p.id = ?",
            (pitch_id,),
        ).fetchone()

        if not pitch:
            return {"ok": False, "error": "Pitch not found"}

        if pitch["status"] == "sent":
            return {"ok": False, "error": "Pitch already sent"}

        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE pitches SET status = 'sent', sent_at = ? WHERE id = ?",
            (now, pitch_id),
        )

        # Update daily pipeline stats
        today = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            """INSERT INTO pipeline_stats (date, pitches_sent)
               VALUES (?, 1)
               ON CONFLICT(date) DO UPDATE SET pitches_sent = pitches_sent + 1""",
            (today,),
        )
        conn.commit()

        return {
            "ok": True,
            "pitch_id": pitch_id,
            "business": pitch["business_name"],
            "phone": pitch["phone"] or "—",
            "pitch_text": pitch["pitch_text"][:100],
            "sent_at": now,
            "message": f"Sandbox SMS sent to {pitch['business_name']}",
        }
    finally:
        conn.close()


def send_batch(pitch_ids: list) -> dict:
    """Send multiple pitches. Returns summary."""
    results = {"ok": True, "sent": 0, "errors": 0, "details": []}
    for pid in pitch_ids:
        r = send_pitch(pid)
        results["details"].append(r)
        if r.get("ok"):
            results["sent"] += 1
        else:
            results["errors"] += 1
    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Sandbox SMS Sender")
    parser.add_argument("--id", type=int, help="Single pitch ID to send")
    parser.add_argument("--batch", type=str, help="Comma-separated pitch IDs")
    parser.add_argument("--send-pending", type=int, help="Send N pending pitches")
    args = parser.parse_args()

    if args.id:
        r = send_pitch(args.id)
        print(f"{'✅' if r['ok'] else '❌'} {r.get('message', r.get('error', 'Unknown'))}")

    elif args.batch:
        ids = [int(x.strip()) for x in args.batch.split(",")]
        r = send_batch(ids)
        print(f"✅ Sent: {r['sent']}, Errors: {r['errors']}")

    elif args.send_pending:
        conn = get_conn()
        pitches = conn.execute(
            "SELECT id FROM pitches WHERE status = 'pending' LIMIT ?",
            (args.send_pending,),
        ).fetchall()
        conn.close()
        ids = [p["id"] for p in pitches]
        if not ids:
            print("No pending pitches to send.")
            return
        r = send_batch(ids)
        print(f"✅ Sent {r['sent']} pitches, {r['errors']} errors")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
