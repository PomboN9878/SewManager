import customtkinter as ctk

from gui.components.sidebar import Sidebar
from gui.views.dashboard_view import DashboardView
from gui.views.clientes_view import ClientesView
from gui.views.estoque_view import EstoqueView
from gui.views.nova_venda_view import NovaVendaView
from gui.views.vendas_view import VendasView
from gui.views.pagamentos_view import PagamentosView

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# Mapa de view_name → classe (adicionar aqui quando criar as outras views)
VIEW_REGISTRY = {
    "dashboard": DashboardView,
    "clientes":    ClientesView,
    "estoque":     EstoqueView,
    "nova_venda":  NovaVendaView,
    "vendas":      VendasView,
    "pagamentos":  PagamentosView,
}

PLACEHOLDER_NAMES = {
    "clientes":   "Clientes",
    "estoque":    "Estoque",
    "nova_venda": "Nova Venda",
    "vendas":     "Vendas",
    "pagamentos": "Pagamentos",
}


class PlaceholderView(ctk.CTkFrame):
    """View temporária para telas ainda não implementadas."""

    def __init__(self, master, title=""):
        super().__init__(master, fg_color="#F4F5F8")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family="Georgia", size=26, weight="bold"),
            text_color="#1C1F2E",
        ).grid(row=0, column=0)

        ctk.CTkLabel(
            self,
            text="Em construção",
            font=ctk.CTkFont(size=13),
            text_color="#8B90A8",
        ).grid(row=1, column=0)


class MainWindow(ctk.CTk):

    def __init__(self, session=None):
        super().__init__()

        self.session = session

        self.title("SewManager")
        self.geometry("1280x660")
        self.minsize(960, 600)
        self.configure(fg_color="#F4F5F8")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = Sidebar(self, on_select=self.switch_view)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        # Container das views
        self.container = ctk.CTkFrame(self, fg_color="#F4F5F8", corner_radius=0)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.current_view = None

        # Abre no dashboard
        self.switch_view("dashboard")

    def switch_view(self, view_name: str):
        if self.current_view:
            self.current_view.destroy()

        # Sincroniza estado ativo no sidebar
        self.sidebar.set_active(view_name)

        # Instancia a view correta
        if view_name in VIEW_REGISTRY:
            view_class = VIEW_REGISTRY[view_name]
            self.current_view = view_class(self.container, session=self.session)
        else:
            title = PLACEHOLDER_NAMES.get(view_name, view_name.replace("_", " ").title())
            self.current_view = PlaceholderView(self.container, title=title)

        self.current_view.grid(row=0, column=0, sticky="nsew")