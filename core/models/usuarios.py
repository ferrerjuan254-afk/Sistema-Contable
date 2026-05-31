from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from datetime import datetime
from core.database import Base
import enum


class RolUsuario(str, enum.Enum):
    ADMIN      = "admin"
    CONTADOR   = "contador"
    AUXILIAR   = "auxiliar"
    SOLO_LECTURA = "solo_lectura"


class Usuario(Base):
    __tablename__ = "usuarios"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id   = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    nombre       = Column(String(150), nullable=False)
    email        = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol          = Column(Enum(RolUsuario), default=RolUsuario.AUXILIAR)
    activo       = Column(Boolean, default=True)
    ultimo_acceso = Column(DateTime, nullable=True)
    creado_en    = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Usuario {self.email} [{self.rol}]>"
