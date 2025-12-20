from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import List, Sequence, Set
from urllib import error as url_error
from urllib import request as url_request


class LmStudioError(Exception):
    """Base error for LM Studio interactions."""


class LmStudioTimeoutError(LmStudioError):
    """Raised when LM Studio does not respond within the timeout window."""


class LmStudioInvalidResponseError(LmStudioError):
    """Raised when the LM response cannot be parsed into tags."""


class LmStudioService:
    """Encapsulates LM Studio requests and response parsing."""

    DEFAULT_ENDPOINT = "http://localhost:1234/v1/chat/completions"
    DEFAULT_MODEL = "gpt-4o-mini"
    TOKEN_PATTERN = re.compile(r"^[a-z0-9_\- ]+$")

    def __init__(self, endpoint: str | None = None, model: str | None = None, timeout_seconds: float = 15.0):
        self.endpoint = endpoint or os.getenv("LM_STUDIO_ENDPOINT", self.DEFAULT_ENDPOINT)
        self.model = model or os.getenv("LM_STUDIO_MODEL", self.DEFAULT_MODEL)
        self.timeout_seconds = timeout_seconds

    async def analyze_image(
        self,
        image_path: Path,
        current_tags: Sequence[str],
        *,
        exclusions: Sequence[str] | None = None,
    ) -> List[str]:
        payload = self._build_payload(image_path, current_tags)
        content = await asyncio.to_thread(self._send_payload, payload)
        text_output = self._extract_text_content(content)
        return self.parse_first_line_tags(text_output, exclusions=exclusions)

    def _send_payload(self, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = url_request.Request(
            self.endpoint, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with url_request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except url_error.URLError as exc:  # pragma: no cover - environment dependent
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                raise LmStudioTimeoutError("LM Studio request timed out") from exc
            raise LmStudioError(f"LM Studio request failed: {exc}") from exc
        except TimeoutError as exc:  # pragma: no cover - environment dependent
            raise LmStudioTimeoutError("LM Studio request timed out") from exc

        try:
            return json.loads(body.decode("utf-8"))
        except ValueError as exc:
            raise LmStudioInvalidResponseError("LM Studio returned non-JSON response") from exc

    def _build_payload(self, image_path: Path, current_tags: Sequence[str]) -> dict:
        image_bytes = image_path.read_bytes()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        current_tag_line = ", ".join([tag.strip() for tag in current_tags if tag.strip()])
        messages = [
            {
                "role": "system",
                "content": "You are an SDXL LoRA dataset tagger. Respond with a single comma-separated list of suggested tags on the first line. No commentary.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"CURRENT_TAGS: {current_tag_line}"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
                    },
                ],
            },
        ]
        return {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

    def _extract_text_content(self, payload: dict) -> str:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not choices:
            raise LmStudioInvalidResponseError("LM Studio response missing choices")
        first_choice = choices[0] or {}
        message = first_choice.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise LmStudioInvalidResponseError("LM Studio response missing text content")
        return content

    @classmethod
    def parse_first_line_tags(
        cls, output: str, *, exclusions: Sequence[str] | None = None
    ) -> List[str]:
        if not output or not output.strip():
            raise LmStudioInvalidResponseError("Empty response from LM Studio")

        exclusion_set: Set[str] = {
            tag.strip().lower() for tag in (exclusions or []) if str(tag).strip()
        }

        first_line = output.splitlines()[0]
        seen = set()
        tags: List[str] = []
        for token in first_line.split(","):
            cleaned = token.strip().lower()
            if not cleaned or cleaned in exclusion_set:
                continue
            if cleaned in seen:
                continue
            if not cls.TOKEN_PATTERN.match(cleaned):
                raise LmStudioInvalidResponseError(f"Invalid token: {cleaned}")
            seen.add(cleaned)
            tags.append(cleaned)

        if not tags:
            raise LmStudioInvalidResponseError("No valid tags returned from LM Studio")

        return tags

