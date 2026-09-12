"""CLI entrypoint."""

from __future__ import annotations

import typer
from rich import print as rprint

from webtester.config.settings import get_settings
from webtester.exploration.engine import ExplorationEngine

app = typer.Typer(
    name="webtester",
    help="Autonomous black-box web testing agent",
    add_completion=False,
    invoke_without_command=False,
)


@app.command("explore")
def explore(
    url: str = typer.Argument(..., help="Target URL (authorized sites only)"),
    max_actions: int = typer.Option(10, "--max-actions", "-n"),
    strategy: str = typer.Option("novelty", "--strategy", "-s", help="novelty|bfs"),
    authorize: bool = typer.Option(
        False,
        "--authorize",
        help="Confirm you are authorized to test this site",
    ),
    no_llm: bool = typer.Option(False, "--no-llm", help="Disable LLM prioritization"),
    max_llm_calls: int = typer.Option(5, "--max-llm-calls"),
    headed: bool = typer.Option(False, "--headed", help="Show browser window"),
    persist_postgres: bool = typer.Option(
        False, "--persist-postgres", help="Also write metadata to Postgres"
    ),
) -> None:
    """Explore a website and write a JSON report under data/<run_id>/."""
    settings = get_settings()
    if persist_postgres:
        settings.persist_postgres = True
    engine = ExplorationEngine(settings)
    result = engine.run(
        url,
        max_actions=max_actions,
        strategy_name=strategy,
        authorize=authorize,
        use_llm=not no_llm,
        max_llm_calls=max_llm_calls,
        headless=not headed,
    )
    rprint(f"[green]Run[/green] {result.run.id} — {result.run.status}")
    rprint(f"Metrics: {result.metrics}")
    if result.anomalies:
        rprint(f"[yellow]Anomalies:[/yellow] {len(result.anomalies)}")
        for anomaly in result.anomalies[:10]:
            rprint(f"  - {anomaly.signals}: {anomaly.detail[:120]}")
    if result.report_path:
        rprint(f"Report: {result.report_path}")


@app.command("status")
def status(run_id: str = typer.Argument(...)) -> None:
    """Show metrics for a previous run from the local data directory."""
    settings = get_settings()
    report = settings.webtester_data_dir / run_id / "report.json"
    if not report.exists():
        rprint(f"[red]No report found for run {run_id}[/red]")
        raise typer.Exit(code=1)
    rprint(report.read_text(encoding="utf-8"))


@app.callback()
def main() -> None:
    """webtester CLI."""


if __name__ == "__main__":
    app()
