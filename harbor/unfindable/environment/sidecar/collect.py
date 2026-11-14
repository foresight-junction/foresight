import json
import urllib.request

with open("/run/uf-verifier-token", encoding="utf-8") as token_file:
    verifier_token = token_file.read().strip()

request = urllib.request.Request(
    "http://127.0.0.1:8000/admin/finalize",
    data=b"{}",
    method="POST",
    headers={"X-Verifier-Token": verifier_token},
)

with urllib.request.urlopen(request, timeout=20) as response:
    result = json.loads(response.read())

with open("/evidence/finalize.json", "w", encoding="utf-8") as evidence:
    json.dump(result, evidence)

print(json.dumps({"reward": result["reward"]["reward"]}))
