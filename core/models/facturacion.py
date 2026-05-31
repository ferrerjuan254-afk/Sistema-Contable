from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean,
    ForeignKey, DateTime, Enum, Date, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
import enum


class TipoDocumento(str, enum.Enum):
    FACTURA_VENTA       = "factura_venta"
    FACTURA_COMPRA      = "factura_compra"
    NOTA_CREDITO_VENTA  = "nota_credito_venta"
    NOTA_DEBITO_VENTA   = "nota_debito_venta"
    NOTA_CREDITO_COMPRA = "nota_credito_compra"
    NOTA_DEBITO_COMPRA  = "nota_debito_compra"
    COTIZACION          = "cotizacion"
    ORDEN_COMPRA        = "orden_compra"
    REMISION            = "remision"


class EstadoDocumento(str, enum.Enum):
    BORRADOR    = "borrador"
    EMITIDO     = "emitido"
    ANULADO     = "anulado"


class TipoImpuesto(str, enum.Enum):
    IVA          = "iva"
    INC          = "inc"            # Impoconsumo
    RETENCION    = "retencion"
    RETEIVA      = "reteiva"
    RETEICA      = "reteica"
    NINGUNO      = "ninguno"


class UnidadMedida(str, enum.Enum):
    UNIDAD      = "und"
    KILOGRAMO   = "kg"
    GRAMO       = "g"
    LITRO       = "lt"
    METRO       = "mt"
    METRO2      = "m2"
    METRO3      = "m3"
    CAJA        = "caja"
    PAQUETE     = "paquete"
    HORA        = "hora"
    DIA         = "dia"
    MES         = "mes"
    SERVICIO    = "servicio"


# ── Productos / Servicios ──────────────────────────────────────
class Producto(Base):
    __tablename__ = "productos"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    codigo          = Column(String(40), nullable=False)
    nombre          = Column(String(200), nullable=False)
    descripcion     = Column(Text, nullable=True)
    unidad_medida   = Column(Enum(UnidadMedida), default=UnidadMedida.UNIDAD)
    precio_venta    = Column(Numeric(18, 2), default=0)
    precio_compra   = Column(Numeric(18, 2), default=0)
    tipo_impuesto   = Column(Enum(TipoImpuesto), default=TipoImpuesto.IVA)
    tarifa_impuesto = Column(Numeric(6, 4), default=0)   # 0.19 para IVA 19%
    es_servicio     = Column(Boolean, default=False)
    activo          = Column(Boolean, default=True)
    creado_en       = Column(DateTime, default=datetime.utcnow)

    # Cuenta contable para ingresos/gastos (opcional)
    cuenta_ingreso_id = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=True)
    cuenta_gasto_id   = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=True)

    lineas = relationship("LineaDocumento", back_populates="producto")

    def __repr__(self):
        return f"<Producto {self.codigo} - {self.nombre}>"


# ── Consecutivos por tipo de documento ───────────────────────
class Consecutivo(Base):
    __tablename__ = "consecutivos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id  = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    tipo        = Column(Enum(TipoDocumento), nullable=False)
    prefijo     = Column(String(10), default="")
    actual      = Column(Integer, default=0)
    resolucion  = Column(String(100), nullable=True)   # DIAN
    desde       = Column(Integer, nullable=True)
    hasta       = Column(Integer, nullable=True)
    vence       = Column(Date, nullable=True)

    def siguiente(self) -> str:
        self.actual += 1
        return f"{self.prefijo}{self.actual:07d}"


# ── Cabecera del documento ─────────────────────────────────────
class Documento(Base):
    __tablename__ = "documentos"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    sede_id         = Column(Integer, ForeignKey("sedes.id"), nullable=True)
    tipo            = Column(Enum(TipoDocumento), nullable=False)
    numero          = Column(String(20), nullable=False)
    fecha           = Column(Date, nullable=False)
    fecha_vence     = Column(Date, nullable=True)
    tercero_id      = Column(Integer, ForeignKey("terceros.id"), nullable=False)
    # Referencia a documento origen (nota crédito/débito)
    documento_origen_id = Column(Integer, ForeignKey("documentos.id"), nullable=True)
    observaciones   = Column(Text, nullable=True)
    estado          = Column(Enum(EstadoDocumento), default=EstadoDocumento.BORRADOR)

    # Totales (desnormalizados para rendimiento)
    subtotal        = Column(Numeric(18, 2), default=0)
    total_descuento = Column(Numeric(18, 2), default=0)
    total_impuesto  = Column(Numeric(18, 2), default=0)
    total           = Column(Numeric(18, 2), default=0)

    periodo_id      = Column(Integer, ForeignKey("periodos_contables.id"), nullable=True)
    asiento_id      = Column(Integer, ForeignKey("asientos.id"), nullable=True)
    creado_en       = Column(DateTime, default=datetime.utcnow)
    creado_por      = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    tercero         = relationship("Tercero")
    lineas          = relationship(
        "LineaDocumento", back_populates="documento",
        cascade="all, delete-orphan", order_by="LineaDocumento.orden"
    )
    documento_origen = relationship("Documento", remote_side="Documento.id")

    def __repr__(self):
        return f"<Documento {self.tipo.value} {self.numero}>"


# ── Líneas del documento ───────────────────────────────────────
class LineaDocumento(Base):
    __tablename__ = "lineas_documento"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    documento_id    = Column(Integer, ForeignKey("documentos.id"), nullable=False)
    orden           = Column(Integer, default=1)
    producto_id     = Column(Integer, ForeignKey("productos.id"), nullable=True)
    descripcion     = Column(String(300), nullable=False)
    unidad_medida   = Column(Enum(UnidadMedida), default=UnidadMedida.UNIDAD)
    cantidad        = Column(Numeric(14, 4), default=1)
    precio_unitario = Column(Numeric(18, 2), default=0)
    descuento_pct   = Column(Numeric(6, 4), default=0)   # 0.05 = 5%
    descuento_valor = Column(Numeric(18, 2), default=0)
    subtotal        = Column(Numeric(18, 2), default=0)  # sin impuesto
    tipo_impuesto   = Column(Enum(TipoImpuesto), default=TipoImpuesto.IVA)
    tarifa_impuesto = Column(Numeric(6, 4), default=0)
    valor_impuesto  = Column(Numeric(18, 2), default=0)
    total_linea     = Column(Numeric(18, 2), default=0)

    documento       = relationship("Documento", back_populates="lineas")
    producto        = relationship("Producto", back_populates="lineas")

    def __repr__(self):
        return f"<Linea Doc:{self.documento_id} Prod:{self.producto_id}>"
