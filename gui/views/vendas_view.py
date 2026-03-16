"""
gui/views/vendas_view.py

Listagem de vendas com filtros, métricas e acesso ao detalhe.

ARQUITETURA:
    VendasView  →  VendaController  →  venda_service / pagamento_service
    (sem imports de services aqui)

MELHORIAS APLICADAS:
- Acoplamento removido: View usa VendaController exclusivamente
- Filtros delegados ao controller (sem lógica de filtragem duplicada)
- Banner de feedback com crédito gerado (mesmo padrão de PagamentosView)
- _registrar() passa observacoes ao controller
- Código de layout extraído em métodos privados focados
"""
from __future__ import annotations

from datetime import datetime

import customtkinter as ctk
from CTkTable import CTkTable

from gui.controllers.venda_controller import VendaController
from gui.components.venda_detalhe_modal import VendaDetalheModal
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
_LILAC    = "#7C3AED"

STATUS_CFG: dict[str, tuple[str, str]] = {
    "ABERTA":  ("● Em aberto", _AMARELO),
    "QUITADA": ("● Quitada",   _VERDE),
}
TIPO_CFG: dict[str, tuple[str, str]] = {
    "AVISTA":    ("À vista",   _AZUL),
    "PARCELADO": ("Parcelado", _LILAC),
}

HEADERS    = ["#", "Cliente", "Data", "Tipo", "Valor Total", "Pago", "Status", "Ações"]
COL_STATUS = 6
COL_ACOES  = 7

_FILTROS = [
    ("todas",      "Todas",      None,       None),
    ("abertas",    "Em aberto",  "ABERTA",   None),
    ("quitadas",   "Quitadas",   "QUITADA",  None),
    ("avista",     "À vista",    None,       "AVISTA"),
    ("parceladas", "Parceladas", None,       "PARCELADO"),
]


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

        self._val = ctk.CTkLabel(
            self, text=value,
            font=ctk.CTkFont(family="Georgia", size=22, weight="bold"),
            text_color=TEXT_MAIN,
        )
        self._val.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 2))

        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=11),
                     text_color=TEXT_SUB,
                     ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 16))

    def set_value(self, value: str) -> None:
        self._val.configure(text=value)


# ── View principal ────────────────────────────────────────────────────────────

