from __future__ import annotations

from webtester.domain.models import (
    Action,
    ActionType,
    InteractiveElement,
    Observation,
    ScopePolicy,
    StateFingerprint,
)
from webtester.exploration.strategies import (
    BFSStrategy,
    NoveltyStrategy,
    generate_candidate_actions,
)
from webtester.model.graph import BehaviouralModel


def _obs(url: str = "http://example.com/") -> Observation:
    return Observation(
        url=url,
        title="Home",
        simplified_dom="<a>About</a>",
        interactive_elements=[
            InteractiveElement(
                element_id="el-1",
                tag="a",
                name="About",
                text="About",
                href="/about",
                selector_candidates=["a[href='/about']"],
            ),
            InteractiveElement(
                element_id="el-2",
                tag="a",
                name="Buggy",
                text="Buggy Page",
                href="/buggy",
                selector_candidates=["a[href='/buggy']"],
            ),
            InteractiveElement(
                element_id="el-3",
                tag="button",
                name="Save",
                text="Save",
                selector_candidates=["button"],
            ),
        ],
        state_fingerprint=StateFingerprint(
            normalized_url=url,
            simplified_dom_hash="a",
            interactive_signature_hash="b",
            form_values_hash="c",
        ),
    )


def test_generate_candidate_actions_respects_scope() -> None:
    scope = ScopePolicy(allowed_domains=["example.com"], authorized=True)
    actions = generate_candidate_actions(_obs(), source_state_id="s1", scope=scope)
    assert actions
    assert all(a.type in {ActionType.CLICK, ActionType.FILL} for a in actions)


def test_bfs_prefers_document_order() -> None:
    model = BehaviouralModel()
    obs = _obs()
    scope = ScopePolicy(allowed_domains=["example.com"], authorized=True)
    candidates = generate_candidate_actions(obs, source_state_id="s1", scope=scope)
    scored = BFSStrategy().propose(model, obs, candidates)
    assert scored
    assert scored[0].action.element_id == candidates[0].element_id


def test_novelty_boosts_unvisited_and_skips_executed() -> None:
    model = BehaviouralModel()
    obs = _obs()
    scope = ScopePolicy(allowed_domains=["example.com"], authorized=True)
    candidates = generate_candidate_actions(obs, source_state_id="s1", scope=scope)
    first = candidates[0]
    model.record_action(first)
    scored = NoveltyStrategy().propose(model, obs, candidates)
    assert all(model.action_key(s.action) != model.action_key(first) for s in scored)
    assert scored[0].score >= scored[-1].score


def test_action_model_defaults() -> None:
    action = Action(type=ActionType.CLICK, target_ref="#x", description="click")
    assert action.id
    assert action.execution_result is None
