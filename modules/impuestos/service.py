from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from core.models.impuestos import (
    Retencion, DeclaracionImpuesto,
    TipoRetencion, TipoDeclaracion, EstadoDeclaracion
)
from core.models.facturacion import Documento, LineaDocumento, TipoImpuesto
from core.models.terceros import Tercero
from core.models.contabilidad import PeriodoContable


def _r(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Tarifas legales de referencia (Colombia 2024)
TARIFAS_RTEFUENTE = {
    TipoRetencion.HONORARIOS:      Decimal("0.10"),
    TipoRetencion.SERVICIOS:       Decimal("0.04"),
    TipoRetencion.COMPRAS:         Decimal("0.025"),
    TipoRetencion.ARRENDAMIENTOS:  Decimal("0.035"),
    TipoRetencion.COMISIONES:      Decimal("0.10"),
    TipoRetencion.INTERESES:       Decimal("0.07"),
    TipoRetencion.DIVIDENDOS:      Decimal("0.00"),
    TipoRetencion.OTROS:           Decimal("0.035"),
}


class ImpuestosService:

    def __init__(self, db: Session, empresa_id: int):
        self.db         = db
        self.empresa_id = empresa_id

    # ══════════════════════════════════════════════════════════
    # Periodos
    # ══════════════════════════════════════════════════════════
    def listar_periodos(self) -> List[PeriodoContable]:
        return (
            self.db.query(PeriodoContable)
            .filter(PeriodoContable.empresa_id == self.empresa_id)
            .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
            .all()
        )

    # ══════════════════════════════════════════════════════════
    # Retenciones
    # ══════════════════════════════════════════════════════════
    def listar_retenciones(
        self,
        periodo_id: int = None,
        tipo: TipoRetencion = None,
        es_practicada: bool = None,
        incluidas: bool = None,
    ) -> List[Retencion]:
        q = (
            self.db.query(Retencion)
            .options(joinedload(Retencion.tercero))
            .filter(Retencion.empresa_id == self.empresa_id)
        )
        if periodo_id:
            q = q.filter(Retencion.periodo_id == periodo_id)
        if tipo:
            q = q.filter(Retencion.tipo == tipo)
        if es_practicada is not None:
            q = q.filter(Retencion.es_practicada == es_practicada)
        if incluidas is not None:
            q = q.filter(Retencion.incluida == incluidas)
        return q.order_by(Retencion.fecha.desc()).all()

    def crear_retencion(self, datos: dict) -> Retencion:
        r = Retencion(empresa_id=self.empresa_id, **datos)
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return r

    def eliminar_retencion(self, ret_id: int):
        r = self.db.query(Retencion).filter(
            Retencion.id == ret_id,
            Retencion.empresa_id == self.empresa_id,
            Retencion.incluida == False
        ).first()
        if not r:
            raise ValueError("Retención no encontrada o ya incluida en una declaración.")
        self.db.delete(r)
        self.db.commit()

    def calcular_valor_retencion(self, tipo: TipoRetencion,
                                 base: Decimal) -> Decimal:
        tarifa = TARIFAS_RTEFUENTE.get(tipo, Decimal("0"))
        return _r(base * tarifa)

    # ══════════════════════════════════════════════════════════
    # Resumenes desde facturación
    # ══════════════════════════════════════════════════════════
    def resumen_iva_periodo(self, fecha_inicio: date,
                            fecha_fin: date) -> dict:
        """IVA generado (ventas) e IVA descontable (compras) del período."""
        from core.models.facturacion import TipoDocumento, EstadoDocumento

        docs_ventas = (
            self.db.query(LineaDocumento)
            .join(Documento)
            .filter(
                Documento.empresa_id == self.empresa_id,
                Documento.tipo.in_([
                    TipoDocumento.FACTURA_VENTA,
                    TipoDocumento.NOTA_DEBITO_VENTA,
                ]),
                Documento.estado == EstadoDocumento.EMITIDO,
                Documento.fecha.between(fecha_inicio, fecha_fin),
                LineaDocumento.tipo_impuesto == TipoImpuesto.IVA,
            )
            .all()
        )
        docs_compras = (
            self.db.query(LineaDocumento)
            .join(Documento)
            .filter(
                Documento.empresa_id == self.empresa_id,
                Documento.tipo.in_([
                    TipoDocumento.FACTURA_COMPRA,
                    TipoDocumento.NOTA_DEBITO_COMPRA,
                ]),
                Documento.estado == EstadoDocumento.EMITIDO,
                Documento.fecha.between(fecha_inicio, fecha_fin),
                LineaDocumento.tipo_impuesto == TipoImpuesto.IVA,
            )
            .all()
        )

        nc_ventas = (
            self.db.query(LineaDocumento)
            .join(Documento)
            .filter(
                Documento.empresa_id == self.empresa_id,
                Documento.tipo == TipoDocumento.NOTA_CREDITO_VENTA,
                Documento.estado == EstadoDocumento.EMITIDO,
                Documento.fecha.between(fecha_inicio, fecha_fin),
                LineaDocumento.tipo_impuesto == TipoImpuesto.IVA,
            )
            .all()
        )

        iva_generado    = sum(Decimal(str(l.valor_impuesto or 0)) for l in docs_ventas)
        iva_nc_ventas   = sum(Decimal(str(l.valor_impuesto or 0)) for l in nc_ventas)
        iva_descontable = sum(Decimal(str(l.valor_impuesto or 0)) for l in docs_compras)

        iva_neto = iva_generado - iva_nc_ventas - iva_descontable
        return {
            "iva_generado":     _r(iva_generado),
            "iva_nc_ventas":    _r(iva_nc_ventas),
            "iva_descontable":  _r(iva_descontable),
            "iva_neto":         _r(iva_neto),
            "saldo_pagar":      _r(max(iva_neto, Decimal("0"))),
            "saldo_favor":      _r(max(-iva_neto, Decimal("0"))),
            "n_facturas_venta": len(docs_ventas),
            "n_facturas_compra":len(docs_compras),
        }

    def resumen_retenciones_periodo(self, periodo_id: int) -> dict:
        practicadas = self.listar_retenciones(periodo_id=periodo_id, es_practicada=True)
        recibidas   = self.listar_retenciones(periodo_id=periodo_id, es_practicada=False)
        total_pract = sum(Decimal(str(r.valor or 0)) for r in practicadas)
        total_recib = sum(Decimal(str(r.valor or 0)) for r in recibidas)
        return {
            "practicadas": practicadas,
            "recibidas":   recibidas,
            "total_practicadas": _r(total_pract),
            "total_recibidas":   _r(total_recib),
            "saldo_pagar":       _r(max(total_pract - total_recib, Decimal("0"))),
        }

    # ══════════════════════════════════════════════════════════
    # Declaraciones
    # ══════════════════════════════════════════════════════════
    def listar_declaraciones(self, tipo: TipoDeclaracion = None) -> List[DeclaracionImpuesto]:
        q = (
            self.db.query(DeclaracionImpuesto)
            .filter(DeclaracionImpuesto.empresa_id == self.empresa_id)
        )
        if tipo:
            q = q.filter(DeclaracionImpuesto.tipo == tipo)
        return q.order_by(
            DeclaracionImpuesto.fecha_fin.desc()
        ).all()

    def crear_declaracion(self, datos: dict) -> DeclaracionImpuesto:
        d = DeclaracionImpuesto(empresa_id=self.empresa_id, **datos)
        self.db.add(d)
        self.db.commit()
        self.db.refresh(d)
        return d

    def actualizar_declaracion(self, dec_id: int,
                               datos: dict) -> DeclaracionImpuesto:
        d = self.db.query(DeclaracionImpuesto).filter(
            DeclaracionImpuesto.id == dec_id,
            DeclaracionImpuesto.empresa_id == self.empresa_id
        ).first()
        if not d:
            raise ValueError("Declaración no encontrada.")
        for k, v in datos.items():
            setattr(d, k, v)
        # Recalcular saldo
        d.saldo_pagar = max(
            d.impuesto_cargo - d.descuentos - d.anticipos + d.sancion + d.intereses,
            Decimal("0")
        )
        d.saldo_favor = max(
            d.anticipos + d.descuentos - d.impuesto_cargo,
            Decimal("0")
        )
        self.db.commit()
        return d

    def presentar_declaracion(self, dec_id: int,
                              numero_formulario: str,
                              fecha_presentacion: date) -> DeclaracionImpuesto:
        d = self.db.query(DeclaracionImpuesto).filter(
            DeclaracionImpuesto.id == dec_id,
            DeclaracionImpuesto.empresa_id == self.empresa_id
        ).first()
        if not d:
            raise ValueError("Declaración no encontrada.")
        if d.estado != EstadoDeclaracion.BORRADOR:
            raise ValueError("Solo se pueden presentar declaraciones en borrador.")
        d.numero_formulario  = numero_formulario
        d.fecha_presentacion = fecha_presentacion
        d.estado             = EstadoDeclaracion.PRESENTADA
        # Marcar retenciones incluidas
        self.db.query(Retencion).filter(
            Retencion.declaracion_id == dec_id
        ).update({"incluida": True})
        self.db.commit()
        return d

    def registrar_pago(self, dec_id: int,
                       fecha_pago: date) -> DeclaracionImpuesto:
        d = self.db.query(DeclaracionImpuesto).filter(
            DeclaracionImpuesto.id == dec_id,
            DeclaracionImpuesto.empresa_id == self.empresa_id
        ).first()
        if not d:
            raise ValueError("Declaración no encontrada.")
        d.fecha_pago = fecha_pago
        d.estado     = EstadoDeclaracion.PAGADA
        self.db.commit()
        return d

    def buscar_terceros(self, criterio: str) -> List[Tercero]:
        term = f"%{criterio}%"
        return (
            self.db.query(Tercero)
            .filter(
                Tercero.empresa_id == self.empresa_id,
                Tercero.activo     == True,
                (Tercero.nombre.ilike(term) |
                 Tercero.numero_documento.ilike(term))
            )
            .order_by(Tercero.nombre).limit(25).all()
        )
