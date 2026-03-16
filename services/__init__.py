from services.estoque_service import (
    adicionar_maquina, listar_maquinas, buscar_maquina, atualizar_maquina,
    adicionar_mesa, listar_mesas, buscar_mesa, atualizar_mesa,
    resumo_estoque,
)
from services.cliente_service import (
    criar_cliente, listar_clientes, buscar_cliente, atualizar_cliente,
    resumo_cliente,
)
from services.venda_service import (
    criar_venda_avista, criar_venda_parcelada,
    buscar_venda, listar_vendas, saldo_venda,
)
from services.pagamento_service import (
    registrar_pagamento,
    parcelas_em_aberto, parcelas_atrasadas, historico_pagamentos,
)

__all__ = [
    # estoque
    "adicionar_maquina", "listar_maquinas", "buscar_maquina", "atualizar_maquina",
    "adicionar_mesa", "listar_mesas", "buscar_mesa", "atualizar_mesa",
    "resumo_estoque",
    # clientes
    "criar_cliente", "listar_clientes", "buscar_cliente", "atualizar_cliente",
    "resumo_cliente",
    # vendas
    "criar_venda_avista", "criar_venda_parcelada",
    "buscar_venda", "listar_vendas", "saldo_venda",
    # pagamentos
    "registrar_pagamento",
    "parcelas_em_aberto", "parcelas_atrasadas", "historico_pagamentos",
]