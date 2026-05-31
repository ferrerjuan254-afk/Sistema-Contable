from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean,
    ForeignKey, DateTime, Enum, Date
)
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
import enum


class TipoContrato(str, enum.Enum):
    INDEFINIDO  = "indefinido"
    FIJO        = "fijo"
    OBRA        = "obra_labor"
    APRENDIZAJE = "aprendizaje"


class EstadoLiquidacion(str, enum.Enum):
    BORRADOR  = "borrador"
    APROBADA  = "aprobada"
    PAGADA    = "pagada"


class TipoConcepto(str, enum.Enum):
    DEVENGADO  = "devengado"   # Suma al salario
    DEDUCCION  = "deduccion"   # Resta al salario
    APORTE_EMP = "aporte_empleador"  # Solo para SS


# ── Empleados ──────────────────────────────────────────────────
class Empleado(Base):
    __tablename__ = "empleados"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id       = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sede_id          = Column(Integer, ForeignKey("sedes.id"), nullable=True)
    tercero_id       = Column(Integer, ForeignKey("terceros.id"), nullable=False, unique=True)
    cargo            = Column(String(150))
    departamento     = Column(String(100))
    tipo_contrato    = Column(Enum(TipoContrato), nullable=False)
    salario_base     = Column(Numeric(18, 2), nullable=False)
    fecha_ingreso    = Column(Date, nullable=False)
    fecha_retiro     = Column(Date, nullable=True)
    activo           = Column(Boolean, default=True)

    # Entidades de seguridad social
    eps              = Column(String(100))   # Entidad de salud
    fondo_pension    = Column(String(100))
    fondo_cesantias  = Column(String(100))
    arl              = Column(String(100))
    caja_compensacion = Column(String(100))
    nivel_riesgo_arl = Column(Integer, default=1)  # 1-5

    creado_en        = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    tercero          = relationship("Tercero", back_populates="empleado")
    liquidaciones    = relationship("Liquidacion", back_populates="empleado")

    def __repr__(self):
        return f"<Empleado {self.tercero_id} - {self.cargo}>"


# ── Conceptos de Nómina ────────────────────────────────────────
class ConceptoNomina(Base):
    __tablename__ = "conceptos_nomina"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id  = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    codigo      = Column(String(20), nullable=False)
    nombre      = Column(String(150), nullable=False)
    tipo        = Column(Enum(TipoConcepto), nullable=False)
    porcentaje  = Column(Numeric(6, 4),  nullable=True)   # Si aplica %
    monto       = Column(Numeric(14, 2), nullable=True)   # Valor predeterminado si es manual
    es_manual   = Column(Boolean, default=False)           # True = valor manual, False = porcentaje
    activo      = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Concepto {self.codigo} - {self.nombre}>"


# ── Liquidaciones de Nómina ────────────────────────────────────
class Liquidacion(Base):
    __tablename__ = "liquidaciones"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id   = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    empleado_id  = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    periodo_id   = Column(Integer, ForeignKey("periodos_contables.id"), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin    = Column(Date, nullable=False)
    total_devengado  = Column(Numeric(18, 2), default=0)
    total_deduccion  = Column(Numeric(18, 2), default=0)
    neto_pagar       = Column(Numeric(18, 2), default=0)
    estado           = Column(Enum(EstadoLiquidacion), default=EstadoLiquidacion.BORRADOR)
    creada_en        = Column(DateTime, default=datetime.utcnow)

    empleado     = relationship("Empleado", back_populates="liquidaciones")
    detalles     = relationship("DetalleLiquidacion", back_populates="liquidacion", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Liquidacion Emp:{self.empleado_id} Periodo:{self.periodo_id}>"


# ── Detalle de Liquidación ─────────────────────────────────────
class DetalleLiquidacion(Base):
    __tablename__ = "detalle_liquidacion"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    liquidacion_id  = Column(Integer, ForeignKey("liquidaciones.id"), nullable=False)
    concepto_id     = Column(Integer, ForeignKey("conceptos_nomina.id"), nullable=False)
    cantidad        = Column(Numeric(10, 2), default=1)   # Ej: horas extras
    valor_unitario  = Column(Numeric(18, 2), default=0)
    valor_total     = Column(Numeric(18, 2), default=0)

    liquidacion     = relationship("Liquidacion", back_populates="detalles")

    def __repr__(self):
        return f"<Detalle Liq:{self.liquidacion_id} Concepto:{self.concepto_id}>"


# ── Aportes de Seguridad Social ────────────────────────────────
class AportesSeguridadSocial(Base):
    __tablename__ = "aportes_seguridad_social"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id          = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    empleado_id         = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    periodo_id          = Column(Integer, ForeignKey("periodos_contables.id"), nullable=False)

    # Salud
    salud_empleado      = Column(Numeric(18, 2), default=0)   # 4%
    salud_empleador     = Column(Numeric(18, 2), default=0)   # 8.5%

    # Pensión
    pension_empleado    = Column(Numeric(18, 2), default=0)   # 4%
    pension_empleador   = Column(Numeric(18, 2), default=0)   # 12%

    # ARL (solo empleador)
    arl                 = Column(Numeric(18, 2), default=0)   # Según nivel riesgo

    # Parafiscales (solo empleador)
    icbf                = Column(Numeric(18, 2), default=0)   # 3%
    sena                = Column(Numeric(18, 2), default=0)   # 2%
    caja_compensacion   = Column(Numeric(18, 2), default=0)   # 4%

    ibc                 = Column(Numeric(18, 2), default=0)   # Ingreso base de cotización
    creado_en           = Column(DateTime, default=datetime.utcnow)
    empleado            = relationship("Empleado")

    def __repr__(self):
        return f"<SS Emp:{self.empleado_id} Periodo:{self.periodo_id}>"
