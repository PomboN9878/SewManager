"""
gui/views/dashboard_view.py

Visão geral do sistema.

IMPLEMENTAÇÕES:
- Dados reais via estoque_service, cliente_service, pagamento_service, venda_service
- Tabela de atividade recente (últimas vendas)
- Tabela de parcelas com vencimento próximo

CORREÇÕES:
- StatCard.value_label: referência direta — sem busca por row
- Cards indexados por chave estável — mudar texto de UI não quebra o refresh
- Loading state: cards mostram "..." enquanto carregam, erro exibe banner
- Scrollbar visível (#D8DBE5)
- Sentence case no subtítulo
"""
from __future__ import annotations

from datetime import datetime, timedelta

import customtkinter as ctk

from gui.components.base_modal import fmt_brl as _fmt_brl

# ── Paleta ────────────────────────────────────────────────────────────────────
BG        = "#F4F5F8"
CARD_BG   = "#FFFFFF"
ACCENT    = "#4F6AF0"
TEXT_MAIN = "#1C1F2E"
TEXT_SUB  = "#8B90A8"
BORDER    = "#ECEEF4"

_VERDE    = "#059669"
_AMARELO  = "#D97706"
_VERMELHO = "#DC2626"

# ── Definição dos cards (chave estável, ícone, label de UI, cor, tint) ────────
_CARD_DEFS = [
    ("maquinas", "▣", "Máquinas em estoque", "#4F6AF0", "#EEF1FD"),
    ("mesas",    "◫", "Mesas disponíveis",   "#22C993", "#E6FAF4"),
    ("clientes", "◎", "Clientes ativos",     "#F0934F", "#FDF0E8"),
    ("atrasos",  "◈", "Parcelas em atraso",  "#E05C5C", "#FAEAEA"),
]


# ── Componentes reutilizáveis ─────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    """Card de métrica: ícone + valor + label."""

    def __init__(self, master, icon: str, label: str, value: str,
                 accent_color: str = ACCENT, tint_color: str = "#EEF1FD"):
        super().__init__(master, corner_radius=12, fg_color=CARD_BG,
                         border_width=1, border_color=BORDER)
        self.grid_columnconfigure(0, weight=1)

        pill = ctk.CTkFrame(self, fg_color=tint_color, corner_radius=8,
                            width=40, height=40)
        pill.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 6))
        pill.grid_propagate(False)
        ctk.CTkLabel(pill, text=icon, font=ctk.CTkFont(size=18),
                     text_color=accent_color,
                     ).place(relx=0.5, rely=0.5, anchor="center")

        # Referência direta — sem busca por row no refresh
        self.value_label = ctk.CTkLabel(
            self, text=value,
            font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
            text_color=TEXT_MAIN,
        )
        self.value_label.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 2))

        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=12),
                     text_color=TEXT_SUB,
                     ).grid(row=2, column=0, sticky="w", padx=18, pady=(0, 18))

    def set_value(self, value: str) -> None:
        """Atualiza o valor exibido."""
        self.value_label.configure(text=value)


class SectionHeader(ctk.CTkFrame):
    """Cabeçalho de seção: título + linha separadora."""

    def __init__(self, master, title: str):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_SUB,
                     ).grid(row=0, column=0, padx=(0, 12))

        ctk.CTkFrame(self, height=1, fg_color=BORDER,
                     ).grid(row=0, column=1, sticky="ew")


# ── View principal ────────────────────────────────────────────────────────────

