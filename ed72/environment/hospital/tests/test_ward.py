import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

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


def ward(url, *args):
    return subprocess.run(
        [sys.executable, str(WARD), "--url", url, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_rules_prints_handbook(url):
    r = ward(url, "rules")
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
    r = ward(url, "step", "--json", "not json")
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
