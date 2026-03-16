"""
gui/views/pagamentos_view.py

Visão financeira de pagamentos/parcelas.

ARQUITETURA:
    PagamentosView  →  PagamentoController  →  pagamento_service
    (sem imports de services aqui)

MELHORIAS APLICADAS:
- Acoplamento removido: View usa PagamentoController exclusivamente
- atualizar_status_atrasados() chamado automaticamente ao abrir a tela
- Feedback de crédito gerado exibido ao usuário
- _status_efetivo() removido: status já vem correto do banco (ATRASADO persistido)
- Lógica de negócio removida da View (cálculo de métricas simplificado)
"""
from __future__ import annotations

from datetime import datetime, timedelta

import customtkinter as ctk
from CTkTable import CTkTable

from gui.controllers.pagamento_controller import PagamentoController
from gui.components.registrar_pagamento_modal import RegistrarPagamentoModal
from gui.components.base_modal import (
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER,
    HEADER_BG, ROW_ALT, ROW_HOVER,
    fmt_brl as _fmt_brl,
    make_label as _label,
)

# ── Cores semânticas ──────────────────────────────────────────────────────────
_VERDE    = "#059669"
_AMARELO  = "#D97706"
_VERMELHO = "#DC2626"
_AZUL     = "#4F6AF0"

STATUS_CFG: dict[str, tuple[str, str]] = {
    "PAGO":     ("Pago",     _VERDE),
    "PENDENTE": ("Pendente", _AMARELO),
    "ATRASADO": ("Atrasado", _VERMELHO),
}

HEADERS    = ["Cliente", "Venda", "Parcela", "Valor", "Vencimento", "Status", "Ações"]
COL_STATUS = 5
COL_ACOES  = 6


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hoje() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_data(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except (ValueError, TypeError):
        return None


# ── Card de métrica ───────────────────────────────────────────────────────────

class _MetricCard(ctk.CTkFrame):

    def __init__(self, master, icon: str, label: str, value: str,
                 accent: str, tint: str):
        super().__init__(master, fg_color=CARD_BG, corner_radius=12,
                         border_width=1, border_color=BORDER)
        self.grid_columnconfigure(0, weight=1)

        pill = ctk.CTkFrame(self, fg_color=tint, corner_radius=8,
                            width=38, height=38)
        pill.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
        pill.grid_propagate(False)
        ctk.CTkLabel(pill, text=icon, font=ctk.CTkFont(size=16),
                     text_color=accent,
                     ).place(relx=0.5, rely=0.5, anchor="center")

        self._val_lbl = ctk.CTkLabel(
            self, text=value,
            font=ctk.CTkFont(family="Georgia", size=22, weight="bold"),
            text_color=TEXT_MAIN,
        )
        self._val_lbl.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 2))

        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=11),
                     text_color=TEXT_SUB,
                     ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 16))

    def update_value(self, value: str) -> None:
        self._val_lbl.configure(text=value)


# ── View principal ────────────────────────────────────────────────────────────

