"""日志控制台面板 - CustomTkinter 版本"""

import customtkinter as ctk
from datetime import datetime


class ConsolePanel(ctk.CTkFrame):
    """日志控制台面板"""

    # 标签颜色映射
    TAG_COLORS = {
        "info": "#e4e4e7",
        "debug": "#a1a1aa",
        "warning": "#fbbf24",
        "error": "#ef4444",
        "success": "#22c55e",
        "channel_a": "#34d399",
        "channel_b": "#fbbf24",
    }

    def __init__(self, master, theme=None, **kwargs):
        kwargs.setdefault("fg_color", "#1a1a1a")
        super().__init__(master, **kwargs)

        self._theme = theme or {}
        self._debug_enabled = False

        self._build_ui()
        self._setup_tags()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- 标题栏 ---
        header = ctk.CTkFrame(self, fg_color="transparent", height=36)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="日志", text_color="#e4e4e7",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self._debug_btn = ctk.CTkButton(
            header, text="Debug", width=60,
            font=ctk.CTkFont(size=11),
            fg_color="#333333", hover_color="#3a3a4a",
            text_color="#a1a1aa", corner_radius=4,
            command=self._toggle_debug
        )
        self._debug_btn.grid(row=0, column=1, padx=(4, 4))

        self._clear_btn = ctk.CTkButton(
            header, text="清空", width=60,
            font=ctk.CTkFont(size=11),
            fg_color="#333333", hover_color="#3a3a4a",
            text_color="#a1a1aa", corner_radius=4,
            command=self._clear_log
        )
        self._clear_btn.grid(row=0, column=2, padx=(0, 0))

        # --- 日志文本框 ---
        self._textbox = ctk.CTkTextbox(
            self, fg_color="#0d0d0d", text_color="#e4e4e7",
            font=ctk.CTkFont(family="Consolas", size=11),
            border_color="#333333", border_width=1,
            corner_radius=6, wrap="word", state="disabled"
        )
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))

    def _setup_tags(self):
        """配置文本标签颜色"""
        text_widget = self._textbox._textbox  # 内部 tk.Text
        for tag_name, color in self.TAG_COLORS.items():
            text_widget.tag_configure(tag_name, foreground=color)

    def _toggle_debug(self):
        """切换 debug 模式"""
        self._debug_enabled = not self._debug_enabled
        if self._debug_enabled:
            self._debug_btn.configure(fg_color="#d4a054", text_color="#e4e4e7")
        else:
            self._debug_btn.configure(fg_color="#333333", text_color="#a1a1aa")

    def _clear_log(self):
        """清空日志"""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")

    # --- 公开方法 ---
    def append(self, text: str, tag: str = "info"):
        """追加日志文本"""
        if tag == "debug" and not self._debug_enabled:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {text}\n"

        self._textbox.configure(state="normal")
        text_widget = self._textbox._textbox
        text_widget.insert("end", line, tag)
        self._textbox.configure(state="disabled")
        self._textbox.see("end")

    def apply_theme(self, theme: dict):
        pass  # no-op，配色已硬编码
