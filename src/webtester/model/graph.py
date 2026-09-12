"""In-memory behavioural state graph for Phase 1."""

from __future__ import annotations

from webtester.domain.models import (
    Action,
    Observation,
    StateNode,
    Transition,
)


class BehaviouralModel:
    def __init__(self) -> None:
        self.states: dict[str, StateNode] = {}
        self.states_by_fingerprint: dict[str, str] = {}
        self.transitions: list[Transition] = []
        self.actions: list[Action] = []
        self.executed_action_keys: set[str] = set()

    def upsert_state(self, observation: Observation) -> StateNode:
        key = observation.state_fingerprint.key
        existing_id = self.states_by_fingerprint.get(key)
        if existing_id:
            node = self.states[existing_id]
            node.visit_count += 1
            return node
        node = StateNode(
            fingerprint=observation.state_fingerprint,
            label=observation.title or observation.url,
            url=observation.url,
            title=observation.title,
            interactive_element_ids=[e.element_id for e in observation.interactive_elements],
        )
        self.states[node.id] = node
        self.states_by_fingerprint[key] = node.id
        return node

    def record_action(self, action: Action) -> None:
        self.actions.append(action)
        self.executed_action_keys.add(self.action_key(action))

    def record_transition(
        self, *, from_state_id: str, to_state_id: str, action_id: str
    ) -> Transition:
        transition = Transition(
            from_state_id=from_state_id,
            to_state_id=to_state_id,
            action_id=action_id,
        )
        self.transitions.append(transition)
        return transition

    @staticmethod
    def action_key(action: Action) -> str:
        return f"{action.type}:{action.target_ref}:{action.parameters.get('url', '')}"

    def was_executed(self, action: Action) -> bool:
        return self.action_key(action) in self.executed_action_keys

    def summary(self) -> dict[str, int]:
        return {
            "states": len(self.states),
            "transitions": len(self.transitions),
            "actions": len(self.actions),
        }
