"""
Representa o estado transitório de uma venda em criação na GUI.
Substitui o _dados: dict sem tipo por uma estrutura validável.
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
    numero_serie:         str  = "—"
    mesa:                 str  = "—"
    preco_venda_sugerido: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class PagamentoDraft:
    tipo:       str     = "avista"           # "avista" | "parcelado"
    preco:      Decimal = field(default_factory=lambda: Decimal("0"))
    entrada:    Decimal = field(default_factory=lambda: Decimal("0"))
    parcelas:   int     = 1
    intervalo:  int     = 30                 # dias entre parcelas


@dataclass
class VendaDraft:
    cliente:   ClienteDraft   | None = None
    maquina:   MaquinaDraft   | None = None
    pagamento: PagamentoDraft        = field(default_factory=PagamentoDraft)

    def is_ready(self) -> bool:
        """True se todos os dados obrigatórios estiverem preenchidos."""
        return (
            self.cliente  is not None
            and self.maquina  is not None
            and self.pagamento.preco > Decimal("0")
        )

    def reset(self) -> None:
        self.cliente   = None
        self.maquina   = None
        self.pagamento = PagamentoDraft()