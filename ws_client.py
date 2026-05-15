"""DG-LAB WebSocket server - strictly following official v2 protocol."""
import asyncio
import json
import uuid
import threading
import logging
import socket
from typing import Callable, Optional, Dict

logger = logging.getLogger(__name__)

import websockets  # noqa: E402  — imported at module level for PyInstaller


def _get_local_ip() -> str:
    """Get the LAN IP address that phones can reach."""
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        for ip in ips:
            if ip.startswith("192.168."):
                return ip
        for ip in ips:
            if ip.startswith("10."):
                return ip
        for ip in ips:
            if ip != "127.0.0.1":
                return ip
        return "127.0.0.1"
    except Exception:
        return "127.0.0.1"


def _make_msg(msg_type: str, client_id: str = "", target_id: str = "", message: str = "") -> str:
    return json.dumps({
        "type": msg_type,
        "clientId": client_id,
        "targetId": target_id,
        "message": str(message),
    })


class WSClient:
    """DG-LAB WebSocket server - official v2 protocol."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9999,
        on_status_change: Callable[[str], None] = None,
        on_qr_url: Callable[[str], None] = None,
        on_message: Callable[[dict], None] = None,
        on_strength_update: Callable[[dict], None] = None,
        on_get_a_limit: Callable[[], int] = None,
        on_get_b_limit: Callable[[], int] = None,
    ):
        self._host = host
        self._port = port
        self._on_status = on_status_change or (lambda s: None)
        self._on_qr = on_qr_url or (lambda u: None)
        self._on_message = on_message or (lambda m: None)
        self._on_strength = on_strength_update or (lambda s: None)
        self._on_get_a_limit = on_get_a_limit
        self._on_get_b_limit = on_get_b_limit

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()

        # IDs
        self._local_client_id = str(uuid.uuid4())
        self._app_target_id: Optional[str] = None

        # WebSocket connections
        self._uuid_to_ws: Dict[str, object] = {}

        # Bind state
        self._bound = False
        self._app_uuid_in_bind: Optional[str] = None

        self._strength = {"A": 0, "B": 0}
        self._strength_max = {"A": 200, "B": 200}
        self._waveform_active = False  # Suppress reactive strength correction during waveform playback
        self._server_socket = None
        self._ws_server = None
        self._stop_event: Optional[asyncio.Event] = None
        self._init_task: Optional[asyncio.Task] = None  # track init strength task for cancellation

    def _run_server(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Custom exception handler: suppress expected errors during shutdown
        _default_handler = self._loop.get_exception_handler()

        def _shutdown_exception_handler(loop, context):
            # During shutdown, suppress all asyncio errors (IOCP abort, closed loop, etc.)
            if not self._running:
                return
            exc = context.get("exception")
            if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 995:
                return  # Suppress IOCP abort
            if _default_handler:
                _default_handler(loop, context)
            else:
                loop.default_exception_handler(context)

        self._loop.set_exception_handler(_shutdown_exception_handler)

        try:
            self._loop.run_until_complete(self._server_main())
        except RuntimeError as e:
            # "Event loop stopped before Future completed" is expected during shutdown
            if "Event loop stopped" not in str(e):
                logger.error(f"服务器线程异常: {e}")
        finally:
            # Give websockets internal tasks time to finish naturally.
            # websockets uses asyncio.shield() internally so cancellation
            # doesn't propagate — we must let them complete on their own.
            try:
                self._loop.run_until_complete(asyncio.sleep(0.1))
            except Exception:
                pass
            # Cancel any remaining tasks (IOCP etc.)
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.sleep(0.1))
            except Exception:
                pass
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            # Suppress "Task was destroyed but it is pending" errors on close.
            # These are harmless — break message was already sent successfully.
            # websockets' shielded tasks can't be cancelled and will be GC'd.
            _asyncio_logger = logging.getLogger("asyncio")
            _prev_level = _asyncio_logger.level
            _asyncio_logger.setLevel(logging.CRITICAL)
            self._loop.close()
            _asyncio_logger.setLevel(_prev_level)
            self._loop = None

    async def _server_main(self):
        self._stop_event = asyncio.Event()

        async def handler(ws):
            await self._handle_client(ws)

        try:
            import socket as _sock
            local_ip = _get_local_ip()
            qr_url = (
                f"https://www.dungeon-lab.com/app-download.php"
                f"#DGLAB-SOCKET"
                f"#ws://{local_ip}:{self._port}/{self._local_client_id}"
            )
            self._on_qr(qr_url)

            # Create socket with SO_REUSEADDR
            sock = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
            sock.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
            sock.bind((self._host, self._port))
            sock.listen()
            self._server_socket = sock

            self._on_status("connected")
            self._on_message({"type": "info", "text": f"服务器已启动: {local_ip}:{self._port}"})
            self._on_message({"type": "info", "text": f"终端ID: {self._local_client_id[:16]}.."})

            self._ws_server = await websockets.serve(
                handler, sock=sock,
                ping_interval=None,
                compression=None,
                server_header=None,
                close_timeout=2,
            )
            try:
                await self._stop_event.wait()
            finally:
                self._ws_server.close()
                await self._ws_server.wait_closed()
        except asyncio.CancelledError:
            pass
        except OSError as e:
            # WinError 995: I/O operation aborted during shutdown - expected
            if e.winerror == 995:
                pass
            else:
                self._on_message({"type": "error", "text": f"服务器启动失败: {e}"})
                self._on_status("disconnected")
        except Exception as e:
            self._on_message({"type": "error", "text": f"服务器启动失败: {e}"})
            self._on_status("disconnected")

    async def _handle_client(self, ws):
        """Handle a new WebSocket connection (APP connects here)."""
        self._on_message({"type": "debug", "text": "APP连接"})

        # Step 1: Send bind with our own UUID as clientId
        bind_init = _make_msg("bind", client_id=self._local_client_id, target_id="", message="targetId")
        self._on_message({"type": "debug", "text": f"发送: {bind_init[:120]}"})
        await ws.send(bind_init)

        hb_task = asyncio.ensure_future(self._heartbeat(ws))

        try:
            async for raw_message in ws:
                self._on_message({"type": "debug", "text": f"收到: {str(raw_message)[:150]}"})
                try:
                    event = json.loads(raw_message)
                except json.JSONDecodeError:
                    self._on_message({"type": "debug", "text": "JSON解析失败"})
                    continue

                msg_type = event.get("type", "")
                msg_client = event.get("clientId", "")
                msg_target = event.get("targetId", "")
                msg_data = event.get("message", "")

                if msg_type == "bind":
                    self._on_message({
                        "type": "debug",
                        "text": f"Bind请求: client={msg_client[:16]}.. target={msg_target[:16]}.. msg={msg_data}"
                    })

                    # Accept bind if message is "DGLAB" and we have a targetId
                    # APP may send its own UUID as clientId (not the server's)
                    if msg_data == "DGLAB" and msg_target:
                        with self._lock:
                            # Clear previous app entry if a different client binds
                            old_target = self._app_target_id
                            if old_target and old_target != msg_target:
                                self._uuid_to_ws.pop(old_target, None)
                            self._bound = True
                            self._app_target_id = msg_target
                            self._app_uuid_in_bind = msg_client
                            self._uuid_to_ws[msg_target] = ws

                        resp = _make_msg("bind", client_id=self._local_client_id, target_id=msg_target, message="200")
                        await ws.send(resp)
                        self._on_message({"type": "info", "text": f"APP已配对 (UUID: {msg_target[:16]}..)"})
                        self._on_status("paired")

                        a_limit = self._on_get_a_limit() if self._on_get_a_limit else 200
                        b_limit = self._on_get_b_limit() if self._on_get_b_limit else 200
                        if self._init_task and not self._init_task.done():
                            self._init_task.cancel()
                            self._init_task = None
                        self._init_task = asyncio.ensure_future(self._init_strength(a_limit, b_limit))
                    else:
                        resp = _make_msg("bind", client_id=msg_client, target_id=msg_target, message="400")
                        await ws.send(resp)
                        self._on_message({"type": "warning", "text": f"Bind失败: client={msg_client[:16]}.. msg={msg_data}"})

                elif msg_type == "msg":
                    if isinstance(msg_data, str) and msg_data.startswith("strength-"):
                        parts = msg_data[len("strength-"):].split("+")
                        if len(parts) == 4:
                            with self._lock:
                                self._strength["A"] = int(parts[0])
                                self._strength["B"] = int(parts[1])
                                self._strength_max["A"] = int(parts[2])
                                self._strength_max["B"] = int(parts[3])
                            self._on_message({"type": "debug", "text": f"APP报告强度: A={parts[0]} B={parts[1]} maxA={parts[2]} maxB={parts[3]}"})
                            self._on_strength({
                                "a_strength": self._strength["A"],
                                "b_strength": self._strength["B"],
                                "a_limit": self._strength_max["A"],
                                "b_limit": self._strength_max["B"],
                            })
                            # Reactive: force strength back to limit when it deviates
                            # Skip during waveform playback to avoid flooding device with commands
                            if not self._waveform_active:
                                a_limit = self._on_get_a_limit() if self._on_get_a_limit else 200
                                b_limit = self._on_get_b_limit() if self._on_get_b_limit else 200
                                # Clamp to phone's reported max
                                a_limit = min(a_limit, self._strength_max.get("A", 200))
                                b_limit = min(b_limit, self._strength_max.get("B", 200))
                                if self._strength["A"] != 0 and self._strength["A"] != a_limit:
                                    self._on_message({"type": "debug", "text": f"矫正强度A: {self._strength['A']} -> {a_limit}"})
                                    await self._send_to_app("msg", f"strength-1+2+{a_limit}")
                                if self._strength["B"] != 0 and self._strength["B"] != b_limit:
                                    self._on_message({"type": "debug", "text": f"矫正强度B: {self._strength['B']} -> {b_limit}"})
                                    await self._send_to_app("msg", f"strength-2+2+{b_limit}")
                    else:
                        self._on_message({"type": "debug", "text": f"MSG: {msg_data}"})

                elif msg_type == "heartbeat":
                    self._on_message({"type": "debug", "text": "收到心跳"})
                else:
                    self._on_message({"type": "debug", "text": f"未知消息类型: {msg_type} data={str(msg_data)[:80]}"})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._on_message({"type": "warning", "text": f"连接异常: {e}"})
        finally:
            hb_task.cancel()
            if self._init_task and not self._init_task.done():
                self._init_task.cancel()
            try:
                tasks = [hb_task]
                if self._init_task:
                    tasks.append(self._init_task)
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            self._init_task = None
            with self._lock:
                if self._app_target_id:
                    self._uuid_to_ws.pop(self._app_target_id, None)
                self._bound = False
                self._app_target_id = None
                self._app_uuid_in_bind = None
            self._on_message({"type": "warning", "text": "APP已断开"})
            self._on_status("connected")

    async def _heartbeat(self, ws):
        while True:
            try:
                await asyncio.sleep(60)
                with self._lock:
                    target = self._app_target_id
                if target:
                    hb = _make_msg("heartbeat", client_id=self._local_client_id, target_id=target, message="200")
                    await ws.send(hb)
            except asyncio.CancelledError:
                raise  # Re-raise CancelledError so gather() sees clean cancellation
            except Exception as e:
                self._on_message({"type": "warning", "text": f"Heartbeat异常退出: {type(e).__name__}: {e}"})
                break

    async def _init_strength(self, a_limit: int = 200, b_limit: int = 200):
        try:
            await asyncio.sleep(2)  # Wait for APP to fully initialize
            # Match reference project: set to 1 first, let reactive correction raise to limit
            await self._send_to_app("msg", f"strength-1+2+{a_limit}")
            await asyncio.sleep(0.5)
            await self._send_to_app("msg", f"strength-2+2+{b_limit}")
            self._on_message({"type": "info", "text": f"强度初始化 A:{a_limit} B:{b_limit}"})
        except asyncio.CancelledError:
            raise  # Re-raise so gather() sees clean cancellation

    async def _send_to_app(self, msg_type: str, message: str):
        """Send a message to the APP."""
        with self._lock:
            target = self._app_target_id
            ws = self._uuid_to_ws.get(target) if target else None
        if not target:
            self._on_message({"type": "warning", "text": f"发送失败: 无targetId (msg={message[:30]})"})
            return
        if not ws:
            self._on_message({"type": "warning", "text": f"发送失败: 无websocket (msg={message[:30]})"})
            return
        msg = _make_msg(msg_type, client_id=self._local_client_id, target_id=target, message=message)
        try:
            await ws.send(msg)
            if message.startswith("pulse"):
                self._on_message({"type": "info", "text": f"✓ pulse已发送({len(message)}字符): {message[:60]}"})
            else:
                self._on_message({"type": "debug", "text": f"发送({len(message)}字符): {message[:60]}"})
        except Exception as e:
            self._on_message({"type": "warning", "text": f"发送异常: {type(e).__name__}: {e} (msg={message[:30]})"})

    def connect(self, host: str = "0.0.0.0", port: int = 9999):
        if self._running:
            return
        self._host = host
        self._port = port
        self._local_client_id = str(uuid.uuid4())
        self._running = True
        self._on_status("connecting")
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._running = False
        # First, reset strength to 0 so device stops output before we disconnect
        if self._loop and self._loop.is_running() and self._app_target_id:
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self._send_to_app("msg", "strength-1+2+0"), self._loop
                )
                fut.result(timeout=1)
                fut = asyncio.run_coroutine_threadsafe(
                    self._send_to_app("msg", "strength-2+2+0"), self._loop
                )
                fut.result(timeout=1)
            except Exception as e:
                logger.debug(f"归零强度异常: {e}")
            # Send protocol-level "break" message so DG-LAB App knows we disconnected
            try:
                with self._lock:
                    target = self._app_target_id
                break_msg = _make_msg("break", client_id=self._local_client_id,
                                      target_id=target or "", message="209")
                # Send directly to the ws object since _send_to_app uses "msg" type
                with self._lock:
                    ws = self._uuid_to_ws.get(target) if target else None
                if ws:
                    fut = asyncio.run_coroutine_threadsafe(ws.send(break_msg), self._loop)
                    fut.result(timeout=1)
            except Exception as e:
                logger.debug(f"发送break消息异常: {e}")
        # Clear internal state
        with self._lock:
            self._uuid_to_ws.clear()
            self._bound = False
            self._app_target_id = None
            self._app_uuid_in_bind = None
        # Signal the server to stop gracefully
        # _ws_server.close() + wait_closed() will properly close all client connections
        # (sends close frames and waits for handshake completion)
        if self._loop and self._loop.is_running() and self._stop_event:
            try:
                self._loop.call_soon_threadsafe(self._stop_event.set)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                # Thread didn't exit gracefully, force stop the loop
                if self._loop:
                    try:
                        self._loop.call_soon_threadsafe(self._loop.stop)
                    except Exception:
                        pass
                    self._thread.join(timeout=1)
            self._thread = None
        self._server_socket = None
        self._on_status("disconnected")

    @property
    def is_paired(self) -> bool:
        with self._lock:
            return self._bound

    @property
    def client_id(self) -> Optional[str]:
        return self._local_client_id

    def set_strength(self, channel: str, value: int):
        if not self.is_paired:
            return
        ch_num = "1" if channel.upper() == "A" else "2"
        value = max(0, min(200, value))
        if self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._send_to_app("msg", f"strength-{ch_num}+2+{value}"), self._loop
                )
            except RuntimeError:
                pass

    def force_strength(self, a_limit: int, b_limit: int):
        """Immediately force both channels to their limits."""
        if not self.is_paired:
            return
        # Clamp to phone's reported max — phone rejects values above its slider
        with self._lock:
            a_val = min(a_limit, self._strength_max.get("A", 200))
            b_val = min(b_limit, self._strength_max.get("B", 200))
        if self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._send_to_app("msg", f"strength-1+2+{a_val}"), self._loop
                )
                asyncio.run_coroutine_threadsafe(
                    self._send_to_app("msg", f"strength-2+2+{b_val}"), self._loop
                )
            except RuntimeError:
                pass

    def send_waveform(self, channel: str, hex_data, duration: int = 5):
        """Send waveform data to device. No clear needed - device replaces queue automatically."""
        if not self.is_paired:
            self._on_message({"type": "warning", "text": f"send_waveform 跳过: 未配对"})
            return
        if isinstance(hex_data, list):
            pass  # already a list
        elif isinstance(hex_data, str):
            try:
                hex_data = json.loads(hex_data)  # parse JSON string to list
            except (json.JSONDecodeError, ValueError):
                self._on_message({"type": "warning", "text": f"send_waveform 跳过: JSON解析失败 type={type(hex_data)}"})
                return
        else:
            self._on_message({"type": "warning", "text": f"send_waveform 跳过: 未知类型 {type(hex_data)}"})
            return
        if not isinstance(hex_data, list) or not hex_data:
            self._on_message({"type": "warning", "text": f"send_waveform 跳过: 数据为空 type={type(hex_data)}"})
            return
        self._waveform_active = True
        ch_name = channel.upper()  # pulse uses letters: A, B
        # pydglab_ws limit: max 86 entries per message, max 1950 chars
        CHUNK_SIZE = 86
        if self._loop and self._loop.is_running():
            self._on_message({"type": "info", "text": f"发送波形 {ch_name}: {len(hex_data)}条数据"})
            for i in range(0, len(hex_data), CHUNK_SIZE):
                chunk = hex_data[i:i + CHUNK_SIZE]
                wavestr = json.dumps(chunk, separators=(",", ":"))
                asyncio.run_coroutine_threadsafe(
                    self._send_to_app("msg", f"pulse-{ch_name}:{wavestr}"), self._loop
                )
        else:
            self._on_message({"type": "warning", "text": f"send_waveform 跳过: loop不可用"})

    def clear_waveform(self, channel: str):
        if not self.is_paired:
            return
        self._waveform_active = False
        ch_num = "1" if channel.upper() == "A" else "2"
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_to_app("msg", f"clear-{ch_num}"), self._loop
            )

    def stop_waveform(self):
        """Mark waveform as inactive without sending clear to device."""
        self._waveform_active = False
