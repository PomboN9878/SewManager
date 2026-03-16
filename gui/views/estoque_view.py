"""
gui/views/estoque_view.py
Usa:  CTkTable      (pip install CTkTable)    — tabelas
      CTkMessagebox (pip install CTkMessagebox) — alertas de erro/sucesso
"""

import customtkinter as ctk
from CTkTable import CTkTable
from CTkMessagebox import CTkMessagebox

from services.estoque_service import (
    listar_maquinas, listar_mesas, adicionar_mesa,
    adicionar_maquina, atualizar_maquina, atualizar_mesa
)
from gui.components import MaquinaFormModal, MesaFormModal
from gui.components.base_modal import (
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER,
    HEADER_BG, ROW_ALT, ROW_HOVER,
    fmt_brl as _fmt_brl,
)


# ── Helpers de feedback ───────────────────────────────────────────────────────

def _erro(title: str, message: str):
    """Exibe um CTkMessagebox de erro."""
    CTkMessagebox(title=title, message=message, icon="cancel")


def _sucesso(title: str, message: str):
    """Exibe um CTkMessagebox de sucesso."""
    CTkMessagebox(title=title, message=message, icon="check")


# Status: (texto na célula, cor do texto)
STATUS_CFG = {
    "EM_ESTOQUE": ("● Disponível", "#059669"),
    "VENDIDO":    ("● Vendido",    "#DC2626"),
    "RESERVADO":  ("● Reservado",  "#D97706"),
}


# ── Barra de filtros ──────────────────────────────────────────────────────────

class _FilterBar(ctk.CTkFrame):
    """Botões de filtro + busca + contador + botão de ação principal."""

    def __init__(self, master, filters: list, placeholder: str,
                 action_label: str, on_filter, on_search, on_action):
        super().__init__(master, fg_color="transparent")
        self._btns: dict[str, ctk.CTkButton] = {}

        for idx, (key, label) in enumerate(filters):
            btn = ctk.CTkButton(
                self, text=label, width=110, height=32,
                fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
                corner_radius=8, font=ctk.CTkFont(size=12),
                command=lambda k=key: on_filter(k),
            )
            btn.grid(row=0, column=idx, padx=(0, 6))
            self._btns[key] = btn

        sc = len(filters)
        self.grid_columnconfigure(sc, weight=1)

        self._search = ctk.CTkEntry(
            self, height=32, placeholder_text=placeholder,
            corner_radius=8, fg_color=CARD_BG, border_color=BORDER,
            border_width=1, text_color=TEXT_MAIN, font=ctk.CTkFont(size=12),
        )
        self._search.grid(row=0, column=sc, sticky="ew", padx=(0, 12))
        self._search.bind("<KeyRelease>", lambda e: on_search())

        self._count = ctk.CTkLabel(self, text="",
                                   font=ctk.CTkFont(size=12), text_color=TEXT_SUB)
        self._count.grid(row=0, column=sc + 1, padx=(0, 12))

        ctk.CTkButton(
            self, text=action_label, width=145, height=32,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFF",
            corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
            command=on_action,
        ).grid(row=0, column=sc + 2)

    def set_active(self, key: str):
        for k, btn in self._btns.items():
            a = k == key
            btn.configure(
                fg_color=ACCENT if a else BORDER,
                hover_color=ACCENT_HOVER if a else "#DDDFE8",
                text_color="#FFF" if a else TEXT_MAIN,
                font=ctk.CTkFont(size=12, weight="bold" if a else "normal"),
            )

    def get_search(self) -> str:
        return self._search.get().lower().strip()

    def set_count(self, text: str):
        self._count.configure(text=text)


# ── Tabela base com CTkTable ──────────────────────────────────────────────────

