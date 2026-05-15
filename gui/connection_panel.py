from gui.fonts import UI_XS, UI_S, UI_S_B, UI_M, UI_M_B, UI_L, MONO_S
import tkinter as tk
import os


class ConnectionPanel(tk.Frame):
    QR_SIZE = 280  # pixels - smaller for better layout

    def __init__(self, master, theme: dict = None, on_connect=None, on_disconnect=None, **kwargs):
        self._theme = theme or {}
        super().__init__(master, bg=self._theme.get("bg_panel", "#111827"), **kwargs)
        self._on_connect = on_connect or (lambda: None)
        self._on_disconnect = on_disconnect or (lambda: None)
        self._qr_image = None
        self._qr_path = None
        self._build()

    def _build(self):
        t = self._theme

        # Panel container with subtle border
        container = tk.Frame(self, bg=t.get("bg_card", "#151d2b"),
                            highlightbackground=t.get("border_color", "#1e293b"),
                            highlightthickness=1)
        container.pack(fill="x", padx=4, pady=4)

        # Header
        header = tk.Frame(container, bg=t.get("bg_card", "#151d2b"))
        header.pack(fill="x", padx=12, pady=(12, 8))

        tk.Label(
            header, text="连接状态",
            bg=t.get("bg_card", "#151d2b"),
            fg=t.get("text_primary", "#f1f5f9"),
            font=(UI_M_B), anchor="w",
        ).pack(side="left")

        # Status indicator
        status_frame = tk.Frame(container, bg=t.get("bg_card", "#151d2b"))
        status_frame.pack(fill="x", padx=12, pady=(0, 8))

        self._status_dot = tk.Canvas(status_frame, width=10, height=10,
                                     bg=t.get("bg_card", "#151d2b"), highlightthickness=0)
        self._status_dot.pack(side="left", padx=(0, 8))
        self._draw_dot(t.get("status_offline", "#6b7280"))

        self._status_label = tk.Label(
            status_frame, text="未启动",
            bg=t.get("bg_card", "#151d2b"),
            fg=t.get("text_secondary", "#94a3b8"),
            font=(UI_S),
        )
        self._status_label.pack(side="left")

        # Port input
        port_frame = tk.Frame(container, bg=t.get("bg_card", "#151d2b"))
        port_frame.pack(fill="x", padx=12, pady=(0, 8))

        tk.Label(
            port_frame, text="端口",
            bg=t.get("bg_card", "#151d2b"),
            fg=t.get("text_dim", "#64748b"),
            font=(UI_S),
        ).pack(side="left")

        self._port_var = tk.StringVar(value="9999")
        self._port_entry = tk.Entry(
            port_frame, textvariable=self._port_var,
            bg=t.get("bg_input", "#0f1520"),
            fg=t.get("text_primary", "#f1f5f9"),
            insertbackground=t.get("text_primary", "#f1f5f9"),
            font=(MONO_S), relief="flat", width=8,
            highlightbackground=t.get("border_color", "#1e293b"),
            highlightthickness=1,
        )
        self._port_entry.pack(side="left", padx=(8, 0))

        # Buttons
        btn_frame = tk.Frame(container, bg=t.get("bg_card", "#151d2b"))
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))

        self._start_btn = tk.Button(
            btn_frame, text="启动服务",
            bg=t.get("bg_button_success", "#059669"),
            fg="#ffffff",
            activebackground=t.get("bg_button_success_hover", "#10b981"),
            activeforeground="#ffffff",
            font=(UI_S_B), relief="flat",
            cursor="hand2", command=self._on_connect_click, width=10,
        )
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = tk.Button(
            btn_frame, text="停止",
            bg=t.get("bg_button_danger", "#dc2626"),
            fg="#ffffff",
            activebackground=t.get("bg_button_danger_hover", "#ef4444"),
            activeforeground="#ffffff",
            font=(UI_S), relief="flat",
            cursor="hand2", command=self._on_disconnect_click, width=8,
            state="disabled",
        )
        self._stop_btn.pack(side="left")

        # QR code section
        qr_section = tk.Frame(container, bg=t.get("bg_card", "#151d2b"))
        qr_section.pack(fill="x", padx=12, pady=(0, 12))

        tk.Label(
            qr_section, text="APP扫码配对",
            bg=t.get("bg_card", "#151d2b"),
            fg=t.get("text_dim", "#64748b"),
            font=(UI_XS),
        ).pack(pady=(0, 8))

        # QR code container with border
        qr_container = tk.Frame(qr_section, bg=t.get("bg_input", "#0f1520"),
                               highlightbackground=t.get("border_color", "#1e293b"),
                               highlightthickness=1)
        qr_container.pack()

        self._qr_canvas = tk.Canvas(
            qr_container,
            width=self.QR_SIZE, height=self.QR_SIZE,
            bg=t.get("qr_background", "#ffffff"),
            highlightthickness=0,
        )
        self._qr_canvas.pack(padx=2, pady=2)
        self._qr_canvas.create_text(
            self.QR_SIZE // 2, self.QR_SIZE // 2,
            text="启动服务后显示",
            fill=t.get("text_muted", "#475569"),
            font=(UI_S), tags="placeholder",
        )

        # Zoom button
        self._zoom_btn = tk.Button(
            qr_section, text="放大二维码",
            bg=t.get("bg_button", "#2563eb"),
            fg="#ffffff",
            activebackground=t.get("bg_button_hover", "#3b82f6"),
            font=(UI_XS), relief="flat", cursor="hand2",
            command=self._on_qr_click,
        )
        self._zoom_btn.pack(pady=(8, 0))

        # Full-screen QR overlay (hidden by default)
        self._qr_overlay = None
        self._qr_enlarged = False
        self._qr_full_image = None

        # Client ID
        self._id_label = tk.Label(
            container, text="",
            bg=t.get("bg_card", "#151d2b"),
            fg=t.get("text_muted", "#475569"),
            font=(MONO_S), wraplength=260,
        )
        self._id_label.pack(padx=12, pady=(0, 8))

    def _draw_dot(self, color: str):
        self._status_dot.delete("all")
        self._status_dot.create_oval(2, 2, 8, 8, fill=color, outline=color)

    def _on_connect_click(self):
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._on_connect()

    def _on_disconnect_click(self):
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._on_disconnect()

    def apply_theme(self, theme: dict):
        self._theme = theme
        t = theme
        self.configure(bg=t.get("bg_panel", "#111827"))
        for w in self._get_all_widgets():
            try:
                bg = t.get("bg_card", "#151d2b")
                fg = t.get("text_primary", "#f1f5f9")
                if isinstance(w, tk.Canvas):
                    w.configure(bg=t.get("bg_input", "#0f1520"))
                elif isinstance(w, tk.Button):
                    txt = str(w.cget("text"))
                    if txt == "停止":
                        w.configure(bg=t.get("bg_button_danger", "#dc2626"), fg="#ffffff",
                                    activebackground=t.get("bg_button_danger_hover", "#ef4444"))
                    elif txt == "放大二维码":
                        w.configure(bg=t.get("bg_button", "#2563eb"), fg="#ffffff",
                                    activebackground=t.get("bg_button_hover", "#3b82f6"))
                    else:
                        w.configure(bg=t.get("bg_button_success", "#059669"), fg="#ffffff",
                                    activebackground=t.get("bg_button_success_hover", "#10b981"))
                elif isinstance(w, tk.Entry):
                    w.configure(bg=t.get("bg_input", "#0f1520"), fg=fg, insertbackground=fg,
                                highlightbackground=t.get("border_color", "#1e293b"))
                elif isinstance(w, tk.Frame):
                    w.configure(bg=bg)
                elif isinstance(w, tk.Label):
                    current_fg = str(w.cget("fg"))
                    if current_fg in ["#f1f5f9", "#e6edf3"]:
                        w.configure(bg=bg, fg=fg)
                    else:
                        w.configure(bg=bg, fg=t.get("text_dim", "#64748b"))
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

    def set_status(self, status: str):
        t = self._theme
        status_map = {
            "connecting": (t.get("status_warning", "#f59e0b"), "启动中..."),
            "connected": (t.get("status_online", "#10b981"), "服务运行中"),
            "paired": (t.get("accent_blue", "#3b82f6"), "已配对"),
            "disconnected": (t.get("status_offline", "#6b7280"), "未启动"),
        }
        color, text = status_map.get(status, (t.get("status_error", "#ef4444"), "未知"))
        self._draw_dot(color)
        self._status_label.configure(text=text)

        if status == "disconnected":
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._qr_canvas.delete("all")
            self._qr_canvas.create_text(
                self.QR_SIZE // 2, self.QR_SIZE // 2,
                text="启动服务后显示",
                fill=t.get("text_muted", "#475569"),
                font=(UI_S), tags="placeholder",
            )
            self._id_label.configure(text="")
        elif status in ("connected", "paired"):
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")

    def set_qr(self, url_or_image, client_id: str = ""):
        if hasattr(url_or_image, "size"):
            from PIL import ImageTk
            if hasattr(self, '_qr_image') and self._qr_image:
                del self._qr_image
            self._qr_original = url_or_image
            img = url_or_image.resize((self.QR_SIZE, self.QR_SIZE))
            self._qr_image = ImageTk.PhotoImage(img)
            self._qr_canvas.delete("all")
            self._qr_canvas.create_image(
                self.QR_SIZE // 2, self.QR_SIZE // 2, image=self._qr_image, anchor="center",
            )
            try:
                self._qr_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dgcode.png"
                )
                url_or_image.save(self._qr_path)
            except Exception:
                pass
        elif isinstance(url_or_image, str) and url_or_image:
            try:
                import qrcode
                from PIL import ImageTk
                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10, border=4,
                )
                qr.add_data(url_or_image)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                self._qr_original = img

                # Save to PNG file
                self._qr_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dgcode.png"
                )
                img.save(self._qr_path)

                # Display on Canvas at fixed pixel size
                display_img = img.resize((self.QR_SIZE, self.QR_SIZE))
                if hasattr(self, '_qr_image') and self._qr_image:
                    del self._qr_image
                self._qr_image = ImageTk.PhotoImage(display_img)
                self._qr_canvas.delete("all")
                self._qr_canvas.create_image(
                    self.QR_SIZE // 2, self.QR_SIZE // 2, image=self._qr_image, anchor="center",
                )
            except Exception as e:
                self._qr_canvas.delete("all")
                self._qr_canvas.create_text(
                    self.QR_SIZE // 2, self.QR_SIZE // 2,
                    text=str(e)[:50], fill=self._theme.get("status_error", "#ef4444"),
                    font=(MONO_S), width=self.QR_SIZE - 20,
                )
        if client_id:
            self._id_label.configure(text=f"ID: {client_id[:20]}")

    def _on_qr_click(self, event=None):
        if not self._qr_image:
            return
        if self._qr_enlarged:
            self._shrink_qr()
        else:
            self._enlarge_qr()

    def _enlarge_qr(self):
        if self._qr_enlarged or not self._qr_image:
            return
        self._qr_enlarged = True
        root = self.winfo_toplevel()
        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()

        self._qr_overlay = tk.Frame(root, bg="#000000")
        self._qr_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._qr_overlay.bind("<Button-1>", lambda e: self._shrink_qr())

        # Use saved original image
        size = min(w, h) - 80
        from PIL import ImageTk
        img = getattr(self, '_qr_original', None)
        if img is None and self._qr_path and os.path.exists(self._qr_path):
            from PIL import Image
            img = Image.open(self._qr_path)
        if img:
            display = img.resize((size, size))
            if hasattr(self, '_qr_full_image') and self._qr_full_image:
                del self._qr_full_image
            self._qr_full_image = ImageTk.PhotoImage(display)
        else:
            self._qr_full_image = self._qr_image

        canvas = tk.Canvas(
            self._qr_overlay, width=size, height=size,
            bg="#000000", highlightthickness=0, cursor="hand2",
        )
        canvas.place(relx=0.5, rely=0.5, anchor="center")
        canvas.create_image(size // 2, size // 2, image=self._qr_full_image, anchor="center")
        canvas.bind("<Button-1>", lambda e: self._shrink_qr())

        hint = tk.Label(
            self._qr_overlay, text="点击任意位置关闭",
            bg="#000000", fg="#64748b",
            font=(UI_L),
        )
        hint.place(relx=0.5, rely=0.9, anchor="center")

    def _shrink_qr(self):
        if not self._qr_enlarged:
            return
        self._qr_enlarged = False
        if self._qr_overlay:
            self._qr_overlay.destroy()
            self._qr_overlay = None
        self._qr_full_image = None

    def get_port(self) -> int:
        try:
            return int(self._port_var.get().strip())
        except ValueError:
            return 9999

    def set_port(self, port: int):
        self._port_var.set(str(port))
