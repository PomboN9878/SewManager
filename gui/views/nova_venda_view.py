"""
NovaVendaView — GUI de criação de venda em 4 passos.

ARQUITETURA:
    NovaVendaView  →  VendaController  →  venda_service / cliente_service
                   ↕
                VendaDraft  (estado tipado, sem dict solto)

MELHORIAS v2:
- Step 2: carrinho multi-máquina — clique = adiciona/remove; mostra lista abaixo da tabela
- Debounce 300 ms nas buscas (evita query a cada tecla)
- Validação completa do draft antes de finalizar (_validar_draft)
- Step 3: preview ao vivo das parcelas com nota de arredondamento
- Step 4: lista todas as máquinas do carrinho (não apenas uma)
- Resumo lateral: "N máquinas" quando múltiplas
- Atalhos: Enter → próximo, Esc → voltar, Ctrl+F → foco na busca
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import customtkinter as ctk
from CTkTable import CTkTable

from gui.controllers.venda_controller import VendaController
from gui.components import ClienteFormModal
from gui.components.base_modal import (
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER,
    HEADER_BG, ROW_ALT, ROW_HOVER,
    fmt_brl as _fmt_brl,
    make_label,
)
from gui.drafts.venda_draft import (
    VendaDraft, ClienteDraft, MaquinaDraft, PagamentoDraft,
)

SUCCESS      = "#059669"
ROW_SELECTED = "#EEF0FF"
ROW_CART     = "#F0FFF4"   # verde suave para itens no carrinho
ROW_CART_HOV = "#E0FFF0"

STEPS = [
    ("1", "Cliente"),
    ("2", "Máquinas"),
    ("3", "Pagamento"),
    ("4", "Confirmar"),
]


# ── Helpers locais ────────────────────────────────────────────────────────────

def _parse_decimal(text: str) -> Decimal:
    """
    Parser monetário robusto.
    Aceita: "1500" / "1500.00" / "1.500" / "1.500,00" / "1,500.00"
    Retorna Decimal("0") se inválido.
    """
    raw = text.strip()
    if not raw:
        return Decimal("0")

    raw = re.sub(r"[R$\s]", "", raw)

    if "," in raw and "." in raw:
        if raw.index(",") > raw.index("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        parts = raw.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")

    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _entry(parent, placeholder="", width=None, initial=""):
    kw = dict(height=36, corner_radius=8, fg_color=CARD_BG,
              border_color=BORDER, border_width=1,
              text_color=TEXT_MAIN, font=ctk.CTkFont(size=13),
              placeholder_text=placeholder)
    if width:
        kw["width"] = width
    e = ctk.CTkEntry(parent, **kw)
    if initial:
        e.insert(0, initial)
    return e


def _section_label(parent, text, row, col=0, colspan=1, pady=(16, 6)):
    ctk.CTkLabel(parent, text=text,
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=TEXT_SUB, anchor="w",
                 ).grid(row=row, column=col, columnspan=colspan,
                        sticky="w", pady=pady)


def _table_card(parent, row) -> tuple:
    card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                        border_width=1, border_color=BORDER)
    card.grid(row=row, column=0, sticky="nsew")
    card.grid_columnconfigure(0, weight=1)
    card.grid_rowconfigure(0, weight=1)

    scroll = ctk.CTkScrollableFrame(card, fg_color=CARD_BG,
                                    scrollbar_button_color=BORDER,
                                    corner_radius=0)
    scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
    scroll.grid_columnconfigure(0, weight=1)
    return card, scroll


# ── Stepper header ────────────────────────────────────────────────────────────

class _Stepper(ctk.CTkFrame):

    def __init__(self, master, steps):
        super().__init__(master, fg_color=CARD_BG, corner_radius=0, height=72)
        self.grid_propagate(False)
        self.steps    = steps
        self._current = 0
        self._done:   set  = set()
        self._circles: list = []
        self._labels:  list = []
        self._lines:   list = []

        n = len(steps)
        for i in range(n * 2 - 1):
            self.grid_columnconfigure(i, weight=1 if i % 2 == 1 else 0)
        self._build()

    def _build(self):
        for i, (num, label) in enumerate(self.steps):
            col = i * 2
            circle = ctk.CTkLabel(
                self, text=num, width=32, height=32, corner_radius=16,
                fg_color=BORDER, text_color=TEXT_SUB,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            circle.grid(row=0, column=col, pady=(16, 4))
            self._circles.append(circle)

            lbl = ctk.CTkLabel(self, text=label,
                               font=ctk.CTkFont(size=11), text_color=TEXT_SUB)
            lbl.grid(row=1, column=col, pady=(0, 12))
            self._labels.append(lbl)

            if i < len(self.steps) - 1:
                line = ctk.CTkFrame(self, height=2, fg_color=BORDER, corner_radius=1)
                line.grid(row=0, column=col + 1, sticky="ew", padx=4)
                self._lines.append(line)

        self._refresh()

    def _refresh(self):
        for i, (circle, lbl) in enumerate(zip(self._circles, self._labels)):
            if i in self._done:
                circle.configure(fg_color=SUCCESS, text_color="#FFFFFF", text="✓")
                lbl.configure(text_color=SUCCESS,
                              font=ctk.CTkFont(size=11, weight="bold"))
            elif i == self._current:
                circle.configure(fg_color=ACCENT, text_color="#FFFFFF",
                                 text=self.steps[i][0])
                lbl.configure(text_color=ACCENT,
                              font=ctk.CTkFont(size=11, weight="bold"))
            else:
                circle.configure(fg_color=BORDER, text_color=TEXT_SUB,
                                 text=self.steps[i][0])
                lbl.configure(text_color=TEXT_SUB, font=ctk.CTkFont(size=11))

        for i, line in enumerate(self._lines):
            line.configure(fg_color=SUCCESS if i in self._done else BORDER)

    def set_step(self, idx: int, completed_up_to: int):
        self._current = idx
        self._done    = set(range(completed_up_to))
        self._refresh()


# ── Painel lateral: Resumo ────────────────────────────────────────────────────

class _ResumoPanel(ctk.CTkFrame):

    _FIELDS = [
        ("cliente",   "Cliente"),
        ("itens",     "Itens"),          # N máquinas ou nome único
        ("preco",     "Preço Total"),
        ("pagamento", "Pagamento"),
        ("entrada",   "Entrada"),
        ("parcelas",  "Parcelas"),
    ]

    def __init__(self, master):
        super().__init__(master, fg_color=CARD_BG, corner_radius=12,
                         border_width=1, border_color=BORDER, width=260)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self._rows: dict = {}

        ctk.CTkLabel(self, text="Resumo da Venda",
                     font=ctk.CTkFont(family="Georgia", size=15, weight="bold"),
                     text_color=TEXT_MAIN, anchor="w",
                     ).grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 4))
        ctk.CTkFrame(self, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        for i, (key, label) in enumerate(self._FIELDS):
            ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=11),
                         text_color=TEXT_SUB, anchor="w",
                         ).grid(row=i * 2 + 2, column=0, sticky="w",
                                padx=20, pady=(6, 1))
            val = ctk.CTkLabel(self, text="—",
                               font=ctk.CTkFont(size=13, weight="bold"),
                               text_color=TEXT_MAIN, anchor="w", wraplength=210)
            val.grid(row=i * 2 + 3, column=0, sticky="ew", padx=20)
            self._rows[key] = val

        base = len(self._FIELDS) * 2 + 2
        ctk.CTkFrame(self, height=1, fg_color=BORDER).grid(
            row=base, column=0, sticky="ew", padx=12, pady=(16, 8))
        ctk.CTkLabel(self, text="TOTAL",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT_SUB, anchor="w",
                     ).grid(row=base + 1, column=0, sticky="w", padx=20)
        self._total = ctk.CTkLabel(self, text="—",
                                   font=ctk.CTkFont(family="Georgia", size=22,
                                                    weight="bold"),
                                   text_color=ACCENT, anchor="w")
        self._total.grid(row=base + 2, column=0, sticky="w", padx=20, pady=(2, 20))

    def update(self, **kwargs):
        for key, val in kwargs.items():
            if key == "total":
                self._total.configure(text=val or "—")
            elif key in self._rows:
                self._rows[key].configure(text=val or "—")

    def update_from_draft(self, draft: VendaDraft) -> None:
        """Atualiza o painel a partir de um VendaDraft tipado."""
        pg    = draft.pagamento
        preco = pg.preco
        saldo = preco - pg.entrada
        val_p = (saldo / pg.parcelas) if pg.parcelas else Decimal("0")

        # Resumo dos itens no carrinho
        n = len(draft.maquinas)
        if n == 0:
            itens_str = None
        elif n == 1:
            m = draft.maquinas[0]
            itens_str = f"{m.marca} {m.modelo}"
        else:
            itens_str = f"{n} máquinas"

        self.update(
            cliente   = draft.cliente.nome if draft.cliente else None,
            itens     = itens_str,
            preco     = _fmt_brl(float(preco)) if preco else None,
            pagamento = "À Vista"  if pg.tipo == "avista"
                        else "Parcelado" if pg.tipo == "parcelado" else None,
            entrada   = (
                _fmt_brl(float(pg.entrada))
                if pg.tipo == "parcelado" and pg.entrada else None
            ),
            parcelas  = (
                f"{pg.parcelas}× de {_fmt_brl(float(val_p))}"
                if pg.tipo == "parcelado" and pg.parcelas else None
            ),
            total     = _fmt_brl(float(preco)) if preco else None,
        )


# ── Step 1: Cliente ───────────────────────────────────────────────────────────

class _Step1Cliente(ctk.CTkFrame):

    HEADERS = ["Nome", "Documento", "Telefone"]

    def __init__(self, master, controller: VendaController, on_change):
        super().__init__(master, fg_color="transparent")
        self.controller  = controller
        self.on_change   = on_change
        self._all:       list[ClienteDraft] = []
        self._cur:       list[ClienteDraft] = []
        self.selected:   ClienteDraft | None = None
        self._table:     CTkTable | None = None
        self._sel_row:   int | None = None
        self._warn_lbl:  ctk.CTkLabel | None = None
        self._deb_id:    str | None = None   # debounce handle

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self._load()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        top.grid_columnconfigure(0, weight=1)

        self.search = _entry(top, placeholder="Buscar cliente por nome ou documento…")
        self.search.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(top, text="＋ Novo Cliente", width=120, height=36,
                      fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
                      corner_radius=8, font=ctk.CTkFont(size=13),
                      command=self._novo_cliente,
                      ).grid(row=0, column=1)

        _, self._scroll = _table_card(self, row=1)

    def _load(self):
        try:
            self._all = self.controller.listar_clientes()
        except Exception as e:
            print(f"Erro clientes: {e}")
            self._all = []
        self._render(self._all)

    # ── Debounce 300 ms ───────────────────────────────────────────────────────

    def _on_search(self, event=None):
        if self._deb_id:
            self.after_cancel(self._deb_id)
        self._deb_id = self.after(300, self._do_search)

    def _do_search(self):
        self._deb_id = None
        self._render(self._filter())

    def _filter(self) -> list[ClienteDraft]:
        return self.controller.listar_clientes(filtro=self.search.get())

    def _render(self, dados: list[ClienteDraft]):
        self._cur = dados

        if self._table:
            self._table.destroy()
            self._table = None
        for w in self._scroll.winfo_children():
            w.destroy()

        if not dados:
            make_label(self._scroll, "Nenhum cliente encontrado.",
                       font_size=13, color=TEXT_SUB, anchor="center",
                       row=0, column=0, pady=32)
            return

        values = [self.HEADERS] + [
            [c.nome, c.documento, c.telefone] for c in dados
        ]
        self._table = CTkTable(
            self._scroll, values=values,
            header_color=HEADER_BG, colors=[CARD_BG, ROW_ALT],
            text_color=TEXT_MAIN, hover=True, hover_color=ROW_HOVER,
            height=44, font=ctk.CTkFont(size=13),
            padx=1, pady=1, corner_radius=8,
            border_width=1, border_color=BORDER,
            command=self._on_cell_click, anchor="w",
        )
        self._table.pack(fill="both", expand=True, padx=4, pady=4)
        self._table.edit_row(0, text_color=TEXT_SUB, fg_color=HEADER_BG,
                             hover_color=HEADER_BG, hover=False,
                             font=ctk.CTkFont(size=11, weight="bold"), height=38)

        if self.selected:
            for i, c in enumerate(dados):
                if c.id == self.selected.id:
                    self._highlight_row(i + 1)
                    break

    def _on_cell_click(self, cell: dict):
        row = cell["row"]
        if row == 0 or row - 1 >= len(self._cur):
            return
        self._select(self._cur[row - 1], row)

    def _select(self, cliente: ClienteDraft, row_idx: int):
        if self._sel_row is not None and self._table:
            prev_bg = ROW_ALT if (self._sel_row - 1) % 2 else CARD_BG
            self._table.edit_row(self._sel_row,
                                 fg_color=prev_bg, hover_color=ROW_HOVER)
        self.selected  = cliente
        self._sel_row  = row_idx
        self._highlight_row(row_idx)
        self.on_change("cliente", cliente)
        if self._warn_lbl:
            self._warn_lbl.destroy()
            self._warn_lbl = None

    def _highlight_row(self, row_idx: int):
        if self._table:
            self._table.edit_row(row_idx, fg_color=ROW_SELECTED,
                                 hover_color=ROW_SELECTED)
            self._table.frame[row_idx, 0].configure(
                font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT)

    def _novo_cliente(self):
        def _salvar(data: dict):
            try:
                novo = self.controller.criar_cliente(
                    nome=data["nome"],
                    documento=data.get("documento"),
                    telefone=data.get("telefone"),
                )
                self._load()
                for i, c in enumerate(self._cur):
                    if c.id == novo.id:
                        self._select(c, i + 1)
                        break
            except Exception as ex:
                print(f"Erro criar cliente: {ex}")

        ClienteFormModal(self, on_save=_salvar)

    def focus_search(self):
        self.search.focus_set()

    def validate(self) -> bool:
        if self.selected:
            return True
        if self._warn_lbl:
            self._warn_lbl.destroy()
        self._warn_lbl = ctk.CTkLabel(
            self, text="⚠  Selecione um cliente para continuar.",
            font=ctk.CTkFont(size=12), text_color="#E05C5C",
        )
        self._warn_lbl.grid(row=2, column=0, sticky="w", pady=(6, 0))
        return False


# ── Step 2: Máquinas (carrinho) ───────────────────────────────────────────────

class _Step2Maquina(ctk.CTkFrame):
    """
    Tabela de estoque + carrinho de seleção multi-máquina.

    • Clique em uma linha da tabela → adiciona/remove do carrinho.
    • Linhas no carrinho ficam em verde claro na tabela.
    • O painel inferior mostra os itens do carrinho com opção × de remoção.
    • Debounce de 300 ms na busca.
    """

    HEADERS = ["Marca", "Modelo", "Série", "Mesa", "P. Venda"]

    def __init__(self, master, controller: VendaController, on_change):
        super().__init__(master, fg_color="transparent")
        self.controller  = controller
        self.on_change   = on_change
        self._all:       list[MaquinaDraft] = []
        self._cur:       list[MaquinaDraft] = []
        self._cart:      list[MaquinaDraft] = []
        self._table:     CTkTable | None = None
        self._warn_lbl:  ctk.CTkLabel | None = None
        self._deb_id:    str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self._load()

    def _build(self):
        # ── Barra de busca ────────────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.grid_columnconfigure(0, weight=1)

        self.search = _entry(top, placeholder="Buscar marca, modelo ou série…")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", self._on_search)

        # ── Tabela de estoque ─────────────────────────────────────────────────
        _, self._scroll = _table_card(self, row=1)

        # ── Painel do carrinho ────────────────────────────────────────────────
        self._cart_outer = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10,
                                        border_width=1, border_color=BORDER)
        self._cart_outer.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._cart_outer.grid_columnconfigure(0, weight=1)
        self._build_cart_header()

        sep = ctk.CTkFrame(self._cart_outer, height=1, fg_color=BORDER)
        sep.grid(row=1, column=0, sticky="ew")

        self._cart_scroll = ctk.CTkScrollableFrame(
            self._cart_outer, fg_color="transparent",
            height=88, scrollbar_button_color=BORDER, corner_radius=0,
        )
        self._cart_scroll.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 6))
        self._cart_scroll.grid_columnconfigure(0, weight=1)

        self._render_cart()

    def _build_cart_header(self):
        hdr = ctk.CTkFrame(self._cart_outer, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 6))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="CARRINHO",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TEXT_SUB).grid(row=0, column=0, sticky="w")

        self._cart_count_lbl = ctk.CTkLabel(
            hdr, text="• nenhum item",
            font=ctk.CTkFont(size=10), text_color=TEXT_SUB)
        self._cart_count_lbl.grid(row=0, column=1, sticky="w", padx=(6, 0))

        self._cart_total_lbl = ctk.CTkLabel(
            hdr, text="",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT)
        self._cart_total_lbl.grid(row=0, column=2, sticky="e")

    # ── Debounce 300 ms ───────────────────────────────────────────────────────

    def _on_search(self, event=None):
        if self._deb_id:
            self.after_cancel(self._deb_id)
        self._deb_id = self.after(300, self._do_search)

    def _do_search(self):
        self._deb_id = None
        self._render(self._filter())

    # ── Carregar / filtrar ────────────────────────────────────────────────────

    def _load(self):
        try:
            self._all = self.controller.listar_maquinas()
        except Exception as e:
            print(f"Erro máquinas: {e}")
            self._all = []
        self._render(self._all)

    def _filter(self) -> list[MaquinaDraft]:
        return self.controller.listar_maquinas(filtro=self.search.get())

    def _in_cart(self, maq: MaquinaDraft) -> bool:
        return any(c.id == maq.id for c in self._cart)

    # ── Renderização da tabela ────────────────────────────────────────────────

    def _render(self, dados: list[MaquinaDraft]):
        self._cur = dados

        if self._table:
            self._table.destroy()
            self._table = None
        for w in self._scroll.winfo_children():
            w.destroy()

        if not dados:
            make_label(self._scroll, "Nenhuma máquina disponível.",
                       font_size=13, color=TEXT_SUB, anchor="center",
                       row=0, column=0, pady=32)
            return

        values = [self.HEADERS] + [
            [
                m.marca, m.modelo, m.numero_serie, m.mesa,
                _fmt_brl(float(m.preco_venda_sugerido))
                if m.preco_venda_sugerido else "—",
            ]
            for m in dados
        ]
        self._table = CTkTable(
            self._scroll, values=values,
            header_color=HEADER_BG, colors=[CARD_BG, ROW_ALT],
            text_color=TEXT_MAIN, hover=True, hover_color=ROW_HOVER,
            height=44, font=ctk.CTkFont(size=13),
            padx=1, pady=1, corner_radius=8,
            border_width=1, border_color=BORDER,
            command=self._on_cell_click, anchor="w",
        )
        self._table.pack(fill="both", expand=True, padx=4, pady=4)
        self._table.edit_row(0, text_color=TEXT_SUB, fg_color=HEADER_BG,
                             hover_color=HEADER_BG, hover=False,
                             font=ctk.CTkFont(size=11, weight="bold"), height=38)

        for i in range(1, len(dados) + 1):
            self._table.frame[i, 4].configure(
                font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT)

        # Restaura destaque das máquinas já no carrinho
        for i, m in enumerate(dados):
            if self._in_cart(m):
                self._highlight_cart_row(i + 1)

    def _on_cell_click(self, cell: dict):
        row = cell["row"]
        if row == 0 or row - 1 >= len(self._cur):
            return
        maq = self._cur[row - 1]
        if self._in_cart(maq):
            self._remove_from_cart(maq)
            # Devolve cor original da linha
            if self._table:
                prev_bg = ROW_ALT if (row - 1) % 2 else CARD_BG
                self._table.edit_row(row, fg_color=prev_bg, hover_color=ROW_HOVER)
                self._table.frame[row, 0].configure(
                    font=ctk.CTkFont(size=13), text_color=TEXT_MAIN)
                self._table.frame[row, 4].configure(text_color=ACCENT)
        else:
            self._add_to_cart(maq)
            self._highlight_cart_row(row)

    def _highlight_cart_row(self, row_idx: int):
        if self._table:
            self._table.edit_row(row_idx, fg_color=ROW_CART,
                                 hover_color=ROW_CART_HOV)
            self._table.frame[row_idx, 0].configure(
                font=ctk.CTkFont(size=13, weight="bold"), text_color=SUCCESS)

    # ── Carrinho ──────────────────────────────────────────────────────────────

    def _add_to_cart(self, maq: MaquinaDraft):
        if not self._in_cart(maq):
            self._cart.append(maq)
        self._render_cart()
        self.on_change("maquinas", list(self._cart))
        if self._warn_lbl:
            self._warn_lbl.destroy()
            self._warn_lbl = None

    def _remove_from_cart(self, maq: MaquinaDraft):
        self._cart = [c for c in self._cart if c.id != maq.id]
        self._render_cart()
        self._render(self._cur)          # atualiza cores da tabela
        self.on_change("maquinas", list(self._cart))

    def _render_cart(self):
        for w in self._cart_scroll.winfo_children():
            w.destroy()

        if not self._cart:
            ctk.CTkLabel(
                self._cart_scroll,
                text="Clique em uma máquina para adicioná-la à venda",
                font=ctk.CTkFont(size=11), text_color=TEXT_SUB,
            ).pack(pady=8)
            self._cart_count_lbl.configure(text="• nenhum item")
            self._cart_total_lbl.configure(text="")
            return

        for maq in self._cart:
            row = ctk.CTkFrame(self._cart_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text="✓", font=ctk.CTkFont(size=12),
                         text_color=SUCCESS, width=22,
                         ).grid(row=0, column=0, padx=(0, 4), sticky="w")
            ctk.CTkLabel(
                row,
                text=f"{maq.marca} {maq.modelo}  ·  {maq.numero_serie}",
                font=ctk.CTkFont(size=12), text_color=TEXT_MAIN, anchor="w",
            ).grid(row=0, column=1, sticky="w")

            preco_txt = (
                _fmt_brl(float(maq.preco_venda_sugerido))
                if maq.preco_venda_sugerido else "—"
            )
            ctk.CTkLabel(row, text=preco_txt,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=ACCENT,
                         ).grid(row=0, column=2, padx=(8, 4))

            _m = maq
            ctk.CTkButton(
                row, text="×", width=24, height=24,
                fg_color="#FFEBEB", hover_color="#FFD6D6",
                text_color="#E05C5C", corner_radius=6,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda m=_m: self._remove_from_cart(m),
            ).grid(row=0, column=3, padx=(0, 4))

        n     = len(self._cart)
        total = sum(m.preco_venda_sugerido for m in self._cart)
        self._cart_count_lbl.configure(
            text=f"• {n} {'item' if n == 1 else 'itens'}")
        self._cart_total_lbl.configure(
            text=_fmt_brl(float(total)) if total else "")

    # ── Foco e validação ──────────────────────────────────────────────────────

    def focus_search(self):
        self.search.focus_set()

    def validate(self) -> bool:
        if self._cart:
            return True
        if self._warn_lbl:
            self._warn_lbl.destroy()
        self._warn_lbl = ctk.CTkLabel(
            self,
            text="⚠  Adicione ao menos uma máquina ao carrinho para continuar.",
            font=ctk.CTkFont(size=12), text_color="#E05C5C",
        )
        self._warn_lbl.grid(row=3, column=0, sticky="w", pady=(6, 0))
        return False


# ── Step 3: Preço e Pagamento ─────────────────────────────────────────────────

class _Step3Pagamento(ctk.CTkFrame):

    def __init__(self, master, on_change, preco_sugerido: Decimal = Decimal("0")):
        super().__init__(master, fg_color="transparent")
        self.on_change      = on_change
        self.preco_sugerido = preco_sugerido
        self.grid_columnconfigure((0, 1), weight=1)
        self._build()

    def _build(self):
        _section_label(self, "PREÇO DA VENDA", row=0, colspan=2, pady=(0, 6))

        price_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10,
                                  border_width=1, border_color=BORDER)
        price_card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        price_card.grid_columnconfigure((0, 1), weight=1)

        make_label(price_card, "Valor total (R$) *", font_size=11, color=TEXT_SUB,
                   anchor="w", row=0, column=0, sticky="w",
                   padx=16, pady=(14, 4))
        self.preco_entry = _entry(
            price_card, placeholder="0,00",
            initial=(
                f"{self.preco_sugerido:.2f}"
                if self.preco_sugerido else ""
            ),
        )
        self.preco_entry.grid(row=1, column=0, sticky="ew",
                              padx=(16, 8), pady=(0, 14))
        self.preco_entry.bind("<KeyRelease>", self._on_change)

        make_label(price_card, "Preço sugerido", font_size=11, color=TEXT_SUB,
                   anchor="w", row=0, column=1, sticky="w",
                   padx=(8, 16), pady=(14, 4))
        self._sug_lbl = ctk.CTkLabel(
            price_card,
            text=_fmt_brl(float(self.preco_sugerido)) if self.preco_sugerido else "—",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_SUB, anchor="w",
        )
        self._sug_lbl.grid(row=1, column=1, sticky="w", padx=(8, 16), pady=(0, 14))

        _section_label(self, "TIPO DE PAGAMENTO", row=2, colspan=2)

        tipo_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10,
                                 border_width=1, border_color=BORDER)
        tipo_card.grid(row=3, column=0, columnspan=2, sticky="ew")
        tipo_card.grid_columnconfigure((0, 1), weight=1)

        self.tipo_var = ctk.StringVar(value="avista")
        self.tipo_var.trace_add("write", self._on_tipo_change)

        for col, (val, lbl, icon) in enumerate([
            ("avista",    "À Vista",   "◉"),
            ("parcelado", "Parcelado", "☰"),
        ]):
            btn = ctk.CTkFrame(
                tipo_card,
                fg_color=ROW_SELECTED if val == "avista" else "transparent",
                corner_radius=8,
            )
            btn.grid(row=0, column=col, sticky="ew",
                     padx=(12 if col == 0 else 4, 4 if col == 0 else 12),
                     pady=10)
            btn.grid_columnconfigure(1, weight=1)
            rb = ctk.CTkRadioButton(
                btn, text=f" {icon}  {lbl}",
                variable=self.tipo_var, value=val,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=ACCENT if val == "avista" else TEXT_MAIN,
                fg_color=ACCENT, border_color=BORDER,
                hover_color=ACCENT_HOVER,
            )
            rb.grid(row=0, column=0, padx=12, pady=10)
            setattr(self, f"_btn_{val}", btn)
            setattr(self, f"_rb_{val}",  rb)

        # ── Campos de parcelamento ────────────────────────────────────────────
        self.parcela_frame = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10,
                                          border_width=1, border_color=BORDER)
        self.parcela_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self._par_entries: dict[str, ctk.CTkEntry] = {}
        for col, (lbl, key, ph) in enumerate([
            ("Entrada (R$)",     "entrada",   "0,00"),
            ("Nº de Parcelas",   "parcelas",  "3"),
            ("Intervalo (dias)", "intervalo", "30"),
        ]):
            make_label(self.parcela_frame, lbl, font_size=11, color=TEXT_SUB,
                       anchor="w", row=0, column=col, sticky="w",
                       padx=(16 if col == 0 else 8, 8), pady=(14, 4))
            e = _entry(self.parcela_frame, placeholder=ph)
            e.grid(row=1, column=col, sticky="ew",
                   padx=(16 if col == 0 else 8, 8 if col < 2 else 16),
                   pady=(0, 10))
            e.bind("<KeyRelease>", self._on_change)
            self._par_entries[key] = e

        # Preview ao vivo das parcelas
        self._preview_lbl = ctk.CTkLabel(
            self.parcela_frame, text="",
            font=ctk.CTkFont(size=11), text_color=TEXT_SUB, anchor="w",
        )
        self._preview_lbl.grid(row=2, column=0, columnspan=3, sticky="w",
                               padx=16, pady=(0, 10))

        self._on_tipo_change()

    def _on_tipo_change(self, *_):
        tipo = self.tipo_var.get()
        for val in ("avista", "parcelado"):
            btn = getattr(self, f"_btn_{val}")
            rb  = getattr(self, f"_rb_{val}")
            active = val == tipo
            btn.configure(fg_color=ROW_SELECTED if active else "transparent")
            rb.configure(text_color=ACCENT if active else TEXT_MAIN)

        if tipo == "parcelado":
            self.parcela_frame.grid(row=4, column=0, columnspan=2,
                                    sticky="ew", pady=(12, 0))
        else:
            self.parcela_frame.grid_remove()

        self._on_change()

    def _on_change(self, *_):
        self._update_preview()
        self.on_change("pagamento", self.get_draft())

    def _update_preview(self):
        """Mostra o valor de cada parcela ao vivo, com nota de arredondamento."""
        if self.tipo_var.get() != "parcelado":
            self._preview_lbl.configure(text="")
            return

        preco = _parse_decimal(self.preco_entry.get())
        try:
            entrada  = _parse_decimal(self._par_entries["entrada"].get())
            parcelas = int(self._par_entries["parcelas"].get() or "0")
        except ValueError:
            self._preview_lbl.configure(text="")
            return

        if parcelas < 1 or preco <= Decimal("0"):
            self._preview_lbl.configure(text="")
            return

        saldo = preco - entrada
        if saldo < Decimal("0"):
            self._preview_lbl.configure(
                text="⚠ Entrada maior que o valor total.",
                text_color="#E05C5C")
            return

        val_p     = round(saldo / parcelas, 2)
        val_ult   = round(saldo - val_p * (parcelas - 1), 2)
        base_txt  = f"{parcelas}× de {_fmt_brl(float(val_p))}"

        if parcelas > 1 and val_ult != val_p:
            txt = f"{base_txt}   (última: {_fmt_brl(float(val_ult))})"
        else:
            txt = base_txt

        self._preview_lbl.configure(text=txt, text_color=TEXT_SUB)

    def get_draft(self) -> PagamentoDraft:
        """Retorna um PagamentoDraft tipado."""
        preco = _parse_decimal(self.preco_entry.get())
        tipo  = self.tipo_var.get()

        if tipo == "parcelado":
            entrada = _parse_decimal(self._par_entries["entrada"].get())
            try:
                parcelas  = int(self._par_entries["parcelas"].get())
            except ValueError:
                parcelas  = 1
            try:
                intervalo = int(self._par_entries["intervalo"].get())
            except ValueError:
                intervalo = 30
        else:
            entrada   = Decimal("0")
            parcelas  = 1
            intervalo = 30

        return PagamentoDraft(
            tipo=tipo, preco=preco,
            entrada=entrada, parcelas=parcelas, intervalo=intervalo,
        )

    def validate(self) -> bool:
        ok = _parse_decimal(self.preco_entry.get()) > Decimal("0")
        self.preco_entry.configure(border_color=BORDER if ok else "#E05C5C")
        if ok and self.tipo_var.get() == "parcelado":
            # Valida que entrada não excede o preço
            preco   = _parse_decimal(self.preco_entry.get())
            entrada = _parse_decimal(self._par_entries["entrada"].get())
            if entrada > preco:
                self._par_entries["entrada"].configure(border_color="#E05C5C")
                return False
            self._par_entries["entrada"].configure(border_color=BORDER)
        return ok

    def update_preco_sugerido(self, preco: Decimal):
        """Chamado quando o carrinho muda; atualiza o preço sugerido."""
        self.preco_sugerido = preco
        self._sug_lbl.configure(
            text=_fmt_brl(float(preco)) if preco else "—")
        if preco and not self.preco_entry.get().strip():
            self.preco_entry.delete(0, "end")
            self.preco_entry.insert(0, f"{preco:.2f}")
            self._on_change()


# ── Step 4: Confirmação ───────────────────────────────────────────────────────

class _Step4Confirmar(ctk.CTkScrollableFrame):

    def __init__(self, master, draft: VendaDraft):
        super().__init__(master, fg_color="transparent",
                         scrollbar_button_color=BORDER)
        self.draft = draft
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        make_label(self, "Revise antes de finalizar",
                   font_size=16, weight="bold", anchor="w",
                   row=0, column=0, sticky="w", pady=(0, 16))

        pg    = self.draft.pagamento
        preco = pg.preco
        saldo = preco - pg.entrada
        val_p = (saldo / pg.parcelas) if pg.parcelas else Decimal("0")
        val_u = round(saldo - val_p * (pg.parcelas - 1), 2) if pg.parcelas > 1 else val_p

        pag_rows = [
            ("Valor total", _fmt_brl(float(preco))),
            ("Tipo",        "À Vista" if pg.tipo == "avista" else "Parcelado"),
        ]
        if pg.tipo == "parcelado":
            pag_rows += [
                ("Entrada",  _fmt_brl(float(pg.entrada))),
                ("Parcelas", f"{pg.parcelas}× de {_fmt_brl(float(val_p))}"),
            ]
            if pg.parcelas > 1 and val_u != val_p:
                pag_rows.append(("Última parcela", _fmt_brl(float(val_u))))

        c = self.draft.cliente

        # Constrói seção das máquinas
        maquinas = self.draft.maquinas
        n        = len(maquinas)
        maq_rows = []
        for i, m in enumerate(maquinas):
            pfx = f"#{i + 1} " if n > 1 else ""
            maq_rows.append((f"{pfx}Máquina",  f"{m.marca} {m.modelo}"))
            maq_rows.append((f"{pfx}Série",    m.numero_serie))
            maq_rows.append((f"{pfx}Mesa",     m.mesa))
            if m.preco_venda_sugerido and n > 1:
                maq_rows.append((f"{pfx}P. sugerido",
                                 _fmt_brl(float(m.preco_venda_sugerido))))

        titulo_maq = "Máquinas" if n > 1 else "Máquina"

        sections = [
            ("Cliente", [
                ("Nome",      c.nome      if c else "—"),
                ("Documento", c.documento if c else "—"),
                ("Telefone",  c.telefone  if c else "—"),
            ]),
            (titulo_maq, maq_rows or [("Máquina", "—")]),
            ("Pagamento", pag_rows),
        ]

        for s_idx, (title, rows) in enumerate(sections):
            card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=10,
                                border_width=1, border_color=BORDER)
            card.grid(row=s_idx + 1, column=0, sticky="ew", pady=(0, 12))
            card.grid_columnconfigure(1, weight=1)

            make_label(card, title, font_size=11, weight="bold", color=TEXT_SUB,
                       anchor="w", row=0, column=0, columnspan=2,
                       sticky="w", padx=16, pady=(12, 6))
            ctk.CTkFrame(card, height=1, fg_color=BORDER).grid(
                row=1, column=0, columnspan=2, sticky="ew", padx=12)

            for i, (k, v) in enumerate(rows):
                last = i == len(rows) - 1
                py   = (6, 12 if last else 2)
                make_label(card, k, font_size=12, color=TEXT_SUB, anchor="w",
                           row=i + 2, column=0, sticky="w", padx=16, pady=py)
                make_label(card, str(v), font_size=13, weight="bold", anchor="e",
                           row=i + 2, column=1, sticky="e", padx=16, pady=py)


# ── View principal ────────────────────────────────────────────────────────────

class NovaVendaView(ctk.CTkFrame):
    """
    View de criação de venda em 4 passos.

    Atalhos de teclado:
        Enter    → próximo passo (ou finalizar)
        Esc      → passo anterior
        Ctrl+F   → foca campo de busca (steps 1 e 2)
    """

    def __init__(self, master, session=None):
        super().__init__(master, fg_color=BG, corner_radius=0)

        self._controller: VendaController | None = (
            VendaController(session) if session else None
        )
        self._draft       = VendaDraft()
        self._step        = 0
        self._step_views: dict[int, ctk.CTkFrame] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_stepper()
        self._build_content()
        self._build_footer()
        self._build_resumo()
        self._show_step(0)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_header(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=28, pady=(28, 0))
        ctk.CTkLabel(top, text="Nova Venda",
                     font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
                     text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkLabel(top, text="registro de venda",
                     font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
                     ).pack(side="left", padx=(10, 0), pady=(8, 0))

    def _build_stepper(self):
        self.stepper = _Stepper(self, STEPS)
        self.stepper.grid(row=1, column=0, sticky="ew", padx=28, pady=(16, 0))

    def _build_content(self):
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=2, column=0, sticky="nsew", padx=28, pady=12)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def _build_footer(self):
        foot = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=60)
        foot.grid(row=3, column=0, columnspan=2, sticky="ew")
        foot.grid_propagate(False)
        foot.grid_columnconfigure(1, weight=1)

        self.btn_back = ctk.CTkButton(
            foot, text="← Voltar", width=110, height=36,
            fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
            corner_radius=8, font=ctk.CTkFont(size=13),
            command=self._prev,
        )
        self.btn_back.grid(row=0, column=0, padx=(24, 0), pady=12)

        self._step_label = ctk.CTkLabel(foot, text="",
                                        font=ctk.CTkFont(size=12),
                                        text_color=TEXT_SUB)
        self._step_label.grid(row=0, column=1)

        self.btn_next = ctk.CTkButton(
            foot, text="Próximo →", width=130, height=36,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFFFFF",
            corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._next,
        )
        self.btn_next.grid(row=0, column=2, padx=(0, 24), pady=12)

    def _build_resumo(self):
        self.resumo = _ResumoPanel(self)
        self.resumo.grid(row=1, column=1, rowspan=2, sticky="ns",
                         padx=(0, 28), pady=(16, 12))

    def _focus_search(self):
        view = self._step_views.get(self._step)
        if hasattr(view, "focus_search"):
            view.focus_search()

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _show_step(self, idx: int):
        for w in self.content.winfo_children():
            w.grid_remove()

        self._step = idx
        self.stepper.set_step(idx, completed_up_to=idx)
        self._step_label.configure(text=f"Passo {idx + 1} de {len(STEPS)}")

        self.btn_back.configure(
            state="normal" if idx > 0 else "disabled",
            fg_color=BORDER if idx > 0 else "#E5E7EB",
            text_color=TEXT_MAIN if idx > 0 else TEXT_SUB,
        )

        is_last = idx == len(STEPS) - 1
        self.btn_next.configure(
            text="✓  Finalizar Venda" if is_last else "Próximo →",
            fg_color=SUCCESS if is_last else ACCENT,
            hover_color="#047857" if is_last else ACCENT_HOVER,
        )

        if idx not in self._step_views:
            self._step_views[idx] = self._create_step(idx)

        self._step_views[idx].grid(row=0, column=0, sticky="nsew")

    def _create_step(self, idx: int) -> ctk.CTkFrame:
        if idx == 0:
            return _Step1Cliente(self.content, self._controller,
                                 self._on_data_change)
        elif idx == 1:
            return _Step2Maquina(self.content, self._controller,
                                 self._on_data_change)
        elif idx == 2:
            preco = self._draft.preco_total_sugerido()
            return _Step3Pagamento(self.content, self._on_data_change, preco)
        else:
            return _Step4Confirmar(self.content, self._draft)

    def _on_data_change(self, key: str, value):
        """
        Atualiza o VendaDraft tipado.
        key ∈ {"cliente", "maquinas", "pagamento"}
        """
        if key == "cliente" and isinstance(value, ClienteDraft):
            self._draft.cliente = value

        elif key == "maquinas" and isinstance(value, list):
            self._draft.maquinas = value
            # Propaga soma dos preços sugeridos ao step3 se já criado
            total_sug = self._draft.preco_total_sugerido()
            if 2 in self._step_views:
                self._step_views[2].update_preco_sugerido(total_sug)

        elif key == "pagamento" and isinstance(value, PagamentoDraft):
            self._draft.pagamento = value

        self.resumo.update_from_draft(self._draft)

    def _prev(self):
        if self._step > 0:
            self._show_step(self._step - 1)

    def _next(self):
        view = self._step_views.get(self._step)
        if hasattr(view, "validate") and not view.validate():
            return

        if self._step < len(STEPS) - 1:
            # Recria step3 (Pagamento) quando saindo do step1 (Máquinas)
            # para que o preço sugerido reflita o carrinho atual
            if self._step == 1 and 2 in self._step_views:
                self._step_views.pop(2).destroy()
            self._show_step(self._step + 1)
        else:
            self._finalizar()

    def _validar_draft(self):
        """
        Valida o draft completo antes de finalizar.
        Lança ValueError com mensagem descritiva se algo estiver faltando.
        Protege contra inconsistências causadas por retorno de steps.
        """
        if not self._draft.cliente:
            raise ValueError("Cliente não selecionado.")
        if not self._draft.maquinas:
            raise ValueError("Nenhuma máquina selecionada.")
        pg = self._draft.pagamento
        if pg.preco <= Decimal("0"):
            raise ValueError("Preço inválido.")
        if pg.tipo == "parcelado":
            if pg.parcelas < 1:
                raise ValueError("Número de parcelas inválido.")
            if pg.entrada < Decimal("0") or pg.entrada > pg.preco:
                raise ValueError(
                    f"Valor de entrada ({_fmt_brl(float(pg.entrada))}) "
                    f"inválido para o total ({_fmt_brl(float(pg.preco))})."
                )

    def _finalizar(self):
        if not self._controller:
            self._sucesso()
            return

        try:
            self._validar_draft()
            self._controller.finalizar_venda(self._draft)
            self._sucesso()
        except Exception as e:
            self._erro(str(e))

    # ── Feedback ──────────────────────────────────────────────────────────────

    def _sucesso(self):
        for w in self.content.winfo_children():
            w.destroy()

        n_maq = len(self._draft.maquinas)
        sub   = (
            f"{n_maq} máquinas"
            if n_maq > 1
            else (
                f"{self._draft.maquinas[0].marca} {self._draft.maquinas[0].modelo}"
                if n_maq == 1 else "—"
            )
        )

        f = ctk.CTkFrame(self.content, fg_color=CARD_BG, corner_radius=12,
                         border_width=1, border_color=BORDER)
        f.grid(row=0, column=0, sticky="nsew", pady=40, padx=40)
        f.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(f, text="✓", font=ctk.CTkFont(size=48),
                     text_color=SUCCESS).grid(row=0, column=0, pady=(40, 8))
        ctk.CTkLabel(f, text="Venda registrada com sucesso!",
                     font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
                     text_color=TEXT_MAIN).grid(row=1, column=0)
        ctk.CTkLabel(
            f,
            text=f"Cliente: {self._draft.cliente.nome if self._draft.cliente else '—'}",
            font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
        ).grid(row=2, column=0, pady=(4, 0))
        ctk.CTkLabel(
            f, text=sub,
            font=ctk.CTkFont(size=12), text_color=TEXT_SUB,
        ).grid(row=3, column=0, pady=(2, 0))
        ctk.CTkButton(f, text="Nova Venda", width=140, height=36,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFF",
                      corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._resetar,
                      ).grid(row=4, column=0, pady=(24, 40))

        self.stepper.set_step(len(STEPS) - 1, completed_up_to=len(STEPS))
        self.btn_next.configure(state="disabled")
        self.btn_back.configure(state="disabled")

    def _erro(self, msg: str):
        # Remove erros anteriores
        for w in self.content.winfo_children():
            if getattr(w, "_is_erro_lbl", False):
                w.destroy()
        lbl = ctk.CTkLabel(self.content, text=f"⚠  {msg}",
                           font=ctk.CTkFont(size=13), text_color="#E05C5C",
                           wraplength=500, anchor="w")
        lbl._is_erro_lbl = True
        lbl.grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _resetar(self):
        self._draft.reset()
        for v in self._step_views.values():
            v.destroy()
        self._step_views = {}
        self.resumo.update_from_draft(self._draft)
        self._show_step(0)
        self.btn_next.configure(state="normal")
        self.btn_back.configure(state="normal")