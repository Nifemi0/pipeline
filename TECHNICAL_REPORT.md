# Pipeline — Multi-Agent Sales Assistant

## Technical Report for AI Agent Olympics 2026

---

## 1. Executive Summary

**Pipeline** is an autonomous multi-agent sales assistant that discovers US blue-collar businesses without a web presence, analyzes their signals, generates personalized sales pitches, and simulates SMS delivery — all on autopilot.

Built for the AI Agent Olympics (Milan AI Week, May 2026), Pipeline demonstrates a complete end-to-end AI agent workflow: data collection → analysis → content generation → delivery simulation — with ethical safeguards built in at every stage.

**GitHub**: https://github.com/Nifemi0/pipeline  
**Live Demo**: https://gem-stamps-watt-whale.trycloudflare.com  

---

## 2. Architecture

### 2.1 System Overview

Pipeline operates as a **multi-agent orchestration system** with five distinct stages, each handled by a dedicated agent:

```
┌─────────┐    ┌──────────┐    ┌────────┐    ┌──────────┐    ┌─────────┐
│  SCOUT  │ →  │ ANALYST  │ →  │ WRITER │ →  │ DELIVERY │ →  │  CLOSE  │
│(collect)│    │ (score)  │    │(pitch) │    │ (send)   │    │(follow) │
└─────────┘    └──────────┘    └────────┘    └──────────┘    └─────────┘
```

### 2.2 Agent Descriptions

| Agent | Role | Technology | Data Source |
|-------|------|-----------|-------------|
| **SCOUT** | Business discovery | Yelp Fusion API (free tier, 500/day) | Yelp business listings |
| **ANALYST** | Lead scoring & signal extraction | Google Gemini LLM + DuckDuckGo search | Search engines, DNS, HTTP headers |
| **WRITER** | Pitch generation | Google Gemini LLM | Analysis output from Analyst |
| **DELIVERY** | Sandbox SMS simulation | Custom Python sender (DB-driven) | Internal database |

### 2.3 Data Flow

1. **Scout** collects businesses from Yelp (plumbers, electricians, masons, etc.)
2. **Analyst** scores each lead using multi-signal analysis:
   - DuckDuckGo HTML search (email, Facebook, Google Business Profile)
   - DNS/HTTP website detection (`website_detector.py`)
   - Gemini LLM classification (hot/warm/cold)
3. **Writer** generates personalized pitches referencing each business's name, category, location, and discovered signals
4. **Delivery** marks pitches as "sent" in the database and presents them in a chat-style SMS Inbox UI
5. **Close** (planned) would handle follow-ups based on reply detection

---

## 3. Technology Stack

### 3.1 Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web server | **Flask** (Python 3.12) | Serves API + admin UI |
| Database | **SQLite 3** | Lightweight, file-based, zero configuration |
| LLM integration | **Google Gemini API** | Scoring reasoning + pitch generation |
| Search | **DuckDuckGo HTML** (requests) | Lead signal extraction (email, social media) |
| DNS resolution | **Python `socket` + `requests`** | Website detection via DNS lookup + HTTP HEAD |
| Task scheduling | **Hermes Agent cron system** | 9 batch sessions/day for Analyst |

