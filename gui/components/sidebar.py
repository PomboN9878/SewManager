import customtkinter as ctk

# ── Paleta ───────────────────────────────────────────────────────────────────
SIDEBAR_BG    = "#0F1117"
ITEM_HOVER    = "#1A1D2E"
ACTIVE_BG     = "#1E2235"
ACTIVE_ACCENT = "#6C63FF"
TEXT_DEFAULT  = "#6B7280"
TEXT_ACTIVE   = "#F9FAFB"
DIVIDER       = "#1F2130"

MENU_ITEMS = [
    ("dashboard",  "Dashboard"),
    ("clientes",   "Clientes"),
    ("estoque",    "Estoque"),
    ("nova_venda", "Nova Venda"),
    ("vendas",     "Vendas"),
    ("pagamentos", "Pagamentos"),
]

class Sidebar(ctk.CTkFrame):

    def __init__(self, master, on_select):
        super().__init__(master, width=240, corner_radius=0)
        self.on_select  = on_select
        self.active_key = None
        self.buttons    = {}

        self.configure(fg_color=SIDEBAR_BG)
        self.grid_columnconfigure(0, weight=1)
        self.grid_propagate(False)

        row = 0

        # ── Logo ─────────────────────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=(32, 4))
        row += 1

        dot = ctk.CTkFrame(logo_frame, width=8, height=8,
                           fg_color=ACTIVE_ACCENT, corner_radius=4)
        dot.pack(side="left", padx=(0, 8), pady=6)

        ctk.CTkLabel(
            logo_frame, text="Sew",
            font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
            text_color="#F9FAFB",
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame, text="Manager",
            font=ctk.CTkFont(family="Georgia", size=20),
            text_color=ACTIVE_ACCENT,
        ).pack(side="left", padx=(2, 0))

        # Tagline
        ctk.CTkLabel(
            self, text="Sistema de Gestão",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_DEFAULT,
        ).grid(row=row, column=0, sticky="w", padx=36, pady=(0, 24))
        row += 1

        # Divisor superior
        ctk.CTkFrame(self, height=1, fg_color=DIVIDER).grid(
            row=row, column=0, sticky="ew", padx=16, pady=(0, 12)
        )
        row += 1

        # ── Botões de navegação ───────────────────────────────────────────────
        for key, label in MENU_ITEMS:
            self._make_button(row=row, key=key, label=label)
            row += 1

    # ── Botão individual ──────────────────────────────────────────────────────
    def _make_button(self, row, key, label):
        outer = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        outer.grid(row=row, column=0, sticky="ew", padx=12, pady=1)
        outer.grid_columnconfigure(0, weight=1)

        pill = ctk.CTkFrame(outer, fg_color="transparent", corner_radius=10)
        pill.grid(row=0, column=0, sticky="ew")
        pill.grid_columnconfigure(1, weight=1)

        # Barra accent lateral
        accent_bar = ctk.CTkFrame(
            pill, width=3, height=20,
            fg_color="transparent", corner_radius=2,
        )
        accent_bar.grid(row=0, column=0, padx=(8, 0), pady=8, sticky="ns")

        btn = ctk.CTkButton(
            pill,
            text=label,
            anchor="w",
            fg_color="transparent",
            hover_color=ITEM_HOVER,
            text_color=TEXT_DEFAULT,
            height=36,
            corner_radius=10,
            font=ctk.CTkFont(size=13),
            command=lambda k=key: self._on_click(k),
        )
        btn.grid(row=0, column=1, sticky="ew", padx=(4, 4), pady=2)

        self.buttons[key] = (btn, pill, accent_bar)

    # ── Interação ─────────────────────────────────────────────────────────────
    def _on_click(self, key):
        self.set_active(key)
        self.on_select(key)

    def set_active(self, key):
        if self.active_key and self.active_key in self.buttons:
            btn, pill, accent_bar = self.buttons[self.active_key]
            btn.configure(fg_color="transparent", text_color=TEXT_DEFAULT,
                          font=ctk.CTkFont(size=13))
            pill.configure(fg_color="transparent")
            accent_bar.configure(fg_color="transparent")

        self.active_key = key

        if key in self.buttons:
            btn, pill, accent_bar = self.buttons[key]
            btn.configure(fg_color="transparent", text_color=TEXT_ACTIVE,
                          font=ctk.CTkFont(size=13, weight="bold"))
            pill.configure(fg_color=ACTIVE_BG)
            accent_bar.configure(fg_color=ACTIVE_ACCENT)