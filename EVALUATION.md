# EVALUATION.md

**Project:** `webtester` — Autonomous Black-Box Web Testing Agent  
**Related:** [RESEARCH.md](RESEARCH.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [ROADMAP.md](ROADMAP.md)

Evaluation is designed from Phase 0 so instrumentation and benchmarks are not afterthoughts. Primary question: **does the system discover real bugs efficiently under browser + free-LLM budgets?**

---

## 1. Evaluation Principles

1. Prefer **controlled apps with ground truth** over ad-hoc production websites.
2. Separate **exploration quality**, **bug-finding quality**, and **LLM efficiency**.
3. Do not equate **task-completion** benchmarks (WebArena/WebVoyager-style) with bug-finding success.
4. Treat LLM-as-judge as a **metric to study**, not as ground truth.
5. Report **verified** bugs separately from suspected anomalies.
6. Fix random seeds, model IDs, budgets, and app versions for reproducibility.

---

## 2. What We Measure (Instrumentation)

Instrument from Phase 1 onward (even if not all metrics are meaningful yet).

### 2.1 Exploration counters

| Metric | Definition |
| --- | --- |
| Pages discovered | Distinct normalized URLs |
| States discovered | Distinct state fingerprints |
| Transitions discovered | Distinct (from, action, to) edges |
| Workflows discovered | Extracted multi-step paths (Phase 2+) |
| Actions executed | Successful + failed executions |
| Unique actions exercised | Distinct action identities |
| Exploration time | Wall clock |
| Browser time | Time inside browser operations |

### 2.2 Testing counters (Phase 3+)

| Metric | Definition |
| --- | --- |
| Tests generated | Count by category |
| Tests executed | Count / pass / fail / error |
| Oracle firings | By oracle type |

### 2.3 Bug counters (Phase 4+)

| Metric | Definition |
| --- | --- |
| Anomalies raised | Pre-verification |
| Bugs reported | By status |
| True positives | Match ground truth |
| False positives | Reported verified/suspected without GT match (define policy) |
| Duplicate bugs | Same GT bug, multiple reports |
| Reproduction success | Successful repros / attempts |

### 2.4 LLM / cost counters

| Metric | Definition |
| --- | --- |
| LLM calls | Total + by purpose + by provider |
| Tokens in/out | Sum + percentiles |
| Cache hit rate | Hits / lookups |
| Rate-limit errors | 429 count |
| Retries | Count |
| Latency | p50/p95 per provider |
| Estimated cost | 0 on free tiers; track anyway |
| Remaining budget | When headers available |

Export machine-readable `metrics.json` per run.

---

## 3. Primary Metrics

### State Coverage

\[
\text{StateCoverage} = \frac{|\text{DiscoveredStates} \cap \text{GroundTruthStates}|}{|\text{GroundTruthStates}|}
\]

### Action Coverage

\[
\text{ActionCoverage} = \frac{|\text{ExercisedActions} \cap \text{GroundTruthActions}|}{|\text{GroundTruthActions}|}
\]

### Workflow Coverage

\[
\text{WorkflowCoverage} = \frac{|\text{CoveredWorkflows}|}{|\text{GroundTruthWorkflows}|}
\]

A workflow is covered if its critical ordered action subsequence is observed (exact matching rules defined per benchmark manifest).

### Bug Precision

\[
\text{Precision} = \frac{\text{TruePositiveBugs}}{\text{ReportedBugs}}
\]

Default reporting set for precision: status ∈ {`reproduced`, `verified`} (configurable). Also report precision including `suspected` separately.

### Bug Recall

\[
\text{Recall} = \frac{\text{KnownBugsDiscovered}}{\text{TotalKnownBugs}}
\]

A known bug is discovered if a report matches its ground-truth id via signature rules (URL pattern + symptom + minimal step overlap).

### Bug Discovery Rate

\[
\text{DiscoveryRate} = \frac{\text{ConfirmedBugs}}{\text{ExplorationBudget}}
\]

Budget may be actions, minutes, or LLM calls — report all three normalizations.

### Reproduction Reliability

\[
\text{ReproReliability} = \frac{\text{SuccessfulReproductions}}{\text{ReproductionAttempts}}
\]

### LLM Efficiency

\[
\text{LLMEfficiency}_{\text{bugs}} = \frac{\text{ConfirmedBugs}}{\text{LLMCalls}}
\quad\text{and}\quad
\frac{\text{ConfirmedBugs}}{\text{Tokens}}
\]

Also report useful discoveries (new states/workflows) per LLM call for Phase 1–2 when bugs are rare.

---

## 4. Benchmark Suite

Do not evaluate only on random production sites. Build **controlled applications** with known functionality and injected bugs.

### 4.1 Benchmark types

| ID | Type | Why |
| --- | --- | --- |
| B1 | CRUD app | Forms, persistence, validation |
| B2 | E-commerce mini | Cart state, checkout paths |
| B3 | Dashboard | Filters, async widgets |
| B4 | Auth app | Login/logout/session |
| B5 | Booking / multi-step form | Wizard state |
| B6 | SPA router app | Client-side states vs URL |
| B7 | Async / delayed UI | Timing, flaky loading |
| B8 | Dynamic content | Infinite scroll / changing DOM |
| B9 | Subtle state bugs | Stale state, duplicate submit |
| B10 | Pagination / sorting | Metamorphic relations |

Phase 6 minimum viable suite: **B1, B4, B5, B9** (expand afterward).

### 4.2 Per-benchmark ground truth manifest

Each benchmark ships:

```text
benchmarks/<name>/
  app/                    # dockerized or static server
  ground_truth/
    states.json           # known state ids + fingerprints/descriptions
    workflows.json        # known workflows
    actions.json          # known interactive opportunities (optional)
    bugs.json             # known bugs
  README.md               # how to run
```

`bugs.json` fields (minimum):

- `id`, `title`, `category`, `severity`
- `symptoms` (console / network / UI / state)
- `expected_behaviour`, `actual_behaviour`
- `reproduction_steps` (canonical)
- `detection_hints` (for automated matching, not given to the agent)

### 4.3 Controlled bug classes

Inject bugs such as:

- Broken client/server validation mismatch
- Broken navigation / 404 on valid UI link
- Duplicate submission creating duplicate entities
- Inconsistent UI vs observable data state
- Auth/session bugs (logout not clearing state)
- Incorrect pagination (duplicate/missing items)
- Race-like UI (double-click creates two items)
- Stale state after back/refresh
- Subtle workflow failures (confirmation skipped)

Inspired by WebTestPilot’s bug-injected webapps approach, but oriented to **exploratory QA without mandatory NL specs**.

---

## 5. Baselines

Compare systems under **identical budgets** (actions, time, LLM calls).

| ID | Baseline | Description |
| --- | --- | --- |
| BL1 | Traditional crawler | Link/URL BFS, minimal DOM interaction |
| BL2 | Random browser exploration | Uniform random legal actions |
| BL3 | LLM browser agent without memory | Observation → LLM action; no state graph |
| BL4 | LLM browser agent with memory | Short trajectory memory only |
| BL5 | LLM + behavioural model | Model-guided exploration |
| BL6 | Behavioural model + generated tests | Phase 3 stack |
| BL7 | Full system | Model + tests + investigation (Phase 4+) |

**Rule:** Do not assume BL7 wins. Measure.

Phase 1 implements BL2 and a thin BL3/BL5 precursor. Full matrix is Phase 6.

---

## 6. Experiment Protocol

### 6.1 Configuration snapshot

Every experiment records:

- benchmark version / git commit
- strategy
- max actions / max minutes / max LLM calls
- provider + model IDs
- temperature / decoding settings
- seed
- headless flag
- scope policy

### 6.2 Repetitions

- Minimum **3** runs per (system × benchmark × budget) for stochastic methods.
- Report mean ± std for coverage and bug metrics.

### 6.3 Matching reported bugs to ground truth

A reported bug matches a GT bug if:

1. Symptom class overlaps (e.g. both duplicate-submit), AND
2. Affected route/state family matches, AND
3. Reproduction step Jaccard / ordered subsequence similarity ≥ threshold, OR
4. Manual adjudicator override (logged).

False positives: verified/reproduced reports with no GT match after adjudication.

### 6.4 Human adjudication

Keep a lightweight adjudication log for ambiguous matches. LLM judges may assist but do not finalize ground truth.

---

## 7. Research Questions

Aligned for a future paper; phases indicate earliest measurability.

| RQ | Question | Earliest phase |
| --- | --- | --- |
| RQ1 | Can LLM-driven black-box browser agents discover meaningful website functionality? | 2 |
| RQ2 | Does maintaining a behavioural model improve exploration efficiency? | 2 / 6 |
| RQ3 | Does model-based exploration discover more bugs than naive LLM browsing? | 4 / 6 |
| RQ4 | Does hypothesis-driven exploration outperform random exploration? | 4 / 6 |
| RQ5 | Can metamorphic testing improve black-box web bug discovery? | 3 / 6 |
| RQ6 | How accurately can an LLM distinguish anomalies from real bugs? | 4 / 6 |
| RQ7 | How does model choice affect black-box web testing performance? | 1 / 6 |
| RQ8 | What is the relationship between exploration budget and bug discovery? | 6 |
| RQ9 | How much does each architectural component contribute (ablation)? | 6 |

### Ablations for RQ9

- No LLM (deterministic only)
- No behavioural model
- No metamorphic oracles
- No reproduction loop
- No observation simplification (stress test — expect quota failure)

---

## 8. Secondary / Cautionary Benchmarks

| Resource | Use | Caution |
| --- | --- | --- |
| WebArena / VisualWebArena | Agent competence reference | Task success ≠ bug finding |
| BrowserGym | Harness patterns | Optional adapter later |
| Mind2Web / WebLINX | Action taxonomy studies | Offline; not our primary GT |
| WebVoyager | Historical multimodal agent ref | Inflated scores / weak judges reported in later critiques — do not use as sole quality claim |
| AgentBench / OSWorld | Broad agent ability | Out of scope for core webtester claims |

---

## 9. Success Thresholds (initial targets)

Not publication claims — engineering gates.

| Gate | Target |
| --- | --- |
| Phase 1 fixture | ≥10 states or until budget; zero crashes in harness |
| Phase 2 | State coverage ≥60% on B1 ground-truth states at fixed budget |
| Phase 3 | ≥1 generated test suite catches ≥2 injected bugs on B1 |
| Phase 4 | Precision(verified) ≥0.7 on suite subset; repro reliability ≥0.8 for verified set |
| Phase 6 | Full baseline table for ≥3 apps; RQ2/RQ3 measurable |

Thresholds will be revised after first baseline runs.

---

## 10. LLM Efficiency Evaluation

Because free APIs are scarce:

1. Cap LLM calls per experiment (e.g. 50 / 200 / 500).
2. Compare discovery curves vs calls and vs tokens.
3. Measure cache hit rate impact.
4. Compare Groq-small vs Gemini-Flash-Lite vs mixed router (RQ7).
5. Always include a **zero-LLM** deterministic baseline.

---

## 11. Reporting Format

Each Phase 6 experiment produces:

```text
results/<experiment_id>/
  config.json
  metrics.json
  bugs.json
  coverage.json
  llm_usage.json
  notes.md
```

Aggregate tables:

- Coverage vs budget
- Precision/recall by system
- LLM efficiency Pareto (bugs vs tokens)

---

## 12. Ethics and Safety in Evaluation

- Benchmarks are self-hosted or explicitly authorized.
- No evaluation that requires attacking third-party production sites.
- Destructive actions disabled in ScopePolicy for all default experiments.

---

## 13. Immediate Evaluation Hooks for Phase 1

Even before full benchmarks:

1. Tiny fixture app with 2–3 pages and one injected console error.
2. Emit `metrics.json` with states, actions, transitions, LLM calls.
3. Manual checklist: did the agent reach page B? did it flag the console anomaly?

This validates the measurement pipeline early.
