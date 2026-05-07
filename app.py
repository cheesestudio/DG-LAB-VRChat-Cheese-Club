import logging
import threading
from settings import Settings
from themes import get_theme
from log_monitor import LogMonitor
from ws_client import WSClient
from waveform import generate_ab_waveforms, waveform_to_display_data
from avatar_handler import AvatarManager
from gui.main_window import MainWindow

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
        self._shock_recent_events = []  # [(timestamp, seconds), ...] for 1s window safety
        self._waveform_name_a = ""
        self._waveform_name_b = ""

    def run(self):
        theme = get_theme(self._current_theme_name)
        self._window = MainWindow(self, theme=theme)
        self._load_settings_to_ui()
        self._start_log_monitor()
        self._log_to_console("软件已启动", "info")
        # Auto-connect everything
        self._window.after(500, self._auto_connect)
        # Register chatbox toggle callback
        self._window.osc_panel.set_on_chatbox_toggle(self._on_chatbox_toggle)
        self._window.run()

    def _auto_connect(self):
        """Auto-start all connections on startup."""
        # Update connection panel button state
        self._window.connection_panel._start_btn.configure(state="disabled")
        self._window.connection_panel._stop_btn.configure(state="normal")
        # Start WebSocket server
        self.on_connect()
        # Start OSC (chatbox + avatar) - update button state first
        def _start_osc_auto():
            self._window.osc_panel._connect_btn.configure(state="disabled")
            self._window.osc_panel._disconnect_btn.configure(state="normal")
            self._window.osc_panel._connected = True
            self._window.osc_panel._status_label.configure(text="连接中...")
            self._window.osc_panel._draw_dot(self._window.osc_panel._theme.get("accent_orange", "#ffb74d"))
            self.on_osc_toggle(True)
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
        hand = event.get("hand", "A")

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
        self._shock_recent_events.append((now, seconds))
        # Remove events older than 1 second
        self._shock_recent_events = [(t, s) for t, s in self._shock_recent_events if now - t <= 1.0]
        # Sum of durations in the last 1 second
        recent_sum = sum(s for _, s in self._shock_recent_events)
        if recent_sum > 10:
            # Clamp: only allow what fits within the 10s limit
            allowed = max(0, 10 - (recent_sum - seconds))
            seconds = allowed
            self._shock_recent_events[-1] = (now, seconds)
        if seconds <= 0:
            self._log_to_console(f"安全限制: 1秒内累计已超10秒，忽略本次电击", "warning")
            return
        if now < self._shock_end_time:
            self._shock_remaining_a += seconds
            self._shock_remaining_b += seconds
        else:
            self._shock_remaining_a = seconds
            self._shock_remaining_b = seconds
        self._shock_end_time = now + self._shock_remaining_a

        a_wave, b_wave, a_name, b_name = generate_ab_waveforms(
            seconds, a_intensity, b_intensity, ui_mode, wf_mode, alternate=True,
        )
        self._waveform_name_a = a_name
        self._waveform_name_b = b_name

        a_display = waveform_to_display_data(a_wave)
        b_display = waveform_to_display_data(b_wave)
        self._window.after(0, lambda: self._window.waveform_panel.update_waveform(
            a_display, b_display, seconds, a_intensity, b_intensity, ui_mode, a_name, b_name,
        ))

        if self._ws_client and self._ws_client.is_paired:
            self._ws_client.clear_waveform("A")
            self._ws_client.clear_waveform("B")
            # Set strength before waveform
            self._ws_client.force_strength(a_limit, b_limit)
            import time as _t
            _t.sleep(0.3)
            self._ws_client.send_waveform("A", a_wave, duration=seconds)
            _t.sleep(0.1)
            self._ws_client.send_waveform("B", b_wave, duration=seconds)
            self._log_to_console(
                f"电击: {seconds}秒 | A:{a_intensity}({a_name}) B:{b_intensity}({b_name}) | "
                f"{'一键开火' if ui_mode == 'instant' else '温柔加力'}",
                "shock",
            )
        else:
            self._log_to_console(
                f"电击: {seconds}秒 A:{a_intensity} B:{b_intensity} (未发送-等待APP连接)",
                "shock",
            )

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
        self._log_to_console("服务已停止", "warning")

    def _on_ws_status(self, status: str):
        if self._window:
            self._window.after(0, lambda: self._window.connection_panel.set_status(status))

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

    # --- VRChat OSC (merged: chatbox + avatar) ---
    def on_osc_toggle(self, connected: bool):
        if connected:
            self._start_osc()
        else:
            self._stop_osc()

    def _start_osc(self):
        chatbox_port = self._window.osc_panel.get_chatbox_port()
        avatar_port = self._window.osc_panel.get_avatar_port()
        mode_a = self._window.osc_panel.get_mode_a()
        mode_b = self._window.osc_panel.get_mode_b()

        from pythonosc import udp_client

        # 1. Chatbox client (send to VRChat) - always create first
        try:
            self._osc_client = udp_client.SimpleUDPClient("127.0.0.1", chatbox_port)
            self._chatbox_running = True
            self._log_to_console(f"Chatbox 已连接 (端口:{chatbox_port})", "info")
        except Exception as e:
            self._log_to_console(f"Chatbox启动失败: {e}", "error")

        # 2. Avatar OSC server (receive from VRChat)
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

            for path in a_params:
                d.map(path, self._avatar_manager._channels["A"].on_osc)
            for path in b_params:
                d.map(path, self._avatar_manager._channels["B"].on_osc)

            self._avatar_manager._running = True
            self._avatar_manager._start_bg_tasks()

            self._osc_server = osc_server.ThreadingOSCUDPServer(
                ("127.0.0.1", avatar_port), d
            )
            threading.Thread(target=self._osc_server.serve_forever, daemon=True).start()
            self._log_to_console(f"Avatar OSC 已连接 (端口:{avatar_port})", "info")
        except Exception as e:
            self._log_to_console(f"Avatar OSC启动失败: {e}", "error")

        self._send_chatbox_status()
        self._window.after(0, lambda: self._window.osc_panel.set_status("connected"))

    def _stop_osc(self):
        self._chatbox_running = False
        if self._osc_server:
            try:
                self._osc_server.shutdown()
            except Exception:
                pass
            self._osc_server = None
            self._osc_client = None
        self._stop_avatar()
        self._log_to_console("VRChat OSC 已断开", "info")

    def _stop_avatar(self):
        if self._avatar_manager:
            self._avatar_manager.stop()
            self._avatar_manager = None

    def _send_chatbox(self, text: str):
        if not self._osc_client:
            return
        if not self._window.osc_panel.get_chatbox_enabled():
            return
        try:
            self._osc_client.send_message("/chatbox/input", [text, True, False])
        except Exception:
            pass

    def _send_chatbox_status(self):
        import time as _time
        if not self._chatbox_running:
            return
        if not self._window.osc_panel.get_chatbox_enabled():
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
            # Line 4: Waveform names
            if toggles.get("line4", True):
                name_parts = []
                if self._waveform_name_a:
                    name_parts.append(f"A:{self._waveform_name_a}")
                if self._waveform_name_b:
                    name_parts.append(f"B:{self._waveform_name_b}")
                if name_parts:
                    lines.append(" ".join(name_parts))
            # Line 5: Custom
            if toggles.get("line5", True) and custom_line:
                lines.append(custom_line)
            # Footer: QQ + version (always show)
            lines.append("QQ:757992539 | v1.0")
            self._send_chatbox("\n".join(lines))
        if self._chatbox_running:
            self._window.after(1000, self._send_chatbox_status)

    def _on_osc_message(self, address: str, *args):
        """Default handler for unmatched OSC messages - display in params."""
        if self._window:
            params = {address: args[0] if len(args) == 1 else args}
            self._window.after(0, lambda p=params: self._window.osc_panel.update_params(p))

    def _on_avatar_wave(self, channel: str, wave_hex: str):
        if self._ws_client and self._ws_client.is_paired:
            self._ws_client.send_waveform(channel, wave_hex)

    def _on_avatar_clear(self, channel: str):
        if self._ws_client and self._ws_client.is_paired:
            self._ws_client.clear_waveform(channel)

    def _on_chatbox_toggle(self, enabled: bool):
        self._settings.set("chatbox_enabled", enabled)
        self._settings.save()
        state = "开启" if enabled else "关闭"
        self._log_to_console(f"Chatbox显示已{state}", "info")

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

    def _load_settings_to_ui(self):
        s = self._settings
        self._window.connection_panel.set_port(s.get("port", 9999))
        self._window.settings_panel.set_a_limit(s.get("a_limit", 200))
        self._window.settings_panel.set_b_limit(s.get("b_limit", 200))
        self._window.settings_panel.set_mode(s.get("mode", "instant"))
        self._window.settings_panel.set_channel(s.get("channel", "A"))
        self._window.settings_panel.set_waveform_mode(s.get("waveform_mode", "library"))
        self._window.mapping_panel.set_mapping(s.get("seconds_mapping", {}))
        self._window.osc_panel.set_chatbox_port(s.get("osc_port", 9000))
        self._window.osc_panel.set_avatar_port(s.get("avatar_osc_port", 9001))
        self._window.osc_panel.set_mode_a(s.get("avatar_channel_a_mode", "distance"))
        self._window.osc_panel.set_mode_b(s.get("avatar_channel_b_mode", "distance"))
        self._window.osc_panel.set_chatbox_enabled(s.get("chatbox_enabled", True))
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
        s.set("osc_port", self._window.osc_panel.get_chatbox_port())
        s.set("avatar_osc_port", self._window.osc_panel.get_avatar_port())
        s.set("avatar_channel_a_mode", self._window.osc_panel.get_mode_a())
        s.set("avatar_channel_b_mode", self._window.osc_panel.get_mode_b())
        s.set("chatbox_enabled", self._window.osc_panel.get_chatbox_enabled())
        s.set("custom_chatbox", self._window.settings_panel.get_custom_chatbox())
        s.set("chatbox_toggles", self._window.settings_panel.get_chatbox_toggles())
        s.set("seconds_mapping", self._window.mapping_panel.get_mapping())
        s.save()

    def on_close(self):
        # Stop all services in order
        self._chatbox_running = False
        if self._log_monitor:
            self._log_monitor.stop()
            self._log_monitor = None
        if self._ws_client:
            self._ws_client.disconnect()
            self._ws_client = None
        self._stop_osc()
        self._save_settings_from_ui()
        # Force destroy the root window to end mainloop
        if self._window:
            try:
                self._window._root.destroy()
            except Exception:
                pass
            self._window = None
