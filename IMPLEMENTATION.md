# Cybersecurity Standup Report

**Status:** Complete and tested ✓

## Overview

A scheduled Python application that fetches security news from RSS feeds, analyzes them using Claude LLM (via claude-agent-sdk), and generates intelligence reports in HTML and Markdown formats.

## Architecture

### Core Pipeline
```
Fetch RSS Feeds → Filter & Deduplicate → Analyze with LLM → Render Templates → Output (File/Zulip)
```

### Project Structure
```
cyber-security-report/
├── main.py                          # Async orchestrator
├── config.yaml                      # Configuration (feeds, output settings)
├── .env                             # Secrets (CLAUDE_CODE_OAUTH_TOKEN, ZULIP_*)
├── pyproject.toml                   # Dependencies
├── src/
│   ├── config.py                    # load_config() → AppConfig
│   ├── filters.py                   # apply_filters() - deterministic ignore backstop
│   ├── models.py                    # Pydantic: FeedItem, BriefingItem, IntelReport, AppConfig
│   ├── fetchers/rss.py              # fetch_all_feeds() - concurrent httpx + feedparser
│   ├── intelligence/analyst.py      # analyze() - deterministic pre-processing + LLM query
│   ├── renderers/
│   │   ├── html.py                  # Jinja2 HTML rendering
│   │   └── markdown.py              # Jinja2 Markdown rendering
│   └── outputs/
│       ├── file.py                  # Local file writing
│       └── zulip.py                 # Zulip API posting
└── templates/
    ├── report.html.j2               # HTML template (unfoldingWord brand colors)
    └── report.md.j2                 # Markdown template
└── reports/                         # Output directory (created at runtime)
    └── standup_YYYY-MM-DD.{html,md} # Date-stamped reports
```

## Key Features

### 1. Resilient Feed Fetching
- Concurrent httpx requests to configurable RSS feeds
- A shared browser-like `User-Agent` (plus a `+repo-URL` bot identifier) is sent
  on every request so WAF-protected feeds (e.g. SecurityWeek) don't 403 the
  default `python-httpx` agent; see `DEFAULT_HEADERS` in `fetchers/rss.py`
- Individual feed failures don't crash the pipeline (logged and skipped)
- HTML stripping from feed summaries before LLM (deterministic, saves tokens)

### 2. Hybrid Filtering (deterministic backstop + LLM relevance)

Two layers with different jobs (details in the project `README.md`):

- **`filters.ignore` — deterministic backstop** (`filters.py`): regex/substring
  patterns (case-insensitive) matched on title + summary. Matches are
  **hard-dropped before the LLM sees them** — for products/vendors you never run.
  Compiled once at load; invalid regex fails fast at startup.
- **`environment` — LLM relevance judgment** (`analyst.py` prompt): no keyword
  whitelist. The analyst is given `environment.description` + `stack` (flat list
  or category → assets mapping) and surfaces **only** items relevant to what you
  run, judged by meaning rather than string match.
- **`environment.interests` — watch topics** (optional): a separate "worth
  knowing" axis. Each topic carries an `include`/`exclude` bar; the LLM applies a
  high bar, caps output at 1–2 items per briefing, and prefixes them `[Watch]`.

> The old keyword *include* whitelist was removed — substring matches caused
> false positives and missed items phrased differently (a `glibc`/`sudo` CVE that
> never says "Linux"). Relevance is a semantic judgment, so the LLM does it.

### 3. Token-Efficient LLM Integration
- Deterministic pre-processing before any LLM call:
  - Time window filtering (last 24 hours by default)
  - URL-based deduplication
  - Truncation to `max_items_to_llm` most-recent items (size it above the count
    that survives the lookback + ignore backstop, or relevant items get cut)
- Single LLM call with compact `SOURCE | TITLE | URL\nSUMMARY` format
- JSON output validation with Pydantic

### 4. Template-Driven Rendering
- **HTML**: Full-page styling with unfoldingWord brand colors
  - Ocean `#014263` for headers
  - Inspire `#31ADE3` for section headings
  - Kindle `#E59D33` for action item bullets
  - Tech `#231F20` for body text
- **Markdown**: Clean, Zulip-compatible format

### 5. Flexible Output
- **File output**: Date-stamped HTML and/or Markdown files to `reports/`
- **Zulip integration**: Posts Markdown reports to configured stream/topic (optional; enable via `config.yaml`)
- All output options configurable in `config.yaml`

## Configuration

### config.yaml

*The values below are examples — filters, output format, and Zulip settings are all freely adjustable in `config.yaml`.*

```yaml
feeds:
  news:
    - url: https://hnrss.org/frontpage
      name: Hacker News
      max_items: 20
    - url: https://www.bleepingcomputer.com/feed/
      name: BleepingComputer
      max_items: 20
    - url: https://www.theregister.com/security/headlines.atom
      name: The Register
      max_items: 20

report:
  title: "Cybersecurity Standup Intelligence Report"
  lookback_hours: 24          # Deterministic pre-filter window
  max_items_to_llm: 40        # Cap on items sent to the LLM (size above post-backstop count)

filters:
  ignore:                     # Regex/substring; matches are hard-dropped before the LLM
    - "Microsoft Windows"
    - Cisco
    - "(Fortinet|VMWare)"

environment:                  # LLM judges relevance against this profile (no keyword whitelist)
  description: >
    Our production infrastructure and developer tooling. Surface only security
    news that could affect these systems, the software on them, or their supply
    chain. Drop news about products we do not run.
  stack:                      # Flat list, or a mapping of category -> assets
    External Platforms / SaaS:
      - AWS
      - Cloudflare
      - GitHub
      - npm
    Internal Systems:
      - Docker
      - Linux
      - Nginx
  interests:                  # Optional "worth knowing" watch topics, capped at 1-2/briefing
    - topic: AI / LLM security
      include: >
        Novel attack techniques, actively-exploited vulns in AI tooling, and
        supply-chain poisoning of models or datasets.
      exclude: >
        Product launches, funding, benchmarks, and generic AI commentary.

output:
  format: "both"              # "html", "markdown", or "both"
  file:
    enabled: true
    html_path: "reports/standup_{date}.html"
    markdown_path: "reports/standup_{date}.md"
  zulip:
    enabled: false
    stream: "security"
    topic: "Daily Standup"
```

