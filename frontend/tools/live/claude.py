"""Claude as a one-tick-per-call ED-72 player, through the official `anthropic` Python SDK.

- Structured outputs (`output_config.format`, a JSON schema) guarantee the reply is {thought, actions}.
- The system prompt (handbook + brief) is identical every tick, so it carries `cache_control`: after
  the first tick it is read from the prompt cache.
- Thinking is adaptive and always on for Claude Opus 5.5; `effort` sets its depth (default `medium`,
  set explicitly). `fallbacks: "default"` lets the API re-run a declined request on Anthropic's
  recommended fallback model instead of returning a refusal.
- The SDK retries 408/409/429/5xx and connection errors (max_retries); after that a tick is skipped.
"""

import copy
import os

import anthropic
from llm import RESPONSE_SCHEMA, LlmDecider, ModelFatal, ModelUnavailable

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
TIMEOUT_S = 180.0
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _strict(schema: dict) -> dict:
    """Structured outputs need `additionalProperties: false` on every object."""
    schema = copy.deepcopy(schema)
    stack = [schema]
    while stack:
        node = stack.pop()
        if node.get("type") == "object":
            node["additionalProperties"] = False
            stack.extend(node["properties"].values())
        elif node.get("type") == "array":
            stack.append(node["items"])
    return schema


CLAUDE_SCHEMA = _strict(RESPONSE_SCHEMA)


class ClaudeDecider(LlmDecider):
    def __init__(self, model: str, effort: str = "medium", client: anthropic.Anthropic | None = None) -> None:
        super().__init__()
        self.model = model
        self._effort = effort
        # ANTHROPIC_API_KEY (or a token / `ant auth login` profile) is the SDK's own lookup; CLAUDE_API_KEY
        # is the name the team's .env uses, passed explicitly only when the standard one is unset.
        key = None if os.environ.get("ANTHROPIC_API_KEY") else os.environ.get("CLAUDE_API_KEY")
        self._client = client or anthropic.Anthropic(api_key=key, timeout=TIMEOUT_S, max_retries=3)

    def _reply_text(self, user_turn: str) -> str:
        try:
            response = self._client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": self._system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_turn}],
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": CLAUDE_SCHEMA},
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except (
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
            anthropic.NotFoundError,
        ) as err:
            raise ModelFatal(f"{type(err).__name__}: {err.message}") from err
        except anthropic.BadRequestError as err:
            raise ModelFatal(f"bad request: {err.message}") from err
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as err:
            # The SDK already retried these; skip this tick.
            raise ModelUnavailable(f"{type(err).__name__}: {err}") from err
        if response.stop_reason == "refusal":
            raise ValueError("the model declined this tick")
        if response.stop_reason == "max_tokens":
            raise ValueError("reply cut off at max_tokens")
        return "".join(block.text for block in response.content if block.type == "text")
