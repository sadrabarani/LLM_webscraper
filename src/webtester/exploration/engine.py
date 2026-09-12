"""Exploration engine — Phase 1 vertical slice loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from webtester.anomalies.detect import detect_anomalies
from webtester.browser.playwright_adapter import PlaywrightBrowserController
from webtester.config.settings import Settings, scope_from_url
from webtester.domain.models import (
    Anomaly,
    Budget,
    ExplorationRun,
    LLMCallRecord,
    Observation,
    RunStatus,
    utcnow,
)
from webtester.exploration.strategies import (
    generate_candidate_actions,
    get_strategy,
)
from webtester.llm.providers import (
    NullLLMProvider,
    build_provider,
    prioritize_actions_with_llm,
)
from webtester.model.graph import BehaviouralModel
from webtester.observation.pipeline import compact_llm_context, process_observation
from webtester.persistence.artifacts import ArtifactStore
from webtester.persistence.report import write_run_report


@dataclass
class ExplorationResult:
    run: ExplorationRun
    model: BehaviouralModel
    anomalies: list[Anomaly] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    llm_calls: list[LLMCallRecord] = field(default_factory=list)
    report_path: Path | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


class ExplorationEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        url: str,
        *,
        max_actions: int = 10,
        strategy_name: str = "novelty",
        authorize: bool = False,
        use_llm: bool = True,
        max_llm_calls: int = 5,
        max_runtime_seconds: int = 180,
        headless: bool | None = None,
    ) -> ExplorationResult:
        authorized = authorize or self.settings.webtester_authorized
        scope = scope_from_url(
            url,
            max_actions=max_actions,
            max_runtime_seconds=max_runtime_seconds,
            max_llm_calls=max_llm_calls,
            authorized=authorized,
        )
        if scope.require_explicit_authorization and not scope.authorized:
            raise PermissionError(
                "Exploration not authorized. Pass --authorize or set WEBTESTER_AUTHORIZED=true"
            )

        run = ExplorationRun(
            target_url=url,
            status=RunStatus.RUNNING,
            strategy=strategy_name,
            started_at=utcnow(),
            config_snapshot={
                "max_actions": max_actions,
                "strategy": strategy_name,
                "use_llm": use_llm,
                "max_llm_calls": max_llm_calls,
            },
        )
        budget = Budget(
            actions_remaining=max_actions,
            runtime_deadline=utcnow() + timedelta(seconds=max_runtime_seconds),
            llm_calls_remaining=max_llm_calls,
        )
        model = BehaviouralModel()
        anomalies: list[Anomaly] = []
        observations: list[Observation] = []
        llm_calls: list[LLMCallRecord] = []
        strategy = get_strategy(strategy_name)
        artifacts = ArtifactStore(self.settings.webtester_data_dir / run.id)

        provider = NullLLMProvider()
        if use_llm and self.settings.webtester_llm_provider != "none":
            try:
                provider = build_provider(
                    self.settings.webtester_llm_provider,
                    groq_api_key=self.settings.groq_api_key,
                    groq_model=self.settings.groq_model,
                    google_api_key=self.settings.google_api_key,
                    gemini_model=self.settings.gemini_model,
                    openrouter_api_key=self.settings.openrouter_api_key,
                    openrouter_model=self.settings.openrouter_model,
                )
            except Exception:  # noqa: BLE001
                provider = NullLLMProvider()

        browser = PlaywrightBrowserController(scope)
        headless_flag = self.settings.webtester_headless if headless is None else headless
        try:
            browser.start(headless=headless_flag)
            nav = browser.navigate(url)
            raw = browser.observe()
            obs = process_observation(raw)
            if raw.screenshot_png:
                obs.screenshot_ref = artifacts.save_bytes(
                    "screenshots/step-000.png", raw.screenshot_png
                )
            if raw.html:
                obs.raw_html_ref = artifacts.save_text("html/step-000.html", raw.html)
            observations.append(obs)
            state = model.upsert_state(obs)
            anomalies.extend(
                detect_anomalies(
                    obs,
                    action_result=nav,
                    state_id=state.id,
                )
            )

            step = 0
            while budget.can_act():
                candidates = generate_candidate_actions(
                    obs, source_state_id=state.id, scope=scope
                )
                scored = strategy.propose(model, obs, candidates)
                if not scored:
                    break

                if (
                    use_llm
                    and budget.can_call_llm()
                    and not isinstance(provider, NullLLMProvider)
                ):
                    scored, record = prioritize_actions_with_llm(
                        provider,
                        context=compact_llm_context(obs),
                        scored=scored,
                        run_id=run.id,
                    )
                    if record:
                        llm_calls.append(record)
                        budget.consume_llm()

                chosen = scored[0].action
                result = browser.execute(chosen)
                chosen.execution_result = result.status
                chosen.error = result.error
                model.record_action(chosen)
                budget.consume_action()
                step += 1

                raw = browser.observe()
                raw.previous_action_id = chosen.id
                obs = process_observation(raw)
                if raw.screenshot_png:
                    obs.screenshot_ref = artifacts.save_bytes(
                        f"screenshots/step-{step:03d}.png", raw.screenshot_png
                    )
                if raw.html:
                    obs.raw_html_ref = artifacts.save_text(
                        f"html/step-{step:03d}.html", raw.html
                    )
                observations.append(obs)
                next_state = model.upsert_state(obs)
                chosen.result_state_id = next_state.id
                model.record_transition(
                    from_state_id=state.id,
                    to_state_id=next_state.id,
                    action_id=chosen.id,
                )
                anomalies.extend(
                    detect_anomalies(
                        obs,
                        action=chosen,
                        action_result=result,
                        state_id=next_state.id,
                    )
                )
                state = next_state

            run.status = RunStatus.COMPLETED
        except Exception:
            run.status = RunStatus.FAILED
            raise
        finally:
            browser.stop()
            run.finished_at = utcnow()

        metrics = {
            **model.summary(),
            "observations": len(observations),
            "anomalies": len(anomalies),
            "llm_calls": len(llm_calls),
            "actions_executed": len(model.actions),
        }
        report_path = write_run_report(
            artifacts.root,
            run=run,
            model=model,
            anomalies=anomalies,
            observations=observations,
            llm_calls=llm_calls,
            metrics=metrics,
        )

        if self.settings.persist_postgres:
            try:
                from webtester.persistence.db import persist_run

                persist_run(
                    self.settings.database_url,
                    run=run,
                    model=model,
                    anomalies=anomalies,
                    metrics=metrics,
                )
            except Exception as exc:  # noqa: BLE001
                metrics["postgres_error"] = str(exc)

        return ExplorationResult(
            run=run,
            model=model,
            anomalies=anomalies,
            observations=observations,
            llm_calls=llm_calls,
            report_path=report_path,
            metrics=metrics,
        )
