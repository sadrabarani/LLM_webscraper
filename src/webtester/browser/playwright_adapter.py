"""Playwright-backed browser controller."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from webtester.domain.models import (
    Action,
    ActionResult,
    ActionResultStatus,
    ActionType,
    ConsoleEvent,
    InteractiveElement,
    NavigationEvent,
    NetworkEvent,
    PageTiming,
    RawObservation,
    ScopePolicy,
)


class ScopeViolationError(RuntimeError):
    pass


class PlaywrightBrowserController:
    def __init__(self, scope: ScopePolicy) -> None:
        self._scope = scope
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._console: list[ConsoleEvent] = []
        self._network: list[NetworkEvent] = []
        self._navigation: list[NavigationEvent] = []
        self._previous_action_id: str | None = None

    def start(self, *, headless: bool = True) -> None:
        self._pw = sync_playwright().start()
        self._browser = self._launch_browser(headless=headless)
        context = self._browser.new_context(ignore_https_errors=True)
        self._page = context.new_page()
        self._page.on("console", self._on_console)
        self._page.on("requestfailed", self._on_request_failed)
        self._page.on("response", self._on_response)

    def _launch_browser(self, *, headless: bool) -> Browser:
        assert self._pw is not None
        # Prefer bundled Chromium; fall back to system browsers when CDN is blocked.
        launchers = [
            lambda: self._pw.chromium.launch(headless=headless),
            lambda: self._pw.chromium.launch(headless=headless, channel="msedge"),
            lambda: self._pw.chromium.launch(headless=headless, channel="chrome"),
        ]
        errors: list[str] = []
        for launch in launchers:
            try:
                return launch()
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        raise RuntimeError(
            "Could not launch a browser. Install Playwright Chromium "
            "(`playwright install chromium`) or install Chrome/Edge. "
            f"Errors: {' | '.join(errors)}"
        )

    def stop(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()
        self._browser = None
        self._pw = None
        self._page = None

    def current_url(self) -> str:
        return self._require_page().url

    def navigate(self, url: str) -> ActionResult:
        self._assert_allowed(url)
        page = self._require_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status = response.status if response else None
            ok = bool(response.ok) if response else True
            self._navigation.append(
                NavigationEvent(url=page.url, status=status, ok=ok)
            )
            if status is not None and status >= 500:
                return ActionResult(
                    status=ActionResultStatus.FAILED,
                    error=f"HTTP {status}",
                    navigation=self._navigation[-1],
                )
            return ActionResult(
                status=ActionResultStatus.OK,
                navigation=self._navigation[-1],
            )
        except Exception as exc:  # noqa: BLE001
            nav = NavigationEvent(url=url, ok=False, error=str(exc))
            self._navigation.append(nav)
            return ActionResult(
                status=ActionResultStatus.FAILED,
                error=str(exc),
                navigation=nav,
            )

    def observe(self) -> RawObservation:
        page = self._require_page()
        html = page.content()
        title = page.title()
        visible_text = page.inner_text("body") if page.locator("body").count() else ""
        a11y = ""
        try:
            a11y = page.locator("body").aria_snapshot()
        except Exception:  # noqa: BLE001
            a11y = ""
        elements = self._extract_interactive(page)
        screenshot = page.screenshot(full_page=False, type="png")
        timing = PageTiming()
        obs = RawObservation(
            url=page.url,
            title=title,
            html=html,
            accessibility_snapshot=a11y,
            visible_text=visible_text,
            interactive_elements=elements,
            console_events=list(self._console),
            network_events=list(self._network),
            navigation_events=list(self._navigation),
            timing=timing,
            screenshot_png=screenshot,
            previous_action_id=self._previous_action_id,
        )
        # Keep recent console/network only for next observe deltas feel fresher
        self._console.clear()
        self._network.clear()
        return obs

    def screenshot(self) -> bytes:
        return self._require_page().screenshot(full_page=False, type="png")

    def execute(self, action: Action) -> ActionResult:
        if action.type in self._scope.dangerous_action_deny_list:
            return ActionResult(
                status=ActionResultStatus.FAILED,
                error=f"Action {action.type} denied by scope policy",
            )
        page = self._require_page()
        self._previous_action_id = action.id
        try:
            if action.type == ActionType.NAVIGATE:
                url = str(action.parameters.get("url", ""))
                return self.navigate(url)
            if action.type == ActionType.BACK:
                page.go_back(wait_until="domcontentloaded")
                self._assert_allowed(page.url)
                return ActionResult(status=ActionResultStatus.OK)
            if action.type == ActionType.FORWARD:
                page.go_forward(wait_until="domcontentloaded")
                self._assert_allowed(page.url)
                return ActionResult(status=ActionResultStatus.OK)
            if action.type == ActionType.REFRESH:
                page.reload(wait_until="domcontentloaded")
                return ActionResult(status=ActionResultStatus.OK)
            if action.type == ActionType.WAIT:
                page.wait_for_timeout(int(action.parameters.get("ms", 500)))
                return ActionResult(status=ActionResultStatus.OK)
            if action.type == ActionType.SCROLL:
                page.mouse.wheel(0, int(action.parameters.get("dy", 600)))
                return ActionResult(status=ActionResultStatus.OK)

            locator = self._resolve_locator(page, action)
            if action.type == ActionType.CLICK:
                locator.click(timeout=5000)
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            elif action.type in {ActionType.TYPE, ActionType.FILL}:
                text = str(action.parameters.get("text", "test"))
                locator.fill(text, timeout=5000)
            elif action.type == ActionType.CHECK:
                locator.check(timeout=5000)
            elif action.type == ActionType.UNCHECK:
                locator.uncheck(timeout=5000)
            elif action.type == ActionType.SELECT:
                value = str(action.parameters.get("value", ""))
                locator.select_option(value, timeout=5000)
            elif action.type == ActionType.HOVER:
                locator.hover(timeout=5000)
            elif action.type == ActionType.SUBMIT:
                locator.press("Enter", timeout=5000)
            else:
                return ActionResult(
                    status=ActionResultStatus.FAILED,
                    error=f"Unsupported action type: {action.type}",
                )

            self._assert_allowed(page.url)
            return ActionResult(status=ActionResultStatus.OK)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if action.type == ActionType.CLICK and "Timeout" in msg:
                # Navigation/load wait timed out after a successful click.
                try:
                    self._assert_allowed(page.url)
                    return ActionResult(status=ActionResultStatus.OK)
                except ScopeViolationError:
                    return ActionResult(status=ActionResultStatus.FAILED, error=msg)
            return ActionResult(status=ActionResultStatus.FAILED, error=msg)

    def _resolve_locator(self, page: Page, action: Action) -> Any:
        selectors = []
        if action.target_ref:
            selectors.append(action.target_ref)
        for sel in action.parameters.get("selector_candidates", []):
            if isinstance(sel, str):
                selectors.append(sel)
        last_error: Exception | None = None
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    return loc
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise RuntimeError(
            f"Could not resolve locator for action {action.id}: {last_error}"
        )

    def _extract_interactive(self, page: Page) -> list[InteractiveElement]:
        script = """
        () => {
          const nodes = Array.from(document.querySelectorAll(
            'a[href], button, input, select, textarea, [role="button"]'
          ));
          return nodes.slice(0, 80).map((el, i) => {
            const style = window.getComputedStyle(el);
            const visible = style && style.visibility !== 'hidden'
              && style.display !== 'none'
              && el.offsetParent !== null;
            const rect = el.getBoundingClientRect();
            const text = (el.innerText || el.value || '').trim().slice(0, 120);
            const name = el.getAttribute('aria-label')
              || el.getAttribute('name')
              || el.getAttribute('id')
              || text
              || el.tagName.toLowerCase();
            const attrs = {};
            for (const a of el.attributes) {
              if (['id','name','type','role','aria-label','href','value','placeholder'].includes(a.name)) {
                attrs[a.name] = a.value;
              }
            }
            const selectors = [];
            if (el.id) selectors.push('#' + CSS.escape(el.id));
            if (el.getAttribute('name')) {
              selectors.push(el.tagName.toLowerCase() + "[name='" + el.getAttribute('name') + "']");
            }
            if (el.tagName.toLowerCase() === 'a' && el.getAttribute('href')) {
              selectors.push("a[href='" + el.getAttribute('href') + "']");
            }
            selectors.push(el.tagName.toLowerCase());
            return {
              element_id: 'el-' + (i + 1),
              role: el.getAttribute('role') || '',
              tag: el.tagName.toLowerCase(),
              name,
              text,
              attributes: attrs,
              selector_candidates: selectors,
              is_visible: Boolean(visible && rect.width >= 0 && rect.height >= 0),
              is_enabled: !el.disabled,
              href: el.getAttribute('href'),
              input_type: el.getAttribute('type'),
            };
          });
        }
        """
        raw_items = page.evaluate(script)
        elements: list[InteractiveElement] = []
        for item in raw_items:
            if not item.get("is_visible", True):
                continue
            elements.append(InteractiveElement.model_validate(item))
        return elements

    def _on_console(self, msg: Any) -> None:
        self._console.append(
            ConsoleEvent(
                level=msg.type,
                text=msg.text,
                location=str(msg.location) if msg.location else "",
            )
        )

    def _on_request_failed(self, request: Any) -> None:
        failure = request.failure
        self._network.append(
            NetworkEvent(
                url=request.url,
                method=request.method,
                resource_type=request.resource_type,
                failed=True,
                failure_text=failure or "",
            )
        )

    def _on_response(self, response: Any) -> None:
        status = response.status
        if status >= 400:
            self._network.append(
                NetworkEvent(
                    url=response.url,
                    method=response.request.method,
                    status=status,
                    resource_type=response.request.resource_type,
                    failed=status >= 500,
                )
            )

    def _assert_allowed(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        if any(self._domain_match(host, d) for d in self._scope.blocked_domains):
            raise ScopeViolationError(f"Blocked domain: {host}")
        if self._scope.allowed_domains:
            if not any(self._domain_match(host, d) for d in self._scope.allowed_domains):
                raise ScopeViolationError(
                    f"Domain {host} not in allowed_domains {self._scope.allowed_domains}"
                )

    @staticmethod
    def _domain_match(host: str, pattern: str) -> bool:
        host = host.lower()
        pattern = pattern.lower()
        return host == pattern or host.endswith("." + pattern)

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not started")
        return self._page


def resolve_url(base: str, href: str) -> str:
    return urljoin(base, href)
