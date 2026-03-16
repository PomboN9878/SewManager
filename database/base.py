import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

def get_base_path():
    if getattr(sys, "frozen", False):
        # executável
        return os.path.dirname(sys.executable)
    else:
        # python normal
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
DB_PATH = os.path.join(BASE_DIR, "costura.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def init_db():
    from database.models import cliente, maquina, mesa, venda, item_venda, pagamento
    Base.metadata.create_all(bind=engine)

    from database.events import register_events
    register_events()