### 3.2 Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Admin panel | **Vanilla HTML/CSS/JS** | Single-page application, no framework |
| Design system | **SpaceX-inspired monochrome** | Black (#000) background, spectral white, ghost borders |
| Routing | **URL hash-based** (`#leads`, `#inbox`) | Client-side SPA routing |
| Charts | **CSS bar charts** (no libraries) | Analytics visualization |
| Mobile | **Responsive CSS** | Hamburger menu, adaptive layouts |

### 3.3 Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Host | **Ubuntu 22.04 VM** (Linux 6.8) | Development + production server |
| Tunnel | **Cloudflared** | Exposes local Flask to internet via `trycloudflare.com` |
| Port | **5050** | Internal Flask binding |
| Process management | **Background shell** | Run via `python3 server.py &` |

### 3.4 Key Dependencies

```
flask            # Web framework
google-genai     # Gemini LLM API client
requests         # HTTP client for DuckDuckGo + website detection
cloudscraper     # Cloudflare bypass (SportyBet — not used in Pipeline)
sqlite3          # Built-in Python database
socket           # DNS resolution for website detection
```

---

## 4. Sandbox SMS Delivery — Ethical Design Decision

### 4.1 The Problem

The Pipeline system generates personalized sales pitches for small businesses. In a real-world deployment, these would be sent via SMS or email to the business owners. However, for a hackathon demonstration, there is a **critical ethical concern**:

> Sending unsolicited sales pitches to real businesses without their consent is **spam**.

Even if the pitches are personalized, even if the businesses "need a website" — sending unsolicited commercial messages to phone numbers is:
- **Illegal** under TCPA (Telephone Consumer Protection Act) in the US
- **Unethical** as a demonstration practice
- **Irreversible** — once sent, you cannot unsend a message

### 4.2 Our Solution: Sandbox Mode with Visual Inbox

Instead of sending real SMS messages, Pipeline operates in **sandbox mode**:

1. **No real messages are sent.** The system never connects to an SMS gateway (Twilio, etc.)
2. **"Sending" means a database write.** When a pitch is "sent", the system:
   - Sets `status = 'sent'` in the `pitches` table
   - Records a `sent_at` timestamp
   - Increments the `pitches_sent` counter in `pipeline_stats`
3. **The SMS Inbox UI proves delivery visually.** The sent pitch appears as a chat bubble in the Inbox page — same experience as a real SMS inbox, zero ethical risk

### 4.3 Why This Is Better Than Real SMS

| Concern | Real SMS | Sandbox Inbox |
|---------|----------|---------------|
| Spam risk | Sends unsolicited messages to real businesses | Zero messages sent |
| TCPA compliance | Requires opt-in consent | N/A — demonstration mode |
| Demo reliability | 5-30 second carrier delay, may fail | Instant, guaranteed |
| Judge experience | Judge never sees the SMS arrive | Full inbox visible on screen |
| Cost | $0.0075+ per SMS (Twilio) | Free |
| State reset | Cannot unsend | Database can be rolled back instantly |

### 4.4 Ready for Production

The sandbox system is designed so that **adding real SMS is a plug-in change**, not an architectural overhaul:

```python
# Current (agents/sender.py):
conn.execute("UPDATE pitches SET status='sent', sent_at=? WHERE id=?", (now, pitch_id))

# Production (future):
twilio_client.messages.create(body=pitch_text, to=phone, from_=TWILIO_NUMBER)
conn.execute("UPDATE pitches SET status='sent', ...")
```

The entire UI, database schema, and API surface remain identical. Only the `send_pitch()` function body changes.

---

## 5. Lead Scoring System

### 5.1 Yelp-Free Signal Extraction

After Yelp's API key was revoked (403 error, May 14 2026), we built a **Yelp-free scoring pipeline**:

1. **DuckDuckGo HTML search**: One search per lead (`{business_name} {city} {state}`)
2. **Signal extraction via regex**:
   - Email addresses (regex: `[\w.+-]+@[\w-]+\.[\w.]+`)
   - Facebook page URLs (regex: `facebook\.com/[^/\s"\']+`)
   - Google Business Profile presence
3. **Website detection via DNS + HTTP** (`agents/website_detector.py`):
   - Checks `{business_name_slug}.com`, `{business_name_slug}llc.com`, etc.
   - Uses DNS resolution (Python `socket`) + HTTP HEAD request
4. **Gemini LLM classification**: Analyzes all signals and returns `hot`, `warm`, or `cold` with reasoning

### 5.2 Scoring Criteria

| Score | Criteria | Action |
|-------|----------|--------|
| **Hot** | 4+ stars, 5+ reviews, active business, no website | High-priority pitch target |
| **Warm** | Has phone, may have email or social media | Secondary target |
| **Cold** | Closed business, no signals, or already has website | Skip |

---

## 6. Database Schema

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

### 6.2 Current State (as of demo)

| Metric | Count |
|--------|-------|
| Total leads | 1,174 |
| Analyzed | 447 |
| Hot leads | 106 |
| Warm leads | 264 |
| Cold leads | 77 |
| Pitches generated | 153 |
| Pitches sent (sandbox) | 5+ |

---

## 7. Deployment Architecture

### 7.1 Runtime

Pipeline runs as a single Python process serving both the API and the admin frontend:

```bash
# Start server (port 5050)
cd /home/ubuntu/sales-agent && python3 server.py 5050 &

# Start tunnel (public URL)
cloudflared tunnel --url http://localhost:5050
```

### 7.2 File Structure

```
/home/ubuntu/sales-agent/
├── server.py                 # Flask app (API + HTML serving)
├── landing.html              # Public landing page
├── admin.html                # Admin dashboard SPA
├── agents/
│   ├── analyst.py            # Lead scoring agent
│   ├── writer.py             # Pitch generation agent
│   ├── sender.py             # Sandbox SMS sender
│   └── website_detector.py   # DNS/HTTP website detection
├── data/
│   ├── sales_agent.db        # SQLite database
│   └── schema.py             # DB schema definition
├── scripts/
│   ├── batch-runner.py       # Cron batch processor
│   ├── snapshot.py           # Vercel JSON snapshot
│   └── batch_verify_websites.py  # Website verification batch
├── orchestrator.py           # Multi-agent orchestration
└── api/
    └── index.py              # Vercel API adapter
```

### 7.3 Cron Automation

Pipeline runs 9 automated batch sessions per day via Hermes Agent cron:

| Time (UTC) | Action |
|------------|--------|
| 06:00 | Batch 1 — 50 leads analyzed + pitched |
| 08:00 | Batch 2 |
| 10:00 | Batch 3 |
| 12:00 | Batch 4 |
| 13:00 | Daily pipeline summary |
| 14:00 | Batch 5 |
| 16:00 | Batch 6 |
| 18:00 | Batch 7 |
| 20:00 | Batch 8 |
| 22:00 | Batch 9 |

Each batch processes 50 leads at a time with **3-second delays** between searches to be polite to search engines.

---

## 8. Admin Dashboard

### 8.1 Pages

| Page | Route | Features |
|------|-------|----------|
| **Dashboard** | `#dashboard` | Live stats (total/hot/warm/cold), pipeline flow, agent status, top hot leads |
| **Leads** | `#leads` | Filterable table (city, category, score, website), pagination, clickable rows |
| **Lead Detail** | `#lead/:id` | Full business info, analysis signals, pitch history with send action |
| **Pitches** | `#pitches` | All pitches with status filters, checkboxes, send selected, send all pending |
| **Inbox** | `#inbox` | Chat-style SMS inbox — sent pitches as chat bubbles, contact list, compose |
| **Controls** | `#controls` | Agent command buttons (Run Analyst, Writer, Pipeline), output log |
| **Analytics** | `#analytics` | Score distribution, top cities/categories bar charts, daily activity |

### 8.2 Design Philosophy

The UI follows a **SpaceX mission control aesthetic**:
- Pure black background (`#000000`)
- Spectral white text (`#f0f0fa`)
- No colors except for scoring signals (green=hot, yellow=warm, red=cold, blue=sent)
- Ghost borders (`1px solid rgba(240,240,250,0.25)`)
- Pill buttons (`border-radius: 999px`)
- Rounded cards (`border-radius: 12px`)
- Minimal, information-dense layout
- No emojis in UI elements

---

## 9. Key Technical Decisions

### 9.1 Why SQLite Instead of PostgreSQL

- **Zero configuration** — no database server to install or maintain
- **File-based** — entire database is a single file, easy to backup, snapshot, and deploy
- **Sufficient for scale** — 1,174 leads with sub-millisecond queries
- **Portable** — works identically on the demo VM, a laptop, or a cloud server

### 9.2 Why Vanilla JS Instead of React

- **Zero build step** — single HTML file, no webpack/vite/npm
- **Instant reload** — edit HTML file, refresh browser, changes appear
- **Adequate complexity** — the UI has ~7 views with simple CRUD operations
- **Hackathon-appropriate** — no dependency management, no build failures

### 9.3 Why Sandbox Instead of Real SMS

Covered in detail in Section 4. In short: **ethics over features**. A hackathon demo should never spam real businesses.

### 9.4 Why DuckDuckGo Instead of Google/Bing APIs

- **No API key required** — works with plain HTTP requests
- **No billing setup** — free, unlimited searches (within reason)
- **No rate limit enforcement** — though we impose our own (3s delays, 10 per 10 min)
- **Downside**: Server IP was eventually blocked by all search engines (DuckDuckGo included), which is why the pipeline currently operates on cached/scored data rather than live scouting

---

## 10. Future Roadmap

| Feature | Status | Target |
|---------|--------|--------|
| Google Places API integration | Blocked (billing not enabled) | Unblocks live lead discovery |
| Real SMS via Twilio | Ready to integrate (one function swap) | Post-demo |
| Email delivery (SendGrid) | Separate channel, same architecture | Post-demo |
| Reply detection & follow-ups | Schema ready, logic pending | Post-demo |
| Residential proxy pool | Unblocks search engine scraping | Post-demo |
| Lead dashboard SaaS | Multi-tenant version planned | Long-term |

---

## 11. Ethical Safeguards Summary

| Safeguard | Implementation |
|-----------|---------------|
| **No spam** | Sandbox SMS mode — no real messages sent |
| **Rate limiting** | 3-second delays between searches, 10 businesses per 10 minutes |
| **API respect** | Single DuckDuckGo search per lead, not aggressive scraping |
| **Data privacy** | All business data from public Yelp listings, no personal data collected |
| **Transparency** | Demo mode clearly documented; real SMS requires explicit opt-in |

---

*Prepared for AI Agent Olympics 2026 — Milan AI Week*  
*May 13–20, 2026*  
*Build time: 8 days (solo developer)*
