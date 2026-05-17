THEME = {
    # 背景层次 (从深到浅)
    "bg_base": "#111111",       # 最底层
    "bg_panel": "#1a1a1a",      # 面板/卡片背景
    "bg_elevated": "#242424",   # 悬浮/弹出层
    "bg_input": "#161616",      # 输入框背景
    "bg_hover": "#2d2d2d",      # 悬停态

    # 边框
    "border": "#333333",
    "border_focus": "#d4a054",

    # 文字层次
    "text": "#e4e4e7",          # 主文字
    "text_secondary": "#a1a1aa",  # 次要文字
    "text_dim": "#71717a",      # 暗淡文字
    "text_muted": "#52525b",    # 最暗文字/占位符

    # 强调色
    "accent": "#d4a054",        # 主强调 (琥珀金)
    "accent_hover": "#b8893e",  # 强调悬停
    "accent_muted": "#9c7232",  # 强调按下

    # 语义色
    "success": "#22c55e",
    "success_hover": "#16a34a",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "warning": "#f59e0b",

    # 通道色
    "channel_a": "#34d399",     # 翠绿
    "channel_b": "#fbbf24",     # 琥珀

    # 控制台
    "console_bg": "#0d0d0d",
    "console_text": "#a1a1aa",
    "console_info": "#60a5fa",
    "console_warning": "#fbbf24",
    "console_error": "#f87171",
    "console_success": "#34d399",
    "console_shock": "#a78bfa",

    # 波形
    "waveform_bg": "#111111",
    "waveform_grid": "#242424",
    "waveform_line_a": "#34d399",
    "waveform_line_b": "#fbbf24",

    # 状态
    "status_online": "#22c55e",
    "status_offline": "#52525b",
    "status_warning": "#f59e0b",
    "status_error": "#ef4444",
}


def get_theme(name: str = "dark") -> dict:
    return THEME


def get_theme_names() -> list:
    return ["dark"]
