# ARCHITECTURE.md

**Project:** `webtester` — Autonomous Black-Box Web Testing Agent  
**Phase:** 0 — Research & Architecture  
**Related:** [RESEARCH.md](RESEARCH.md) · [ROADMAP.md](ROADMAP.md) · [EVALUATION.md](EVALUATION.md)

This document locks system architecture for implementation. It prefers explicit modular Python components with **sparse LLM use**, not a swarm of LLM “agents”.

---

## 1. Goals and Non-Goals

### Goals

- Explore authorized websites through a real browser.
- Observe multimodal browser-level information (HTML/DOM, a11y, screenshots, network, console, behaviour).
- Maintain an evolving behavioural model (states, actions, transitions, workflows).
- Generate tests, detect anomalies, reproduce bugs, emit structured evidence-backed reports.
- Run on **free LLM APIs** during this development phase.
- Remain maintainable at large scale (tens of thousands of lines).

### Non-Goals (this phase of the product)

- Frontend/UI.
- Inspecting target source repositories or server internals.
- Vision-only black-box interpretation.
- Required paid LLM providers.
- Unrestricted attacks on arbitrary sites.
- Copying TRACER or wrapping browser-use/Skyvern as the core runtime.

---

## 2. High-Level Architecture

```text
Authorized Target Website
        │
        ▼
┌───────────────────┐
│ BrowserController │  Playwright adapter (replaceable)
└─────────┬─────────┘
          │ RawObservation
          ▼
┌───────────────────┐
│ Observation Pipeline │  deterministic first
└─────────┬─────────┘
          │ CompactState + candidates
          ▼
┌───────────────────┐
│ Behavioural Model │  state graph / workflows
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Exploration Engine │  strategies + budget
└─────────┬─────────┘
          │ Action
          ▼
     (loop back to browser)
          │
          ▼
┌───────────────────┐
│ Anomaly / Oracle  │  multi-signal
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Bug Investigator  │  reproduce + evidence
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Reporter / API/CLI │
└───────────────────┘

Cross-cutting: LLMProvider (sparse), Persistence (Postgres + files), Config/Safety
```

### Design principles

1. **Dependency inversion** for browser, LLM, and persistence ports.
2. **Deterministic before probabilistic** — parse, hash, compare, then optionally ask an LLM.
3. **Anomaly ≠ bug** — verification gate required.
4. **Budget-aware** — every run has action, time, and LLM budgets.
5. **Evidence-first** — raw artifacts retained separately from LLM context.
6. **No over-abstraction before the Phase 1 vertical slice works.**

---

## 3. Layer Boundaries

| Package | Responsibility | May depend on | Must not depend on |
| --- | --- | --- | --- |
| `webtester.domain` | Entities, value objects, ports (protocols) | stdlib, pydantic | Playwright, SQLAlchemy, FastAPI, provider SDKs |
| `webtester.browser` | BrowserController port + Playwright adapter | domain | FastAPI, LLM providers |
| `webtester.observation` | DOM simplify, fingerprints, LLM context builders | domain | Playwright (except via browser DTOs) |
| `webtester.model` | Behavioural state graph services | domain | Playwright, FastAPI |
| `webtester.exploration` | Loop + strategies | domain, model, observation ports | Playwright, provider SDKs directly |
| `webtester.llm` | Provider adapters, cache, metrics | domain | Playwright, FastAPI |
| `webtester.testing` | Test generation & execution (Phase 3+) | domain, browser port | — |
| `webtester.oracle` | Oracles & metamorphic relations (Phase 3–4) | domain | — |
| `webtester.bugs` | Investigation & reporting (Phase 4) | domain | — |
| `webtester.persistence` | SQLAlchemy repos, file store | domain | Playwright, FastAPI |
| `webtester.api` | FastAPI thin adapters | application services | domain internals leaking |
| `webtester.cli` | Typer CLI | application services | — |
| `webtester.config` | Settings, scope policies | pydantic-settings | — |

---

## 4. Repository Structure (to create in Phase 1)

```text
LLM_webscraper/
├── ARCHITECTURE.md
├── RESEARCH.md
├── ROADMAP.md
├── EVALUATION.md
├── README.md                 # Phase 1
├── pyproject.toml
├── docker-compose.yml        # Postgres (+ optional MinIO later)
├── .env.example
├── src/webtester/
│   ├── domain/
│   ├── browser/
│   │   ├── ports.py
│   │   └── playwright_adapter.py
│   ├── observation/
│   ├── model/
│   ├── exploration/
│   │   ├── engine.py
│   │   └── strategies/
│   ├── llm/
│   │   ├── ports.py
│   │   ├── cache.py
│   │   ├── metrics.py
│   │   └── providers/
│   ├── testing/
│   ├── oracle/
│   ├── bugs/
│   ├── persistence/
│   ├── api/
│   ├── cli/
│   └── config/
├── benchmarks/               # controlled apps (Phase 6; stubs earlier)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── data/                     # local evidence (gitignored)
    ├── screenshots/
    ├── html/
    └── traces/
```

