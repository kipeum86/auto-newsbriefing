<div align="center">

# auto-newsbriefing

**RSS → AI → Briefing**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Claude](https://img.shields.io/badge/Claude-d4a574?style=for-the-badge&logo=anthropic&logoColor=white)](https://anthropic.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)

Domain-agnostic RSS newsletter automation.<br>
Collect news via RSS, classify and summarize with AI, archive to Google Sheets, and deliver email briefings — all on autopilot.

[**한국어**](README_KO.md)

```
   RSS Feeds          AI Engine          Output
 ┌──────────┐     ┌──────────────┐     ┌──────────────┐
 │ Tier A   │────▶│  Keyword     │────▶│ Google Sheets│
 │ Tier B   │     │  Filter      │     │   Archive    │
 └──────────┘     │      ▼       │     ├──────────────┤
       │          │  LLM Top-N   │     │  HTML Email  │
       ▼          │  Selection   │     │   Briefing   │
  3-Stage         │      ▼       │     ├──────────────┤
  Dedup           │  Summarize   │     │  trends/     │
  (URL→Token      │  & Classify  │     │   Archive    │
   →EventKey)     │      ▼       │     └──────────────┘
                  │  EventKey    │
                  │  Dedup       │
                  └──────────────┘
```

</div>

---

## Features

- **Multi-LLM support** — Claude, OpenAI, or Gemini (swap with one config change)
- **3-stage deduplication** — URL normalization → topic-token similarity → EventKey fingerprinting
- **Google Sheets archive** — structured data store with automatic header setup
- **HTML email briefings** — category-grouped, styled newsletters via Gmail SMTP
- **GitHub Actions** — scheduled runs with automatic trend file commits
- **Setup wizard** — interactive CLI to configure everything from scratch
- **Fully configurable** — domain, categories, keywords, sources, schedule — all in `config.yaml`

## Quick Start

```bash
git clone https://github.com/kipeum86/auto-newsbriefing.git
cd auto-newsbriefing
pip install -r requirements.txt
cp .env.example .env          # fill in API keys
python -m pipeline.setup.wizard
python main.py --dry-run      # test without Sheets/email
```

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.12+ | Tested with 3.12–3.14 |
| LLM API key | One of: Anthropic, OpenAI, or Google AI |
| Google Cloud service account | For Google Sheets API (free tier sufficient) |
| Gmail + App Password | Optional — only needed for email delivery |
| GitHub repository | Optional — only needed for scheduled automation |

## Setup Guide

### Step 1: Clone & Install

```bash
git clone https://github.com/kipeum86/auto-newsbriefing.git
cd auto-newsbriefing
pip install -r requirements.txt
```

### Step 2: Get API Keys

#### LLM Provider (choose one)

| Provider | Get key at | Env variable |
|----------|-----------|--------------|
| Claude | [console.anthropic.com](https://console.anthropic.com/) | `ANTHROPIC_API_KEY` |
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |
| Gemini | [aistudio.google.com](https://aistudio.google.com/apikey) | `GOOGLE_API_KEY` |

#### Google Sheets Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **Google Sheets API** and **Google Drive API**:
   - Navigate to *APIs & Services → Library*
   - Search for each API and click *Enable*
4. Create a service account:
   - Go to *IAM & Admin → Service Accounts*
   - Click *Create Service Account*
   - Name it (e.g., `newsbriefing-bot`) and click *Done*
5. Create a JSON key:
   - Click the service account → *Keys* tab → *Add Key → Create new key → JSON*
   - Save the downloaded `.json` file securely
6. Note the file path — you'll use it as `GOOGLE_SHEETS_CREDENTIALS` in `.env`

#### Gmail App Password (optional, for email)

1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Select *Mail* and generate a password
4. Copy the 16-character password — use it as `SMTP_PASS` in `.env`

### Step 3: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
# LLM — only the one matching your provider is required
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AI...

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS=/path/to/service-account-key.json

# Email (optional)
SMTP_USER=you@gmail.com
SMTP_PASS=abcd efgh ijkl mnop

# Logging
LOG_LEVEL=INFO
```

### Step 4: Configure Your Briefing

**Option A: Interactive wizard (recommended)**

```bash
python -m pipeline.setup.wizard
```

The wizard walks you through 8 steps: API validation → domain → categories → keywords → RSS sources → Google Sheets → email → save.

**Option B: Copy the example config**

```bash
cp config.example.yaml config.yaml
# Edit config.yaml to match your domain
```

#### Config Sections Explained

| Section | What it controls |
|---------|-----------------|
| `domain` | Name, description, output language |
| `categories` | News classification buckets (name + description for LLM) |
| `keywords` | Include/exclude filters applied before LLM |
| `sources` | RSS feed URLs — `tier_a` (reliable) and `tier_b` (best-effort) |
| `llm` | Provider (`claude`/`openai`/`gemini`), model override, max input chars |
| `email` | Sender name, subject prefix, recipient list |
| `sheets` | `spreadsheet_id` (auto-filled by wizard or Sheets creator) |
| `schedule` | Cron expression and timezone (reference for GitHub Actions) |

### Step 5: Test Run

```bash
# Full dry run (collects RSS, runs LLM, but skips Sheets/email)
python main.py --dry-run

# Quick test without LLM calls
python main.py --dry-run --no-llm

# Limit to 3 articles
python main.py --dry-run --max-items 3
```

If successful, you'll see a `DRY RUN SUMMARY` with categorized and summarized articles.

### Step 6: Deploy to GitHub Actions

#### 6.1 Encode Google Sheets credentials

```bash
# macOS
cat /path/to/service-account-key.json | base64 | pbcopy

# Linux
cat /path/to/service-account-key.json | base64 -w 0
```

#### 6.2 Add GitHub Secrets

Go to your repository → *Settings → Secrets and variables → Actions → New repository secret*:

| Secret name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic key (or `OPENAI_API_KEY` / `GOOGLE_API_KEY`) |
| `GOOGLE_SHEETS_CREDENTIALS_B64` | Base64-encoded service account JSON |
| `SMTP_USER` | Gmail address (optional) |
| `SMTP_PASS` | Gmail App Password (optional) |

#### 6.3 (Optional) Set timezone variable

Go to *Settings → Secrets and variables → Actions → Variables*:

| Variable name | Value |
|---------------|-------|
| `BRIEFING_TZ` | e.g., `Asia/Seoul`, `America/New_York` |

#### 6.4 Customize schedule

Edit `.github/workflows/schedule.yml` — change the cron line:

```yaml
schedule:
  - cron: '7 1 * * 1,3,5'   # 1:07 AM UTC on Mon/Wed/Fri
```

The workflow also supports manual triggering via *Actions → Run workflow*.

## CLI Reference

```
python main.py [OPTIONS]

Options:
  --dry-run          Collect and process, but skip Sheets upload and email
  --no-llm           Skip all LLM calls (useful for testing RSS/dedup only)
  --max-items N      Limit number of articles processed
  --config PATH      Use a custom config file (default: config.yaml)
```

```
python -m pipeline.setup.wizard [OPTIONS]

Options:
  --from-example     Start from config.example.yaml instead of blank
```

## Architecture

```
main.py
 ├─ [1/6] collector.py    → RSS fetch + date filter
 ├─ [2/6] dedup.py        → URL + topic-token + Sheets/trends dedup
 ├─ [3/6] classifier.py   → Keyword filter + LLM Top-N selection
 ├─ [4/6] classifier.py   → Body extraction + LLM summarization
 ├─ [5/6] dedup.py        → EventKey post-summary dedup
 └─ [6/6] archiver.py     → Google Sheets upload
          mailer.py        → HTML email dispatch
          dedup.py         → trends/ local archive
```

```
pipeline/
├── config.py          # Config loading, validation, defaults
├── collector.py       # RSS parsing + body extraction
├── dedup.py           # 3-stage deduplication + trend snapshots
├── classifier.py      # Keyword filter, Top-N, summarization
├── archiver.py        # Google Sheets upload + snapshot
├── mailer.py          # HTML email builder + SMTP
├── models.py          # Data classes (Article, AIResult, etc.)
├── llm/
│   ├── base.py        # Provider interface + prompt builders
│   ├── claude.py      # Anthropic Claude
│   ├── openai.py      # OpenAI GPT
│   └── gemini.py      # Google Gemini
└── setup/
    ├── wizard.py      # Interactive setup CLI
    ├── sheets_creator.py  # Auto-create spreadsheet
    └── validator.py   # API key validation
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'yaml'` | Run `pip install -r requirements.txt` |
| `config.yaml not found` | Run `python -m pipeline.setup.wizard` or `cp config.example.yaml config.yaml` |
| `ANTHROPIC_API_KEY not set` | Add the key to `.env` and restart your terminal |
| `Google Sheets credentials not found` | Check `GOOGLE_SHEETS_CREDENTIALS` path in `.env` is correct (use absolute path) |
| `SMTP connection failed` | Enable 2FA on Google account, generate a new App Password |
| `No articles collected` | Check RSS feed URLs are accessible; try `--no-llm` to isolate |
| GitHub Actions: credentials decode error | Re-encode JSON with `cat file.json \| base64` (no line breaks) |
| `0 articles after keyword filter` | Broaden `keywords.include` in config or set to `[]` to skip filtering |

## 한국어

한국어 문서는 [README_KO.md](README_KO.md)를 참조하세요.

## License

MIT
