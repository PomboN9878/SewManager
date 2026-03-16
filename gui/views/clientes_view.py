"""
gui/views/clientes_view.py
Usa CTkTable (pip install CTkTable) para a tabela principal e o histórico.
"""

import customtkinter as ctk
from CTkTable import CTkTable

from gui.components import ClienteFormModal, HistoricoModal
from gui.components.base_modal import (
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER,
    HEADER_BG, ROW_ALT, ROW_HOVER,
    fmt_brl as _fmt_brl,
    make_label as _label,
)
from services.cliente_service import (
    ClienteNaoEncontrado,
    DocumentoDuplicado,
    atualizar_cliente,
    criar_cliente,
    listar_clientes,
    resumo_cliente,
)
from services.venda_service import listar_vendas

# Cabeçalhos da tabela principal
HEADERS    = ["Nome", "Documento", "Telefone", "Vendas", "Em aberto", "Ações"]
COL_ABERTO = 4   # índice da coluna "Em aberto" (para colorir valores positivos)


# ── View principal ────────────────────────────────────────────────────────────

class ClientesView(ctk.CTkFrame):

    def __init__(self, master, session=None):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.session = session
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._clientes: list[dict] = []
        self._cur_data: list[dict] = []
        self._table:    CTkTable | None = None
        self._build()
        self._load()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Cabeçalho da página
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=28, pady=(28, 0))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top, text="Clientes",
            font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
            text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            top, text="cadastro e histórico de compras",
            font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkButton(
            top, text="＋  Novo Cliente", height=36, width=150,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFF",
            corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            command=self._abrir_novo,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        # Barra de busca
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=28, pady=(18, 10))
        bar.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            bar, height=36,
            placeholder_text="Buscar por nome ou documento...",
            corner_radius=8, fg_color=CARD_BG,
            border_color=BORDER, border_width=1,
            text_color=TEXT_MAIN, font=ctk.CTkFont(size=13),
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        self.count_label = ctk.CTkLabel(
            bar, text="",
            font=ctk.CTkFont(size=12), text_color=TEXT_SUB,
        )
        self.count_label.grid(row=0, column=1, padx=(12, 0))

        # Mensagem de erro inline (DocumentoDuplicado, etc.)
        self._error_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12),
            text_color="#DC2626",
        )
        self._error_label.grid(row=1, column=0, sticky="e", padx=28)

        # Card da tabela
        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 28))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(
            card, fg_color=CARD_BG,
            scrollbar_button_color=BORDER, corner_radius=0,
        )
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self._scroll.grid_columnconfigure(0, weight=1)

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _load(self):
        """Carrega clientes + resumo financeiro de cada um via service."""
        try:
            rows = []
            for c in listar_clientes(self.session):
                r = resumo_cliente(self.session, c.id)
                rows.append({
                    "id":           c.id,
                    "nome":         c.nome,
                    "documento":    c.documento,
                    "telefone":     c.telefone,
                    "observacoes":  c.observacoes,
                    "total_vendas": r["vendas_abertas"] + r["vendas_quitadas"],
                    "em_aberto":    r["total_em_aberto"],
                })
            self._clientes = rows
        except Exception as exc:
            print(f"[ClientesView] Erro ao carregar clientes: {exc}")
            self._clientes = []

        self._render(self._clientes)

    # ── Renderização com CTkTable ─────────────────────────────────────────────

    def _render(self, clientes: list[dict]):
        self._cur_data = clientes
        n = len(clientes)
        self.count_label.configure(text=f"{n} cliente{'s' if n != 1 else ''}")

        # Remove tabela anterior
        if self._table:
            self._table.destroy()
            self._table = None
        for w in self._scroll.winfo_children():
            w.destroy()

        if not clientes:
            _label(self._scroll, "Nenhum cliente encontrado.",
                   font_size=13, color=TEXT_SUB, anchor="center",
                   row=0, column=0, pady=48)
            return

        # Linha 0 = cabeçalho; coluna "Ações" receberá botões depois
        values = [HEADERS] + [
            [
                c.get("nome", "—"),
                c.get("documento") or "—",
                c.get("telefone") or "—",
                str(c.get("total_vendas", 0)),
                _fmt_brl(c["em_aberto"]) if c.get("em_aberto") else "—",
                "",   # placeholder para os botões de ação
            ]
            for c in clientes
        ]

        self._table = CTkTable(
            self._scroll,
            values=values,
            header_color=HEADER_BG,
            colors=[CARD_BG, ROW_ALT],
            text_color=TEXT_MAIN,
            hover=True,
            hover_color=ROW_HOVER,
            height=46,
            font=ctk.CTkFont(size=13),
            padx=1,
            pady=1,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            command=self._on_cell_click,
            anchor="w",
        )
        self._table.pack(fill="both", expand=True, padx=4, pady=4)

        # Estiliza header
        self._table.edit_row(
            0,
            text_color=TEXT_SUB,
            fg_color=HEADER_BG,
            hover_color=HEADER_BG,
            hover=False,
            font=ctk.CTkFont(size=11, weight="bold"),
            height=38,
        )

        # Pós-processamento célula a célula
        COL_ACOES = len(HEADERS) - 1
        for i, c in enumerate(clientes):
            row_idx = i + 1     # +1 pelo header

            # Destaca saldo devedor
            if c.get("em_aberto", 0) > 0:
                self._table.frame[row_idx, COL_ABERTO].configure(
                    text_color="#D97706",
                    font=ctk.CTkFont(size=13, weight="bold"),
                )

            # Injeta botões na célula de ações
            cell = self._table.frame[row_idx, COL_ACOES]
            cell.configure(text="", hover=False)

            btn_frame = ctk.CTkFrame(cell, fg_color="transparent")
            btn_frame.place(relx=0.5, rely=0.5, anchor="center")

            ctk.CTkButton(
                btn_frame, text="Editar", width=60, height=28,
                fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
                corner_radius=6, font=ctk.CTkFont(size=11),
                command=lambda cl=c: self._abrir_editar(cl),
            ).pack(side="left", padx=(0, 4))

            ctk.CTkButton(
                btn_frame, text="Histórico", width=78, height=28,
                fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFF",
                corner_radius=6, font=ctk.CTkFont(size=11),
                command=lambda cl=c: self._abrir_historico(cl),
            ).pack(side="left")

    # ── Clique em célula ──────────────────────────────────────────────────────

    def _on_cell_click(self, cell: dict):
        """Clique fora da coluna de ações abre o histórico diretamente."""
        row, col = cell["row"], cell["column"]
        if row == 0 or col == len(HEADERS) - 1:
            return
        idx = row - 1
        if idx < len(self._cur_data):
            self._abrir_historico(self._cur_data[idx])

    # ── Busca ─────────────────────────────────────────────────────────────────

    def _on_search(self, _event=None):
        termo = self.search_entry.get().lower().strip()
        filtrados = self._clientes if not termo else [
            c for c in self._clientes
            if termo in c["nome"].lower()
            or termo in (c["documento"] or "").lower()
        ]
        self._render(filtrados)

    # ── Feedback de erro inline ───────────────────────────────────────────────

    def _show_error(self, msg: str):
        self._error_label.configure(text=msg)
        self.after(4000, lambda: self._error_label.configure(text=""))

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _abrir_novo(self):
        ClienteFormModal(self, on_save=self._salvar_novo)

    def _abrir_editar(self, cliente: dict):
        ClienteFormModal(
            self,
            on_save=lambda d: self._salvar_edicao(cliente["id"], d),
            cliente=cliente,
        )

    def _abrir_historico(self, cliente: dict):
        HistoricoModal(
            self,
            cliente_nome=cliente["nome"],
            vendas=self._buscar_vendas(cliente["id"]),
        )

    def _salvar_novo(self, data: dict):
        if not self.session:
            return
        try:
            criar_cliente(
                self.session,
                nome=data["nome"],
                documento=data["documento"] or None,
                telefone=data["telefone"] or None,
                observacoes=data["obs"] or None,
            )
            self.session.commit()
        except DocumentoDuplicado as exc:
            self.session.rollback()
            self._show_error(str(exc))
            return
        except Exception as exc:
            self.session.rollback()
            print(f"[ClientesView] Erro ao criar cliente: {exc}")
            return
        self._load()

    def _salvar_edicao(self, cliente_id: int, data: dict):
        if not self.session:
            return
        try:
            atualizar_cliente(
                self.session,
                cliente_id,
                nome=data["nome"],
                documento=data["documento"] or None,
                telefone=data["telefone"] or None,
                observacoes=data["obs"] or None,
            )
            self.session.commit()
        except (ClienteNaoEncontrado, DocumentoDuplicado) as exc:
            self.session.rollback()
            self._show_error(str(exc))
            return
        except Exception as exc:
            self.session.rollback()
            print(f"[ClientesView] Erro ao editar cliente: {exc}")
            return
        self._load()

    def _buscar_vendas(self, cliente_id: int) -> list[dict]:
        try:
            result = []
            for v in listar_vendas(self.session, cliente_id=cliente_id):
                maquinas = ", ".join(
                    f"{iv.maquina.marca} {iv.maquina.modelo}"
                    for iv in v.itens if iv.maquina
                )
                result.append({
                    "data":        v.data.strftime("%d/%m/%Y") if v.data else "—",
                    "maquina":     maquinas or "—",
                    "valor_total": v.valor_total,
                    "total_pago":  v.total_pago,
                    "status":      v.status,
                })
            return result
        except Exception as exc:
            print(f"[ClientesView] Erro ao buscar vendas do cliente {cliente_id}: {exc}")
            return []