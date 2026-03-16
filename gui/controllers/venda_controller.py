"""
VendaController — camada entre a GUI e os services.

Responsabilidades:
- Chamar services (criar_venda_avista / criar_venda_parcelada / saldo_venda)
- Fazer commit
- Buscar listas para preencher a UI (clientes, máquinas, vendas)
- Normalizar ORM → dict para a camada de apresentação

A View NUNCA importa services diretamente; só fala com este controller.

Fluxo:
    View  →  VendaController  →  Service  →  Model/DB
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from gui.drafts.venda_draft import ClienteDraft, MaquinaDraft, VendaDraft


class VendaController:

    def __init__(self, session: Session):
        self.session = session

    # ── Leitura: clientes e máquinas (para NovaVendaView) ────────────────────

    def listar_clientes(self, filtro: str = "") -> list[ClienteDraft]:
        """Retorna clientes filtrados por nome ou documento."""
        from services.cliente_service import listar_clientes
        rows   = listar_clientes(self.session)
        result = [
            ClienteDraft(
                id=c.id, nome=c.nome,
                documento=c.documento or "—",
                telefone=c.telefone   or "—",
            )
            for c in rows
        ]
        if filtro:
            t      = filtro.lower()
            result = [c for c in result
                      if t in c.nome.lower() or t in c.documento.lower()]
        return result

    def listar_maquinas(self, filtro: str = "") -> list[MaquinaDraft]:
        """Retorna máquinas em estoque, filtradas por marca/modelo/série."""
        from services.estoque_service import listar_maquinas
        rows   = listar_maquinas(self.session, apenas_disponiveis=True)
        result = [
            MaquinaDraft(
                id=m.id, marca=m.marca, modelo=m.modelo,
                numero_serie=m.numero_serie or "—",
                mesa=m.mesa.modelo if m.mesa else "—",
                preco_venda_sugerido=Decimal(str(m.preco_venda_sugerido or 0)),
            )
            for m in rows
        ]
        if filtro:
            t      = filtro.lower()
            result = [m for m in result
                      if t in m.marca.lower()
                      or t in m.modelo.lower()
                      or t in m.numero_serie.lower()]
        return result

    # ── Leitura: vendas (para VendasView) ────────────────────────────────────

    def listar_vendas(
        self,
        filtro_status: str | None = None,
        filtro_tipo:   str | None = None,
        busca:         str        = "",
    ) -> list[dict]:
        """
        Retorna todas as vendas como lista de dicts normalizados para a UI.
        Filtros opcionais:
            filtro_status : "ABERTA" | "QUITADA"
            filtro_tipo   : "AVISTA" | "PARCELADO"
            busca         : substring do nome do cliente
        """
        from services.venda_service import listar_vendas, saldo_venda
        from database.models.venda import StatusVenda

        status_enum = StatusVenda(filtro_status) if filtro_status else None
        vendas      = listar_vendas(self.session, status=status_enum)

        resultado = []
        for v in vendas:
            saldo = saldo_venda(self.session, v.id)
            d     = self._venda_para_dict(v, saldo)
            if filtro_tipo and d["tipo_pagamento"] != filtro_tipo:
                continue
            if busca and busca.lower() not in d["cliente"].lower():
                continue
            resultado.append(d)

        return resultado

    # ── Normalização ORM → dict ───────────────────────────────────────────────

    @staticmethod
    def _venda_para_dict(v, saldo: dict) -> dict:
        """Converte ORM Venda + saldo_dict → dict consumível pela View."""
        data_str = v.data.strftime("%d/%m/%Y") if v.data else "—"
        tipo     = v.tipo_pagamento.value if hasattr(v.tipo_pagamento, "value") else str(v.tipo_pagamento)
        status   = v.status.value         if hasattr(v.status,         "value") else str(v.status)

        total_parcelas = sum(
            1 for p in v.pagamentos
            if getattr(p.tipo, "value", p.tipo) == "PARCELA"
        )

        pagamentos = []
        for p in v.pagamentos:
            t    = getattr(p.tipo,   "value", str(p.tipo))
            s    = getattr(p.status, "value", str(p.status))
            venc = p.data_vencimento.strftime("%d/%m/%Y") if p.data_vencimento else "—"
            pago = p.data_pagamento.strftime("%d/%m/%Y")  if p.data_pagamento  else None
            pagamentos.append({
                "id":              p.id,
                "tipo":            t,
                "numero_parcela":  p.numero_parcela,
                "total_parcelas":  total_parcelas,
                "valor":           float(p.valor) if p.valor is not None else 0.0,
                "data_vencimento": venc,
                "data_pagamento":  pago,
                "status":          s,
                "observacoes":     p.observacoes or "",
            })

        itens = []
        for iv in v.itens:
            maq  = iv.maquina
            mesa = maq.mesa if maq else None
            itens.append({
                "maquina": f"{maq.marca} {maq.modelo}" if maq else "—",
                "mesa":    mesa.modelo if mesa else "—",
                "preco":   float(iv.preco_maquina) if iv.preco_maquina else 0.0,
            })

        return {
            "id":             v.id,
            "cliente":        v.cliente.nome if v.cliente else "—",
            "cliente_id":     v.cliente_id,
            "data":           data_str,
            "tipo_pagamento": tipo,
            "valor_total":    float(v.valor_total) if v.valor_total else 0.0,
            "total_pago":     float(saldo.get("total_pago",    0)),
            "saldo_devedor":  float(saldo.get("saldo_devedor", 0)),
            "num_parcelas":   v.num_parcelas,
            "status":         status,
            "observacoes":    v.observacoes or "",
            "itens":          itens,
            "pagamentos":     pagamentos,
        }

    # ── Escrita: cliente ──────────────────────────────────────────────────────

    def criar_cliente(
        self, nome: str, documento: str | None, telefone: str | None
    ) -> ClienteDraft:
        """Cria o cliente no banco, faz commit e retorna um ClienteDraft."""
        from services.cliente_service import criar_cliente
        c = criar_cliente(
            self.session,
            nome=nome,
            documento=documento or None,
            telefone=telefone   or None,
        )
        self.session.commit()
        return ClienteDraft(
            id=c.id, nome=c.nome,
            documento=c.documento or "—",
            telefone=c.telefone   or "—",
        )

    # ── Escrita: venda ────────────────────────────────────────────────────────

    def finalizar_venda(self, draft: VendaDraft) -> None:
        """
        Executa a venda com base no VendaDraft, faz commit.
        Lança ValueError se os dados estiverem incompletos ou se houver
        violação de regra de negócio no service.
        """
        if not draft.is_ready():
            raise ValueError("Dados da venda incompletos.")

        item = {
            "maquina_id":    draft.maquina.id,
            "preco_maquina": draft.pagamento.preco,
        }
        pg = draft.pagamento

        if pg.tipo == "avista":
            from services.venda_service import criar_venda_avista
            criar_venda_avista(
                self.session,
                cliente_id=draft.cliente.id,
                itens=[item],
            )
        else:
            from services.venda_service import criar_venda_parcelada
            criar_venda_parcelada(
                self.session,
                cliente_id=draft.cliente.id,
                itens=[item],
                valor_entrada=pg.entrada,
                num_parcelas=pg.parcelas,
                intervalo_dias=pg.intervalo,
            )

        self.session.commit()

    # ── Escrita: pagamento (a partir da VendasView) ───────────────────────────

    def registrar_pagamento(
        self,
        pagamento_id:   int,
        valor_pago:     float,
        data_pagamento: datetime | None = None,
        observacoes:    str | None      = None,
    ) -> dict:
        """
        Delega ao pagamento_service, faz commit.
        Retorna {"pagamento", "credito_gerado", "redistribuido"}.
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