"""自定义 OSC 参数联动规则面板 - CustomTkinter 版本"""

import customtkinter as ctk
import json
import base64
import zlib


class CustomParamsPanel(ctk.CTkFrame):
    """自定义 OSC 参数联动规则面板"""

    CHANNEL_OPTIONS = ["A", "B", "AB"]
    TYPE_OPTIONS = ["bool", "int", "float"]
    OPERATOR_OPTIONS = ["==", "!=", ">", "<", ">=", "<="]

    def __init__(self, master, theme=None, on_rules_change=None, **kwargs):
        kwargs.setdefault("fg_color", "#1a1a1a")
        super().__init__(master, **kwargs)

        self._theme = theme or {}
        self._on_rules_change = on_rules_change
        self._rules: list = []

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1, minsize=380)
        self.grid_rowconfigure(1, weight=1)

        # --- 标题栏 ---
        header = ctk.CTkFrame(self, fg_color="transparent", height=36)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="自定义参数规则", text_color="#e4e4e7",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self._count_label = ctk.CTkLabel(
            header, text="(0)", text_color="#71717a",
            font=ctk.CTkFont(size=12)
        )
        self._count_label.grid(row=0, column=1, padx=(4, 8))

        self._add_btn = ctk.CTkButton(
            header, text="+ 新建", width=70,
            font=ctk.CTkFont(size=12),
            fg_color="#d4a054", hover_color="#b8893e",
            text_color="#e4e4e7", corner_radius=4,
            command=self._show_form
        )
        self._add_btn.grid(row=0, column=2)

        # 导入/导出按钮
        self._export_btn = ctk.CTkButton(
            header, text="导出", width=50,
            font=ctk.CTkFont(size=11),
            fg_color="#333333", hover_color="#2d2d2d",
            text_color="#a1a1aa", corner_radius=4,
            command=self._export_rules
        )
        self._export_btn.grid(row=0, column=3, padx=(6, 0))

        self._import_btn = ctk.CTkButton(
            header, text="导入", width=50,
            font=ctk.CTkFont(size=11),
            fg_color="#333333", hover_color="#2d2d2d",
            text_color="#a1a1aa", corner_radius=4,
            command=self._import_rules
        )
        self._import_btn.grid(row=0, column=4, padx=(4, 0))

        # --- 规则列表 ---
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="#0d0d0d", border_color="#333333",
            border_width=1, corner_radius=6
        )
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._list_frame.grid_columnconfigure(0, weight=1)

        # --- 新建表单（默认隐藏）---
        self._form_frame = ctk.CTkFrame(
            self, fg_color="#242424", border_color="#333333",
            border_width=1, corner_radius=8
        )
        # 不 grid，初始隐藏

        self._build_form()

    def _build_form(self):
        """构建新建规则表单"""
        f = self._form_frame
        f.grid_columnconfigure(1, weight=1)

        # 路径（前缀固定显示，用户只输入参数名）
        path_row = ctk.CTkFrame(f, fg_color="transparent")
        path_row.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="ew")
        path_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(path_row, text="OSC 路径:", text_color="#a1a1aa",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 4), sticky="w")
        ctk.CTkLabel(path_row, text="/avatar/parameters/", text_color="#52525b",
                     font=ctk.CTkFont(family="Consolas", size=11)).grid(row=0, column=1, sticky="w")
        self._form_path = ctk.CTkEntry(
            path_row, fg_color="#161616", border_color="#333333",
            text_color="#e4e4e7", placeholder_text="参数名称"
        )
        self._form_path.grid(row=0, column=2, padx=(0, 0), sticky="ew")
        path_row.grid_columnconfigure(2, weight=1)

        # 通道
        ctk.CTkLabel(f, text="通道:", text_color="#a1a1aa",
                     font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=(12, 4), pady=4, sticky="w")
        self._form_channel = ctk.CTkSegmentedButton(
            f, values=self.CHANNEL_OPTIONS, font=ctk.CTkFont(size=11),
            selected_color="#d4a054", selected_hover_color="#b8893e",
            unselected_color="#161616", unselected_hover_color="#333333",
            text_color="#e4e4e7"
        )
        self._form_channel.set("A")
        self._form_channel.grid(row=1, column=1, padx=(4, 12), pady=4, sticky="ew")

        # 类型
        ctk.CTkLabel(f, text="类型:", text_color="#a1a1aa",
                     font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, padx=(12, 4), pady=4, sticky="w")
        self._form_type = ctk.CTkSegmentedButton(
            f, values=self.TYPE_OPTIONS, font=ctk.CTkFont(size=11),
            selected_color="#d4a054", selected_hover_color="#b8893e",
            unselected_color="#161616", unselected_hover_color="#333333",
            text_color="#e4e4e7", command=self._on_type_change
        )
        self._form_type.set("bool")
        self._form_type.grid(row=2, column=1, padx=(4, 12), pady=4, sticky="ew")

        # 条件（运算符 + 值）— 用于 int/float
        self._cond_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._cond_frame.grid(row=3, column=0, columnspan=2, padx=12, pady=4, sticky="ew")
        self._cond_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self._cond_frame, text="条件:", text_color="#a1a1aa",
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(0, 4), sticky="w")

        self._form_operator = ctk.CTkOptionMenu(
            self._cond_frame, values=self.OPERATOR_OPTIONS, width=70,
            fg_color="#161616", button_color="#333333",
            button_hover_color="#3a3a4a", text_color="#e4e4e7",
            font=ctk.CTkFont(size=11)
        )
        self._form_operator.set("==")
        self._form_operator.grid(row=0, column=1, padx=4, sticky="w")

        self._form_value = ctk.CTkEntry(
            self._cond_frame, width=100, fg_color="#161616",
            border_color="#333333", text_color="#e4e4e7",
            placeholder_text="值"
        )
        self._form_value.grid(row=0, column=2, padx=(4, 0), sticky="w")

        # Bool 值选择 — 用于 bool 类型
        self._bool_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._bool_frame.grid(row=3, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(self._bool_frame, text="触发值:", text_color="#a1a1aa",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self._form_bool_var = ctk.StringVar(value="true")
        self._form_bool_seg = ctk.CTkSegmentedButton(
            self._bool_frame, values=["true", "false"],
            variable=self._form_bool_var,
            font=ctk.CTkFont(size=11),
            selected_color="#d4a054", selected_hover_color="#b8893e",
            unselected_color="#161616", unselected_hover_color="#333333",
            text_color="#e4e4e7", width=120,
        )
        self._form_bool_seg.pack(side="left")

        # 初始状态：bool 模式
        self._on_type_change("bool")

        # 时长
        ctk.CTkLabel(f, text="时长(ms):", text_color="#a1a1aa",
                     font=ctk.CTkFont(size=12)).grid(
            row=4, column=0, padx=(12, 4), pady=4, sticky="w")
        self._form_duration = ctk.CTkEntry(
            f, width=100, fg_color="#161616",
            border_color="#333333", text_color="#e4e4e7",
            placeholder_text="1000"
        )
        self._form_duration.insert(0, "1000")
        self._form_duration.grid(row=4, column=1, padx=(4, 12), pady=4, sticky="w")

        # 表单按钮
        form_btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        form_btn_frame.grid(row=5, column=0, columnspan=2, padx=12, pady=(4, 10), sticky="ew")
        form_btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            form_btn_frame, text="确认添加", font=ctk.CTkFont(size=12),
            fg_color="#22c55e", hover_color="#16a34a",
            text_color="#e4e4e7", corner_radius=4,
            command=self._submit_form
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            form_btn_frame, text="取消", font=ctk.CTkFont(size=12),
            fg_color="#333333", hover_color="#3a3a4a",
            text_color="#a1a1aa", corner_radius=4,
            command=self._hide_form
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

    # --- 表单控制 ---
    def _on_type_change(self, selected_type: str):
        """切换类型时显示/隐藏对应的值输入控件。"""
        if selected_type == "bool":
            self._cond_frame.grid_remove()
            self._bool_frame.grid(row=3, column=0, columnspan=2, padx=12, pady=4, sticky="ew")
        else:
            self._bool_frame.grid_remove()
            self._cond_frame.grid(row=3, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

    def _show_form(self):
        self._form_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

    def _hide_form(self):
        self._form_frame.grid_forget()

    def _submit_form(self):
        """提交新规则"""
        raw_path = self._form_path.get().strip()
        if not raw_path:
            return

        # 自动补全前缀
        if raw_path.startswith("/"):
            path = raw_path  # 用户输入了完整路径，直接使用
        else:
            path = "/avatar/parameters/" + raw_path

        rule_type = self._form_type.get()

        # 解析值
        if rule_type == "bool":
            value = self._form_bool_var.get() == "true"
            value_str = ""
        else:
            value_str = self._form_value.get().strip()
            if rule_type == "int":
                try:
                    value = int(value_str)
                except ValueError:
                    value = 0
            else:
                try:
                    value = float(value_str)
                except ValueError:
                    value = 0.0

        try:
            duration = int(self._form_duration.get().strip())
        except ValueError:
            duration = 1000

        rule = {
            "path": path,
            "channel": self._form_channel.get(),
            "type": rule_type,
            "value": value,
            "operator": self._form_operator.get(),
            "duration": duration,
            "enabled": True,
        }

        self._rules.append(rule)
        self._hide_form()
        self._refresh_list()
        self._notify_change()

        # 清空表单
        self._form_path.delete(0, "end")
        self._form_value.delete(0, "end")
        self._form_duration.delete(0, "end")
        self._form_duration.insert(0, "1000")

    # --- 列表渲染 ---
    def _refresh_list(self):
        """重新渲染规则列表"""
        for widget in self._list_frame.winfo_children():
            widget.destroy()

        self._count_label.configure(text=f"({len(self._rules)})")

        for idx, rule in enumerate(self._rules):
            self._create_rule_card(idx, rule)

    def _create_rule_card(self, idx: int, rule: dict):
        """创建单条规则卡片"""
        card = ctk.CTkFrame(
            self._list_frame, fg_color="#242424",
            border_color="#333333", border_width=1, corner_radius=6
        )
        card.grid(row=idx, column=0, sticky="ew", padx=4, pady=3)
        card.grid_columnconfigure(1, weight=1)

        # 启用开关
        switch_var = ctk.BooleanVar(value=rule.get("enabled", True))
        switch = ctk.CTkSwitch(
            card, text="", variable=switch_var, width=40,
            progress_color="#d4a054", button_color="#e4e4e7",
            button_hover_color="#b8893e",
            command=lambda i=idx, v=switch_var: self._toggle_rule(i, v)
        )
        switch.grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=8)

        # 路径（第一行）
        ch_color = "#34d399" if rule["channel"] == "A" else (
            "#fbbf24" if rule["channel"] == "B" else "#e4e4e7"
        )
        path_text = f"[{rule['channel']}] {rule['path']}"
        ctk.CTkLabel(
            card, text=path_text, text_color=ch_color,
            font=ctk.CTkFont(family="Consolas", size=11)
        ).grid(row=0, column=1, padx=4, pady=(8, 0), sticky="w")

        # 条件（第二行）
        cond_text = (
            f"{rule['type']} {rule['operator']} {rule['value']}  "
            f"| {rule['duration']}ms"
        )
        ctk.CTkLabel(
            card, text=cond_text, text_color="#71717a",
            font=ctk.CTkFont(size=11)
        ).grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")

        # 删除按钮
        ctk.CTkButton(
            card, text="✕", width=28, height=28,
            font=ctk.CTkFont(size=12),
            fg_color="transparent", hover_color="#ef4444",
            text_color="#71717a", corner_radius=4,
            command=lambda i=idx: self._delete_rule(i)
        ).grid(row=0, column=2, rowspan=2, padx=(4, 8), pady=8)

    # --- 规则操作 ---
    def _toggle_rule(self, idx: int, var: ctk.BooleanVar):
        if 0 <= idx < len(self._rules):
            self._rules[idx]["enabled"] = var.get()
            self._notify_change()

    def _delete_rule(self, idx: int):
        if 0 <= idx < len(self._rules):
            self._rules.pop(idx)
            self._refresh_list()
            self._notify_change()

    def _notify_change(self):
        if self._on_rules_change:
            self._on_rules_change(self._rules)

    # --- 导入导出 ---
    def _encode_rules(self, rules: list) -> str:
        """将规则列表编码为可分享的字符串。"""
        data = json.dumps(rules, ensure_ascii=False, separators=(",", ":"))
        compressed = zlib.compress(data.encode("utf-8"), level=9)
        return base64.urlsafe_b64encode(compressed).decode("ascii")

    def _decode_rules(self, text: str) -> list:
        """从分享字符串解码规则列表。"""
        raw = base64.urlsafe_b64decode(text.strip())
        data = zlib.decompress(raw).decode("utf-8")
        rules = json.loads(data)
        if not isinstance(rules, list):
            raise ValueError("无效的规则数据")
        return rules

    def _export_rules(self):
        """导出当前规则到剪贴板。"""
        if not self._rules:
            self._show_toast("没有规则可导出")
            return
        encoded = self._encode_rules(self._rules)
        self.clipboard_clear()
        self.clipboard_append(encoded)
        self._show_toast(f"已复制到剪贴板 ({len(self._rules)} 条规则)")

    def _import_rules(self):
        """从剪贴板导入规则。"""
        try:
            text = self.clipboard_get()
        except Exception:
            self._show_toast("剪贴板为空", error=True)
            return

        if not text or not text.strip():
            self._show_toast("剪贴板为空", error=True)
            return

        try:
            new_rules = self._decode_rules(text)
        except Exception:
            self._show_toast("无效的规则字符串", error=True)
            return

        # 验证规则格式
        valid_rules = []
        for r in new_rules:
            if isinstance(r, dict) and "path" in r and "channel" in r:
                valid_rules.append({
                    "path": str(r.get("path", "")),
                    "channel": str(r.get("channel", "A")),
                    "type": str(r.get("type", "bool")),
                    "value": r.get("value", True),
                    "operator": str(r.get("operator", "==")),
                    "duration": int(r.get("duration", 2)),
                    "enabled": bool(r.get("enabled", True)),
                })

        if not valid_rules:
            self._show_toast("未找到有效规则", error=True)
            return

        # 追加到现有规则
        self._rules.extend(valid_rules)
        self._refresh_list()
        self._notify_change()
        self._show_toast(f"已导入 {len(valid_rules)} 条规则")

    def _show_toast(self, message: str, error: bool = False):
        """在面板底部短暂显示提示信息。"""
        color = "#ef4444" if error else "#22c55e"
        toast = ctk.CTkLabel(
            self, text=message, text_color=color,
            font=ctk.CTkFont(size=11), fg_color="#242424",
            corner_radius=4, height=24,
        )
        toast.grid(row=3, column=0, padx=8, pady=(0, 4), sticky="ew")
        # 2 秒后自动消失
        self.after(2000, toast.destroy)

    # --- 公开方法 ---
    def set_rules(self, rules: list):
        """设置规则列表"""
        self._rules = [dict(r) for r in rules]
        self._refresh_list()

    def get_rules(self) -> list:
        """获取当前规则列表"""
        return [dict(r) for r in self._rules]

    def apply_theme(self, theme: dict):
        pass  # no-op，配色已硬编码
