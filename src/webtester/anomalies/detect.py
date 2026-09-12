"""Trivial Phase-1 anomaly detection (deterministic)."""

from __future__ import annotations

from webtester.domain.models import (
    Action,
    ActionResult,
    ActionResultStatus,
    Anomaly,
    AnomalySeverity,
    Observation,
)


def detect_anomalies(
    observation: Observation,
    *,
    action: Action | None = None,
    action_result: ActionResult | None = None,
    state_id: str | None = None,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    for event in observation.console_events:
        if event.level in {"error", "assert"}:
            anomalies.append(
                Anomaly(
                    signals=["console_error"],
                    severity=AnomalySeverity.HIGH,
                    related_state_id=state_id,
                    related_action_id=action.id if action else None,
                    detail=event.text[:500],
                )
            )

    for event in observation.network_events:
        if event.status is not None and event.status >= 500:
            anomalies.append(
                Anomaly(
                    signals=["http_5xx"],
                    severity=AnomalySeverity.HIGH,
                    related_state_id=state_id,
                    related_action_id=action.id if action else None,
                    detail=f"{event.method} {event.url} -> {event.status}",
                )
            )
        elif event.failed:
            anomalies.append(
                Anomaly(
                    signals=["network_failure"],
                    severity=AnomalySeverity.MEDIUM,
                    related_state_id=state_id,
                    related_action_id=action.id if action else None,
                    detail=f"{event.method} {event.url} failed: {event.failure_text}",
                )
            )

    for nav in observation.navigation_events:
        if not nav.ok or (nav.status is not None and nav.status >= 500):
            anomalies.append(
                Anomaly(
                    signals=["navigation_failure"],
                    severity=AnomalySeverity.HIGH,
                    related_state_id=state_id,
                    related_action_id=action.id if action else None,
                    detail=nav.error or f"navigation status={nav.status}",
                )
            )

    if action_result and action_result.status != ActionResultStatus.OK:
        anomalies.append(
            Anomaly(
                signals=["action_failure"],
                severity=AnomalySeverity.MEDIUM,
                related_state_id=state_id,
                related_action_id=action.id if action else None,
                detail=action_result.error or "action failed",
            )
        )

    return anomalies
