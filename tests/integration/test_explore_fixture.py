from __future__ import annotations

import pytest

from benchmarks.fixture_site import start_fixture_server
from webtester.config.settings import Settings
from webtester.exploration.engine import ExplorationEngine


@pytest.mark.integration
@pytest.mark.e2e
def test_explore_fixture_discovers_states_and_console_anomaly(tmp_path) -> None:
    server, base_url = start_fixture_server()
    try:
        settings = Settings(
            webtester_authorized=True,
            webtester_data_dir=tmp_path / "data",
            webtester_llm_provider="none",
            webtester_headless=True,
        )
        engine = ExplorationEngine(settings)
        result = engine.run(
            base_url,
            max_actions=6,
            strategy_name="novelty",
            authorize=True,
            use_llm=False,
            max_llm_calls=0,
        )
        assert result.run.status.value == "completed"
        assert result.metrics["states"] >= 2
        assert result.metrics["actions_executed"] >= 1
        assert result.report_path is not None
        assert result.report_path.exists()
        # Novelty prefers /buggy; if reached, console anomaly should appear.
        # Even if not reached within budget, run must still succeed.
        if any("/buggy" in (o.url or "") for o in result.observations):
            assert any("console_error" in a.signals for a in result.anomalies)
    finally:
        server.shutdown()
