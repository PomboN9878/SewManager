from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from database.base import Base
from database.models.pagamento import TipoPagamento


class StatusVenda(StrEnum):
    ABERTA    = "ABERTA"
    QUITADA   = "QUITADA"
    CANCELADA = "CANCELADA"


class Venda(Base):
    __tablename__ = "vendas"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    data       = Column(DateTime, default=datetime.utcnow)

    valor_total    = Column(Numeric(10, 2), nullable=False)
    tipo_pagamento = Column(String(20), nullable=False)
    valor_entrada  = Column(Numeric(10, 2), default=Decimal("0"))
    num_parcelas   = Column(Integer, default=1)

    status      = Column(String(20), default=StatusVenda.ABERTA, nullable=False)
    observacoes = Column(String(500))
    criado_em   = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    cliente    = relationship("Cliente", back_populates="vendas")
    itens      = relationship("ItemVenda", back_populates="venda", cascade="all, delete-orphan")
    pagamentos = relationship("Pagamento", back_populates="venda", cascade="all, delete-orphan")

    # Propriedades calculadas

    @property
    def total_pago(self) -> Decimal:
        """
        CORREÇÃO: retorna Decimal puro.
        sum() sobre uma lista vazia retorna int(0); forçamos Decimal("0")
        para manter consistência de tipo em todas as situações.
        """
        valores = [p.valor for p in self.pagamentos if p.data_pagamento is not None]
        return sum(valores, Decimal("0"))

    @property
    def saldo_devedor(self) -> Decimal:
        """
        CORREÇÃO: Decimal("0") em vez de 0.0 (float).
        Misturar Decimal e float gera TypeError no Python 3.
        """
        return max(self.valor_total - self.total_pago, Decimal("0"))

    @property
    def quitada(self) -> bool:
        return self.total_pago >= self.valor_total

    def verificar_e_quitar(self) -> None:
        if self.status == StatusVenda.CANCELADA:
            return  # venda cancelada nunca muda de status automaticamente

        if self.quitada:
            self.status = StatusVenda.QUITADA
        else:
            # Reabre caso tenha havido estorno
            if self.status == StatusVenda.QUITADA:
                self.status = StatusVenda.ABERTA

    def __repr__(self) -> str:
        return (
            f"<Venda id={self.id} cliente_id={self.cliente_id} "
            f"total={self.valor_total} status={self.status}>"
        )