---

## 5. Core Domain Models

### 5.1 Projects and safety

```text
Project
  id, name, created_at

Target
  id, project_id, base_url, name

ScopePolicy
  allowed_domains: list[str]
  blocked_domains: list[str]
  max_actions: int
  max_runtime_seconds: int
  max_llm_calls: int
  max_depth: int | null
  allow_downloads: bool
  allow_file_upload: bool
  dangerous_action_deny_list: list[ActionType]
  require_explicit_authorization: bool  # must be true to run
```

### 5.2 Runs and budget

```text
ExplorationRun
  id, project_id, target_id, status, strategy, started_at, finished_at, config_snapshot

Budget
  actions_remaining, runtime_deadline, llm_calls_remaining, tokens_remaining_estimate

BrowserSession
  id, run_id, browser_engine, started_at, ended_at
```

### 5.3 Observation

```text
Observation
  id, session_id, url, title, timestamp
  raw_html_ref          # file pointer, not always in DB blob
  simplified_dom
  accessibility_tree_summary
  visible_text
  interactive_elements: list[InteractiveElement]
  forms: list[Form]
  screenshot_ref
  console_events: list[ConsoleEvent]
  network_events: list[NetworkEvent]
  navigation_events: list[NavigationEvent]
  timing: PageTiming
  previous_action_id: ActionId | null
  state_fingerprint: StateFingerprint

InteractiveElement
  element_id            # stable within observation
  role, tag, name, text
  attributes            # subset: type, href, aria-*, disabled, etc.
  selector_candidates   # css/xpath/role-based for reproducibility
  bbox | null
  is_visible, is_enabled

NetworkEvent
  url, method, status, resource_type, timing_ms, from_browser

ConsoleEvent
  level, text, location, timestamp
```

### 5.4 Behavioural model

```text
StateNode
  id, run_id, fingerprint, label, first_seen_at, visit_count
  summary                 # optional LLM-generated, cached

StateFingerprint
  normalized_url
  simplified_dom_hash
  interactive_signature_hash
  form_values_hash
  # Phase 2+: fragment_hashes, storage_hash, screenshot_features

Transition
  id, from_state_id, to_state_id, action_id, observed_at

Action
  id, type: ActionType
  target_ref              # selector / element identity recipe
  parameters              # text, keys, etc.
  source_state_id
  result_state_id | null
  timestamp
  execution_result        # ok | failed | timeout
  error | null

ActionType
  click, type, fill, select, check, uncheck, submit,
  navigate, back, forward, refresh, scroll, hover,
  keyboard, wait, upload, open_dialog

Workflow
  id, name, state_sequence, action_sequence, confidence
```

**State identity rule:** URL alone is insufficient. Same URL may encode different carts/sessions; different URLs may be equivalent. Similarity = exact fingerprint match first; soft similarity later (Phase 2).

### 5.5 Testing and bugs

```text
TestCase
  id, project_id, category, preconditions, steps: list[Action], expected_oracles

TestExecution
  id, test_case_id, run_id, status, oracle_results, started_at, finished_at

OracleResult
  oracle_type, passed, evidence_refs, detail

Anomaly
  id, run_id, signals, severity_estimate, related_state_id, related_action_id

BugHypothesis
  id, anomaly_id, statement, expected_behaviour, confidence_prior

BugReport
  id, title, category, severity, confidence
  status: observed | suspected | reproduced | verified
  target_url, affected_state_id
  preconditions, reproduction_steps
  expected_behaviour, actual_behaviour
  evidence_refs, related_workflow_id, related_test_id
  reproduction_count, created_at, updated_at

EvidenceArtifact
  id, kind, path, content_type, metadata

LLMCallRecord
  id, run_id, provider, model, purpose
  input_tokens, output_tokens, latency_ms
  cache_hit, status, error, estimated_cost
```

---

## 6. Browser Layer

### Port

```text
BrowserController
  start(session_config) -> BrowserSession
  navigate(url)
  observe() -> RawObservation
  execute(action: Action) -> ActionResult
  screenshot() -> bytes
  stop()
```

