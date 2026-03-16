"""
gui/components/registrar_pagamento_modal.py

Modal para registrar o pagamento de uma parcela.
Herda de BaseModal (gui/components/base_modal.py).

Melhorias v2:
  - DatePicker customizado com CustomTkinter (sem tkcalendar)
  - Máscara automática de moeda  (digitando "1000" → "R$ 10,00")
  - Diálogo de confirmação contextual antes de salvar
"""

import calendar
import customtkinter as ctk
from datetime import datetime, date

from gui.components.base_modal import (
    BaseModal,
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER,
    fmt_brl as _fmt_brl,
    make_label as _label,
    divider,
)


# ── Cores semânticas ──────────────────────────────────────────────────────────
_VERDE    = "#059669"
_AMARELO  = "#D97706"
_VERMELHO = "#DC2626"

STATUS_COLOR = {
    "PENDENTE": _AMARELO,
    "PAGO":     _VERDE,
    "ATRASADO": _VERMELHO,
}


# ─────────────────────────────────────────────────────────────────────────────
#  1. DATEPICKER CUSTOMTKINTER
#     Abre como CTkToplevel, fecha ao selecionar uma data e chama on_select(date)
# ─────────────────────────────────────────────────────────────────────────────

class _CTkDatePicker(ctk.CTkToplevel):

    DAYS_ABBR = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    MONTHS_PT = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho",   "Agosto",  "Setembro", "Outubro", "Novembro", "Dezembro",
    ]

    def __init__(self, anchor_widget, initial_date: date = None, on_select=None):
        super().__init__(anchor_widget)
        self._on_select   = on_select
        self._today       = date.today()
        self._selected    = initial_date or self._today
        self._viewing     = date(self._selected.year, self._selected.month, 1)
        self._anchor      = anchor_widget

        self.title("")
        self.resizable(False, False)
        self.overrideredirect(True)          # sem barra de título nativa
        self.grab_set()

        self._build_shell()
        self._render_month()
        self.after(10, self._place_near_anchor)
        self.bind("<FocusOut>", lambda e: self._on_focus_out(e))

    # ── posicionamento ────────────────────────────────────────────────────────

    def _place_near_anchor(self):
        self.update_idletasks()
        ax = self._anchor.winfo_rootx()
        ay = self._anchor.winfo_rooty() + self._anchor.winfo_height() + 4
        # garante que não saia pela direita/baixo da tela
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = self.winfo_width()
        h  = self.winfo_height()
        x  = min(ax, sw - w - 8)
        y  = min(ay, sh - h - 8)
        self.geometry(f"+{x}+{y}")

    def _on_focus_out(self, event):
        # Fecha se o foco foi para fora de qualquer janela filha
        if str(event.widget) == str(self):
            self.after(100, lambda: self.destroy()
                       if self.winfo_exists() else None)

    # ── estrutura shell ───────────────────────────────────────────────────────

    def _build_shell(self):
        self._wrap = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        self._wrap.pack(padx=1, pady=1)

    # ── renderização do mês ───────────────────────────────────────────────────

    def _render_month(self):
        for w in self._wrap.winfo_children():
            w.destroy()

        wrap = self._wrap
        wrap.grid_columnconfigure(0, weight=1)

        # Cabeçalho navegação
        hdr = ctk.CTkFrame(wrap, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))
        hdr.grid_columnconfigure(1, weight=1)

        def _nav(delta):
            y, m = self._viewing.year, self._viewing.month
            m += delta
            if m > 12: m, y = 1, y + 1
            if m < 1:  m, y = 12, y - 1
            self._viewing = date(y, m, 1)
            self._render_month()

        ctk.CTkButton(
            hdr, text="‹", width=30, height=30, corner_radius=8,
            fg_color=BG, text_color=TEXT_MAIN, hover_color=BORDER,
            font=ctk.CTkFont(size=18), command=lambda: _nav(-1),
        ).grid(row=0, column=0)

        ctk.CTkLabel(
            hdr,
            text=f"{self.MONTHS_PT[self._viewing.month - 1]}  {self._viewing.year}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_MAIN,
        ).grid(row=0, column=1)

        ctk.CTkButton(
            hdr, text="›", width=30, height=30, corner_radius=8,
            fg_color=BG, text_color=TEXT_MAIN, hover_color=BORDER,
            font=ctk.CTkFont(size=18), command=lambda: _nav(+1),
        ).grid(row=0, column=2)

        # Abreviações dos dias
        days_row = ctk.CTkFrame(wrap, fg_color="transparent")
        days_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 0))
        for i, d in enumerate(self.DAYS_ABBR):
            ctk.CTkLabel(
                days_row, text=d, width=36, height=22,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=TEXT_SUB,
            ).grid(row=0, column=i, padx=1)

        # Grade de dias
        grid = ctk.CTkFrame(wrap, fg_color="transparent")
        grid.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 10))

        cal = calendar.monthcalendar(self._viewing.year, self._viewing.month)
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(grid, text="", width=36, height=32
                                 ).grid(row=r, column=c, padx=1, pady=1)
                    continue

                d = date(self._viewing.year, self._viewing.month, day)
                is_sel   = (d == self._selected)
                is_today = (d == self._today)

                if is_sel:
                    fg, tc, hov = ACCENT,       "#FFFFFF", ACCENT_HOVER
                elif is_today:
                    fg, tc, hov = ACCENT_HOVER,  TEXT_MAIN, BORDER
                else:
                    fg, tc, hov = BG,            TEXT_MAIN, BORDER

                def _cb(chosen=d):
                    self._selected = chosen
                    if self._on_select:
                        self._on_select(chosen)
                    self.destroy()

                ctk.CTkButton(
                    grid, text=str(day), width=36, height=32,
                    corner_radius=8, fg_color=fg, text_color=tc,
                    hover_color=hov, font=ctk.CTkFont(size=12),
                    command=_cb,
                ).grid(row=r, column=c, padx=1, pady=1)


