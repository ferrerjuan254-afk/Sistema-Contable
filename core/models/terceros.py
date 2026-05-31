from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
import enum


class TipoTercero(str, enum.Enum):
    CLIENTE    = "cliente"
    PROVEEDOR  = "proveedor"
    EMPLEADO   = "empleado"
    OTRO       = "otro"


class TipoDocumento(str, enum.Enum):
    CC   = "cc"     # Cédula de ciudadanía
    CE   = "ce"     # Cédula de extranjería
    NIT  = "nit"
    PA   = "pa"     # Pasaporte
    TI   = "ti"     # Tarjeta de identidad


class Tercero(Base):
    __tablename__ = "terceros"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    tipo_documento  = Column(Enum(TipoDocumento), nullable=False)
    numero_documento = Column(String(20), nullable=False)
    nombre          = Column(String(200), nullable=False)
    email           = Column(String(150))
    telefono        = Column(String(30))
    direccion       = Column(String(300))
    ciudad          = Column(String(100))

    # Tipos (un tercero puede ser cliente Y proveedor)
    es_cliente      = Column(Boolean, default=False)
    es_proveedor    = Column(Boolean, default=False)
    es_empleado     = Column(Boolean, default=False)

    activo          = Column(Boolean, default=True)
    creado_en       = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    empleado        = relationship("Empleado", back_populates="tercero", uselist=False)

    def __repr__(self):
        return f"<Tercero {self.numero_documento} - {self.nombre}>"