Supporting collectors (implementation details of the Playwright adapter):

- `PageObserver`, `DOMObserver`, `AccessibilityObserver`
- `NetworkObserver`, `ConsoleObserver`, `ScreenshotCollector`
- `ActionExecutor`

### Decision

- **Playwright** is the default adapter.
- Domain/exploration code talks only to `BrowserController`.
- Alternative adapters (e.g. future CDP-only) can be added without rewriting the loop.

### Why not browser-use as core?

Task-completion agent loops, LLM-every-step economics, and product coupling conflict with deterministic-first behavioural modeling. See [RESEARCH.md](RESEARCH.md).

---

## 7. Observation Pipeline

```text
RawObservation
  → DOM parse
  → visibility filter
  → interactive element extraction
  → semantic simplification (strip scripts, ads, noise; keep structure/labels/ARIA)
  → state fingerprint
  → compact LLM context (only if LLM step requested)
```

**Rules:**

- Never send full raw HTML to the LLM by default.
- Preserve raw HTML/screenshots/traces in the evidence store when needed for bugs.
- Phase 1 fingerprint: `normalized_url + simplified_dom_hash + interactive_signature + form_values_hash`.
- Accessibility tree included in simplification inputs when available.
- Network/console events attached to observations for anomaly signals.

---

## 8. Exploration Engine

### Loop

```text
OBSERVE
 → UNDERSTAND (deterministic summary; optional LLM)
 → UPDATE MODEL
 → GENERATE CANDIDATE ACTIONS (deterministic from interactive elements)
 → PRIORITIZE (strategy; optional LLM re-rank if budget)
 → EXECUTE
 → OBSERVE
 → ANALYZE (diff states, console, network)
 → DETECT ANOMALY
 → UPDATE MODEL
 → CONTINUE until budget exhausted or stop condition
```

### Strategies (plugin interface)

| Strategy | Phase |
| --- | --- |
| BFS | Phase 1 |
| Novelty-driven | Phase 1 |
| DFS | Phase 2 |
| Random | Phase 2 (baseline) |
| Goal-oriented | Phase 2–3 |
| Risk-driven | Phase 4 |
| LLM-guided | Phase 1 optional / Phase 2 |
| Information-gain | Phase 2+ |

```text
ExplorationStrategy.propose(model, observation, budget) -> list[ScoredAction]
```

### Action reproducibility

Every executed action stores type, target identity recipe, parameters, source/result states, timestamp, and result. Target identity prefers role+name+selector candidates over brittle absolute XPath alone.

---

## 9. LLM Architecture

### Port

```text
LLMProvider
  complete(request: LLMRequest) -> LLMResponse
  # supports: structured output schema, timeout, abort

LLMRequest
  purpose, messages, response_schema | null, max_tokens, temperature
  cache_key_parts, multimodal_refs | null
```

### Providers

```text
LLMProvider
├── GroqProvider                 # primary volume
├── GeminiProvider               # Flash-Lite secondary reasoning
├── OpenAICompatibleProvider     # OpenRouter :free, local gateways
└── LocalModelProvider           # Ollama/vLLM
```

### Router policy

1. If task is solvable deterministically → no LLM.
2. Cheap structured tasks → Groq small model.
3. Harder semantic / multimodal tasks → Gemini Flash-Lite.
4. On 429 / outage → failover chain + exponential backoff.
5. Always consult cache first.
6. Persist `LLMCallRecord` for every attempt (including failures/cache hits).

### Where LLMs are used

| Use | Phase |
| --- | --- |
| Action prioritization (optional) | 1 |
| Page/workflow semantic summary | 2 |
| Test hypothesis generation | 3 |
| Anomaly interpretation | 4 |
| Bug classification / expected behaviour inference | 4 |
| Exploration planning | 2+ |

### Where LLMs are not used

DOM parsing, element extraction, hashing, duplicate detection, browser action execution, logging, persistence, retries, evidence I/O.

---

## 10. Behavioural Model Service

Responsibilities:

- Insert/find `StateNode` by fingerprint.
- Record `Transition` and `Action`.
- Track visit counts and unexplored outgoing actions.
- Extract candidate workflows (Phase 2).
- Export graph snapshots for inspection/API.

Storage: PostgreSQL tables for nodes/edges; optional Graphviz/JSON export for humans (TRACER-like visualization without making Graphviz the source of truth).

---

## 11. Testing, Oracles, Bugs

### Test categories (Phase 3+)

Functional, boundary, invalid input, state transition, robustness, consistency.

