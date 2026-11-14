import json
import os
import urllib.error
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/admin/finalize",
    data=b"{}",
    method="POST",
    headers={"X-Verifier-Token": os.environ.get("VERIFIER_TOKEN", "")},
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())
        body["http_status"] = resp.status
except urllib.error.HTTPError as exc:
    body = {"reward": 0, "pings": 0, "http_status": exc.code}
except Exception as exc:
    body = {"reward": 0, "pings": 0, "error": repr(exc)}

os.makedirs("/evidence", exist_ok=True)
with open("/evidence/finalize.json", "w") as fh:
    json.dump(body, fh)
print(json.dumps(body))
