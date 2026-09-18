# VerifAI — Real-Time Hallucination Audit Trail

> **Verify any AI-generated text in seconds.** VerifAI is a Chrome browser extension that performs a claim-by-claim trust audit on text from ChatGPT, Gemini, Claude, Perplexity, blog posts, or any web page — and delivers verified results with sources, domain detection, confidence scores, and hallucination forensics directly in a sleek side panel.

---

## What it Does

1. **Extracts** atomic factual claims from the text (Claude Sonnet 4).  
2. **Detects the document domain** automatically — healthcare, legal, finance, education, news, or general.  
3. **Searches the web** via a three-provider fallback chain: **Tavily → Serper → Brave**.  
4. **Evaluates** each claim as `VERIFIED` / `UNVERIFIED` / `HALLUCINATED` with a domain-aware confidence model.  
5. **Runs hallucination forensics** on flagged claims — classifying the error type as attribute swap, amalgamation, temporal drift, domain confusion, or pure confabulation.  
6. **Produces a trust score** (0–100) and an exportable **PDF audit certificate**.

---

## Project Layout

```
verifai/
├── backend/                  FastAPI backend (Python)
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── routers/
│   │   └── audit.py          All API endpoints
│   ├── services/
│   │   ├── claim_extractor.py
│   │   ├── domain_detector.py
│   │   ├── web_verifier.py   Tavily → Serper → Brave fallback + disk cache
│   │   ├── verdict_engine.py Domain-aware confidence caps
│   │   ├── genealogy.py      Hallucination forensics
│   │   ├── report_generator.py Trust score + PDF certificate
│   │   ├── pipeline.py       Async orchestration
│   │   └── llm_client.py
│   ├── models/schemas.py
│   ├── db/database.py        SQLite via SQLAlchemy
│   └── data/
│       ├── samples.py        Three preset demo documents
│       └── mock_fixtures.py  Canned verdicts for offline demo
└── extension/                Chrome Extension (Manifest V3)
    ├── manifest.json
    ├── background.js         Service worker, backend bridge, context menu
    ├── content.js            Streaming-safe page capture + highlight painter
    ├── highlight.css         Injected into pages for claim highlighting
    ├── sidebar.html
    ├── sidebar.css           Dark-theme side panel
    ├── sidebar.js            SVG gauge, live feed, claim cards, PDF upload
    └── icons/
```

---

## Quick Start

### 1. Prerequisites