class PagamentosView(ctk.CTkFrame):
    """
    View de Pagamentos — lista parcelas com filtros e métricas.

    Parâmetro `session`: SQLAlchemy Session (None → modo demonstração sem banco).
    """

    _CARD_DEFS = [
        ("$", "Total em aberto",    "—", _AZUL,     "#EEF1FD"),
        ("⚠", "Atrasadas",          "—", _VERMELHO, "#FEE2E2"),
        ("◷", "Vencem esta semana", "—", _AMARELO,  "#FEF3C7"),
        ("✓", "Pagas este mês",     "—", _VERDE,    "#D1FAE5"),
    ]

    def __init__(self, master, session=None):
        super().__init__(master, fg_color=BG, corner_radius=0)

        self._controller: PagamentoController | None = (
            PagamentoController(session) if session else None
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._filtro:    str             = "todas"
        self._parcelas:  list[dict]      = []
        self._cur_data:  list[dict]      = []
        self._table:     CTkTable | None = None
        self._cards:     dict[str, _MetricCard] = {}

        self._build()
        self._load()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_header()
        self._build_metrics()
        self._build_filterbar()
        self._build_table_area()

    def _build_header(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=28, pady=(28, 0))

        ctk.CTkLabel(top, text="Pagamentos",
                     font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
                     text_color=TEXT_MAIN,
                     ).pack(side="left")
        ctk.CTkLabel(top, text="visão financeira de parcelas",
                     font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
                     ).pack(side="left", padx=(10, 0), pady=(8, 0))

    def _build_metrics(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, sticky="ew", padx=28, pady=(20, 0))
        frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        for col, (icon, label, val, accent, tint) in enumerate(self._CARD_DEFS):
            c = _MetricCard(frame, icon, label, val, accent, tint)
            c.grid(row=0, column=col, sticky="nsew",
                   padx=(0 if col == 0 else 8, 0))
            self._cards[label] = c

    def _build_filterbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=28, pady=(18, 10))

        filtros = [
            ("todas",     "Todas"),
            ("pendentes", "Pendentes"),
            ("atrasadas", "Atrasadas"),
            ("pagas",     "Pagas"),
        ]
        self._filter_btns: dict[str, ctk.CTkButton] = {}
        for idx, (key, label) in enumerate(filtros):
            btn = ctk.CTkButton(
                bar, text=label, width=105, height=32,
                fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
                corner_radius=8, font=ctk.CTkFont(size=12),
                command=lambda k=key: self._set_filtro(k),
            )
            btn.grid(row=0, column=idx, padx=(0, 6))
            self._filter_btns[key] = btn

        bar.grid_columnconfigure(len(filtros), weight=1)

        self._search_entry = ctk.CTkEntry(
            bar, height=32, placeholder_text="Buscar por cliente ou venda...",
            corner_radius=8, fg_color=CARD_BG, border_color=BORDER,
            border_width=1, text_color=TEXT_MAIN, font=ctk.CTkFont(size=12),
        )
        self._search_entry.grid(row=0, column=len(filtros), sticky="ew",
                                padx=(0, 12))
        self._search_entry.bind("<KeyRelease>", lambda _: self._render(self._filtrar()))

        self._count_label = ctk.CTkLabel(bar, text="",
                                         font=ctk.CTkFont(size=12),
                                         text_color=TEXT_SUB)
        self._count_label.grid(row=0, column=len(filtros) + 1, padx=(0, 12))

        self._set_filtro_btn_style("todas")

    def _build_table_area(self):
        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.grid(row=3, column=0, sticky="nsew", padx=28, pady=(0, 28))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(card, fg_color=CARD_BG,
                                              scrollbar_button_color=BORDER,
                                              corner_radius=0)
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self._scroll.grid_columnconfigure(0, weight=1)

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _load(self):
        """Sincroniza atrasos e recarrega todos os pagamentos."""
        if self._controller:
            try:
                self._controller.sincronizar_atrasos()
                self._parcelas = self._controller.listar_todos()
            except Exception as e:
                print(f"Erro ao carregar pagamentos: {e}")
                self._parcelas = []

        self._atualizar_metricas()
        self._render(self._filtrar())

    # ── Métricas ──────────────────────────────────────────────────────────────

    def _atualizar_metricas(self):
        hoje   = _hoje()
        semana = hoje + timedelta(days=7)

        em_aberto    = sum(
            p["valor"] for p in self._parcelas
            if p["status"] != "PAGO"
        )
        atrasadas    = sum(1 for p in self._parcelas if p["status"] == "ATRASADO")
        vence_semana = sum(
            1 for p in self._parcelas
            if p["status"] != "PAGO"
            and (dt := _parse_data(p.get("data_vencimento", "")))
            and hoje <= dt <= semana
        )
        pagas_mes    = sum(
            1 for p in self._parcelas
            if p["status"] == "PAGO"
            and (dt := _parse_data(p.get("data_pagamento") or ""))
            and dt.month == hoje.month and dt.year == hoje.year
        )

        self._cards["Total em aberto"].update_value(_fmt_brl(em_aberto))
        self._cards["Atrasadas"].update_value(str(atrasadas))
        self._cards["Vencem esta semana"].update_value(str(vence_semana))
        self._cards["Pagas este mês"].update_value(str(pagas_mes))

    # ── Filtros ───────────────────────────────────────────────────────────────

    def _set_filtro(self, filtro: str):
        self._filtro = filtro
        self._set_filtro_btn_style(filtro)
        self._render(self._filtrar())

    def _set_filtro_btn_style(self, ativo: str):
        for key, btn in self._filter_btns.items():
            a = key == ativo
            btn.configure(
                fg_color=ACCENT if a else BORDER,
                hover_color=ACCENT_HOVER if a else "#DDDFE8",
                text_color="#FFF" if a else TEXT_MAIN,
                font=ctk.CTkFont(size=12, weight="bold" if a else "normal"),
            )

    def _filtrar(self) -> list[dict]:
        dados = self._parcelas

        if self._filtro == "pendentes":
            dados = [p for p in dados if p["status"] == "PENDENTE"]
        elif self._filtro == "atrasadas":
            dados = [p for p in dados if p["status"] == "ATRASADO"]
        elif self._filtro == "pagas":
            dados = [p for p in dados if p["status"] == "PAGO"]

        termo = self._search_entry.get().lower().strip()
        if termo:
            dados = [p for p in dados
                     if termo in p["cliente"].lower()
                     or termo in str(p["venda_id"])]
        return dados

    # ── Renderização ──────────────────────────────────────────────────────────

    def _render(self, dados: list[dict]):
        self._cur_data = dados
        n = len(dados)
        self._count_label.configure(text=f"{n} parcela{'s' if n != 1 else ''}")

        if self._table:
            self._table.destroy()
            self._table = None
        for w in self._scroll.winfo_children():
            w.destroy()

        if not dados:
            _label(self._scroll, "Nenhuma parcela encontrada.",
                   font_size=13, color=TEXT_SUB, anchor="center",
                   row=0, column=0, pady=48)
            return

        values = [HEADERS]
        for p in dados:
            status_lbl, _ = STATUS_CFG.get(p["status"], (p["status"], TEXT_SUB))
            num  = p.get("numero_parcela")
            tot  = p.get("total_parcelas")
            parc = f"{num}/{tot}" if num and tot else (str(num) if num else "—")

            values.append([
                p.get("cliente", "—"),
                f"#{p.get('venda_id', '—')}",
                parc,
                _fmt_brl(p.get("valor")),
                p.get("data_vencimento", "—"),
                status_lbl,
                "",
            ])

        self._table = CTkTable(
            self._scroll, values=values,
            header_color=HEADER_BG, colors=[CARD_BG, ROW_ALT],
            text_color=TEXT_MAIN, hover=True, hover_color=ROW_HOVER,
            height=46, font=ctk.CTkFont(size=13),
            padx=1, pady=1, corner_radius=8,
            border_width=1, border_color=BORDER,
            command=self._on_cell_click, anchor="w",
        )
        self._table.pack(fill="both", expand=True, padx=4, pady=4)

        self._table.edit_row(0, text_color=TEXT_SUB, fg_color=HEADER_BG,
                             hover_color=HEADER_BG, hover=False,
                             font=ctk.CTkFont(size=11, weight="bold"), height=38)

        for i, p in enumerate(dados):
            row_idx  = i + 1
            _, color = STATUS_CFG.get(p["status"], ("—", TEXT_SUB))

            self._table.frame[row_idx, COL_STATUS].configure(
                text_color=color, font=ctk.CTkFont(size=12, weight="bold"))

            if p["status"] == "ATRASADO":
                self._table.frame[row_idx, 4].configure(
                    text_color=_VERMELHO, font=ctk.CTkFont(size=13, weight="bold"))

            self._injetar_botao(row_idx, p)

    def _injetar_botao(self, row_idx: int, p: dict):
        """Injeta o botão de ação na célula correta da tabela."""
        cell = self._table.frame[row_idx, COL_ACOES]
        cell.configure(text="", hover=False)

        btn_frame = ctk.CTkFrame(cell, fg_color="transparent")
        btn_frame.place(relx=0.5, rely=0.5, anchor="center")

        is_pago = p["status"] == "PAGO"
        if is_pago:
            ctk.CTkButton(
                btn_frame, text="✓ Pago", width=82, height=28,
                fg_color="#D1FAE5", hover_color="#D1FAE5", text_color=_VERDE,
                corner_radius=6, font=ctk.CTkFont(size=11, weight="bold"),
                state="disabled",
            ).pack()
        else:
            ctk.CTkButton(
                btn_frame, text="Registrar", width=82, height=28,
                fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFF",
                corner_radius=6, font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda pp=p: self._abrir_registrar(pp),
            ).pack()

    # ── Clique em célula ──────────────────────────────────────────────────────

    def _on_cell_click(self, cell: dict):
        row = cell["row"]
        col = cell["column"]
        if row == 0 or col == COL_ACOES:
            return
        idx = row - 1
        if idx < len(self._cur_data):
            p = self._cur_data[idx]
            if p["status"] != "PAGO":
                self._abrir_registrar(p)

    # ── Modal e registro ──────────────────────────────────────────────────────

    def _abrir_registrar(self, parcela: dict):
        RegistrarPagamentoModal(
            self,
            parcela=parcela,
            on_save=self._on_registrar,
        )

    def _on_registrar(
        self,
        pagamento_id:   int,
        valor_pago:     float,
        data_pagamento: datetime,
        observacoes:    str = "",
    ):
        if not self._controller:
            self._load()
            return

        try:
            resultado = self._controller.registrar_pagamento(
                pagamento_id=pagamento_id,
                valor_pago=valor_pago,
                data_pagamento=data_pagamento,
                observacoes=observacoes or None,
            )
            self._load()
            self._exibir_feedback(resultado)

        except ValueError as e:
            self._exibir_erro(str(e))

    def _exibir_feedback(self, resultado: dict):
        """
        Exibe um banner temporário de sucesso.
        Se houver crédito gerado, informa o valor ao usuário.
        """
        credito = resultado.get("credito_gerado", 0)
        if credito and credito > 0:
            msg = f"✓  Pagamento registrado  •  Crédito gerado: {_fmt_brl(float(credito))}"
            color = _AZUL
        else:
            msg   = "✓  Pagamento registrado com sucesso."
            color = _VERDE

        self._mostrar_banner(msg, color)

    def _exibir_erro(self, msg: str):
        self._mostrar_banner(f"⚠  {msg}", _VERMELHO)

    def _mostrar_banner(self, msg: str, color: str):
        """Banner temporário no topo da view, auto-remove após 4 segundos."""
        # Remove banner anterior se existir
        if hasattr(self, "_banner") and self._banner.winfo_exists():
            self._banner.destroy()

        self._banner = ctk.CTkLabel(
            self, text=msg,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FFF",
            fg_color=color,
            corner_radius=8,
            height=36,
        )
        self._banner.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 8))
        self.after(4000, lambda: self._banner.destroy()
                   if self._banner.winfo_exists() else None)