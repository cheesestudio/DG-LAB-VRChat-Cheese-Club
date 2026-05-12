import tkinter as tk


class OSCPanel(tk.Frame):
    def __init__(self, master, theme: dict = None, on_osc_toggle=None, **kwargs):
        self._theme = theme or {}
        super().__init__(master, bg=self._theme.get("bg_panel", "#1a1a2e"), **kwargs)
        self._on_toggle = on_osc_toggle or (lambda connected: None)
        self._connected = False
        self._build()

    def _build(self):
        t = self._theme

        # Header
        header = tk.Frame(self, bg=t.get("bg_header", "#16213e"))
        header.pack(fill="x", padx=2, pady=(2, 0))
        tk.Label(
            header, text="🎮 VRChat OSC", bg=t.get("bg_header", "#16213e"),
            fg=t.get("text_primary", "#e0e0e0"),
            font=("Microsoft YaHei UI", 10, "bold"), anchor="w",
        ).pack(side="left", padx=8, pady=4)

        # Status
        status_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        status_frame.pack(fill="x", padx=8, pady=2)

        self._status_dot = tk.Canvas(status_frame, width=12, height=12,
                                     bg=t.get("bg_panel", "#1a1a2e"), highlightthickness=0)
        self._status_dot.pack(side="left", padx=(0, 6))
        self._draw_dot(t.get("text_muted", "#666666"))

        self._status_label = tk.Label(
            status_frame, text="未连接", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_secondary", "#b0b0b0"),
            font=("Microsoft YaHei UI", 9),
        )
        self._status_label.pack(side="left")

        # Chatbox port
        port_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        port_frame.pack(fill="x", padx=8, pady=2)

        tk.Label(
            port_frame, text="Chatbox端口:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_dim", "#888888"),
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        self._chatbox_port_var = tk.StringVar(value="9000")
        self._chatbox_port_entry = tk.Entry(
            port_frame, textvariable=self._chatbox_port_var,
            bg=t.get("bg_input", "#0a0a1a"), fg=t.get("text_primary", "#e0e0e0"),
            insertbackground=t.get("text_primary", "#e0e0e0"),
            font=("Consolas", 9), relief="flat", width=6,
        )
        self._chatbox_port_entry.pack(side="left", padx=(4, 0))

        # Avatar OSC port
        avt_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        avt_frame.pack(fill="x", padx=8, pady=2)

        tk.Label(
            avt_frame, text="Avatar端口:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_dim", "#888888"),
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        self._avatar_port_var = tk.StringVar(value="9001")
        self._avatar_port_entry = tk.Entry(
            avt_frame, textvariable=self._avatar_port_var,
            bg=t.get("bg_input", "#0a0a1a"), fg=t.get("text_primary", "#e0e0e0"),
            insertbackground=t.get("text_primary", "#e0e0e0"),
            font=("Consolas", 9), relief="flat", width=6,
        )
        self._avatar_port_entry.pack(side="left", padx=(4, 0))

        # Mode selection (A/B)
        mode_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        mode_frame.pack(fill="x", padx=8, pady=2)

        # Channel A mode
        ch_a = tk.Frame(mode_frame, bg=t.get("bg_panel", "#1a1a2e"))
        ch_a.pack(fill="x", pady=1)
        tk.Label(
            ch_a, text="A:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_cyan", "#39d2c0"),
            font=("Microsoft YaHei UI", 9, "bold"), width=3,
        ).pack(side="left")
        self._mode_a_var = tk.StringVar(value="distance")
        for txt, val in [("距离", "distance"), ("电击", "shock"), ("触感", "touch")]:
            tk.Radiobutton(
                ch_a, text=txt, variable=self._mode_a_var, value=val,
                bg=t.get("bg_panel", "#1a1a2e"), fg=t.get("text_primary", "#e0e0e0"),
                selectcolor=t.get("bg_input", "#0a0a1a"),
                activebackground=t.get("bg_panel", "#1a1a2e"),
                activeforeground=t.get("text_primary", "#e0e0e0"),
                font=("Microsoft YaHei UI", 8),
            ).pack(side="left", padx=2)

        # Channel B mode
        ch_b = tk.Frame(mode_frame, bg=t.get("bg_panel", "#1a1a2e"))
        ch_b.pack(fill="x", pady=1)
        tk.Label(
            ch_b, text="B:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_orange", "#ffb74d"),
            font=("Microsoft YaHei UI", 9, "bold"), width=3,
        ).pack(side="left")
        self._mode_b_var = tk.StringVar(value="distance")
        for txt, val in [("距离", "distance"), ("电击", "shock"), ("触感", "touch")]:
            tk.Radiobutton(
                ch_b, text=txt, variable=self._mode_b_var, value=val,
                bg=t.get("bg_panel", "#1a1a2e"), fg=t.get("text_primary", "#e0e0e0"),
                selectcolor=t.get("bg_input", "#0a0a1a"),
                activebackground=t.get("bg_panel", "#1a1a2e"),
                activeforeground=t.get("text_primary", "#e0e0e0"),
                font=("Microsoft YaHei UI", 8),
            ).pack(side="left", padx=2)

        # Buttons
        btn_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        btn_frame.pack(fill="x", padx=8, pady=4)

        self._connect_btn = tk.Button(
            btn_frame, text="连接", bg=t.get("bg_button", "#0f3460"),
            fg=t.get("text_primary", "#e0e0e0"),
            activebackground=t.get("bg_button_hover", "#1a5276"),
            activeforeground=t.get("text_primary", "#ffffff"),
            font=("Microsoft YaHei UI", 9, "bold"), relief="flat",
            cursor="hand2", command=self._on_connect_click, width=8,
        )
        self._connect_btn.pack(side="left", padx=(0, 4))

        self._disconnect_btn = tk.Button(
            btn_frame, text="关闭Chatbox", bg=t.get("bg_button_danger", "#4a1a1a"),
            fg=t.get("text_primary", "#e0e0e0"),
            activebackground=t.get("bg_button_danger_hover", "#6a2a2a"),
            activeforeground=t.get("text_primary", "#ffffff"),
            font=("Microsoft YaHei UI", 9), relief="flat",
            cursor="hand2", command=self._on_disconnect_click,
            state="disabled",
        )
        self._disconnect_btn.pack(side="left")

        # Received parameter display
        param_frame = tk.Frame(self, bg=t.get("bg_panel", "#1a1a2e"))
        param_frame.pack(fill="x", padx=8, pady=(2, 6))

        tk.Label(
            param_frame, text="接收参数:", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("text_dim", "#888888"),
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")

        self._param_label = tk.Label(
            param_frame, text="--", bg=t.get("bg_panel", "#1a1a2e"),
            fg=t.get("accent_cyan", "#39d2c0"),
            font=("Consolas", 9), anchor="w", justify="left",
            wraplength=260,
        )
        self._param_label.pack(anchor="w", pady=2)

    def _draw_dot(self, color: str):
        self._status_dot.delete("all")
        self._status_dot.create_oval(2, 2, 10, 10, fill=color, outline=color)

    def _on_connect_click(self):
        self._connect_btn.configure(state="disabled")
        self._disconnect_btn.configure(state="normal")
        self._connected = True
        self._status_label.configure(text="连接中...")
        self._draw_dot(self._theme.get("accent_orange", "#ffb74d"))
        self._on_toggle(True)

    def _on_disconnect_click(self):
        self._connect_btn.configure(state="normal")
        self._disconnect_btn.configure(state="disabled")
        self._connected = False
        self._status_label.configure(text="未连接")
        self._draw_dot(self._theme.get("text_muted", "#666666"))
        self._param_label.configure(text="--")
        self._on_toggle(False)

    def set_status(self, status: str):
        t = self._theme
        status_map = {
            "connecting": (t.get("accent_orange", "#ffb74d"), "连接中..."),
            "connected": (t.get("accent_green", "#66bb6a"), "已连接"),
            "disconnected": (t.get("text_muted", "#666666"), "未连接"),
        }
        color, text = status_map.get(status, (t.get("text_muted", "#666666"), "未知"))
        self._draw_dot(color)
        self._status_label.configure(text=text)

        if status == "disconnected":
            self._connect_btn.configure(state="normal")
            self._disconnect_btn.configure(state="disabled")
            self._connected = False
        elif status in ("connected", "connecting"):
            self._connect_btn.configure(state="disabled")
            self._disconnect_btn.configure(state="normal")

    def update_params(self, params: dict):
        if not params:
            self._param_label.configure(text="--")
            return
        lines = [f"{k}: {v}" for k, v in params.items()]
        self._param_label.configure(text="\n".join(lines[:6]))

    def get_chatbox_port(self) -> int:
        try:
            val = int(self._chatbox_port_var.get().strip())
            return max(1, min(65535, val))
        except ValueError:
            return 9000

    def set_chatbox_port(self, port: int):
        port = max(1, min(65535, int(port)))
        self._chatbox_port_var.set(str(port))

    def get_avatar_port(self) -> int:
        try:
            val = int(self._avatar_port_var.get().strip())
            return max(1, min(65535, val))
        except ValueError:
            return 9001

    def set_avatar_port(self, port: int):
        port = max(1, min(65535, int(port)))
        self._avatar_port_var.set(str(port))

    def get_mode_a(self) -> str:
        return self._mode_a_var.get()

    def set_mode_a(self, mode: str):
        self._mode_a_var.set(mode)

    def get_mode_b(self) -> str:
        return self._mode_b_var.get()

    def set_mode_b(self, mode: str):
        self._mode_b_var.set(mode)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self.configure(bg=t.get("bg_panel", "#1a1a2e"))
        for w in self._get_all_widgets():
            try:
                bg = t.get("bg_panel", "#1a1a2e")
                fg = t.get("text_primary", "#e0e0e0")
                if isinstance(w, tk.Canvas):
                    w.configure(bg=bg)
                elif isinstance(w, tk.Button):
                    txt = str(w.cget("text"))
                    if txt == "断开":
                        w.configure(bg=t.get("bg_button_danger", "#4a1a1a"), fg=fg,
                                    activebackground=t.get("bg_button_danger_hover", "#6a2a2a"))
                    else:
                        w.configure(bg=t.get("bg_button", "#0f3460"), fg=fg,
                                    activebackground=t.get("bg_button_hover", "#1a5276"))
                elif isinstance(w, tk.Entry):
                    w.configure(bg=t.get("bg_input", "#0a0a1a"), fg=fg, insertbackground=fg)
                elif isinstance(w, tk.Frame):
                    w.configure(bg=bg)
                elif isinstance(w, tk.Label):
                    current_fg = str(w.cget("fg"))
                    if "d2c0" in current_fg or "39d2c0" in current_fg:
                        w.configure(bg=bg, fg=t.get("accent_cyan", "#39d2c0"))
                    elif "ffb74d" in current_fg:
                        w.configure(bg=bg, fg=t.get("accent_orange", "#ffb74d"))
                    else:
                        w.configure(bg=bg, fg=t.get("text_secondary", "#b0b0b0"))
                elif isinstance(w, tk.Radiobutton):
                    w.configure(bg=bg, fg=fg, selectcolor=t.get("bg_input", "#0a0a1a"),
                                activebackground=bg, activeforeground=fg)
                elif isinstance(w, tk.Checkbutton):
                    w.configure(bg=bg, fg=fg, selectcolor=t.get("bg_input", "#0a0a1a"),
                                activebackground=bg, activeforeground=fg)
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
