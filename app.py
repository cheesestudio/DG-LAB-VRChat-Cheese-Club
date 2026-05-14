import logging
import threading
import collections
from settings import Settings
from themes import get_theme
from log_monitor import LogMonitor
from ws_client import WSClient
from waveform import generate_ab_waveforms
from avatar_handler import AvatarManager
from gui.main_window import MainWindow
from http_server import HttpServer
from constants import (
    APP_VERSION, DEFAULT_WS_PORT, DEFAULT_HTTP_PORT,
    SAFETY_WINDOW_SECONDS, SAFETY_MAX_PER_WINDOW, SAFETY_MAX_TOTAL,
    MIN_INTENSITY, MAX_INTENSITY,
)

logger = logging.getLogger(__name__)


def _flat_waveform_entry(intensity: int) -> str:
    """Generate V3 8-byte hex: 4 carrier bytes + 4 pulse bytes.
    UI intensity 0-200 maps to hex pulse 0-100 (0x00-0x64)."""
    i = max(MIN_INTENSITY, min(MAX_INTENSITY, intensity)) // 2  # 0-200 → 0-100 hex
    i = max(0, min(100, i))
    # Moderate carrier (0x32 = 50) for a balanced sensation
    return f"32323232{i:02X}{i:02X}{i:02X}{i:02X}"


