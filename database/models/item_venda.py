from sqlalchemy import Column, Integer, Numeric, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from database.base import Base


class ItemVenda(Base):
    """
    Cada linha representa a venda de 1 máquina + 1 mesa juntas.
    Regra de negócio: maquina e mesa são OBRIGATÓRIAS.
    """

    __tablename__ = "itens_venda"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    venda_id   = Column(Integer, ForeignKey("vendas.id"), nullable=False)
    maquina_id = Column(Integer, ForeignKey("maquinas.id"), nullable=False)
    preco_maquina = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        CheckConstraint("preco_maquina >= 0", name="ck_preco_maquina_positivo"),
        UniqueConstraint("maquina_id", name="uq_maquina_por_item_venda"),
    )

    # Relacionamentos
    venda   = relationship("Venda", back_populates="itens")
    maquina = relationship("Maquina", back_populates="item_venda")

    @property
    def subtotal(self):
        return self.preco_maquina

    def __repr__(self) -> str:
        return (
            f"<ItemVenda id={self.id} venda={self.venda_id} "
            f"maquina={self.maquina_id} subtotal={self.subtotal}>"
        )