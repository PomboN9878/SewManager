from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import StrEnum
from database.base import Base


class TipoPagamento(StrEnum):
    PARCELADO = "PARCELADO"
    ENTRADA   = "ENTRADA"
    PARCELA   = "PARCELA"
    AVISTA    = "AVISTA"


class StatusPagamento(StrEnum):
    PENDENTE = "PENDENTE"
    PAGO     = "PAGO"
    ATRASADO = "ATRASADO"


class Pagamento(Base):
    __tablename__ = "pagamentos"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    venda_id       = Column(Integer, ForeignKey("vendas.id"), nullable=False)
    tipo           = Column(String(20), nullable=False)
    numero_parcela = Column(Integer)
    valor          = Column(Numeric(10, 2), nullable=False)
    data_vencimento = Column(DateTime)
    data_pagamento  = Column(DateTime)
    status          = Column(String(20), default=StatusPagamento.PENDENTE, nullable=False)
    observacoes     = Column(String(255))
    criado_em       = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("valor >= 0", name="ck_valor_nao_negativo"),
    )

    venda = relationship("Venda", back_populates="pagamentos")

    @property
    def pago(self) -> bool:
        return self.data_pagamento is not None

    def registrar_pagamento(self, data: datetime = None) -> None:
        """Marca este pagamento como pago."""
        self.data_pagamento = data or datetime.utcnow()
        self.status         = StatusPagamento.PAGO

    def __repr__(self) -> str:
        return (
            f"<Pagamento id={self.id} venda={self.venda_id} "
            f"tipo={self.tipo} valor={self.valor} status={self.status}>"
        )