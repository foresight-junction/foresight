"""Gemini as a one-tick-per-call ED-72 player, over the REST generateContent API (stdlib only).

Request shape follows Google's generateContent docs: the API key in the `x-goog-api-key` header,
JSON output via `generationConfig.responseFormat.text` (mimeType + a JSON schema), and
`thinkingConfig.thinkingLevel` for Gemini 3 models. Prompt and parsing are shared (llm.py).
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from llm import RESPONSE_SCHEMA, LlmDecider, ModelFatal, ModelUnavailable, parse_text

API = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_S = 60
RETRIES = 2
BACKOFF_S = 2.0

# Kept for callers that predate the shared module.
GeminiFatal = ModelFatal
GeminiUnavailable = ModelUnavailable

# (url, headers, body, timeout) -> (HTTP status, response body). Swapped out in tests.
Post = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def http_post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def post_with_retries(
    url: str, headers: dict[str, str], body: bytes, post: Post, timeout: float = TIMEOUT_S
) -> bytes:
    """The 200 response body. 429/5xx/network errors retry with backoff, then ModelUnavailable;
    any other HTTP error is ModelFatal (bad key, model or request)."""
    problem = ""
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(BACKOFF_S * 2 ** (attempt - 1))
        try:
            status, raw = post(url, headers, body, timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            problem = f"network error: {err}"
            continue
        if status == 200:
            return raw
        problem = f"HTTP {status}: {error_message(raw)}"
        if status != 429 and status < 500:
            raise ModelFatal(problem)
    raise ModelUnavailable(problem)


def error_message(raw: bytes) -> str:
    try:
        return str(json.loads(raw)["error"]["message"])[:200]
    except (ValueError, KeyError, TypeError):
        return raw[:200].decode(errors="replace")


def parse_reply(response: dict) -> tuple[list[dict], str]:
    """The (actions, thought) in a generateContent response. Raises ValueError if there are none."""
    candidates = response.get("candidates") or []
    if not candidates:
        reason = (response.get("promptFeedback") or {}).get("blockReason", "no candidates")
        raise ValueError(f"empty reply ({reason})")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))
    if not text.strip():
        raise ValueError(f"empty reply ({candidates[0].get('finishReason', 'no text')})")
    return parse_text(text)


class GeminiDecider(LlmDecider):
    def __init__(self, model: str, api_key: str, thinking_level: str = "low", post: Post = http_post) -> None:
        super().__init__()
        self.model = model
        self._api_key = api_key
        self._thinking_level = thinking_level
        self._post = post

    def _reply_text(self, user_turn: str) -> str:
        response = json.loads(self._request(user_turn))
        actions, thought = parse_reply(response)
        # Hand the cleaned reply back as text, so the shared decide() parses one format for all models.
        return json.dumps({"thought": thought, "actions": actions})

    def _request(self, user_turn: str) -> bytes:
        body = json.dumps(
            {
                "systemInstruction": {"parts": [{"text": self._system}]},
                "contents": [{"role": "user", "parts": [{"text": user_turn}]}],
                "generationConfig": {
                    "responseFormat": {"text": {"mimeType": "APPLICATION_JSON", "schema": RESPONSE_SCHEMA}},
                    "thinkingConfig": {"thinkingLevel": self._thinking_level},
                },
            }
        ).encode()
        url = f"{API}/{self.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._api_key}
        return post_with_retries(url, headers, body, self._post)
