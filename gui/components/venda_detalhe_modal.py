"""
gui/components/venda_detalhe_modal.py

Modal de detalhe de uma venda — mostra resumo, itens e pagamentos.
Permite registrar pagamento direto pelo modal.
Herda de BaseModal.
"""

import customtkinter as ctk
from CTkTable import CTkTable

from gui.components.base_modal import (
    BaseModal,
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER, HEADER_BG,
    ROW_ALT,
    fmt_brl as _fmt_brl,
    make_label as _label,
    divider,
)

# ── Semântica de cores ────────────────────────────────────────────────────────
_VERDE    = "#059669"
_AMARELO  = "#D97706"
_VERMELHO = "#DC2626"
_AZUL     = "#4F6AF0"
_LILAC    = "#7C3AED"

STATUS_VENDA_CFG = {
    "ABERTA":  ("Em aberto",  _AMARELO, "#FEF3C7"),
    "QUITADA": ("Quitada",    _VERDE,   "#D1FAE5"),
}

STATUS_PAG_CFG = {
    "PAGO":     ("● Pago",     _VERDE),
    "PENDENTE": ("● Pendente", _AMARELO),
    "ATRASADO": ("● Atrasado", _VERMELHO),
}

TIPO_CFG = {
    "AVISTA":   ("À vista",   _AZUL),
    "PARCELADO":("Parcelado", _LILAC),
    "ENTRADA":  ("Entrada",   _VERDE),
    "PARCELA":  ("Parcela",   TEXT_SUB),
}


def _status_pag_efetivo(p: dict) -> str:
    """Detecta ATRASADO em tempo de execução."""
    if p.get("status") == "PAGO":
        return "PAGO"
    from datetime import datetime
    venc = p.get("data_vencimento", "")
    try:
        dt = datetime.strptime(venc, "%d/%m/%Y")
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if dt < hoje:
            return "ATRASADO"
    except (ValueError, TypeError):
        pass
    return "PENDENTE"


# ── Sub-componente: seção com título ─────────────────────────────────────────

def _section_title(parent, text: str, row: int):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.grid(row=row, column=0, sticky="ew", pady=(18, 6))
    f.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(f, text=text,
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=TEXT_SUB,
                 ).grid(row=0, column=0, padx=(0, 10))
    ctk.CTkFrame(f, height=1, fg_color=BORDER).grid(row=0, column=1, sticky="ew")


# ── Modal ─────────────────────────────────────────────────────────────────────

