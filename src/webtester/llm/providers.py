"""LLM provider ports and free-tier adapters."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Protocol

import httpx

from webtester.domain.models import LLMCallRecord, ScoredAction


class LLMRequest:
    def __init__(
        self,
        *,
        purpose: str,
        prompt: str,
        response_schema: dict[str, Any] | None = None,
        max_tokens: int = 512,
        temperature: float = 0.1,
        cache_key_parts: list[str] | None = None,
    ) -> None:
        self.purpose = purpose
        self.prompt = prompt
        self.response_schema = response_schema
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.cache_key_parts = cache_key_parts or []


class LLMResponse:
    def __init__(
        self,
        *,
        text: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
        cache_hit: bool = False,
        raw: dict[str, Any] | None = None,
    ) -> None:
        self.text = text
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.cache_hit = cache_hit
        self.raw = raw or {}


class LLMProvider(Protocol):
    name: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


class LLMCache:
    def __init__(self) -> None:
        self._store: dict[str, LLMResponse] = {}

    @staticmethod
    def key(provider: str, model: str, parts: list[str], prompt: str) -> str:
        blob = "|".join([provider, model, *parts, prompt])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, key: str) -> LLMResponse | None:
        return self._store.get(key)

    def put(self, key: str, response: LLMResponse) -> None:
        self._store[key] = response


class NullLLMProvider:
    name = "none"

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("LLM provider disabled")


class OpenAICompatibleProvider:
    """Works for Groq and OpenRouter free endpoints."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        cache: LLMCache | None = None,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.cache = cache or LLMCache()

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError(f"{self.name} API key missing")
        cache_key = LLMCache.key(
            self.name, self.model, request.cache_key_parts, request.prompt
        )
        cached = self.cache.get(cache_key)
        if cached:
            return LLMResponse(
                text=cached.text,
                provider=self.name,
                model=self.model,
                input_tokens=cached.input_tokens,
                output_tokens=cached.output_tokens,
                latency_ms=0.0,
                cache_hit=True,
                raw=cached.raw,
            )

        started = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=body
            )
            if resp.status_code == 429:
                raise RuntimeError(f"{self.name} rate limited (429)")
            resp.raise_for_status()
            data = resp.json()
        latency = (time.perf_counter() - started) * 1000
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        result = LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency,
            cache_hit=False,
            raw=data,
        )
        self.cache.put(cache_key, result)
        return result


class GeminiProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        cache: LLMCache | None = None,
    ) -> None:
        self.name = "gemini"
        self.api_key = api_key
        self.model = model
        self.cache = cache or LLMCache()

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("Gemini API key missing")
        cache_key = LLMCache.key(
            self.name, self.model, request.cache_key_parts, request.prompt
        )
        cached = self.cache.get(cache_key)
        if cached:
            return LLMResponse(
                text=cached.text,
                provider=self.name,
                model=self.model,
                input_tokens=cached.input_tokens,
                output_tokens=cached.output_tokens,
                latency_ms=0.0,
                cache_hit=True,
                raw=cached.raw,
            )

        started = time.perf_counter()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        body = {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, params={"key": self.api_key}, json=body)
            if resp.status_code == 429:
                raise RuntimeError("Gemini rate limited (429)")
            resp.raise_for_status()
            data = resp.json()
        latency = (time.perf_counter() - started) * 1000
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata") or {}
        result = LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0),
            latency_ms=latency,
            cache_hit=False,
            raw=data,
        )
        self.cache.put(cache_key, result)
        return result


def build_provider(
    name: str,
    *,
    groq_api_key: str = "",
    groq_model: str = "llama-3.1-8b-instant",
    google_api_key: str = "",
    gemini_model: str = "gemini-2.0-flash-lite",
    openrouter_api_key: str = "",
    openrouter_model: str = "openrouter/auto:free",
    cache: LLMCache | None = None,
) -> LLMProvider:
    cache = cache or LLMCache()
    if name == "none":
        return NullLLMProvider()
    if name == "groq":
        return OpenAICompatibleProvider(
            name="groq",
            api_key=groq_api_key,
            model=groq_model,
            base_url="https://api.groq.com/openai/v1",
            cache=cache,
        )
    if name == "gemini":
        return GeminiProvider(api_key=google_api_key, model=gemini_model, cache=cache)
    if name == "openrouter":
        return OpenAICompatibleProvider(
            name="openrouter",
            api_key=openrouter_api_key,
            model=openrouter_model,
            base_url="https://openrouter.ai/api/v1",
            cache=cache,
        )
    raise ValueError(f"Unknown LLM provider: {name}")


def prioritize_actions_with_llm(
    provider: LLMProvider,
    *,
    context: str,
    scored: list[ScoredAction],
    run_id: str | None = None,
) -> tuple[list[ScoredAction], LLMCallRecord | None]:
    if not scored:
        return scored, None
    catalog = [
        {
            "index": i,
            "type": s.action.type,
            "description": s.action.description,
            "element_id": s.action.element_id,
            "deterministic_score": s.score,
        }
        for i, s in enumerate(scored[:20])
    ]
    prompt = (
        "You are assisting a black-box web testing agent.\n"
        "Pick the best next action index to explore website functionality.\n"
        "Reply with JSON only: {\"index\": <int>, \"reason\": \"...\"}\n\n"
        f"PAGE_CONTEXT:\n{context}\n\nACTIONS:\n{json.dumps(catalog)}\n"
    )
    request = LLMRequest(
        purpose="action_prioritize",
        prompt=prompt,
        cache_key_parts=[context[:200], str(len(catalog))],
    )
    try:
        response = provider.complete(request)
    except Exception as exc:  # noqa: BLE001
        record = LLMCallRecord(
            run_id=run_id,
            provider=getattr(provider, "name", "unknown"),
            model=getattr(provider, "model", ""),
            purpose="action_prioritize",
            status="error",
            error=str(exc),
        )
        return scored, record

    record = LLMCallRecord(
        run_id=run_id,
        provider=response.provider,
        model=response.model,
        purpose="action_prioritize",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        latency_ms=response.latency_ms,
        cache_hit=response.cache_hit,
        status="ok",
    )
    try:
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        idx = int(data["index"])
        reason = str(data.get("reason", "llm"))
        if 0 <= idx < len(scored):
            chosen = scored[idx]
            boosted = ScoredAction(
                action=chosen.action,
                score=chosen.score + 100.0,
                reason=f"llm:{reason}",
            )
            rest = [s for i, s in enumerate(scored) if i != idx]
            return [boosted, *rest], record
    except Exception:  # noqa: BLE001
        record.status = "parse_error"
    return scored, record
