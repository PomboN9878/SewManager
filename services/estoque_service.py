"""
Serviço de estoque: máquinas e mesas.

Regras:
- Não faz commit — responsabilidade do controller/caller
- Usa session.get() (API moderna do SQLAlchemy 2.x)
"""
from sqlalchemy.orm import Session

from database.models.maquina import Maquina
from database.models.mesa import Mesa
from database.models.maquina import StatusEstoque


# ─────────────────────────────── MÁQUINAS ────────────────────────────────────

def adicionar_maquina(
    session: Session,
    marca: str,
    modelo: str,
    mesa_id: int,
    numero_serie: str = None,
    cor: str = None,
    preco_custo: float = 0.0,
    preco_venda_sugerido: float = 0.0,
    observacoes: str = None,
) -> Maquina:
    if numero_serie:
        numero_serie = numero_serie.strip()

    if not numero_serie or numero_serie == "-":
        numero_serie = None

    if numero_serie is not None:
        existe = (
            session.query(Maquina)
            .filter(Maquina.numero_serie == numero_serie)
            .first()
        )

        if existe:
            raise ValueError(f"Número de série '{numero_serie}' já cadastrado.")

    mesa = buscar_mesa(session, mesa_id)

    if mesa.status != StatusEstoque.EM_ESTOQUE:
        raise ValueError(f"Mesa id={mesa_id} não está disponível.")

    maquina = Maquina(
        marca=marca,
        modelo=modelo,
        mesa_id=mesa_id,
        numero_serie=numero_serie,
        cor=cor,
        preco_custo=preco_custo,
        preco_venda_sugerido=preco_venda_sugerido,
        observacoes=observacoes,
    )

    session.add(maquina)
    return maquina


def listar_maquinas(session: Session, apenas_disponiveis: bool = False) -> list[Maquina]:
    q = session.query(Maquina)
    if apenas_disponiveis:
        q = q.filter(Maquina.status == StatusEstoque.EM_ESTOQUE)
    return q.order_by(Maquina.id).all()


def buscar_maquina(session: Session, maquina_id: int) -> Maquina:
    m = session.get(Maquina, maquina_id)
    if not m:
        raise ValueError(f"Máquina id={maquina_id} não encontrada.")
    return m


def atualizar_maquina(session: Session, maquina_id: int, **campos) -> Maquina:
    m = buscar_maquina(session, maquina_id)
    permitidos = {"marca", "modelo", "numero_serie", "cor",
                  "preco_custo", "preco_venda_sugerido", "observacoes"}

    if "numero_serie" in campos and campos["numero_serie"]:
        existe = (
            session.query(Maquina)
            .filter(Maquina.numero_serie == campos["numero_serie"])
            .filter(Maquina.id != maquina_id)
            .first()
        )
        if existe:
            raise ValueError(f"Número de série '{campos['numero_serie']}' já cadastrado.")

    for campo, valor in campos.items():
        if campo not in permitidos:
            raise ValueError(f"Campo '{campo}' não permitido em atualizar_maquina.")
        setattr(m, campo, valor)

    return m

# ─────────────────────────────────  MESAS  ───────────────────────────────────
# Mesas não têm preço próprio — são vendidas junto com a máquina.

def adicionar_mesa(
    session: Session,
    modelo: str,
    material: str = None,
    cor: str = None,
    observacoes: str = None,
) -> Mesa:
    mesa = Mesa(
        modelo=modelo,
        material=material,
        cor=cor,
        observacoes=observacoes,
    )
    session.add(mesa)
    return mesa


def listar_mesas(
    session: Session,
    apenas_disponiveis: bool = False,
    apenas_sem_vinculo: bool = False,
) -> list[Mesa]:
    q = session.query(Mesa)
    if apenas_disponiveis:
        q = q.filter(Mesa.status == StatusEstoque.EM_ESTOQUE)
    if apenas_sem_vinculo:
        # Retorna somente mesas que NÃO têm nenhuma máquina apontando para elas
        q = q.filter(~Mesa.maquina.has())
    return q.order_by(Mesa.id).all()


def buscar_mesa(session: Session, mesa_id: int) -> Mesa:
    m = session.get(Mesa, mesa_id)
    if not m:
        raise ValueError(f"Mesa id={mesa_id} não encontrada.")
    return m


def atualizar_mesa(session: Session, mesa_id: int, **campos) -> Mesa:
    m = buscar_mesa(session, mesa_id)
    permitidos = {"modelo", "material", "cor", "observacoes"}
    for campo, valor in campos.items():
        if campo not in permitidos:
            raise ValueError(f"Campo '{campo}' não permitido em atualizar_mesa.")
        setattr(m, campo, valor)
    return m


# ──────────────────────────────── RESUMO ─────────────────────────────────────

def resumo_estoque(session: Session) -> dict:
    total_maquinas  = session.query(Maquina).count()
    disp_maquinas   = session.query(Maquina).filter_by(status=StatusEstoque.EM_ESTOQUE).count()
    total_mesas     = session.query(Mesa).count()
    disp_mesas      = session.query(Mesa).filter_by(status=StatusEstoque.EM_ESTOQUE).count()
    return {
        "maquinas_total":       total_maquinas,
        "maquinas_disponiveis": disp_maquinas,
        "maquinas_vendidas":    total_maquinas - disp_maquinas,
        "mesas_total":          total_mesas,
        "mesas_disponiveis":    disp_mesas,
        "mesas_vendidas":       total_mesas - disp_mesas,
    }