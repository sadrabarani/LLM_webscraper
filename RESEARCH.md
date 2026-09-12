# RESEARCH.md

**Project:** `webtester` — Autonomous Black-Box Web Testing Agent  
**Phase:** 0 — Research & Architecture  
**Date:** 2026-09-12  

This document records literature review, system comparisons, free-LLM API findings, reuse decisions, research gaps, and technical risks. Implementation begins only after architecture approval (see [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md), [EVALUATION.md](EVALUATION.md)).

---

## 1. Problem Statement

Build a large-scale Python backend that, given an authorized target website URL:

1. Explores the site through a real browser (black-box).
2. Observes multimodal browser-level signals (HTML/DOM, accessibility tree, screenshots, network, console, behaviour).
3. Builds an evolving behavioural model.
4. Generates and executes tests.
5. Detects anomalies, investigates and reproduces bugs.
6. Produces evidence-backed structured bug reports.

**Black-box definition used here:** no access to target source code or server-side implementation. Any information legitimately available through normal browser interaction is allowed, including HTML/DOM. This is **not** vision-only.

**Non-goal for shallow scrapers:** URL → crawl links → dump HTML to LLM → “find bugs”.

---

## 2. TRACER Analysis

### 2.1 Sources

- Repository: [Chatbot-TRACER/TRACER](https://github.com/Chatbot-TRACER/TRACER)
- Evaluation data: [Chatbot-TRACER/TRACER-evaluation](https://github.com/Chatbot-TRACER/TRACER-evaluation)
- Connectors: [Chatbot-TRACER/chatbot-connectors](https://github.com/Chatbot-TRACER/chatbot-connectors)
- Paper: *Reverse Engineering of Chatbot Behaviour for Automated Testing* (SN Computer Science, 2026) — [Springer](https://link.springer.com/article/10.1007/s42979-026-05237-5)
- Earlier ICTSS version: *Automated Exploration of Conversational Agents for the Synthesis of Testing Profiles*

### 2.2 What TRACER Does

TRACER is an LLM-driven **black-box reverse-engineering** tool for **deployed chatbots** (not websites). Pipeline:

1. **Exploration phase** — Explorer agent converses in multiple sessions (`S` sessions × `N` turns).
2. **Initial probing** — Detect language and fallback messages.
3. **Functionality extraction** — After each session, LLM extracts functionality nodes (name, description, parameters, outputs).
4. **Consolidation** — Session-local and global merge of semantically duplicate nodes.
5. **Refinement phase** — Global consolidation; classify chatbot as transactional vs informational; infer workflow edges (previous/followers).
6. **Profile generation** — Synthesize YAML conversation profiles for the Sensei user simulator.
7. **Testing** — Sensei executes profiles; reports crashes, timeouts, loops, unfinished goals.

Reported results (evaluation repo / paper): high functionality coverage; ~84.6% mutation score; ~94–96% precision on real-world chatbot functionality discovery.

### 2.3 Architecture Notes (from repo)

| Area | Contents |
| --- | --- |
| `tracer/agent.py` | Core LangGraph-style agent orchestration |
| `tracer/analysis/` | Functionality analysis / classification |
| `tracer/generation/` | Profile generation |
| `tracer/schemas/` | Structured model schemas |
| `tracer/prompts/` | Prompt templates |
| `tracer/graphs/` | Workflow graph visualization (Graphviz) |
| `tracer/conversation/` | Session conversation handling |
| `chatbot-connectors` | Extensible connector abstraction |

LLM usage: exploration model can differ from profile-generation model (cost split). Supports OpenAI and Gemini via env keys. Timing system includes token-bucket rate limiting, human-like delays, exponential backoff, session cooldowns, and LLM rate-limit protection.

### 2.4 Concepts That Transfer to Web Testing

| TRACER concept | Web analogue |
| --- | --- |
| Black-box via interface only | Browser-observable interaction only |
| FunctionalityNode | Page/UI state + capability + form fields |
| Parameters / admitted values | Input fields, options, validation cues |
| Outputs | Visible results, confirmations, network outcomes |
| Entry points / followers graph | State-flow / workflow graph |
| Explore → refine → synthesize tests | Same macro pipeline |
| Rate-limit / budget awareness | LLM + crawl budgets |
| Duplicate merge / refinement | State similarity + workflow dedup |
| Profile → simulator execution | Reproducible action sequences → test executor |
| Observed failures (crash, timeout, loop) | Console/network/state anomalies |

### 2.5 Concepts That Do Not Transfer

| TRACER concept | Why not |
| --- | --- |
| Natural-language utterances as primary actions | Web actions are clicks, fills, navigation, etc. |
| Fallback-message probing | No universal “fallback” in websites |
| Chatbot transactional vs informational classification | Websites need richer page/workflow types |
| Sensei conversation profiles as YAML goals | Need action graphs + oracles over UI/state |
| LangGraph conversational loop as the core | Prefer deterministic explore loop + sparse LLM |
| Graphviz as primary model store | Need persisted PostgreSQL state graphs |

### 2.6 Decision

**Do not fork or copy TRACER.** Use it as the primary **methodological inspiration** for: explore → behavioural model → test synthesis → oracle-driven execution under LLM budget constraints.

---

## 3. Related Systems Comparison (12+)

### 3.1 Summary Table

| System | Problem | Browser tech | LLM role | Relevant? | Reuse? |
| --- | --- | --- | --- | --- | --- |
| **TRACER** | Chatbot model + tests | Chat connectors | Explore + refine + profiles | High (method) | Inspiration only |
| **Crawljax** | AJAX state-flow crawl | WebDriver | None | High | Inspiration (Java) |
| **FragGen** | Fragment-based exploration + regression tests | Crawljax/WebDriver | None | High | Inspiration |
| **WebTestPilot** | NL-spec E2E testing + oracles | Playwright / browser-use | Agent + symbolized oracles | Very high | Inspiration; study benchmarks |
| **browser-use** | Goal-driven web agent | Playwright → CDP/Rust | Every-step agent | Medium | Inspiration only |
| **Playwright MCP** | LLM browser tools via a11y | Playwright | Tool-calling host | Medium | Inspiration |
| **Skyvern** | Workflow automation | Playwright + vision | Goal agent | Low–medium | Inspiration only (AGPL) |
| **BrowserGym** | Unified web-agent eval | Playwright | External agents | Medium (eval) | Optional later adapter |
| **WebArena** | Realistic task benchmark | Self-hosted sites | Agents under test | Medium (eval) | Benchmark ideas |
| **Mind2Web** | Offline generalist web tasks | Snapshots/traces | Training/eval | Low–medium | Action taxonomy |
| **WebLINX** | Instruction-following traces | Real sites (static) | Eval | Low | Minor |
| **WebVoyager** | Live multimodal web agent | Live sites | Vision+action agent | Medium (caution) | Do not copy eval blindly |
| **AgentBench** | Multi-env agent eval | Mixed | Agents under test | Low | Out of scope early |
| **OSWorld** | Desktop computer-use | VM desktop | Multimodal agents | Low | Out of scope |
| **GUISpector** | NL GUI requirement verification | Playwright | MLLM agent | Medium | Adjacent inspiration |
| **Trident** | Non-crash GUI functional bugs | Mobile UI Automator | Multi-agent | Low–medium | Adjacent inspiration |

### 3.2 Classical Model-Based Web Testing

#### Crawljax

- **Problem:** Explore modern JS/AJAX apps by firing UI events; build a **state-flow graph** of DOM states and transitions.
- **Strengths:** Mature event-driven crawling; plugin architecture; deterministic model inference without LLMs.
- **Weaknesses:** Java; brittle on highly dynamic SPAs; limited semantic understanding; weak functional oracles.
- **For us:** Primary inspiration for **state graph + action transitions + novelty exploration**. Reimplement concepts in Python/Playwright; do not wrap the Java tool as a hard dependency.

#### FragGen (Fragment-Based Test Generation)

- **Problem:** Improve state abstraction and regression oracles via page **fragments** (structural + visual similarity), diversify exploration, generate robust tests.
- **Strengths:** Better than whole-page DOM equality; fragment-level oracles; empirical gains on state-pair discrimination.
- **Weaknesses:** Complex VIPS-style fragmentation; still largely regression/diff oriented.
- **For us:** Inform Phase 2+ **state similarity** (fragment / interactive-region hashing before screenshot embeddings).

### 3.3 Modern LLM Web Testing / Agents

#### WebTestPilot (2026, FSE)

- **Problem:** Agentic E2E testing against **natural-language specifications**; infer pre/postcondition oracles via **symbolized GUI elements**.
- **How:** Symbolize critical GUI elements; translate NL into steps with symbolic assertions; Playwright/browser-use execution; bug-injected Docker webapps.
- **Reported:** High task completion and bug precision/recall on their benchmark.
- **Strengths:** Best published peer for **oracle reliability** and **controlled buggy apps**.
- **Weaknesses / mismatch:** Requires NL requirements; not primarily open-ended exploratory QA without specs.
- **Reuse:** Study `/webapps` and oracle symbolization ideas. **Do not depend** on the package as our core runtime.

#### browser-use

- **Problem:** Make websites accessible to AI agents for task automation.
- **How:** Distilled DOM/a11y state → LLM structured actions → execute → loop. Historically Playwright; moving toward CDP and Rust-backed agent.
- **Strengths:** Strong observation distillation; popular action schemas; rapid iteration.
- **Weaknesses:** Optimized for **task completion**, not behavioural modeling / bug verification; LLM-heavy; product/cloud coupling; AGPL-adjacent ecosystem complexity for a research backend.
- **Reuse:** Inspiration for compact observations and action enums. **Own Playwright adapter** instead.

#### Playwright MCP (Microsoft)

- **Problem:** Expose Playwright to coding agents via MCP using **accessibility snapshots** (not pixels).
- **Strengths:** LLM-friendly structured observations; deterministic tool application.
- **Weaknesses:** MCP host model, not a testing architecture.
- **Reuse:** Design principle — prefer a11y + DOM over vision-only.

#### Skyvern

- **Problem:** Automate browser workflows with LLMs + computer vision.
- **Strengths:** Resilient workflows, auth/CAPTCHA handling, Playwright-compatible SDK.
- **Weaknesses:** AGPL-3.0; goal automation product, not exploratory QA with behavioural models.
- **Reuse:** Inspiration only.

#### GUISpector / Trident

- **GUISpector:** Verify NL requirements on GUI prototypes with Playwright + MLLM.
- **Trident:** Vision-driven multi-agent GUI testing for non-crash functional bugs (mobile-oriented).
- **Reuse:** Adjacent ideas for requirement checks and non-crash bug taxonomies.

### 3.4 Benchmarks & Agent Frameworks

| System | Use for webtester |
| --- | --- |
| **BrowserGym / AgentLab** | Later optional evaluation harness patterns |
| **WebArena / VisualWebArena** | Task completion environments — secondary; not bug ground truth |
| **Mind2Web / WebLINX** | Action vocabulary and interaction patterns |
| **WebVoyager** | Live multimodal agent reference; **eval caution** — shortcut-prone tasks and weak LLM-as-judge agreement reported in later critiques |
| **AgentBench / OSWorld** | Broader agent capability; out of scope for Phases 1–4 |

### 3.5 Reuse vs Build Matrix

| Capability | Decision | Rationale |
| --- | --- | --- |
| Browser automation | **Build** Playwright adapter | Control, testability, replaceability |
| DOM/a11y distillation | **Build** (inspire browser-use / Playwright MCP) | Core observation pipeline |
| State-flow graph | **Build** (inspire Crawljax/FragGen/TRACER) | Domain-specific persistence & APIs |
| LLM provider layer | **Build** | Free-tier routing, metrics, caching |
| Exploration strategies | **Build** | Pluggable strategies are core IP |
| Oracles / metamorphic | **Build** (inspire WebTestPilot + classical MBT) | Research differentiator |
| Bug-injected fixtures | **Build** (inspire WebTestPilot layout) | Need web-specific ground truth |
| browser-use / Skyvern as runtime | **Do not reuse** | Wrong product shape / license / LLM coupling |
| Crawljax binary | **Do not reuse** | Java stack mismatch |
| Paid LLM SDKs as required deps | **Do not** | Phase constraint |

---

## 4. Free LLM API Research

**Constraint:** Phase development must run on **free APIs / free tiers**. Quotas change; architecture must not hard-code limits as constants of truth — read provider headers / AI Studio when available and fail gracefully.

### 4.1 Provider Comparison (as of research, Sep 2026)

| Provider | Free nature | Approx practical limits | Model quality for us | Structured output | Python | OpenAI-compatible | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Groq** | Renewable free org rate limits | Small models: ~30 RPM, very high RPD (e.g. ~14.4K for `llama-3.1-8b-instant`); larger models often ~1K RPD / lower TPM | Good for fast cheap calls; weaker on deep multimodal | Via JSON mode / tools depending on model | Official SDK + OpenAI client | Yes | **Primary volume provider** |
| **Google Gemini** | Free tier (project-specific) | Flash often ~20 RPD (too scarce); **Flash-Lite ~500 RPD** reported; Google docs push “check AI Studio” | Stronger reasoning / multimodal | Native structured output | `google-genai` | Partial | **Secondary reasoning provider** |
| **OpenRouter `:free`** | Free model variants | ~20 RPM; **~50 RPD** without credits (higher after lifetime credit threshold) | Variable; models appear/disappear | Depends on upstream | OpenAI client | Yes | **Fallback only** |
| **Cerebras** | Trial credits ($5, card often required, expires) | e.g. 5 RPM / 30K TPM on trial models | Fast open models | Yes via chat API | OpenAI client | Yes | **Not a core free dependency** |
| **Local (Ollama/vLLM)** | Truly free locally | Hardware-bound | Depends on local GPU/CPU | Via frameworks | Yes | Often | **Optional LocalModelProvider** |
| **OpenAI / Anthropic paid** | Paid | N/A for this phase | High | Excellent | Yes | Yes | **Optional later adapters only** |

### 4.2 Recommended Default Stack

1. **Groq** small/fast model — candidate action prioritization, cheap classification, high-frequency structured tasks.
2. **Gemini Flash-Lite** — semantic page understanding, anomaly interpretation, bug classification when budget allows.
3. **OpenAICompatibleProvider** — OpenRouter `:free` and local gateways as failover.
4. **LocalModelProvider** — offline/dev without cloud quota.

### 4.3 LLM Cost-Awareness Implications

- Prefer deterministic DOM/state processing; LLM only when reasoning adds value.
- Cache by `(provider, model, prompt_hash, observation_fingerprint)`.
- Track: calls, input/output tokens, latency, 429s, retries, estimated cost, remaining budget headers.
- Split models by role (TRACER pattern: strong explore vs cheap synthesis).
- Cap LLM calls per exploration run via `Budget`.

### 4.4 Why Not a Single Provider?

- Free Flash RPD alone cannot sustain agent loops.
- Groq volume + Gemini-Lite quality covers development better than either alone.
- Trade-off: dual configuration and response-format differences — mitigated by `LLMProvider` abstraction and response validation.

---

## 5. Research Gap

| Lineage | Optimizes for |
| --- | --- |
| LLM browser agents (browser-use, WebVoyager, Skyvern) | Task completion |
| Classical crawlers (Crawljax, FragGen) | Coverage / regression diffs |
| Spec-driven LLM testers (WebTestPilot, GUISpector) | NL requirement conformance |

**Gap:** Few systems combine:

> multimodal **browser-observable** observation → evolving **behavioural model** → **pluggable exploration strategies** → **multi-oracle** anomaly pipeline → **reproduction** → **evidence-backed** bug reports  

under **free-tier LLM budgets** and **authorized-scope safety**, without requiring target source code or mandatory NL specs.

**webtester** targets that gap.

---

## 6. Technical Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Free LLM quotas collapse mid-run | Exploration stalls | Multi-provider failover, caching, deterministic fallbacks, hard budgets |
| Oracle problem / false positives | Untrustworthy reports | Multi-evidence confidence; statuses `observed|suspected|reproduced|verified`; LLM never sole oracle |
| State explosion on dynamic sites | Memory/time blowup | Budgets, novelty scoring, fragment fingerprints, scope limits |
| SPA / auth / CAPTCHA | Incomplete exploration | Explicit scope; credentialed targets only when configured; no CAPTCHA-bypass attacks |
| Flaky Playwright timing | Non-reproducible bugs | Explicit waits, traces, evidence retention, reproduction retries |
| HTML too large for LLM context | Cost + truncation | Simplification pipeline; never send raw full HTML by default |
| Over-abstraction before MVP | Delayed learning | Phase 1 vertical slice before full plugin matrix |
| License contamination (AGPL agent stacks) | Legal risk | Own Playwright layer; inspiration-only from AGPL projects |
| Evaluating with task-success benchmarks | Misleading claims | Primary eval on bug-injected apps with ground truth |

---

## 7. Major Decisions (Evidence-Backed)

### D1 — Own Playwright `BrowserController`

- **Why:** Network/console/a11y/screenshots/traces; Python maturity; industry standard for testing.
- **Alternatives:** browser-use runtime; Selenium; raw CDP.
- **Trade-off:** More engineering vs control and deterministic-first design.
- **Evidence:** Playwright MCP and WebTestPilot both center Playwright; browser-use itself historically used Playwright then moved away for product reasons that do not match ours.

### D2 — Free-first multi-provider LLM layer

- **Why:** Phase constraint; quota fragility.
- **Alternatives:** Single Gemini Flash; paid OpenAI-only.
- **Trade-off:** Routing complexity vs survivable free development.
- **Evidence:** Flash RPD scarcity vs Groq volume; Flash-Lite as Gemini practical tier.

### D3 — Behavioural model first (not pure LLM agent)

- **Why:** TRACER shows model → tests improves systematic coverage; Crawljax shows graphs enable reproducible exploration.
- **Alternatives:** Stateless LLM browser loop.
- **Trade-off:** Slower MVP; better research and test generation later.

### D4 — PostgreSQL + file evidence store

- **Why:** Structured runs/states/bugs/LLM metrics at research scale; concurrent runs.
- **Alternatives:** SQLite-only; MongoDB.
- **Trade-off:** Docker required for local full stack; SQLite retained for unit tests only.

### D5 — Multi-oracle bug pipeline

- **Why:** LLM-as-judge alone is unreliable (WebVoyager critique literature).
- **Alternatives:** Crash-only oracles; LLM-only judgment.
- **Trade-off:** More engineering; higher precision.

---

## 8. Open Questions for Later Phases

1. How aggressive should Phase 2 fragment similarity be vs simple interactive signatures?
2. When to introduce screenshot embeddings (cost vs gain under free quotas)?
3. How much BrowserGym integration is worth vs custom harness?
4. Can metamorphic relations be learned semi-automatically from the behavioural model?

These do not block Phase 0 or Phase 1.

---

## 9. References (selected)

1. Sotillo del Horno et al. — *Reverse Engineering of Chatbot Behaviour for Automated Testing*, SN Computer Science, 2026.  
2. TRACER — https://github.com/Chatbot-TRACER/TRACER  
3. Mesbah et al. — Crawljax / AJAX state-flow crawling (ICWE 2008 and follow-ons).  
4. FragGen — *Fragment-Based Test Generation for Web Apps*, TSE / arXiv:2110.14043.  
5. Teoh et al. — *WebTestPilot*, PACMSE FSE, 2026. https://github.com/code-philia/WebTestPilot  
6. Zhou et al. — *WebArena*, 2023/2024.  
7. Deng et al. — *Mind2Web*, 2023.  
8. He et al. — *WebVoyager*, ACL 2024.  
9. BrowserGym ecosystem — arXiv:2412.05467; https://github.com/ServiceNow/BrowserGym  
10. Playwright MCP — https://github.com/microsoft/playwright-mcp  
11. browser-use — https://github.com/browser-use/browser-use  
12. Skyvern — https://github.com/Skyvern-AI/skyvern  
13. Groq rate limits — https://console.groq.com/docs/rate-limits  
14. Gemini rate limits — https://ai.google.dev/gemini-api/docs/rate-limits  

---

## 10. Next Document

See [ARCHITECTURE.md](ARCHITECTURE.md) for the concrete system design derived from this research.
