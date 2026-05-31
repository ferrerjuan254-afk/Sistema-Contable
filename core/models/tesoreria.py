from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean,
    ForeignKey, DateTime, Enum, Date, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
import enum


class TipoCuenta(str, enum.Enum):
    CAJA            = "caja"
    BANCO           = "banco"
    BOLSILLO        = "bolsillo"      # petty cash / fondo menor


class TipoTransaccion(str, enum.Enum):
    INGRESO         = "ingreso"       # recaudo, consignación, cobro
    EGRESO          = "egreso"        # pago, giro, retiro
    TRASLADO        = "traslado"      # entre cuentas propias


class EstadoTransaccion(str, enum.Enum):
    PENDIENTE       = "pendiente"
    APLICADA        = "aplicada"
    ANULADA         = "anulada"


class EstadoConciliacion(str, enum.Enum):
    NO_CONCILIADO   = "no_conciliado"
    CONCILIADO      = "conciliado"
    EN_PROCESO      = "en_proceso"


# ── Cuentas de Caja / Banco ────────────────────────────────────
class CuentaTesoreria(Base):
    __tablename__ = "cuentas_tesoreria"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    tipo            = Column(Enum(TipoCuenta), nullable=False)
    nombre          = Column(String(150), nullable=False)
    # Datos bancarios (solo si tipo=BANCO)
    banco           = Column(String(100), nullable=True)
    numero_cuenta   = Column(String(30),  nullable=True)
    tipo_cuenta_banco = Column(String(30), nullable=True)   # Ahorros / Corriente
    # Cuenta contable asociada (PUC)
    cuenta_puc_id   = Column(Integer, ForeignKey("plan_cuentas.id"), nullable=True)
    saldo_inicial   = Column(Numeric(18, 2), default=0)
    saldo_actual    = Column(Numeric(18, 2), default=0)
    activa          = Column(Boolean, default=True)
    creada_en       = Column(DateTime, default=datetime.utcnow)

    transacciones   = relationship("Transaccion", back_populates="cuenta",
                                   foreign_keys="Transaccion.cuenta_id")

    def __repr__(self):
        return f"<CuentaTesoreria {self.nombre}>"


# ── Transacciones (ingresos / egresos / traslados) ─────────────
class Transaccion(Base):
    __tablename__ = "transacciones_tesoreria"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id      = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    cuenta_id       = Column(Integer, ForeignKey("cuentas_tesoreria.id"), nullable=False)
    # En traslados: cuenta destino
    cuenta_destino_id = Column(Integer, ForeignKey("cuentas_tesoreria.id"), nullable=True)
    tipo            = Column(Enum(TipoTransaccion), nullable=False)
    fecha           = Column(Date, nullable=False)
    concepto        = Column(String(300), nullable=False)
    referencia      = Column(String(80),  nullable=True)   # No. cheque, No. transferencia, etc.
    valor           = Column(Numeric(18, 2), nullable=False)
    tercero_id      = Column(Integer, ForeignKey("terceros.id"), nullable=True)
    # Origen: documento de facturación que generó el pago
    documento_id    = Column(Integer, ForeignKey("documentos.id"), nullable=True)
    # Asiento contable generado
    asiento_id      = Column(Integer, ForeignKey("asientos.id"), nullable=True)
    periodo_id      = Column(Integer, ForeignKey("periodos_contables.id"), nullable=True)
    estado          = Column(Enum(EstadoTransaccion), default=EstadoTransaccion.APLICADA)
    conciliacion    = Column(Enum(EstadoConciliacion),
                             default=EstadoConciliacion.NO_CONCILIADO)
    notas           = Column(Text, nullable=True)
    creada_en       = Column(DateTime, default=datetime.utcnow)
    creada_por      = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    cuenta          = relationship("CuentaTesoreria", back_populates="transacciones",
                                   foreign_keys=[cuenta_id])
    cuenta_destino  = relationship("CuentaTesoreria",
                                   foreign_keys=[cuenta_destino_id])
    tercero         = relationship("Tercero")

    def __repr__(self):
        return f"<Transaccion {self.tipo.value} {self.valor}>"


# ── Extracto Bancario (para conciliación) ─────────────────────
class LineaExtracto(Base):
    __tablename__ = "lineas_extracto"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    cuenta_id       = Column(Integer, ForeignKey("cuentas_tesoreria.id"), nullable=False)
    fecha           = Column(Date, nullable=False)
    descripcion     = Column(String(300), nullable=False)
    referencia      = Column(String(80),  nullable=True)
    debito          = Column(Numeric(18, 2), default=0)
    credito         = Column(Numeric(18, 2), default=0)
    saldo           = Column(Numeric(18, 2), nullable=True)
    conciliado      = Column(Boolean, default=False)
    # Transacción que concilia esta línea
    transaccion_id  = Column(Integer, ForeignKey("transacciones_tesoreria.id"), nullable=True)
    importada_en    = Column(DateTime, default=datetime.utcnow)