### Oracle types

1. Deterministic rules (console errors, HTTP 5xx, broken nav).
2. Invariants learned/configured.
3. State comparison.
4. Workflow expectations.
5. Cross-path comparison.
6. Repeated execution.
7. Metamorphic relations.
8. LLM semantic judgement (**never alone**).
9. Browser-level heuristics.

### Bug pipeline

```text
Observation → Anomaly → Hypothesis → Investigation → Reproduction (≥ N)
  → status upgrade → BugReport + Evidence
```

Statuses: `observed` → `suspected` → `reproduced` → `verified`.

Confidence combines deterministic, behavioural, repetition, and optional LLM signals.

### Metamorphic relations (generic representation)

```text
MetamorphicRelation
  id, name, description
  transform: ActionSequence -> ActionSequence
  expectation: equivalence | preserved_properties | monotonicity
  applicable_when: predicate over model/state
```

Examples (not hard-coded as universal truths): refresh preserves cart contents under X; sort twice ≡ sort once; back/forward restores expected UI state when history allows.

---

## 12. Persistence

### PostgreSQL

Projects, targets, runs, sessions, states, transitions, actions, observations (metadata), workflows, tests, executions, anomalies, bugs, evidence metadata, LLM call records.

### File / object store

Screenshots, large HTML snapshots, Playwright traces, recordings.

Phase 1: local `data/` directory behind a `ArtifactStore` interface. Later: S3-compatible backend without domain changes.

### Migrations

Alembic from Phase 1 once Postgres is wired.

---

## 13. API and CLI

### CLI (Phase 1 first)

```text
webtester explore <url> [--max-actions N] [--strategy novelty]
webtester status <run_id>
webtester bugs <project>
webtester reproduce <bug_id>
webtester tests <project>          # Phase 3+
```

### FastAPI (Phase 1 stub optional; real surface Phase 2+)

- create project / configure target
- start / stop exploration
- exploration status
- inspect states / workflows
- generate / run tests
- list / inspect bugs and evidence
- reproduce bug

No frontend in this phase.

---

## 14. Safety / Authorization

A run cannot start unless:

1. `Target` + `ScopePolicy` exist.
2. Explicit authorization flag is set in config.
3. Navigation stays within allowed domains.
4. Action/runtime/LLM budgets are enforced.
5. Dangerous actions (e.g. unconstrained upload/payment if listed) are denied.

Security testing remains non-destructive. No unrestricted autonomous attacking.

---

## 15. Tooling and Quality

| Tool | Role |
| --- | --- |
| `pyproject.toml` + uv/pip | Packaging |
| pytest | Unit / integration / e2e |
| ruff | Lint/format |
| mypy | Type checking |
| pre-commit | Hooks |
| Docker Compose | Postgres (+ app later) |
| structured logging | Observability |

Python version: **3.11+** (aligns with modern async Playwright / type features).

---

## 16. Phase 1 Vertical Slice (architecture-level)

End-to-end path to prove the architecture before expanding plugins:

```text
URL
 → Browser (Playwright)
 → Observation (DOM simplify + fingerprint)
 → Candidate actions (deterministic)
 → Optional LLM prioritize (free provider)
 → Execute action
 → New observation
 → Update in-memory/persisted state model
 → Trivial anomaly detection (console error, HTTP 5xx, nav failure)
 → Evidence + JSON run report
```

**CLI entry:** `webtester explore <url> --max-actions N`

**Out of Phase 1:** full FastAPI product surface, metamorphic suite, parallel workers, full oracle stack, benchmark suite, screenshot embeddings.

---

## 17. Decision Log (architecture)

| Decision | Why | Alternatives | Trade-offs |
| --- | --- | --- | --- |
| Playwright adapter | Mature testing surface | browser-use, Selenium, raw CDP | More code; better control |
| Sparse LLM + model | TRACER/Crawljax evidence | Monolithic LLM agent | Slower MVP; better precision/cost |
| Groq + Gemini-Lite | Free volume + reasoning | Single free provider | Dual config |
| Postgres + files | Research-scale persistence | SQLite-only | Needs Docker for full stack |
| Multi-oracle pipeline | Avoid LLM-judge failure modes | Crash-only / LLM-only | More complexity |
| Explicit ScopePolicy | Authorized testing only | Open crawl | Requires config friction |

---

## 18. Next Documents

- [ROADMAP.md](ROADMAP.md) — phased delivery and exit criteria  
- [EVALUATION.md](EVALUATION.md) — metrics, benchmarks, baselines, RQs
