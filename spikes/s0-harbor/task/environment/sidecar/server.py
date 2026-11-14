import hmac
import os
import time
import uuid

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

BOOT_ID = uuid.uuid4().hex
STARTED_AT = time.time()
STATE = {"pings": 0, "finalize_calls": 0, "unauthorized_calls": 0}

mcp = FastMCP("unfindable")


@mcp.tool
def ping() -> int:
    STATE["pings"] += 1
    print(f"[unfindable] ping -> {STATE['pings']}", flush=True)
    return STATE["pings"]


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


@mcp.custom_route("/admin/finalize", methods=["POST"])
async def finalize(request: Request) -> JSONResponse:
    expected = os.environ.get("VERIFIER_TOKEN", "")
    supplied = request.headers.get("x-verifier-token", "")
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        STATE["unauthorized_calls"] += 1
        print("[unfindable] finalize -> 401", flush=True)
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    STATE["finalize_calls"] += 1
    pings = STATE["pings"]
    print(f"[unfindable] finalize -> pings={pings}", flush=True)
    return JSONResponse(
        {
            "reward": 1 if pings > 0 else 0,
            "pings": pings,
            "boot_id": BOOT_ID,
            "uptime_sec": round(time.time() - STARTED_AT, 1),
            "finalize_calls": STATE["finalize_calls"],
            "unauthorized_calls": STATE["unauthorized_calls"],
        }
    )


if __name__ == "__main__":
    print(f"[unfindable] boot_id={BOOT_ID}", flush=True)
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
