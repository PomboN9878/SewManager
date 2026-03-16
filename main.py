import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.base import init_db, SessionLocal
from gui.main_window import MainWindow


def main():
    print("Inicializando banco de dados...")
    init_db()
    print("Banco OK")

    # Cria a session uma única vez para toda a aplicação
    session = SessionLocal()
    print("Session criada OK")

    try:
        app = MainWindow(session=session)
        app.mainloop()
    finally:
        # Garante que a session é fechada mesmo se a janela travar
        session.close()
        print("Session encerrada")


if __name__ == "__main__":
    main()