class _TableView(ctk.CTkFrame):
    HEADERS: list[str] = []
    STATUS_COL: int = -1

    def __init__(self, master, session, filter_defs, placeholder,
                 action_label):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.session     = session
        self._filtro     = filter_defs[0][0]
        self._all_data:  list[dict] = []
        self._cur_data:  list[dict] = []
        self._table: CTkTable | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.bar = _FilterBar(
            self, filters=filter_defs,
            placeholder=placeholder,
            action_label=action_label,
            on_filter=self._set_filtro,
            on_search=lambda: self._render(self._filtered()),
            on_action=self._open_new,
        )
        self.bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.bar.set_active(self._filtro)

        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(card, fg_color=CARD_BG,
                                              scrollbar_button_color=BORDER,
                                              corner_radius=0)
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._load()

    def _load(self):
        self._all_data = self._fetch_data()
        self._render(self._filtered())

    def _fetch_data(self) -> list[dict]:
        return []

    def _filtered(self) -> list[dict]:
        return self._all_data

    def _set_filtro(self, filtro: str):
        self._filtro = filtro
        self.bar.set_active(filtro)
        self._render(self._filtered())

    def _render(self, dados: list[dict]):
        self._cur_data = dados
        self.bar.set_count(self._count_label(len(dados)))

        if self._table:
            self._table.destroy()
            self._table = None
        for w in self._scroll.winfo_children():
            w.destroy()

        if not dados:
            ctk.CTkLabel(self._scroll,
                         text="Nenhum item encontrado.",
                         font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
                         ).pack(pady=48)
            return

        values = [self.HEADERS] + [self._to_row(m) for m in dados]

        self._table = CTkTable(
            self._scroll,
            values=values,
            header_color=HEADER_BG,
            colors=[CARD_BG, ROW_ALT],
            text_color=TEXT_MAIN,
            hover=True,
            hover_color=ROW_HOVER,
            height=44,
            font=ctk.CTkFont(size=13),
            padx=1, pady=1,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            command=self._on_cell_click,
            anchor="w",
        )
        self._table.pack(fill="both", expand=True, padx=4, pady=4)

        self._table.edit_row(
            0,
            text_color=TEXT_SUB,
            fg_color=HEADER_BG,
            hover_color=HEADER_BG,
            hover=False,
            font=ctk.CTkFont(size=11, weight="bold"),
            height=38,
        )

        if self.STATUS_COL >= 0:
            for i, m in enumerate(dados):
                status = m.get("status", "")
                label, color = STATUS_CFG.get(status, (status, TEXT_SUB))
                self._table.frame[i + 1, self.STATUS_COL].configure(
                    text_color=color,
                    font=ctk.CTkFont(size=12, weight="bold"),
                )

    def _on_cell_click(self, cell: dict):
        row = cell["row"]
        if row == 0:
            return
        idx = row - 1
        if idx < len(self._cur_data):
            self._open_edit(self._cur_data[idx])

    def _to_row(self, m: dict) -> list:
        raise NotImplementedError

    def _count_label(self, n: int) -> str:
        return f"{n} item{'s' if n != 1 else ''}"

    def _open_new(self):
        raise NotImplementedError

    def _open_edit(self, item: dict):
        raise NotImplementedError


# ── helpers internos ─────────────────────────────────────────────────────────

def _status_str(status) -> str:
    """Normaliza status Enum ou string para string pura."""
    return status.value if hasattr(status, "value") else str(status)


# ── Aba Máquinas ──────────────────────────────────────────────────────────────

