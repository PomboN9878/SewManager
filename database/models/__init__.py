"""
database/models/__init__.py
─────────────────────────────────────────────────────────────────
Exporta todos os models e constantes do domínio em um único lugar.

Ordem de importação respeita dependências:
  pagamento  (define TipoPagamento — sem deps internas)
  cliente    (sem deps internas)
  maquina    (define StatusEstoque — sem deps internas)
  mesa       (sem deps internas)
  venda      (depende de TipoPagamento de pagamento)
  item_venda (depende de Maquina, Mesa, Venda)

Uso nos services:
  from database.models import Cliente, Venda, TipoPagamento, StatusVenda, ...
"""

# ── Constantes / enums ────────────────────────────────────────────────────────
from database.models.pagamento import TipoPagamento, StatusPagamento
from database.models.maquina import StatusEstoque
from database.models.venda import StatusVenda

# ── Entidades (models SQLAlchemy) ─────────────────────────────────────────────
from database.models.cliente import Cliente
from database.models.maquina import Maquina
from database.models.mesa import Mesa
from database.models.venda import Venda
from database.models.item_venda import ItemVenda
from database.models.pagamento import Pagamento

# ── Exportações explícitas ────────────────────────────────────────────────────
__all__ = [
    # Entidades
    "Cliente",
    "Maquina",
    "Mesa",
    "Venda",
    "ItemVenda",
    "Pagamento",
    # Constantes de domínio
    "TipoPagamento",    # AVISTA | PARCELADO | ENTRADA | PARCELA  (fonte: pagamento.py)
    "StatusPagamento",  # PENDENTE | PAGO | ATRASADO
    "StatusEstoque",    # EM_ESTOQUE | VENDIDO | RESERVADO
    "StatusVenda",      # ABERTA | QUITADA | CANCELADA
]