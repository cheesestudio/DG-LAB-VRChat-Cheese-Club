import tkinter as tk
import os
from gui.connection_panel import ConnectionPanel
from gui.settings_panel import SettingsPanel
from gui.mapping_panel import MappingPanel
from gui.console_panel import ConsolePanel
from gui.waveform_panel import WaveformPanel
from gui.osc_panel import OSCPanel


class MainWindow:
    def __init__(self, app, theme: dict = None):
        self._app = app
        self._theme = theme or {}
        self._root = tk.Tk()
        self._root.title("芝士郊狼控制软件 - 芝士郊狼台球后援会")
        self._root.geometry("1280x760")
        self._root.minsize(1100, 660)
        self._root.configure(bg=self._theme.get("bg_main", "#0d1117"))

        # Set app icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_icon.ico")
        if os.path.exists(icon_path):
            self._root.iconbitmap(icon_path)

        self._build_ui()

    def _build_ui(self):
        t = self._theme

        # Top banner with QQ group
        banner = tk.Frame(self._root, bg=t.get("bg_header", "#1c2333"), height=28)
        banner.pack(fill="x")
        banner.pack_propagate(False)

        tk.Label(
            banner, text="[ 芝士郊狼台球后援会 ]",
            bg=t.get("bg_header", "#1c2333"),
            fg=t.get("accent_cyan", "#39d2c0"),
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left", padx=12, pady=4)

        tk.Label(
            banner, text="QQ群: 757992539",
            bg=t.get("bg_header", "#1c2333"),
            fg=t.get("text_dim", "#6e7681"),
            font=("Consolas", 9),
        ).pack(side="right", padx=12, pady=4)

        # Center info in banner
        self._banner_center = tk.Label(
            banner, text="VRChat + DG-LAB",
            bg=t.get("bg_header", "#1c2333"),
            fg=t.get("text_muted", "#6e7681"),
            font=("Consolas", 9),
        )
        self._banner_center.pack(side="left", expand=True)

        # Main content - 3 columns
        main = tk.Frame(self._root, bg=t.get("bg_main", "#0d1117"))
        main.pack(fill="both", expand=True, padx=6, pady=(4, 6))

        # Column 1: Connection + OSC
        col1 = tk.Frame(main, bg=t.get("bg_main", "#0d1117"), width=280)
        col1.pack(side="left", fill="y", padx=(0, 4))
        col1.pack_propagate(False)

        # Column 2: Shock settings + mapping
        col2 = tk.Frame(main, bg=t.get("bg_main", "#0d1117"), width=280)
        col2.pack(side="left", fill="y", padx=(0, 4))
        col2.pack_propagate(False)

        # Column 3: Waveform + console
        col3 = tk.Frame(main, bg=t.get("bg_main", "#0d1117"))
        col3.pack(side="right", fill="both", expand=True)

        # Col1: Connection + OSC
        self.connection_panel = ConnectionPanel(
            col1, theme=t,
            on_connect=self._app.on_connect,
            on_disconnect=self._app.on_disconnect,
        )
        self.connection_panel.pack(fill="x", pady=(0, 4))

        self.osc_panel = OSCPanel(
            col1, theme=t,
            on_osc_toggle=self._app.on_osc_toggle,
        )
        self.osc_panel.pack(fill="x", pady=(0, 4))

        # Col2: Settings + Mapping
        self.settings_panel = SettingsPanel(
            col2, theme=t,
            on_settings_change=self._app.on_settings_change,
            on_theme_toggle=self._app.on_theme_toggle,
            on_test_shock=self._app.on_test_shock,
        )
        self.settings_panel.pack(fill="x", pady=(0, 4))

        self.mapping_panel = MappingPanel(
            col2, theme=t,
            on_mapping_change=self._app.on_mapping_change,
        )
        self.mapping_panel.pack(fill="x")

        # Col3: Waveform + Console
        self.waveform_panel = WaveformPanel(col3, theme=t)
        self.waveform_panel.pack(fill="x", pady=(0, 4))

        self.console_panel = ConsolePanel(col3, theme=t)
        self.console_panel.pack(fill="both", expand=True)

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self._root.configure(bg=t.get("bg_main", "#0d1117"))
        for w in self._root.winfo_children():
            try:
                if isinstance(w, tk.Frame):
                    # Check if it's the banner
                    children = w.winfo_children()
                    if children and isinstance(children[0], tk.Label):
                        first_text = str(children[0].cget("text"))
                        if "芝士郊狼台球后援会" in first_text:
                            w.configure(bg=t.get("bg_header", "#1c2333"))
                            for c in children:
                                if "QQ" in str(c.cget("text")):
                                    c.configure(bg=t.get("bg_header", "#1c2333"),
                                                fg=t.get("text_dim", "#6e7681"))
                                else:
                                    c.configure(bg=t.get("bg_header", "#1c2333"),
                                                fg=t.get("accent_cyan", "#39d2c0"))
                            continue
                    w.configure(bg=t.get("bg_main", "#0d1117"))
            except (tk.TclError, KeyError):
                pass
        self.connection_panel.apply_theme(t)
        self.osc_panel.apply_theme(t)
        self.settings_panel.apply_theme(t)
        self.mapping_panel.apply_theme(t)
        self.waveform_panel.apply_theme(t)
        self.console_panel.apply_theme(t)

    def run(self):
        def _on_close():
            self._app.on_close()
            import os
            os._exit(0)
        self._root.protocol("WM_DELETE_WINDOW", _on_close)
        self._root.mainloop()

    def destroy(self):
        self._root.destroy()

    def after(self, ms, func):
        self._root.after(ms, func)
