import tkinter as tk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class WaveformPanel(tk.Frame):
    def __init__(self, master, theme: dict = None, **kwargs):
        self._theme = theme or {}
        super().__init__(master, bg=self._theme.get("bg_panel", "#1a1a2e"), **kwargs)

        # Animation state
        self._anim_id = None
        self._anim_start = 0.0
        self._playhead = 0.0
        self._a_data = []
        self._b_data = []
        self._total_entries = 0
        self._duration = 0
        self._a_intensity = 0
        self._b_intensity = 0
        self._mode = ""
        self._a_name = ""
        self._b_name = ""
        self._window_size = 1000  # visible window in ms

        self._build()

    def _build(self):
        t = self._theme

        # Header
        header = tk.Frame(self, bg=t.get("bg_header", "#16213e"))
        header.pack(fill="x", padx=2, pady=(2, 0))
        tk.Label(
            header, text="📊 波形预览", bg=t.get("bg_header", "#16213e"),
            fg=t.get("text_primary", "#e0e0e0"),
            font=("Microsoft YaHei UI", 10, "bold"), anchor="w",
        ).pack(side="left", padx=8, pady=4)

        self._preset_label = tk.Label(
            header, text="", bg=t.get("bg_header", "#16213e"),
            fg=t.get("accent_purple", "#e040fb"),
            font=("Microsoft YaHei UI", 9), anchor="e",
        )
        self._preset_label.pack(side="right", padx=8, pady=4)

        # Matplotlib figure
        self._fig = Figure(figsize=(5, 2.8), dpi=100, facecolor=t.get("waveform_bg", "#0a0a1a"))
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
        self._ax.set_xlabel("Time (ms)", color=t.get("text_dim", "#888888"), fontsize=8)
        self._ax.set_ylabel("Intensity", color=t.get("text_dim", "#888888"), fontsize=8)
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
        # Fill areas under curves for visual depth
        self._fill_a = None
        self._fill_b = None
        # Playhead cursor (thick, bright)
        self._cursor = self._ax.axvline(
            x=0, color=t.get("accent_cyan", "#39d2c0"),
            linewidth=2.0, linestyle="-", alpha=0.9, zorder=10,
        )
        # Playhead glow effect (wider, translucent)
        self._cursor_glow = self._ax.axvline(
            x=0, color=t.get("accent_cyan", "#39d2c0"),
            linewidth=6.0, linestyle="-", alpha=0.2, zorder=9,
        )
        # Vertical gradient bar at playhead position
        self._gradient_bars = []
        for i in range(5):
            alpha_val = 0.15 - i * 0.03
            bar = self._ax.axvline(
                x=0, color=t.get("accent_cyan", "#39d2c0"),
                linewidth=1.0, linestyle="-", alpha=max(alpha_val, 0.02), zorder=8,
            )
            self._gradient_bars.append(bar)

        self._ax.legend(loc="upper right", fontsize=7,
                         facecolor=t.get("waveform_bg", "#0a0a1a"),
                         edgecolor=t.get("waveform_grid", "#333333"),
                         labelcolor=t.get("text_muted", "#666666"))
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 200)
        self._fig.tight_layout(pad=1.5)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=2, pady=2)

        # Info label
        self._info_label = tk.Label(
            self, text="等待触发...", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_muted", "#666666"),
            font=("Microsoft YaHei UI", 9),
        )
        self._info_label.pack(pady=(0, 4))

    def update_waveform(self, a_data: list[int], b_data: list[int],
                        seconds: int, a_intensity: int, b_intensity: int,
                        mode: str, a_name: str = "", b_name: str = ""):
        if not a_data and not b_data:
            return

        # Stop previous animation
        self._stop_anim()

        # Store data
        self._a_data = a_data
        self._b_data = b_data
        self._total_entries = max(len(a_data), len(b_data))
        self._duration = self._total_entries * 100  # ms
        self._a_intensity = a_intensity
        self._b_intensity = b_intensity
        self._mode = mode
        self._a_name = a_name
        self._b_name = b_name

        # Window size: show ~3 seconds or full duration if shorter
        self._window_size = min(max(seconds * 1000, 3000), self._duration)

        # Start animation
        import time
        self._anim_start = time.time()
        self._playhead = 0

        # Update info immediately
        self._update_info()

        # Start animation loop
        self._tick()

    def _tick(self):
        """Animation tick - called every ~60ms for smooth playback."""
        import time
        now = time.time()
        elapsed_ms = (now - self._anim_start) * 1000

        if elapsed_ms >= self._duration:
            # Animation complete - show final state
            self._playhead = self._duration
            self._render_frame()
            self._info_label.configure(
                text=f"播放完成 | {self._mode_text()} | {self._duration // 1000}秒 "
                     f"| A:{self._a_intensity} B:{self._b_intensity}",
                fg=self._theme.get("text_muted", "#666666"),
            )
            return

        self._playhead = elapsed_ms
        self._render_frame()

        # ~15 FPS - enough for waveform visualization, avoids blocking UI
        self._anim_id = self.after(100, self._tick)

    def _render_frame(self):
        """Render the current visible window with scrolling-left effect."""
        win = self._window_size
        half = win / 2

        # Calculate visible X range - playhead stays at ~60% from left
        playhead_pos = 0.6
        if self._playhead <= half:
            x_min, x_max = 0, win
            cursor_x = self._playhead
        elif self._playhead >= self._duration - half:
            x_min, x_max = self._duration - win, self._duration
            cursor_x = self._playhead - x_min
        else:
            x_min = self._playhead - win * playhead_pos
            x_max = x_min + win
            cursor_x = self._playhead - x_min

        # Generate stepped X coordinates (each entry = 100ms)
        def get_stepped_xy(data, x_min, x_max):
            xs, ys = [], []
            for i, v in enumerate(data):
                x = i * 100
                if x_min - 100 <= x <= x_max + 100:
                    # Create stepped waveform (flat top per entry)
                    if xs and xs[-1] == x:
                        continue
                    xs.append(x)
                    ys.append(v)
            return xs, ys

        x_a, y_a = get_stepped_xy(self._a_data, x_min, x_max)
        x_b, y_b = get_stepped_xy(self._b_data, x_min, x_max)

        # Update line data
        self._line_a.set_data(x_a, y_a)
        self._line_b.set_data(x_b, y_b)

        # Remove old fills and create new ones
        if self._fill_a is not None:
            self._fill_a.remove()
            self._fill_a = None
        if self._fill_b is not None:
            self._fill_b.remove()
            self._fill_b = None

        if x_a and y_a:
            self._fill_a = self._ax.fill_between(
                x_a, y_a, alpha=0.15,
                color=self._theme.get("accent_green", "#66bb6a"),
                linewidth=0,
            )
        if x_b and y_b:
            self._fill_b = self._ax.fill_between(
                x_b, y_b, alpha=0.15,
                color=self._theme.get("accent_orange", "#ffb74d"),
                linewidth=0,
            )

        # Update cursor positions
        self._cursor.set_xdata([cursor_x])
        self._cursor_glow.set_xdata([cursor_x])
        # Gradient trail bars (spread behind playhead)
        trail_spacing = win * 0.015
        for i, bar in enumerate(self._gradient_bars):
            offset = -(i + 1) * trail_spacing
            bar.set_xdata([cursor_x + offset])

        # Update axes
        self._ax.set_xlim(x_min, x_max)
        all_y = y_a + y_b
        if all_y:
            self._ax.set_ylim(0, max(max(all_y) * 1.2, 10))

        self._canvas.draw()

    def _mode_text(self):
        return "一键开火" if self._mode == "instant" else "温柔加力"

    def _update_info(self):
        names = []
        if self._a_name:
            names.append(f"A:{self._a_name}")
        if self._b_name and self._b_name != self._a_name:
            names.append(f"B:{self._b_name}")
        name_str = " | ".join(names) if names else ""

        self._info_label.configure(
            text=f"{self._mode_text()} | {self._duration // 1000}秒 "
                 f"| A:{self._a_intensity} B:{self._b_intensity}",
            fg=self._theme.get("text_primary", "#e0e0e0"),
        )
        self._preset_label.configure(text=name_str)

    def _stop_anim(self):
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None

    def clear(self):
        self._stop_anim()
        t = self._theme
        self._a_data = []
        self._b_data = []
        self._total_entries = 0
        self._duration = 0
        self._line_a.set_data([], [])
        self._line_b.set_data([], [])
        if self._fill_a is not None:
            self._fill_a.remove()
            self._fill_a = None
        if self._fill_b is not None:
            self._fill_b.remove()
            self._fill_b = None
        self._cursor.set_xdata([0])
        self._cursor_glow.set_xdata([0])
        for bar in self._gradient_bars:
            bar.set_xdata([0])
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 200)
        self._canvas.draw()
        self._info_label.configure(text="等待触发...", fg=t.get("text_muted", "#666666"))
        self._preset_label.configure(text="")

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self.configure(bg=t.get("bg_panel", "#1a1a2e"))

        self._fig.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
        self._ax.set_facecolor(t.get("waveform_bg", "#0a0a1a"))
        self._ax.set_xlabel("Time (ms)", color=t.get("text_dim", "#888888"), fontsize=8)
        self._ax.set_ylabel("Intensity", color=t.get("text_dim", "#888888"), fontsize=8)
        self._ax.tick_params(colors=t.get("text_muted", "#666666"), labelsize=7)
        for spine in self._ax.spines.values():
            spine.set_color(t.get("waveform_grid", "#333333"))
        self._line_a.set_color(t.get("accent_green", "#66bb6a"))
        self._line_b.set_color(t.get("accent_orange", "#ffb74d"))
        self._cursor.set_color(t.get("accent_cyan", "#39d2c0"))
        self._cursor_glow.set_color(t.get("accent_cyan", "#39d2c0"))
        for bar in self._gradient_bars:
            bar.set_color(t.get("accent_cyan", "#39d2c0"))
        self._ax.legend(loc="upper right", fontsize=7,
                         facecolor=t.get("waveform_bg", "#0a0a1a"),
                         edgecolor=t.get("waveform_grid", "#333333"),
                         labelcolor=t.get("text_muted", "#666666"))

        for w in self._get_all_widgets():
            try:
                if isinstance(w, tk.Frame):
                    current_bg = str(w.cget("bg"))
                    if current_bg in ("#16213e",):
                        w.configure(bg=t.get("bg_header", "#16213e"))
                    else:
                        w.configure(bg=t.get("bg_panel", "#1a1a2e"))
                elif isinstance(w, tk.Label):
                    current_fg = str(w.cget("fg"))
                    if current_fg in ("#e0e0e0",):
                        w.configure(bg=t.get("bg_panel", "#1a1a2e"),
                                    fg=t.get("text_primary", "#e0e0e0"))
                    elif current_fg in ("#e040fb",):
                        w.configure(bg=t.get("bg_header", "#16213e"),
                                    fg=t.get("accent_purple", "#e040fb"))
                    else:
                        w.configure(bg=t.get("bg_panel", "#1a1a2e"),
                                    fg=t.get("text_muted", "#666666"))
            except (tk.TclError, KeyError):
                pass

        self._canvas.draw()

    def _get_all_widgets(self):
        widgets = []
        stack = [self]
        while stack:
            w = stack.pop()
            widgets.append(w)
            stack.extend(w.winfo_children())
        return widgets
