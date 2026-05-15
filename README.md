# Pipeline — Multi-Agent Sales Assistant 🤖

**An AI-powered sales pipeline that discovers, analyzes, and pitches to blue-collar businesses without websites.**

Built for the AI Agent Olympics @ Milan AI Week 2026.

---

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  SCOUT      │ →  │  ANALYST    │ →  │  WRITER     │
│  (find      │    │  (score     │    │  (generate  │
│   leads)    │    │   leads)    │    │   pitches)  │
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
    ┌──────────────────────────────────────────┐
    │            SHARED DATABASE                │
    │  Leads → Analysis → Pitches → Tracking   │
    └──────────────────────────────────────────┘
```

### Agents

| Agent | Role | Method |
|-------|------|--------|
| **Scout** | Discovers blue-collar businesses | Yellowpages scraping (cloudscraper) |
| **Analyst** | Scores leads hot/warm/cold | Website email + Facebook signal extraction |
| **Writer** | Generates personalized sales pitches | LLM-powered (Gemini) |

### Pipeline Flow

```
Scout → Find 50 new leads (plumbers, electricians, roofers, etc.)
  ↓
Analyst → Score each lead: has website? email? Facebook? phone?
  ↓
Writer → Generate personalized pitch for hot/warm leads
  ↓
Dashboard → View, filter, manage your pipeline
```

---

## Dashboard

Live mission-control interface at: **https://pipeline.vercel.app**

- **Dashboard** — Pipeline overview with system stats
- **Leads** — Browse/filter 1,000+ leads by city, category, score
- **Pitches** — Generated pitch history with status tracking
- **Controls** — Run agents on demand via command center
- **Analytics** — Score distribution, top cities, daily activity

---

## Stats

- **1,174** leads collected across 26 US cities
- **397** analyzed with multi-signal scoring
- **106** hot leads (no website, active business, reachable)
- **103** AI-generated pitches ready to send

---

## Tech Stack

- **Python** — Agent scripts (scout, analyst, writer)
- **Flask** — API server + admin dashboard
- **SQLite** — Lead database
- **Gemini** — AI scoring + pitch generation
- **Cloudscraper** — Yellowpages data collection
- **Vercel** — Static snapshot hosting

---

## Quick Start

```bash
# Run the full pipeline
python3 orchestrator.py

# Run individual agents
python3 agents/scout.py --max 50
python3 agents/analyst.py --limit 50
python3 agents/writer.py --limit 50

# Start the dashboard
python3 server.py

# Generate Vercel snapshot
python3 scripts/snapshot.py
```

---

*Built solo in 8 days for the AI Agent Olympics @ Milan AI Week 2026*
