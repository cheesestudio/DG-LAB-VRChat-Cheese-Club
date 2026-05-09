import logging
import threading
from settings import Settings
from themes import get_theme
from log_monitor import LogMonitor
from ws_client import WSClient
from waveform import generate_ab_waveforms
from avatar_handler import AvatarManager
from gui.main_window import MainWindow
from http_server import HttpServer

logger = logging.getLogger(__name__)


class App:
    def __init__(self):
        self._settings = Settings()
        self._window = None
        self._log_monitor = None
        self._ws_client = None
        self._avatar_manager = None
        self._osc_server = None
        self._osc_client = None
        self._chatbox_running = False
        self._current_theme_name = self._settings.get("theme", "dark")
        self._shock_remaining_a = 0
        self._shock_remaining_b = 0
        self._shock_end_time = 0
        self._shock_recent_events_log = []   # 日志触发的 1s 窗口安全限制
        self._shock_recent_events_http = []  # HTTP 触发的 1s 窗口安全限制
        self._waveform_name_a = ""
        self._waveform_name_b = ""
        self._waveform_feeder_running = False
        # Statistics: per-channel total seconds and intensity*time
        self._stats_a_seconds = 0
        self._stats_b_seconds = 0
        self._stats_a_intensity_time = 0.0
        self._stats_b_intensity_time = 0.0
        self._http_server = HttpServer(port=self._settings.get("http_port", 8800))

    def run(self):
        theme = get_theme(self._current_theme_name)
        self._window = MainWindow(self, theme=theme)
        self._load_settings_to_ui()
        self._start_log_monitor()
        self._log_to_console("软件已启动", "info")
        # Auto-connect everything
        self._window.after(500, self._auto_connect)
        # Register chatbox enabled callback
        self._window.settings_panel.set_on_chatbox_enabled(self._on_chatbox_enabled)
        # Start HTTP server for VRChat ShockingManager compatibility
        if self._http_server.start(self):
            self._log_to_console(f"HTTP 服务已启动 (端口:{self._settings.get('http_port', 8800)})", "info")
        self._window.run()

    @staticmethod
    def _port_in_use(port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return False
            except OSError:
                return True

    def _auto_connect(self):
        """Auto-start all connections on startup."""
        self._window.connection_panel._start_btn.configure(state="disabled")
        self._window.connection_panel._stop_btn.configure(state="normal")
        # Start WebSocket server
        port = self._window.connection_panel.get_port()
        if self._port_in_use(port):
            self._log_to_console(f"端口 {port} 已被占用，跳过WebSocket启动", "warning")
        else:
            self.on_connect()
        # Start OSC (chatbox + avatar)
        def _start_osc_auto():
            self._window.osc_panel._connect_btn.configure(state="disabled")
            self._window.osc_panel._disconnect_btn.configure(state="normal")
            self._window.osc_panel._connected = True
            self._window.osc_panel._status_label.configure(text="连接中...")
            self._window.osc_panel._draw_dot(self._window.osc_panel._theme.get("accent_orange", "#ffb74d"))
            chatbox_port = self._window.osc_panel.get_chatbox_port()
            from pythonosc import udp_client
            try:
                self._osc_client = udp_client.SimpleUDPClient("127.0.0.1", chatbox_port)
                self._chatbox_running = True
                self._log_to_console(f"Chatbox 已连接 (端口:{chatbox_port})", "info")
            except Exception as e:
                self._log_to_console(f"Chatbox启动失败: {e}", "error")
            self._start_avatar(self._window.osc_panel.get_avatar_port(),
                              self._window.osc_panel.get_mode_a(),
                              self._window.osc_panel.get_mode_b())
            self._send_chatbox_status()
            self._window.osc_panel.set_status("connected")
        self._window.after(1000, _start_osc_auto)

    def _start_log_monitor(self):
        log_dir = self._settings.get("log_dir_override", "")
        self._log_monitor = LogMonitor(
            on_shock_event=self._on_shock_event,
            on_log_line=self._on_log_line,
            log_dir=log_dir,
            poll_interval=self._settings.get("poll_interval", 0.5),
            idle_check_interval=self._settings.get("idle_check_interval", 5),
        )
        self._log_monitor.start()

    def _on_shock_event(self, event: dict):
        import time as _time
        mode = event.get("mode", "instant")
        seconds = event.get("seconds", 3)
        _ = event.get("hand", "A")  # reserved for future single-channel support

        mapping = self._settings.get("seconds_mapping", {})
        base_intensity = mapping.get(str(seconds), seconds * 20)
        a_limit = self._window.settings_panel.get_a_limit()
        b_limit = self._window.settings_panel.get_b_limit()
        a_intensity = min(base_intensity, a_limit)
        b_intensity = min(base_intensity, b_limit)

        ui_mode = self._window.settings_panel.get_mode()
        wf_mode = self._window.settings_panel.get_waveform_mode()

        # Accumulate remaining time with 1s/10s safety limit
        now = _time.time()
        self._shock_recent_events_log.append((now, seconds))
        self._shock_recent_events_log = [(t, s) for t, s in self._shock_recent_events_log if now - t <= 1.0]
        recent_sum = sum(s for _, s in self._shock_recent_events_log)
        if recent_sum > 10:
            # Clamp: only allow what fits within the 10s limit
            allowed = max(0, 10 - (recent_sum - seconds))
            seconds = allowed
            self._shock_recent_events[-1] = (now, seconds)
        if seconds <= 0:
            self._log_to_console(f"安全限制: 1秒内累计已超10秒，忽略本次电击", "warning")
            return
        # 30-second total cap (always enforce, even across shock gaps)
        if now < self._shock_end_time:
            current_remaining = self._shock_end_time - now
        else:
            current_remaining = 0
        if current_remaining + seconds > 30:
            seconds = max(0, 30 - current_remaining)
            if seconds <= 0:
                self._log_to_console("安全限制: 总时长已达30秒上限", "warning")
                return
        if now < self._shock_end_time:
            self._shock_remaining_a += seconds
            self._shock_remaining_b += seconds
        else:
            self._shock_remaining_a = seconds
            self._shock_remaining_b = seconds
        self._shock_end_time = now + self._shock_remaining_a

        custom_wf = self._window.settings_panel.get_custom_waveform() if wf_mode == "custom" else ""
        a_wave, b_wave, a_name, b_name = generate_ab_waveforms(
            seconds, a_intensity, b_intensity, ui_mode, wf_mode, alternate=True,
            custom_waveform=custom_wf,
        )
        self._waveform_name_a = a_name
        self._waveform_name_b = b_name

        if self._ws_client and self._ws_client.is_paired:
            # Only clear if no shock is currently playing
            if now >= self._shock_end_time:
                self._ws_client.clear_waveform("A")
                self._ws_client.clear_waveform("B")
            # Set strength before waveform (use after to avoid blocking main thread)
            self._ws_client.force_strength(a_limit, b_limit)
            self._window.after(300, lambda: self._ws_client.send_waveform("A", a_wave, duration=seconds))
            self._window.after(400, lambda: self._ws_client.send_waveform("B", b_wave, duration=seconds))
            self._log_to_console(
                f"电击: {seconds}秒 | A:{a_intensity}({a_name}) B:{b_intensity}({b_name}) | "
                f"{'一键开火' if ui_mode == 'instant' else '温柔加力'}",
                "shock",
            )
            self._stats_a_seconds += seconds
            self._stats_b_seconds += seconds
            self._stats_a_intensity_time += a_intensity * seconds
            self._stats_b_intensity_time += b_intensity * seconds
            self._window.after(0, lambda: self._window.settings_panel.update_stats(
                self._stats_a_seconds, self._stats_b_seconds,
                self._stats_a_intensity_time, self._stats_b_intensity_time,
            ))
            self._start_waveform_feeder()
        else:
            self._log_to_console(
                f"电击: {seconds}秒 A:{a_intensity} B:{b_intensity} (未发送-等待APP连接)",
                "shock",
            )

    def _start_waveform_feeder(self):
        if not self._waveform_feeder_running:
            self._waveform_feeder_running = True
            # Read UI values on main thread, then run feeder in background
            self._feeder_ui_mode = self._window.settings_panel.get_mode()
            self._feeder_wf_mode = self._window.settings_panel.get_waveform_mode()
            self._feeder_a_limit = self._window.settings_panel.get_a_limit()
            self._feeder_b_limit = self._window.settings_panel.get_b_limit()
            self._feeder_custom_wf = (
                self._window.settings_panel.get_custom_waveform()
                if self._feeder_wf_mode == "custom" else ""
            )
            threading.Thread(target=self._waveform_feeder_thread, daemon=True).start()

    def _waveform_feeder_thread(self):
        import time as _time
        while self._waveform_feeder_running:
            now = _time.time()
            remaining = self._shock_end_time - now
            if remaining <= 0 or not self._ws_client or not self._ws_client.is_paired:
                self._waveform_feeder_running = False
                break
            chunk_sec = 1
            a_wave, b_wave, _, _ = generate_ab_waveforms(
                chunk_sec, self._feeder_a_limit, self._feeder_b_limit,
                self._feeder_ui_mode, self._feeder_wf_mode, alternate=True,
                custom_waveform=self._feeder_custom_wf,
            )
            self._ws_client.send_waveform("A", a_wave, duration=chunk_sec)
            self._ws_client.send_waveform("B", b_wave, duration=chunk_sec)
            # Update stats on main thread
            stats = (self._stats_a_seconds, self._stats_b_seconds,
                     self._stats_a_intensity_time, self._stats_b_intensity_time)
            try:
                self._window.after(0, lambda s=stats: self._window.settings_panel.update_stats(*s))
            except Exception:
                pass
            _time.sleep(0.8)

    def get_stats(self) -> dict:
        return {
            "a_seconds": self._stats_a_seconds,
            "b_seconds": self._stats_b_seconds,
            "a_intensity_time": self._stats_a_intensity_time,
            "b_intensity_time": self._stats_b_intensity_time,
        }

    def _on_log_line(self, line: str):
        if "[DGLABCheeseShocking]" in line:
            pass
        elif "[ShockingManager]" in line:
            cleaned = self._clean_log_line(line)
            self._log_to_console(cleaned, "recv")
        elif "ShockingPlayer" in line:
            cleaned = self._clean_log_line(line)
            self._log_to_console(cleaned, "recv")
        elif line.startswith("[日志]"):
            self._log_to_console(line, "info")

    def _clean_log_line(self, line: str) -> str:
        if "Debug" in line:
            idx = line.find("Debug")
            if idx >= 0:
                rest = line[idx:]
                rest = rest.replace("Debug", "", 1).lstrip(" -")
                return rest.strip()
        return line

    def _log_to_console(self, text: str, tag: str = "info"):
        if self._window:
            self._window.after(0, lambda: self._window.console_panel.append(text, tag))

    # --- Theme ---
    def on_theme_toggle(self):
        self._current_theme_name = "light" if self._current_theme_name == "dark" else "dark"
        self._settings.set("theme", self._current_theme_name)
        self._settings.save()
        theme = get_theme(self._current_theme_name)
        self._window.after(0, lambda: self._apply_theme(theme))

    def _apply_theme(self, theme: dict):
        self._window.apply_theme(theme)
        self._window.settings_panel.set_theme_button_text(self._current_theme_name)

    # --- Connection (server mode) ---
    def on_connect(self):
        port = self._window.connection_panel.get_port()
        self._ws_client = WSClient(
            port=port,
            on_status_change=self._on_ws_status,
            on_qr_url=self._on_qr_url,
            on_message=self._on_ws_message,
            on_strength_update=self._on_strength_update,
            on_get_a_limit=lambda: self._window.settings_panel.get_a_limit(),
            on_get_b_limit=lambda: self._window.settings_panel.get_b_limit(),
        )
        self._ws_client.connect(host="0.0.0.0", port=port)
        from ws_client import _get_local_ip
        self._log_to_console(f"启动WebSocket服务: {_get_local_ip()}:{port}", "info")

    def on_disconnect(self):
        if self._ws_client:
            self._ws_client.disconnect()
            self._ws_client = None
        self._stop_waveform_monitor()
        self._log_to_console("服务已停止", "warning")

    def _start_waveform_monitor(self):
        if self._ws_client:
            self._window.waveform_panel.start(
                get_a_value=lambda: self._ws_client._strength.get("A", 0) if self._ws_client else 0,
                get_b_value=lambda: self._ws_client._strength.get("B", 0) if self._ws_client else 0,
            )

    def _stop_waveform_monitor(self):
        if self._window:
            self._window.waveform_panel.stop()

    def _on_ws_status(self, status: str):
        if self._window:
            self._window.after(0, lambda: self._window.connection_panel.set_status(status))
            if status == "paired":
                self._window.after(0, self._start_waveform_monitor)
            elif status in ("connected", "disconnected"):
                self._window.after(0, self._stop_waveform_monitor)

    def _on_qr_url(self, url: str):
        if self._window:
            self._window.after(0, lambda: self._window.connection_panel.set_qr(
                url, self._ws_client.client_id if self._ws_client else ""
            ))

    def _on_ws_message(self, msg: dict):
        msg_type = msg.get("type", "")
        text = msg.get("text", "")
        if msg_type == "error":
            self._log_to_console(text, "error")
        elif msg_type == "warning":
            self._log_to_console(text, "warning")
        elif msg_type == "debug":
            self._log_to_console(text, "debug")
        elif msg_type == "info":
            self._log_to_console(text, "info")

    def _on_strength_update(self, data: dict):
        if self._window:
            self._window.after(0, lambda: self._window.settings_panel.update_strength(
                data.get("a_strength", 0), data.get("b_strength", 0)
            ))

    # --- VRChat OSC ---
    def on_osc_toggle(self, connected: bool):
        if connected:
            self._start_osc()
        else:
            self._stop_chatbox()

    def _start_osc(self):
        chatbox_port = self._window.osc_panel.get_chatbox_port()
        avatar_port = self._window.osc_panel.get_avatar_port()
        mode_a = self._window.osc_panel.get_mode_a()
        mode_b = self._window.osc_panel.get_mode_b()

        from pythonosc import udp_client

        # 1. Chatbox client (send to VRChat)
        try:
            self._osc_client = udp_client.SimpleUDPClient("127.0.0.1", chatbox_port)
            self._chatbox_running = True
            self._log_to_console(f"Chatbox 已连接 (端口:{chatbox_port})", "info")
        except Exception as e:
            self._log_to_console(f"Chatbox启动失败: {e}", "error")

        # 2. Avatar OSC server (receive from VRChat) - always start, never stopped by user
        self._start_avatar(avatar_port, mode_a, mode_b)

        self._send_chatbox_status()

    def _start_avatar(self, avatar_port, mode_a, mode_b):
        if self._avatar_manager is not None:
            return  # already running
        try:
            from pythonosc import dispatcher, osc_server
            d = dispatcher.Dispatcher()
            d.set_default_handler(self._on_osc_message)

            a_params = self._settings.get("avatar_channel_a_params", [])
            b_params = self._settings.get("avatar_channel_b_params", [])

            self._avatar_manager = AvatarManager(
                on_wave=self._on_avatar_wave,
                on_clear=self._on_avatar_clear,
                on_log=self._log_to_console,
            )
            a_config = self._settings.get("avatar_channel_a_config", {})
            b_config = self._settings.get("avatar_channel_b_config", {})
            self._avatar_manager.configure(a_params, mode_a, a_config, b_params, mode_b, b_config)

            # 去重：同一地址只绑定一次，先绑定的通道优先
            bound_paths = set()
            for path in a_params:
                if path not in bound_paths:
                    d.map(path, self._avatar_manager._channels["A"].on_osc)
                    bound_paths.add(path)
            for path in b_params:
                if path not in bound_paths:
                    d.map(path, self._avatar_manager._channels["B"].on_osc)
                    bound_paths.add(path)

            self._avatar_manager._running = True
            self._avatar_manager._start_bg_tasks()

            import socket as _sock

            class ReusableOSCUDPServer(osc_server.ThreadingOSCUDPServer):
                allow_reuse_address = True

                def server_bind(self):
                    self.socket.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                    super().server_bind()

            self._osc_server = ReusableOSCUDPServer(
                ("127.0.0.1", avatar_port), d
            )
            threading.Thread(target=self._osc_server.serve_forever, daemon=True).start()
            self._log_to_console(f"Avatar OSC 已连接 (端口:{avatar_port})", "info")
        except Exception as e:
            self._log_to_console(f"Avatar OSC启动失败: {e}", "error")

    def _stop_chatbox(self):
        self._chatbox_running = False
        if self._osc_client:
            self._osc_client = None
        self._log_to_console("Chatbox 已断开", "info")

    def _send_chatbox(self, text: str):
        if not self._osc_client:
            return
        if not self._window.settings_panel.get_chatbox_enabled():
            return
        try:
            self._osc_client.send_message("/chatbox/input", [text, True, False])
        except Exception:
            pass

    def _send_chatbox_status(self):
        import time as _time
        if not self._chatbox_running:
            return
        if not self._window.settings_panel.get_chatbox_enabled():
            self._window.after(1000, self._send_chatbox_status)
            return
        if self._ws_client and self._ws_client.is_paired:
            a_cur = self._ws_client._strength.get("A", 0)
            b_cur = self._ws_client._strength.get("B", 0)
            custom_line = self._window.settings_panel.get_custom_chatbox()
            toggles = self._window.settings_panel.get_chatbox_toggles()
            # Calculate remaining shock time
            now = _time.time()
            remaining = max(0, int(self._shock_end_time - now))
            lines = []
            # Line 1: Title
            if toggles.get("line1", True):
                lines.append("[芝士郊狼台球后援会]")
            # Line 2: Strength
            if toggles.get("line2", True):
                lines.append(f"A: {a_cur} | B: {b_cur}")
            # Line 3: Remaining time (only when active)
            if toggles.get("line3", True) and remaining > 0:
                lines.append(f"剩余电击: {remaining}秒")
            # Line 4: Waveform names (active shock names or current selection)
            if toggles.get("line4", True):
                name_parts = []
                if self._waveform_name_a:
                    name_parts.append(f"A:{self._waveform_name_a}")
                elif self._waveform_name_b:
                    name_parts.append(f"B:{self._waveform_name_b}")
                else:
                    wf_mode = self._window.settings_panel.get_waveform_mode()
                    if wf_mode == "custom":
                        cw = self._window.settings_panel.get_custom_waveform()
                        if cw:
                            name_parts.append(f"波形:{cw}")
                    else:
                        name_parts.append("波形:随机")
                if name_parts:
                    lines.append(" ".join(name_parts))
            # Line 5: Custom
            if toggles.get("line5", True) and custom_line:
                lines.append(custom_line)
            # Footer: QQ + version (always show)
            lines.append("QQ:757992539 | v1.2.2")
            self._send_chatbox("\n".join(lines))
        if self._chatbox_running:
            self._window.after(1000, self._send_chatbox_status)

    def _on_osc_message(self, address: str, *args):
        """Default handler for unmatched OSC messages - display in params."""
        if self._window:
            params = {address: args[0] if len(args) == 1 else args}
            panel = self._window.osc_panel
            self._window.after(0, lambda p=params, pan=panel: pan.update_params(p))

    def _on_avatar_wave(self, channel: str, wave_hex):
        if self._ws_client and self._ws_client.is_paired:
            self._ws_client.send_waveform(channel, wave_hex)

    def _on_avatar_clear(self, channel: str):
        if self._ws_client and self._ws_client.is_paired:
            self._ws_client.clear_waveform(channel)

    def _on_chatbox_enabled(self, enabled: bool):
        self._settings.set("chatbox_enabled", enabled)
        self._settings.save()
        state = "开启" if enabled else "关闭"
        self._log_to_console(f"Chatbox显示已{state}", "info")
        if not enabled and self._osc_client:
            try:
                self._osc_client.send_message("/chatbox/input", ["", True, False])
            except Exception:
                pass

    # --- Settings ---
    def on_settings_change(self):
        self._save_settings_from_ui()

    def on_mapping_change(self):
        self._save_settings_from_ui()

    def on_test_shock(self):
        """Test shock: both channels at max for 3 seconds."""
        if not self._ws_client or not self._ws_client.is_paired:
            self._log_to_console("测试失败: APP未连接", "error")
            return
        a_limit = self._window.settings_panel.get_a_limit()
        b_limit = self._window.settings_panel.get_b_limit()
        self._ws_client.clear_waveform("A")
        self._ws_client.clear_waveform("B")
        a_wave, b_wave, _, _ = generate_ab_waveforms(
            3, a_limit, b_limit, "instant", "library", alternate=False,
        )
        self._ws_client.send_waveform("A", a_wave, duration=3)
        self._ws_client.send_waveform("B", b_wave, duration=3)
        self._ws_client.force_strength(a_limit, b_limit)
        self._log_to_console(f"测试电击: 3秒双通道 A:{a_limit} B:{b_limit}", "shock")
        self._send_chatbox(f"[测试] 3秒双通道 | A:{a_limit} B:{b_limit}")

    def on_http_shock(self, mode: int, seconds: int):
        """Handle shock trigger from VRChat ShockingManager HTTP request."""
        if not self._ws_client or not self._ws_client.is_paired:
            return
        a_limit = self._window.settings_panel.get_a_limit()
        b_limit = self._window.settings_panel.get_b_limit()
        ui_mode = self._window.settings_panel.get_mode()
        wf_mode = self._window.settings_panel.get_waveform_mode()

        # Accumulate remaining time
        import time as _time
        now = _time.time()
        self._shock_recent_events_http.append((now, seconds))
        self._shock_recent_events_http = [(t, s) for t, s in self._shock_recent_events_http if now - t <= 1.0]
        recent_sum = sum(s for _, s in self._shock_recent_events_http)
        if recent_sum > 10:
            allowed = max(0, 10 - (recent_sum - seconds))
            seconds = allowed
            self._shock_recent_events[-1] = (now, seconds)
        if seconds <= 0:
            return
        # 30-second total cap (always enforce, even across shock gaps)
        if now < self._shock_end_time:
            current_remaining = self._shock_end_time - now
        else:
            current_remaining = 0
        if current_remaining + seconds > 30:
            seconds = max(0, 30 - current_remaining)
            if seconds <= 0:
                return
        if now < self._shock_end_time:
            self._shock_remaining_a += seconds
            self._shock_remaining_b += seconds
        else:
            self._shock_remaining_a = seconds
            self._shock_remaining_b = seconds
        self._shock_end_time = now + self._shock_remaining_a

        mapping = self._settings.get("seconds_mapping", {})
        base_intensity = mapping.get(str(seconds), seconds * 20)
        a_intensity = min(base_intensity, a_limit)
        b_intensity = min(base_intensity, b_limit)

        self._ws_client.force_strength(a_limit, b_limit)

        # Only clear if no shock is currently playing
        should_clear = now >= self._shock_end_time
        # Determine which channels to send
        custom_wf = self._window.settings_panel.get_custom_waveform() if wf_mode == "custom" else ""
        if mode == 0:  # A only
            a_wave, _, a_name, _ = generate_ab_waveforms(
                seconds, a_intensity, 0, ui_mode, wf_mode, alternate=False,
                custom_waveform=custom_wf,
            )
            self._waveform_name_a = a_name
            self._waveform_name_b = ""
            if should_clear:
                self._ws_client.clear_waveform("A")
            self._ws_client.send_waveform("A", a_wave, duration=seconds)
        elif mode == 1:  # B only
            b_wave, _, _, b_name = generate_ab_waveforms(
                seconds, 0, b_intensity, ui_mode, wf_mode, alternate=False,
                custom_waveform=custom_wf,
            )
            self._waveform_name_a = ""
            self._waveform_name_b = b_name
            if should_clear:
                self._ws_client.clear_waveform("B")
            self._ws_client.send_waveform("B", b_wave, duration=seconds)
        else:  # AB both
            a_wave, b_wave, a_name, b_name = generate_ab_waveforms(
                seconds, a_intensity, b_intensity, ui_mode, wf_mode, alternate=True,
                custom_waveform=custom_wf,
            )
            self._waveform_name_a = a_name
            self._waveform_name_b = b_name
            if should_clear:
                self._ws_client.clear_waveform("A")
                self._ws_client.clear_waveform("B")
            self._ws_client.send_waveform("A", a_wave, duration=seconds)
            self._ws_client.send_waveform("B", b_wave, duration=seconds)

        # Track stats
        if mode == 0:
            self._stats_a_seconds += seconds
            self._stats_a_intensity_time += a_intensity * seconds
        elif mode == 1:
            self._stats_b_seconds += seconds
            self._stats_b_intensity_time += b_intensity * seconds
        else:
            self._stats_a_seconds += seconds
            self._stats_b_seconds += seconds
            self._stats_a_intensity_time += a_intensity * seconds
            self._stats_b_intensity_time += b_intensity * seconds
        self._log_to_console(
            f"HTTP电击: {seconds}秒 | mode={mode} | "
            f"A:{a_intensity} B:{b_intensity} | "
            f"{'一键开火' if ui_mode == 'instant' else '温柔加力'}",
            "shock",
        )

    def _load_settings_to_ui(self):
        s = self._settings
        self._window.connection_panel.set_port(s.get("port", 9999))
        self._window.settings_panel.set_a_limit(s.get("a_limit", 200))
        self._window.settings_panel.set_b_limit(s.get("b_limit", 200))
        self._window.settings_panel.set_mode(s.get("mode", "instant"))
        self._window.settings_panel.set_channel(s.get("channel", "A"))
        self._window.settings_panel.set_waveform_mode(s.get("waveform_mode", "library"))
        self._window.settings_panel.set_custom_waveform(s.get("custom_waveform", ""))
        self._window.mapping_panel.set_mapping(s.get("seconds_mapping", {}))
        self._window.osc_panel.set_chatbox_port(s.get("osc_port", 9000))
        self._window.osc_panel.set_avatar_port(s.get("avatar_osc_port", 9001))
        self._window.osc_panel.set_mode_a(s.get("avatar_channel_a_mode", "distance"))
        self._window.osc_panel.set_mode_b(s.get("avatar_channel_b_mode", "distance"))
        self._window.settings_panel.set_chatbox_enabled(s.get("chatbox_enabled", True))
        self._window.settings_panel.set_custom_chatbox(s.get("custom_chatbox", ""))
        self._window.settings_panel.set_chatbox_toggles(s.get("chatbox_toggles", {}))
        self._window.settings_panel.set_theme_button_text(self._current_theme_name)

    def _save_settings_from_ui(self):
        s = self._settings
        s.set("port", self._window.connection_panel.get_port())
        s.set("a_limit", self._window.settings_panel.get_a_limit())
        s.set("b_limit", self._window.settings_panel.get_b_limit())
        s.set("mode", self._window.settings_panel.get_mode())
        s.set("channel", self._window.settings_panel.get_channel())
        s.set("waveform_mode", self._window.settings_panel.get_waveform_mode())
        s.set("custom_waveform", self._window.settings_panel.get_custom_waveform())
        s.set("osc_port", self._window.osc_panel.get_chatbox_port())
        s.set("avatar_osc_port", self._window.osc_panel.get_avatar_port())
        s.set("avatar_channel_a_mode", self._window.osc_panel.get_mode_a())
        s.set("avatar_channel_b_mode", self._window.osc_panel.get_mode_b())
        s.set("chatbox_enabled", self._window.settings_panel.get_chatbox_enabled())
        s.set("custom_chatbox", self._window.settings_panel.get_custom_chatbox())
        s.set("chatbox_toggles", self._window.settings_panel.get_chatbox_toggles())
        s.set("seconds_mapping", self._window.mapping_panel.get_mapping())
        s.save()

    def on_close(self):
        import logging
        log = logging.getLogger(__name__)
        try:
            log.info("on_close start")
            self._chatbox_running = False
            if self._http_server:
                self._http_server.stop()
                self._http_server = None
                log.info("http stopped")

            if self._log_monitor:
                self._log_monitor.stop()
                self._log_monitor = None
                log.info("log_monitor stopped")

            if self._ws_client:
                self._ws_client.disconnect()
                self._ws_client = None
                log.info("ws stopped")

            if self._osc_server:
                try:
                    self._osc_server.shutdown()
                except Exception:
                    pass
                try:
                    self._osc_server.server_close()
                except Exception:
                    pass
                self._osc_server = None
                log.info("osc_server stopped")

            if self._avatar_manager:
                self._avatar_manager.stop()
                self._avatar_manager = None
                log.info("avatar stopped")

            self._save_settings_from_ui()
            log.info("settings saved")

            if self._window:
                root = self._window._root
                self._window = None
                root.after(50, root.destroy)
                log.info("window destroyed")
        except Exception as e:
            log.error(f"on_close error: {e}")
