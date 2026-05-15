"""
Sales Agent Pipeline — Data Schema
Shared database models for the multi-agent sales assistant.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "sales_agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    category TEXT,
    city TEXT,
    state TEXT,
    address TEXT,
    phone TEXT,
    website TEXT,
    has_website INTEGER DEFAULT 0,
    source TEXT DEFAULT 'yellowpages',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lead_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    -- research fields
    google_maps_found INTEGER DEFAULT 0,
    facebook_url TEXT,
    facebook_active INTEGER DEFAULT 0,
    email_found INTEGER DEFAULT 0,
    email TEXT DEFAULT '',
    review_count INTEGER DEFAULT 0,
    avg_rating REAL DEFAULT 0,
    last_review_date TEXT,
    other_socials TEXT DEFAULT '{}',
    -- quality scoring
    is_active INTEGER DEFAULT 1,
    lead_score TEXT DEFAULT 'warm',  -- hot / warm / cold
    notes TEXT,
    analyzed_at TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

CREATE TABLE IF NOT EXISTS pitches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    analysis_id INTEGER,
    pitch_text TEXT NOT NULL,
    pitch_type TEXT DEFAULT 'initial',  -- initial / followup_1 / followup_2
    status TEXT DEFAULT 'pending',  -- pending / sent / replied / rejected
    sent_at TIMESTAMP,
    reply_at TIMESTAMP,
    reply_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(id),
    FOREIGN KEY (analysis_id) REFERENCES lead_analyses(id)
);

CREATE TABLE IF NOT EXISTS pipeline_stats (
    date TEXT PRIMARY KEY,
    leads_scouted INTEGER DEFAULT 0,
    leads_analyzed INTEGER DEFAULT 0,
    pitches_generated INTEGER DEFAULT 0,
    pitches_sent INTEGER DEFAULT 0,
    replies_received INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lead_status ON lead_analyses(status);
CREATE INDEX IF NOT EXISTS idx_pitch_status ON pitches(status);
CREATE INDEX IF NOT EXISTS idx_lead_category ON leads(category);
"""


def get_db():
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def insert_lead(conn, business_name, category, city, state, address=None,
                phone=None, website=None, has_website=0, source="yellowpages"):
    """Insert a lead, skip if duplicate (same name + city)."""
    existing = conn.execute(
        "SELECT id FROM leads WHERE business_name = ? AND city = ?",
        (business_name, city)
    ).fetchone()
    if existing:
        return existing["id"]
    
    cur = conn.execute(
        """INSERT INTO leads (business_name, category, city, state, address,
           phone, website, has_website, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (business_name, category, city, state, address, phone,
         website, has_website, source)
    )
    return cur.lastrowid


def get_pending_leads(conn, limit=10):
    """Get leads that haven't been analyzed yet."""
    rows = conn.execute(
        """SELECT l.* FROM leads l
           LEFT JOIN lead_analyses la ON l.id = la.lead_id
           WHERE la.id IS NULL
           LIMIT ?""", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_leads_needing_pitches(conn, limit=10):
    """Get analyzed leads that don't have pitches yet."""
    rows = conn.execute(
        """SELECT l.*, la.lead_score, la.facebook_url, la.is_active
           FROM leads l
           JOIN lead_analyses la ON l.id = la.lead_id
           LEFT JOIN pitches p ON l.id = p.lead_id
           WHERE p.id IS NULL AND la.is_active = 1
           LIMIT ?""", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_daily_stats(conn):
    """Get today's pipeline statistics."""
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT * FROM pipeline_stats WHERE date = ?", (today,)
    ).fetchone()
    if row:
        return dict(row)
    return {
        "date": today,
        "leads_scouted": 0,
        "leads_analyzed": 0,
        "pitches_generated": 0,
        "pitches_sent": 0,
        "replies_received": 0
    }


def update_stat(conn, field, increment=1):
    """Increment a daily statistic."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        f"""INSERT INTO pipeline_stats (date, {field})
            VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET {field} = {field} + ?""",
        (today, increment)
    )
    conn.commit()
