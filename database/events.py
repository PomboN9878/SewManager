from sqlalchemy import event
from database.models.pagamento import Pagamento

def register_events():
    @event.listens_for(Pagamento, "after_insert")
    @event.listens_for(Pagamento, "after_update")
    def _auto_quitar(mapper, connection, target):
        if target.venda:
            target.venda.verificar_e_quitar()