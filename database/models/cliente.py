from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database.base import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    documento = Column(String(30), unique=True, nullable=True)  # CPF / CNPJ
    telefone = Column(String(20))
    observacoes = Column(String(500))
    criado_em = Column(DateTime, default=datetime.utcnow)

    vendas = relationship("Venda", back_populates="cliente", lazy="dynamic")

    def __repr__(self):
        return f"<Cliente> i{self.id} nome ={self.nome!r}>"

    @property
    def total_divida(self):
        return sum(v.saldo_devedor for v in self.vendas if v.status != "QUITADA")