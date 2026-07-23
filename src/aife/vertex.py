"""Vertex AI client wrapper with rate limiting, retries, and JSON recovery."""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from aife.config import Settings

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_RETRY_DELAYS = (5.0, 3.0, 1.0)


class RateLimiter:
    """Serializes calls so the aggregate request rate stays under a ceiling."""

    def __init__(self, requests_per_minute: int) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self._delay = 60.0 / requests_per_minute
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            wait = self._delay - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


def parse_json_array(text: str) -> list[Any] | None:
    """Parse a JSON array, tolerating markdown fences and leading prose."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_ARRAY.search(text.replace("```json", "").replace("```", ""))
        if match is None:
            return None
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, list) else None


class TeacherClient:
    """Deterministic batch inference against a Vertex AI generative model.

    Safety filters are disabled because domain vocabulary ("kill process",
    "master/slave architecture") otherwise triggers false positives on
    ordinary technical job descriptions.
    """

    def __init__(self, settings: Settings, limiter: RateLimiter | None = None) -> None:
        import vertexai
        from vertexai.generative_models import (
            GenerationConfig,
            GenerativeModel,
            SafetySetting,
        )

        vertexai.init(project=settings.project_id, location=settings.location)

        self._model = GenerativeModel(settings.model_id)
        self._limiter = limiter or RateLimiter(settings.max_rpm)
        self._generation_config = GenerationConfig(
            temperature=0.0,
            top_k=1,
            response_mime_type="application/json",
        )
        self._safety_settings = [
            SafetySetting(
                category=category,
                threshold=SafetySetting.HarmBlockThreshold.BLOCK_NONE,
            )
            for category in (
                SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
            )
        ]

    async def complete_json(self, prompt: str) -> list[Any] | None:
        """Run one prompt and return the parsed JSON array, or None on failure."""
        from google.api_core.exceptions import (
            InternalServerError,
            ResourceExhausted,
            ServiceUnavailable,
        )

        for delay in _RETRY_DELAYS:
            await self._limiter.acquire()
            try:
                response = await self._model.generate_content_async(
                    prompt,
                    generation_config=self._generation_config,
                    safety_settings=self._safety_settings,
                )
            except ResourceExhausted:
                await asyncio.sleep(delay)
                continue
            except (ServiceUnavailable, InternalServerError):
                await asyncio.sleep(delay)
                continue
            return parse_json_array(response.text)

        return None
