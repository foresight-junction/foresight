"""Kimi as a one-tick-per-call ED-72 player, via Verda Inference (OpenAI-compatible, stdlib only).

Request shape follows Verda's docs (docs.verda.com/inference): POST /v1/chat/completions with
`Authorization: Bearer <VERDA_INFERENCE_API_KEY>`, JSON mode via `response_format`, and
`reasoning_effort` (none|low|high|max; Kimi defaults to max, which can outrun the 60 s non-streaming
timeout, so we default to low). `max_tokens` covers reasoning plus the answer.
"""

import json

from gemini import Post, http_post, post_with_retries
from llm import LlmDecider

API = "https://inference.verda.com/v1/chat/completions"
DEFAULT_MODEL = "kimi-k3-1-pro"
MAX_TOKENS = 16000
TIMEOUT_S = 60  # Verda's non-streaming limit


def reply_text(response: dict) -> str:
    """The answer text of a chat completion; ValueError if reasoning used up max_tokens."""
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("empty reply (no choices)")
    content = (choices[0].get("message") or {}).get("content") or ""
    if not content.strip():
        raise ValueError(f"empty reply ({choices[0].get('finish_reason', 'no text')})")
    return content


class KimiDecider(LlmDecider):
    def __init__(
        self, model: str, api_key: str, reasoning_effort: str = "low", post: Post = http_post
    ) -> None:
        super().__init__()
        self.model = model
        self._api_key = api_key
        self._effort = reasoning_effort
        self._post = post

    def _reply_text(self, user_turn: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self._system},
                    {"role": "user", "content": user_turn},
                ],
                "max_tokens": MAX_TOKENS,
                "reasoning_effort": self._effort,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}
        return reply_text(json.loads(post_with_retries(API, headers, body, self._post, TIMEOUT_S)))
