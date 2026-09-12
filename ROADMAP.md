# ROADMAP.md

**Project:** `webtester` — Autonomous Black-Box Web Testing Agent  
**Related:** [RESEARCH.md](RESEARCH.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [EVALUATION.md](EVALUATION.md)

Phased delivery. Do not implement later phases before earlier exit criteria are met.

---

## Guiding Rules

1. Do not over-engineer before the vertical slice works.
2. Do not make every component an LLM agent.
3. Free LLM APIs only as required dependencies.
4. Do not send raw massive HTML to the LLM.
5. Do not report unverified anomalies as bugs.
6. Do not inspect target source code; browser-observable info is allowed.
7. No frontend/UI in Phases 0–5 unless explicitly re-scoped.
8. Every major decision must have a reason (recorded in RESEARCH/ARCHITECTURE).

---

## Phase Overview

```text
Phase 0  Research & Architecture          ← current deliverable (docs)
Phase 1  Minimal Vertical Slice
Phase 2  Behavioural Model
Phase 3  Test Generation
Phase 4  Bug Investigation
Phase 5  Scaling
Phase 6  Evaluation & Benchmarks
```

---

## Phase 0 — Research & Architecture

### Objectives

- Analyze TRACER (repo + paper).
- Survey related systems (browser agents, black-box web testing, benchmarks).
- Verify free LLM API options and limits.
- Lock architecture, domain models, observation pipeline, exploration loop.
- Define MVP and evaluation methodology.

### Deliverables

| Artifact | Status |
| --- | --- |
| [RESEARCH.md](RESEARCH.md) | Required |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Required |
| [ROADMAP.md](ROADMAP.md) | Required |
| [EVALUATION.md](EVALUATION.md) | Required |

### Exit criteria

- Architecture approved for Phase 1.
- Free LLM provider strategy chosen (Groq primary volume, Gemini Flash-Lite secondary).
- Phase 1 vertical slice scoped and non-goals listed.
- **No large-scale implementation started.**

### Non-goals

- Application code, package scaffold (unless separately requested), Playwright integration, API server.

---

## Phase 1 — Minimal Vertical Slice

### Objectives

Prove end-to-end flow with minimal abstractions:

```text
URL → Browser → Observation → DOM processing → (optional) LLM
  → Action → Browser → Observation → State model → Trivial anomaly → Evidence → Report
```

### Deliverables

- `pyproject.toml`, package layout per ARCHITECTURE.md
- Playwright `BrowserController` adapter
- Observation simplification + state fingerprint (Phase 1 signals)
- Exploration engine with BFS + novelty strategies
- Optional free LLM action prioritization via `LLMProvider`
- CLI: `webtester explore <url> --max-actions N`
- File evidence store + JSON run summary
- Docker Compose Postgres (metadata persistence for runs/states)
- Unit tests for fingerprinting, action model, strategy selection
- Integration test against a tiny local fixture site
- `.env.example` for Groq / Gemini / OpenRouter keys

### Exit criteria

- Exploring a local fixture site for N actions works without crashes.
- State graph contains multiple nodes/transitions after a run.
- At least one deterministic anomaly class detected when injected (e.g. console error page).
- LLM path works with a free provider **or** cleanly degrades to deterministic prioritization when keys/quota missing.
- Domain layer has zero Playwright/provider imports.

### Non-goals

- Full FastAPI product API
- Metamorphic testing suite
- Parallel workers
- Screenshot embeddings
- Complete oracle / bug verification stack
- Research benchmark suite

---

## Phase 2 — Behavioural Model

### Objectives

Harden the evolving website behavioural model and exploration memory.

### Deliverables

- Persisted state graph with similarity / soft matching (fragment-oriented signals)
- Transition and action graphs; workflow extraction (heuristic first)
- Exploration memory (visited actions, frontiers)
- Additional strategies: DFS, random, information-gain, optional LLM-guided planning
- API endpoints: run status, list states, inspect transitions/workflows
- CLI: `webtester status <run>`

### Exit criteria

- Same logical UI state with different volatile DOM noise maps together more often than Phase 1 exact hash alone.
- Workflow paths can be exported for a controlled multi-page fixture.
- Demonstration write-up on a controlled website (internal note or docs section).

### Non-goals

- Full test generation productization
- Distributed workers

---

## Phase 3 — Test Generation

### Objectives

Generate and execute tests from the behavioural model.

### Deliverables

- Test generator for functional / boundary / invalid / transition / robustness / consistency categories (incremental coverage OK)
- Deterministic test executor via BrowserController
- Oracle framework (deterministic + state comparison + repetition)
- Initial metamorphic relation representation + a few seeded relations
- Regression re-run support for saved tests
- CLI: `webtester tests <project>`
- API: generate/run/list tests

### Exit criteria

- Generated tests replay discovered workflows with stable selectors where possible.
- Oracles catch injected validation / navigation failures on fixtures.
- At least one metamorphic relation implemented and measured.

### Non-goals

- Claiming high recall on production sites
- Parallel distributed execution

---

## Phase 4 — Bug Investigation

### Objectives

Turn anomalies into verified, evidence-backed bug reports.

### Deliverables

- Anomaly detectors (console, network, inconsistent state, workflow dead-ends, etc.)
- Hypothesis generation (LLM-assisted, budgeted)
- Reproduction loop with N attempts and slight perturbations
- Confidence scoring from multi-evidence
- Structured `BugReport` schema + persistence
- CLI: `webtester bugs <project>`, `webtester reproduce <bug>`
- API: list/inspect bugs and evidence

### Exit criteria

- Pipeline distinguishes `observed` / `suspected` / `reproduced` / `verified`.
- Verified bugs include reproduction steps + evidence artifacts.
- LLM-only suspicions are never auto-marked `verified`.

### Non-goals

- Exploit generation / offensive security tooling
- Public dashboard UI

---

## Phase 5 — Scaling

### Objectives

Support larger runs and operational robustness.

### Deliverables

- Parallel browser workers (process/job based)
- Job management and resumable runs
- Advanced budget management and provider failover polish
- Observation/LLM caching improvements
- Optional S3-compatible artifact store
- Hardening: retries, timeouts, observability dashboards (logs/metrics)

### Exit criteria

- Multiple workers can explore under a shared model/job queue without corrupting state.
- Runs resume after intentional interruption.
- LLM efficiency metrics exported per run.

### Non-goals

- Multi-tenant SaaS productization
- Frontend

---

## Phase 6 — Evaluation & Benchmarks

### Objectives

Make the system research-grade measurable.

### Deliverables

- Controlled benchmark applications with known bugs (see EVALUATION.md)
- Ground-truth manifests (states, workflows, bugs)
- Baseline runners: crawler, random, LLM-no-memory, model-based, full system
- Machine-readable metrics export (JSON/CSV)
- Experiment config reproducibility
- Results appendix / paper-oriented notes

### Exit criteria

- At least one full baseline comparison on ≥3 benchmark apps.
- Precision/recall for bugs computable from ground truth.
- LLM efficiency (bugs or discoveries per call/token) reported.

### Non-goals

- Treating WebVoyager task success as primary quality metric.

---

## Cross-Cutting Work (all implementation phases)

| Concern | When |
| --- | --- |
| Type safety (mypy), ruff, pytest | From Phase 1 |
| pre-commit | Phase 1 |
| ScopePolicy / safety gates | Phase 1 (required to run) |
| LLM metrics + caching | Phase 1 (basic), harden in 5 |
| Documentation updates | Each phase exit |
| Evaluation hooks (counters) | Instrument from Phase 1 |

---

## Suggested Near-Term Sequence After Phase 0 Approval

1. Scaffold `src/webtester` + tooling.
2. Implement Playwright adapter + observation pipeline.
3. Implement exploration loop without LLM.
4. Add Groq/Gemini providers + optional prioritize.
5. Persist run + emit report.
6. Fixture site + e2e test.
7. Stop and review before Phase 2.

---

## Milestone Checklist

| Milestone | Done when |
| --- | --- |
| M0 | Four architecture docs accepted |
| M1 | Vertical slice CLI demo on fixture |
| M2 | Behavioural model demo with workflows |
| M3 | Generated tests + oracles on fixtures |
| M4 | Verified bug reports with reproduction |
| M5 | Parallel/resumable runs |
| M6 | Benchmark comparison published internally |
