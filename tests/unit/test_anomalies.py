from __future__ import annotations

from webtester.anomalies.detect import detect_anomalies
from webtester.domain.models import (
    ActionResult,
    ActionResultStatus,
    ConsoleEvent,
    NetworkEvent,
    Observation,
    StateFingerprint,
)


def _obs(**kwargs: object) -> Observation:
    base = dict(
        url="http://example.com/",
        title="t",
        simplified_dom="",
        state_fingerprint=StateFingerprint(
            normalized_url="http://example.com/",
            simplified_dom_hash="x",
            interactive_signature_hash="y",
            form_values_hash="z",
        ),
    )
    base.update(kwargs)
    return Observation(**base)  # type: ignore[arg-type]


def test_detect_console_error() -> None:
    obs = _obs(console_events=[ConsoleEvent(level="error", text="boom")])
    anomalies = detect_anomalies(obs, state_id="s1")
    assert any("console_error" in a.signals for a in anomalies)


def test_detect_http_5xx() -> None:
    obs = _obs(
        network_events=[
            NetworkEvent(url="http://example.com/x", method="GET", status=500)
        ]
    )
    anomalies = detect_anomalies(obs)
    assert any("http_5xx" in a.signals for a in anomalies)


def test_detect_action_failure() -> None:
    obs = _obs()
    anomalies = detect_anomalies(
        obs,
        action_result=ActionResult(status=ActionResultStatus.FAILED, error="nope"),
    )
    assert any("action_failure" in a.signals for a in anomalies)
