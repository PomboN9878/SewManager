"""
Serviço de clientes.

Regras:
- Documento é opcional
- Sem foto
- Não faz commit — responsabilidade do controller/caller
- SQLAlchemy 2.x (select + execute)
- Exceções de domínio
- Aggregates no banco para resumo financeiro
"""
from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database.models import Cliente, Venda, Pagamento, StatusVenda


class ClienteNaoEncontrado(Exception):
    """HTTP 404"""

class DocumentoDuplicado(Exception):
    """HTTP 409"""

class CampoNaoPermitido(Exception):
    """HTTP 422"""


def _buscar_documento(
    session: Session,
    documento: str,
    excluir_id: Optional[int] = None,
) -> Optional[Cliente]:
    """Retorna cliente com esse documento, opcionalmente excluindo um id."""
    stmt = select(Cliente).where(Cliente.documento == documento)
    if excluir_id is not None:
        stmt = stmt.where(Cliente.id != excluir_id)
    return session.execute(stmt).scalar_one_or_none()


def criar_cliente(
    session: Session,
    nome: str,
    documento: Optional[str] = None,
    telefone: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> Cliente:
    if documento and _buscar_documento(session, documento):
        raise DocumentoDuplicado(f"Documento '{documento}' já cadastrado.")

    cliente = Cliente(
        nome=nome,
        documento=documento,
        telefone=telefone,
        observacoes=observacoes,
    )
    session.add(cliente)
    return cliente


def listar_clientes(
    session: Session,
    busca: Optional[str] = None,
) -> List[Cliente]:
    stmt = select(Cliente)
    if busca:
        termo = f"%{busca}%"
        stmt = stmt.where(
            or_(
                Cliente.nome.ilike(termo),
                Cliente.documento.ilike(termo),
            )
        )
    stmt = stmt.order_by(Cliente.nome)
    return list(session.execute(stmt).scalars().all())


def buscar_cliente(session: Session, cliente_id: int) -> Cliente:
    cliente = session.get(Cliente, cliente_id)
    if not cliente:
        raise ClienteNaoEncontrado(f"Cliente id={cliente_id} não encontrado.")
    return cliente


def atualizar_cliente(
    session: Session,
    cliente_id: int,
    nome: Optional[str] = None,
    documento: Optional[str] = None,
    telefone: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> Cliente:
    cliente = buscar_cliente(session, cliente_id)

    if documento is not None:
        if _buscar_documento(session, documento, excluir_id=cliente_id):
            raise DocumentoDuplicado(f"Documento '{documento}' já pertence a outro cliente.")
        cliente.documento = documento

    if nome        is not None: cliente.nome        = nome
    if telefone    is not None: cliente.telefone    = telefone
    if observacoes is not None: cliente.observacoes = observacoes

    return cliente


def resumo_cliente(session: Session, cliente_id: int) -> dict:
    cliente = buscar_cliente(session, cliente_id)

    # Agrega pagamentos por venda ANTES do join
    pagamentos_sub = (
        select(
            Pagamento.venda_id,
            func.sum(Pagamento.valor).label("total_pago"),
        )
        .where(Pagamento.data_pagamento.is_not(None))
        .group_by(Pagamento.venda_id)
        .subquery()
    )

    stmt_totais = (
        select(
            func.coalesce(func.sum(Venda.valor_total), 0).label("total_comprado"),
            func.coalesce(func.sum(pagamentos_sub.c.total_pago), 0).label("total_pago"),
            func.coalesce(
                func.sum(Venda.valor_total) - func.sum(pagamentos_sub.c.total_pago), 0
            ).label("total_em_aberto"),
        )
        .outerjoin(pagamentos_sub, pagamentos_sub.c.venda_id == Venda.id)
        .where(Venda.cliente_id == cliente_id)
    )

    stmt_contagens = (
        select(
            func.count(Venda.id).filter(Venda.status == StatusVenda.QUITADA).label("quitadas"),
            func.count(Venda.id).filter(Venda.status == StatusVenda.ABERTA).label("abertas"),
        )
        .where(Venda.cliente_id == cliente_id)
    )

    totais    = session.execute(stmt_totais).one()
    contagens = session.execute(stmt_contagens).one()

    return {
        "cliente_id":      cliente.id,
        "nome":            cliente.nome,
        "total_comprado":  totais.total_comprado,
        "total_pago":      totais.total_pago,
        "total_em_aberto": totais.total_em_aberto,
        "vendas_quitadas": contagens.quitadas,
        "vendas_abertas":  contagens.abertas,
    }