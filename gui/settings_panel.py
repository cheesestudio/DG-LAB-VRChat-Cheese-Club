import tkinter as tk


class SettingsPanel(tk.Frame):
    def __init__(self, master, theme: dict = None, on_settings_change=None, on_theme_toggle=None, on_test_shock=None, **kwargs):
        self._theme = theme or {}
        super().__init__(master, bg=self._theme.get("bg_panel", "#1a1a2e"), **kwargs)
        self._on_change = on_settings_change or (lambda: None)
        self._on_theme_toggle = on_theme_toggle or (lambda: None)
        self._on_test_shock = on_test_shock or (lambda: None)
        self._build()

    def _build(self):
        t = self._theme

        # Header
        header = tk.Frame(self, bg=t.get("bg_header", "#16213e"))
        header.pack(fill="x", padx=2, pady=(2, 0))
        tk.Label(
            header, text="⚡ 电击设置", bg=t.get("bg_header", "#16213e"),
            fg=t.get("text_primary", "#e0e0e0"),
            font=("Microsoft YaHei UI", 10, "bold"), anchor="w",
        ).pack(side="left", padx=8, pady=4)

        self._theme_btn = tk.Button(
            header, text="🌙", bg=t.get("bg_button", "#0f3460"),
            fg=t.get("text_primary", "#e0e0e0"),
            activebackground=t.get("bg_button_hover", "#1a5276"),
            font=("Segoe UI Emoji", 11), relief="flat", cursor="hand2",
            command=self._on_theme_toggle, width=3,
        )
        self._theme_btn.pack(side="right", padx=8, pady=4)

        # A channel limit
        a_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        a_frame.pack(fill="x", padx=8, pady=2)

        tk.Label(
            a_frame, text="A上限:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_green", "#66bb6a"),
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")

        self._a_limit_var = tk.IntVar(value=200)
        self._a_limit_label = tk.Label(
            a_frame, text="200", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_green", "#66bb6a"),
            font=("Consolas", 10, "bold"), width=4,
        )
        self._a_limit_label.pack(side="right")

        self._a_limit_scale = tk.Scale(
            a_frame, from_=0, to=200, orient="horizontal",
            variable=self._a_limit_var, command=self._on_a_limit_change,
            bg=t.get("bg_panel", "#1a1a2e"), fg=t.get("text_secondary", "#b0b0b0"),
            troughcolor=t.get("bg_slider_trough", "#0f3460"),
            highlightthickness=0, sliderrelief="flat", length=130,
        )
        self._a_limit_scale.pack(side="right", padx=(8, 4))

        # B channel limit
        b_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        b_frame.pack(fill="x", padx=8, pady=2)

        tk.Label(
            b_frame, text="B上限:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_orange", "#ffb74d"),
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")

        self._b_limit_var = tk.IntVar(value=200)
        self._b_limit_label = tk.Label(
            b_frame, text="200", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_orange", "#ffb74d"),
            font=("Consolas", 10, "bold"), width=4,
        )
        self._b_limit_label.pack(side="right")

        self._b_limit_scale = tk.Scale(
            b_frame, from_=0, to=200, orient="horizontal",
            variable=self._b_limit_var, command=self._on_b_limit_change,
            bg=t.get("bg_panel", "#1a1a2e"), fg=t.get("text_secondary", "#b0b0b0"),
            troughcolor=t.get("bg_slider_trough", "#0f3460"),
            highlightthickness=0, sliderrelief="flat", length=130,
        )
        self._b_limit_scale.pack(side="right", padx=(8, 4))

        # Current strength display
        strength_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        strength_frame.pack(fill="x", padx=8, pady=2)

        tk.Label(
            strength_frame, text="当前:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_secondary", "#b0b0b0"),
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        self._a_label = tk.Label(
            strength_frame, text="A: 0", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_green", "#66bb6a"),
            font=("Consolas", 10, "bold"),
        )
        self._a_label.pack(side="left", padx=(8, 0))

        self._b_label = tk.Label(
            strength_frame, text="B: 0", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_orange", "#ffb74d"),
            font=("Consolas", 10, "bold"),
        )
        self._b_label.pack(side="left", padx=(8, 0))

        # Mode selection
        mode_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        mode_frame.pack(fill="x", padx=8, pady=(6, 2))

        tk.Label(
            mode_frame, text="模式", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_primary", "#e0e0e0"),
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="w")

        radio_frame = tk.Frame(mode_frame, bg=t.get("bg_panel", "#1a1a2e"))
        radio_frame.pack(fill="x", pady=2)

        self._mode_var = tk.StringVar(value="instant")

        self._instant_rb = tk.Radiobutton(
            radio_frame, text="一键开火", variable=self._mode_var,
            value="instant", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_purple", "#e040fb"),
            selectcolor=t.get("bg_button", "#0f3460"),
            activebackground=t.get("bg_panel", "#1a1a2e"),
            activeforeground=t.get("accent_purple", "#e040fb"),
            font=("Microsoft YaHei UI", 9), command=self._on_mode_change,
        )
        self._instant_rb.pack(side="left", padx=(0, 8))

        self._gradual_rb = tk.Radiobutton(
            radio_frame, text="温柔加力", variable=self._mode_var,
            value="gradual", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_blue", "#4fc3f7"),
            selectcolor=t.get("bg_button", "#0f3460"),
            activebackground=t.get("bg_panel", "#1a1a2e"),
            activeforeground=t.get("accent_blue", "#4fc3f7"),
            font=("Microsoft YaHei UI", 9), command=self._on_mode_change,
        )
        self._gradual_rb.pack(side="left")

        # Waveform mode
        wf_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        wf_frame.pack(fill="x", padx=8, pady=2)

        tk.Label(
            wf_frame, text="波形:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_secondary", "#b0b0b0"),
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        self._wf_var = tk.StringVar(value="library")
        for val, label in [("library", "波形库"), ("custom", "自定义")]:
            rb = tk.Radiobutton(
                wf_frame, text=label, variable=self._wf_var,
                value=val, bg=t.get("bg_panel", "#1a1a2e"),
                fg=t.get("text_secondary", "#b0b0b0"),
                selectcolor=t.get("bg_button", "#0f3460"),
                activebackground=t.get("bg_panel", "#1a1a2e"),
                font=("Microsoft YaHei UI", 9), command=self._on_mode_change,
            )
            rb.pack(side="left", padx=(0, 6))

        # Channel selection
        ch_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        ch_frame.pack(fill="x", padx=8, pady=4)

        tk.Label(
            ch_frame, text="通道:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_secondary", "#b0b0b0"),
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        self._channel_var = tk.StringVar(value="A")
        self._channel_rbs = []

        for ch in ["A", "B"]:
            rb = tk.Radiobutton(
                ch_frame, text=ch, variable=self._channel_var,
                value=ch, bg=t.get("bg_panel", "#1a1a2e"),
                fg=t.get("text_secondary", "#b0b0b0"),
                selectcolor=t.get("bg_button", "#0f3460"),
                activebackground=t.get("bg_panel", "#1a1a2e"),
                font=("Consolas", 10, "bold"),
                command=self._on_channel_change,
            )
            rb.pack(side="left", padx=4)
            self._channel_rbs.append(rb)

        # Test button
        test_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        test_frame.pack(fill="x", padx=8, pady=(6, 2))

        self._test_btn = tk.Button(
            test_frame, text="测试电击 (3秒双通道满)",
            bg=t.get("bg_button", "#0f3460"),
            fg=t.get("accent_red", "#ef5350"),
            activebackground=t.get("bg_button_hover", "#1a5276"),
            font=("Microsoft YaHei UI", 9, "bold"),
            relief="flat", cursor="hand2",
            command=self._on_test_click,
        )
        self._test_btn.pack(fill="x")

        # Custom chatbox line
        custom_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        custom_frame.pack(fill="x", padx=8, pady=(6, 2))

        tk.Label(
            custom_frame, text="Chatbox自定义:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_secondary", "#b0b0b0"),
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")

        self._custom_var = tk.StringVar(value="我是Saob")
        self._custom_entry = tk.Entry(
            custom_frame, textvariable=self._custom_var,
            bg=t.get("bg_input", "#0d1117"),
            fg=t.get("text_primary", "#e6edf3"),
            insertbackground=t.get("text_primary", "#e6edf3"),
            font=("Microsoft YaHei UI", 9),
            relief="flat", highlightthickness=1,
            highlightbackground=t.get("border_color", "#30363d"),
            highlightcolor=t.get("accent_cyan", "#39d2c0"),
        )
        self._custom_entry.pack(fill="x", pady=(2, 0))
        self._custom_entry.bind("<FocusOut>", lambda e: self._on_change())
        self._custom_entry.bind("<Return>", lambda e: self._on_change())

        # Chatbox line toggles
        toggle_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        toggle_frame.pack(fill="x", padx=8, pady=(6, 2))

        tk.Label(
            toggle_frame, text="Chatbox显示行:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_secondary", "#b0b0b0"),
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")

        self._cb_line1_var = tk.BooleanVar(value=True)
        self._cb_line2_var = tk.BooleanVar(value=True)
        self._cb_line3_var = tk.BooleanVar(value=True)
        self._cb_line4_var = tk.BooleanVar(value=True)
        self._cb_line5_var = tk.BooleanVar(value=True)

        toggles = [
            (self._cb_line1_var, "标题行"),
            (self._cb_line2_var, "强度行"),
            (self._cb_line3_var, "剩余秒数"),
            (self._cb_line4_var, "波形名"),
            (self._cb_line5_var, "自定义"),
        ]
        for var, text in toggles:
            cb = tk.Checkbutton(
                toggle_frame, text=text, variable=var,
                bg=t.get("bg_panel", "#1a1a2e"),
                fg=t.get("text_secondary", "#b0b0b0"),
                selectcolor=t.get("bg_button", "#0f3460"),
                activebackground=t.get("bg_panel", "#1a1a2e"),
                activeforeground=t.get("text_secondary", "#b0b0b0"),
                font=("Microsoft YaHei UI", 8),
                command=self._on_change,
            )
            cb.pack(side="left", padx=(0, 4))

    def _on_a_limit_change(self, value):
        val = int(float(value))
        self._a_limit_label.configure(text=str(val))
        self._on_change()

    def _on_b_limit_change(self, value):
        val = int(float(value))
        self._b_limit_label.configure(text=str(val))
        self._on_change()

    def _on_mode_change(self):
        self._on_change()

    def _on_channel_change(self):
        self._on_change()

    def _on_test_click(self):
        self._on_test_shock()

    def get_a_limit(self) -> int:
        return self._a_limit_var.get()

    def get_b_limit(self) -> int:
        return self._b_limit_var.get()

    def get_mode(self) -> str:
        return self._mode_var.get()

    def get_channel(self) -> str:
        return self._channel_var.get()

    def get_waveform_mode(self) -> str:
        return self._wf_var.get()

    def set_a_limit(self, value: int):
        self._a_limit_var.set(value)
        self._a_limit_label.configure(text=str(value))

    def set_b_limit(self, value: int):
        self._b_limit_var.set(value)
        self._b_limit_label.configure(text=str(value))

    def set_mode(self, mode: str):
        self._mode_var.set(mode)

    def set_channel(self, channel: str):
        self._channel_var.set(channel)

    def set_waveform_mode(self, mode: str):
        self._wf_var.set(mode)

    def get_custom_chatbox(self) -> str:
        return self._custom_var.get().strip()

    def set_custom_chatbox(self, text: str):
        self._custom_var.set(text)

    def get_chatbox_toggles(self) -> dict:
        return {
            "line1": self._cb_line1_var.get(),
            "line2": self._cb_line2_var.get(),
            "line3": self._cb_line3_var.get(),
            "line4": self._cb_line4_var.get(),
            "line5": self._cb_line5_var.get(),
        }

    def set_chatbox_toggles(self, t: dict):
        self._cb_line1_var.set(t.get("line1", True))
        self._cb_line2_var.set(t.get("line2", True))
        self._cb_line3_var.set(t.get("line3", True))
        self._cb_line4_var.set(t.get("line4", True))
        self._cb_line5_var.set(t.get("line5", True))

    def update_strength(self, a: int, b: int):
        self._a_label.configure(text=f"A: {a}")
        self._b_label.configure(text=f"B: {b}")

    def set_theme_button_text(self, theme_name: str):
        self._theme_btn.configure(text="☀️" if theme_name == "light" else "🌙")

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self.configure(bg=t.get("bg_panel", "#1a1a2e"))
        for w in self._get_all_widgets():
            try:
                bg = t.get("bg_panel", "#1a1a2e")
                fg = t.get("text_primary", "#e0e0e0")
                if isinstance(w, tk.Scale):
                    w.configure(bg=bg, fg=t.get("text_secondary", "#b0b0b0"),
                                troughcolor=t.get("bg_slider_trough", "#0f3460"))
                elif isinstance(w, tk.Radiobutton):
                    current_fg = str(w.cget("fg"))
                    if current_fg in ("#e040fb",):
                        w.configure(bg=bg, fg=t.get("accent_purple", "#e040fb"),
                                    selectcolor=t.get("bg_button", "#0f3460"), activebackground=bg)
                    elif current_fg in ("#4fc3f7",):
                        w.configure(bg=bg, fg=t.get("accent_blue", "#4fc3f7"),
                                    selectcolor=t.get("bg_button", "#0f3460"), activebackground=bg)
                    else:
                        w.configure(bg=bg, fg=t.get("text_secondary", "#b0b0b0"),
                                    selectcolor=t.get("bg_button", "#0f3460"), activebackground=bg)
                elif isinstance(w, tk.Button):
                    w.configure(bg=t.get("bg_button", "#0f3460"), fg=fg,
                                activebackground=t.get("bg_button_hover", "#1a5276"))
                elif isinstance(w, tk.Frame):
                    w.configure(bg=bg)
                elif isinstance(w, tk.Label):
                    current_fg = str(w.cget("fg"))
                    if current_fg in ("#66bb6a",):
                        w.configure(bg=bg, fg=t.get("accent_green", "#66bb6a"))
                    elif current_fg in ("#ffb74d",):
                        w.configure(bg=bg, fg=t.get("accent_orange", "#ffb74d"))
                    elif current_fg in ("#4fc3f7",):
                        w.configure(bg=bg, fg=t.get("accent_blue", "#4fc3f7"))
                    else:
                        w.configure(bg=bg, fg=t.get("text_secondary", "#b0b0b0"))
            except (tk.TclError, KeyError):
                pass

    def _get_all_widgets(self):
        widgets = []
        stack = [self]
        while stack:
            w = stack.pop()
            widgets.append(w)
            stack.extend(w.winfo_children())
        return widgets
