import tkinter as tk
import collections
import time
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class WaveformPanel(tk.Frame):
    """Continuous scrolling waveform display showing A/B strength over time."""

    def __init__(self, master, theme: dict = None, **kwargs):
        self._theme = theme or {}
        super().__init__(master, bg=self._theme.get("bg_panel", "#1a1a2e"), **kwargs)

        # History buffer: (timestamp, a_value, b_value)
        self._history = collections.deque(maxlen=120)  # 60 seconds at 0.5s interval
        self._visible_seconds = 30  # show last 30 seconds
        self._tick_id = None
        self._get_a_value = None  # callback -> int
        self._get_b_value = None  # callback -> int

        self._build()

    def _build(self):
        t = self._theme

        # Header
        header = tk.Frame(self, bg=t.get("bg_header", "#16213e"))
        header.pack(fill="x", padx=2, pady=(2, 0))
        tk.Label(
            header, text="波形监视", bg=t.get("bg_header", "#16213e"),
            fg=t.get("text_primary", "#e0e0e0"),
            font=("Microsoft YaHei UI", 10, "bold"), anchor="w",
        ).pack(side="left", padx=8, pady=4)

        self._status_label = tk.Label(
            header, text="未连接", bg=t.get("bg_header", "#16213e"),
            fg=t.get("text_muted", "#666666"),
            font=("Microsoft YaHei UI", 9), anchor="e",
        )
        self._status_label.pack(side="right", padx=8, pady=4)

        # Matplotlib figure
        self._fig = Figure(figsize=(5, 2.5), dpi=100, facecolor=t.get("waveform_bg", "#0a0a1a"))
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
        self._ax.set_ylabel("强度", color=t.get("text_dim", "#888888"), fontsize=8)
        self._ax.tick_params(colors=t.get("text_muted", "#666666"), labelsize=7)
        for spine in self._ax.spines.values():
            spine.set_color(t.get("waveform_grid", "#333333"))

        self._line_a, = self._ax.plot(
            [], [], color=t.get("accent_green", "#66bb6a"),
            linewidth=1.8, label="A", alpha=0.9,
        )
        self._line_b, = self._ax.plot(
            [], [], color=t.get("accent_orange", "#ffb74d"),
            linewidth=1.8, label="B", alpha=0.9,
        )
        self._fill_a = None
        self._fill_b = None

        # Current-time cursor
        self._cursor = self._ax.axvline(
            x=0, color=t.get("accent_cyan", "#39d2c0"),
            linewidth=1.5, linestyle="--", alpha=0.6, zorder=10,
        )

        self._ax.legend(loc="upper right", fontsize=7,
                         facecolor=t.get("waveform_bg", "#0a0a1a"),
                         edgecolor=t.get("waveform_grid", "#333333"),
                         labelcolor=t.get("text_muted", "#666666"))
        self._ax.set_xlim(0, self._visible_seconds)
        self._ax.set_ylim(0, 200)
        self._fig.tight_layout(pad=1.5)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=2, pady=2)

        # Info label
        self._info_label = tk.Label(
            self, text="等待连接...", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_muted", "#666666"),
            font=("Microsoft YaHei UI", 9),
        )
        self._info_label.pack(pady=(0, 4))

    def start(self, get_a_value, get_b_value):
        """Start continuous sampling. get_a_value/get_b_value are callables returning int."""
        self._get_a_value = get_a_value
        self._get_b_value = get_b_value
        self._history.clear()
        if self._tick_id:
            self.after_cancel(self._tick_id)
        self._tick()

    def stop(self):
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        self._get_a_value = None
        self._get_b_value = None

    def _tick(self):
        """Sample strength values and render."""
        if self._get_a_value and self._get_b_value:
            try:
                a_val = self._get_a_value()
                b_val = self._get_b_value()
            except Exception:
                a_val, b_val = 0, 0
            now = time.time()
            # Only record when there's actual strength
            if a_val > 0 or b_val > 0:
                self._history.append((now, a_val, b_val))
            elif self._history:
                # Once idle, stop adding points but keep last known state
                last_ts, last_a, last_b = self._history[-1]
                if last_a > 0 or last_b > 0:
                    # Transition to idle: add one zero point to show the drop
                    self._history.append((now, 0, 0))
            self._render()
            self._update_info(a_val, b_val)

        self._tick_id = self.after(500, self._tick)

    def _render(self):
        if not self._history:
            return

        now = time.time()
        x_min = now - self._visible_seconds
        x_max = now

        xs_a, ys_a = [], []
        xs_b, ys_b = [], []
        for ts, a_val, b_val in self._history:
            if ts >= x_min - 1:
                xs_a.append(ts - x_min)
                ys_a.append(a_val)
                xs_b.append(ts - x_min)
                ys_b.append(b_val)

        self._line_a.set_data(xs_a, ys_a)
        self._line_b.set_data(xs_b, ys_b)

        # Update fill
        if self._fill_a is not None:
            self._fill_a.remove()
            self._fill_a = None
        if self._fill_b is not None:
            self._fill_b.remove()
            self._fill_b = None
        if xs_a and ys_a:
            self._fill_a = self._ax.fill_between(
                xs_a, ys_a, alpha=0.12,
                color=self._theme.get("accent_green", "#66bb6a"),
                linewidth=0,
            )
        if xs_b and ys_b:
            self._fill_b = self._ax.fill_between(
                xs_b, ys_b, alpha=0.12,
                color=self._theme.get("accent_orange", "#ffb74d"),
                linewidth=0,
            )

        # Cursor at right edge (now)
        self._cursor.set_xdata([self._visible_seconds])

        self._ax.set_xlim(0, self._visible_seconds)
        self._ax.set_ylim(0, 200)

        self._canvas.draw()

    def _update_info(self, a_val, b_val):
        self._info_label.configure(
            text=f"A: {a_val}  B: {b_val}",
            fg=self._theme.get("text_primary", "#e0e0e0"),
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
        self._line_a.set_data([], [])
        self._line_b.set_data([], [])
        if self._fill_a is not None:
            self._fill_a.remove()
            self._fill_a = None
        if self._fill_b is not None:
            self._fill_b.remove()
            self._fill_b = None
        self._cursor.set_xdata([self._visible_seconds])
        self._ax.set_xlim(0, self._visible_seconds)
        self._ax.set_ylim(0, 200)
        self._canvas.draw()
        self.set_disconnected()

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self.configure(bg=t.get("bg_panel", "#1a1a2e"))

        self._fig.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
        self._ax.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
        self._ax.set_ylabel("强度", color=t.get("text_dim", "#888888"), fontsize=8)
        self._ax.tick_params(colors=t.get("text_muted", "#666666"), labelsize=7)
        for spine in self._ax.spines.values():
            spine.set_color(t.get("waveform_grid", "#333333"))
        self._line_a.set_color(t.get("accent_green", "#66bb6a"))
        self._line_b.set_color(t.get("accent_orange", "#ffb74d"))
        self._cursor.set_color(t.get("accent_cyan", "#39d2c0"))
        self._ax.legend(loc="upper right", fontsize=7,
                         facecolor=t.get("waveform_bg", "#0a0a1a"),
                         edgecolor=t.get("waveform_grid", "#333333"),
                         labelcolor=t.get("text_muted", "#666666"))
        self._canvas.draw()
