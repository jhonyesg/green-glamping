"""
MCP dev stub: a mock local MCP server for development/testing
without a real Multibot instance. Run with:
    python -m app.mcp.stub
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

STUB_RESPONSES = {
    "initialize": {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}, "resources": {}},
        "serverInfo": {"name": "multibot-mcp-stub", "version": "0.1.0"},
    },
    "tools/list": {
        "tools": [
            {"name": "get_conversation", "description": "stub"},
            {"name": "search_kb", "description": "stub"},
        ]
    },
    "tools/call": {"content": [{"type": "text", "text": '{"stub": true}'}]},
    "resources/list": {"resources": []},
    "resources/read": {"contents": []},
}


class MCPStubHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        method = body.get("method", "")
        result = STUB_RESPONSES.get(method, {"error": "unknown"})
        resp = json.dumps({"jsonrpc": "2.0", "id": body.get("id"), "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, format, *args):
        pass  # silent


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3002
    print(f"MCP stub running on http://localhost:{port}")
    HTTPServer(("localhost", port), MCPStubHandler).serve_forever()
