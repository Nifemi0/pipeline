# Pipeline — Multi-Agent Sales Assistant

**An autonomous multi-agent system that discovers US blue-collar businesses without a web presence, analyzes their signals, generates personalized sales pitches, and simulates SMS delivery — all on autopilot.**

Built for the **AI Agent Olympics @ Milan AI Week 2026** (May 13–20).  
Build time: **8 days, solo developer.**  
Live demo: https://gem-stamps-watt-whale.trycloudflare.com  
Vercel (read-only): https://sales-agent-sepia.vercel.app  
GitHub: https://github.com/Nifemi0/pipeline

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture](#2-architecture)
3. [Partner Integrations](#3-partner-integrations)
4. [Technology Stack](#4-technology-stack)
5. [Sandbox SMS Delivery — Ethical Design Decision](#5-sandbox-sms-delivery--ethical-design-decision)
6. [Lead Scoring System](#6-lead-scoring-system)
7. [Database Schema](#7-database-schema)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Admin Dashboard](#9-admin-dashboard)
10. [Key Technical Decisions](#10-key-technical-decisions)
11. [Future Roadmap](#11-future-roadmap)
12. [Ethical Safeguards Summary](#12-ethical-safeguards-summary)
13. [Quick Start](#13-quick-start)

---

## 1. Executive Summary

Pipeline is a multi-agent sales assistant that operates on a **discover → score → pitch → deliver → close** pipeline. It scouts blue-collar service businesses (plumbers, electricians, masons, roofers, etc.) from Yelp, analyzes their digital footprint, generates personalized website-building pitches, and displays them in a chat-style SMS inbox for demo purposes.

The system demonstrates a complete end-to-end AI agent workflow with ethical safeguards built in at every stage — most notably, a sandbox SMS mode that proves delivery visually without sending a single real message.

---

## 2. Architecture

### 2.1 System Overview

Pipeline operates as an orchestrated multi-agent system with five stages:

```
┌─────────┐    ┌──────────┐    ┌────────┐    ┌──────────┐    ┌─────────┐
│  SCOUT  │ →  │ ANALYST  │ →  │ WRITER │ →  │ DELIVERY │ →  │  CLOSE  │
│(collect)│    │ (score)  │    │(pitch) │    │ (send)   │    │(follow) │
└─────────┘    └──────────┘    └────────┘    └──────────┘    └─────────┘
                                                    │
                                                    ▼
                                            ┌──────────────┐
                                            │  SMS INBOX   │
                                            │ (sandbox UI) │
                                            └──────────────┘
```

### 2.2 Agent Descriptions

| Agent | Role | Technology | Data Source |
|-------|------|-----------|-------------|
| **SCOUT** | Business discovery | Yelp Fusion API (free tier, 500/day) | Yelp business listings |
| **ANALYST** | Lead scoring & signal extraction | Google Gemini LLM + DuckDuckGo search + DNS/HTTP | Search engines, DNS, HTTP headers |
| **WRITER** | Pitch generation | Google Gemini LLM | Analysis output from Analyst |
| **DELIVERY** | Sandbox SMS simulation | Custom Python sender (DB-driven) | Internal SQLite database |

### 2.3 Data Flow

1. **Scout** collects businesses from Yelp across 26 US cities, filtering for categories like plumbers, electricians, masons, roofers, and painters.
2. **Analyst** scores each lead using a multi-signal analysis pipeline:
   - DuckDuckGo HTML search (1 search per lead, extracts email + Facebook + Google Business Profile)
   - DNS/HTTP website detection (`agents/website_detector.py`)
   - Gemini LLM classification — returns `hot`, `warm`, or `cold` with reasoning
3. **Writer** generates personalized pitches referencing each business's name, category, location, and discovered signals.
4. **Delivery** marks pitches as "sent" in the database and presents them in a chat-style SMS Inbox UI.
5. **Close** (planned) would handle automated follow-ups based on reply detection.

---

## 3. Partner Integrations

### 3.1 Google Gemini Challenge

Pipeline integrates **Google Gemini 2.5 Flash** as the primary LLM for the Writer Agent, generating personalized sales pitches for each business lead. We participated in the **Best Use of Gemini** track ($5K prize).

**Integration Points:**

| Agent | Gemini Role | Model | Temperature |
|-------|------------|-------|-------------|
| **Writer** | Generates personalized cold outreach emails | `gemini-2.5-flash` | 0.7–0.8 |
| **Analyst** | (Planned) Business website content analysis | — | — |

**How It Works:**

1. The Writer receives a lead's business name, category, location, and lead score (hot/warm/cold)
2. It optionally fetches the business website (if available) via HTTP for real-time context
3. A structured prompt is sent to Gemini 2.5 Flash with all context + website analysis
4. Gemini returns a 2–3 sentence personalized pitch — no templates, no fill-in-the-blank
5. If Gemini is unreachable or the API key is missing, the system gracefully falls back to template-based generation

**Prompt Engineering:**

The Writer prompt includes:
- Business details (name, category, city, state, lead quality)
- Website analysis (title, tagline, services, headings — extracted via regex from live HTML)
- Strict rules: max 3 sentences, no pricing mentions, no generic fluff, reference something specific
- Tone constraints: professional, helpful, confident — not pushy

**Sample Output (Gemini-generated):**

> *"Noticed Kys Logistics is operating without a web presence — your customers are searching for freight partners online and landing on competitors. A simple one-page site showing your service areas and fleet would capture that traffic. I'll build you a demo for free within 24 hours — just say yes."*

**Fallback Chain:**
```
Gemini API (primary) → Gemini simplified prompt → Template (guaranteed output)
```

**Setup:**
```bash
# Add your Gemini API key
echo "GEMINI_API_KEY=AIzaSy..." >> .env

# The Writer agent picks it up automatically
python3 agents/writer.py --limit 10
```

The integration is fully open-source in `agents/writer.py` and requires no external services beyond the Gemini API.

### 3.2 Firecrawl Integration

Pipeline uses **Firecrawl** to replace raw HTTP scraping for the Analyst Agent. Instead of making 13 sequential BeautifulSoup requests (homepage + /contact + /about + /contact-us + ...) that get IP-blocked, the Analyst makes **1 Firecrawl API call** per lead.

**What Firecrawl Handles:**

| Function | Before (Raw HTTP) | After (Firecrawl) |
|----------|------------------|-------------------|
| Website scraping | 13 sequential requests, often blocked | 1 API call, proxy rotates automatically |
| Email extraction | Manual regex on raw HTML | Clean markdown + raw HTML with regex |
| Social link detection | BeautifulSoup link traversal | Pre-extracted links array from Firecrawl |
| JS-rendered pages | Missed entirely (no JS execution) | Handles React/Vue/SPA sites |
| Rate limiting | Self-imposed delays (1-3s) | Built-in, no manual delays |

**Architecture:**
The Firecrawl logic lives in `agents/firecrawl_scraper.py` and exposes two main functions:
- `scrape_website(url)` — Single page scrape returning markdown, links, emails, social
- `analyze_lead_website(lead)` — Full lead analysis returning structured signals

**Sample run (1 lead, 1 call):**
```
→ Whitmore Construction (https://whitmoreconstruction.net)
  ✓ Title: "Home - Whitmore Construction"
  ✓ 2 emails found: info@whitmoreconstruction.net, info@withmoreconstruction.net
  ✓ 1 Firecrawl API call — 0.8s total
```

**Fallback Chain:**
```
Firecrawl API (primary) → Static data (lead has phone/address → warm) → cold
```

The `agents/analyst.py` imports Firecrawl at module level and falls back gracefully if the API key is missing or credits are exhausted.

---

## 4. Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web server | **Flask** (Python 3.12) | Serves REST API + admin SPA |
| Database | **SQLite 3** | Lightweight, file-based, zero configuration |
| LLM integration | **Google Gemini API** | Scoring reasoning + pitch generation |
| Web scraping | **Firecrawl API** | Lead website analysis (1 call vs 13 requests) |
| DNS resolution | **Python socket + requests** | Website detection via DNS lookup + HTTP HEAD |
| Task scheduling | **Hermes Agent cron system** | 9 automated batch sessions/day |

### Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Admin panel | **Vanilla HTML/CSS/JS** | Single-page application, no frameworks |
| Design system | **SpaceX-inspired monochrome** | Black (#000) background, spectral white text |
| Routing | **URL hash-based** (`#dashboard`, `#inbox`) | Client-side SPA routing |
| Charts | **CSS bar charts** (zero libraries) | Analytics visualization |
| Mobile | **Responsive CSS** | Hamburger menu, adaptive layouts |

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Host | **Ubuntu 22.04 VM** (Linux 6.8) | Production server |
| Tunnel | **Cloudflared** (trycloudflare.com) | Exposes local Flask to the internet |
| Port | **5050** | Internal Flask binding |
| Process mgmt | **Background shell** | `python3 server.py 5050 &` |

### Key Python Dependencies

```
flask            # Web framework (API + HTML serving)
google-genai     # Gemini LLM API client
requests         # HTTP client for DuckDuckGo + website detection
cloudscraper     # Cloudflare bypass (SportyBet — not used in Pipeline)
sqlite3          # Built-in Python database (stdlib)
socket           # DNS resolution for website detection (stdlib)
```

---

## 5. Sandbox SMS Delivery — Ethical Design Decision

### 4.1 The Problem

Pipeline generates personalized sales pitches for real small businesses. In a production deployment, these would be sent via SMS or email. However, for a hackathon demonstration, there is a critical ethical concern:

> Sending unsolicited sales pitches to real businesses without their consent is **spam**.

This is:
- **Illegal** under the US Telephone Consumer Protection Act (TCPA)
- **Unethical** as a demonstration practice — a hackathon should never spam real people
- **Irreversible** — once a message is sent, it cannot be unsent

### 4.2 Our Solution: Sandbox Mode with Visual Inbox

Instead of sending real SMS messages, Pipeline operates in **sandbox mode**:

1. **No real messages are sent.** The system never connects to an SMS gateway.
2. **"Sending" is a database write.** When a pitch is "sent", the system:
   - Sets `status = 'sent'` in the `pitches` table
   - Records a `sent_at` timestamp
   - Increments the `pitches_sent` counter in `pipeline_stats`
3. **The SMS Inbox UI proves delivery visually.** The sent pitch appears as a chat bubble in the Inbox page — identical UX to a real SMS inbox, zero ethical risk.

### 4.3 Why This Is Better Than Real SMS for a Demo

| Concern | Real SMS | Sandbox Inbox |
|---------|----------|---------------|
| Spam risk | Sends unsolicited messages to real businesses | Zero messages sent |
| TCPA compliance | Requires opt-in consent | N/A — demo mode |
| Demo reliability | 5–30s carrier delay, may fail | Instant, guaranteed |
| Judge experience | Judge never sees the SMS arrive | Full inbox visible on screen |
| Cost | $0.0075+ per message (Twilio) | Free |
| State reset | Cannot unsend | DB rollback in seconds |

### 4.4 Ready for Production

The sandbox system is designed so adding real SMS is a one-function swap:

```python
# Current (agents/sender.py) — sandbox mode:
conn.execute("UPDATE pitches SET status='sent', sent_at=? WHERE id=?", (now, pitch_id))

# Production (future) — adds Twilio without changing anything else:
twilio_client.messages.create(body=pitch_text, to=phone, from_=TWILIO_NUMBER)
conn.execute("UPDATE pitches SET status='sent', sent_at=? WHERE id=?", (now, pitch_id))
```

The entire UI, database schema, and API surface remain identical.

---

## 6. Lead Scoring System

### 5.1 Yelp-Free Signal Extraction

After Yelp's API key was revoked (403 error, May 14 2026), we built a signal extraction pipeline that requires zero paid APIs:

1. **DuckDuckGo HTML search**: One search per lead (`{business_name} {city} {state}`) with realistic User-Agent headers.
2. **Regex-based signal extraction** from search results:
   - Email addresses: `[\w.+-]+@[\w-]+\.[\w.]+`
   - Facebook page URLs: `facebook\.com/[^/\s"']+`
   - Google Business Profile presence detection
3. **DNS + HTTP website detection** (`agents/website_detector.py`):
   - Checks common domain patterns (`{name}.com`, `{name}llc.com`)
   - Uses Python `socket.getaddrinfo()` for DNS resolution
   - Fallback HTTP HEAD request to verify the domain serves a page
4. **Gemini LLM classification**: Analyzes all signals and returns one of `hot`, `warm`, or `cold` with explanatory reasoning.

### 5.2 Scoring Criteria

| Score | Criteria | Action |
|-------|----------|--------|
| **Hot** | 4+ stars, 5+ reviews, active, no website, has phone | High-priority pitch target |
| **Warm** | Has phone, may have email or social media | Secondary target |
| **Cold** | Closed business, no signals found, or already has website | Skip |

### 5.3 Rate Limiting

To be respectful to search engines:
- **3-second delays** between searches
- **Maximum 10 businesses** per 10-minute window
- **Single search** per lead (no retry loops)

---

## 7. Database Schema

### 6.1 Tables

**`leads`** — Business leads discovered by Scout
```
id, business_name, category, city, state, phone, address,
website, source, status, created_at
```

**`lead_analyses`** — Analysis results per lead
```
id, lead_id, lead_score, avg_rating, review_count, is_active,
email_found, email, facebook_url, notes, analyzed_at
```

**`pitches`** — Generated sales pitches
```
id, lead_id, analysis_id, pitch_text, pitch_type,
status (pending/sent/replied/rejected), sent_at, reply_at,
reply_text, created_at
```

**`pipeline_stats`** — Daily aggregate statistics
```
date, leads_scouted, leads_analyzed, pitches_generated,
pitches_sent, replies_received
```

### 6.2 Current State

| Lead Quality | Count |
|--------------|-------|
| Total leads discovered | 1,174 |
| Leads analyzed | 457 |
| Hot leads (high priority) | 106 |
| Warm leads (medium priority) | 269 |
| Cold leads (skipped) | 82 |
| Pitches generated | 167 |
| Pitches sent (sandbox) | 10 |

---

## 8. Deployment Architecture

### 7.1 Runtime

Pipeline runs as a single Python process serving both the REST API and the admin frontend:

```bash
# Start the server
cd /home/ubuntu/sales-agent && python3 server.py 5050 &

# Expose to the internet
cloudflared tunnel --url http://localhost:5050
```

### 7.2 Project Structure

```
/home/ubuntu/sales-agent/
├── server.py                 # Flask app (API + HTML serving, 320+ lines)
├── landing.html              # Public landing page (SPA entry point)
├── admin.html                # Admin dashboard (1,160+ lines, single-file SPA)
├── TECHNICAL_REPORT.md        # This document (standalone)
├── agents/
│   ├── analyst.py            # Lead scoring agent (Gemini + DuckDuckGo)
│   ├── writer.py             # Pitch generation agent (Gemini)
│   ├── sender.py             # Sandbox SMS sender (DB-driven)
│   └── website_detector.py   # DNS/HTTP website detection
├── data/
│   ├── sales_agent.db        # SQLite database (all leads, analyses, pitches)
│   └── schema.py             # DB schema definition
├── scripts/
│   ├── batch-runner.py       # 9 daily cron batches (50 leads each)
│   ├── snapshot.py           # Vercel JSON snapshot generator
│   └── batch_verify_websites.py  # Batch website verification
├── orchestrator.py           # Multi-agent orchestration runner
└── api/
    └── index.py              # Vercel serverless API adapter
```

### 7.3 Cron Schedule

9 automated batch sessions + 1 daily summary run via Hermes Agent cron:

| Time (UTC) | Action |
|------------|--------|
| 06:00 | Batch 1 — 50 leads analyzed + pitched |
| 08:00 | Batch 2 |
| 10:00 | Batch 3 |
| 12:00 | Batch 4 |
| 13:00 | Daily pipeline summary report |
| 14:00 | Batch 5 |
| 16:00 | Batch 6 |
| 18:00 | Batch 7 |
| 20:00 | Batch 8 |
| 22:00 | Batch 9 |

Each batch processes 50 leads with 3-second delays between searches.

---

## 9. Admin Dashboard

### 8.1 Pages

| Page | Route | Features |
|------|-------|----------|
| **Dashboard** | `#dashboard` | Live stats, pipeline flow visualization, agent status table, top hot leads |
| **Leads** | `#leads` | Filterable table (city, category, score, website presence), paginated, clickable rows |
| **Lead Detail** | `#lead/:id` | Full business info, analysis signals, pitch history with inline Send action |
| **Pitches** | `#pitches` | All pitches with status filters, batch select, send selected, send all pending |
| **Inbox** | `#inbox` | Chat-style SMS inbox — sent pitches as chat bubbles, contact list, compose box |
| **Controls** | `#controls` | One-click agent commands (Run Analyst, Writer, Pipeline), output log |
| **Analytics** | `#analytics` | Score distribution bar chart, top cities/categories, daily activity table |
| **Report** | `#report` | This full technical report, rendered as styled HTML |

### 8.2 Design Philosophy

The UI follows a **SpaceX mission control aesthetic**:
- Pure black background (`#000000`)
- Spectral white text (`#f0f0fa`)
- Color reserved for scoring signals only: green (hot), yellow (warm), red (cold), blue (sent)
- Ghost borders (`1px solid rgba(240,240,250,0.25)`)
- Pill buttons (`border-radius: 999px`)
- Rounded cards (`border-radius: 12px`)
- Information-dense, minimal layout
- No emojis, no decorative icons, no gradients

---

## 10. Key Technical Decisions

### 9.1 Why SQLite Instead of PostgreSQL

- **Zero configuration** — no database server to install or maintain
- **File-based** — entire database is a single file; trivial to backup, snapshot, and deploy
- **Sufficient at this scale** — 1,174 leads with sub-millisecond queries
- **Portable** — works identically on a VM, laptop, or cloud server

### 9.2 Why Vanilla JS Instead of React

- **Zero build step** — single HTML file, no webpack/vite/npm
- **Instant reload** — edit file, refresh browser, changes appear
- **Adequate complexity** — the UI has ~8 views with simple CRUD operations
- **Hackathon-appropriate** — no dependency management, no build failures, no npm audit

### 9.3 Why Sandbox Instead of Real SMS

Covered in detail in Section 4. In short: **ethics over features.** A hackathon demo should never spam real businesses.

### 9.4 Why DuckDuckGo Instead of Google/Bing APIs

- **No API key required** — works with plain HTTP requests
- **No billing setup** — free and unlimited (within reason)
- **No rate limit enforcement** — though we self-impose rate limits (3s delays, 10/10min)
- **Downside**: The server IP was eventually blocked by all search engines, which is why the pipeline currently operates on cached data rather than live scouting

### 9.5 Why No Frontend Framework

- Vanilla HTML/CSS/JS keeps the entire admin panel in **one file** (~1,160 lines)
- No npm, no build, no bundler — just `view page source` and edit
- The SPA uses URL hash-based routing (`#leads`, `#inbox`) — zero library needed
- CSS bar charts replace Chart.js entirely

---

## 11. Future Roadmap

| Feature | Status | Target |
|---------|--------|--------|
| Google Places API integration | Blocked (billing not enabled) | Unblocks live lead discovery |
| Real SMS via Twilio | Ready to integrate (one function swap) | Post-demo |
| Email delivery (SendGrid) | Separate channel, same architecture | Post-demo |
| Automated follow-up sequences | Schema ready, logic pending | Post-demo |
| Residential proxy pool | Unblocks search engine scraping | Post-demo |
| Multi-tenant SaaS dashboard | Architecture designed | Long-term |

---

## 12. Ethical Safeguards Summary

| Safeguard | Implementation |
|-----------|---------------|
| **No spam** | Sandbox SMS mode — zero real messages sent |
| **Rate limiting** | 3s delays between searches, max 10/10min |
| **API respect** | Single DuckDuckGo search per lead, no aggressive scraping |
| **Data privacy** | All business data from public Yelp listings, no personal data |
| **Transparency** | Sandbox mode clearly documented; real SMS requires explicit opt-in |

---

## 13. Quick Start

```bash
# Clone the repo
git clone https://github.com/Nifemi0/pipeline.git
cd pipeline

# Set up environment
pip install flask google-genai requests cloudscraper

# Run the full pipeline (analyze 10 leads + generate pitches for them)
python3 orchestrator.py --mode full --analyst-limit 10 --writer-limit 10

# Run individual agents
python3 agents/analyst.py --limit 10
python3 agents/writer.py --limit 10

# Start the dashboard
python3 server.py 5050
# Open http://localhost:5050

# Expose via tunnel (optional)
cloudflared tunnel --url http://localhost:5050

# Generate Vercel snapshot
python3 scripts/snapshot.py
```

---

*Prepared for AI Agent Olympics 2026 — Milan AI Week*  
*May 13–20, 2026 | Built solo in 8 days*  
**Live demo**: https://gem-stamps-watt-whale.trycloudflare.com  
**GitHub**: https://github.com/Nifemi0/pipeline
