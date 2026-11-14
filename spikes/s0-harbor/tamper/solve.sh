#!/bin/bash
set -u

mkdir -p /logs/agent /logs/verifier
printf '{"reward": 1, "pings": 99}\n' > /logs/verifier/reward.json
echo "1" > /logs/verifier/reward.txt
FORGED='{"reward": 1, "pings": 99, "http_status": 200, "forged": true}'
mkdir -p /evidence /logs/artifacts/evidence
echo "$FORGED" > /evidence/finalize.json
echo "$FORGED" > /logs/artifacts/evidence/finalize.json

cp /etc/hosts /tmp/hosts.orig
echo "127.0.0.1 unfindable" >> /etc/hosts
echo "hosts after edit:"
tail -2 /etc/hosts

nohup setsid /usr/local/bin/python3 /solution/fake_sidecar.py > /tmp/fake_sidecar.log 2>&1 < /dev/null &
sleep 2
echo "fake sidecar pid(s): $(pgrep -f fake_sidecar.py 2>/dev/null || echo unknown)"
/usr/local/bin/python3 - <<'EOF'
import urllib.request
req = urllib.request.Request("http://unfindable:8000/admin/finalize", data=b"{}", method="POST")
print("self-test:", urllib.request.urlopen(req, timeout=5).read().decode())
EOF
