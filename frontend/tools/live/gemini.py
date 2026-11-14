"""Gemini as a one-tick-per-call ED-72 player, over the REST generateContent API (stdlib only).

Request shape follows Google's generateContent docs: the API key in the `x-goog-api-key` header,
JSON output via `generationConfig.responseFormat.text` (mimeType + a JSON schema), and
`thinkingConfig.thinkingLevel` for Gemini 3 models.
"""

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable

API = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_S = 60
RETRIES = 2
BACKOFF_S = 2.0
# Ticks in a row with no usable reply before the agent gives up on the model.
MAX_FAILED_TICKS = 3
MAX_THOUGHT_CHARS = 400

BRIEF = """

---
You are playing this episode live, one tick per message. Each message gives you the current
observation (JSON), the actions the department rejected last tick with their reasons, and your last
few thoughts. Reply with JSON {"thought": ..., "actions": [...]}:
- thought: at most 50 words of plain English explaining the key decision this tick. Spectators read it.
- actions: the actions for this tick, applied in order (at most 50). Shapes, as in the step tool:
  {"type":"admit","patient":"P042","zone":"resus|acute|fast_track"},
  {"type":"assign","staff":"D3","to":"resus|acute|fast_track|rest"},
  {"type":"agency","role":"doctor|nurse"}, {"type":"repair"}, {"type":"divert"}.
  An empty list waits one tick.
"""

ZONES = ["resus", "acute", "fast_track"]
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["admit", "assign", "agency", "repair", "divert"]},
                    "patient": {"type": "string"},
                    "zone": {"type": "string", "enum": ZONES},
                    "staff": {"type": "string"},
                    "to": {"type": "string", "enum": [*ZONES, "rest"]},
                    "role": {"type": "string", "enum": ["doctor", "nurse"]},
                },
                "required": ["type"],
            },
        },
    },
    "required": ["thought", "actions"],
}
# The fields each action type uses; the flat schema lets the model fill others, which we drop.
ACTION_FIELDS = {
    "admit": ("patient", "zone"),
    "assign": ("staff", "to"),
    "agency": ("role",),
    "repair": (),
    "divert": (),
}

# (url, headers, body, timeout) -> (HTTP status, response body). Swapped out in tests.
Post = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


class GeminiFatal(Exception):
    """The model cannot be used for the rest of the episode (bad key or model, repeated failures)."""


class GeminiUnavailable(Exception):
    """One request failed after its retries; the next tick may work."""


def http_post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def _strip_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1) if match else text


def _clean_action(raw: object) -> dict | None:
    if not isinstance(raw, dict) or raw.get("type") not in ACTION_FIELDS:
        return None
    action = {"type": raw["type"]}
    for key in ACTION_FIELDS[raw["type"]]:
        if raw.get(key) not in (None, ""):
            action[key] = raw[key]
    return action


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
    try:
        reply = json.loads(_strip_fences(text))
    except json.JSONDecodeError as err:
        raise ValueError(f"unparseable JSON ({err.msg})") from err
    if not isinstance(reply, dict) or not isinstance(reply.get("actions"), list):
        raise ValueError("reply has no actions list")  # noqa: TRY004
    # Malformed entries go to the sim as-is so they come back as bad_action, visible to the model.
    actions = [_clean_action(a) or a for a in reply["actions"]]
    thought = reply.get("thought")
    thought = thought.strip()[:MAX_THOUGHT_CHARS] if isinstance(thought, str) else ""
    return actions, thought


class GeminiDecider:
    def __init__(self, model: str, api_key: str, thinking_level: str = "low", post: Post = http_post) -> None:
        self.model = model
        self._api_key = api_key
        self._thinking_level = thinking_level
        self._post = post
        self._system = BRIEF
        self._thoughts: list[str] = []
        self._failed_ticks = 0

    def start(self, handbook: str) -> None:
        self._system = handbook + BRIEF

    def decide(self, obs: dict, last_actions: list[dict], last_results: list[dict]) -> tuple[list[dict], str]:
        """One tick's (actions, thought). A bad reply gives ([], "(no decision: ...)")."""
        try:
            actions, thought = parse_reply(self._request(self._user_turn(obs, last_actions, last_results)))
        except (ValueError, GeminiUnavailable) as err:
            self._failed_ticks += 1
            if self._failed_ticks >= MAX_FAILED_TICKS:
                raise GeminiFatal(f"{MAX_FAILED_TICKS} ticks in a row without a decision: {err}") from err
            return [], f"(no decision: {err})"
        self._failed_ticks = 0
        self._thoughts = [*self._thoughts, thought][-3:]
        return actions, thought

    def _user_turn(self, obs: dict, last_actions: list[dict], last_results: list[dict]) -> str:
        rejected = [
            {
                "action": last_actions[r["index"]] if r["index"] < len(last_actions) else None,
                "reason": r["reason"],
            }
            for r in last_results
            if not r.get("ok")
        ]
        # last_rejected repeats `rejected` and misses actions past the 50-action cap.
        observation = {k: v for k, v in obs.items() if k != "last_rejected"}
        turn = {
            "observation": observation,
            "rejected_last_tick": rejected,
            "your_last_thoughts": self._thoughts,
        }
        return json.dumps(turn, separators=(",", ":"))

    def _request(self, user_turn: str) -> dict:
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
        problem = ""
        for attempt in range(RETRIES + 1):
            if attempt:
                time.sleep(BACKOFF_S * 2 ** (attempt - 1))
            try:
                status, raw = self._post(url, headers, body, TIMEOUT_S)
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                problem = f"network error: {err}"
                continue
            if status == 200:
                return json.loads(raw)
            problem = f"HTTP {status}: {_error_message(raw)}"
            if status != 429 and status < 500:
                raise GeminiFatal(problem)
        raise GeminiUnavailable(problem)


def _error_message(raw: bytes) -> str:
    try:
        return str(json.loads(raw)["error"]["message"])[:200]
    except (ValueError, KeyError, TypeError):
        return raw[:200].decode(errors="replace")
