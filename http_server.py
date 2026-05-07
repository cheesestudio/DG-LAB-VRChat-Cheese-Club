"""HTTP server for VRChat ShockingManager compatibility."""
import json
import socket
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class ShockHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from VRChat ShockingManager."""

    app = None  # Set by App before starting server

    def log_message(self, format, *args):
        logger.debug(f"HTTP {args[0]}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # /api/v1/status — status check (compatible with Shocking-VRChat)
        if path == "/api/v1/status":
            self._handle_status()
        # /api/v1/shock/<channel>/<second> — shock trigger
        # channel: "A", "B", or "all"; second: 1-10 float
        elif path.startswith("/api/v1/shock/"):
            parts = path.split("/")
            if len(parts) >= 6:
                channel = parts[4]
                second = parts[5]
                self._handle_shock(channel, second)
            else:
                self._send_json({"status": "error"}, 400)
        # /api/v1/sendwave/<channel>/<repeat>/<wavedata>
        elif path.startswith("/api/v1/sendwave/"):
            parts = path.split("/")
            if len(parts) >= 7:
                channel = parts[4]
                repeat = parts[5]
                wavedata = parts[6]
                self._handle_sendwave(channel, repeat, wavedata)
            else:
                self._send_json({"status": "error"}, 400)
        # Fallback: any path with ?ret=status returns status
        elif params.get("ret") == ["status"]:
            self._handle_status()
        else:
            self._handle_status()

    def _handle_status(self):
        app = self.app
        if not app or not app._ws_client or not app._ws_client.is_paired:
            data = {"healthy": "ok", "devices": []}
        else:
            strength = app._ws_client._strength
            data = {
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
            }
        self._send_json(data)

    def _handle_shock(self, channel: str, second_str: str):
        app = self.app
        if not app or not app._ws_client or not app._ws_client.is_paired:
            self._send_json({"status": "error", "message": "not connected"})
            return
        try:
            seconds = min(float(second_str), 10.0)
        except ValueError:
            seconds = 1.0
        if seconds < 1:
            seconds = 1.0
        seconds = int(seconds)
        # Map channel: "A"->0, "B"->1, "all"->2
        if channel.lower() == "all":
            mode = 2
        elif channel.upper() == "A":
            mode = 0
        elif channel.upper() == "B":
            mode = 1
        else:
            mode = 2
        app.on_http_shock(mode, seconds)
        self._send_json({"status": "ok"})

    def _handle_sendwave(self, channel: str, repeat_str: str, wavedata: str):
        app = self.app
        if not app or not app._ws_client or not app._ws_client.is_paired:
            self._send_json({"status": "error", "message": "not connected"})
            return
        try:
            repeat = int(repeat_str)
        except ValueError:
            repeat = 1
        ch = channel.upper() if channel.upper() in ("A", "B") else "A"
        # Build wave list: repeat the wavedata entry
        wave_list = [wavedata] * repeat
        app._ws_client.send_waveform(ch, wave_list, duration=max(repeat // 10, 1))
        self._send_json({"status": "ok"})

    def _send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


class HttpServer:
    """Runs the HTTP server in a background thread."""

    def __init__(self, port: int = 9002):
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
