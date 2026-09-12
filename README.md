# webtester

Autonomous **black-box** web testing agent (Phase 1 vertical slice).

Given an authorized URL, `webtester` launches Playwright, observes the page (DOM / interactive elements / console / network), builds a simple behavioural state graph, optionally asks a free-tier LLM to prioritize the next action, executes actions, detects trivial anomalies, and writes evidence + a JSON report.

## Phase 1 features

- Playwright browser controller (domain code never imports Playwright)
- Deterministic observation pipeline + state fingerprints
- BFS and novelty exploration strategies
- Optional Groq / Gemini / OpenRouter prioritization (degrades without keys)
- CLI: `webtester explore <url>`
- File evidence store + JSON run report
- Optional PostgreSQL via Docker Compose

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
playwright install chromium     # optional; falls back to system Chrome/Edge if CDN blocked

copy .env.example .env          # set WEBTESTER_AUTHORIZED=true

# Optional Postgres
docker compose up -d postgres

# Local fixture (injected console-error page)
python benchmarks/fixture_site/server.py
# in another terminal:
webtester explore http://127.0.0.1:8765 --max-actions 8 --strategy novelty --authorize
```

## Safety

Runs require `--authorize` (or `WEBTESTER_AUTHORIZED=true`) and stay within allowed domains derived from the start URL unless overridden.

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [RESEARCH.md](RESEARCH.md)
- [ROADMAP.md](ROADMAP.md)
- [EVALUATION.md](EVALUATION.md)

## Tests

```bash
pytest tests/unit -q
pytest tests/integration -q   # needs Playwright browsers
```