class _TabMaquinas(_TableView):

    HEADERS    = ["ID", "Marca", "Modelo", "Série", "Mesa", "P. Venda", "Status"]
    STATUS_COL = 6

    def __init__(self, master, session=None):
        super().__init__(
            master, session,
            filter_defs=[
                ("todas",       "Todas"),
                ("disponiveis", "Disponíveis"),
                ("vendidas",    "Vendidas"),
                ("reservadas",  "Reservadas"),
            ],
            placeholder="Buscar marca, modelo ou série...",
            action_label="＋  Nova Máquina",
        )

    # ── Dados ──────────────────────────────────────────────────────────────

    def _fetch_data(self) -> list[dict]:
        try:
            return [
                {
                    "id":                   m.id,
                    "marca":                m.marca,
                    "modelo":               m.modelo,
                    "numero_serie":         m.numero_serie or "—",
                    "mesa":                 m.mesa.modelo if m.mesa else "—",
                    "mesa_id":              m.mesa_id,
                    "preco_venda_sugerido": m.preco_venda_sugerido,
                    "status":               _status_str(m.status),
                    "cor":                  m.cor or "",
                    "preco_custo":          m.preco_custo,
                    "observacoes":          m.observacoes or "",
                }
                for m in listar_maquinas(self.session)
            ]
        except Exception as e:
            _erro("Erro ao carregar máquinas", str(e))
            return []

    def _filtered(self) -> list[dict]:
        dados = self._all_data
        if self._filtro == "disponiveis":
            dados = [m for m in dados if m["status"] == "EM_ESTOQUE"]
        elif self._filtro == "vendidas":
            dados = [m for m in dados if m["status"] == "VENDIDO"]
        elif self._filtro == "reservadas":
            dados = [m for m in dados if m["status"] == "RESERVADO"]
        termo = self.bar.get_search()
        if termo:
            dados = [m for m in dados if
                     termo in m["marca"].lower()
                     or termo in m["modelo"].lower()
                     or termo in str(m["numero_serie"]).lower()]
        return dados

    def _to_row(self, m: dict) -> list:
        status_label, _ = STATUS_CFG.get(m["status"], (m["status"], TEXT_SUB))
        return [
            f"#{m['id']}",
            m["marca"],
            m["modelo"],
            m["numero_serie"],
            m["mesa"],
            _fmt_brl(m.get("preco_venda_sugerido")),
            status_label,
        ]

    def _count_label(self, n: int) -> str:
        return f"{n} máquina{'s' if n != 1 else ''}"

    # ── CRUD ───────────────────────────────────────────────────────────────

    def _open_new(self):
        MaquinaFormModal(
            self,
            mesas_disponiveis=self._mesas_disponiveis(),
            on_save=self._salvar_novo,
        )

    def _open_edit(self, m: dict):
        MaquinaFormModal(
            self,
            # Passa a mesa já vinculada para que apareça no dropdown
            # mesmo não estando "disponível" (já está ocupada por esta máquina)
            mesas_disponiveis=self._mesas_disponiveis(mesa_id_atual=m.get("mesa_id")),
            on_save=lambda d: self._salvar_edicao(m["id"], d),
            maquina=m,
        )

    def _mesas_disponiveis(self, mesa_id_atual: int | None = None) -> list:
        """
        Retorna mesas sem vínculo com nenhuma máquina (status EM_ESTOQUE +
        sem backref de máquina apontando para elas).

        Quando editando, inclui a mesa já vinculada à máquina atual
        no topo da lista para que ela apareça pré-selecionada no dropdown.
        """
        try:
            from database.models.mesa import Mesa

            # Mesas livres: EM_ESTOQUE E sem nenhuma máquina vinculada
            mesas = [
                {"id": m.id, "modelo": m.modelo, "material": m.material}
                for m in listar_mesas(
                    self.session,
                    apenas_disponiveis=True,
                    apenas_sem_vinculo=True,
                )
            ]

            # Edição: injeta a mesa atual no topo se ela não está na lista
            if mesa_id_atual and not any(m["id"] == mesa_id_atual for m in mesas):
                mesa_atual = self.session.get(Mesa, mesa_id_atual)
                if mesa_atual:
                    mesas.insert(0, {
                        "id":       mesa_atual.id,
                        "modelo":   mesa_atual.modelo,
                        "material": mesa_atual.material,
                    })

            return mesas
        except Exception as e:
            _erro("Erro ao listar mesas disponíveis", str(e))
            return []

    def _salvar_novo(self, data: dict):
        if not self.session:
            self._load()
            return
        try:
            adicionar_maquina(
                self.session,
                marca=data["marca"],
                modelo=data["modelo"],
                mesa_id=data["mesa_id"],
                numero_serie=data["numero_serie"] or None,
                cor=data["cor"] or None,
                preco_custo=data["preco_custo"],
                preco_venda_sugerido=data["preco_venda_sugerido"],
                observacoes=data["observacoes"] or None,
            )
            self.session.commit()
            _sucesso("Máquina cadastrada", "Máquina adicionada ao estoque com sucesso.")
        except ValueError as e:
            # Erro de negócio (ex: número de série duplicado, mesa indisponível)
            self.session.rollback()
            _erro("Não foi possível salvar", str(e))
        except Exception as e:
            self.session.rollback()
            _erro("Erro inesperado", f"Ocorreu um erro ao salvar a máquina:\n{e}")
        self._load()

    def _salvar_edicao(self, maquina_id: int, data: dict):
        if not self.session:
            self._load()
            return
        try:
            atualizar_maquina(
                self.session,
                maquina_id,
                marca=data["marca"],
                modelo=data["modelo"],
                numero_serie=data["numero_serie"] or None,
                cor=data["cor"] or None,
                preco_custo=data["preco_custo"],
                preco_venda_sugerido=data["preco_venda_sugerido"],
                observacoes=data["observacoes"] or None,
            )
            self.session.commit()
            _sucesso("Máquina atualizada", "Os dados foram salvos com sucesso.")
        except ValueError as e:
            self.session.rollback()
            _erro("Não foi possível salvar", str(e))
        except Exception as e:
            self.session.rollback()
            _erro("Erro inesperado", f"Ocorreu um erro ao editar a máquina:\n{e}")
        self._load()


