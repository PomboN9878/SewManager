"""
Serviço de vendas.

Regras de negócio garantidas aqui:
- Máquina e mesa devem estar EM_ESTOQUE antes de vender
- Ao vender: ambas passam para VENDIDO
- Mesa não tem preço próprio: o preço do par é preco_maquina
- À vista: 1 pagamento, venda já sai QUITADA
- Parcelada: 1 pagamento de entrada (opcional) + N parcelas distribuídas

Regras de arquitetura:
- Não faz commit — responsabilidade do controller/caller
- Usa session.get() (API moderna do SQLAlchemy 2.x)
- Enums usados de forma consistente (TipoPagamento, StatusVenda, StatusPagamento)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from database.models import (
    Venda, ItemVenda, Pagamento, Cliente, Maquina, Mesa,
    TipoPagamento, StatusVenda, StatusPagamento,
)
from database.models.maquina import StatusEstoque


# ──────────────────────────── VALIDAÇÃO INTERNA ──────────────────────────────

def _construir_itens(
    session: Session,
    venda_id: int,
    itens: list[dict],
) -> tuple[list[ItemVenda], Decimal]:
    """
    Valida, cria os ItemVenda e atualiza o estoque.
    Retorna (lista_de_itens, valor_total).
    Não faz flush/commit.
    """
    if not itens:
        raise ValueError("A venda deve ter pelo menos 1 item.")

    resultado: list[ItemVenda] = []
    valor_total = Decimal("0")

    for item in itens:
        # SELECT ... FOR UPDATE — trava a linha até o commit/rollback
        maquina = session.get(Maquina, item["maquina_id"], with_for_update=True)
        if not maquina:
            raise ValueError(f"Máquina id={item['maquina_id']} não encontrada.")
        if maquina.status != StatusEstoque.EM_ESTOQUE:
            raise ValueError(
                f"Máquina '{maquina.marca} {maquina.modelo}' "
                f"não está disponível (status: {maquina.status})."
            )

        mesa = maquina.mesa
        if mesa.status != StatusEstoque.EM_ESTOQUE:
            raise ValueError(
                f"Mesa '{mesa.modelo}' vinculada a esta máquina "
                f"não está disponível (status: {mesa.status})."
            )

        # Decimal desde a entrada — nunca float
        preco = Decimal(str(item["preco_maquina"]))
        valor_total += preco

        iv = ItemVenda(
            venda_id=venda_id,
            maquina_id=maquina.id,
            preco_maquina=preco,
        )
        session.add(iv)

        maquina.status = StatusEstoque.VENDIDO
        mesa.status    = StatusEstoque.VENDIDO
        resultado.append(iv)

    return resultado, round(valor_total, 2)


# ────────────────────────── CRIAÇÃO DE VENDAS ────────────────────────────────

def criar_venda_avista(
    session: Session,
    cliente_id: int,
    itens: list[dict],
    data: datetime = None,
    observacoes: str = None,
) -> Venda:
    cliente = session.get(Cliente, cliente_id)
    if not cliente:
        raise ValueError(f"Cliente id={cliente_id} não encontrado.")

    agora = data or datetime.utcnow()

    venda = Venda(
        cliente_id=cliente_id,
        valor_total=Decimal("0"),
        tipo_pagamento=TipoPagamento.AVISTA,
        valor_entrada=Decimal("0"),
        num_parcelas=1,
        status=StatusVenda.ABERTA,
        observacoes=observacoes,
        data=agora,
    )
    session.add(venda)
    session.flush()

    _, valor_total = _construir_itens(session, venda.id, itens)

    venda.valor_total  = valor_total
    venda.valor_entrada = valor_total

    session.add(Pagamento(
        venda_id=venda.id,
        tipo=TipoPagamento.AVISTA,
        valor=valor_total,
        data_vencimento=agora,
        data_pagamento=agora,
        status=StatusPagamento.PAGO,
    ))
    session.flush()
    venda.verificar_e_quitar()
    return venda


def criar_venda_parcelada(
    session: Session,
    cliente_id: int,
    itens: list[dict],
    valor_entrada: float | Decimal,
    num_parcelas: int,
    data_primeira_parcela: datetime = None,
    intervalo_dias: int = 30,
    data: datetime = None,
    observacoes: str = None,
) -> Venda:
    if num_parcelas < 1:
        raise ValueError("Número de parcelas deve ser >= 1.")

    cliente = session.get(Cliente, cliente_id)
    if not cliente:
        raise ValueError(f"Cliente id={cliente_id} não encontrado.")

    # Normaliza entrada para Decimal imediatamente
    valor_entrada = Decimal(str(valor_entrada))
    agora = data or datetime.utcnow()

    venda = Venda(
        cliente_id=cliente_id,
        valor_total=Decimal("0"),
        tipo_pagamento=TipoPagamento.PARCELADO,
        valor_entrada=valor_entrada,
        num_parcelas=num_parcelas,
        status=StatusVenda.ABERTA,
        observacoes=observacoes,
        data=agora,
    )
    session.add(venda)
    session.flush()

    _, valor_total = _construir_itens(session, venda.id, itens)
    venda.valor_total = valor_total

    if valor_entrada < Decimal("0") or valor_entrada > valor_total:
        raise ValueError(
            f"Valor de entrada ({valor_entrada}) inválido para total ({valor_total})."
        )

    # Entrada imediata
    if valor_entrada > Decimal("0"):
        session.add(Pagamento(
            venda_id=venda.id,
            tipo=TipoPagamento.ENTRADA,
            valor=round(valor_entrada, 2),
            data_vencimento=agora,
            data_pagamento=agora,
            status=StatusPagamento.PAGO,
        ))

    # Parcelas — última absorve arredondamento
    saldo       = round(valor_total - valor_entrada, 2)
    val_parcela = round(saldo / num_parcelas, 2)
    val_ultima  = round(saldo - val_parcela * (num_parcelas - 1), 2)
    data_ref    = data_primeira_parcela or (agora + timedelta(days=intervalo_dias))

    for n in range(1, num_parcelas + 1):
        valor = val_ultima if n == num_parcelas else val_parcela
        session.add(Pagamento(
            venda_id=venda.id,
            tipo=TipoPagamento.PARCELA,
            numero_parcela=n,
            valor=valor,
            data_vencimento=data_ref + timedelta(days=intervalo_dias * (n - 1)),
            status=StatusPagamento.PENDENTE,
        ))

    session.flush()
    venda.verificar_e_quitar()
    return venda


# ──────────────────────────────── CONSULTAS ──────────────────────────────────

def buscar_venda(session: Session, venda_id: int) -> Venda:
    v = session.get(Venda, venda_id)
    if not v:
        raise ValueError(f"Venda id={venda_id} não encontrada.")
    return v


def listar_vendas(
    session: Session,
    cliente_id: int = None,
    status: StatusVenda = None,   # CORREÇÃO: era str, aceitava qualquer coisa
) -> list[Venda]:
    q = session.query(Venda)
    if cliente_id:
        q = q.filter_by(cliente_id=cliente_id)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(Venda.data.desc()).all()


def saldo_venda(session: Session, venda_id: int) -> dict:
    """Snapshot financeiro de uma venda."""
    v = buscar_venda(session, venda_id)

    parcelas_pendentes = [p for p in v.pagamentos if p.status == StatusPagamento.PENDENTE]
    parcelas_pagas     = [p for p in v.pagamentos if p.status == StatusPagamento.PAGO]

    return {
        "venda_id":           v.id,
        "cliente_id":         v.cliente_id,
        "valor_total":        v.valor_total,
        "total_pago":         v.total_pago,
        "saldo_devedor":      v.saldo_devedor,
        "status":             v.status,
        "tipo_pagamento":     v.tipo_pagamento,
        "num_parcelas":       v.num_parcelas,
        "parcelas_pagas":     len(parcelas_pagas),
        "parcelas_pendentes": len(parcelas_pendentes),
        "proxima_parcela":    min(
            (p.data_vencimento for p in parcelas_pendentes if p.data_vencimento),
            default=None,
        ),
    }