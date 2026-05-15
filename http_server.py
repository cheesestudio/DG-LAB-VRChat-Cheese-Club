"""HTTP server for VRChat ShockingManager compatibility."""
import json
import socket
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


def _check_vrchat_origin(handler) -> bool:
    """Check if request comes from VRChat via UnityPlayer user-agent."""
    ua = handler.headers.get("User-Agent", "")
    return "UnityPlayer" in ua


class ShockHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from VRChat ShockingManager."""

    app = None  # Set by App before starting server

    def log_message(self, format, *args):
        logger.debug(f"HTTP {args[0]}")

    def _send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Auth check: only allow requests from VRChat UnityPlayer
        if not _check_vrchat_origin(self):
            self._send_json({"status": "error", "message": "origin not allowed"}, 403)
            return

        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/v1/status":
            self._handle_status()
        elif params.get("ret") == ["status"]:
            self._handle_status()
        elif path.startswith("/api/v1/shock"):
            # /api/v1/shock?channel=A&second=5
            channel = params.get("channel", ["all"])[0]
            second_str = params.get("second", ["1"])[0]
            self._handle_shock(channel, second_str)
        elif path.startswith("/api/v1/sendwave"):
            # /api/v1/sendwave?channel=A&repeat=10&wavedata=...
            channel = params.get("channel", ["A"])[0]
            repeat_str = params.get("repeat", ["1"])[0]
            wavedata = params.get("wavedata", [""])[0]
            self._handle_sendwave(channel, repeat_str, wavedata)
        else:
            self._handle_status()

    def _handle_status(self):
        app = self.app
        if not app or not app._ws_client or not app._ws_client.is_paired:
            self._send_json({"healthy": "ok", "devices": []})
        else:
            strength = app._ws_client._strength
            self._send_json({
                "healthy": "ok",
                "devices": [{
                    "type": "shock",
                    "device": "coyotev3",
                    "attr": {
                        "strength": {
                            "A": strength.get("A", 0),
                            "B": strength.get("B", 0),
                        },
                        "uuid": app._ws_client.client_id or "",
                    },
                }],
            })

    def _handle_shock(self, channel: str, second_str: str):
        app = self.app
        if not app or not app._ws_client or not app._ws_client.is_paired:
            self._send_json({"status": "error", "message": "not connected"}, 503)
            return
        try:
            seconds = min(float(second_str), 10.0)
        except ValueError:
            seconds = 1.0
        if seconds < 1:
            seconds = 1.0
        seconds = round(seconds)
        # Map channel: A->0, B->1, all->2
        channel_map = {"a": 0, "b": 1}
        mode = channel_map.get(channel.lower(), 2) if channel.lower() not in ("all",) else 2
        app.on_http_shock(mode, seconds)
        self._send_json({"status": "ok"})

    def _handle_sendwave(self, channel: str, repeat_str: str, wavedata: str):
        app = self.app
        if not app or not app._ws_client or not app._ws_client.is_paired:
            self._send_json({"status": "error", "message": "not connected"}, 503)
            return
        try:
            repeat = max(1, min(int(repeat_str), 100))
        except ValueError:
            repeat = 1
        ch = channel.upper() if channel.upper() in ("A", "B") else "A"
        wave_list = [wavedata] * repeat
        app._ws_client.send_waveform(ch, wave_list, duration=max(repeat // 10, 1))
        self._send_json({"status": "ok"})


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


class HttpServer:
    """Runs the HTTP server in a background thread."""

    def __init__(self, port: int = 8800):
        self._port = port
        self._server = None
        self._thread = None

    def start(self, app):
        ShockHandler.app = app
        try:
            self._server = ReusableHTTPServer(("0.0.0.0", self._port), ShockHandler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            logger.info(f"HTTP server started on port {self._port}")
            return True
        except OSError as e:
            logger.error(f"HTTP server failed: {e}")
            return False

    def stop(self):
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            try:
                self._server.server_close()
            except Exception:
                pass
            self._server = None
            self._thread = None
        ShockHandler.app = None  # Release App reference to allow GC