# ── Aba Mesas ─────────────────────────────────────────────────────────────────

class _TabMesas(_TableView):

    HEADERS    = ["ID", "Modelo", "Material", "Cor", "Máquina vinculada", "Status"]
    STATUS_COL = 5

    def __init__(self, master, session=None):
        super().__init__(
            master, session,
            filter_defs=[
                ("todas",       "Todas"),
                ("disponiveis", "Disponíveis"),
                ("vendidas",    "Vendidas"),
            ],
            placeholder="Buscar modelo ou material...",
            action_label="＋  Nova Mesa",
        )

    # ── Dados ──────────────────────────────────────────────────────────────

    def _fetch_data(self) -> list[dict]:
        try:
            return [
                {
                    "id":        m.id,
                    "modelo":    m.modelo,
                    "material":  m.material or "—",
                    "cor":       m.cor or "—",
                    # Acessa a máquina via relacionamento inverso (se existir)
                    "maquina":   (
                        f"{m.maquina.marca} {m.maquina.modelo}"
                        if m.maquina else "—"
                    ),
                    "status":      _status_str(m.status),
                    "observacoes": m.observacoes or "",
                }
                for m in listar_mesas(self.session)
            ]
        except Exception as e:
            _erro("Erro ao carregar mesas", str(e))
            return []

    def _filtered(self) -> list[dict]:
        dados = self._all_data
        if self._filtro == "disponiveis":
            dados = [m for m in dados if m["status"] == "EM_ESTOQUE"]
        elif self._filtro == "vendidas":
            dados = [m for m in dados if m["status"] == "VENDIDO"]
        termo = self.bar.get_search()
        if termo:
            dados = [m for m in dados if
                     termo in m["modelo"].lower()
                     or termo in m["material"].lower()]
        return dados

    def _to_row(self, m: dict) -> list:
        status_label, _ = STATUS_CFG.get(m["status"], (m["status"], TEXT_SUB))
        return [
            f"#{m['id']}",
            m["modelo"],
            m["material"],
            m["cor"],
            m["maquina"],
            status_label,
        ]

    def _count_label(self, n: int) -> str:
        return f"{n} mesa{'s' if n != 1 else ''}"

    # ── CRUD ───────────────────────────────────────────────────────────────

    def _open_new(self):
        MesaFormModal(self, on_save=self._salvar_nova)

    def _open_edit(self, m: dict):
        MesaFormModal(
            self,
            on_save=lambda d: self._salvar_edicao(m["id"], d),
            mesa=m,
        )

    def _salvar_nova(self, data: dict):
        if not self.session:
            self._load()
            return
        try:
            adicionar_mesa(
                self.session,
                modelo=data["modelo"],
                material=data["material"] or None,
                cor=data["cor"] or None,
                observacoes=data["observacoes"] or None,
            )
            self.session.commit()
            _sucesso("Mesa cadastrada", "Mesa adicionada ao estoque com sucesso.")
        except ValueError as e:
            self.session.rollback()
            _erro("Não foi possível salvar", str(e))
        except Exception as e:
            self.session.rollback()
            _erro("Erro inesperado", f"Ocorreu um erro ao salvar a mesa:\n{e}")
        self._load()

    def _salvar_edicao(self, mesa_id: int, data: dict):
        if not self.session:
            self._load()
            return
        try:
            atualizar_mesa(
                self.session,
                mesa_id,
                modelo=data["modelo"],
                material=data["material"] or None,
                cor=data["cor"] or None,
                observacoes=data["observacoes"] or None,
            )
            self.session.commit()
            _sucesso("Mesa atualizada", "Os dados foram salvos com sucesso.")
        except ValueError as e:
            self.session.rollback()
            _erro("Não foi possível salvar", str(e))
        except Exception as e:
            self.session.rollback()
            _erro("Erro inesperado", f"Ocorreu um erro ao editar a mesa:\n{e}")
        self._load()


