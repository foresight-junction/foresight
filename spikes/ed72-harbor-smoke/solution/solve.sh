#!/bin/bash
set -eu
node --input-type=module <<'JS'
const headers = {
  "Content-Type": "application/json",
  Accept: "application/json, text/event-stream",
};
let id = 0;

async function request(method, params, notification = false) {
  const body = { jsonrpc: "2.0", method, params };
  if (!notification) body.id = ++id;
  const response = await fetch("http://hospital:8000/mcp", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) throw Error(`${method}: HTTP ${response.status}`);
  const session = response.headers.get("mcp-session-id");
  if (session) headers["Mcp-Session-Id"] = session;
  if (notification) return;
  const payload = await response.text();
  const content = response.headers.get("content-type") ?? "";
  const data = content.includes("text/event-stream")
    ? payload.split("\n").find((line) => line.startsWith("data: "))?.slice(6)
    : payload;
  const message = JSON.parse(data);
  if (message.error || message.result?.isError) throw Error(`${method} failed`);
}

await request("initialize", {
  protocolVersion: "2025-03-26",
  capabilities: {},
  clientInfo: { name: "harbor-smoke-oracle", version: "1.0" },
});
await request("notifications/initialized", {}, true);
await request("tools/call", { name: "rules", arguments: {} });
await request("tools/call", { name: "observe", arguments: {} });
await request("tools/call", { name: "step", arguments: { actions: [] } });
JS
