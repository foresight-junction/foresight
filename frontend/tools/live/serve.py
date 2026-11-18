"""Live ED-72 episode for the pixel viewer: the real hospital MCP server, an agent, and an SSE feed.

The hospital tool server (ed72/environment/hospital/server.py) runs on 127.0.0.1:<mcp-port>/mcp
over a LiveRecorder-wrapped Simulation. The agent plays through that endpoint as an MCP client,
and every finished tick goes to the browser at GET /live/stream (see README.md for the command).
"""

import argparse
import asyncio
import contextlib
import http.server
import json
import os
import queue
import socket
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
from pathlib import Path

from agent import ScriptedDecider, play
from ed72_sim.config import load_config
from ed72_sim.engine import Simulation
from ed72_sim.world import generate_world
from gemini import DEFAULT_MODEL as GEMINI_MODEL
from gemini import GeminiDecider
from kimi import DEFAULT_MODEL as KIMI_MODEL
from llm import LlmDecider
from recorder import LiveRecorder
from server import ToolHost, build_server

ROOT = Path(__file__).resolve().parents[3]
HANDBOOK = ROOT / "ed72" / "environment" / "workspace" / "HANDBOOK.md"
RUNS_DIR = ROOT / "frontend" / "public" / "replays" / "runs"  # served by the viewer, gitignored
PING_S = 15
LABELS = {"reference": "Reference policy (live)", "reactive": "Reactive proxy (live)"}
# claude.DEFAULT_MODEL, repeated so the anthropic SDK is only imported when Claude plays.
CLAUDE_MODEL = "claude-opus-5-5"


def load_env_file(path: Path) -> None:
    """KEY=VALUE lines into os.environ; variables already set in the environment win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if value:
            os.environ.setdefault(key.strip(), value)


AGENTS = ("gemini", "kimi", "claude", "reference", "reactive")
# Each model agent and the environment variables that can hold its credentials (any one is enough).
MODEL_KEYS = {
    "gemini": ("GEMINI_API_KEY",),
    "kimi": ("VERDA_INFERENCE_API_KEY",),
    "claude": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
}
ALIASES = {"llm": "gemini"}  # the name of the Gemini agent before Kimi and Claude joined
MAX_SEED = 2**31 - 1


def make_meta(agent: str, seed: int, model: str | None, run: str = "") -> dict:
    return {
        "name": f"live-{agent}-seed{seed}",
        "policy": f"live-{agent}",
        "label": f"{model} (live)" if agent in MODEL_KEYS else LABELS[agent],
        "seed": seed,
        "reward": None,
        "score": None,
        # `run` tells the viewer a new episode started (same agent and seed can run twice).
        "live": {"agent": agent, "model": model, "state": "starting", "run": run},
    }


def has_key(agent: str) -> bool:
    return any(os.environ.get(name) for name in MODEL_KEYS.get(agent, ()))


def available_agents() -> list[str]:
    return [a for a in AGENTS if a not in MODEL_KEYS or has_key(a)]


def check_agent(agent: str) -> str:
    """The canonical agent name; ValueError if it is unknown or its key is missing."""
    agent = ALIASES.get(agent, agent)
    if agent not in AGENTS:
        raise ValueError(f"agent must be one of {', '.join(AGENTS)}")
    if agent not in available_agents():
        raise ValueError(f"{' or '.join(MODEL_KEYS[agent])} is not set, so the {agent} agent is unavailable")
    return agent


def model_of(agent: str, args: argparse.Namespace) -> str | None:
    return {"gemini": args.gemini_model, "kimi": args.kimi_model, "claude": args.claude_model}.get(agent)


def parse_start(body: bytes) -> tuple[int, str]:
    """The viewer's "New run" request: {"seed": int, "agent": "gemini|kimi|claude|reference|reactive"}."""
    try:
        req = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise ValueError("body must be JSON") from None
    seed, agent = req.get("seed"), req.get("agent")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be an integer from 0 to {MAX_SEED}")
    return seed, check_agent(str(agent))