class DashboardView(ctk.CTkScrollableFrame):
    """
    Visão geral do sistema.

    `session`: SQLAlchemy Session (None → placeholders vazios).

    Os dados são carregados de forma lazy em `_carregar_dados()`,
    que é chamado após o layout estar montado para não bloquear a UI.
    """

    def __init__(self, master, session=None):
        super().__init__(master, fg_color=BG,
                         scrollbar_button_color="#D8DBE5")   # scrollbar visível
        self.session = session
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._stat_cards:      dict[str, StatCard] = {}
        self._recent_frame:    ctk.CTkFrame | None = None
        self._due_frame:       ctk.CTkFrame | None = None
        self._error_banner:    ctk.CTkLabel | None = None

        self._build()

        # Carrega dados após render (evita travar a inicialização da janela)
        self.after(100, self._carregar_dados)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_header()
        self._build_cards()
        self._build_recent_section()
        self._build_due_section()

    def _build_header(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, columnspan=4, sticky="ew",
                   padx=28, pady=(28, 4))

        ctk.CTkLabel(frame, text="Dashboard",
                     font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
                     text_color=TEXT_MAIN,
                     ).pack(side="left")
        ctk.CTkLabel(frame, text="Visão geral do sistema",   # sentence case
                     font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
                     ).pack(side="left", padx=(10, 0), pady=(8, 0))

    def _build_cards(self):
        for col, (key, icon, label, color, tint) in enumerate(_CARD_DEFS):
            card = StatCard(self, icon=icon, label=label, value="...",
                            accent_color=color, tint_color=tint)
            card.grid(row=1, column=col, sticky="nsew",
                      padx=(28 if col == 0 else 8, 8 if col < 3 else 28),
                      pady=8)
            self._stat_cards[key] = card   # chave estável — não o texto

    def _build_recent_section(self):
        SectionHeader(self, "ATIVIDADE RECENTE").grid(
            row=2, column=0, columnspan=4,
            sticky="ew", padx=28, pady=(20, 10),
        )
        self._recent_frame = ctk.CTkFrame(
            self, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self._recent_frame.grid(row=3, column=0, columnspan=4,
                                sticky="ew", padx=28, pady=(0, 8))
        self._recent_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._render_table_header(
            self._recent_frame,
            ["Cliente", "Máquina", "Valor", "Status"],
        )
        self._placeholder(self._recent_frame, row=1)

    def _build_due_section(self):
        SectionHeader(self, "PARCELAS COM VENCIMENTO PRÓXIMO").grid(
            row=4, column=0, columnspan=4,
            sticky="ew", padx=28, pady=(20, 10),
        )
        self._due_frame = ctk.CTkFrame(
            self, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self._due_frame.grid(row=5, column=0, columnspan=4,
                             sticky="ew", padx=28, pady=(0, 28))
        self._due_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._render_table_header(
            self._due_frame,
            ["Cliente", "Parcela", "Valor", "Vencimento"],
        )
        self._placeholder(self._due_frame, row=1)

    # ── Helpers de layout ────────────────────────────────────────────────────

    @staticmethod
    def _render_table_header(parent: ctk.CTkFrame, cols: list[str]):
        header_row = ctk.CTkFrame(parent, fg_color="#F9FAFB", corner_radius=0)
        header_row.grid(row=0, column=0, columnspan=len(cols), sticky="ew")
        header_row.grid_columnconfigure(list(range(len(cols))), weight=1)
        for col, h in enumerate(cols):
            ctk.CTkLabel(header_row, text=h,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=TEXT_SUB,
                         ).grid(row=0, column=col, sticky="w", padx=18, pady=10)

    @staticmethod
    def _placeholder(parent: ctk.CTkFrame, row: int, msg: str = "Nenhum registro encontrado"):
        ctk.CTkLabel(parent, text=msg,
                     font=ctk.CTkFont(size=13), text_color=TEXT_SUB,
                     ).grid(row=row, column=0, columnspan=4, pady=24)

    @staticmethod
    def _clear_rows(frame: ctk.CTkFrame, from_row: int = 1):
        """Remove todas as linhas de dados (preserva o cabeçalho em row=0)."""
        for w in frame.winfo_children():
            info = w.grid_info()
            if info and int(info.get("row", 0)) >= from_row:
                w.destroy()

    # ── Carregamento de dados ─────────────────────────────────────────────────

    def _carregar_dados(self):
        """
        Busca dados dos services e atualiza a UI.
        Chamado via after() para não bloquear a inicialização.
        """
        try:
            resumo   = self._buscar_resumo()
            recentes = self._buscar_recentes()
            proximas = self._buscar_proximas()

            self._aplicar_resumo(resumo)
            self._render_recent(recentes)
            self._render_due(proximas)

        except Exception as e:
            self._exibir_erro(f"Erro ao carregar dashboard: {e}")
            # Mesmo com erro, exibe "—" nos cards
            self._aplicar_resumo({})

    def _buscar_resumo(self) -> dict:
        from services.estoque_service import resumo_estoque
        from services.cliente_service import listar_clientes
        from services.pagamento_service import parcelas_atrasadas

        estoque  = resumo_estoque(self.session)
        clientes = listar_clientes(self.session)
        atrasadas = parcelas_atrasadas(self.session)

        return {
            "maquinas":  estoque["maquinas_disponiveis"],
            "mesas":     estoque["mesas_disponiveis"],
            "clientes":  len(clientes),
            "atrasos":   len(atrasadas),
        }

    def _buscar_recentes(self) -> list[dict]:
        """Retorna as 7 vendas mais recentes como dicts simples."""
        from services.venda_service import listar_vendas
        vendas = listar_vendas(self.session)[:7]
        resultado = []
        for v in vendas:
            maquina = "—"
            if v.itens:
                iv = v.itens[0]
                maq = iv.maquina
                maquina = f"{maq.marca} {maq.modelo}" if maq else "—"
            status = v.status.value if hasattr(v.status, "value") else str(v.status)
            resultado.append({
                "cliente": v.cliente.nome if v.cliente else "—",
                "maquina": maquina,
                "valor":   float(v.valor_total) if v.valor_total else 0.0,
                "status":  status,
            })
        return resultado

    def _buscar_proximas(self) -> list[dict]:
        """Retorna parcelas pendentes com vencimento nos próximos 14 dias."""
        from services.pagamento_service import parcelas_em_aberto
        hoje   = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        limite = hoje + timedelta(days=14)

        todas = parcelas_em_aberto(self.session)
        resultado = []
        for p in todas:
            if not p.data_vencimento:
                continue
            # Normaliza para naive se vier com timezone
            venc = p.data_vencimento
            if venc.tzinfo is not None:
                venc = venc.replace(tzinfo=None)
            if not (hoje <= venc <= limite):
                continue
            cliente = p.venda.cliente.nome if (p.venda and p.venda.cliente) else "—"
            num = p.numero_parcela
            tot = sum(1 for x in p.venda.pagamentos
                      if getattr(x.tipo, "value", x.tipo) == "PARCELA") if p.venda else "?"
            resultado.append({
                "cliente":   cliente,
                "parcela":   f"{num}/{tot}" if num else "—",
                "valor":     float(p.valor) if p.valor else 0.0,
                "vencimento": venc.strftime("%d/%m/%Y"),
                "atrasada":  venc < hoje,
            })
        return resultado

    # ── Atualização da UI ─────────────────────────────────────────────────────

    def _aplicar_resumo(self, resumo: dict):
        """
        Atualiza os cards usando chaves estáveis.
        Mudar o texto de UI de um card não quebra mais esse método.
        """
        mapeamento = {
            "maquinas": str(resumo.get("maquinas", "—")),
            "mesas":    str(resumo.get("mesas",    "—")),
            "clientes": str(resumo.get("clientes", "—")),
            "atrasos":  str(resumo.get("atrasos",  "—")),
        }
        for key, value in mapeamento.items():
            if key in self._stat_cards:
                self._stat_cards[key].set_value(value)

    def _render_recent(self, vendas: list[dict]):
        self._clear_rows(self._recent_frame, from_row=1)

        if not vendas:
            self._placeholder(self._recent_frame, row=1)
            return

        STATUS_COLOR = {
            "QUITADA": _VERDE,
            "ABERTA":  _AMARELO,
        }

        for i, v in enumerate(vendas):
            bg = "#F9FAFB" if i % 2 == 0 else CARD_BG
            row_f = ctk.CTkFrame(self._recent_frame, fg_color=bg, corner_radius=0)
            row_f.grid(row=i + 1, column=0, columnspan=4, sticky="ew")
            row_f.grid_columnconfigure((0, 1, 2, 3), weight=1)

            status_color = STATUS_COLOR.get(v["status"], TEXT_SUB)

            for col, (text, color) in enumerate([
                (v["cliente"],          TEXT_MAIN),
                (v["maquina"],          TEXT_SUB),
                (_fmt_brl(v["valor"]),  ACCENT),
                (v["status"],           status_color),
            ]):
                ctk.CTkLabel(row_f, text=text,
                             font=ctk.CTkFont(size=13,
                                             weight="bold" if col == 3 else "normal"),
                             text_color=color, anchor="w",
                             ).grid(row=0, column=col, sticky="w", padx=18, pady=10)

    def _render_due(self, parcelas: list[dict]):
        self._clear_rows(self._due_frame, from_row=1)

        if not parcelas:
            self._placeholder(self._due_frame, row=1,
                              msg="Nenhuma parcela vencendo nos próximos 14 dias.")
            return

        for i, p in enumerate(parcelas):
            bg = "#F9FAFB" if i % 2 == 0 else CARD_BG
            row_f = ctk.CTkFrame(self._due_frame, fg_color=bg, corner_radius=0)
            row_f.grid(row=i + 1, column=0, columnspan=4, sticky="ew")
            row_f.grid_columnconfigure((0, 1, 2, 3), weight=1)

            venc_color = _VERMELHO if p.get("atrasada") else TEXT_MAIN

            for col, (text, color) in enumerate([
                (p["cliente"],           TEXT_MAIN),
                (p["parcela"],           TEXT_SUB),
                (_fmt_brl(p["valor"]),   ACCENT),
                (p["vencimento"],        venc_color),
            ]):
                ctk.CTkLabel(row_f, text=text,
                             font=ctk.CTkFont(size=13,
                                             weight="bold" if col == 3 else "normal"),
                             text_color=color, anchor="w",
                             ).grid(row=0, column=col, sticky="w", padx=18, pady=10)

    # ── Erro ──────────────────────────────────────────────────────────────────

    def _exibir_erro(self, msg: str):
        if self._error_banner and self._error_banner.winfo_exists():
            self._error_banner.destroy()
        self._error_banner = ctk.CTkLabel(
            self, text=f"⚠  {msg}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FFF", fg_color=_VERMELHO,
            corner_radius=8, height=36,
        )
        self._error_banner.grid(row=6, column=0, columnspan=4,
                                sticky="ew", padx=28, pady=(0, 8))

    # ── API pública ───────────────────────────────────────────────────────────

    def refresh(self):
        """Recarrega todos os dados. Pode ser chamado externamente."""
        for key in self._stat_cards:
            self._stat_cards[key].set_value("...")
        self._carregar_dados()