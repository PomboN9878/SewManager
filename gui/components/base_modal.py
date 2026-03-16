"""
gui/components/base_modal.py
Base compartilhada para todos os modals da aplicação.
"""

import customtkinter as ctk

# ── Paleta (importada pelos filhos via: from .base_modal import *) ─────────────
BG           = "#F4F5F8"
CARD_BG      = "#FFFFFF"
ACCENT       = "#6C63FF"
ACCENT_HOVER = "#574FD4"
TEXT_MAIN    = "#1C1F2E"
TEXT_SUB     = "#8B90A8"
BORDER       = "#ECEEF4"
HEADER_BG    = "#F0F1F8"
ROW_ALT      = "#FAFBFD"
ROW_HOVER    = "#EEEEFF"


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_brl(valor) -> str:
    """Formata float → R$ 1.500,00"""
    if valor is None:
        return "—"
    try:
        s = f"{float(valor):,.2f}"
        return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "—"


def divider(parent, row: int, padx: int = 0):
    """Linha horizontal separadora."""
    ctk.CTkFrame(parent, height=1, fg_color=BORDER).grid(
        row=row, column=0, columnspan=99, sticky="ew", padx=padx,
    )


def make_label(parent, text, font_size=13, color=TEXT_MAIN,
               weight="normal", anchor="w", **grid_kw):
    """Cria CTkLabel e opcionalmente já posiciona com .grid()."""
    lbl = ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(size=font_size, weight=weight),
        text_color=color, anchor=anchor,
    )
    if grid_kw:
        lbl.grid(**grid_kw)
    return lbl


# ── Modal base ────────────────────────────────────────────────────────────────

class BaseModal(ctk.CTkToplevel):
    """
    Janela modal com:
      - header fixo com título
      - body scrollável
      - centralização automática sobre o pai
    """

    def __init__(self, master, title: str, width: int = 480, height: int = 420):
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.minsize(width, height)
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=BG)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.after(10, self._center)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=56)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_propagate(False)
        ctk.CTkLabel(
            hdr, text=title,
            font=ctk.CTkFont(family="Georgia", size=16, weight="bold"),
            text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", padx=24, pady=16)
        divider(hdr, row=1)

        # Body scrollável — subclasses usam self.body
        self.body = ctk.CTkScrollableFrame(
            self, fg_color=BG, scrollbar_button_color=BORDER,
        )
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

    def _center(self):
        """Centraliza a janela sobre o widget pai."""
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + m.winfo_width()  // 2 - self.winfo_width()  // 2
        y = m.winfo_rooty() + m.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")

    def _footer(self, parent, on_cancel, on_save, row: int):
        """Rodapé padrão com botões Cancelar / Salvar."""
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=0, columnspan=2, sticky="e", pady=(20, 8))
        ctk.CTkButton(
            f, text="Cancelar", width=100, height=36,
            fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
            corner_radius=8, font=ctk.CTkFont(size=13),
            command=on_cancel,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            f, text="Salvar", width=100, height=36,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFF",
            corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            command=on_save,
        ).pack(side="left")

    def _entry_field(self, parent, label: str, key: str,
                     grid_row: int, grid_col: int,
                     entries: dict, initial: str = ""):
        """
        Cria label + CTkEntry em grid 2-colunas e registra em `entries[key]`.
        grid_row / grid_col referem-se à grade lógica de campos (0-based).
        Internamente ocupa duas linhas reais (label na par, entry na ímpar).
        """
        padx = (0, 6) if grid_col == 0 else (6, 0)
        make_label(parent, label, font_size=11, color=TEXT_SUB, anchor="w",
                   row=grid_row * 2, column=grid_col, sticky="w",
                   padx=padx, pady=(10, 2))
        e = ctk.CTkEntry(
            parent, height=36, corner_radius=8,
            fg_color=CARD_BG, border_color=BORDER, border_width=1,
            text_color=TEXT_MAIN, font=ctk.CTkFont(size=13),
        )
        e.grid(row=grid_row * 2 + 1, column=grid_col,
               sticky="ew", padx=padx, pady=(0, 4))
        if initial:
            e.insert(0, initial)
        entries[key] = e