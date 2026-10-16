# https://github.com/ram133/api/blob/main/api.py
import http.server
import json
import os
import socketserver
import urllib.error
import urllib.request
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", 8080))

class AgentGatewayHandler(http.server.BaseHTTPRequestHandler):
    def _send_agent_response(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._send_agent_response(200, {"status": "ok"})

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if path == "/health":
            self._send_agent_response(200, {
                "status": "ok",
                "service": "AgentGateway",
                "version": "1.1.0"
            })
            return

        if path == "/proxy":
            target_url = query_params.get("url", [None])[0]
            if not target_url:
                self._send_agent_response(400, {
                    "status": "error",
                    "error": "Missing required query parameter: 'url'",
                    "data": None
                })
                return

            try:
                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "AgentGateway/1.1"}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    raw_body = response.read().decode("utf-8", errors="replace")
                    try:
                        parsed_body = json.loads(raw_body)
                    except json.JSONDecodeError:
                        parsed_body = raw_body

                    self._send_agent_response(200, {
                        "status": "success",
                        "upstream_code": response.getcode(),
                        "meta": {
                            "target_url": target_url,
                            "content_type": response.headers.get("Content-Type")
                        },
                        "data": parsed_body,
                        "error": None
                    })

            except urllib.error.HTTPError as e:
                self._send_agent_response(e.code, {
                    "status": "upstream_error",
                    "upstream_code": e.code,
                    "meta": {"target_url": target_url},
                    "data": None,
                    "error": f"HTTP {e.code}: {e.reason}"
                })
            except urllib.error.URLError as e:
                self._send_agent_response(502, {
                    "status": "gateway_error",
                    "upstream_code": None,
                    "meta": {"target_url": target_url},
                    "data": None,
                    "error": f"Failed to reach upstream: {e.reason}"
                })
            except Exception as e:
                self._send_agent_response(500, {
                    "status": "internal_error",
                    "upstream_code": None,
                    "meta": {"target_url": target_url},
                    "data": None,
                    "error": str(e)
                })
            return

        self._send_agent_response(404, {
            "status": "error",
            "error": f"Endpoint '{path}' not found",
            "data": None
        })

    def do_POST(self) -> None:
        self.do_GET()

def run_gateway(port: int = PORT) -> None:
    with socketserver.TCPServer(("", port), AgentGatewayHandler) as httpd:
        print(f"Agent Gateway running on port {port}...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Gateway.")

if __name__ == "__main__":
    run_gateway()