# ── View principal ────────────────────────────────────────────────────────────

class EstoqueView(ctk.CTkFrame):
    """
    View principal do módulo Estoque.

    Mudanças em relação à versão anterior:
    - Cabeçalho e tabs na MESMA linha → elimina o espaço morto entre eles
    - Tabs construídas manualmente com CTkSegmentedButton para controle
      total sobre cores, peso da fonte e tamanho — o CTkTabview nativo
      não expõe essas propriedades de forma confiável
    - Texto das tabs em TEXT_MAIN (quase preto) com peso bold quando ativo
    - Conteúdo das abas gerenciado com grid show/hide em vez de destroy/create,
      evitando recriação custosa dos widgets a cada troca de aba
    """

    _ABAS = [("maquinas", "  🔧  Máquinas  "), ("mesas", "  🪑  Mesas  ")]

    def __init__(self, master, session=None):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.session = session
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._aba_ativa = "maquinas"
        self._views: dict[str, ctk.CTkFrame] = {}
        self._build()

    def _build(self):
        # ── Linha de cabeçalho + tabs (tudo na mesma faixa) ───────────────
        #
        #   [ Estoque   máquinas e mesas ]   [ 🔧 Máquinas | 🪑 Mesas ]
        #   ─────────────────────────────────────────────────────────────
        #
        top = ctk.CTkFrame(self, fg_color=CARD_BG,
                           corner_radius=0,
                           border_width=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)   # espaço entre título e tabs

        # Título + subtítulo (lado esquerdo)
        title_block = ctk.CTkFrame(top, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w",
                         padx=(28, 0), pady=(20, 0))

        ctk.CTkLabel(
            title_block,
            text="Estoque",
            font=ctk.CTkFont(family="Georgia", size=24, weight="bold"),
            text_color=TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_block,
            text="máquinas e mesas",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SUB,
        ).grid(row=1, column=0, sticky="w", pady=(1, 0))

        # Tabs customizadas (lado direito, alinhadas ao centro vertical)
        tab_bar = ctk.CTkFrame(top, fg_color=BORDER, corner_radius=10)
        tab_bar.grid(row=0, column=2, rowspan=2, sticky="e",
                     padx=28, pady=16)

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for idx, (key, label) in enumerate(self._ABAS):
            btn = ctk.CTkButton(
                tab_bar,
                text=label,
                width=130, height=34,
                corner_radius=8,
                border_width=0,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda k=key: self._trocar_aba(k),
            )
            btn.grid(row=0, column=idx, padx=3, pady=3)
            self._tab_btns[key] = btn

        # Linha separadora abaixo do cabeçalho
        ctk.CTkFrame(self, height=1, fg_color=BORDER).grid(
            row=0, column=0, sticky="sew"   # cola na borda inferior do row 0
        )

        # ── Container do conteúdo ─────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        # Cria as duas abas mas só mostra a ativa
        for key, cls in [("maquinas", _TabMaquinas), ("mesas", _TabMesas)]:
            v = cls(content, session=self.session)
            v.grid(row=0, column=0, sticky="nsew", padx=28, pady=20)
            self._views[key] = v

        # Aplica estado inicial dos botões e visibilidade
        self._trocar_aba("maquinas")

    # ── Lógica de troca de aba ────────────────────────────────────────────────

    def _trocar_aba(self, key: str):
        self._aba_ativa = key

        for k, btn in self._tab_btns.items():
            ativo = k == key
            btn.configure(
                fg_color=ACCENT        if ativo else "transparent",
                hover_color=ACCENT_HOVER if ativo else "#DDDFE8",
                text_color="#FFFFFF"   if ativo else TEXT_MAIN,
            )

        for k, view in self._views.items():
            if k == key:
                view.grid()        # torna visível
            else:
                view.grid_remove() # esconde sem destruir