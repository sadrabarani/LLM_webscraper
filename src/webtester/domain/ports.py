"""Ports (protocols) used by the domain and application layers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from webtester.domain.models import Action, ActionResult, RawObservation


@runtime_checkable
class BrowserController(Protocol):
    def start(self, *, headless: bool = True) -> None: ...

    def navigate(self, url: str) -> ActionResult: ...

    def observe(self) -> RawObservation: ...

    def execute(self, action: Action) -> ActionResult: ...

    def screenshot(self) -> bytes: ...

    def current_url(self) -> str: ...

    def stop(self) -> None: ...
