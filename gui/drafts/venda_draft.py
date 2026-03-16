"""
Representa o estado transitório de uma venda em criação na GUI.
Substitui o _dados: dict sem tipo por uma estrutura validável.

v2: VendaDraft.maquinas é agora uma lista (carrinho), em vez de uma máquina única.
    O service já suportava múltiplos itens; a view agora também.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ClienteDraft:
    id:        int
    nome:      str
    documento: str = "—"
    telefone:  str = "—"


@dataclass
class MaquinaDraft:
    id:                   int
    marca:                str
    modelo:               str
    numero_serie:         str     = "—"
    mesa:                 str     = "—"
    preco_venda_sugerido: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class PagamentoDraft:
    tipo:      str     = "avista"           # "avista" | "parcelado"
    preco:     Decimal = field(default_factory=lambda: Decimal("0"))
    entrada:   Decimal = field(default_factory=lambda: Decimal("0"))
    parcelas:  int     = 1
    intervalo: int     = 30                 # dias entre parcelas


@dataclass
class VendaDraft:
    cliente:   ClienteDraft       | None = None
    maquinas:  list[MaquinaDraft]        = field(default_factory=list)
    pagamento: PagamentoDraft            = field(default_factory=PagamentoDraft)

    # ── Compatibilidade com código que ainda usa .maquina (singular) ──────────
    @property
    def maquina(self) -> MaquinaDraft | None:
        """Primeira máquina do carrinho, ou None se vazio."""
        return self.maquinas[0] if self.maquinas else None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def preco_total_sugerido(self) -> Decimal:
        """Soma dos preços sugeridos de todas as máquinas no carrinho."""
        return sum((m.preco_venda_sugerido for m in self.maquinas), Decimal("0"))

    def is_ready(self) -> bool:
        """True se todos os dados obrigatórios estiverem preenchidos."""
        return (
            self.cliente  is not None
            and len(self.maquinas) > 0
            and self.pagamento.preco > Decimal("0")
        )

    def reset(self) -> None:
        self.cliente   = None
        self.maquinas  = []
        self.pagamento = PagamentoDraft()