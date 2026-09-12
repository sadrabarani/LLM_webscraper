from __future__ import annotations

from webtester.domain.models import InteractiveElement, RawObservation
from webtester.observation.pipeline import (
    compute_fingerprint,
    extract_interactive_from_html,
    normalize_url,
    process_observation,
    simplify_dom,
)


def test_normalize_url_strips_trailing_slash_and_sorts_query() -> None:
    assert (
        normalize_url("https://Example.com/path/?b=2&a=1")
        == "https://example.com/path?a=1&b=2"
    )


def test_simplify_dom_keeps_interactive_structure() -> None:
    html = """
    <html><body>
      <script>alert(1)</script>
      <h1>Title</h1>
      <a href="/about" id="a1">About</a>
      <button name="go">Go</button>
    </body></html>
    """
    simplified = simplify_dom(html)
    assert "script" not in simplified.lower() or "<script" not in simplified
    assert "About" in simplified
    assert "button" in simplified


def test_fingerprint_changes_when_interactive_set_changes() -> None:
    html1 = '<html><body><a href="/a">A</a></body></html>'
    html2 = '<html><body><a href="/a">A</a><a href="/b">B</a></body></html>'
    e1 = extract_interactive_from_html(html1)
    e2 = extract_interactive_from_html(html2)
    fp1 = compute_fingerprint("http://x/", simplify_dom(html1), e1)
    fp2 = compute_fingerprint("http://x/", simplify_dom(html2), e2)
    assert fp1.key != fp2.key


def test_fingerprint_stable_for_same_content() -> None:
    html = '<html><body><a href="/a" id="x">A</a></body></html>'
    els = extract_interactive_from_html(html)
    a = compute_fingerprint("http://x/a", simplify_dom(html), els)
    b = compute_fingerprint("http://x/a", simplify_dom(html), els)
    assert a.key == b.key


def test_process_observation_builds_observation() -> None:
    raw = RawObservation(
        url="http://example.com/",
        title="Home",
        html='<html><body><a href="/about">About</a></body></html>',
        interactive_elements=[
            InteractiveElement(
                element_id="el-1",
                tag="a",
                name="About",
                text="About",
                href="/about",
                selector_candidates=["#x", "a[href='/about']"],
            )
        ],
    )
    obs = process_observation(raw)
    assert obs.state_fingerprint.normalized_url.startswith("http://example.com")
    assert obs.interactive_elements
