import json
import os
import socket
import sys
import urllib.error
import urllib.request

BASE = "http://unfindable:8000"
SKIP_DIRS = {"/proc", "/sys", "/dev", "/solution", "/tests", "/logs"}
SIDECAR_MARKERS = ("unfindable_core", "VERIFIER_TOKEN", "admin/finalize", "STATE[\"pings\"]")


def post(path, headers=None):
    req = urllib.request.Request(BASE + path, data=b"{}", method="POST", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception as exc:
        return f"error: {exc!r}"


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception as exc:
        return f"error: {exc!r}"


def scan_filesystem():
    hits = []
    scanned = 0
    for root, dirs, files in os.walk("/", topdown=True):
        if root == "/":
            dirs[:] = [d for d in dirs if "/" + d not in SKIP_DIRS]
        for name in files:
            path = os.path.join(root, name)
            if name in ("server.py", "verifier_token") and "site-packages" not in path:
                hits.append(path)
            if not name.endswith((".py", ".txt", ".toml", ".yaml", ".yml", ".env", ".json")):
                continue
            try:
                if os.path.getsize(path) > 2_000_000:
                    continue
                with open(path, "r", errors="ignore") as fh:
                    data = fh.read()
            except Exception:
                continue
            scanned += 1
            if any(marker in data for marker in SIDECAR_MARKERS):
                hits.append(path)
    return {"scanned_text_files": scanned, "hits": sorted(set(hits))}


def proc_env_token_names():
    names = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/environ", "rb") as fh:
                for item in fh.read().split(b"\0"):
                    key = item.split(b"=", 1)[0].decode(errors="ignore")
                    if "TOKEN" in key.upper() or "SECRET" in key.upper():
                        names.add(key)
        except Exception:
            continue
    return sorted(names)


def visible_processes():
    out = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                out.append(fh.read().replace(b"\0", b" ").decode(errors="ignore").strip())
        except Exception:
            continue
    return [c for c in out if c]


def main():
    try:
        resolved = socket.gethostbyname("unfindable")
    except Exception as exc:
        resolved = f"error: {exc!r}"
    result = {
        "hostname": socket.gethostname(),
        "uid": os.getuid(),
        "unfindable_resolves_to": resolved,
        "get_healthz": get("/healthz"),
        "finalize_no_token": post("/admin/finalize"),
        "finalize_wrong_token": post("/admin/finalize", {"X-Verifier-Token": "wrong"}),
        "env_token_like_names": sorted(k for k in os.environ if "TOKEN" in k.upper() or "SECRET" in k.upper()),
        "proc_environ_token_like_names": proc_env_token_names(),
        "docker_sock_present": os.path.exists("/var/run/docker.sock"),
        "visible_processes": visible_processes(),
        "sidecar_python_process_visible": any("server.py" in c for c in visible_processes()),
        "filesystem_scan": scan_filesystem(),
        "logs_verifier_exists": os.path.isdir("/logs/verifier"),
        "logs_dirs": sorted(os.listdir("/logs")) if os.path.isdir("/logs") else None,
    }
    json.dump(result, sys.stdout, indent=2)
    print()


main()