# ─────────────────────────────────────────────────────────────────────────────
#  2. WIDGET _DateField  —  CTkEntry (readonly) + botão 📅
# ─────────────────────────────────────────────────────────────────────────────

class _DateField(ctk.CTkFrame):
    """
    Campo de data com caixa de texto somente-leitura e botão que abre o picker.
    """

    def __init__(self, master, initial_date: date = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._date   = initial_date or date.today()
        self._picker = None

        self.grid_columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(
            self, height=38, corner_radius=8,
            fg_color=CARD_BG, border_color=BORDER, border_width=1,
            text_color=TEXT_MAIN, font=ctk.CTkFont(size=14),
            state="readonly",
        )
        self._entry.grid(row=0, column=0, sticky="ew")
        self._refresh_entry()

        self._btn = ctk.CTkButton(
            self, text="📅", width=38, height=38, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=self._open_picker,
        )
        self._btn.grid(row=0, column=1, padx=(4, 0))

    def _refresh_entry(self):
        self._entry.configure(state="normal")
        self._entry.delete(0, "end")
        self._entry.insert(0, self._date.strftime("%d/%m/%Y"))
        self._entry.configure(state="readonly")

    def _open_picker(self):
        # Se já está aberto, apenas foca
        if self._picker and self._picker.winfo_exists():
            self._picker.focus()
            return
        self._picker = _CTkDatePicker(
            anchor_widget=self._btn,
            initial_date=self._date,
            on_select=self._on_date_selected,
        )

    def _on_date_selected(self, d: date):
        self._date   = d
        self._picker = None
        self._refresh_entry()

    def get(self) -> date:
        return self._date


# ─────────────────────────────────────────────────────────────────────────────
#  3. DIÁLOGO DE CONFIRMAÇÃO CONTEXTUAL
# ─────────────────────────────────────────────────────────────────────────────

class _ConfirmDialog(ctk.CTkToplevel):
    """
    Mostra um resumo antes de confirmar o pagamento.
    Chama on_confirm() se o usuário clicar em "Confirmar".
    """

    def __init__(self, master, cliente: str, valor: float,
                 data: date, on_confirm=None):
        super().__init__(master)
        self._on_confirm = on_confirm

        self.title("Confirmar pagamento")
        self.resizable(False, False)
        self.grab_set()
        self.after(10, self._center)
        self._build(cliente, valor, data)

    def _center(self):
        self.update_idletasks()
        rx  = self.master.winfo_rootx()
        ry  = self.master.winfo_rooty()
        mw  = self.master.winfo_width()
        mh  = self.master.winfo_height()
        w   = self.winfo_width()
        h   = self.winfo_height()
        self.geometry(f"+{rx + (mw - w) // 2}+{ry + (mh - h) // 2}")

    def _build(self, cliente, valor, data):
        wrap = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=14,
                            border_width=1, border_color=BORDER)
        wrap.pack(padx=2, pady=2)
        wrap.grid_columnconfigure(0, weight=1)

        # Ícone + título
        ctk.CTkLabel(wrap, text="💳",
                     font=ctk.CTkFont(size=34),
                     ).grid(row=0, column=0, pady=(22, 4))

        ctk.CTkLabel(wrap, text="Confirmar pagamento?",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT_MAIN,
                     ).grid(row=1, column=0, pady=(0, 14))

        # Card de detalhes
        details = ctk.CTkFrame(wrap, fg_color=BG, corner_radius=10)
        details.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))
        details.grid_columnconfigure(1, weight=1)

        hoje     = date.today()
        data_txt = "Hoje" if data == hoje else data.strftime("%d/%m/%Y")

        rows = [("Cliente", cliente), ("Valor", _fmt_brl(valor)), ("Data", data_txt)]
        for i, (lbl, val) in enumerate(rows):
            top_pad = 10 if i == 0 else 4
            bot_pad = 10 if i == len(rows) - 1 else 4

            ctk.CTkLabel(details, text=lbl,
                         font=ctk.CTkFont(size=11), text_color=TEXT_SUB,
                         anchor="w",
                         ).grid(row=i, column=0, sticky="w",
                                padx=(14, 8), pady=(top_pad, bot_pad))
            ctk.CTkLabel(details, text=val,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=TEXT_MAIN, anchor="w",
                         ).grid(row=i, column=1, sticky="w",
                                padx=(0, 14), pady=(top_pad, bot_pad))

        # Botões
        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 22))
        btns.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btns, text="Cancelar", height=38, corner_radius=8,
            fg_color=BG, border_width=1, border_color=BORDER,
            text_color=TEXT_MAIN, hover_color=BORDER,
            command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ctk.CTkButton(
            btns, text="Confirmar", height=38, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#FFFFFF", font=ctk.CTkFont(weight="bold"),
            command=self._confirmar,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _confirmar(self):
        self.destroy()
        if self._on_confirm:
            self._on_confirm()


# ─────────────────────────────────────────────────────────────────────────────
#  4. MODAL PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class RegistrarPagamentoModal(BaseModal):
    """
    Exibe os detalhes de uma parcela e permite registrar o pagamento.

    Parâmetros
    ----------
    master       : widget pai
    parcela      : dict
        {
          "id":              int,
          "cliente":         str,
          "venda_id":        int,
          "numero_parcela":  int,
          "total_parcelas":  int,
          "valor":           float,
          "data_vencimento": str  (dd/mm/aaaa),
          "status":          str  (PENDENTE | PAGO | ATRASADO),
        }
    on_save      : callable(pagamento_id, valor_pago, data_pagamento) → None
    """

    def __init__(self, master, parcela: dict, on_save=None):
        self._parcela = parcela
        self._on_save = on_save

        super().__init__(master, title="Registrar Pagamento", width=460, height=520)
        self._build_body()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_body(self):
        body = self.body
        body.grid_columnconfigure((0, 1), weight=1)

        p = self._parcela

        # ── Cartão de resumo da parcela ───────────────────────────────────
        card = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=10,
                            border_width=1, border_color=BORDER)
        card.grid(row=0, column=0, columnspan=2, sticky="ew",
                  padx=20, pady=(20, 12))
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        top.grid_columnconfigure(0, weight=1)

        _label(top, p.get("cliente", "—"),
               font_size=14, weight="bold", color=TEXT_MAIN,
               row=0, column=0, sticky="w")

        status       = p.get("status", "PENDENTE")
        status_color = STATUS_COLOR.get(status, TEXT_SUB)
        badge_bg     = {
            "PENDENTE": "#FEF3C7",
            "PAGO":     "#D1FAE5",
            "ATRASADO": "#FEE2E2",
        }.get(status, BORDER)

        badge = ctk.CTkFrame(top, fg_color=badge_bg, corner_radius=6,
                             width=90, height=24)
        badge.grid(row=0, column=1, sticky="e")
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text=status,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=status_color,
                     ).place(relx=0.5, rely=0.5, anchor="center")

        divider(card, row=1, padx=16)

        meta = ctk.CTkFrame(card, fg_color="transparent")
        meta.grid(row=2, column=0, sticky="ew", padx=16, pady=(10, 14))
        meta.grid_columnconfigure((0, 1, 2), weight=1)

        num_parcela    = p.get("numero_parcela", "—")
        total_parcelas = p.get("total_parcelas", "—")
        parcela_txt    = (f"{num_parcela}/{total_parcelas}"
                          if num_parcela != "—" else "—")

        for col, (lbl, val) in enumerate([
            ("Venda",      f"Venda #{p.get('venda_id', '—')}"),
            ("Parcela",    parcela_txt),
            ("Vencimento", p.get("data_vencimento", "—")),
        ]):
            _label(meta, lbl, font_size=10, color=TEXT_SUB,
                   row=0, column=col, sticky="w")
            _label(meta, val, font_size=13, weight="bold", color=TEXT_MAIN,
                   row=1, column=col, sticky="w", pady=(2, 0))

        # Valor em destaque
        vf = ctk.CTkFrame(body, fg_color="transparent")
        vf.grid(row=1, column=0, columnspan=2, sticky="ew",
                padx=20, pady=(0, 8))
        vf.grid_columnconfigure(0, weight=1)

        _label(vf, "Valor da parcela", font_size=11, color=TEXT_SUB,
               row=0, column=0, sticky="w")
        _label(vf, _fmt_brl(p.get("valor")),
               font_size=22, weight="bold", color=ACCENT,
               row=1, column=0, sticky="w", pady=(2, 0))

        # ── Labels de campo ────────────────────────────────────────────────
        _label(body, "Valor pago", font_size=11, color=TEXT_SUB,
               row=2, column=0, sticky="w", padx=(20, 6), pady=(8, 2))
        _label(body, "Data do pagamento", font_size=11, color=TEXT_SUB,
               row=2, column=1, sticky="w", padx=(6, 20), pady=(8, 2))

        # ── Entry com máscara de moeda ─────────────────────────────────────
        self._centavos        = 0
        self._updating_valor  = False
        self._valor_var       = ctk.StringVar(value="R$ 0,00")

        self._valor_entry = ctk.CTkEntry(
            body, height=38, corner_radius=8,
            fg_color=CARD_BG, border_color=BORDER, border_width=1,
            text_color=TEXT_MAIN, font=ctk.CTkFont(size=14),
            textvariable=self._valor_var,
        )
        self._valor_entry.grid(row=3, column=0, sticky="ew",
                               padx=(20, 6), pady=(0, 4))

        # Pré-preenche com o valor da parcela
        raw = p.get("valor")
        if raw is not None:
            try:
                self._centavos = int(round(float(raw) * 100))
                self._apply_mask()
            except (ValueError, TypeError):
                pass

        self._valor_var.trace_add("write", self._on_valor_change)

        # ── Campo de data com picker customizado ───────────────────────────
        self._date_field = _DateField(body, initial_date=date.today())
        self._date_field.grid(row=3, column=1, sticky="ew",
                              padx=(6, 20), pady=(0, 4))

        # ── Observações ────────────────────────────────────────────────────
        _label(body, "Observações (opcional)", font_size=11, color=TEXT_SUB,
               row=4, column=0, columnspan=2, sticky="w",
               padx=20, pady=(10, 2))
        self._obs_entry = ctk.CTkEntry(
            body, height=36, corner_radius=8,
            fg_color=CARD_BG, border_color=BORDER, border_width=1,
            text_color=TEXT_MAIN, font=ctk.CTkFont(size=13),
        )
        self._obs_entry.grid(row=5, column=0, columnspan=2,
                             sticky="ew", padx=20, pady=(0, 4))

        # ── Label de erro ──────────────────────────────────────────────────
        self._error_label = ctk.CTkLabel(
            body, text="", text_color=_VERMELHO,
            font=ctk.CTkFont(size=11), anchor="w",
        )
        self._error_label.grid(row=6, column=0, columnspan=2,
                               sticky="ew", padx=20)

        # ── Footer ─────────────────────────────────────────────────────────
        self._footer(body, on_cancel=self.destroy,
                     on_save=self._pedir_confirmacao, row=7)

    # ── Máscara de moeda ──────────────────────────────────────────────────────

    @staticmethod
    def _format_centavos(centavos: int) -> str:
        """Converte centavos inteiros → string 'R$ 1.234,56'."""
        reais = centavos // 100
        cents = centavos % 100
        # Separador de milhar
        reais_str = f"{reais:,}".replace(",", ".")
        return f"R$ {reais_str},{cents:02d}"

    def _apply_mask(self):
        self._valor_var.set(self._format_centavos(self._centavos))

    def _on_valor_change(self, *_):
        if self._updating_valor:
            return
        self._updating_valor = True
        try:
            raw    = self._valor_var.get()
            digits = "".join(c for c in raw if c.isdigit())
            self._centavos = min(int(digits or "0"), 999_999_999)
            self._apply_mask()
            self._valor_entry.icursor("end")
        finally:
            self._updating_valor = False

    # ── Confirmação ───────────────────────────────────────────────────────────

    def _pedir_confirmacao(self):
        if self._centavos <= 0:
            self._error_label.configure(
                text="⚠  Insira um valor válido e maior que zero.")
            return
        self._error_label.configure(text="")

        valor_pago     = self._centavos / 100.0
        data_pagamento = self._date_field.get()
        cliente        = self._parcela.get("cliente", "—")

        _ConfirmDialog(
            master=self,
            cliente=cliente,
            valor=valor_pago,
            data=data_pagamento,
            on_confirm=lambda: self._confirmar(valor_pago, data_pagamento),
        )

    def _confirmar(self, valor_pago: float, data_pagamento: date):
        if self._on_save:
            self._on_save(
                pagamento_id=self._parcela.get("id"),
                valor_pago=valor_pago,
                data_pagamento=datetime.combine(data_pagamento,
                                                datetime.min.time()),
            )
        self.destroy()