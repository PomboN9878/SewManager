"""
gui/components/clientes_modals.py
Modals do módulo Clientes: ClienteFormModal, HistoricoModal.
"""

import customtkinter as ctk
from CTkTable import CTkTable
from .base_modal import (
    BaseModal, fmt_brl, make_label,
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER,
    HEADER_BG, ROW_ALT, ROW_HOVER,
)

STATUS_COLORS = {
    "QUITADA":   ("#D1FAE5", "#059669"),
    "ABERTA":    ("#FEF3C7", "#D97706"),
    "CANCELADA": ("#FEE2E2", "#DC2626"),
}


# ── Modal: Novo / Editar cliente ──────────────────────────────────────────────

class ClienteFormModal(BaseModal):
    """Formulário para criar ou editar um Cliente."""

    FIELDS = [
        ("Nome *",      "nome"),
        ("Documento",   "documento"),
        ("Telefone",    "telefone"),
        ("Observações", "obs"),
    ]

    def __init__(self, master, on_save, cliente: dict | None = None):
        super().__init__(
            master,
            title="Editar Cliente" if cliente else "Novo Cliente",
            width=460, height=380,
        )
        self.on_save = on_save
        self.cliente = cliente or {}
        self._build()

    def _build(self):
        b = self.body
        self.entries: dict[str, ctk.CTkEntry] = {}

        prefill = {
            "nome":      self.cliente.get("nome", ""),
            "documento": self.cliente.get("documento", ""),
            "telefone":  self.cliente.get("telefone", ""),
            "obs":       self.cliente.get("observacoes", ""),
        }

        for i, (lbl_text, key) in enumerate(self.FIELDS):
            make_label(b, lbl_text, font_size=11, color=TEXT_SUB, anchor="w",
                       row=i * 2, column=0, sticky="w",
                       pady=(8 if i else 0, 2))
            e = ctk.CTkEntry(
                b, height=36, corner_radius=8,
                fg_color=CARD_BG, border_color=BORDER, border_width=1,
                text_color=TEXT_MAIN, font=ctk.CTkFont(size=13),
            )
            e.grid(row=i * 2 + 1, column=0, sticky="ew", pady=(0, 2))
            if prefill.get(key):
                e.insert(0, prefill[key])
            self.entries[key] = e

        btn_row = ctk.CTkFrame(b, fg_color="transparent")
        btn_row.grid(row=len(self.FIELDS) * 2 + 1, column=0,
                     sticky="e", pady=(16, 8))
        ctk.CTkButton(
            btn_row, text="Cancelar", width=100, height=36,
            fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
            corner_radius=8, font=ctk.CTkFont(size=13),
            command=self.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Salvar", width=100, height=36,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFF",
            corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._submit,
        ).pack(side="left")

    def _submit(self):
        data = {k: e.get().strip() for k, e in self.entries.items()}
        if not data["nome"]:
            self.entries["nome"].configure(border_color="#E05C5C")
            return
        self.entries["nome"].configure(border_color=BORDER)
        self.on_save(data)
        self.destroy()


# ── Modal: Histórico do cliente ───────────────────────────────────────────────

class HistoricoModal(BaseModal):
    """Exibe resumo financeiro e lista de vendas de um cliente."""

    HIST_HEADERS = ["Data", "Máquina", "Valor Total", "Status"]
    STATUS_COL   = 3   # índice da coluna "Status" na tabela

    def __init__(self, master, cliente_nome: str, vendas: list):
        super().__init__(
            master,
            title=f"Histórico — {cliente_nome}",
            width=700, height=520,
        )
        self.vendas = vendas
        self._build()

    def _build(self):
        b = self.body
        b.grid_columnconfigure(0, weight=1)

        # ── Resumo financeiro ─────────────────────────────────────────────
        total  = sum(v.get("valor_total", 0) for v in self.vendas)
        pago   = sum(v.get("total_pago",  0) for v in self.vendas)
        aberto = total - pago

        resumo = ctk.CTkFrame(b, fg_color=CARD_BG, corner_radius=10,
                              border_width=1, border_color=BORDER)
        resumo.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        resumo.grid_columnconfigure((0, 1, 2), weight=1)

        for col, (lbl, val, color) in enumerate([
            ("Total comprado", fmt_brl(total),  TEXT_MAIN),
            ("Total pago",     fmt_brl(pago),   "#059669"),
            ("Em aberto",      fmt_brl(aberto),
             "#D97706" if aberto > 0 else TEXT_SUB),
        ]):
            ctk.CTkLabel(
                resumo, text=val,
                font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                text_color=color,
            ).grid(row=0, column=col, padx=20, pady=(14, 2))
            ctk.CTkLabel(
                resumo, text=lbl,
                font=ctk.CTkFont(size=11), text_color=TEXT_SUB,
            ).grid(row=1, column=col, padx=20, pady=(0, 14))

        # ── Tabela de vendas com CTkTable ─────────────────────────────────
        card = ctk.CTkFrame(b, fg_color=CARD_BG, corner_radius=10,
                            border_width=1, border_color=BORDER)
        card.grid(row=1, column=0, sticky="nsew", pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(card, fg_color=CARD_BG,
                                        scrollbar_button_color=BORDER,
                                        corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        scroll.grid_columnconfigure(0, weight=1)

        if not self.vendas:
            make_label(scroll, "Nenhuma venda encontrada.",
                       font_size=13, color=TEXT_SUB, anchor="center",
                       row=0, column=0, pady=32)
            return

        values = [self.HIST_HEADERS] + [
            [
                v.get("data", "—"),
                v.get("maquina", "—"),
                fmt_brl(v.get("valor_total")),
                v.get("status", "—"),
            ]
            for v in self.vendas
        ]

        table = CTkTable(
            scroll,
            values=values,
            header_color=HEADER_BG,
            colors=[CARD_BG, ROW_ALT],
            text_color=TEXT_MAIN,
            hover=True,
            hover_color=ROW_HOVER,
            height=40,
            font=ctk.CTkFont(size=13),
            padx=1,
            pady=1,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            anchor="w",
        )
        table.pack(fill="both", expand=True, padx=4, pady=4)

        # Estiliza header
        table.edit_row(
            0,
            text_color=TEXT_SUB,
            fg_color=HEADER_BG,
            hover_color=HEADER_BG,
            hover=False,
            font=ctk.CTkFont(size=11, weight="bold"),
            height=36,
        )

        # Colore coluna de status
        for i, v in enumerate(self.vendas):
            _, color = STATUS_COLORS.get(v.get("status", ""), ("#F3F4F6", TEXT_SUB))
            table.frame[i + 1, self.STATUS_COL].configure(
                text_color=color,
                font=ctk.CTkFont(size=12, weight="bold"),
            )