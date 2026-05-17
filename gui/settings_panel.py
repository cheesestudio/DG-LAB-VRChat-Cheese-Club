import customtkinter as ctk
from tkinter import StringVar, IntVar, BooleanVar
from waveform_library import get_names


class SettingsPanel(ctk.CTkScrollableFrame):
    """电击设置面板 - CustomTkinter 重写版"""

    # 配色常量
    _BG_PANEL = "#1a1a1a"
    _BG_CARD = "#242424"
    _BG_INPUT = "#161616"
    _BORDER = "#333333"
    _TEXT_PRIMARY = "#e4e4e7"
    _TEXT_SECONDARY = "#a1a1aa"
    _TEXT_DIM = "#71717a"
    _ACCENT = "#d4a054"
    _CH_A = "#34d399"
    _CH_B = "#fbbf24"
    _SUCCESS = "#22c55e"
    _DANGER = "#ef4444"
    _WARNING = "#f59e0b"

    def __init__(self, master, theme=None, on_settings_change=None, on_test_shock=None, **kwargs):
        super().__init__(
            master,
            fg_color=self._BG_PANEL,
            scrollbar_button_color=self._BORDER,
            scrollbar_button_hover_color=self._ACCENT,
            **kwargs,
        )
        self._on_change = on_settings_change or (lambda: None)
        self._on_test_shock = on_test_shock or (lambda: None)
        self._chatbox_enabled_callback = None
        self._build()

    # ─── UI 构建 ───────────────────────────────────────────────────────

    def _make_group(self, parent=None) -> ctk.CTkFrame:
        """创建一个分组卡片"""
        frame = ctk.CTkFrame(
            parent or self,
            fg_color=self._BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=self._BORDER,
        )
        frame.pack(fill="x", pady=8)
        return frame

    def _build(self):
        # ── 电击设置组 ──
        main_group = self._make_group()

        # 标题
        ctk.CTkLabel(
            main_group, text="电击设置",
            text_color=self._TEXT_PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # ── A 通道上限 ──
        self._build_limit_slider(main_group, "A上限", self._CH_A, is_a=True)

        # ── B 通道上限 ──
        self._build_limit_slider(main_group, "B上限", self._CH_B, is_a=False)

        # ── 当前强度 ──
        strength_row = ctk.CTkFrame(main_group, fg_color="transparent")
        strength_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            strength_row, text="当前强度",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left")

        self._a_label = ctk.CTkLabel(
            strength_row, text="A: 0",
            text_color=self._CH_A, font=ctk.CTkFont(family="Consolas", size=12),
        )
        self._a_label.pack(side="left", padx=(8, 16))

        self._b_label = ctk.CTkLabel(
            strength_row, text="B: 0",
            text_color=self._CH_B, font=ctk.CTkFont(family="Consolas", size=12),
        )
        self._b_label.pack(side="left")

        # ── 模式选择 ──
        mode_row = ctk.CTkFrame(main_group, fg_color="transparent")
        mode_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            mode_row, text="模式",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        self._mode_var = StringVar(value="一键开火")
        self._MODE_TO_LABEL = {"instant": "一键开火", "gradual": "温柔加力", "max": "拉满"}
        self._LABEL_TO_MODE = {"一键开火": "instant", "温柔加力": "gradual", "拉满": "max"}
        self._mode_seg = ctk.CTkSegmentedButton(
            mode_row,
            values=["一键开火", "温柔加力", "拉满"],
            variable=self._mode_var,
            command=self._on_mode_change,
            font=ctk.CTkFont(size=12),
            fg_color=self._BG_INPUT,
            selected_color=self._ACCENT,
            selected_hover_color="#9c7232",
            unselected_color=self._BG_INPUT,
            unselected_hover_color=self._BORDER,
            text_color=self._TEXT_PRIMARY,
        )
        self._mode_seg.pack(side="left", fill="x", expand=True)

        # ── 波形模式 ──
        wf_row = ctk.CTkFrame(main_group, fg_color="transparent")
        wf_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            wf_row, text="波形",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        self._wf_var = StringVar(value="波形库")
        self._WF_TO_LABEL = {"library": "波形库", "custom": "自定义"}
        self._WF_LABEL_TO_MODE = {"波形库": "library", "自定义": "custom"}
        self._wf_seg = ctk.CTkSegmentedButton(
            wf_row,
            values=["波形库", "自定义"],
            variable=self._wf_var,
            command=self._on_wf_mode_change,
            font=ctk.CTkFont(size=12),
            fg_color=self._BG_INPUT,
            selected_color=self._ACCENT,
            selected_hover_color="#9c7232",
            unselected_color=self._BG_INPUT,
            unselected_hover_color=self._BORDER,
            text_color=self._TEXT_PRIMARY,
        )
        self._wf_seg.pack(side="left", fill="x", expand=True)

        # ── 波形库选择（默认隐藏） ──
        self._wf_names = get_names()
        self._custom_wf_frame = ctk.CTkFrame(main_group, fg_color="transparent")

        ctk.CTkLabel(
            self._custom_wf_frame, text="选择波形",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        self._custom_wf_var = StringVar(value=self._wf_names[0] if self._wf_names else "")
        self._custom_wf_menu = ctk.CTkOptionMenu(
            self._custom_wf_frame,
            values=self._wf_names if self._wf_names else [""],
            variable=self._custom_wf_var,
            command=lambda _: self._on_change(),
            fg_color=self._BG_INPUT,
            button_color=self._BORDER,
            button_hover_color=self._ACCENT,
            dropdown_fg_color=self._BG_INPUT,
            dropdown_hover_color=self._ACCENT,
            text_color=self._TEXT_PRIMARY,
            font=ctk.CTkFont(size=12),
            corner_radius=6,
        )
        self._custom_wf_menu.pack(fill="x", pady=(4, 0))
        self._update_custom_wf_visibility()

        # ── 通道选择 ──
        ch_row = ctk.CTkFrame(main_group, fg_color="transparent")
        ch_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            ch_row, text="通道",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        self._channel_var = StringVar(value="A")
        self._channel_seg = ctk.CTkSegmentedButton(
            ch_row,
            values=["A", "B"],
            variable=self._channel_var,
            command=self._on_channel_change,
            font=ctk.CTkFont(size=12),
            fg_color=self._BG_INPUT,
            selected_color=self._ACCENT,
            selected_hover_color="#9c7232",
            unselected_color=self._BG_INPUT,
            unselected_hover_color=self._BORDER,
            text_color=self._TEXT_PRIMARY,
            dynamic_resizing=False,
        )
        self._channel_seg.pack(side="left")

        self._dual_var = BooleanVar(value=False)
        self._dual_switch = ctk.CTkSwitch(
            ch_row, text="双通道",
            variable=self._dual_var,
            command=self._on_dual_toggle,
            font=ctk.CTkFont(size=12),
            text_color=self._TEXT_SECONDARY,
            progress_color=self._ACCENT,
            button_color=self._TEXT_DIM,
            button_hover_color=self._TEXT_SECONDARY,
            fg_color=self._BORDER,
        )
        self._dual_switch.pack(side="left", padx=(16, 0))

        self._alternate_var = BooleanVar(value=False)
        self._alternate_switch = ctk.CTkSwitch(
            ch_row, text="波形交替",
            variable=self._alternate_var,
            command=lambda: self._on_change(),
            font=ctk.CTkFont(size=12),
            text_color=self._TEXT_SECONDARY,
            progress_color=self._ACCENT,
            button_color=self._TEXT_DIM,
            button_hover_color=self._TEXT_SECONDARY,
            fg_color=self._BORDER,
        )
        self._alternate_switch.pack(side="left", padx=(16, 0))

        # ── 测试电击按钮 ──
        self._test_btn = ctk.CTkButton(
            main_group, text="测试电击 (3秒双通道)",
            command=self._on_test_shock,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self._ACCENT,
            hover_color="#9c7232",
            text_color="#ffffff",
            corner_radius=6,
            height=36,
        )
        self._test_btn.pack(fill="x", padx=16, pady=(0, 12))

        # ── Chatbox 设置组 ──
        chatbox_group = self._make_group()

        ctk.CTkLabel(
            chatbox_group, text="Chatbox 设置",
            text_color=self._TEXT_PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # Chatbox 自定义文本
        ctk.CTkLabel(
            chatbox_group, text="Chatbox自定义",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=16)

        self._chatbox_entry = ctk.CTkEntry(
            chatbox_group,
            fg_color=self._BG_INPUT,
            border_color=self._BORDER,
            text_color=self._TEXT_PRIMARY,
            font=ctk.CTkFont(size=12),
            corner_radius=6,
        )
        self._chatbox_entry.pack(fill="x", padx=16, pady=(4, 12))

        # Chatbox 显示行开关
        ctk.CTkLabel(
            chatbox_group, text="Chatbox显示行",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=16)

        toggles_row = ctk.CTkFrame(chatbox_group, fg_color="transparent")
        toggles_row.pack(fill="x", padx=16, pady=(4, 12))

        self._chatbox_toggles = {}
        toggle_labels = ["全部", "标题行", "强度行", "剩余秒数", "波形名", "自定义"]
        for label in toggle_labels:
            var = BooleanVar(value=(label == "全部"))
            sw = ctk.CTkSwitch(
                toggles_row, text=label,
                variable=var,
                command=self._on_change,
                font=ctk.CTkFont(size=11),
                text_color=self._TEXT_SECONDARY,
                progress_color=self._ACCENT,
                button_color=self._TEXT_DIM,
                button_hover_color=self._TEXT_SECONDARY,
                fg_color=self._BORDER,
                width=40,
            )
            sw.pack(side="left", padx=(0, 12))
            self._chatbox_toggles[label] = var

        # ── 统计组 ──
        stats_group = self._make_group()

        ctk.CTkLabel(
            stats_group, text="电击统计",
            text_color=self._TEXT_PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 8))

        self._stats_a_label = ctk.CTkLabel(
            stats_group, text="A: 0秒 | 强度x时间: 0",
            text_color=self._CH_A,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self._stats_a_label.pack(anchor="w", padx=16, pady=(0, 4))

        self._stats_b_label = ctk.CTkLabel(
            stats_group, text="B: 0秒 | 强度x时间: 0",
            text_color=self._CH_B,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self._stats_b_label.pack(anchor="w", padx=16, pady=(0, 12))

        # ── 安全模式组 ──
        safety_group = self._make_group()

        safety_header = ctk.CTkFrame(safety_group, fg_color="transparent")
        safety_header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            safety_header, text="安全模式",
            text_color=self._TEXT_PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        self._safety_mode_var = BooleanVar(value=True)
        self._safety_switch = ctk.CTkSwitch(
            safety_header, text="启用",
            variable=self._safety_mode_var,
            command=lambda: self._on_change(),
            font=ctk.CTkFont(size=12),
            text_color=self._SUCCESS,
            progress_color=self._SUCCESS,
            button_color=self._TEXT_DIM,
            button_hover_color=self._TEXT_SECONDARY,
            fg_color=self._BORDER,
        )
        self._safety_switch.pack(side="right")

        ctk.CTkLabel(
            safety_group, text="限制累计电击时间的最高上限",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # 安全时长滑块
        dur_row = ctk.CTkFrame(safety_group, fg_color="transparent")
        dur_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            dur_row, text="最大累计时长",
            text_color=self._TEXT_DIM, font=ctk.CTkFont(size=12),
        ).pack(side="left")

        self._safety_max_var = IntVar(value=15)
        self._safety_max_label = ctk.CTkLabel(
            dur_row, text="15秒",
            text_color=self._WARNING,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
        )
        self._safety_max_label.pack(side="right")

        self._safety_max_slider = ctk.CTkSlider(
            dur_row,
            from_=5, to=60, number_of_steps=55,
            variable=self._safety_max_var,
            command=self._on_safety_max_change,
            fg_color=self._BORDER,
            progress_color=self._WARNING,
            button_color=self._WARNING,
            button_hover_color="#fcd34d",
            width=160,
        )
        self._safety_max_slider.pack(side="right", padx=(8, 8))

    # ─── 辅助构建方法 ─────────────────────────────────────────────────

    def _build_limit_slider(self, parent, label_text: str, color: str, is_a: bool):
        """构建通道上限滑块行"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            row, text=label_text,
            text_color=color, font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        var = IntVar(value=200)
        value_label = ctk.CTkLabel(
            row, text="200",
            text_color=color,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            width=40,
        )
        value_label.pack(side="right")

        slider = ctk.CTkSlider(
            row,
            from_=0, to=200, number_of_steps=200,
            variable=var,
            command=lambda v, lbl=value_label: self._on_limit_change(v, lbl),
            fg_color=self._BORDER,
            progress_color=color,
            button_color=color,
            button_hover_color=color,
            width=180,
        )
        slider.pack(side="right", padx=(8, 8))

        if is_a:
            self._a_limit_var = var
            self._a_limit_label = value_label
            self._a_limit_slider = slider
        else:
            self._b_limit_var = var
            self._b_limit_label = value_label
            self._b_limit_slider = slider

    # ─── 内部回调 ─────────────────────────────────────────────────────

    def _on_limit_change(self, value, label):
        label.configure(text=str(int(value)))
        self._on_change()

    def _on_mode_change(self, _value):
        self._on_change()

    def _on_wf_mode_change(self, _value):
        self._update_custom_wf_visibility()
        self._on_change()

    def _on_channel_change(self, _value):
        self._on_change()

    def _on_dual_toggle(self):
        dual = self._dual_var.get()
        state = "disabled" if dual else "normal"
        self._channel_seg.configure(state=state)
        self._on_change()

    def _on_safety_max_change(self, value):
        self._safety_max_label.configure(text=f"{int(value)}秒")
        self._on_change()

    def _update_custom_wf_visibility(self):
        if self._wf_var.get() == "自定义":
            self._custom_wf_frame.pack(fill="x", padx=16, pady=(0, 12))
        else:
            self._custom_wf_frame.pack_forget()

    # ─── 公开 API ─────────────────────────────────────────────────────

    def get_a_limit(self) -> int:
        return self._a_limit_var.get()

    def set_a_limit(self, value: int):
        self._a_limit_var.set(value)
        self._a_limit_label.configure(text=str(value))

    def get_b_limit(self) -> int:
        return self._b_limit_var.get()

    def set_b_limit(self, value: int):
        self._b_limit_var.set(value)
        self._b_limit_label.configure(text=str(value))

    def get_mode(self) -> str:
        label = self._mode_var.get()
        return self._LABEL_TO_MODE.get(label, "instant")

    def set_mode(self, mode: str):
        label = self._MODE_TO_LABEL.get(mode, "一键开火")
        self._mode_var.set(label)

    def get_waveform_mode(self) -> str:
        label = self._wf_var.get()
        return self._WF_LABEL_TO_MODE.get(label, "library")

    def set_waveform_mode(self, mode: str):
        label = self._WF_TO_LABEL.get(mode, "波形库")
        self._wf_var.set(label)
        self._update_custom_wf_visibility()

    def get_channel(self) -> str:
        return self._channel_var.get()

    def set_channel(self, channel: str):
        self._channel_var.set(channel)

    def get_dual_channel(self) -> bool:
        return self._dual_var.get()

    def set_dual_channel(self, dual: bool):
        self._dual_var.set(dual)
        state = "disabled" if dual else "normal"
        self._channel_seg.configure(state=state)

    def get_alternate_waveform(self) -> bool:
        return self._alternate_var.get()

    def set_alternate_waveform(self, alternate: bool):
        self._alternate_var.set(alternate)

    def get_max_mode(self) -> bool:
        return self._mode_var.get() == "拉满"

    def set_max_mode(self, max_mode: bool):
        if max_mode:
            self._mode_var.set("拉满")

    def get_custom_waveform(self) -> str:
        return self._custom_wf_var.get()

    def set_custom_waveform(self, waveform: str):
        if waveform in self._wf_names:
            self._custom_wf_var.set(waveform)

    def set_chatbox_enabled(self, enabled: bool):
        if hasattr(self, '_chatbox_toggles') and "全部" in self._chatbox_toggles:
            self._chatbox_toggles["全部"].set(enabled)

    def get_chatbox_enabled(self) -> bool:
        if hasattr(self, '_chatbox_toggles') and "全部" in self._chatbox_toggles:
            return self._chatbox_toggles["全部"].get()
        return True

    def set_custom_chatbox(self, text: str):
        if hasattr(self, '_chatbox_entry'):
            self._chatbox_entry.delete(0, "end")
            self._chatbox_entry.insert(0, text)

    def get_custom_chatbox(self) -> str:
        if hasattr(self, '_chatbox_entry'):
            return self._chatbox_entry.get().strip()
        return ""

    def set_chatbox_toggles(self, toggles: dict):
        if hasattr(self, '_chatbox_toggles'):
            for key, value in toggles.items():
                if key in self._chatbox_toggles:
                    self._chatbox_toggles[key].set(value)

    def get_chatbox_toggles(self) -> dict:
        return {k: v.get() for k, v in self._chatbox_toggles.items()}

    def set_theme_button_text(self, theme_name: str):
        """No-op: 主题切换已移除"""
        pass

    def set_on_chatbox_enabled(self, callback):
        self._chatbox_enabled_callback = callback

    def set_chatbox_enabled_callback(self, callback):
        self._chatbox_enabled_callback = callback

    def get_safety_mode(self) -> bool:
        return self._safety_mode_var.get()

    def set_safety_mode(self, enabled: bool):
        self._safety_mode_var.set(enabled)

    def get_safety_max_seconds(self) -> int:
        return self._safety_max_var.get()

    def set_safety_max_seconds(self, value: int):
        self._safety_max_var.set(value)
        self._safety_max_label.configure(text=f"{value}秒")

    def update_stats(self, a_seconds, b_seconds, a_intensity_time, b_intensity_time):
        self._stats_a_label.configure(
            text=f"A: {a_seconds}秒 | 强度x时间: {int(a_intensity_time)}"
        )
        self._stats_b_label.configure(
            text=f"B: {b_seconds}秒 | 强度x时间: {int(b_intensity_time)}"
        )

    def set_strength(self, a: int, b: int):
        self._a_label.configure(text=f"A: {a}")
        self._b_label.configure(text=f"B: {b}")

    def update_strength(self, a: int, b: int):
        self.set_strength(a, b)

    def apply_theme(self, theme: dict):
        """No-op: 配色已硬编码"""
        pass
