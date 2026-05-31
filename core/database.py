from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config.settings import DATABASE_URL


# ── Base declarativa compartida por todos los modelos ──────────
class Base(DeclarativeBase):
    pass


# ── Engine y fábrica de sesiones ───────────────────────────────
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Detecta conexiones caídas
    pool_recycle=3600,       # Renueva conexiones cada hora
    echo=False,              # True para debug SQL
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session():
    """Entrega una sesión y la cierra al terminar."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Crea todas las tablas si no existen (uso inicial / desarrollo)."""
    from core.models import empresa, contabilidad, terceros, nomina, facturacion, tesoreria  # noqa
    Base.metadata.create_all(bind=engine)
