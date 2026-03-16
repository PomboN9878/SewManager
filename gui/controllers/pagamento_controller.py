"""
PagamentoController — camada entre a GUI e o pagamento_service.

A View NUNCA importa services diretamente; só fala com este controller.

Fluxo:
    PagamentosView  →  PagamentoController  →  pagamento_service  →  Model/DB
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from database.models.pagamento import TipoPagamento


class PagamentoController:

    def __init__(self, session: Session):
        self.session = session

    # ── Inicialização ─────────────────────────────────────────────────────────

    def sincronizar_atrasos(self) -> int:
        """
        Atualiza parcelas vencidas para ATRASADO no banco.
        Deve ser chamado ao abrir a tela de pagamentos.
        """
        from services.pagamento_service import atualizar_status_atrasados
        n = atualizar_status_atrasados(self.session)
        if n:
            self.session.commit()
        return n

    # ── Leitura ───────────────────────────────────────────────────────────────

    def listar_todos(self) -> list[dict]:
        """
        Retorna todos os pagamentos do sistema como lista de dicts normalizados
        para a UI (sem objetos ORM na camada de apresentação).
        """
        from services.venda_service import listar_vendas

        resultado = []
        for venda in listar_vendas(self.session):
            cliente_nome   = venda.cliente.nome if venda.cliente else "—"
            total_parcelas = sum(
                1 for p in venda.pagamentos
                if p.tipo == TipoPagamento.PARCELA
            )
            for p in venda.pagamentos:
                resultado.append(self._para_dict(p, cliente_nome, total_parcelas))
        return resultado

    # ── Escrita ───────────────────────────────────────────────────────────────

    def registrar_pagamento(
        self,
        pagamento_id:   int,
        valor_pago:     Decimal | float | str,
        data_pagamento: datetime | None = None,
        observacoes:    str | None      = None,
    ) -> dict:
        """
        Registra o pagamento e faz commit.
        Retorna o resultado do service:
            {"pagamento": ..., "credito_gerado": Decimal, "redistribuido": bool}
        Levanta ValueError em caso de regra de negócio violada.
        """
        from services.pagamento_service import registrar_pagamento
        resultado = registrar_pagamento(
            self.session,
            pagamento_id=pagamento_id,
            valor_pago=valor_pago,
            data_pagamento=data_pagamento,
            observacoes=observacoes,
        )
        self.session.commit()
        return resultado

    # ── Normalização ORM → dict ───────────────────────────────────────────────

    @staticmethod
    def _para_dict(p, cliente_nome: str, total_parcelas: int) -> dict:
        """Converte ORM Pagamento → dict consumível pela View."""
        venc    = (p.data_vencimento.strftime("%d/%m/%Y")
                   if p.data_vencimento else "—")
        pago_em = (p.data_pagamento.strftime("%d/%m/%Y")
                   if p.data_pagamento else None)
        status  = p.status.value if hasattr(p.status, "value") else str(p.status)
        tipo    = p.tipo.value   if hasattr(p.tipo,   "value") else str(p.tipo)

        return {
            "id":              p.id,
            "cliente":         cliente_nome,
            "venda_id":        p.venda_id,
            "tipo":            tipo,
            "numero_parcela":  p.numero_parcela,
            "total_parcelas":  total_parcelas,
            "valor":           float(p.valor) if p.valor is not None else 0.0,
            "data_vencimento": venc,
            "data_pagamento":  pago_em,
            "status":          status,
            "observacoes":     p.observacoes or "",
        }