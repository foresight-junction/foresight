import contextlib
import importlib.machinery
import importlib.util
import io
import json
import socket
import subprocess
import sys
import time
import urllib.request
from functools import cache
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

HOSPITAL = Path(__file__).parents[1]
WARD = Path(__file__).parents[2] / "ward"

SERVER_CODE = """
import pathlib, sys
import mock_sim, server
h = server.ToolHost(mock_sim.MockSimulation(1, pathlib.Path(sys.argv[2])), "HANDBOOK TEXT")
server.build_server(h).run(transport="streamable-http", host="127.0.0.1", port=int(sys.argv[1]), path="/mcp")
"""


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log = tmp_path_factory.mktemp("log") / "events.jsonl"
    proc = subprocess.Popen(
        [sys.executable, "-c", SERVER_CODE, str(port), str(log)],
        cwd=HOSPITAL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 20
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except OSError:
                if time.time() > deadline or proc.poll() is not None:
                    raise RuntimeError("hospital server did not start")
                time.sleep(0.2)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.kill()
        proc.wait()


def ward_script(url, *args):
    """Run the real script in a new process: the entry point and its exit code."""
    return subprocess.run(
        [sys.executable, str(WARD), "--url", url, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


@cache
def _ward_module() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("ward_cli", str(WARD))  # the script has no .py suffix
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("ward_cli", loader))
    loader.exec_module(module)
    return module


def ward(url, *args):
    """Run ward's main() in this process against the live server. A new process per call costs
    seconds of interpreter start and mcp import, so only ward_script tests pay it."""
    out, err = io.StringIO(), io.StringIO()
    argv = sys.argv
    sys.argv = [str(WARD), "--url", url, *args]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = _ward_module().main()
            except SystemExit as exc:  # argparse errors exit directly
                code = exc.code
    finally:
        sys.argv = argv
    return SimpleNamespace(returncode=code, stdout=out.getvalue(), stderr=err.getvalue())


def test_rules_prints_handbook(url):
    r = ward_script(url, "rules")
    assert r.returncode == 0
    assert r.stdout.strip() == "HANDBOOK TEXT"


def test_observe_is_tick_zero(url):
    r = ward(url, "observe")
    assert r.returncode == 0
    assert json.loads(r.stdout)["tick"] == 0


def test_step_advances_one_tick(url):
    r = ward(url, "step", "--json", "[]")
    assert r.returncode == 0
    assert json.loads(r.stdout)["observation"]["tick"] == 1


def test_step_rejects_bad_json(url):
    r = ward_script(url, "step", "--json", "not json")
    assert r.returncode == 2
    assert r.stdout == ""
    r = ward(url, "step", "--json", '{"a": 1}')
    assert r.returncode == 2
    assert ward(url, "observe", "--json", '{"x": 1}').returncode == 2


def test_step_accepts_the_tool_args_object(url):
    tick = json.loads(ward(url, "observe", "--json", "{}").stdout)["tick"]
    r = ward(url, "step", "--json", '{"actions": []}')
    assert r.returncode == 0
    assert json.loads(r.stdout)["observation"]["tick"] == tick + 1


def test_rules_json_prints_the_tool_result(url):
    for args in (["--json"], ["--json", "{}"]):
        r = ward(url, "rules", *args)
        assert r.returncode == 0
        assert json.loads(r.stdout) == {"text": "HANDBOOK TEXT"}
