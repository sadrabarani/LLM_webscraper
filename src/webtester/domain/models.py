"""Domain layer: entities and value objects with no infrastructure imports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ActionType(StrEnum):
    CLICK = "click"
    TYPE = "type"
    FILL = "fill"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    SUBMIT = "submit"
    NAVIGATE = "navigate"
    BACK = "back"
    FORWARD = "forward"
    REFRESH = "refresh"
    SCROLL = "scroll"
    HOVER = "hover"
    KEYBOARD = "keyboard"
    WAIT = "wait"
    UPLOAD = "upload"
    OPEN_DIALOG = "open_dialog"


class ActionResultStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    TIMEOUT = "timeout"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScopePolicy(BaseModel):
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    max_actions: int = 20
    max_runtime_seconds: int = 300
    max_llm_calls: int = 20
    max_depth: int | None = None
    allow_downloads: bool = False
    allow_file_upload: bool = False
    dangerous_action_deny_list: list[ActionType] = Field(
        default_factory=lambda: [ActionType.UPLOAD]
    )
    require_explicit_authorization: bool = True
    authorized: bool = False


class Budget(BaseModel):
    actions_remaining: int
    runtime_deadline: datetime
    llm_calls_remaining: int
    tokens_remaining_estimate: int | None = None

    def can_act(self) -> bool:
        return self.actions_remaining > 0 and utcnow() < self.runtime_deadline

    def can_call_llm(self) -> bool:
        return self.llm_calls_remaining > 0 and utcnow() < self.runtime_deadline

    def consume_action(self) -> None:
        self.actions_remaining = max(0, self.actions_remaining - 1)

    def consume_llm(self) -> None:
        self.llm_calls_remaining = max(0, self.llm_calls_remaining - 1)


class InteractiveElement(BaseModel):
    element_id: str
    role: str = ""
    tag: str
    name: str = ""
    text: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    selector_candidates: list[str] = Field(default_factory=list)
    is_visible: bool = True
    is_enabled: bool = True
    href: str | None = None
    input_type: str | None = None


class ConsoleEvent(BaseModel):
    level: str
    text: str
    location: str = ""
    timestamp: datetime = Field(default_factory=utcnow)


class NetworkEvent(BaseModel):
    url: str
    method: str = "GET"
    status: int | None = None
    resource_type: str = ""
    timing_ms: float | None = None
    failed: bool = False
    failure_text: str = ""


class NavigationEvent(BaseModel):
    url: str
    status: int | None = None
    ok: bool = True
    error: str = ""


class PageTiming(BaseModel):
    load_ms: float | None = None
    dom_content_loaded_ms: float | None = None


class StateFingerprint(BaseModel):
    normalized_url: str
    simplified_dom_hash: str
    interactive_signature_hash: str
    form_values_hash: str

    @property
    def key(self) -> str:
        return "|".join(
            [
                self.normalized_url,
                self.simplified_dom_hash,
                self.interactive_signature_hash,
                self.form_values_hash,
            ]
        )


class Action(BaseModel):
    id: str = Field(default_factory=new_id)
    type: ActionType
    target_ref: str = ""
    element_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    source_state_id: str | None = None
    result_state_id: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    execution_result: ActionResultStatus | None = None
    error: str | None = None
    description: str = ""


class ScoredAction(BaseModel):
    action: Action
    score: float
    reason: str = ""


class ActionResult(BaseModel):
    status: ActionResultStatus
    error: str | None = None
    navigation: NavigationEvent | None = None


class RawObservation(BaseModel):
    """Browser-captured observation before pipeline processing."""

    url: str
    title: str = ""
    html: str = ""
    accessibility_snapshot: str = ""
    visible_text: str = ""
    interactive_elements: list[InteractiveElement] = Field(default_factory=list)
    console_events: list[ConsoleEvent] = Field(default_factory=list)
    network_events: list[NetworkEvent] = Field(default_factory=list)
    navigation_events: list[NavigationEvent] = Field(default_factory=list)
    timing: PageTiming = Field(default_factory=PageTiming)
    screenshot_png: bytes | None = None
    previous_action_id: str | None = None


class Observation(BaseModel):
    id: str = Field(default_factory=new_id)
    url: str
    title: str = ""
    simplified_dom: str = ""
    accessibility_tree_summary: str = ""
    visible_text: str = ""
    interactive_elements: list[InteractiveElement] = Field(default_factory=list)
    console_events: list[ConsoleEvent] = Field(default_factory=list)
    network_events: list[NetworkEvent] = Field(default_factory=list)
    navigation_events: list[NavigationEvent] = Field(default_factory=list)
    timing: PageTiming = Field(default_factory=PageTiming)
    previous_action_id: str | None = None
    state_fingerprint: StateFingerprint
    screenshot_ref: str | None = None
    raw_html_ref: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)


class StateNode(BaseModel):
    id: str = Field(default_factory=new_id)
    fingerprint: StateFingerprint
    label: str = ""
    url: str = ""
    title: str = ""
    first_seen_at: datetime = Field(default_factory=utcnow)
    visit_count: int = 1
    interactive_element_ids: list[str] = Field(default_factory=list)


class Transition(BaseModel):
    id: str = Field(default_factory=new_id)
    from_state_id: str
    to_state_id: str
    action_id: str
    observed_at: datetime = Field(default_factory=utcnow)


class Anomaly(BaseModel):
    id: str = Field(default_factory=new_id)
    signals: list[str] = Field(default_factory=list)
    severity: AnomalySeverity = AnomalySeverity.MEDIUM
    related_state_id: str | None = None
    related_action_id: str | None = None
    detail: str = ""
    timestamp: datetime = Field(default_factory=utcnow)


class ExplorationRun(BaseModel):
    id: str = Field(default_factory=new_id)
    target_url: str
    status: RunStatus = RunStatus.PENDING
    strategy: str = "novelty"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    config_snapshot: dict[str, Any] = Field(default_factory=dict)


class LLMCallRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    run_id: str | None = None
    provider: str
    model: str
    purpose: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cache_hit: bool = False
    status: str = "ok"
    error: str | None = None
    estimated_cost: float = 0.0
