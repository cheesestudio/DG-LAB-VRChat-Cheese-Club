from gui.fonts import UI_XS, UI_S, UI_S_B, UI_M, UI_M_B, UI_L, MONO_S
import tkinter as tk
import collections
import time
import threading
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt
import matplotlib

# Configure matplotlib to use Chinese-compatible font
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei UI', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False


class WaveformPanel(tk.Frame):
    """Waveform display: shows A/B channels separately like official DG-LAB app."""

    SUB_INTERVAL = 0.025  # 25ms per sub-frame

    def __init__(self, master, theme: dict = None, **kwargs):
        self._theme = theme or {}
        kwargs.pop("bg", None)
        super().__init__(master, bg="#111111", **kwargs)

        self._history = collections.deque(maxlen=600)  # 15s @ 25ms per sample
        self._visible_seconds = 12
        self._tick_id = None
        self._active = False
        self._push_pending = []  # thread-safe push buffer
        self._lock = threading.Lock()
        self._push_max_pending = 50  # cap pending buffer to prevent unbounded growth
        self._last_render_time = 0  # throttle renders to every 200ms
        self._stopped = False  # 调用 stop() 后为 True

        # Current intensity values for display
        self._current_a = 0
        self._current_b = 0

        self._build()
        # Start tick loop immediately — it's lightweight when idle
        self._tick()

    def _build(self):
        t = self._theme

        # Header
        header = tk.Frame(self, bg="#111111")
        header.pack(fill="x", padx=2, pady=(2, 0))
        tk.Label(
            header, text="波形监视", bg="#111111",
            fg="#e4e4e7",
            font=(UI_M_B), anchor="w",
        ).pack(side="left", padx=8, pady=4)

        self._status_label = tk.Label(
            header, text="未连接", bg="#111111",
            fg="#52525b",
            font=(UI_S), anchor="e",
        )
        self._status_label.pack(side="right", padx=8, pady=4)

        # Channel info frame
        info_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        info_frame.pack(fill="x", padx=4, pady=(4, 0))

        # Channel A info
        a_frame = tk.Frame(info_frame, bg=t.get("bg_panel", "#1a1a2e"))
        a_frame.pack(side="left", fill="x", expand=True)
        tk.Label(
            a_frame, text="A", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_green", "#66bb6a"),
            font=(UI_M_B),
        ).pack(side="left", padx=(0, 4))
        self._a_value_label = tk.Label(
            a_frame, text="0", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_green", "#66bb6a"),
            font=(UI_L),
        )
        self._a_value_label.pack(side="left")
        tk.Label(
            a_frame, text="强度", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_muted", "#666666"),
            font=(UI_XS),
        ).pack(side="left", padx=(2, 0))

        # Channel B info
        b_frame = tk.Frame(info_frame, bg=t.get("bg_panel", "#1a1a2e"))
        b_frame.pack(side="right", fill="x", expand=True)
        tk.Label(
            b_frame, text="B", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_orange", "#ffb74d"),
            font=(UI_M_B),
        ).pack(side="left", padx=(0, 4))
        self._b_value_label = tk.Label(
            b_frame, text="0", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_orange", "#ffb74d"),
            font=(UI_L),
        )
        self._b_value_label.pack(side="left")
        tk.Label(
            b_frame, text="强度", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_muted", "#666666"),
            font=(UI_XS),
        ).pack(side="left", padx=(2, 0))

        # Matplotlib figure with two subplots
        self._fig = Figure(figsize=(6, 3.5), dpi=80, facecolor=t.get("waveform_bg", "#0a0a1a"))

        # Create two subplots stacked vertically
        self._ax_a = self._fig.add_subplot(211)
        self._ax_b = self._fig.add_subplot(212, sharex=self._ax_a)

        # Style both axes
        for ax, color, label in [
            (self._ax_a, t.get("accent_green", "#66bb6a"), "A"),
            (self._ax_b, t.get("accent_orange", "#ffb74d"), "B"),
        ]:
            ax.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
            ax.set_ylabel("强度", color=t.get("text_dim", "#888888"), fontsize=7)
            ax.set_ylim(0, 200)
            ax.set_xlim(0, self._visible_seconds)
            ax.tick_params(colors=t.get("text_muted", "#666666"), labelsize=6)
            for spine in ax.spines.values():
                spine.set_color(t.get("waveform_grid", "#333333"))
            ax.grid(True, alpha=0.3, color=t.get("waveform_grid", "#333333"))
            # Add channel label
            ax.text(0.02, 0.95, label, transform=ax.transAxes,
                    color=color, fontsize=12, fontweight='bold',
                    verticalalignment='top')

        # Only show x-axis label on bottom plot
        self._ax_b.set_xlabel("时间 (秒)", color=t.get("text_dim", "#888888"), fontsize=7)
        self._ax_a.tick_params(labelbottom=False)

        # Create line objects
        self._line_a, = self._ax_a.plot([], [], color=t.get("accent_green", "#66bb6a"),
                                        linewidth=1.5, alpha=0.9)
        self._line_b, = self._ax_b.plot([], [], color=t.get("accent_orange", "#ffb74d"),
                                        linewidth=1.5, alpha=0.9)

        self._fig.tight_layout(pad=1.0)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=2, pady=2)

        # Bottom info
        self._info_label = tk.Label(
            self, text="等待连接...", bg=t.get("bg_panel", "#1a1a2e"),
            fg=self._theme.get("text_muted", "#666666"),
            font=(UI_S),
        )
        self._info_label.pack(pady=(0, 4))

    def start(self, get_a_value, get_b_value):
        self._history.clear()
        self._active = True

    def stop(self):
        """暂停（但不清除数据，允许 resume）"""
        self._active = False

    def shutdown(self):
        """永久停止循环（在窗口关闭时调用）"""
        self._active = False
        self._stopped = True
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None

    def set_active(self, active: bool):
        self._active = active

    def set_intensity(self, a: int, b: int):
        """Set actual intensity values for display (called from main thread)."""
        self._current_a = a
        self._current_b = b

    def push_waveform(self, a_intensities, b_intensities, base_time):
        """Thread-safe: queue waveform data for main thread to consume."""
        if not a_intensities and not b_intensities:
            return
        with self._lock:
            self._push_pending.append((a_intensities, b_intensities, base_time))
            # Cap pending buffer to prevent unbounded growth
            while len(self._push_pending) > self._push_max_pending:
                self._push_pending.pop(0)

    def _flush_push(self):
        """Called from main thread tick to consume pending push data."""
        with self._lock:
            pending = self._push_pending[:]
            self._push_pending.clear()
        if not pending:
            return
        dt = self.SUB_INTERVAL
        for a_ints, b_ints, base_time in pending:
            # Ensure new data starts after existing data (no overlap)
            if self._history:
                last_ts = self._history[-1][0]
                if base_time <= last_ts:
                    base_time = last_ts + dt
            max_len = max(len(a_ints), len(b_ints))
            for i in range(max_len):
                ts = base_time + i * dt
                a_val = a_ints[i] if i < len(a_ints) else 0
                b_val = b_ints[i] if i < len(b_ints) else 0
                self._history.append((ts, a_val, b_val))

    def _tick(self):
        if self._stopped:
            return
        self._flush_push()
        now = time.time()
        # Render at most every 200ms to keep chart scrolling smoothly
        if self._history and (now - self._last_render_time >= 0.2):
            try:
                self._render(now)
                self._last_render_time = now
            except Exception:
                pass
        self._update_info(now)
        self._tick_id = self.after(100, self._tick)

    def _render(self, now=None):
        if not self._history:
            return
        if now is None:
            now = time.time()

        x_min = now - self._visible_seconds

        xs_a, ys_a = [], []
        xs_b, ys_b = [], []

        # Only iterate visible entries (skip old data without copying full list)
        for entry in self._history:
            ts, a_val, b_val = entry
            if ts < x_min - 0.05:
                continue
            x = ts - x_min
            xs_a.append(x)
            ys_a.append(a_val)
            xs_b.append(x)
            ys_b.append(b_val)

        # Update channel A
        self._line_a.set_data(xs_a, ys_a)
        self._line_b.set_data(xs_b, ys_b)

        # Update axes
        self._ax_a.set_xlim(0, self._visible_seconds)
        self._ax_b.set_xlim(0, self._visible_seconds)
        self._canvas.draw_idle()

    def _update_info(self, now=None):
        if now is None:
            now = time.time()

        # Update value labels
        self._a_value_label.configure(text=str(self._current_a))
        self._b_value_label.configure(text=str(self._current_b))

        if self._active and self._history:
            self._info_label.configure(
                text=f"[波形播放中]",
                fg=self._theme.get("accent_green", "#66bb6a"),
            )
            self._status_label.configure(
                text="电击中",
                fg=self._theme.get("accent_orange", "#ffb74d"),
            )
        elif self._active:
            self._info_label.configure(
                text="等待波形数据...",
                fg=self._theme.get("text_muted", "#666666"),
            )
            self._status_label.configure(
                text="电击中",
                fg=self._theme.get("accent_orange", "#ffb74d"),
            )
        elif self._history:
            self._info_label.configure(
                text=f"[已暂停]",
                fg=self._theme.get("text_muted", "#666666"),
            )
            self._status_label.configure(
                text="已暂停",
                fg=self._theme.get("text_muted", "#666666"),
            )
        else:
            self._info_label.configure(
                text="待机",
                fg=self._theme.get("text_muted", "#666666"),
            )
            self._status_label.configure(
                text="采集中",
                fg=self._theme.get("accent_green", "#66bb6a"),
            )

    def set_disconnected(self):
        self._status_label.configure(
            text="未连接",
            fg=self._theme.get("text_muted", "#666666"),
        )
        self._info_label.configure(
            text="等待连接...",
            fg=self._theme.get("text_muted", "#666666"),
        )

    def clear(self):
        self._history.clear()
        with self._lock:
            self._push_pending.clear()
        self._active = False
        self._current_a = 0
        self._current_b = 0
        self._line_a.set_data([], [])
        self._line_b.set_data([], [])
        self._ax_a.set_xlim(0, self._visible_seconds)
        self._ax_b.set_xlim(0, self._visible_seconds)
        self._canvas.draw_idle()
        self.set_disconnected()

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self.configure(bg=t.get("bg_panel", "#1a1a2e"))
        self._fig.set_facecolor(t.get("waveform_bg", "#0a0a1a"))

        for ax, color in [
            (self._ax_a, t.get("accent_green", "#66bb6a")),
            (self._ax_b, t.get("accent_orange", "#ffb74d")),
        ]:
            ax.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
            ax.tick_params(colors=t.get("text_muted", "#666666"), labelsize=6)
            for spine in ax.spines.values():
                spine.set_color(t.get("waveform_grid", "#333333"))
            ax.grid(True, alpha=0.3, color=t.get("waveform_grid", "#333333"))

        self._line_a.set_color(t.get("accent_green", "#66bb6a"))
        self._line_b.set_color(t.get("accent_orange", "#ffb74d"))
        self._canvas.draw_idle()
