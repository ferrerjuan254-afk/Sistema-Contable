from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean,
    ForeignKey, DateTime, Enum, Date, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
import enum


class TipoDeclaracion(str, enum.Enum):
    RETENCION_FUENTE = "retencion_fuente"   # Ret. en la fuente mensual
    IVA              = "iva"                 # Bimestral / cuatrimestral / anual
    ICA              = "ica"                 # Industria y comercio (bimestral / anual)
    RENTA            = "renta"               # Anual
    CREE             = "cree"                # Si aplica
    GMF              = "gmf"                 # 4×1000
    INC              = "inc"                 # Impoconsumo


class EstadoDeclaracion(str, enum.Enum):
    BORRADOR    = "borrador"
    PRESENTADA  = "presentada"
    PAGADA      = "pagada"
    EN_FIRME    = "en_firme"


class TipoRetencion(str, enum.Enum):
    SALARIOS            = "salarios"
    HONORARIOS          = "honorarios"
    SERVICIOS           = "servicios"
    COMPRAS             = "compras"
    ARRENDAMIENTOS      = "arrendamientos"
    DIVIDENDOS          = "dividendos"
    INTERESES           = "intereses"
    COMISIONES          = "comisiones"
    OTROS               = "otros"
    # Reteiva
    RETEIVA             = "reteiva"
    # Reteica
    RETEICA             = "reteica"


# ── Retenciones practicadas / recibidas ───────────────────────
class Retencion(Base):
    __tablename__ = "retenciones"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    tipo            = Column(Enum(TipoRetencion), nullable=False)
    # practicada = nosotros retenemos al tercero; recibida = nos retienen a nosotros
    es_practicada   = Column(Boolean, default=True)
    fecha           = Column(Date, nullable=False)
    tercero_id      = Column(Integer, ForeignKey("terceros.id"), nullable=True)
    base_gravable   = Column(Numeric(18, 2), nullable=False)
    tarifa          = Column(Numeric(8, 6), nullable=False)   # 0.035 = 3.5%
    valor           = Column(Numeric(18, 2), nullable=False)
    concepto        = Column(String(300), nullable=True)
    documento_id    = Column(Integer, ForeignKey("documentos.id"), nullable=True)
    periodo_id      = Column(Integer, ForeignKey("periodos_contables.id"), nullable=True)
    declaracion_id  = Column(Integer, ForeignKey("declaraciones_impuesto.id"), nullable=True)
    incluida        = Column(Boolean, default=False)   # ya incluida en declaración
    creada_en       = Column(DateTime, default=datetime.utcnow)

    tercero         = relationship("Tercero")

    def __repr__(self):
        return f"<Retencion {self.tipo.value} ${self.valor}>"


# ── Declaración de impuesto ────────────────────────────────────
class DeclaracionImpuesto(Base):
    __tablename__ = "declaraciones_impuesto"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    tipo            = Column(Enum(TipoDeclaracion), nullable=False)
    periodo_id      = Column(Integer, ForeignKey("periodos_contables.id"), nullable=True)
    # Para declaraciones que abarcan más de un mes (bimestre, cuatrimestre, año)
    fecha_inicio    = Column(Date, nullable=False)
    fecha_fin       = Column(Date, nullable=False)
    fecha_vence     = Column(Date, nullable=True)
    fecha_presentacion = Column(Date, nullable=True)
    fecha_pago      = Column(Date, nullable=True)
    # Valores de la declaración
    base_gravable   = Column(Numeric(18, 2), default=0)
    impuesto_cargo  = Column(Numeric(18, 2), default=0)    # impuesto determinado
    descuentos      = Column(Numeric(18, 2), default=0)
    anticipos       = Column(Numeric(18, 2), default=0)    # anticipos / retenciones a favor
    saldo_pagar     = Column(Numeric(18, 2), default=0)
    saldo_favor     = Column(Numeric(18, 2), default=0)
    sancion         = Column(Numeric(18, 2), default=0)
    intereses       = Column(Numeric(18, 2), default=0)
    # Formulario
    numero_formulario = Column(String(30), nullable=True)
    estado          = Column(Enum(EstadoDeclaracion), default=EstadoDeclaracion.BORRADOR)
    notas           = Column(Text, nullable=True)
    creada_en       = Column(DateTime, default=datetime.utcnow)

    retenciones     = relationship("Retencion",
                                   primaryjoin="Retencion.declaracion_id==DeclaracionImpuesto.id",
                                   foreign_keys="Retencion.declaracion_id")

    def __repr__(self):
        return f"<Declaracion {self.tipo.value} {self.fecha_inicio}→{self.fecha_fin}>"
