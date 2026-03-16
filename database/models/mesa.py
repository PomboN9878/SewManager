from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database.base import Base


class StatusEstoque:
    EM_ESTOQUE = "EM_ESTOQUE"
    VENDIDO = "VENDIDO"
    RESERVADO = "RESERVADO"


class Mesa(Base):
    __tablename__ = "mesas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    modelo = Column(String(100), nullable=False)
    material = Column(String(100))           # madeira, aço, etc.
    cor = Column(String(50))
    observacoes = Column(String(500))
    status = Column(String(20), default=StatusEstoque.EM_ESTOQUE, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    maquina = relationship("Maquina", back_populates="mesa", uselist=False)

    def __repr__(self):
        return f"<Mesa id={self.id} {self.modelo} [{self.status}]>"

    @property
    def disponivel(self):
        return self.status == StatusEstoque.EM_ESTOQUE