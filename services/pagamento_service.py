"""
Serviço de pagamentos.

Regras de negócio garantidas aqui:
- Não permite pagar uma parcela já paga
- Pagamento acima do saldo total → gera crédito registrado no cliente
- Pagamento abaixo do valor esperado → redistribui o saldo devedor nas parcelas restantes
- Atualiza status da venda para QUITADA automaticamente quando saldo = 0
- Detecta e persiste parcelas atrasadas (PENDENTE + vencida → ATRASADO)

Regras de arquitetura:
- Não faz commit — responsabilidade do controller/caller
- Usa select() (API moderna do SQLAlchemy 2.x)
- datetime com timezone (UTC) — sem naive datetimes
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Pagamento, Venda
from database.models.pagamento import StatusPagamento, TipoPagamento


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """datetime aware em UTC — substitui o deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


def _to_decimal(value) -> Decimal:
    """Converte qualquer entrada numérica para Decimal sem imprecisão de float."""
    return Decimal(str(value))


def _parcelas_pendentes(venda: Venda, ignorar_id: int | None = None) -> list[Pagamento]:
    """Parcelas do tipo PARCELA ainda não pagas, em ordem de vencimento."""
    return [
        p for p in venda.pagamentos
        if p.status == StatusPagamento.PENDENTE
        and p.tipo  == TipoPagamento.PARCELA
        and p.id    != ignorar_id
    ]


# ── Registrar pagamento ───────────────────────────────────────────────────────

def registrar_pagamento(
    session:        Session,
    pagamento_id:   int,
    valor_pago:     Decimal | float | str,
    data_pagamento: datetime | None = None,
    observacoes:    str | None = None,
) -> dict:
    """
    Registra o pagamento de uma parcela.

    Retorna um dict com o resultado:
        {
            "pagamento":      Pagamento,
            "credito_gerado": Decimal,   # > 0 se pagou além do saldo
            "redistribuido":  bool,      # True se as demais parcelas foram ajustadas
        }

    Casos tratados:
        valor == parcela.valor  → pagamento exato, sem redistribuição
        valor <  parcela.valor  → redistribui o saldo restante nas demais parcelas
        valor >  saldo_total    → quita tudo e registra crédito ao cliente
        valor >  parcela.valor
        mas <= saldo_total      → redistribui o excedente nas demais parcelas
    """
    valor_pago = _to_decimal(valor_pago)

    pagamento = session.get(Pagamento, pagamento_id)
    if not pagamento:
        raise ValueError(f"Pagamento id={pagamento_id} não encontrado.")
    if pagamento.status == StatusPagamento.PAGO:
        raise ValueError(f"Pagamento id={pagamento_id} já foi registrado.")
    if valor_pago <= Decimal("0"):
        raise ValueError("Valor pago deve ser maior que zero.")

    venda = pagamento.venda
    agora = data_pagamento or _utcnow()

    # Registra o pagamento com o valor real recebido
    pagamento.valor          = round(valor_pago, 2)
    pagamento.data_pagamento = agora
    pagamento.status         = StatusPagamento.PAGO
    if observacoes:
        pagamento.observacoes = observacoes

    # Novo saldo após este pagamento (saldo_devedor já re-calcula sobre pagamentos)
    novo_saldo    = _to_decimal(venda.saldo_devedor)
    credito       = Decimal("0")
    redistribuido = False

    if novo_saldo < Decimal("0"):
        # Pagou além do saldo total — quita o restante e registra crédito
        credito = abs(novo_saldo)
        _quitar_parcelas_restantes(venda, ignorar_id=pagamento_id, quando=agora)
        _registrar_credito(session, venda, credito, agora)

    elif novo_saldo > Decimal("0"):
        # Ainda há saldo — redistribui entre as parcelas pendentes
        pendentes = _parcelas_pendentes(venda, ignorar_id=pagamento_id)
        if pendentes:
            _redistribuir_saldo(novo_saldo, pendentes)
            redistribuido = True

    venda.verificar_e_quitar()

    return {
        "pagamento":      pagamento,
        "credito_gerado": credito,
        "redistribuido":  redistribuido,
    }


