"""JSON run report writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from webtester.domain.models import (
    Anomaly,
    ExplorationRun,
    LLMCallRecord,
    Observation,
)
from webtester.model.graph import BehaviouralModel


def write_run_report(
    root: Path,
    *,
    run: ExplorationRun,
    model: BehaviouralModel,
    anomalies: list[Anomaly],
    observations: list[Observation],
    llm_calls: list[LLMCallRecord],
    metrics: dict[str, Any],
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "run": run.model_dump(mode="json"),
        "metrics": metrics,
        "states": [s.model_dump(mode="json") for s in model.states.values()],
        "transitions": [t.model_dump(mode="json") for t in model.transitions],
        "actions": [a.model_dump(mode="json") for a in model.actions],
        "anomalies": [a.model_dump(mode="json") for a in anomalies],
        "observations": [
            o.model_dump(mode="json", exclude={"simplified_dom"})
            | {"simplified_dom_preview": o.simplified_dom[:500]}
            for o in observations
        ],
        "llm_calls": [c.model_dump(mode="json") for c in llm_calls],
    }
    path = root / "report.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    metrics_path = root / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return path