def make_handler(
    recorder: LiveRecorder, requests: "queue.Queue[tuple[int, str]]"
) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/live/health":
                self._send_json({"ok": True, "agents": available_agents()})
            elif self.path.split("?")[0] == "/live/stream":
                self._stream()
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/live/start":
                self.send_error(404)
                return
            length = min(int(self.headers.get("Content-Length") or 0), 4096)
            try:
                requests.put(parse_start(self.rfile.read(length)))
            except ValueError as err:
                self._send_json({"ok": False, "error": str(err)}, 400)
                return
            self._send_json({"ok": True}, 202)

        def _send_json(self, body: dict, status: int = 200) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            q, snapshot = recorder.subscribe()
            try:
                self._write(f"data: {snapshot}\n\n")
                while True:
                    try:
                        self._write(f"data: {q.get(timeout=PING_S)}\n\n")
                    except queue.Empty:
                        self._write(": ping\n\n")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # the browser went away
            finally:
                recorder.unsubscribe(q)

        def _write(self, text: str) -> None:
            self.wfile.write(text.encode())
            self.wfile.flush()

        def log_message(self, format: str, *args: object) -> None:
            return None

    return Handler


def start_mcp(recorder: LiveRecorder, port: int) -> ToolHost:
    # A server already on the port would answer /health and the agent would play someone else's sim.
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(f"port {port} is already in use; stop that server or pass --mcp-port")
    host = ToolHost(recorder, HANDBOOK.read_text(encoding="utf-8"))
    mcp = build_server(host)
    # uvicorn skips signal handlers off the main thread, so Ctrl+C stays with the main thread.
    threading.Thread(
        target=lambda: mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=port,
            path="/mcp",
            show_banner=False,
            log_level="warning",
        ),
        daemon=True,
        name="mcp",
    ).start()
    deadline = time.monotonic() + 30
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if response.status == 200:
                    return host
        except OSError:
            if time.monotonic() > deadline:
                raise SystemExit(f"hospital MCP server did not come up on port {port}") from None
            time.sleep(0.2)


def make_decider(agent: str, args: argparse.Namespace) -> ScriptedDecider | LlmDecider:
    if agent == "reference":
        from policy import ReferencePolicy

        return ScriptedDecider(ReferencePolicy().actions)
    if agent == "reactive":
        from ed72_baselines.policies import ReactiveProxy

        return ScriptedDecider(ReactiveProxy().act)
    if agent == "kimi":
        from kimi import KimiDecider

        return KimiDecider(args.kimi_model, os.environ["VERDA_INFERENCE_API_KEY"], args.kimi_effort)
    if agent == "claude":
        # Imported here so the anthropic SDK is only needed when Claude plays.
        from claude import ClaudeDecider

        return ClaudeDecider(args.claude_model, args.claude_effort)
    return GeminiDecider(args.gemini_model, os.environ["GEMINI_API_KEY"], args.thinking_level)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", choices=[*AGENTS, *ALIASES], default="gemini")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gemini-model", "--model", default=GEMINI_MODEL, help="Gemini model id")
    parser.add_argument("--thinking-level", default="low", help="Gemini thinkingLevel")
    parser.add_argument("--kimi-model", default=KIMI_MODEL, help="Kimi model id on Verda Inference")
    parser.add_argument("--kimi-effort", default="low", help="Kimi reasoning_effort: none|low|high|max")
    parser.add_argument("--claude-model", default=CLAUDE_MODEL, help="Claude model id")
    parser.add_argument("--claude-effort", default="medium", help="Claude effort: low|medium|high|xhigh|max")
    parser.add_argument(
        "--min-tick-seconds",
        type=float,
        default=None,
        help="minimum wall time per tick (default 0 for models, 1 for scripted policies)",
    )
    parser.add_argument("--mcp-port", type=int, default=8000)
    parser.add_argument("--port", type=int, default=8770, help="SSE/HTTP port")
    parser.add_argument(
        "--env-file",
        type=Path,
        action="append",
        help="KEY=VALUE file with model keys; repeat for several (default: <root>/.env)",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=RUNS_DIR,
        help="every run is saved here as a replay, rewritten after each tick (default: viewer's replays/runs)",
    )
    parser.add_argument("--no-save", action="store_true", help="keep the run in memory only")
    args = parser.parse_args()
    for path in args.env_file or [ROOT / ".env"]:
        load_env_file(path)
    try:
        args.agent = check_agent(args.agent)
    except ValueError as err:
        raise SystemExit(f"--agent {args.agent}: {err}") from None
    print(f"agents available: {', '.join(available_agents())}", flush=True)

    recorder = LiveRecorder(*new_episode(args.seed, args.agent, args))
    requests: queue.Queue[tuple[int, str]] = queue.Queue()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(recorder, requests))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True, name="sse").start()
    host = start_mcp(recorder, args.mcp_port)
    print(f"MCP   http://127.0.0.1:{args.mcp_port}/mcp", flush=True)
    print(f"SSE   http://127.0.0.1:{args.port}/live/stream  (POST /live/start starts a new run)", flush=True)

    try:
        asyncio.run(serve_runs(args, recorder, host, requests))
    except KeyboardInterrupt:
        print("stopping", file=sys.stderr)
    finally:
        httpd.shutdown()
        httpd.server_close()