def _redistribuir_saldo(novo_saldo: Decimal, pendentes: list[Pagamento]) -> None:
    """
    Redistribui `novo_saldo` igualmente entre as parcelas pendentes.
    A última parcela absorve o centavo de arredondamento.
    """
    n           = len(pendentes)
    val_parcela = round(novo_saldo / n, 2)
    val_ultima  = round(novo_saldo - val_parcela * (n - 1), 2)

    for i, p in enumerate(pendentes):
        p.valor = val_ultima if i == n - 1 else val_parcela


def _quitar_parcelas_restantes(
    venda: Venda, ignorar_id: int, quando: datetime
) -> None:
    """Marca todas as parcelas pendentes como pagas com valor zero."""
    for p in _parcelas_pendentes(venda, ignorar_id=ignorar_id):
        p.valor          = Decimal("0")
        p.status         = StatusPagamento.PAGO
        p.data_pagamento = quando


def _registrar_credito(
    session: Session, venda: Venda, valor: Decimal, quando: datetime
) -> Pagamento:
    """
    Cria um registro de crédito para o excedente pago.
    Evita que dinheiro desapareça do sistema.
    """
    credito = Pagamento(
        venda_id        = venda.id,
        tipo            = TipoPagamento.CREDITO,
        valor           = round(valor, 2),
        data_pagamento  = quando,
        data_vencimento = quando,
        status          = StatusPagamento.PAGO,
        observacoes     = "Crédito gerado por pagamento acima do saldo",
    )
    session.add(credito)
    return credito


# ── Atualizar atrasos ─────────────────────────────────────────────────────────

def atualizar_status_atrasados(session: Session) -> int:
    """
    Persiste o status ATRASADO para parcelas PENDENTES com vencimento no passado.
    Deve ser chamado ao abrir a tela de pagamentos.
    Retorna a quantidade de parcelas atualizadas.
    """
    hoje = _utcnow()
    stmt = (
        select(Pagamento)
        .where(
            Pagamento.status          == StatusPagamento.PENDENTE,
            Pagamento.data_vencimento <  hoje,
        )
    )
    atrasadas = session.execute(stmt).scalars().all()
    for p in atrasadas:
        p.status = StatusPagamento.ATRASADO
    return len(atrasadas)


# ── Consultas ─────────────────────────────────────────────────────────────────

def parcelas_em_aberto(
    session:    Session,
    venda_id:   int | None = None,
    cliente_id: int | None = None,
) -> list[Pagamento]:
    """Parcelas PENDENTE ou ATRASADO, ordenadas por vencimento."""
    stmt = (
        select(Pagamento)
        .where(Pagamento.status.in_([
            StatusPagamento.PENDENTE,
            StatusPagamento.ATRASADO,
        ]))
        .order_by(Pagamento.data_vencimento)
    )
    if venda_id:
        stmt = stmt.where(Pagamento.venda_id == venda_id)
    if cliente_id:
        stmt = stmt.join(Venda).where(Venda.cliente_id == cliente_id)

    return session.execute(stmt).scalars().all()


def parcelas_atrasadas(session: Session) -> list[Pagamento]:
    """Parcelas com status ATRASADO, ordenadas por vencimento."""
    stmt = (
        select(Pagamento)
        .where(Pagamento.status == StatusPagamento.ATRASADO)
        .order_by(Pagamento.data_vencimento)
    )
    return session.execute(stmt).scalars().all()


def historico_pagamentos(session: Session, venda_id: int) -> list[Pagamento]:
    """Todos os pagamentos de uma venda, em ordem cronológica."""
    stmt = (
        select(Pagamento)
        .where(Pagamento.venda_id == venda_id)
        .order_by(Pagamento.data_vencimento)
    )
    return session.execute(stmt).scalars().all()