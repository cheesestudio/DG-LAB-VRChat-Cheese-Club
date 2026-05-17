"""VRChat OSC 连接面板 - CustomTkinter 版本"""

import customtkinter as ctk


class OSCPanel(ctk.CTkFrame):
    """VRChat OSC 连接控制面板"""

    MODE_OPTIONS = ["距离", "电击", "触感"]
    _MODE_TO_LABEL = {"distance": "距离", "shock": "电击", "touch": "触感"}
    _LABEL_TO_MODE = {"距离": "distance", "电击": "shock", "触感": "touch"}

    def __init__(self, master, theme=None, on_osc_toggle=None, **kwargs):
        kwargs.setdefault("fg_color", "#1a1a1a")
        super().__init__(master, **kwargs)

        self._theme = theme or {}
        self._on_osc_toggle = on_osc_toggle
        self._connected = False

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # --- 状态区 ---
        status_frame = ctk.CTkFrame(
            self, fg_color="#242424", border_color="#333333",
            border_width=1, corner_radius=8
        )
        status_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        status_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            status_frame, text="OSC 状态:", text_color="#a1a1aa",
            font=ctk.CTkFont(size=13)
        ).grid(row=0, column=0, padx=(12, 4), pady=10, sticky="w")

        self._status_label = ctk.CTkLabel(
            status_frame, text="未连接", text_color="#ef4444",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self._status_label.grid(row=0, column=1, padx=4, pady=10, sticky="w")

        # --- 端口区 ---
        port_frame = ctk.CTkFrame(
            self, fg_color="#242424", border_color="#333333",
            border_width=1, corner_radius=8
        )
        port_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        port_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            port_frame, text="Chatbox 端口:", text_color="#a1a1aa",
            font=ctk.CTkFont(size=12)
        ).grid(row=0, column=0, padx=(12, 4), pady=(10, 4), sticky="w")

        self._chatbox_port_entry = ctk.CTkEntry(
            port_frame, width=100, fg_color="#161616",
            border_color="#333333", text_color="#e4e4e7"
        )
        self._chatbox_port_entry.insert(0, "9000")
        self._chatbox_port_entry.grid(row=0, column=1, padx=(4, 12), pady=(10, 4), sticky="w")

        ctk.CTkLabel(
            port_frame, text="Avatar 端口:", text_color="#a1a1aa",
            font=ctk.CTkFont(size=12)
        ).grid(row=1, column=0, padx=(12, 4), pady=(4, 10), sticky="w")

        ctk.CTkLabel(
            port_frame, text="9001 (固定)", text_color="#71717a",
            font=ctk.CTkFont(size=12)
        ).grid(row=1, column=1, padx=(4, 12), pady=(4, 10), sticky="w")

        # --- 通道模式区 ---
        mode_frame = ctk.CTkFrame(
            self, fg_color="#242424", border_color="#333333",
            border_width=1, corner_radius=8
        )
        mode_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        mode_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            mode_frame, text="通道 A 模式:", text_color="#34d399",
            font=ctk.CTkFont(size=12)
        ).grid(row=0, column=0, padx=(12, 4), pady=(10, 4), sticky="w")

        self._mode_a_seg = ctk.CTkSegmentedButton(
            mode_frame, values=self.MODE_OPTIONS,
            font=ctk.CTkFont(size=12),
            selected_color="#d4a054", selected_hover_color="#b8893e",
            unselected_color="#161616", unselected_hover_color="#333333",
            text_color="#e4e4e7"
        )
        self._mode_a_seg.set("距离")
        self._mode_a_seg.grid(row=0, column=1, padx=(4, 12), pady=(10, 4), sticky="ew")

        ctk.CTkLabel(
            mode_frame, text="通道 B 模式:", text_color="#fbbf24",
            font=ctk.CTkFont(size=12)
        ).grid(row=1, column=0, padx=(12, 4), pady=(4, 10), sticky="w")

        self._mode_b_seg = ctk.CTkSegmentedButton(
            mode_frame, values=self.MODE_OPTIONS,
            font=ctk.CTkFont(size=12),
            selected_color="#d4a054", selected_hover_color="#b8893e",
            unselected_color="#161616", unselected_hover_color="#333333",
            text_color="#e4e4e7"
        )
        self._mode_b_seg.set("距离")
        self._mode_b_seg.grid(row=1, column=1, padx=(4, 12), pady=(4, 10), sticky="ew")

        # --- 按钮区 ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self._connect_btn = ctk.CTkButton(
            btn_frame, text="连接", font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#22c55e", hover_color="#16a34a", text_color="#e4e4e7",
            corner_radius=6, command=self._on_connect
        )
        self._connect_btn.grid(row=0, column=0, padx=(0, 4), pady=4, sticky="ew")

        self._disconnect_btn = ctk.CTkButton(
            btn_frame, text="断开", font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#ef4444", hover_color="#dc2626", text_color="#e4e4e7",
            corner_radius=6, command=self._on_disconnect, state="disabled"
        )
        self._disconnect_btn.grid(row=0, column=1, padx=(4, 0), pady=4, sticky="ew")

        # --- 接收参数区 ---
        params_frame = ctk.CTkFrame(
            self, fg_color="#242424", border_color="#333333",
            border_width=1, corner_radius=8
        )
        params_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(4, 8))
        params_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            params_frame, text="接收参数", text_color="#a1a1aa",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")

        self._params_label = ctk.CTkLabel(
            params_frame, text="暂无数据", text_color="#71717a",
            font=ctk.CTkFont(family="Consolas", size=11),
            justify="left", anchor="w", width=280,
        )
        self._params_label.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        # 参数更新节流
        self._params_last_update = 0
        self._params_pending = None
        self._params_throttle_ms = 200  # 最多每 200ms 更新一次

    # --- 回调 ---
    def _on_connect(self):
        self._connected = True
        self._connect_btn.configure(state="disabled")
        self._disconnect_btn.configure(state="normal")
        self.set_status("已连接")
        if self._on_osc_toggle:
            self._on_osc_toggle(True)

    def _on_disconnect(self):
        self._connected = False
        self._connect_btn.configure(state="normal")
        self._disconnect_btn.configure(state="disabled")
        self.set_status("未连接")
        if self._on_osc_toggle:
            self._on_osc_toggle(False)

    # --- 公开方法 ---
    def set_status(self, status: str):
        """设置状态文本"""
        self._status_label.configure(text=status)
        if "已连接" in status or "connected" in status.lower():
            self._status_label.configure(text_color="#22c55e")
        else:
            self._status_label.configure(text_color="#ef4444")

    def update_params(self, params: dict):
        """更新接收参数显示（节流 + 固定宽度格式化）"""
        import time
        now = time.time() * 1000
        if now - self._params_last_update < self._params_throttle_ms:
            # 节流期间暂存最新数据，不立即更新
            if self._params_pending is None:
                self.after(self._params_throttle_ms, self._flush_params)
            self._params_pending = params
            return
        self._params_last_update = now
        self._params_pending = None
        self._render_params(params)

    def _flush_params(self):
        """刷新暂存的参数数据"""
        if self._params_pending is not None:
            import time
            self._params_last_update = time.time() * 1000
            params = self._params_pending
            self._params_pending = None
            self._render_params(params)

    def _render_params(self, params: dict):
        """渲染参数文本（固定格式，避免宽度跳动）"""
        if not params:
            self._params_label.configure(text="暂无数据")
            return
        lines = []
        for k, v in list(params.items())[:6]:
            # 截断路径，固定值宽度
            path = k if len(k) <= 28 else "..." + k[-25:]
            if isinstance(v, float):
                val = f"{v:>8.4f}"
            elif isinstance(v, bool):
                val = f"{'True':>8}" if v else f"{'False':>8}"
            else:
                val = f"{str(v):>8}"
            lines.append(f"{path}: {val}")
        self._params_label.configure(text="\n".join(lines))

    def get_chatbox_port(self) -> int:
        try:
            return int(self._chatbox_port_entry.get())
        except (ValueError, TypeError):
            return 9000

    def set_chatbox_port(self, port: int):
        self._chatbox_port_entry.delete(0, "end")
        self._chatbox_port_entry.insert(0, str(port))

    def get_avatar_port(self) -> int:
        return 9001

    def set_avatar_port(self, port: int):
        pass  # no-op, 固定 9001

    def get_mode_a(self) -> str:
        label = self._mode_a_seg.get()
        return self._LABEL_TO_MODE.get(label, "distance")

    def set_mode_a(self, mode: str):
        label = self._MODE_TO_LABEL.get(mode, "距离")
        if label in self.MODE_OPTIONS:
            self._mode_a_seg.set(label)

    def get_mode_b(self) -> str:
        label = self._mode_b_seg.get()
        return self._LABEL_TO_MODE.get(label, "distance")

    def set_mode_b(self, mode: str):
        label = self._MODE_TO_LABEL.get(mode, "距离")
        if label in self.MODE_OPTIONS:
            self._mode_b_seg.set(label)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _draw_dot(self, *args, **kwargs):
        """兼容旧接口：通过更新 status_label 颜色模拟状态点"""
        color = kwargs.get("color", args[0] if args else None)
        if color:
            self._status_label.configure(text_color=color)

    def apply_theme(self, theme: dict):
        pass  # no-op，配色已硬编码