class VendaDetalheModal(BaseModal):
    """
    Exibe o detalhe completo de uma venda.

    Parâmetros
    ----------
    venda : dict  —  todas as chaves abaixo são opcionais (fallback "—")
        {
          "id":            int,
          "cliente":       str,
          "data":          str   (dd/mm/aaaa),
          "valor_total":   float,
          "total_pago":    float,
          "saldo_devedor": float,
          "status":        str   (ABERTA | QUITADA),
          "tipo_pagamento":str   (AVISTA | PARCELADO),
          "num_parcelas":  int,
          "observacoes":   str,
          "itens": [
              {"maquina": str, "mesa": str, "preco": float}
          ],
          "pagamentos": [
              {
                "id":              int,
                "tipo":            str,
                "numero_parcela":  int | None,
                "total_parcelas":  int | None,
                "valor":           float,
                "data_vencimento": str,
                "data_pagamento":  str | None,
                "status":          str,
              }
          ],
        }
    on_registrar_pagamento : callable(parcela_dict) → None
        Chamado ao clicar em "Registrar" em uma parcela pendente.
        A view pai é responsável por abrir o RegistrarPagamentoModal.
    """

    def __init__(self, master, venda: dict, on_registrar_pagamento=None):
        self._venda  = venda
        self._on_reg = on_registrar_pagamento
        titulo = f"Venda #{venda.get('id', '—')}"
        super().__init__(master, title=titulo, width=680, height=680)
        self._build_body()

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self):
        b = self.body
        b.grid_columnconfigure(0, weight=1)
        v = self._venda

        # ── 1. Cabeçalho do detalhe ───────────────────────────────────────
        hdr = ctk.CTkFrame(b, fg_color=CARD_BG, corner_radius=10,
                           border_width=1, border_color=BORDER)
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 0))
        hdr.grid_columnconfigure(0, weight=1)

        # Linha topo: cliente + badge status
        top_row = ctk.CTkFrame(hdr, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        top_row.grid_columnconfigure(0, weight=1)

        _label(top_row, v.get("cliente", "—"),
               font_size=16, weight="bold", color=TEXT_MAIN,
               row=0, column=0, sticky="w")

        status_v = v.get("status", "ABERTA")
        s_lbl, s_color, s_bg = STATUS_VENDA_CFG.get(
            status_v, (status_v, TEXT_SUB, BORDER)
        )
        badge = ctk.CTkFrame(top_row, fg_color=s_bg, corner_radius=6,
                             width=88, height=24)
        badge.grid(row=0, column=1, sticky="e")
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text=s_lbl,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=s_color,
                     ).place(relx=0.5, rely=0.5, anchor="center")

        divider(hdr, row=1, padx=16)

        # Grade de metadados: 4 colunas
        meta = ctk.CTkFrame(hdr, fg_color="transparent")
        meta.grid(row=2, column=0, sticky="ew", padx=16, pady=(10, 14))
        meta.grid_columnconfigure((0, 1, 2, 3), weight=1)

        tipo_v  = v.get("tipo_pagamento", "")
        tipo_lbl, tipo_color = TIPO_CFG.get(tipo_v, (tipo_v, TEXT_SUB))

        meta_items = [
            ("Data",           v.get("data", "—")),
            ("Tipo",           tipo_lbl),
            ("Parcelas",       str(v.get("num_parcelas", "—"))),
            ("Total",          _fmt_brl(v.get("valor_total"))),
        ]
        for col, (lbl, val) in enumerate(meta_items):
            _label(meta, lbl, font_size=10, color=TEXT_SUB,
                   row=0, column=col, sticky="w")
            color = tipo_color if lbl == "Tipo" else TEXT_MAIN
            _label(meta, val, font_size=13, weight="bold", color=color,
                   row=1, column=col, sticky="w", pady=(2, 0))

        # Barra de progresso financeiro
        prog_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        prog_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        prog_frame.grid_columnconfigure(1, weight=1)

        total   = v.get("valor_total") or 1
        pago    = v.get("total_pago")  or 0
        saldo   = v.get("saldo_devedor") or 0
        progresso = min(pago / total, 1.0) if total else 0

        _label(prog_frame, "Pago", font_size=10, color=TEXT_SUB,
               row=0, column=0, padx=(0, 10))
        bar_bg = ctk.CTkFrame(prog_frame, fg_color=BORDER,
                              corner_radius=4, height=8)
        bar_bg.grid(row=0, column=1, sticky="ew")
        bar_bg.grid_propagate(False)
        bar_fg = ctk.CTkFrame(bar_bg, fg_color=_VERDE if progresso >= 1 else ACCENT,
                              corner_radius=4, height=8)
        bar_fg.place(relx=0, rely=0, relwidth=progresso, relheight=1)

        _label(prog_frame,
               f"{_fmt_brl(pago)} / {_fmt_brl(total)}",
               font_size=10, color=TEXT_SUB,
               row=0, column=2, padx=(10, 0))

        if saldo > 0:
            _label(prog_frame,
                   f"Saldo: {_fmt_brl(saldo)}",
                   font_size=11, weight="bold", color=_AMARELO,
                   row=1, column=1, sticky="w", pady=(4, 0))

        # Observações
        obs = v.get("observacoes", "")
        if obs:
            _label(hdr, f"Obs: {obs}", font_size=11, color=TEXT_SUB,
                   row=4, column=0, sticky="w", padx=16, pady=(0, 12))

        # ── 2. Itens ──────────────────────────────────────────────────────
        _section_title(b, "ITENS DA VENDA", row=1)

        itens = v.get("itens", [])
        if itens:
            i_values = [["Máquina", "Mesa", "Preço"]]
            for it in itens:
                i_values.append([
                    it.get("maquina", "—"),
                    it.get("mesa", "—"),
                    _fmt_brl(it.get("preco")),
                ])
            i_tbl = CTkTable(
                b, values=i_values,
                header_color=HEADER_BG,
                colors=[CARD_BG, ROW_ALT],
                text_color=TEXT_MAIN,
                hover=False,
                height=38,
                font=ctk.CTkFont(size=12),
                padx=1, pady=1,
                corner_radius=8,
                border_width=1,
                border_color=BORDER,
                anchor="w",
            )
            i_tbl.grid(row=2, column=0, sticky="ew", padx=20)
            i_tbl.edit_row(0, text_color=TEXT_SUB, fg_color=HEADER_BG,
                           hover_color=HEADER_BG,
                           font=ctk.CTkFont(size=11, weight="bold"), height=34)
        else:
            _label(b, "Nenhum item registrado.",
                   font_size=12, color=TEXT_SUB, row=2, column=0,
                   padx=20, pady=8)

        # ── 3. Pagamentos ─────────────────────────────────────────────────
        _section_title(b, "PAGAMENTOS", row=3)

        pagamentos = v.get("pagamentos", [])
        self._pag_frame = ctk.CTkFrame(b, fg_color="transparent")
        self._pag_frame.grid(row=4, column=0, sticky="ew", padx=20)
        self._pag_frame.grid_columnconfigure(0, weight=1)
        self._render_pagamentos(pagamentos)

        # ── 4. Footer simples (só fechar) ─────────────────────────────────
        foot = ctk.CTkFrame(b, fg_color="transparent")
        foot.grid(row=5, column=0, sticky="e", pady=(16, 8), padx=20)
        ctk.CTkButton(
            foot, text="Fechar", width=100, height=36,
            fg_color=BORDER, hover_color="#DDDFE8", text_color=TEXT_MAIN,
            corner_radius=8, font=ctk.CTkFont(size=13),
            command=self.destroy,
        ).pack()

    # ── Tabela de pagamentos ──────────────────────────────────────────────────

    def _render_pagamentos(self, pagamentos: list[dict]):
        for w in self._pag_frame.winfo_children():
            w.destroy()

        if not pagamentos:
            _label(self._pag_frame, "Nenhum pagamento registrado.",
                   font_size=12, color=TEXT_SUB, row=0, column=0, pady=8)
            return

        HEADS = ["Tipo / Parcela", "Valor", "Vencimento", "Pago em", "Status", ""]
        COL_STATUS = 4
        COL_BTN    = 5

        values = [HEADS]
        for p in pagamentos:
            tipo_raw = p.get("tipo", "")
            num  = p.get("numero_parcela")
            tot  = p.get("total_parcelas")
            tipo_lbl = (
                f"Parcela {num}/{tot}" if (tipo_raw == "PARCELA" and num)
                else TIPO_CFG.get(tipo_raw, (tipo_raw, TEXT_SUB))[0]
            )
            st = _status_pag_efetivo(p)
            st_lbl, _ = STATUS_PAG_CFG.get(st, (st, TEXT_SUB))
            values.append([
                tipo_lbl,
                _fmt_brl(p.get("valor")),
                p.get("data_vencimento", "—"),
                p.get("data_pagamento") or "—",
                st_lbl,
                "",   # botão
            ])

        tbl = CTkTable(
            self._pag_frame,
            values=values,
            header_color=HEADER_BG,
            colors=[CARD_BG, ROW_ALT],
            text_color=TEXT_MAIN,
            hover=True,
            hover_color="#EEEEFF",
            height=40,
            font=ctk.CTkFont(size=12),
            padx=1, pady=1,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            anchor="w",
        )
        tbl.grid(row=0, column=0, sticky="ew")
        tbl.edit_row(0, text_color=TEXT_SUB, fg_color=HEADER_BG,
                     hover_color=HEADER_BG,
                     font=ctk.CTkFont(size=11, weight="bold"), height=34)

        for i, p in enumerate(pagamentos):
            row_idx = i + 1
            st = _status_pag_efetivo(p)
            _, color = STATUS_PAG_CFG.get(st, ("—", TEXT_SUB))

            tbl.frame[row_idx, COL_STATUS].configure(
                text_color=color,
                font=ctk.CTkFont(size=11, weight="bold"),
            )

            # Data vencimento vermelha se atrasada
            if st == "ATRASADO":
                tbl.frame[row_idx, 2].configure(
                    text_color=_VERMELHO,
                    font=ctk.CTkFont(size=12, weight="bold"),
                )

            # Botão de ação
            cell = tbl.frame[row_idx, COL_BTN]
            cell.configure(text="", hover=False)
            btn_f = ctk.CTkFrame(cell, fg_color="transparent")
            btn_f.place(relx=0.5, rely=0.5, anchor="center")

            if p.get("status") == "PAGO":
                ctk.CTkButton(
                    btn_f, text="✓ Pago", width=72, height=26,
                    fg_color="#D1FAE5", hover_color="#D1FAE5",
                    text_color=_VERDE, state="disabled",
                    corner_radius=6, font=ctk.CTkFont(size=10, weight="bold"),
                ).pack()
            else:
                ctk.CTkButton(
                    btn_f, text="Registrar", width=72, height=26,
                    fg_color=ACCENT, hover_color=ACCENT_HOVER,
                    text_color="#FFF",
                    corner_radius=6, font=ctk.CTkFont(size=10, weight="bold"),
                    command=lambda pp=p: self._registrar(pp),
                ).pack()

    def _registrar(self, parcela: dict):
        """Delega ao pai e fecha o modal."""
        if self._on_reg:
            self._on_reg(parcela)
        self.destroy()