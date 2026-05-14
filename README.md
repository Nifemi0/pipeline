# Pipeline 🪠

> **AI Agent Olympics 2026 — Milan AI Week**  
> Tracks: Agentic Workflows · Collaborative Systems · Enterprise Utility

An automated multi-agent pipeline that finds US blue-collar businesses without websites, researches them via Yelp, scores lead quality, and generates personalized sales pitches — all running autonomously on a daily cron schedule.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   SCOUT     │ ──▶ │   ANALYST   │ ──▶ │   WRITER    │ ──▶ │ ORCHESTRATOR│
│  (Lead Gen) │     │  (Yelp API) │     │ (Pitch Gen) │     │ (Coordinator)│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  Yellowpages.com      Yelp Fusion          Gemini 2.5        Daily Cron
  24 US cities         Real ★ & reviews     Personalized        Telegram
  7+ trade types       is_closed check      HTML pitches        Dashboard
```

### Agent Breakdown

| Agent | Role | Technology | Output |
|-------|------|-----------|--------|
| **Scout** | Finds leads without websites | Yellowpages scraping | Raw leads (name, phone, city) |
| **Analyst** | Researches each lead | Yelp Fusion API (free) | Rating, reviews, active status |
| **Writer** | Generates sales pitches | Gemini 2.5 Flash | Personalized HTML emails |
| **Orchestrator** | Coordinates pipeline + cron | Python + Telegram | Daily reports to Telegram |

## Features

- **🗺️ 24 US Cities** — New York, LA, Chicago, Houston, Phoenix, Philadelphia, San Antonio, San Diego, Dallas, San Jose, Austin, Jacksonville, Fort Worth, Columbus, Charlotte, Indianapolis, San Francisco, Seattle, Denver, Nashville, El Paso, Washington DC, Boston, Las Vegas
- **🔧 7+ Trade Categories** — Plumbing, Electrical, Roofing, HVAC, Masonry/Concrete, Landscaping, Remodeling
- **⭐ Yelp Fusion Integration** — Real ratings (1-5★), review counts, open/closed status replaces unreliable scraping
- **📊 Live Dashboard** — SaaS-style web UI (charcoal + gold) showing pipeline stats, lead scoring, analysis history
- **📈 1,174 Real Leads** — Proven at scale with real US business data
- **🤖 Fully Automated** — 9 daily cron batches (50 leads each = 450/day) with monitoring
- **💰 100% Free APIs** — Yelp Fusion (500/day, no credit card), Gemini 2.5 Flash (free tier)

## Scoring System

| Score | Criteria | Confidence |
|-------|----------|-----------|
| 🔥 **Hot** | 4+★ with 5+ reviews OR 20+ reviews | 80-85% |
| 👍 **Warm** | Active but limited online presence | 50-65% |
| ❄️ **Cold** | Can't verify activity or appears closed | 30-50% |

## Quick Start

```bash
# Clone
git clone https://github.com/Nifemi0/multi-agent-sales-assistant.git
cd multi-agent-sales-assistant

# Install
pip install -r requirements.txt

# Set up APIs (copy .env.example to .env and fill in)
# - YELP_API_KEY (free at yelp.com/developers)
# - GEMINI_API_KEY (free at aistudio.google.com)

# Run a single batch
python agents/analyst.py --limit 10
python agents/writer.py --limit 10

# Run full pipeline
python orchestrator.py --scout --analyze --write --limit 10

# Launch dashboard
cd web && python app.py
```

## Tech Stack

- **Python** — Core agents and pipeline
- **Yelp Fusion API** — Business research (free, 500 req/day, no credit card)
- **Gemini 2.5 Flash** — AI pitch generation (free tier)
- **Flask** — Web dashboard
- **SQLite** — Lead database
- **Telegram Bot** — Daily reports

## Project Structure

```
multi-agent-sales-assistant/
├── agents/
│   ├── scout.py          # Lead scraping (Yellowpages)
│   ├── analyst.py        # Yelp research + scoring
│   └── writer.py         # Pitch generation
├── web/
│   ├── app.py            # Flask dashboard
│   └── templates/        # SaaS UI (charcoal + gold)
├── data/
│   └── schema.py         # Database schema
├── orchestrator.py       # Pipeline coordinator
├── batch-runner.py       # Cron batch handler
└── requirements.txt
```

## AI Agent Olympics Submission

- **Track:** Agentic Workflows, Collaborative Systems, Enterprise Utility
- **Problem:** US blue-collar businesses (plumbers, electricians, roofers) often lack websites — manual outreach is slow
- **Solution:** 4-agent pipeline that autonomously finds, researches, and pitches — no human needed after setup
- **Scale:** 1,174 real leads across 24 US cities, 95 analyzed with real Yelp data
