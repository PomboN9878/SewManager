from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database.base import Base


class StatusEstoque:
    EM_ESTOQUE = "EM_ESTOQUE"
    VENDIDO = "VENDIDO"
    RESERVADO = "RESERVADO"


class Maquina(Base):
    __tablename__ = "maquinas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marca = Column(String(100), nullable=False)
    modelo = Column(String(100), nullable=False)
    numero_serie = Column(String(100), unique=True, nullable=True)
    mesa_id = Column(Integer, ForeignKey("mesas.id"), unique=True)
    mesa = relationship("Mesa", back_populates="maquina")
    cor = Column(String(50))
    preco_custo = Column(Float, default=0.0)            # preço de compra
    preco_venda_sugerido = Column(Float, default=0.0)   # preço sugerido
    observacoes = Column(String(500))
    status = Column(String(20), default=StatusEstoque.EM_ESTOQUE, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    item_venda = relationship("ItemVenda", back_populates="maquina", uselist=False)

    def __repr__(self):
        return f"<Maquina id={self.id} {self.marca} {self.modelo} [{self.status}]>"

    @property
    def disponivel(self):
        return self.status == StatusEstoque.EM_ESTOQUE