"""Deterministic observation processing and state fingerprints."""

from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment, Tag

from webtester.domain.models import (
    InteractiveElement,
    Observation,
    RawObservation,
    StateFingerprint,
)

_STRIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "template"}
_INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "option"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def simplify_dom(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in list(soup.find_all(_STRIP_TAGS)):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    body = soup.body or soup
    lines: list[str] = []
    for el in body.descendants:
        if not isinstance(el, Tag):
            continue
        if el.name not in _INTERACTIVE_TAGS and el.name not in {
            "h1",
            "h2",
            "h3",
            "label",
            "form",
            "main",
            "nav",
            "li",
            "p",
        }:
            continue
        attrs = []
        for key in ("id", "name", "type", "role", "aria-label", "href", "value"):
            if el.has_attr(key):
                attrs.append(f'{key}="{el.get(key)}"')
        text = " ".join(el.stripped_strings)
        text = re.sub(r"\s+", " ", text)[:120]
        attr_s = " ".join(attrs)
        lines.append(f"<{el.name} {attr_s}>{text}".strip())
    return "\n".join(lines)


def interactive_signature(elements: list[InteractiveElement]) -> str:
    parts = []
    for el in sorted(elements, key=lambda e: (e.tag, e.name, e.text, e.element_id)):
        parts.append(
            "|".join(
                [
                    el.tag,
                    el.role,
                    el.name,
                    el.text[:80],
                    el.attributes.get("type", ""),
                    el.href or "",
                ]
            )
        )
    return "\n".join(parts)


def form_values_signature(elements: list[InteractiveElement]) -> str:
    values = []
    for el in elements:
        if el.tag in {"input", "textarea", "select"}:
            values.append(
                f"{el.name or el.element_id}={el.attributes.get('value', '')}"
            )
    return "\n".join(sorted(values))


def compute_fingerprint(
    url: str,
    simplified_dom: str,
    elements: list[InteractiveElement],
) -> StateFingerprint:
    return StateFingerprint(
        normalized_url=normalize_url(url),
        simplified_dom_hash=_hash_text(simplified_dom),
        interactive_signature_hash=_hash_text(interactive_signature(elements)),
        form_values_hash=_hash_text(form_values_signature(elements)),
    )


def extract_interactive_from_html(html: str) -> list[InteractiveElement]:
    """Fallback extractor used in unit tests without a live browser."""
    soup = BeautifulSoup(html or "", "lxml")
    elements: list[InteractiveElement] = []
    idx = 0
    for tag in soup.find_all(["a", "button", "input", "select", "textarea"]):
        if not isinstance(tag, Tag):
            continue
        idx += 1
        text = " ".join(tag.stripped_strings)[:120]
        name = str(tag.get("name") or tag.get("aria-label") or tag.get("id") or text)
        href = tag.get("href")
        attrs = {
            k: str(v)
            for k, v in tag.attrs.items()
            if isinstance(v, str) or isinstance(v, int)
        }
        selectors = []
        if tag.get("id"):
            selectors.append(f"#{tag.get('id')}")
        if tag.get("name"):
            selectors.append(f"{tag.name}[name='{tag.get('name')}']")
        if href:
            selectors.append(f"a[href='{href}']")
        elements.append(
            InteractiveElement(
                element_id=f"el-{idx}",
                role=str(tag.get("role") or ""),
                tag=tag.name or "unknown",
                name=name,
                text=text,
                attributes={k: str(v) for k, v in attrs.items()},
                selector_candidates=selectors or [tag.name or "body"],
                href=str(href) if href else None,
                input_type=str(tag.get("type")) if tag.get("type") else None,
            )
        )
    return elements


def process_observation(raw: RawObservation) -> Observation:
    elements = raw.interactive_elements or extract_interactive_from_html(raw.html)
    simplified = simplify_dom(raw.html)
    fingerprint = compute_fingerprint(raw.url, simplified, elements)
    a11y = raw.accessibility_snapshot
    if len(a11y) > 4000:
        a11y = a11y[:4000] + "\n…[truncated]"
    return Observation(
        url=raw.url,
        title=raw.title,
        simplified_dom=simplified,
        accessibility_tree_summary=a11y,
        visible_text=raw.visible_text[:5000],
        interactive_elements=elements,
        console_events=list(raw.console_events),
        network_events=list(raw.network_events),
        navigation_events=list(raw.navigation_events),
        timing=raw.timing,
        previous_action_id=raw.previous_action_id,
        state_fingerprint=fingerprint,
    )


def compact_llm_context(observation: Observation, max_elements: int = 30) -> str:
    elems = observation.interactive_elements[:max_elements]
    payload = {
        "url": observation.url,
        "title": observation.title,
        "simplified_dom": observation.simplified_dom[:3000],
        "elements": [
            {
                "id": e.element_id,
                "tag": e.tag,
                "name": e.name,
                "text": e.text[:80],
                "href": e.href,
            }
            for e in elems
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
