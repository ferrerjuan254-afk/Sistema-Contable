from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, SmallInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base


class Empresa(Base):
    __tablename__ = "empresas"
    __table_args__ = (
        UniqueConstraint("nit", "dv", name="uq_empresa_nit_dv"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    razon_social  = Column(String(200), nullable=False)
    nit           = Column(String(15), nullable=False)
    dv            = Column(String(1),  nullable=False)
    direccion     = Column(String(300))
    id_pais       = Column(SmallInteger, ForeignKey("paises.id_pais"), nullable=True)
    id_departamento = Column(SmallInteger, ForeignKey("departamentos.id_departamento"), nullable=True)
    id_ciudad     = Column(SmallInteger, ForeignKey("ciudades.id_ciudad"), nullable=True)
    ciudad        = Column(String(100))   # texto libre legacy / cache
    telefono      = Column(String(30))
    email         = Column(String(150))
    representante = Column(String(200))
    activa        = Column(Boolean, default=True)
    creada_en     = Column(DateTime, default=datetime.utcnow)

    sedes         = relationship("Sede", back_populates="empresa", cascade="all, delete-orphan")

    @property
    def nit_completo(self) -> str:
        return f"{self.nit}-{self.dv}"

    def __repr__(self):
        return f"<Empresa {self.nit_completo} - {self.razon_social}>"


class Sede(Base):
    __tablename__ = "sedes"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    nombre          = Column(String(150), nullable=False)
    id_pais         = Column(SmallInteger, ForeignKey("paises.id_pais"), nullable=True)
    id_departamento = Column(SmallInteger, ForeignKey("departamentos.id_departamento"), nullable=True)
    id_ciudad       = Column(SmallInteger, ForeignKey("ciudades.id_ciudad"), nullable=True)
    ciudad          = Column(String(100))
    direccion       = Column(String(300))
    telefono        = Column(String(30))
    activa          = Column(Boolean, default=True)
    creada_en       = Column(DateTime, default=datetime.utcnow)

    empresa         = relationship("Empresa", back_populates="sedes")

    def __repr__(self):
        return f"<Sede {self.nombre} - Empresa {self.empresa_id}>"
