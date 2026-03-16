"""
gui/components/__init__.py
Exporta os modals para uso simplificado nas views.

Uso nas views:
    from gui.components import MaquinaFormModal, MesaFormModal
    from gui.components import ClienteFormModal, HistoricoModal
"""

from .estoque_modals import MaquinaFormModal, MesaFormModal
from .clientes_modals import ClienteFormModal, HistoricoModal

__all__ = [
    "MaquinaFormModal",
    "MesaFormModal",
    "ClienteFormModal",
    "HistoricoModal",
]