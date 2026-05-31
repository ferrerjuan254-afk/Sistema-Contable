from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean,
    ForeignKey, DateTime, Enum, Date, Text, SmallInteger
)
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
import enum


class NaturalezaCuenta(str, enum.Enum):
    DEBITO  = "debito"
    CREDITO = "credito"


class NivelCuenta(str, enum.Enum):
    GRUPO      = "grupo"       # nivel 2
    CUENTA     = "cuenta"      # nivel 3
    SUBCUENTA  = "subcuenta"   # nivel 4
    AUXILIAR   = "auxiliar"    # nivel 5


class ClaseCuenta(str, enum.Enum):
    ACTIVO                    = "activo"
    PASIVO                    = "pasivo"
    PATRIMONIO                = "patrimonio"
    INGRESO                   = "ingreso"
    GASTO                     = "gasto"
    COSTO_DE_VENTA            = "costo de venta"
    COSTO_DE_PRODUCCION       = "costo de produccion"
    CUENTAS_DE_ORDEN_DEUDORAS  = "cuentas de orden deudoras"
    CUENTAS_DE_ORDEN_ACREEDORAS = "cuentas de orden acreedoras"


class TipoCuenta(str, enum.Enum):
    # Activo
    ACTIVO_CORRIENTE              = "activo corriente"
    ACTIVO_NO_CORRIENTE           = "activo no corriente"
    # Pasivo
    PASIVO_CORRIENTE              = "pasivo corriente"
    PASIVO_NO_CORRIENTE           = "pasivo no corriente"
    # Patrimonio
    CAPITAL                       = "capital"
    RESERVAS                      = "reservas"
    RESULTADOS                    = "resultados"
    # Ingresos
    INGRESO_OPERACIONAL           = "ingreso operacional"
    INGRESO_NO_OPERACIONAL        = "ingreso no operacional"
    # Gastos
    GASTO_OPERACIONAL             = "gasto operacional"
    GASTO_NO_OPERACIONAL          = "gasto no operacional"
    # Costos
    COSTO_VENTA                   = "costo de venta"
    COSTO_PRODUCCION              = "costo de produccion"
    # Orden
    ORDEN_DEUDORA                 = "cuentas de orden deudoras"
    ORDEN_ACREEDORA               = "cuentas de orden acreedoras"


class ModuloCuenta(str, enum.Enum):
    EFECTIVO          = "efectivo"           # Caja, bancos
    CUENTAS_COBRAR    = "cuentas por cobrar"
    CUENTAS_PAGAR     = "cuentas por pagar"
    DIFERIDA          = "diferida"
    INVENTARIO        = "inventario"
    NOMINA            = "nomina"
    ACTIVO_FIJO       = "activo fijo"
    GENERAL           = "general"


class EstadoPeriodo(str, enum.Enum):
    ABIERTO  = "abierto"
    CERRADO  = "cerrado"


class EstadoAsiento(str, enum.Enum):
    BORRADOR   = "borrador"
    CONFIRMADO = "confirmado"
    ANULADO    = "anulado"


# ── PUC Contenido (descripción + dinámica en HTML unificados) ─────
class PucContenido(Base):
    """
    Una sola fila por código PUC.
    El campo `contenido` almacena HTML completo que puede incluir
    descripción, sección Débitos, sección Créditos, Cuentas de detalle, etc.
    QTextBrowser lo renderiza directamente sin conversión.
    """
    __tablename__ = "puc_contenido"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    codigo   = Column(String(20), nullable=False, index=True, unique=True)
    contenido = Column(Text, nullable=False)   # HTML completo

    def __repr__(self):
        return f"<PucContenido {self.codigo}>"


# ── Fuentes contables ──────────────────────────────────────────
class TipoFuente(str, enum.Enum):
    COMPRA               = "compra"
    VENTA                = "venta"
    CAUSACION            = "causacion"
    CONSIGNACION         = "consignacion"
    NOTA_DEBITO          = "nota debito"
    NOTA_CREDITO         = "nota credito"
    NOTA_BANCARIA        = "nota bancaria"
    PRESTACIONES_SOCIALES = "prestaciones sociales"
    NOMINA               = "nomina"
    APERTURA             = "apertura"
    CIERRE               = "cierre"
    AJUSTE               = "ajuste"
    OTRO                 = "otro"


class FuenteContable(Base):
    __tablename__ = "fuentes_contables"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    codigo      = Column(String(10), nullable=False, unique=True)
    descripcion = Column(String(200), nullable=False)
    tipo_fuente = Column(Enum(TipoFuente), nullable=False)

    asientos    = relationship("Asiento", back_populates="fuente")

    def __repr__(self):
        return f"<Fuente {self.codigo} - {self.descripcion}>"


# ── Geografía ─────────────────────────────────────────────────
class Pais(Base):
    __tablename__ = "paises"

    id_pais    = Column(SmallInteger, primary_key=True, autoincrement=True)
    codigo_iso = Column(String(3), nullable=False, unique=True)
    nombre     = Column(String(60), nullable=False)
    activo     = Column(Boolean, default=True)

    departamentos = relationship("Departamento", back_populates="pais")

    def __repr__(self):
        return f"<Pais {self.codigo_iso} - {self.nombre}>"