### .env
```
CLAUDE_CODE_OAUTH_TOKEN=<your-token>

ZULIP_SERVER_URL=https://your-org.zulipchat.com
ZULIP_EMAIL=bot@your-org.zulipchat.com
ZULIP_API_KEY=<your-api-key>
```

## Report Output

### Structure

The report is organized into three main sections:

**Core Situation**
> 3–5 bullet points summarizing the overall threat landscape from the analyzed articles.

**Key Items**
> Structured briefing items, each with:
> - **Severity**: critical, high, medium, or threat
> - **Title**: Short descriptive heading (interest/watch-topic items are prefixed `[Watch]`)
> - **Why Relevant**: One-sentence justification
> - **Action**: Concrete recommended response
> - **Links**: Associated URLs (optional)
> - **CVE**: Identifier if applicable (optional)

**Extra Attention**
> 1–4 items that require immediate focus or follow-up action today.

## Usage

### One-Time Run (Local Python)
```bash
python main.py
```

### Docker
```bash
# Build the image
docker build -t cyber-security-report .

# Run once (mount config and .env, output to host)
docker run --rm \
  --env-file .env \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/reports:/app/reports \
  cyber-security-report
```

### Scheduled (Cron)
```bash
# Add to crontab -e (runs daily at 8 AM, Monday-Friday)
0 8 * * 1-5 cd /home/user/cyber-security-report && /home/user/cyber-security-report/.venv/bin/python main.py >> /tmp/cyber-security-report.log 2>&1
```

**Important:** Use absolute paths in cron. Relative imports work because the cwd is set explicitly.

## Dependencies

All dependencies are declared in `pyproject.toml`:
```
anyio>=4.13.0
claude-agent-sdk==0.2.87
feedparser>=6.0.11
httpx>=0.28.1
jinja2>=3.1.4
pydantic>=2.13.0
pydantic-settings>=2.14.0
python-dotenv>=1.2.0
pyyaml>=6.0.2
```

**Install all dependencies:**

Using `uv` (recommended):
```bash
uv sync
```

Or using `pip`:
```bash
pip install -e .
```

Both read `pyproject.toml` and install all required packages.

## Error Handling

- **Feed failures**: Logged as WARNING, pipeline continues with remaining feeds
- **Config errors**: Fail fast with ValueError if config is invalid or Zulip is enabled but credentials are missing
- **LLM failures**: Raised as AnalystError with raw response for debugging
- **File I/O**: Creates parent directories automatically; logs success/failure

## Testing

All components tested end-to-end:

✓ Feed fetching: all configured feeds fetch (browser UA clears WAF 403s)
✓ Ignore backstop: regex/substring matches hard-dropped before the LLM, count tracked
✓ LLM relevance: only stack-relevant items surfaced; each cites the asset it affects
✓ Interests: AI watch-topic nuggets surface `[Watch]`-tagged and capped, hype excluded
✓ Pre-processing: Time window filtering (24h lookback), deduplication, truncation
✓ LLM analysis: Single query returns valid JSON  
✓ HTML rendering: Proper styling, brand colors, filter stats in metadata  
✓ Markdown rendering: Clean format, Zulip-compatible, filter stats displayed  
✓ File output: Date-stamped files created in reports/  
✓ Error handling: Graceful degradation on feed failures  

## Extensibility

### Add a new output destination (e.g., email, Slack):
1. Create `src/outputs/newservice.py` with async function `post_to_newservice(content, config)`
2. Add config options to `config.yaml`
3. Call from `main.py` in the output phase

### Customize filtering logic:
1. Ignore backstop: edit `filters.ignore` in `config.yaml` (regex supported) — no code change
2. Relevance / interests: edit `environment` in `config.yaml`; to change how the profile
   is rendered into the prompt, edit `_build_environment_note()` in `analyst.py`
3. Add per-feed filters: extend the config schema and `apply_filters()` for feed-specific rules

### Modify the LLM prompt:
1. Edit the prompt template in `src/intelligence/analyst.py`
2. Adjust JSON schema if needed
3. Update `IntelReport` model fields in `src/models.py`

### Add new report sections:
1. Add fields to `IntelReport` model
2. Update LLM prompt and output schema in `analyst.py`
3. Add sections to both templates (`report.html.j2` and `report.md.j2`)

## Performance

- **Feed fetch**: ~1 sec (concurrent via asyncio)
- **LLM analysis**: ~20 sec (single query)
- **Rendering + output**: <100 ms
- **Total**: ~25 sec per run
- **Token cost**: ~2-3k tokens per run (minimal; single LLM call, no summaries in prompt)

## Next Steps (Optional)

1. Customize report sections: Edit templates or modify LLM prompt in analyst.py
2. Add email delivery: Create `src/outputs/email.py` using smtplib or SendGrid
