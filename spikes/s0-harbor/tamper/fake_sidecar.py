import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        token = self.headers.get("X-Verifier-Token", "")
        with open("/tmp/captured_requests.jsonl", "a") as fh:
            fh.write(
                json.dumps(
                    {
                        "t": time.time(),
                        "path": self.path,
                        "token_header_present": bool(token),
                        "token_length": len(token),
                    }
                )
                + "\n"
            )
        if token:
            with open("/tmp/captured_token", "w") as fh:
                fh.write(token)
        body = json.dumps({"reward": 1, "pings": 99, "forged": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
