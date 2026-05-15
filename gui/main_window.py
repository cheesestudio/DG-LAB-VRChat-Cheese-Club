from gui.fonts import UI_XS, UI_S, UI_S_B, UI_M, UI_M_B, UI_L, UI_L_B, UI_XL, UI_XL_B
import tkinter as tk
import os
import threading
from constants import APP_NAME, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT, CLEANUP_TIMEOUT_SECONDS
from gui.connection_panel import ConnectionPanel
from gui.settings_panel import SettingsPanel
from gui.console_panel import ConsolePanel
from gui.waveform_panel import WaveformPanel
from gui.osc_panel import OSCPanel


class MainWindow:
    def __init__(self, app, theme: dict = None):
        self._app = app
        self._theme = theme or {}
        self._root = tk.Tk()
        self._shutdown_event = threading.Event()
        self._cleanup_done = threading.Event()

        # High DPI scaling
        try:
            import ctypes
            dpi = ctypes.windll.user32.GetDpiForSystem()
            scale = dpi / 96.0
            self._root.tk.call("tk", "scaling", scale)
        except Exception:
            pass

        self._root.title(f"{APP_NAME} - ○ 未连接")
        self._root.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")
        self._root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self._root.configure(bg=self._theme.get("bg_main", "#0a0e1a"))

        # Set app icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_icon.ico")
        if os.path.exists(icon_path):
            self._root.iconbitmap(icon_path)

        self._after_ids = set()
        self._build_ui()

    def _build_ui(self):
        t = self._theme

        # Main container with subtle gradient effect
        main_container = tk.Frame(self._root, bg=t.get("bg_main", "#0a0e1a"))
        main_container.pack(fill="both", expand=True)

        # Header bar - clean and minimal
        header = tk.Frame(main_container, bg=t.get("bg_header", "#1a2332"), height=48)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Left: Brand
        brand_frame = tk.Frame(header, bg=t.get("bg_header", "#1a2332"))
        brand_frame.pack(side="left", padx=16, pady=8)

        tk.Label(
            brand_frame, text="芝士郊狼",
            bg=t.get("bg_header", "#1a2332"),
            fg=t.get("accent_cyan", "#06b6d4"),
            font=(UI_L_B),
        ).pack(side="left")

        tk.Label(
            brand_frame, text="控制中心",
            bg=t.get("bg_header", "#1a2332"),
            fg=t.get("text_secondary", "#94a3b8"),
            font=(UI_M),
        ).pack(side="left", padx=(4, 0))

        # Center: Status
        self._status_frame = tk.Frame(header, bg=t.get("bg_header", "#1a2332"))
        self._status_frame.pack(side="left", expand=True)

        self._connection_status = tk.Label(
            self._status_frame, text="● 未连接",
            bg=t.get("bg_header", "#1a2332"),
            fg=t.get("status_offline", "#6b7280"),
            font=(UI_S),
        )
        self._connection_status.pack(side="left", padx=8)

        # Right: Info
        info_frame = tk.Frame(header, bg=t.get("bg_header", "#1a2332"))
        info_frame.pack(side="right", padx=16, pady=8)

        tk.Label(
            info_frame, text="VRChat + DG-LAB",
            bg=t.get("bg_header", "#1a2332"),
            fg=t.get("text_muted", "#475569"),
            font=(UI_XS),
        ).pack(side="right")

        # Content area - 3 columns
        content = tk.Frame(main_container, bg=t.get("bg_main", "#0a0e1a"))
        content.pack(fill="both", expand=True, padx=8, pady=8)

        # Configure column weights for responsive layout
        content.columnconfigure(0, weight=0, minsize=320)  # Left panel fixed
        content.columnconfigure(1, weight=0, minsize=320)  # Center panel fixed
        content.columnconfigure(2, weight=1)  # Right panel expands

        # Left column: Connection + OSC
        left_panel = tk.Frame(content, bg=t.get("bg_main", "#0a0e1a"))
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.connection_panel = ConnectionPanel(
            left_panel, theme=t,
            on_connect=self._app.on_connect,
            on_disconnect=self._app.on_disconnect,
        )
        self.connection_panel.pack(fill="x", pady=(0, 8))

        self.osc_panel = OSCPanel(
            left_panel, theme=t,
            on_osc_toggle=self._app.on_osc_toggle,
        )
        self.osc_panel.pack(fill="x")

        # Center column: Settings + Mapping
        center_panel = tk.Frame(content, bg=t.get("bg_main", "#0a0e1a"))
        center_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 8))

        self.settings_panel = SettingsPanel(
            center_panel, theme=t,
            on_settings_change=self._app.on_settings_change,
            on_theme_toggle=self._app.on_theme_toggle,
            on_test_shock=self._app.on_test_shock,
        )
        self.settings_panel.pack(fill="x", pady=(0, 8))

        # Right column: Waveform + Console
        right_panel = tk.Frame(content, bg=t.get("bg_main", "#0a0e1a"))
        right_panel.grid(row=0, column=2, sticky="nsew")

        self.waveform_panel = WaveformPanel(right_panel, theme=t)
        self.waveform_panel.pack(fill="x", pady=(0, 8))

        self.console_panel = ConsolePanel(right_panel, theme=t)
        self.console_panel.pack(fill="both", expand=True)

    def update_connection_status(self, paired: bool, server_running: bool = False):
        """Update header connection status indicator."""
        if paired:
            self._connection_status.configure(
                text="● 已配对",
                fg=self._theme.get("status_online", "#10b981"),
            )
            self._root.title(f"{APP_NAME} - ● 已配对")
        elif server_running:
            self._connection_status.configure(
                text="◌ 等待连接",
                fg=self._theme.get("status_warning", "#f59e0b"),
            )
            self._root.title(f"{APP_NAME} - ◌ 等待连接")
        else:
            self._connection_status.configure(
                text="○ 未连接",
                fg=self._theme.get("status_offline", "#6b7280"),
            )
            self._root.title(f"{APP_NAME} - ○ 未连接")

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self._root.configure(bg=t.get("bg_main", "#0a0e1a"))

        # Update header
        for w in self._root.winfo_children():
            if isinstance(w, tk.Frame):
                try:
                    children = w.winfo_children()
                    if children and isinstance(children[0], tk.Frame):
                        # This is the main_container
                        for child in w.winfo_children():
                            if isinstance(child, tk.Frame):
                                child.configure(bg=t.get("bg_header", "#1a2332"))
                                for label in child.winfo_children():
                                    if isinstance(label, tk.Label):
                                        current_fg = str(label.cget("fg"))
                                        if current_fg in ["#06b6d4", "#39d2c0"]:
                                            label.configure(bg=t.get("bg_header", "#1a2332"),
                                                          fg=t.get("accent_cyan", "#06b6d4"))
                                        else:
                                            label.configure(bg=t.get("bg_header", "#1a2332"),
                                                          fg=t.get("text_secondary", "#94a3b8"))
                except (tk.TclError, KeyError):
                    pass

        # Update panels
        self.connection_panel.apply_theme(t)
        self.osc_panel.apply_theme(t)
        self.settings_panel.apply_theme(t)
        self.waveform_panel.apply_theme(t)
        self.console_panel.apply_theme(t)

    def run(self):
        def _on_close():
            if self._app._closing:
                return
            # Signal shutdown started
            self._shutdown_event.set()
            # Stop app first (sets flags, stops timers)
            self._app.on_close()
            # Stop waveform panel tick
            self.waveform_panel.stop()
            # Cancel all pending after() callbacks
            for after_id in list(self._after_ids):
                try:
                    self._root.after_cancel(after_id)
                except Exception:
                    pass
            self._after_ids.clear()
            # Hide window immediately so user perceives instant close
            self._root.withdraw()
            # Run cleanup in background (including WebSocket disconnect — slow, don't block UI)
            def _cleanup():
                try:
                    self._app._do_cleanup()
                except Exception:
                    pass
                finally:
                    self._cleanup_done.set()
            threading.Thread(target=_cleanup, daemon=True).start()
            # Schedule quit — don't wait for daemon cleanup
            self._root.after(100, self._root.quit)
        self._root.protocol("WM_DELETE_WINDOW", _on_close)
        self._root.mainloop()
        # Wait for cleanup to finish
        self._cleanup_done.wait(timeout=CLEANUP_TIMEOUT_SECONDS)
        # Now force destroy
        try:
            self._root.destroy()
        except Exception:
            pass
        # Force-kill process — tkinter may leave dangling Tcl/Tk refs
        import sys as _sys
        _sys.exit(0)

    def destroy(self):
        self._root.destroy()

    def after(self, ms, func):
        after_id = [None]
        def _tracked():
            self._after_ids.discard(after_id[0])
            if not self._app._closing:
                func()
        after_id[0] = self._root.after(ms, _tracked)
        self._after_ids.add(after_id[0])
        return after_id[0]
