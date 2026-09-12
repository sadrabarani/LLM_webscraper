"""Candidate action generation and exploration strategies."""

from __future__ import annotations

from collections import deque
from typing import Protocol
from urllib.parse import urljoin, urlparse

from webtester.domain.models import (
    Action,
    ActionType,
    Observation,
    ScopePolicy,
    ScoredAction,
)
from webtester.model.graph import BehaviouralModel


def generate_candidate_actions(
    observation: Observation,
    *,
    source_state_id: str,
    scope: ScopePolicy,
) -> list[Action]:
    actions: list[Action] = []
    base = observation.url
    for el in observation.interactive_elements:
        if not el.is_enabled or not el.is_visible:
            continue
        target = el.selector_candidates[0] if el.selector_candidates else el.tag
        params = {"selector_candidates": el.selector_candidates}
        if el.tag == "a" and el.href:
            abs_url = urljoin(base, el.href)
            host = urlparse(abs_url).hostname or ""
            if scope.allowed_domains and not any(
                host == d or host.endswith("." + d) for d in scope.allowed_domains
            ):
                continue
            if el.href.startswith("#"):
                continue
            actions.append(
                Action(
                    type=ActionType.CLICK,
                    target_ref=target,
                    element_id=el.element_id,
                    parameters=params,
                    source_state_id=source_state_id,
                    description=f"Click link {el.text or el.name or el.href}",
                )
            )
        elif el.tag in {"button"} or el.role == "button":
            actions.append(
                Action(
                    type=ActionType.CLICK,
                    target_ref=target,
                    element_id=el.element_id,
                    parameters=params,
                    source_state_id=source_state_id,
                    description=f"Click button {el.text or el.name}",
                )
            )
        elif el.tag == "input" and (el.input_type or "").lower() in {
            "text",
            "email",
            "search",
            "password",
            "",
        }:
            actions.append(
                Action(
                    type=ActionType.FILL,
                    target_ref=target,
                    element_id=el.element_id,
                    parameters={**params, "text": "test"},
                    source_state_id=source_state_id,
                    description=f"Fill input {el.name}",
                )
            )
        elif el.tag == "input" and (el.input_type or "").lower() == "submit":
            actions.append(
                Action(
                    type=ActionType.CLICK,
                    target_ref=target,
                    element_id=el.element_id,
                    parameters=params,
                    source_state_id=source_state_id,
                    description=f"Submit via {el.name or el.text}",
                )
            )
    return actions


class ExplorationStrategy(Protocol):
    name: str

    def propose(
        self,
        model: BehaviouralModel,
        observation: Observation,
        candidates: list[Action],
    ) -> list[ScoredAction]: ...


class BFSStrategy:
    name = "bfs"

    def __init__(self) -> None:
        self._queue: deque[str] = deque()

    def propose(
        self,
        model: BehaviouralModel,
        observation: Observation,
        candidates: list[Action],
    ) -> list[ScoredAction]:
        scored: list[ScoredAction] = []
        for idx, action in enumerate(candidates):
            if model.was_executed(action):
                continue
            # Prefer earlier (document-order) unvisited actions — BFS-ish frontier.
            score = 1000.0 - idx
            scored.append(ScoredAction(action=action, score=score, reason="bfs-order"))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored


class NoveltyStrategy:
    name = "novelty"

    def propose(
        self,
        model: BehaviouralModel,
        observation: Observation,
        candidates: list[Action],
    ) -> list[ScoredAction]:
        scored: list[ScoredAction] = []
        known_urls = {s.fingerprint.normalized_url for s in model.states.values()}
        for action in candidates:
            if model.was_executed(action):
                continue
            score = 1.0
            reason = "unvisited-action"
            if action.type == ActionType.CLICK:
                score += 2.0
                reason = "unvisited-click"
            # Prefer links that may lead to new paths
            href = ""
            for el in observation.interactive_elements:
                if el.element_id == action.element_id and el.href:
                    href = el.href
                    break
            if href and href not in {"#", "/"}:
                abs_guess = urljoin(observation.url, href)
                from webtester.observation.pipeline import normalize_url

                if normalize_url(abs_guess) not in known_urls:
                    score += 5.0
                    reason = "likely-new-state"
            if "error" in (action.description or "").lower():
                score += 3.0
                reason = "risk-signal"
            scored.append(ScoredAction(action=action, score=score, reason=reason))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored


def get_strategy(name: str) -> ExplorationStrategy:
    if name == "bfs":
        return BFSStrategy()
    if name == "novelty":
        return NoveltyStrategy()
    raise ValueError(f"Unknown strategy: {name}")
