"""主窗口 — CustomTkinter 标签页布局，固定暗色主题。

标签页：
1. 主控制 — 连接 + 电击设置
2. 参数联动 — OSC + 自定义规则
3. 监控 — 波形 + 日志
"""
import customtkinter as ctk
import os
import queue
import threading
from constants import (
    APP_NAME, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT, CLEANUP_TIMEOUT_SECONDS,
)
from gui.connection_panel import ConnectionPanel
from gui.settings_panel import SettingsPanel
from gui.console_panel import ConsolePanel
from gui.waveform_panel import WaveformPanel
from gui.osc_panel import OSCPanel
from gui.custom_params_panel import CustomParamsPanel

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MainWindow:
    def __init__(self, app, theme: dict = None):
        self._app = app
        self._theme = theme or {}
        self._root = ctk.CTk()
        self._shutdown_event = threading.Event()
        self._cleanup_done = threading.Event()

        self._root.title(f"{APP_NAME}")
        self._root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")
        self._root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self._root.configure(fg_color="#111111")

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app_icon.ico",
        )
        if os.path.exists(icon_path):
            self._root.iconbitmap(icon_path)

        self._after_ids = set()
        self._thread_queue = queue.Queue()  # 线程安全的回调队列
        self._build_ui()
        self._poll_thread_queue()  # 启动主线程轮询
    def _build_ui(self):
        # === Header bar ===
        header = ctk.CTkFrame(self._root, height=36, corner_radius=0,
                              fg_color="#1a1a1a", border_width=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="芝士郊狼",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#e4e4e7").pack(side="left", padx=(16, 4))
        ctk.CTkLabel(header, text="控制中心",
                     font=ctk.CTkFont(size=13),
                     text_color="#71717a").pack(side="left")

        self._connection_status = ctk.CTkLabel(
            header, text="○ 未连接",
            font=ctk.CTkFont(size=12),
            text_color="#52525b")
        self._connection_status.pack(side="right", padx=16)

        # === Tabview ===
        self._tabview = ctk.CTkTabview(
            self._root, corner_radius=6,
            fg_color="#111111",
            segmented_button_fg_color="#1a1a1a",
            segmented_button_selected_color="#d4a054",
            segmented_button_selected_hover_color="#b8893e",
            segmented_button_unselected_color="#1a1a1a",
            segmented_button_unselected_hover_color="#2d2d2d",
            border_width=0,
        )
        self._tabview.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        tab1 = self._tabview.add("主控制")
        tab2 = self._tabview.add("参数联动")
        tab3 = self._tabview.add("监控")

        # --- Tab 1: Control ---
        tab1.grid_columnconfigure(0, weight=2)
        tab1.grid_columnconfigure(1, weight=3)
        tab1.grid_rowconfigure(0, weight=1)

        self.connection_panel = ConnectionPanel(tab1, theme=self._theme,
                                               on_connect=self._app.on_connect,
                                               on_disconnect=self._app.on_disconnect)
        self.connection_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)

        self.settings_panel = SettingsPanel(tab1, theme=self._theme,
                                           on_settings_change=self._app.on_settings_change,
                                           on_test_shock=self._app.on_test_shock)
        self.settings_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)

        # --- Tab 2: Params ---
        tab2.grid_columnconfigure(0, weight=2, minsize=300)
        tab2.grid_columnconfigure(1, weight=3, minsize=400)
        tab2.grid_rowconfigure(0, weight=1)

        self.osc_panel = OSCPanel(tab2, theme=self._theme,
                                  on_osc_toggle=self._app.on_osc_toggle)
        self.osc_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)

        self.custom_params_panel = CustomParamsPanel(tab2, theme=self._theme,
                                                    on_rules_change=self._app.on_custom_rules_change)
        self.custom_params_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)

        # --- Tab 3: Monitor ---
        tab3.grid_columnconfigure(0, weight=1)
        tab3.grid_rowconfigure(0, weight=2)
        tab3.grid_rowconfigure(1, weight=3)

        self.waveform_panel = WaveformPanel(tab3, theme=self._theme)
        self.waveform_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 5))

        self.console_panel = ConsolePanel(tab3, theme=self._theme)
        self.console_panel.grid(row=1, column=0, sticky="nsew", padx=0, pady=(5, 0))

    # === Public API ===

    def update_connection_status(self, paired: bool, server_running: bool = False):
        if paired:
            self._connection_status.configure(text="● 已配对", text_color="#22c55e")
            self._root.title(f"{APP_NAME} - 已配对")
        elif server_running:
            self._connection_status.configure(text="◌ 等待连接", text_color="#f59e0b")
            self._root.title(f"{APP_NAME} - 等待连接")
        else:
            self._connection_status.configure(text="○ 未连接", text_color="#52525b")
            self._root.title(f"{APP_NAME}")

    def apply_theme(self, theme: dict):
        """No-op: 固定暗色主题，无需切换。"""
        pass

    def run(self):
        def _on_close():
            if self._app._closing:
                return
            self._shutdown_event.set()
            self._app.on_close()
            self.waveform_panel.shutdown()
            for aid in list(self._after_ids):
                try:
                    self._root.after_cancel(aid)
                except Exception:
                    pass
            self._after_ids.clear()
            self._root.withdraw()

            def _cleanup():
                try:
                    self._app._do_cleanup()
                except Exception:
                    pass
                finally:
                    self._cleanup_done.set()
            threading.Thread(target=_cleanup, daemon=True).start()
            self._root.after(100, self._root.quit)

        self._root.protocol("WM_DELETE_WINDOW", _on_close)
        self._root.mainloop()
        self._cleanup_done.wait(timeout=CLEANUP_TIMEOUT_SECONDS)
        try:
            self._root.destroy()
        except Exception:
            pass
        import os as _os
        _os._exit(0)

    def destroy(self):
        self._root.destroy()

    def _poll_thread_queue(self):
        """主线程轮询：处理从后台线程提交的回调。"""
        try:
            while True:
                ms, func = self._thread_queue.get_nowait()
                if ms <= 0:
                    func()
                else:
                    self._root.after(ms, func)
        except queue.Empty:
            pass
        if not self._app._closing:
            self._root.after(16, self._poll_thread_queue)  # ~60fps 轮询

    def after(self, ms, func):
        """线程安全的 after 调度。可从任意线程调用。"""
        if threading.current_thread() is threading.main_thread():
            # 主线程直接调用
            after_id = [None]
            def _tracked():
                self._after_ids.discard(after_id[0])
                if not self._app._closing:
                    func()
            after_id[0] = self._root.after(ms, _tracked)
            self._after_ids.add(after_id[0])
            return after_id[0]
        else:
            # 非主线程：放入队列，由主线程轮询处理
            self._thread_queue.put((ms, func))
            return None
