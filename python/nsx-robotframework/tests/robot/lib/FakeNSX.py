"""In-process fake NSX-T manager for Robot Framework keyword tests.

Started via ``Start Fake NSX`` (returns the base URL) and stopped via
``Stop Fake NSX``. Serves canned Policy + Manager responses so the
``NSXLibrary`` keywords can be exercised end-to-end without a real NSX.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeNSX/0.1"

    def log_message(self, *args):
        pass

    @property
    def _store(self):
        return self.server.nsx_state

    def _send(self, code, body=None, headers=None):
        payload = b"" if body is None else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            return json.loads(self.rfile.read(length))
        return None

    def _path_parts(self):
        path = self.path.split("?")[0]
        return [p for p in path.split("/") if p]

    def do_POST(self):
        if self.path == "/api/v1/session/create":
            self._send(200, {}, headers={"Set-Cookie": "JSESSIONID=fake; Path=/"})
            return
        self._send(404, {"error_message": f"no POST handler for {self.path}"})

    def do_PUT(self):
        body = self._body() or {}
        self._send(200, body)

    def do_DELETE(self):
        if self.path == "/api/v1/session/create":
            self._send(200, {})
            return
        self._send(200, {})

    def do_GET(self):
        store = self._store
        parts = self._path_parts()

        if parts == ["policy", "api", "v1", "infra", "segments"]:
            self._send(200, {"results": store["segments"]})
            return
        if (
            parts[:5] == ["policy", "api", "v1", "infra", "segments"]
            and len(parts) == 6
        ):
            seg_id = parts[5]
            match = [s for s in store["segments"] if s["id"] == seg_id]
            if match:
                self._send(200, match[0])
            else:
                self._send(404, {"error_message": f"segment {seg_id} not found"})
            return
        if (
            parts[:5] == ["policy", "api", "v1", "infra", "segments"]
            and len(parts) == 7
            and parts[6] == "ports"
        ):
            self._send(200, {"results": store["ports"]})
            return
        if parts == ["policy", "api", "v1", "infra", "realized-state"]:
            intent = self.path.split("intent_path=")[-1].split("&")[0]
            calls = store["realize_calls"].get(intent, 0)
            store["realize_calls"][intent] = calls + 1
            state = "UNREALIZED" if calls == 0 else "REALIZED"
            self._send(200, {"results": [{"entity_type": "Generic", "state": state}]})
            return
        if parts == ["policy", "api", "v1", "infra", "lb-virtual-servers"]:
            self._send(200, {"results": store["lb_vs"]})
            return
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "v1" and parts[2] == "tasks":
            self._send(200, {"status": "COMPLETED"})
            return
        if parts[-3:] == ["routing", "bgp", "neighbors"]:
            self._send(200, {"results": store["bgp_neighbors"]})
            return
        if parts[-3:] == ["routing", "bfd", "sessions"]:
            self._send(200, {"results": store["bfd_sessions"]})
            return
        self._send(404, {"error_message": f"no GET handler for {'/'.join(parts)}"})


class FakeNSX:
    """Robot library exposing ``Start Fake NSX`` / ``Stop Fake NSX``."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self):
        self._httpd = None
        self._thread = None

    @property
    def state(self) -> dict:
        return self._httpd.nsx_state

    def start_fake_nsx(self) -> str:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.nsx_state = {
            "segments": [
                {"id": "web", "display_name": "web", "resource_type": "Segment"},
                {"id": "app", "display_name": "app", "resource_type": "Segment"},
            ],
            "ports": [{"address_bindings": [{"vm_id": "vm-123"}]}],
            "realize_calls": {},
            "lb_vs": [{"id": "vs-1", "ip_address": "10.0.0.10"}],
            "bgp_neighbors": [
                {"neighbor_address": "10.0.0.1", "state": "ESTABLISHED"}
            ],
            "bfd_sessions": [{"peer_address": "10.0.0.2", "state": "UP"}],
        }
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        port = self._httpd.server_address[1]
        return f"http://127.0.0.1:{port}"

    def stop_fake_nsx(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def fake_nsx_set_bgp_neighbor_state(self, neighbor_ip: str, state: str) -> None:
        for n in self.state["bgp_neighbors"]:
            if n["neighbor_address"] == neighbor_ip:
                n["state"] = state
                return
        self.state["bgp_neighbors"].append(
            {"neighbor_address": neighbor_ip, "state": state}
        )
