"""What every LLM player shares: the brief added to the handbook, the reply schema, the per-tick user
turn and reply parsing. A provider module (gemini.py, kimi.py, claude.py) only sends one request.

Each tick is one stateless call: system = handbook + brief, user = this tick's observation, the
actions the department rejected last tick, and the model's last few thoughts.
"""

import json
import re

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
ACTION_SCHEMA = {
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
}
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "actions": {"type": "array", "items": ACTION_SCHEMA},
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


class ModelFatal(Exception):
    """The model cannot be used for the rest of the episode (bad key or model, repeated failures)."""


class ModelUnavailable(Exception):
    """One request failed after its retries; the next tick may work."""


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


def parse_text(text: str) -> tuple[list[dict], str]:
    """The (actions, thought) in a model's JSON reply text. Raises ValueError if there are none."""
    if not text.strip():
        raise ValueError("empty reply")
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


class LlmDecider:
    """One tick per call; a subclass implements `_reply_text`, the provider request."""

    def __init__(self) -> None:
        self._system = BRIEF
        self._thoughts: list[str] = []
        self._failed_ticks = 0

    def start(self, handbook: str) -> None:
        self._system = handbook + BRIEF

    def decide(self, obs: dict, last_actions: list[dict], last_results: list[dict]) -> tuple[list[dict], str]:
        """One tick's (actions, thought). A bad reply gives ([], "(no decision: ...)")."""
        try:
            actions, thought = parse_text(self._reply_text(self._user_turn(obs, last_actions, last_results)))
        except (ValueError, ModelUnavailable) as err:
            self._failed_ticks += 1
            if self._failed_ticks >= MAX_FAILED_TICKS:
                raise ModelFatal(f"{MAX_FAILED_TICKS} ticks in a row without a decision: {err}") from err
            return [], f"(no decision: {err})"
        self._failed_ticks = 0
        self._thoughts = [*self._thoughts, thought][-3:]
        return actions, thought

    def _reply_text(self, user_turn: str) -> str:
        raise NotImplementedError

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