class Departamento(Base):
    __tablename__ = "departamentos"

    id_departamento = Column(SmallInteger, primary_key=True, autoincrement=True)
    id_pais         = Column(SmallInteger, ForeignKey("paises.id_pais"), nullable=False)
    codigo_dane     = Column(Integer, nullable=True)
    nombre          = Column(String(60), nullable=False)

    pais     = relationship("Pais", back_populates="departamentos")
    ciudades = relationship("Ciudad", back_populates="departamento")

    def __repr__(self):
        return f"<Departamento {self.nombre}>"


class Ciudad(Base):
    __tablename__ = "ciudades"

    id_ciudad       = Column(SmallInteger, primary_key=True, autoincrement=True)
    id_departamento = Column(SmallInteger, ForeignKey("departamentos.id_departamento"), nullable=False)
    codigo_dane     = Column(Integer, nullable=True)
    nombre          = Column(String(80), nullable=False)

    departamento = relationship("Departamento", back_populates="ciudades")

    def __repr__(self):
        return f"<Ciudad {self.nombre}>"


# ── Plan de Cuentas (PUC) ──────────────────────────────────────
class PlanCuenta(Base):
    __tablename__ = "plan_cuentas"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    codigo          = Column(String(20), nullable=False)
    nombre          = Column(String(200), nullable=False)
    naturaleza      = Column(Enum(NaturalezaCuenta), nullable=False)
    clase           = Column(Enum(ClaseCuenta), nullable=True)     # activo, pasivo, etc.
    tipo            = Column(Enum(TipoCuenta), nullable=True)      # activo corriente, etc.
    nivel_nombre    = Column(Enum(NivelCuenta), nullable=True)     # grupo, cuenta, subcuenta, auxiliar
    nivel           = Column(Integer, nullable=False)               # 1=clase,2=grupo,3=cuenta,4=subcuenta,5=auxiliar
    cuenta_padre    = Column(String(20), nullable=True)
    acepta_mov      = Column(Boolean, default=True)
    activa          = Column(Boolean, default=True)
    # Retención / Impuesto
    es_retencion    = Column(Boolean, default=False)
    es_impuesto     = Column(Boolean, default=False)
    tarifa_pct      = Column(Numeric(8, 4), nullable=True)          # Ej: 19.0000 para IVA 19%
    # Módulo funcional
    modulo          = Column(Enum(ModuloCuenta), default=ModuloCuenta.GENERAL, nullable=True)

    movimientos     = relationship("Movimiento", back_populates="cuenta")

    def __repr__(self):
        return f"<Cuenta {self.codigo} - {self.nombre}>"


# ── Periodos Contables ──────────────────────────────────────────
class PeriodoContable(Base):
    __tablename__ = "periodos_contables"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id  = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    anio        = Column(Integer, nullable=False)
    mes         = Column(Integer, nullable=False)
    estado      = Column(Enum(EstadoPeriodo), default=EstadoPeriodo.ABIERTO)
    cerrado_en  = Column(DateTime, nullable=True)
    cerrado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    asientos    = relationship("Asiento", back_populates="periodo")

    def __repr__(self):
        return f"<Periodo {self.anio}-{self.mes:02d} [{self.estado}]>"


# ── Asientos Contables ─────────────────────────────────────────
class Asiento(Base):
    __tablename__ = "asientos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id  = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sede_id     = Column(Integer, ForeignKey("sedes.id"), nullable=True)
    periodo_id  = Column(Integer, ForeignKey("periodos_contables.id"), nullable=False)
    fuente_id   = Column(Integer, ForeignKey("fuentes_contables.id"), nullable=True)
    numero      = Column(String(20), nullable=False)
    fecha       = Column(Date, nullable=False)
    descripcion = Column(String(500))
    estado      = Column(Enum(EstadoAsiento), default=EstadoAsiento.BORRADOR)
    creado_en   = Column(DateTime, default=datetime.utcnow)
    creado_por  = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    periodo     = relationship("PeriodoContable", back_populates="asientos")
    fuente      = relationship("FuenteContable", back_populates="asientos")
    movimientos = relationship("Movimiento", back_populates="asiento", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Asiento {self.numero} - {self.fecha}>"


# ── Movimientos (líneas del asiento) ───────────────────────────
class Movimiento(Base):
    __tablename__ = "movimientos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id  = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    asiento_id  = Column(Integer, ForeignKey("asientos.id"), nullable=False)
    cuenta_id   = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=False)
    tercero_id  = Column(Integer, ForeignKey("terceros.id"), nullable=True)
    debito      = Column(Numeric(18, 2), default=0)
    credito     = Column(Numeric(18, 2), default=0)
    descripcion = Column(String(300))

    asiento     = relationship("Asiento", back_populates="movimientos")
    cuenta      = relationship("PlanCuenta", back_populates="movimientos")
    tercero     = relationship("Tercero")

    def __repr__(self):
        return f"<Movimiento Asiento:{self.asiento_id} Cuenta:{self.cuenta_id}>"