def new_episode(seed: int, agent: str, args: argparse.Namespace) -> tuple[Simulation, dict, Path | None]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = Path(tempfile.mkdtemp(prefix="ed72-live-")) / "events.jsonl"
    sim = Simulation(generate_world(seed, load_config(os.environ.get("ED72_CONFIG"))), log_path)
    meta = make_meta(agent, seed, model_of(agent, args), f"{stamp}-{agent}-{seed}")
    save_path = None
    if not args.no_save:
        args.save_dir.mkdir(parents=True, exist_ok=True)
        save_path = args.save_dir / f"{meta['name']}-{stamp}.json"
    print(f"\nrun   {agent} on seed {seed}", flush=True)
    print(f"log   {log_path}", flush=True)
    if save_path is not None:
        print(f"save  {save_path}", flush=True)
        if save_path.parent.resolve() == RUNS_DIR.resolve():
            print(f"      viewer query: ?replay=runs/{save_path.name}", flush=True)
    return sim, meta, save_path


async def play_episode(agent: str, args: argparse.Namespace, recorder: LiveRecorder, url: str) -> None:
    min_tick = args.min_tick_seconds
    if min_tick is None:
        min_tick = 0.0 if agent in MODEL_KEYS else 1.0
    try:
        await play(url, recorder, make_decider(agent, args), min_tick)
    except Exception as err:  # noqa: BLE001
        traceback.print_exc()
        # Keep the replay whole: the rest of the episode runs with no actions.
        recorder.set_state("error", f"{type(err).__name__}: {err}")
        recorder.finish()
    print(f"done: reward {recorder.meta['reward']:.6f}. Serving the replay until the next run.", flush=True)


async def serve_runs(
    args: argparse.Namespace,
    recorder: LiveRecorder,
    host: ToolHost,
    requests: "queue.Queue[tuple[int, str]]",
) -> None:
    """Plays the CLI's run, then a new run for every POST /live/start, cancelling one still going."""
    url = f"http://127.0.0.1:{args.mcp_port}/mcp"
    task = asyncio.create_task(play_episode(args.agent, args, recorder, url))
    while True:
        try:
            # A short timeout keeps Ctrl+C prompt: a worker thread blocked forever would hold up exit.
            seed, agent = await asyncio.to_thread(requests.get, True, 0.5)
        except queue.Empty:
            continue
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # A step the old agent already sent may still be in the server; let it land on the old sim.
        await asyncio.sleep(0.3)
        with host.lock:
            host.calls = 0  # the 500-call cap is per episode
        recorder.reset(*new_episode(seed, agent, args))
        task = asyncio.create_task(play_episode(agent, args, recorder, url))


if __name__ == "__main__":
    main()
