"""
gui/components/estoque_modals.py
Modals do módulo Estoque: MaquinaFormModal, MesaFormModal.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from .base_modal import (
    BaseModal, make_label,
    BG, CARD_BG, ACCENT, ACCENT_HOVER,
    TEXT_MAIN, TEXT_SUB, BORDER,
)

# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────

STATUS_CFG: dict[str, tuple[str, str]] = {
    "EM_ESTOQUE": ("Disponível", "#059669"),
    "VENDIDO":    ("Vendido",    "#DC2626"),
    "RESERVADO":  ("Reservado",  "#D97706"),
}

_STATUS_LABELS = [v[0] for v in STATUS_CFG.values()]
_LABEL_TO_KEY  = {v[0]: k for k, v in STATUS_CFG.items()}
_KEY_TO_LABEL  = {k: v[0] for k, v in STATUS_CFG.items()}

_NONE_MESA_LABEL = "— Nenhuma mesa —"


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def parse_float(value: str) -> float:
    """Converte string para float aceitando vírgula como separador decimal."""
    try:
        return float(value.replace(",", "."))
    except (ValueError, AttributeError):
        return 0.0


def _textbox_get(widget: ctk.CTkTextbox) -> str:
    """Retorna conteúdo de CTkTextbox sem o \n final que o Tk insere."""
    return widget.get("1.0", "end-1c").strip()


def _make_option_menu(
    master,
    values: list[str],
    variable: ctk.StringVar,
    command: Optional[Callable] = None,
) -> ctk.CTkOptionMenu:
    """
    CTkOptionMenu no lugar de CTkComboBox para seleções de lista fechada.
    Mais limpo visualmente e sem o bug de padding do CTkComboBox (issue #2570).
    """
    return ctk.CTkOptionMenu(
        master,
        values=values,
        variable=variable,
        command=command,
    )


# ─────────────────────────────────────────────────────────────
# Modal Máquina
# ─────────────────────────────────────────────────────────────

class MaquinaFormModal(BaseModal):
    """
    Formulário para criar ou editar uma Máquina.

    Parâmetros
    ----------
    mesas_disponiveis:
        Lista de dicts com chaves ``id``, ``modelo`` e opcionalmente ``material``.
    on_save:
        Callback chamado com o dict de dados validados.
    maquina:
        Dict com dados existentes para edição (None = criação).
    """

    def __init__(
        self,
        master,
        mesas_disponiveis: list[dict],
        on_save: Callable[[dict], None],
        maquina: Optional[dict] = None,
    ) -> None:
        super().__init__(
            master,
            title="Editar Máquina" if maquina else "Nova Máquina",
            width=520,
            height=580,
        )

        self.on_save = on_save
        self.maquina = maquina or {}
        self.mesas   = mesas_disponiveis
        self.entries: dict[str, ctk.CTkEntry] = {}

        self._build()

    # ── Construção ──────────────────────────────────────────

    def _build(self) -> None:
        b = self.body
        b.grid_columnconfigure((0, 1), weight=1)

        get = self.maquina.get

        for label, key, lrow, col in (
            ("Marca *",     "marca",               0, 0),
            ("Modelo *",    "modelo",              0, 1),
            ("Nº de Série", "numero_serie",        1, 0),
            ("Cor",         "cor",                 1, 1),
        ):
            self._entry_field(b, label, key, lrow, col,
                              self.entries, initial=str(get(key) or ""))

        # placeholder para numero de serie
        self.entries["numero_serie"].configure(placeholder_text="Opcional")

        for col, (label, key) in enumerate((
            ("Preço de Custo (R$)",  "preco_custo"),
            ("Preço de Venda (R$)",  "preco_venda_sugerido"),
        )):
            self._entry_field(b, label, key, 2, col,
                              self.entries, initial=str(get(key) or ""))

        # ── Status  (linha real 6)
        make_label(b, "Status", font_size=11, color=TEXT_SUB, anchor="w",
                   row=6, column=0, columnspan=2, pady=(10, 2))

        current_label = _KEY_TO_LABEL.get(
            get("status", "EM_ESTOQUE"), _STATUS_LABELS[0]
        )
        self.status_var = ctk.StringVar(value=current_label)

        ctk.CTkSegmentedButton(
            b, values=_STATUS_LABELS, variable=self.status_var, corner_radius=8,
        ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        # ── Mesa vinculada  (linha real 8)
        make_label(b, "Mesa vinculada", font_size=11, color=TEXT_SUB, anchor="w",
                   row=8, column=0, columnspan=2, pady=(10, 2))

        self.mesa_map: dict[str, Optional[int]] = {
            _NONE_MESA_LABEL: None,
            **{self._mesa_label(m): m["id"] for m in self.mesas},
        }

        current_mesa_id = get("mesa_id")
        initial_mesa = next(
            (lbl for lbl, mid in self.mesa_map.items() if mid == current_mesa_id),
            _NONE_MESA_LABEL,
        )

        self.mesa_var  = ctk.StringVar(value=initial_mesa)
        self.mesa_menu = _make_option_menu(
            b, values=list(self.mesa_map.keys()), variable=self.mesa_var,
        )
        self.mesa_menu.grid(row=9, column=0, columnspan=2,
                            sticky="ew", pady=(0, 4))

        # ── Observações  (linha real 10)
        make_label(b, "Observações", font_size=11, color=TEXT_SUB, anchor="w",
                   row=10, column=0, columnspan=2, pady=(10, 2))

        self.obs = ctk.CTkTextbox(
            b, height=90, corner_radius=8,
            fg_color=CARD_BG, border_color=BORDER, border_width=1,
            text_color=TEXT_MAIN,
        )
        self.obs.grid(row=11, column=0, columnspan=2,
                      sticky="nsew", pady=(0, 6))

        if obs_text := get("observacoes"):
            self.obs.insert("1.0", obs_text)

        self._footer(b, self.destroy, self._submit, row=12)

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _mesa_label(m: dict) -> str:
        label = f"{m['modelo']} (#{m['id']})"
        if m.get("material"):
            label += f" • {m['material']}"
        return label

    # ── Submit ──────────────────────────────────────────────

    def _submit(self) -> None:
        data = {k: e.get().strip() for k, e in self.entries.items()}
        data["observacoes"] = _textbox_get(self.obs)

        numero_serie = data.get("numero_serie")
        if not numero_serie or numero_serie == "-" or numero_serie == "—":
            data["numero_serie"] = None

        invalid = False
        for key in ("marca", "modelo"):
            ok = bool(data.get(key))
            self.entries[key].configure(border_color=BORDER if ok else "#E05C5C")
            if not ok:
                invalid = True

        if invalid:
            return

        data["status"]  = _LABEL_TO_KEY.get(self.status_var.get(), "EM_ESTOQUE")
        data["mesa_id"] = self.mesa_map.get(self.mesa_var.get())

        data["preco_custo"]          = parse_float(data.get("preco_custo", ""))
        data["preco_venda_sugerido"] = parse_float(data.get("preco_venda_sugerido", ""))

        self.on_save(data)
        self.destroy()


# ─────────────────────────────────────────────────────────────
# Modal Mesa
# ─────────────────────────────────────────────────────────────

class MesaFormModal(BaseModal):
    """
    Formulário para criar ou editar uma Mesa de bilhar.

    Parâmetros
    ----------
    on_save:
        Callback chamado com o dict de dados validados.
    mesa:
        Dict com dados existentes para edição (None = criação).
    """

    def __init__(
        self,
        master,
        on_save: Callable[[dict], None],
        mesa: Optional[dict] = None,
    ) -> None:
        super().__init__(
            master,
            title="Editar Mesa" if mesa else "Nova Mesa",
            width=460,
            height=380,
        )

        self.on_save = on_save
        self.mesa    = mesa or {}
        self.entries: dict[str, ctk.CTkEntry] = {}

        self._build()

    # ── Construção ──────────────────────────────────────────

    def _build(self) -> None:
        b = self.body
        b.grid_columnconfigure((0, 1), weight=1)

        get = self.mesa.get

        # Lógica 0 → reais 0-1  (Modelo / Material)
        # Lógica 1 → reais 2-3  (Cor)
        # Linha real 4 → label Observações
        # Linha real 5 → CTkTextbox
        # Linha real 6 → footer
        for label, key, lrow, col in (
            ("Modelo *", "modelo",   0, 0),
            ("Material", "material", 0, 1),
            ("Cor",      "cor",      1, 0),
        ):
            self._entry_field(b, label, key, lrow, col,
                              self.entries, initial=str(get(key) or ""))

        make_label(b, "Observações", font_size=11, color=TEXT_SUB, anchor="w",
                   row=4, column=0, columnspan=2, pady=(10, 2))

        self.obs = ctk.CTkTextbox(
            b, height=90, corner_radius=8,
            fg_color=CARD_BG, border_color=BORDER, border_width=1,
            text_color=TEXT_MAIN,
        )
        self.obs.grid(row=5, column=0, columnspan=2, sticky="nsew")

        if obs_text := get("observacoes"):
            self.obs.insert("1.0", obs_text)

        self._footer(b, self.destroy, self._submit, row=6)

    # ── Submit ──────────────────────────────────────────────

    def _submit(self) -> None:
        data = {k: e.get().strip() for k, e in self.entries.items()}
        data["observacoes"] = _textbox_get(self.obs)

        ok = bool(data.get("modelo"))
        self.entries["modelo"].configure(border_color=BORDER if ok else "#E05C5C")

        if not ok:
            return

        self.on_save(data)
        self.destroy()