class VendasView(ctk.CTkFrame):
    """
    View de Vendas — lista todas as vendas com métricas e detalhe.

    `session`: SQLAlchemy Session (None → dados de exemplo).
    """

    _CARD_DEFS = [
        ("◎", "Total de vendas",   "—", _AZUL,    "#EEF1FD"),
        ("$", "Faturamento total", "—", _VERDE,   "#D1FAE5"),
        ("◷", "Em aberto",         "—", _AMARELO, "#FEF3C7"),
        ("✦", "Ticket médio",      "—", _LILAC,   "#EDE9FE"),
    ]

    def __init__(self, master, session=None):
        super().__init__(master, fg_color=BG, corner_radius=0)

        self._controller: VendaController | None = (
            VendaController(session) if session else None
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._filtro_key: str        = "todas"
        self._todas:      list[dict] = []   # cache completo (sem filtro)
        self._cur:        list[dict] = []   # dado exibido atualmente
        self._table:      CTkTable | None = None
        self._cards:      dict[str, _MetricCard] = {}
        self._filter_btns: dict[str, ctk.CTkButton] = {}

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
        ctk.CTkLabel(top, text="Vendas",
                     font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
                     text_color=TEXT_MAIN,
                     ).pack(side="left")
        ctk.CTkLabel(top, text="histórico e acompanhamento",
                     font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
                     ).pack(side="left", padx=(10, 0), pady=(8, 0))

    def _build_metrics(self):
        mf = ctk.CTkFrame(self, fg_color="transparent")
        mf.grid(row=1, column=0, sticky="ew", padx=28, pady=(20, 0))
        mf.grid_columnconfigure((0, 1, 2, 3), weight=1)

        for col, (icon, label, val, accent, tint) in enumerate(self._CARD_DEFS):
            c = _MetricCard(mf, icon, label, val, accent, tint)
            c.grid(row=0, column=col, sticky="nsew",
                   padx=(0 if col == 0 else 8, 0))
            self._cards[label] = c

    def _build_filterbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=28, pady=(18, 10))

        for idx, (key, label, *_) in enumerate(_FILTROS):
            btn = ctk.CTkButton(
                bar, text=label, width=108, height=32,
                fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
                corner_radius=8, font=ctk.CTkFont(size=12),
                command=lambda k=key: self._set_filtro(k),
            )
            btn.grid(row=0, column=idx, padx=(0, 6))
            self._filter_btns[key] = btn

        n = len(_FILTROS)
        bar.grid_columnconfigure(n, weight=1)

        self._search = ctk.CTkEntry(
            bar, height=32, placeholder_text="Buscar por cliente...",
            corner_radius=8, fg_color=CARD_BG, border_color=BORDER,
            border_width=1, text_color=TEXT_MAIN, font=ctk.CTkFont(size=12),
        )
        self._search.grid(row=0, column=n, sticky="ew", padx=(0, 12))
        self._search.bind("<KeyRelease>", lambda _: self._render(self._filtrar()))

        self._count_lbl = ctk.CTkLabel(bar, text="",
                                       font=ctk.CTkFont(size=12),
                                       text_color=TEXT_SUB)
        self._count_lbl.grid(row=0, column=n + 1)

        self._apply_btn_style("todas")

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
        if self._controller:
            try:
                self._todas = self._controller.listar_vendas()
            except Exception as e:
                print(f"Erro ao carregar vendas: {e}")
                self._todas = []

        self._atualizar_metricas()
        self._render(self._filtrar())

    # ── Métricas ──────────────────────────────────────────────────────────────

    def _atualizar_metricas(self):
        total       = len(self._todas)
        faturamento = sum(v["valor_total"]  for v in self._todas)
        em_aberto   = sum(v["saldo_devedor"] for v in self._todas)
        ticket      = faturamento / total if total else 0.0

        self._cards["Total de vendas"].set_value(str(total))
        self._cards["Faturamento total"].set_value(_fmt_brl(faturamento))
        self._cards["Em aberto"].set_value(_fmt_brl(em_aberto))
        self._cards["Ticket médio"].set_value(_fmt_brl(ticket))

    # ── Filtros ───────────────────────────────────────────────────────────────

    def _set_filtro(self, key: str):
        self._filtro_key = key
        self._apply_btn_style(key)
        self._render(self._filtrar())

    def _apply_btn_style(self, ativo: str):
        for key, btn in self._filter_btns.items():
            a = key == ativo
            btn.configure(
                fg_color=ACCENT if a else BORDER,
                hover_color=ACCENT_HOVER if a else "#DDDFE8",
                text_color="#FFF" if a else TEXT_MAIN,
                font=ctk.CTkFont(size=12, weight="bold" if a else "normal"),
            )

    def _filtrar(self) -> list[dict]:
        """
        Aplica filtro de status/tipo e busca textual sobre o cache completo.
        Não faz nova query ao banco — apenas filtra _todas em memória.
        """
        cfg = next((f for f in _FILTROS if f[0] == self._filtro_key), _FILTROS[0])
        _, _, filtro_status, filtro_tipo = cfg

        dados = self._todas
        if filtro_status:
            dados = [v for v in dados if v["status"] == filtro_status]
        if filtro_tipo:
            dados = [v for v in dados if v["tipo_pagamento"] == filtro_tipo]

        termo = self._search.get().lower().strip()
        if termo:
            dados = [v for v in dados if termo in v["cliente"].lower()]

        return dados

    # ── Renderização ──────────────────────────────────────────────────────────

    def _render(self, dados: list[dict]):
        self._cur = dados
        n = len(dados)
        self._count_lbl.configure(text=f"{n} venda{'s' if n != 1 else ''}")

        if self._table:
            self._table.destroy()
            self._table = None
        for w in self._scroll.winfo_children():
            w.destroy()

        if not dados:
            _label(self._scroll, "Nenhuma venda encontrada.",
                   font_size=13, color=TEXT_SUB, anchor="center",
                   row=0, column=0, pady=48)
            return

        values = [HEADERS]
        for v in dados:
            tipo_lbl, _ = TIPO_CFG.get(v["tipo_pagamento"], (v["tipo_pagamento"], TEXT_SUB))
            st_lbl,   _ = STATUS_CFG.get(v["status"],       (v["status"],         TEXT_SUB))
            values.append([
                f"#{v['id']}",
                v["cliente"],
                v["data"],
                tipo_lbl,
                _fmt_brl(v["valor_total"]),
                _fmt_brl(v["total_pago"]),
                st_lbl,
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

        for i, v in enumerate(dados):
            row_idx          = i + 1
            _, st_color      = STATUS_CFG.get(v["status"],       (v["status"],         TEXT_SUB))
            _, tipo_color    = TIPO_CFG.get(v["tipo_pagamento"],  (v["tipo_pagamento"], TEXT_SUB))

            self._table.frame[row_idx, COL_STATUS].configure(
                text_color=st_color, font=ctk.CTkFont(size=12, weight="bold"))
            self._table.frame[row_idx, 3].configure(text_color=tipo_color)

            pago_color = _VERDE if v["status"] == "QUITADA" else (
                         _AMARELO if v["saldo_devedor"] > 0 else TEXT_MAIN)
            self._table.frame[row_idx, 5].configure(text_color=pago_color)

            self._injetar_botao(row_idx, v)

    def _injetar_botao(self, row_idx: int, v: dict):
        cell = self._table.frame[row_idx, COL_ACOES]
        cell.configure(text="", hover=False)

        btn_f = ctk.CTkFrame(cell, fg_color="transparent")
        btn_f.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkButton(
            btn_f, text="Ver detalhes", width=100, height=28,
            fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
            corner_radius=6, font=ctk.CTkFont(size=11),
            command=lambda vv=v: self._abrir_detalhe(vv),
        ).pack()

    # ── Clique em célula ──────────────────────────────────────────────────────

    def _on_cell_click(self, cell: dict):
        row = cell["row"]
        col = cell["column"]
        if row == 0 or col == COL_ACOES:
            return
        idx = row - 1
        if idx < len(self._cur):
            self._abrir_detalhe(self._cur[idx])

    # ── Modais ────────────────────────────────────────────────────────────────

    def _abrir_detalhe(self, venda: dict):
        VendaDetalheModal(
            self,
            venda=venda,
            on_registrar_pagamento=self._abrir_registrar_pagamento,
        )

    def _abrir_registrar_pagamento(self, parcela: dict):
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

    # ── Feedback ──────────────────────────────────────────────────────────────

    def _exibir_feedback(self, resultado: dict):
        credito = resultado.get("credito_gerado", 0)
        if credito and credito > 0:
            msg   = f"✓  Pagamento registrado  •  Crédito gerado: {_fmt_brl(float(credito))}"
            color = _AZUL
        else:
            msg   = "✓  Pagamento registrado com sucesso."
            color = _VERDE
        self._mostrar_banner(msg, color)

    def _exibir_erro(self, msg: str):
        self._mostrar_banner(f"⚠  {msg}", _VERMELHO)

    def _mostrar_banner(self, msg: str, color: str):
        if hasattr(self, "_banner") and self._banner.winfo_exists():
            self._banner.destroy()

        self._banner = ctk.CTkLabel(
            self, text=msg,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FFF", fg_color=color,
            corner_radius=8, height=36,
        )
        self._banner.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 8))
        self.after(4000, lambda: self._banner.destroy()
                   if self._banner.winfo_exists() else None)