- **Python 3.11+** (3.12 or 3.13 recommended on Windows)
- **Google Chrome** (or any Chromium-based browser)
- API keys (optional — see [Mock Mode](#mock-mode))

### 2. Backend Setup

```powershell
# Clone / open the project folder
cd VerifAi-main

# Create and activate a virtual environment
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Copy the example env file and fill in your API keys
cp .env.example .env
```

Edit `.env` (located at the project root):

```env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
SERPER_API_KEY=...
BRAVE_API_KEY=...
CORS_ORIGINS=*
MOCK_MODE=         # leave blank for live mode; set to 1 for offline demo
```

Start the backend server:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify it's running: open [http://localhost:8000/healthz](http://localhost:8000/healthz) — you should see `{"ok": true}`.

### 3. Load the Chrome Extension

1. Open `chrome://extensions` in Chrome.
2. Enable **Developer mode** (toggle, top-right).
3. Click **Load unpacked** and select the `extension/` folder inside this project.
4. Pin the **VerifAI** icon to your toolbar.

---

## How to Use

### Scan a Webpage
Click the **VerifAI** toolbar icon to open the side panel → click **Scan This Page**.  
On streaming sites (ChatGPT, Gemini, Claude, Perplexity) the content script waits for the response to settle before capturing.

### Verify Selected Text
Select any text on a webpage → right-click → **Verify with VerifAI**.

### Paste & Verify
Sidebar → **Paste & Verify** → paste any text → **Run Audit**.

### Upload a PDF
Drag and drop a `.pdf` file onto the drop zone in the sidebar, or click **browse files** to pick one.  
The backend extracts the text layer, runs the full audit pipeline, and highlights AI-generated claims in the results panel. A PDF audit certificate is then downloadable.

> **Note:** PDFs must contain selectable text (not scanned images). For scanned PDFs, copy the text manually and use Paste & Verify.

### Try the Samples
Three pre-loaded demo documents appear in the sidebar — useful for testing without API keys.

---

## API Reference

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/audit/start` | Start an audit from plain text (returns `audit_id`) |
| `POST` | `/api/audit/upload-pdf` | Start an audit from a PDF file upload |
| `GET`  | `/api/audit/{id}/status` | Poll live stage / progress / partial claims |
| `GET`  | `/api/audit/{id}/results` | Full result when `status = complete` |
| `GET`  | `/api/audit/{id}/report.pdf` | Download PDF audit certificate |
| `GET`  | `/api/audit/samples/list` | List three preset demo documents |
| `GET`  | `/api/audit/samples/{id}` | Fetch a specific sample document |

---

## Mock Mode

No API keys? No problem. Set `MOCK_MODE=1` in `.env` and the backend returns pre-written verdicts for the three sample documents (French Revolution, Aspirin, James Webb Space Telescope). Useful for offline demos or development.

---

## Trust Score Formula

```
raw   = (Σ weight[verdict] × confidence / 100) / claim_count × 100
final = max(0, raw − high_stakes_hallucinations × 10 × domain_penalty)
```

| Verdict | Weight |
|---------|--------|
| VERIFIED | 1.0 |
| UNVERIFIED | 0.4 |
| HALLUCINATED | 0.0 |

**Domain penalty multiplier:** `2.0` for healthcare / legal · `1.5` for finance · `1.0` everywhere else.

**Trust bands:**

| Score | Band |
|-------|------|
| 85–100 | ✅ High Trustworthiness |
| 60–84 | 🟡 Moderate |
| 35–59 | 🟠 Low |
| 0–34 | 🔴 Unreliable |

**Source trust tiers** (used to cap claim confidence):

| Tier | Examples |
|------|---------|
| 1 — High Trust | .gov / .edu / Nature / WHO / CDC / Reuters / AP / BBC / NYT / PubMed |
| 2 — Trusted | Wikipedia / Britannica / WSJ / FT / The Economist / Guardian |
| 3 — Standard | General web |
| 4 — Low Trust | Medium / Substack / Reddit / Quora / LinkedIn |

---

## Architecture

- **LLM:** `claude-sonnet-4-20250514` via the Anthropic Python SDK — used for claim extraction, domain detection, search query generation, verdicts, and genealogy analysis.
- **Search fallback chain:** Tavily → Serper → Brave, attempted in order. Results are cached to disk (`backend/cache/`) keyed on query hash to avoid burning quota on repeated runs.
- **Concurrency:** Claims are verified in parallel behind an `asyncio.Semaphore(5)` to stay within API rate limits.
- **Streaming detection:** `content.js` uses a `MutationObserver` stability counter to wait for the page text to stop changing before capturing on ChatGPT / Perplexity-style sites.
- **PDF extraction:** `pypdf` extracts the text layer from uploaded PDFs server-side; the full audit pipeline then runs normally.
- **Privacy:** Everything runs locally. The extension talks only to `http://localhost:8000`; the only external calls are the LLM and search APIs, all made from your own machine.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Browser Extension | Chrome Manifest V3 (sidePanel + contextMenus + scripting) |
| Backend Framework | FastAPI + Uvicorn |
| Data Validation | Pydantic v2 |
| LLM | Anthropic Python SDK (Claude Sonnet 4) |
| Search APIs | Tavily / Serper / Brave |
| Database | SQLite + SQLAlchemy |
| PDF Generation | WeasyPrint (with ReportLab fallback for Windows) |
| PDF Parsing | pypdf |
| HTTP Client | httpx |

---

## Development Notes

- The backend auto-reloads on file changes when started with `--reload`.
- Search cache lives in `backend/cache/` — delete it to force fresh web searches.
- To reset the audit database, delete `verifai.db` at the project root.
- The extension can be reloaded in `chrome://extensions` → click the refresh icon on the VerifAI card.
