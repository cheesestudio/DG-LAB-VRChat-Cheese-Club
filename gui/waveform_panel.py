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
        super().__init__(master, bg=self._theme.get("bg_panel", "#1a1a2e"), **kwargs)

        self._history = collections.deque(maxlen=200)
        self._visible_seconds = 6
        self._tick_id = None
        self._tick_stopped = False
        self._active = False
        self._push_pending = []  # thread-safe push buffer
        self._lock = threading.Lock()
        self._push_max_pending = 200  # cap pending buffer to prevent unbounded growth

        # Current intensity values for display
        self._current_a = 0
        self._current_b = 0

        self._build()

    def _build(self):
        t = self._theme

        # Header
        header = tk.Frame(self, bg=t.get("bg_header", "#16213e"))
        header.pack(fill="x", padx=2, pady=(2, 0))
        tk.Label(
            header, text="波形监视", bg=t.get("bg_header", "#16213e"),
            fg=t.get("text_primary", "#e0e0e0"),
            font=(UI_M_B), anchor="w",
        ).pack(side="left", padx=8, pady=4)

        self._status_label = tk.Label(
            header, text="未连接", bg=t.get("bg_header", "#16213e"),
            fg=t.get("text_muted", "#666666"),
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
        self._fig = Figure(figsize=(8, 5), dpi=60, facecolor=t.get("waveform_bg", "#0a0a1a"))

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

        # Fill objects (removed - fill_between was causing memory growth)
        self._fill_a = None
        self._fill_b = None

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
        self._tick_stopped = False
        if self._tick_id:
            self.after_cancel(self._tick_id)
        self._tick()

    def stop(self):
        self._tick_stopped = True
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        if active and self._tick_stopped:
            self._tick_stopped = False
            self._tick()

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
        # Cap history to prevent unbounded growth
        while len(self._history) > self._history.maxlen * 2:
            trim = len(self._history) - self._history.maxlen
            for _ in range(trim):
                self._history.popleft()
        dt = self.SUB_INTERVAL
        for a_ints, b_ints, base_time in pending:
            max_len = max(len(a_ints), len(b_ints))
            for i in range(max_len):
                ts = base_time + i * dt
                a_val = a_ints[i] if i < len(a_ints) else 0
                b_val = b_ints[i] if i < len(b_ints) else 0
                self._history.append((ts, a_val, b_val))

    def _tick(self):
        if self._tick_stopped:
            return
        # When inactive, only run very lightweight info updates at 1s interval
        if not self._active:
            self._update_info()
            self._tick_id = self.after(1000, self._tick)
            return
        self._flush_push()
        now = time.time()
        if self._history:
            self._render(now)
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
        entries = list(self._history)

        for i, (ts, a_val, b_val) in enumerate(entries):
            if ts < x_min - 0.05:
                continue
            x = ts - x_min
            if i + 1 < len(entries):
                x_end = entries[i + 1][0] - x_min
            else:
                x_end = x + 0.025

            xs_a.extend([x, x_end])
            ys_a.extend([a_val, a_val])
            xs_b.extend([x, x_end])
            ys_b.extend([b_val, b_val])

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
        self.stop()
        self._history.clear()
        with self._lock:
            self._push_pending.clear()
        self._active = False
        self._current_a = 0
        self._current_b = 0
        self._line_a.set_data([], [])
        self._line_b.set_data([], [])
        if self._fill_a is not None:
            self._fill_a.remove()
            self._fill_a = None
        if self._fill_b is not None:
            self._fill_b.remove()
            self._fill_b = None
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
