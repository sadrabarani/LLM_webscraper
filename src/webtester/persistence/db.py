"""Optional PostgreSQL persistence for Phase 1 metadata."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from webtester.domain.models import Anomaly, ExplorationRun, utcnow
from webtester.model.graph import BehaviouralModel


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "exploration_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    strategy: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class StateRow(Base):
    __tablename__ = "states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="")
    fingerprint_key: Mapped[str] = mapped_column(Text)
    visit_count: Mapped[int] = mapped_column(Integer, default=1)


class TransitionRow(Base):
    __tablename__ = "transitions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    from_state_id: Mapped[str] = mapped_column(String(64))
    to_state_id: Mapped[str] = mapped_column(String(64))
    action_id: Mapped[str] = mapped_column(String(64))


class AnomalyRow(Base):
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32))
    signals: Mapped[list[str]] = mapped_column(JSON)
    detail: Mapped[str] = mapped_column(Text, default="")


def persist_run(
    database_url: str,
    *,
    run: ExplorationRun,
    model: BehaviouralModel,
    anomalies: list[Anomaly],
    metrics: dict[str, Any],
) -> None:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.merge(
            RunRow(
                id=run.id,
                target_url=run.target_url,
                status=run.status.value,
                strategy=run.strategy,
                started_at=run.started_at or utcnow(),
                finished_at=run.finished_at,
                config_snapshot=run.config_snapshot,
                metrics=metrics,
            )
        )
        for state in model.states.values():
            session.merge(
                StateRow(
                    id=state.id,
                    run_id=run.id,
                    url=state.url,
                    title=state.title,
                    fingerprint_key=state.fingerprint.key,
                    visit_count=state.visit_count,
                )
            )
        for transition in model.transitions:
            session.merge(
                TransitionRow(
                    id=transition.id,
                    run_id=run.id,
                    from_state_id=transition.from_state_id,
                    to_state_id=transition.to_state_id,
                    action_id=transition.action_id,
                )
            )
        for anomaly in anomalies:
            session.merge(
                AnomalyRow(
                    id=anomaly.id,
                    run_id=run.id,
                    severity=anomaly.severity.value,
                    signals=anomaly.signals,
                    detail=anomaly.detail,
                )
            )
        session.commit()
