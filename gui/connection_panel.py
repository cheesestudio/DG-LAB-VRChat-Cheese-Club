"""连接管理面板 — CustomTkinter 重写。"""
import customtkinter as ctk
import tkinter as tk
import os


class ConnectionPanel(ctk.CTkFrame):
    QR_SIZE = 220

    def __init__(self, master, theme=None, on_connect=None, on_disconnect=None, **kwargs):
        kwargs.pop("bg", None)
        super().__init__(master, fg_color="#1a1a1a", corner_radius=0, **kwargs)
        self._theme = theme or {}
        self._on_connect = on_connect or (lambda: None)
        self._on_disconnect = on_disconnect or (lambda: None)
        self._qr_image = None
        self._qr_path = None
        self._qr_original = None
        self._qr_overlay = None
        self._qr_enlarged = False
        self._qr_full_image = None
        self._build()

    def _build(self):
        # Card container
        card = ctk.CTkFrame(self, fg_color="#242424", corner_radius=8,
                            border_width=1, border_color="#333333")
        card.pack(fill="both", expand=True, padx=4, pady=4)

        # Header
        ctk.CTkLabel(card, text="连接管理", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#e4e4e7").pack(anchor="w", padx=16, pady=(16, 4))

        # Status
        status_frame = ctk.CTkFrame(card, fg_color="transparent")
        status_frame.pack(fill="x", padx=16, pady=(0, 8))
        self._status_label = ctk.CTkLabel(status_frame, text="● 未启动",
                                          font=ctk.CTkFont(size=12),
                                          text_color="#52525b")
        self._status_label.pack(side="left")

        # Port
        port_frame = ctk.CTkFrame(card, fg_color="transparent")
        port_frame.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(port_frame, text="端口", font=ctk.CTkFont(size=12),
                     text_color="#71717a").pack(side="left")
        self._port_var = ctk.StringVar(value="9999")
        self._port_entry = ctk.CTkEntry(port_frame, textvariable=self._port_var,
                                        width=80, height=30, corner_radius=6,
                                        fg_color="#161616", border_color="#333333",
                                        text_color="#e4e4e7")
        self._port_entry.pack(side="left", padx=(10, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))
        self._start_btn = ctk.CTkButton(btn_frame, text="启动服务", width=100, height=32,
                                        corner_radius=6, fg_color="#22c55e",
                                        hover_color="#16a34a", text_color="#ffffff",
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        command=self._on_connect_click)
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = ctk.CTkButton(btn_frame, text="停止", width=70, height=32,
                                       corner_radius=6, fg_color="#ef4444",
                                       hover_color="#dc2626", text_color="#ffffff",
                                       font=ctk.CTkFont(size=12),
                                       command=self._on_disconnect_click, state="disabled")
        self._stop_btn.pack(side="left")

        # QR section
        ctk.CTkLabel(card, text="APP 扫码配对", font=ctk.CTkFont(size=11),
                     text_color="#71717a").pack(padx=16, anchor="w", pady=(0, 6))

        qr_border = ctk.CTkFrame(card, fg_color="#161616", corner_radius=6,
                                 border_width=1, border_color="#333333")
        qr_border.pack(padx=16, pady=(0, 8))

        self._qr_canvas = tk.Canvas(qr_border, width=self.QR_SIZE, height=self.QR_SIZE,
                                    bg="#ffffff", highlightthickness=0)
        self._qr_canvas.pack(padx=4, pady=4)
        self._qr_canvas.create_text(self.QR_SIZE // 2, self.QR_SIZE // 2,
                                    text="启动服务后显示", fill="#71717a",
                                    font=("Segoe UI", 11))

        self._zoom_btn = ctk.CTkButton(card, text="放大二维码", width=100, height=28,
                                       corner_radius=6, fg_color="#d4a054",
                                       hover_color="#b8893e", font=ctk.CTkFont(size=11),
                                       command=self._on_qr_click)
        self._zoom_btn.pack(pady=(0, 8))

        self._id_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=10),
                                      text_color="#52525b")
        self._id_label.pack(padx=16, pady=(0, 12))

    # === Callbacks ===

    def _on_connect_click(self):
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._on_connect()

    def _on_disconnect_click(self):
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._on_disconnect()

    # === Public API ===

    def set_status(self, status: str):
        status_map = {
            "connecting": ("#f59e0b", "◌ 启动中..."),
            "connected": ("#22c55e", "● 服务运行中"),
            "paired": ("#d4a054", "● 已配对"),
            "disconnected": ("#52525b", "● 未启动"),
        }
        color, text = status_map.get(status, ("#ef4444", "● 未知"))
        self._status_label.configure(text=text, text_color=color)
        if status == "disconnected":
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            self._qr_canvas.delete("all")
            self._qr_canvas.create_text(self.QR_SIZE // 2, self.QR_SIZE // 2,
                                        text="启动服务后显示", fill="#71717a",
                                        font=("Segoe UI", 11))
            self._id_label.configure(text="")
        elif status in ("connected", "paired"):
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")

    def set_qr(self, url_or_image, client_id: str = ""):
        if hasattr(url_or_image, "size"):
            from PIL import ImageTk
            self._qr_original = url_or_image
            img = url_or_image.resize((self.QR_SIZE, self.QR_SIZE))
            self._qr_image = ImageTk.PhotoImage(img)
            self._qr_canvas.delete("all")
            self._qr_canvas.create_image(self.QR_SIZE // 2, self.QR_SIZE // 2,
                                         image=self._qr_image, anchor="center")
            try:
                self._qr_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dgcode.png")
                url_or_image.save(self._qr_path)
            except Exception:
                pass
        elif isinstance(url_or_image, str) and url_or_image:
            try:
                import qrcode
                from PIL import ImageTk
                qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                                   box_size=10, border=4)
                qr.add_data(url_or_image)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                self._qr_original = img
                self._qr_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dgcode.png")
                img.save(self._qr_path)
                display_img = img.resize((self.QR_SIZE, self.QR_SIZE))
                self._qr_image = ImageTk.PhotoImage(display_img)
                self._qr_canvas.delete("all")
                self._qr_canvas.create_image(self.QR_SIZE // 2, self.QR_SIZE // 2,
                                             image=self._qr_image, anchor="center")
            except Exception as e:
                self._qr_canvas.delete("all")
                self._qr_canvas.create_text(self.QR_SIZE // 2, self.QR_SIZE // 2,
                                            text=str(e)[:40], fill="#ef4444",
                                            font=("Segoe UI", 10), width=self.QR_SIZE - 20)
        if client_id:
            self._id_label.configure(text=f"ID: {client_id[:20]}")

    def _on_qr_click(self):
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
        w, h = root.winfo_width(), root.winfo_height()
        self._qr_overlay = tk.Frame(root, bg="#000000")
        self._qr_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._qr_overlay.bind("<Button-1>", lambda e: self._shrink_qr())
        size = min(w, h) - 80
        from PIL import ImageTk
        img = self._qr_original
        if img is None and self._qr_path and os.path.exists(self._qr_path):
            from PIL import Image
            img = Image.open(self._qr_path)
        if img:
            display = img.resize((size, size))
            self._qr_full_image = ImageTk.PhotoImage(display)
        else:
            self._qr_full_image = self._qr_image
        canvas = tk.Canvas(self._qr_overlay, width=size, height=size,
                           bg="#000000", highlightthickness=0, cursor="hand2")
        canvas.place(relx=0.5, rely=0.5, anchor="center")
        canvas.create_image(size // 2, size // 2, image=self._qr_full_image, anchor="center")
        canvas.bind("<Button-1>", lambda e: self._shrink_qr())
        tk.Label(self._qr_overlay, text="点击任意位置关闭", bg="#000000",
                 fg="#71717a", font=("Segoe UI", 13)).place(relx=0.5, rely=0.92, anchor="center")

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

    def apply_theme(self, theme: dict):
        pass

    # Legacy compat: app.py calls _draw_dot on osc_panel, not here, but just in case
    def _draw_dot(self, color: str):
        pass
