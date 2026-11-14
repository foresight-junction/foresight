#!/bin/bash
set -u

mkdir -p /logs/agent
/usr/local/bin/python3 /solution/probes.py > /logs/agent/probes.json 2>&1
echo "probes written to /logs/agent/probes.json"
/usr/local/bin/python3 /solution/mcp_ping.py http://unfindable:8000/mcp | tee /logs/agent/mcp_ping.json
