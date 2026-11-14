"""Live ED-72 episode for the pixel viewer: the real hospital MCP server, an agent, and an SSE feed.

The hospital tool server (ed72/environment/hospital/server.py) runs on 127.0.0.1:<mcp-port>/mcp
over a LiveRecorder-wrapped Simulation. The agent plays through that endpoint as an MCP client,
and every finished tick goes to the browser at GET /live/stream (see README.md for the command).
"""

import argparse
import asyncio
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
from gemini import DEFAULT_MODEL, GeminiDecider
from recorder import LiveRecorder
from server import ToolHost, build_server

ROOT = Path(__file__).resolve().parents[3]
HANDBOOK = ROOT / "ed72" / "environment" / "workspace" / "HANDBOOK.md"
RUNS_DIR = ROOT / "frontend" / "public" / "replays" / "runs"  # served by the viewer, gitignored
PING_S = 15
LABELS = {"reference": "Reference policy (live)", "reactive": "Reactive proxy (live)"}


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


def make_meta(agent: str, seed: int, model: str | None) -> dict:
    return {
        "name": f"live-{agent}-seed{seed}",
        "policy": f"live-{agent}",
        "label": f"{model} (live)" if agent == "llm" else LABELS[agent],
        "seed": seed,
        "reward": None,
        "score": None,
        "live": {"agent": agent, "model": model, "state": "starting"},
    }


def make_handler(recorder: LiveRecorder) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/live/health":
                self._send_json({"ok": True})
            elif self.path.split("?")[0] == "/live/stream":
                self._stream()
            else:
                self.send_error(404)

        def _send_json(self, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
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


def start_mcp(recorder: LiveRecorder, port: int) -> None:
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
                    return
        except OSError:
            if time.monotonic() > deadline:
                raise SystemExit(f"hospital MCP server did not come up on port {port}") from None
            time.sleep(0.2)


def make_decider(args: argparse.Namespace) -> ScriptedDecider | GeminiDecider:
    if args.agent == "reference":
        from policy import ReferencePolicy

        return ScriptedDecider(ReferencePolicy().actions)
    if args.agent == "reactive":
        from ed72_baselines.policies import ReactiveProxy

        return ScriptedDecider(ReactiveProxy().act)
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit(f"GEMINI_API_KEY is not set (environment or {args.env_file}); --agent llm needs it")
    return GeminiDecider(args.model, key, args.thinking_level)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", choices=["llm", "reference", "reactive"], default="llm")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model id (llm agent)")
    parser.add_argument("--thinking-level", default="low", help="Gemini thinkingLevel (llm agent)")
    parser.add_argument(
        "--min-tick-seconds",
        type=float,
        default=None,
        help="minimum wall time per tick (default 0 llm, 1 scripted)",
    )
    parser.add_argument("--mcp-port", type=int, default=8000)
    parser.add_argument("--port", type=int, default=8770, help="SSE/HTTP port")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=RUNS_DIR,
        help="every run is saved here as a replay, rewritten after each tick (default: viewer's replays/runs)",
    )
    parser.add_argument("--no-save", action="store_true", help="keep the run in memory only")
    args = parser.parse_args()
    load_env_file(args.env_file)
    min_tick = args.min_tick_seconds
    if min_tick is None:
        min_tick = 0.0 if args.agent == "llm" else 1.0

    decider = make_decider(args)
    log_path = Path(tempfile.mkdtemp(prefix="ed72-live-")) / "events.jsonl"
    sim = Simulation(generate_world(args.seed, load_config(os.environ.get("ED72_CONFIG"))), log_path)
    meta = make_meta(args.agent, args.seed, args.model if args.agent == "llm" else None)
    save_path = None
    if not args.no_save:
        args.save_dir.mkdir(parents=True, exist_ok=True)
        save_path = args.save_dir / f"{meta['name']}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    recorder = LiveRecorder(sim, meta, save_path)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(recorder))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True, name="sse").start()
    start_mcp(recorder, args.mcp_port)
    print(f"MCP   http://127.0.0.1:{args.mcp_port}/mcp", flush=True)
    print(f"SSE   http://127.0.0.1:{args.port}/live/stream", flush=True)
    print(f"log   {log_path}", flush=True)
    if save_path is not None:
        print(f"save  {save_path}", flush=True)
        if save_path.parent.resolve() == RUNS_DIR.resolve():
            print(f"      replay later: http://localhost:5170/?replay=runs/{save_path.name}", flush=True)

    try:
        try:
            asyncio.run(play(f"http://127.0.0.1:{args.mcp_port}/mcp", recorder, decider, min_tick))
        except Exception as err:  # noqa: BLE001
            traceback.print_exc()
            # Keep the replay whole: the rest of the episode runs with no actions.
            recorder.set_state("error", f"{type(err).__name__}: {err}")
            recorder.finish()
        meta = recorder.meta
        print(f"done: reward {meta['reward']:.6f}. Still serving the replay; Ctrl+C to stop.", flush=True)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("stopping", file=sys.stderr)
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
