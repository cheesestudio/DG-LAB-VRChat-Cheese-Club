import tkinter as tk
import collections
import time
from matplotlib import rcParams
from matplotlib.figure import Figure

rcParams["font.sans-serif"] = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class WaveformPanel(tk.Frame):
    """Waveform display: scrolls left during active shock, clears when idle."""

    def __init__(self, master, theme: dict = None, **kwargs):
        self._theme = theme or {}
        super().__init__(master, bg=self._theme.get("bg_panel", "#1a1a2e"), **kwargs)

        # History buffer: (timestamp, a_value, b_value)
        self._history = collections.deque(maxlen=300)  # 60 seconds at 0.2s interval
        self._visible_seconds = 10  # show last 10 seconds
        self._tick_id = None
        self._get_a_value = None
        self._get_b_value = None
        self._active = False  # True during shock

        self._build()

    def _build(self):
        t = self._theme

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

        self._fig = Figure(figsize=(5, 2.5), dpi=100, facecolor=t.get("waveform_bg", "#0a0a1a"))
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
        self._ax.set_ylabel("强度", color=t.get("text_dim", "#888888"), fontsize=8)
        self._ax.tick_params(colors=t.get("text_muted", "#666666"), labelsize=7)
        for spine in self._ax.spines.values():
            spine.set_color(t.get("waveform_grid", "#333333"))

        self._line_a, = self._ax.plot([], [], color=t.get("draw_idle", "#66bb6a"),
                                       linewidth=1.5, label="A", alpha=0.9)
        self._line_b, = self._ax.plot([], [], color=t.get("accent_orange", "#ffb74d"),
                                       linewidth=1.5, label="B", alpha=0.9)
        self._fill_a = None
        self._fill_b = None

        self._ax.legend(loc="upper right", fontsize=7,
                         facecolor=t.get("waveform_bg", "#0a0a1a"),
                         edgecolor=t.get("waveform_grid", "#333333"),
                         labelcolor=t.get("text_muted", "#666666"))
        self._ax.set_xlim(0, self._visible_seconds)
        self._ax.set_ylim(0, 200)
        self._fig.tight_layout(pad=1.5)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=2, pady=2)

        self._info_label = tk.Label(
            self, text="等待连接...", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_muted", "#666666"),
            font=("Microsoft YaHei UI", 9),
        )
        self._info_label.pack(pady=(0, 4))

    def start(self, get_a_value, get_b_value):
        self._get_a_value = get_a_value
        self._get_b_value = get_b_value
        self._history.clear()
        self._active = False
        if self._tick_id:
            self.after_cancel(self._tick_id)
        self._tick()

    def stop(self):
        if self._tick_id:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        self._get_a_value = None
        self._get_b_value = None
        self._active = False

    def set_active(self, active: bool):
        """Call this when shock starts/stops."""
        self._active = active
        if not active:
            # Clear the display when shock ends
            self._history.clear()
            self._line_a.set_data([], [])
            self._line_b.set_data([], [])
            if self._fill_a is not None:
                self._fill_a.remove()
                self._fill_a = None
            if self._fill_b is not None:
                self._fill_b.remove()
                self._fill_b = None
            self._ax.set_xlim(0, self._visible_seconds)
            self._ax.set_ylim(0, 200)
            self._canvas.draw()

    def _tick(self):
        if not self._get_a_value or not self._get_b_value:
            return
        try:
            a_val = self._get_a_value()
            b_val = self._get_b_value()
        except Exception:
            a_val, b_val = 0, 0

        now = time.time()
        if self._active and (a_val > 0 or b_val > 0):
            self._history.append((now, a_val, b_val))
            self._render()
        self._update_info(a_val, b_val)
        self._tick_id = self.after(200, self._tick)

    def _render(self):
        if not self._history:
            return

        now = time.time()
        x_min = now - self._visible_seconds

        # Build stepped waveform (flat line per sample)
        xs_a, ys_a = [], []
        xs_b, ys_b = [], []
        entries = list(self._history)

        for i, (ts, a_val, b_val) in enumerate(entries):
            if ts < x_min - 0.5:
                continue
            x = ts - x_min
            # End of this segment = start of next, or current time
            if i + 1 < len(entries):
                x_end = entries[i + 1][0] - x_min
            else:
                x_end = self._visible_seconds

            # Horizontal line (constant value for this sample)
            xs_a.extend([x, x_end])
            ys_a.extend([a_val, a_val])
            xs_b.extend([x, x_end])
            ys_b.extend([b_val, b_val])

        self._line_a.set_data(xs_a, ys_a)
        self._line_b.set_data(xs_b, ys_b)

        # Fill
        if self._fill_a is not None:
            self._fill_a.remove()
            self._fill_a = None
        if self._fill_b is not None:
            self._fill_b.remove()
            self._fill_b = None
        if xs_a:
            self._fill_a = self._ax.fill_between(
                xs_a, ys_a, alpha=0.1,
                color=self._theme.get("accent_green", "#66bb6a"),
                linewidth=0,
            )
        if xs_b:
            self._fill_b = self._ax.fill_between(
                xs_b, ys_b, alpha=0.1,
                color=self._theme.get("accent_orange", "#ffb74d"),
                linewidth=0,
            )

        self._ax.set_xlim(0, self._visible_seconds)
        self._ax.set_ylim(0, 200)
        self._canvas.draw()

    def _update_info(self, a_val, b_val):
        status = "电击中" if self._active else "待机"
        self._info_label.configure(
            text=f"A: {a_val}  B: {b_val}  [{status}]",
            fg=self._theme.get("text_primary", "#e0e0e0"),
        )
        if self._active:
            self._status_label.configure(
                text="电击中",
                fg=self._theme.get("accent_orange", "#ffb74d"),
            )
        else:
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
        self._active = False
        self._line_a.set_data([], [])
        self._line_b.set_data([], [])
        if self._fill_a is not None:
            self._fill_a.remove()
            self._fill_a = None
        if self._fill_b is not None:
            self._fill_b.remove()
            self._fill_b = None
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
        self._ax.legend(loc="upper right", fontsize=7,
                         facecolor=t.get("waveform_bg", "#0a0a1a"),
                         edgecolor=t.get("waveform_grid", "#333333"),
                         labelcolor=t.get("text_muted", "#666666"))
        self._canvas.draw()