def _ramp_waveform(seconds: int, target_intensity: int) -> list:
    """Generate ramp waveform — carrier and pulse both rise linearly."""
    count = seconds * 10
    entries = []
    for i in range(count):
        t = i / max(count - 1, 1)
        ui_val = max(MIN_INTENSITY, min(MAX_INTENSITY, int(target_intensity * t)))
        hex_pulse = max(0, min(100, ui_val // 2))
        # Carrier ramps from 10 to 60 alongside pulse
        carrier = int(10 + 50 * t)
        entries.append(f"{carrier:02X}{carrier:02X}{carrier:02X}{carrier:02X}{hex_pulse:02X}{hex_pulse:02X}{hex_pulse:02X}{hex_pulse:02X}")
    return entries


def _decode_wave_hex(hex_entries):
    """Decode V3 hex: first 8 = carrier[4], last 8 = pulse[4].
    Returns pulse values scaled to 0-200 UI range (hex 0-100 * 2)."""
    result = []
    if not isinstance(hex_entries, list):
        return result
    for entry in hex_entries:
        if not isinstance(entry, str):
            continue
        for j in range(4):
            pos = 8 + j * 2
            if pos + 2 <= len(entry):
                try:
                    result.append(int(entry[pos:pos + 2], 16) * 2)
                except ValueError:
                    result.append(0)
    return result


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
        self._closing = False
        self._current_theme_name = self._settings.get("theme", "dark")
        self._shock_remaining_a = 0
        self._shock_remaining_b = 0
        self._shock_end_time = 0
        self._shock_recent_events_log = collections.deque(maxlen=100)   # 日志触发的窗口安全限制
        self._shock_recent_events_http = collections.deque(maxlen=100)  # HTTP 触发的窗口安全限制
        self._waveform_name_a = ""
        self._waveform_name_b = ""
        self._waveform_feeder_running = False
        self._feeder_generation = 0
        self._safety_lock = threading.Lock()
        self._chatbox_clear_countdown = 0
        # Statistics: per-channel total seconds and intensity*time
        self._stats_a_seconds = 0
        self._stats_b_seconds = 0
        self._stats_a_intensity_time = 0.0
        self._stats_b_intensity_time = 0.0
        self._debug_mode = False
        self._log_file = None
        self._last_http_shock_time = 0
        self._http_server = HttpServer(port=self._settings.get("http_port", 8800))

    def _read_ui(self, func):
        """Thread-safe: read a UI value from a background thread.
        Retries once on timeout. Returns None only if both attempts time out."""
        import threading as _t
        result = [None]
        done = _t.Event()
        def _read():
            result[0] = func()
            done.set()
        self._window.after(0, _read)
        if not done.wait(timeout=2):
            # Retry once — UI thread may have been busy
            done.clear()
            self._window.after(0, _read)
            done.wait(timeout=1)
        return result[0]

    def _read_shock_ui(self) -> dict:
        """Read ALL shock-related UI values in ONE thread-safe call.
        Avoids 8 round-trips to the UI thread that cause multi-second delays."""
        import threading as _t
        result = {}
        done = _t.Event()
        def _read():
            try:
                p = self._window.settings_panel
                result['a_limit'] = p.get_a_limit()
                result['b_limit'] = p.get_b_limit()
                result['dual_ch'] = p.get_dual_channel()
                result['max_mode'] = p.get_max_mode()
                result['mode'] = p.get_mode()
                result['wf_mode'] = p.get_waveform_mode()
                result['custom_wf'] = p.get_custom_waveform()
                result['alternate'] = p.get_alternate_waveform()
            except Exception:
                pass
            done.set()
        self._window.after(0, _read)
        if not done.wait(timeout=2):
            done.clear()
            self._window.after(0, _read)
            done.wait(timeout=1)
        return result

    def run(self):
        # Open session log file (overwrite each launch)
        import os, sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(base_dir, "latest_session.log")
        # Truncate if log file too large (>1MB)
        try:
            if os.path.exists(log_path) and os.path.getsize(log_path) > 1024 * 1024:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("[日志] 日志文件已截断 (大小超过1MB)\n")
            self._log_file = open(log_path, "a", encoding="utf-8")
        except Exception:
            pass
        theme = get_theme(self._current_theme_name)
        self._window = MainWindow(self, theme=theme)
        self._load_settings_to_ui()
        self._load_session_stats()
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

    def _apply_safety_limits(self, seconds: float, recent_events: list, log_warning: bool = True) -> tuple[float, bool]:
        """Apply safety limits. Returns (adjusted_seconds, should_continue)."""
        if seconds <= 0:
            return 0, False
        import time as _time
        with self._safety_lock:
            now = _time.time()

            # Window-based accumulation
            recent_events.append((now, seconds))
            # For deque, we need to remove old items manually
            while recent_events and now - recent_events[0][0] > SAFETY_WINDOW_SECONDS:
                recent_events.popleft()
            recent_sum = sum(s for _, s in recent_events)
            if recent_sum > SAFETY_MAX_PER_WINDOW:
                allowed = max(0, SAFETY_MAX_PER_WINDOW - (recent_sum - seconds))
                seconds = allowed
                # Update last element
                if recent_events:
                    recent_events[-1] = (now, seconds)

            if seconds <= 0:
                # Allow at least 1 second to keep shock running
                seconds = 1
                if log_warning:
                    self._log_to_console(f"安全限制: 窗口内累计超限，限制为1秒", "warning")

            # Total cap — ensure total remaining never exceeds SAFETY_MAX_TOTAL
            if now < self._shock_end_time:
                current_remaining = self._shock_end_time - now
            else:
                current_remaining = 0

            if current_remaining + seconds > SAFETY_MAX_TOTAL:
                seconds = max(1, SAFETY_MAX_TOTAL - current_remaining)  # Allow at least 1 second
                if log_warning:
                    self._log_to_console(f"安全限制: 总时长已达{SAFETY_MAX_TOTAL}秒上限，限制为{seconds}秒", "warning")

            # Update remaining time — use current_remaining, not old accumulated value
            new_remaining = current_remaining + seconds
            self._shock_remaining_a = new_remaining
            self._shock_remaining_b = new_remaining
            self._shock_end_time = now + new_remaining

            return seconds, True

    def _send_waveform(self, channel: str, wave_hex: list, duration: float, clear_first: bool = False):
        """Send waveform to a single channel. Device replaces queue automatically."""
        if not self._ws_client or not self._ws_client.is_paired:
            self._log_to_console(f"_send_waveform 跳过: 未连接", "warning")
            return
        self._log_to_console(f"_send_waveform {channel}: {len(wave_hex)}条", "info")
        self._ws_client.send_waveform(channel, wave_hex, duration=duration)

    def _push_waveform_display(self, a_wave_hex: list, b_wave_hex: list, a_name: str = "", b_name: str = "", a_intensity: int = 0, b_intensity: int = 0):
        """Push waveform data to the display panel. Thread-safe: schedules on main thread."""
        try:
            a_subs = _decode_wave_hex(a_wave_hex)
            b_subs = _decode_wave_hex(b_wave_hex)
            import time as _time
            now = _time.time()
            self._window.after(0, lambda a=a_subs, b=b_subs, t=now, ai=a_intensity, bi=b_intensity: (
                self._window.waveform_panel.set_active(True),
                self._window.waveform_panel.push_waveform(a, b, t),
                self._window.waveform_panel.set_intensity(ai, bi),
            ))
        except Exception as e:
            if self._debug_mode:
                self._log_to_console(f"波形显示更新失败: {type(e).__name__}: {e}", "debug")

    def _on_shock_event(self, event: dict):
        import time as _time
        mode = event.get("mode", "instant")
        seconds = event.get("seconds", 3)
        _ = event.get("hand", "A")  # reserved for future single-channel support

        # Batch-read ALL UI values in ONE call — avoids 8 round-trips blocking for seconds
        ui = self._read_shock_ui()
        a_limit = ui.get('a_limit', 200)
        b_limit = ui.get('b_limit', 200)
        dual_ch = ui.get('dual_ch', False)
        max_mode = ui.get('max_mode', False)

        if dual_ch:
            b_limit = a_limit
        if max_mode:
            a_limit = 200
            b_limit = 200
            a_intensity = 200
            b_intensity = 200
        else:
            a_intensity = a_limit
            b_intensity = b_limit
            if dual_ch:
                b_intensity = a_intensity

        # Skip if device not connected — don't accumulate safety events for unsent shocks
        if not self._ws_client or not self._ws_client.is_paired:
            self._log_to_console(
                f"电击: {seconds}秒 A:{a_intensity} B:{b_intensity} (未发送-等待APP连接)",
                "shock",
            )
            return

        ui_mode = ui.get('mode', 'instant')
        wf_mode = ui.get('wf_mode', 'library')

        # Apply safety limits — do NOT extend shock_end_time, let current shock finish naturally
        seconds, should_continue = self._apply_safety_limits(seconds, self._shock_recent_events_log)
        if not should_continue:
            if self._waveform_feeder_running:
                self._log_to_console(f"安全限制: 已达上限，当前电击继续但不延长时间", "warning")
            return

        custom_wf = ui.get('custom_wf', '') if wf_mode == 'custom' else ''
        if max_mode:
            a_wave = _ramp_waveform(seconds, a_intensity)
            b_wave = _ramp_waveform(seconds, b_intensity)
            a_name = "拉满"
            b_name = "拉满"
        else:
            alternate = ui.get('alternate', True)
            a_wave, b_wave, a_name, b_name = generate_ab_waveforms(
                seconds, a_intensity, b_intensity, ui_mode, wf_mode, alternate=alternate,
                custom_waveform=custom_wf,
            )
        self._waveform_name_a = a_name
        self._waveform_name_b = b_name

        # Seamless feeder transition: update data in place, start new gen without stopping old
        already_feeding = self._waveform_feeder_running
        self._feeder_initial_a = a_wave
        self._feeder_initial_b = b_wave

        # Set strength + send initial waveform — no sleep needed, device handles queue
        self._ws_client.force_strength(a_limit, b_limit)
        self._send_waveform("A", a_wave, seconds)
        self._send_waveform("B", b_wave, seconds)
        self._log_to_console(
            f"电击: {seconds}秒 | A:{a_intensity}({a_name}) B:{b_intensity}({b_name}) | "
            f"{'一键开火' if ui_mode == 'instant' else '温柔加力'}",
            "shock",
        )
        with self._safety_lock:
            self._stats_a_seconds += seconds
            self._stats_b_seconds += seconds
            self._stats_a_intensity_time += a_intensity * seconds
            self._stats_b_intensity_time += b_intensity * seconds
        self._window.after(0, lambda: self._window.settings_panel.update_stats(
            self._stats_a_seconds, self._stats_b_seconds,
            self._stats_a_intensity_time, self._stats_b_intensity_time,
        ))
        self._push_waveform_display(a_wave, b_wave, a_name, b_name, a_intensity, b_intensity)

        # Start or refresh feeder — avoids stop/restart gap that causes device queue drain
        if already_feeding:
            self._refresh_feeder(ui, seconds)
        else:
            self._start_waveform_feeder(ui, seconds)

    def _apply_feeder_ui(self, ui: dict):
        """Apply UI values to feeder state — shared by _start and _refresh."""
        self._feeder_ui_mode = ui.get('mode', 'instant')
        self._feeder_wf_mode = ui.get('wf_mode', 'library')
        self._feeder_a_limit = ui.get('a_limit', 200)
        self._feeder_b_limit = ui.get('b_limit', 200)
        self._feeder_max_mode = ui.get('max_mode', False)
        self._feeder_dual_ch = ui.get('dual_ch', False)
        if self._feeder_dual_ch:
            self._feeder_b_limit = self._feeder_a_limit
        if self._feeder_max_mode:
            self._feeder_a_limit = 200
            self._feeder_b_limit = 200
        self._feeder_custom_wf = (
            ui.get('custom_wf', '') if self._feeder_wf_mode == 'custom' else ''
        )

    def _start_waveform_feeder(self, ui: dict, seconds: int):
        """Start a new waveform feeder thread with pre-read UI values."""
        import time as _time
        self._feeder_generation += 1
        self._waveform_feeder_running = True
        self._apply_feeder_ui(ui)
        now = _time.time()
        current_remaining = max(0, self._shock_end_time - now)
        self._shock_end_time = now + current_remaining + seconds
        try:
            self._window.after(0, lambda: self._window.waveform_panel.set_active(True))
        except Exception:
            pass
        my_gen = self._feeder_generation
        threading.Thread(target=self._waveform_feeder_thread, args=(my_gen,), daemon=True).start()

    def _refresh_feeder(self, ui: dict, seconds: int):
        """Update running feeder with new waveform data without stopping it.
        Avoids the stop/start gap that causes the device queue to drain."""
        import time as _time
        self._feeder_generation += 1  # Old thread will exit on generation mismatch
        self._apply_feeder_ui(ui)
        # Extend shock end time for the new event
        current_remaining = max(0, self._shock_end_time - _time.time())
        self._shock_end_time = _time.time() + current_remaining + seconds
        # Start new thread immediately — old thread exits within 0.5s (one sleep cycle)
        try:
            self._window.after(0, lambda: self._window.waveform_panel.set_active(True))
        except Exception:
            pass
        my_gen = self._feeder_generation
        threading.Thread(target=self._waveform_feeder_thread, args=(my_gen,), daemon=True).start()

    def _waveform_feeder_thread(self, generation: int):
        import time as _time
        import gc
        _tick_count = 0
        _start_time = _time.time()
        _max_runtime = 60  # Hard limit: feeder must stop after 60s regardless of events
        while self._waveform_feeder_running and self._feeder_generation == generation:
            _tick_count += 1
            if _tick_count % 60 == 0:  # Every ~30 seconds, force garbage collection
                gc.collect()
            # Ensure panel stays active while feeder is running
            try:
                self._window.after(0, lambda: self._window.waveform_panel.set_active(True))
            except Exception:
                pass
            now = _time.time()
            remaining = self._shock_end_time - now
            if remaining <= 0 or not self._ws_client or not self._ws_client.is_paired:
                self._waveform_feeder_running = False
                if self._ws_client and self._ws_client.is_paired:
                    self._ws_client.clear_waveform("A")
                    self._ws_client.clear_waveform("B")
                if self._ws_client:
                    self._ws_client.stop_waveform()
                try:
                    self._window.after(0, lambda: self._window.waveform_panel.set_active(False))
                except Exception as e:
                    if self._debug_mode:
                        self._log_to_console(f"波形面板停用失败: {type(e).__name__}: {e}", "debug")
                break
            chunk_sec = 1
            if self._feeder_max_mode:
                a_wave = [_flat_waveform_entry(self._feeder_a_limit)] * 10
                b_wave = [_flat_waveform_entry(self._feeder_b_limit)] * 10
            else:
                # Loop the initial waveform so device plays same pattern consistently
                init_a = getattr(self, '_feeder_initial_a', None)
                init_b = getattr(self, '_feeder_initial_b', None)
                if init_a and init_b:
                    from waveform import loop_waveform
                    a_wave = loop_waveform(init_a, 10)
                    b_wave = loop_waveform(init_b, 10)
                else:
                    from waveform import generate_smooth_feeder_waveform
                    a_wave = generate_smooth_feeder_waveform(self._feeder_a_limit, 10)
                    b_wave = generate_smooth_feeder_waveform(self._feeder_b_limit, 10)
            self._ws_client.send_waveform("A", a_wave, duration=chunk_sec)
            self._ws_client.send_waveform("B", b_wave, duration=chunk_sec)
            # Decode hex waveform into intensity sub-frames and push to panel
            try:
                a_subs = _decode_wave_hex(a_wave)
                b_subs = _decode_wave_hex(b_wave)
                self._window.after(0, lambda a=a_subs, b=b_subs, t=now:
                    self._window.waveform_panel.push_waveform(a, b, t))
            except Exception:
                pass
            # Update stats on main thread
            stats = (self._stats_a_seconds, self._stats_b_seconds,
                     self._stats_a_intensity_time, self._stats_b_intensity_time)
            try:
                self._window.after(0, lambda s=stats: self._window.settings_panel.update_stats(*s))
            except Exception:
                pass
            # Hard stop after max runtime — stop feeding, let device play out its queue naturally
            if _time.time() - _start_time > _max_runtime:
                self._waveform_feeder_running = False
                if self._ws_client:
                    self._ws_client.stop_waveform()
                try:
                    self._window.after(0, lambda: self._window.waveform_panel.set_active(False))
                except Exception:
                    pass
                self._log_to_console(f"波形馈送已达最大时长{_max_runtime}秒，自动停止", "warning")
                break
            _time.sleep(0.5)

    def get_stats(self) -> dict:
        return {
            "a_seconds": self._stats_a_seconds,
            "b_seconds": self._stats_b_seconds,
            "a_intensity_time": self._stats_a_intensity_time,
            "b_intensity_time": self._stats_b_intensity_time,
        }

    def _on_log_line(self, line: str):
        if "[DGLABCheeseShocking]" in line:
            # Log that we detected VRChat event
            self._log_to_console(f"[VRChat事件] {line[:60]}...", "info")
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
        # Rate limit: skip if too many same messages
        import time as _time
        now = _time.time()
        key = f"{tag}:{text[:50]}"
        if not hasattr(self, '_last_log_time'):
            self._last_log_time = {}
        # Clean up old entries if too many
        if len(self._last_log_time) > 100:
            cutoff = now - 60  # Remove entries older than 60s
            self._last_log_time = {k: v for k, v in self._last_log_time.items() if v > cutoff}
        last_time = self._last_log_time.get(key, 0)
        if now - last_time < 0.5:  # Skip if same message within 0.5s
            return
        self._last_log_time[key] = now
        # Write to session log file (all tags except debug when debug is off)
        if self._log_file and (tag != "debug" or self._debug_mode):
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S")
            try:
                self._log_file.write(f"[{ts}] {text}\n")
                self._log_file.flush()
                # Runtime truncation: keep last ~512KB if file exceeds 2MB
                if not hasattr(self, '_log_write_count'):
                    self._log_write_count = 0
                self._log_write_count += 1
                if self._log_write_count % 200 == 0:
                    self._log_write_count = 0
                    pos = self._log_file.tell()
                    if pos > 2 * 1024 * 1024:
                        self._log_file.close()
                        import os as _os
                        log_path = _os.path.join(
                            _os.path.dirname(_os.path.abspath(__file__)),
                            "latest_session.log"
                        )
                        with open(log_path, "r", encoding="utf-8") as old:
                            old.seek(max(0, pos - 512 * 1024))
                            old.readline()  # Skip partial line
                            tail = old.read()
                        self._log_file = open(log_path, "w", encoding="utf-8")
                        self._log_file.write(tail)
                        self._log_file.flush()
            except Exception:
                pass
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
            # Update header: only "paired" means APP is connected
            is_paired = status == "paired"
            is_server_running = status in ("connecting", "connected", "paired")
            self._window.after(0, lambda p=is_paired, s=is_server_running: self._window.update_connection_status(p, s))
            if status == "paired":
                self._window.after(0, self._start_waveform_monitor)
                # Clear safety deques on fresh pair — stale entries would block new shocks
                with self._safety_lock:
                    self._shock_recent_events_log.clear()
                    self._shock_recent_events_http.clear()
            elif status in ("connected", "disconnected"):
                self._window.after(0, self._stop_waveform_monitor)
                # Reset shock state on disconnect so stale end_time doesn't confuse logic
                import time as _time
                self._shock_end_time = 0
                self._waveform_feeder_running = False
                with self._safety_lock:
                    self._shock_recent_events_log.clear()
                    self._shock_recent_events_http.clear()

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

            # 去重：同一通道内同一地址只绑定一次，不同通道可共享同一地址
            bound_a = set()
            for path in a_params:
                if path not in bound_a:
                    d.map(path, self._avatar_manager._channels["A"].on_osc)
                    bound_a.add(path)
            bound_b = set()
            for path in b_params:
                if path not in bound_b:
                    d.map(path, self._avatar_manager._channels["B"].on_osc)
                    bound_b.add(path)

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
        if self._closing or not self._chatbox_running:
            return
        if self._chatbox_clear_countdown > 0:
            self._chatbox_clear_countdown -= 1
            if self._osc_client:
                try:
                    self._osc_client.send_message("/chatbox/input", ["", True, False])
                except Exception:
                    pass
            self._window.after(1000, self._send_chatbox_status)
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
            # Line 4: Waveform names (only during active shock)
            if toggles.get("line4", True) and remaining > 0:
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
            lines.append(f"QQ群:757992539 | {APP_VERSION}")
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
            # Send to both channels on device
            self._ws_client.send_waveform("A", wave_hex)
            self._ws_client.send_waveform("B", wave_hex)
            try:
                if isinstance(wave_hex, str):
                    import json
                    try:
                        wave_hex = json.loads(wave_hex)
                    except (json.JSONDecodeError, ValueError):
                        wave_hex = []
                if isinstance(wave_hex, list) and wave_hex:
                    import time as _time
                    subs = _decode_wave_hex(wave_hex)
                    now = _time.time()
                    self._window.after(0, lambda: self._window.waveform_panel.set_active(True))
                    self._window.after(0, lambda s=subs, t=now: self._window.waveform_panel.push_waveform(s, s, t))
            except Exception:
                pass

    def _on_avatar_clear(self, channel: str):
        if self._ws_client and self._ws_client.is_paired:
            self._ws_client.clear_waveform(channel)
            try:
                self._window.after(0, lambda: self._window.waveform_panel.set_active(False))
            except Exception:
                pass

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
            # Keep clearing for a few seconds so VRChat picks it up
            self._chatbox_clear_countdown = 5

    # --- Settings ---
    def on_settings_change(self):
        self._save_settings_from_ui()

    def on_test_shock(self):
        """Test shock: both channels at max for 3 seconds."""
        if not self._ws_client or not self._ws_client.is_paired:
            self._log_to_console("测试失败: APP未连接", "error")
            return
        a_limit = self._window.settings_panel.get_a_limit()
        b_limit = self._window.settings_panel.get_b_limit()
        if self._window.settings_panel.get_max_mode():
            a_limit = 200
            b_limit = 200
        if self._window.settings_panel.get_max_mode():
            a_wave = [_flat_waveform_entry(a_limit)] * 30
            b_wave = [_flat_waveform_entry(b_limit)] * 30
        else:
            a_wave, b_wave, _, _ = generate_ab_waveforms(
                3, a_limit, b_limit, "instant", "library", alternate=False,
            )
        self._ws_client.force_strength(a_limit, b_limit)
        self._send_waveform("A", a_wave, 3)
        self._send_waveform("B", b_wave, 3)
        self._push_waveform_display(a_wave, b_wave, a_intensity=a_limit, b_intensity=b_limit)
        # Auto-stop display after 3 seconds
        self._window.after(3000, lambda: self._window.waveform_panel.set_active(False))
        self._log_to_console(f"测试电击: 3秒双通道 A:{a_limit} B:{b_limit}", "shock")
        self._send_chatbox(f"[测试] 3秒双通道 | A:{a_limit} B:{b_limit}")

    def on_http_shock(self, mode: int, seconds: int):
        """Handle shock trigger from VRChat ShockingManager HTTP request."""
        if not self._ws_client or not self._ws_client.is_paired:
            return
        import time as _time
        now = _time.time()
        # If shock is already playing, extend with safety cap
        if self._waveform_feeder_running and now < self._shock_end_time:
            current_remaining = self._shock_end_time - now
            new_remaining = current_remaining + seconds
            if new_remaining > SAFETY_MAX_TOTAL:
                new_remaining = SAFETY_MAX_TOTAL
            self._shock_end_time = now + new_remaining
            self._log_to_console(f"延长电击: +{seconds}秒 (剩余{int(self._shock_end_time - now)}秒)", "info")
            return
        # Debounce: ignore rapid repeated HTTP shocks when not playing
        if now - self._last_http_shock_time < 3:
            return
        self._last_http_shock_time = now

        # Batch-read ALL UI values in ONE call
        ui = self._read_shock_ui()
        a_limit = ui.get('a_limit', 200)
        b_limit = ui.get('b_limit', 200)
        max_mode = ui.get('max_mode', False)
        dual_ch = ui.get('dual_ch', False)
        ui_mode = ui.get('mode', 'instant')
        wf_mode = ui.get('wf_mode', 'library')

        if max_mode:
            a_limit = 200
            b_limit = 200
        if dual_ch:
            b_limit = a_limit

        # Apply safety limits
        seconds, should_continue = self._apply_safety_limits(seconds, self._shock_recent_events_http, log_warning=False)
        if not should_continue:
            return

        if max_mode:
            a_intensity = 200
            b_intensity = 200
        else:
            a_intensity = a_limit
            b_intensity = b_limit
            if dual_ch:
                b_intensity = a_intensity

        # Generate waveforms
        custom_wf = ui.get('custom_wf', '') if wf_mode == 'custom' else ''
        if max_mode:
            a_wave = _ramp_waveform(seconds, a_intensity)
            b_wave = _ramp_waveform(seconds, b_intensity)
            a_name = "拉满"
            b_name = "拉满"
        else:
            alternate = ui.get('alternate', True)
            a_wave, b_wave, a_name, b_name = generate_ab_waveforms(
                seconds, a_intensity, b_intensity, ui_mode, wf_mode, alternate=alternate,
                custom_waveform=custom_wf,
            )
        self._waveform_name_a = a_name
        self._waveform_name_b = b_name

        # Seamless feeder transition
        already_feeding = self._waveform_feeder_running
        self._feeder_initial_a = a_wave
        self._feeder_initial_b = b_wave

        self._ws_client.force_strength(a_limit, b_limit)
        self._send_waveform("A", a_wave, seconds)
        self._send_waveform("B", b_wave, seconds)

        self._push_waveform_display(a_wave, b_wave, a_name, b_name, a_intensity, b_intensity)

        if already_feeding:
            self._refresh_feeder(ui, seconds)
        else:
            self._start_waveform_feeder(ui, seconds)

        # Track stats
        with self._safety_lock:
            self._stats_a_seconds += seconds
            self._stats_b_seconds += seconds
            self._stats_a_intensity_time += a_intensity * seconds
            self._stats_b_intensity_time += b_intensity * seconds
        self._window.after(0, lambda: self._window.settings_panel.update_stats(
            self._stats_a_seconds, self._stats_b_seconds,
            self._stats_a_intensity_time, self._stats_b_intensity_time,
        ))
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
        self._window.settings_panel.set_max_mode(s.get("max_mode", False))
        self._window.settings_panel.set_dual_channel(s.get("dual_channel", False))
        self._window.settings_panel.set_alternate_waveform(s.get("alternate_waveform", False))
        self._window.settings_panel.set_waveform_mode(s.get("waveform_mode", "library"))
        self._window.settings_panel.set_custom_waveform(s.get("custom_waveform", ""))
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
        s.set("max_mode", self._window.settings_panel.get_max_mode())
        s.set("dual_channel", self._window.settings_panel.get_dual_channel())
        s.set("alternate_waveform", self._window.settings_panel.get_alternate_waveform())
        s.set("waveform_mode", self._window.settings_panel.get_waveform_mode())
        s.set("custom_waveform", self._window.settings_panel.get_custom_waveform())
        s.set("osc_port", self._window.osc_panel.get_chatbox_port())
        s.set("avatar_osc_port", self._window.osc_panel.get_avatar_port())
        s.set("avatar_channel_a_mode", self._window.osc_panel.get_mode_a())
        s.set("avatar_channel_b_mode", self._window.osc_panel.get_mode_b())
        s.set("chatbox_enabled", self._window.settings_panel.get_chatbox_enabled())
        s.set("custom_chatbox", self._window.settings_panel.get_custom_chatbox())
        s.set("chatbox_toggles", self._window.settings_panel.get_chatbox_toggles())
        s.save()

    def _save_session_stats(self):
        import time as _time
        import json
        import os
        stats = {
            "last_session": _time.strftime("%Y-%m-%d %H:%M:%S"),
            "a_seconds": self._stats_a_seconds,
            "b_seconds": self._stats_b_seconds,
            "a_intensity_time": self._stats_a_intensity_time,
            "b_intensity_time": self._stats_b_intensity_time,
        }
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_stats.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_session_stats(self):
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_stats.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    stats = json.load(f)
                self._stats_a_seconds = stats.get("a_seconds", 0)
                self._stats_b_seconds = stats.get("b_seconds", 0)
                self._stats_a_intensity_time = stats.get("a_intensity_time", 0.0)
                self._stats_b_intensity_time = stats.get("b_intensity_time", 0.0)
            except Exception:
                pass

    def on_close(self):
        """Fast: just set flags. Cleanup runs in background thread."""
        self._closing = True
        self._chatbox_running = False
        self._waveform_feeder_running = False

    def _do_cleanup(self):
        """Slow cleanup - runs in background thread, not on main thread."""
        import logging
        log = logging.getLogger(__name__)
        try:
            if self._log_file:
                try:
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None
            log.info("cleanup start")
            if self._http_server:
                self._http_server.stop()
                self._http_server = None
            if self._log_monitor:
                self._log_monitor.stop()
                self._log_monitor = None
            if self._ws_client:
                try:
                    self._ws_client.disconnect()
                except Exception:
                    pass
                self._ws_client = None
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
            if self._avatar_manager:
                try:
                    self._avatar_manager.stop()
                except Exception:
                    pass
                self._avatar_manager = None
            try:
                self._save_settings_from_ui()
                self._save_session_stats()
            except Exception:
                pass
            log.info("cleanup done")
        except Exception as e:
            log.error(f"cleanup error: {e}")
