from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_

from core.models.contabilidad import (
    PlanCuenta, Movimiento, Asiento, PeriodoContable,
    EstadoAsiento, ClaseCuenta, NaturalezaCuenta
)
from core.models.facturacion import (
    Documento, LineaDocumento,
    TipoDocumento, EstadoDocumento
)
from core.models.terceros import Tercero


def _r(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


class ReportesService:

    def __init__(self, db: Session, empresa_id: int):
        self.db         = db
        self.empresa_id = empresa_id

    def listar_periodos(self) -> List[PeriodoContable]:
        return (
            self.db.query(PeriodoContable)
            .filter(PeriodoContable.empresa_id == self.empresa_id)
            .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
            .all()
        )

    # ══════════════════════════════════════════════════════════
    # Libro Mayor — saldos por cuenta en un rango de fechas
    # ══════════════════════════════════════════════════════════
    def libro_mayor(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        codigo_inicio: str = "",
        codigo_fin: str = "9999999",
    ) -> List[dict]:
        """
        Devuelve saldo inicial, movimientos del período y saldo final
        por cada cuenta que tenga movimientos en el rango.
        """
        # Movimientos del período
        movs = (
            self.db.query(
                PlanCuenta.id.label("cuenta_id"),
                PlanCuenta.codigo,
                PlanCuenta.nombre,
                PlanCuenta.naturaleza,
                func.sum(Movimiento.debito).label("debitos"),
                func.sum(Movimiento.credito).label("creditos"),
            )
            .join(Movimiento, Movimiento.cuenta_id == PlanCuenta.id)
            .join(Asiento, Asiento.id == Movimiento.asiento_id)
            .filter(
                PlanCuenta.empresa_id  == self.empresa_id,
                Asiento.empresa_id     == self.empresa_id,
                Asiento.estado         == EstadoAsiento.CONFIRMADO,
                Asiento.fecha.between(fecha_inicio, fecha_fin),
            )
            .group_by(
                PlanCuenta.id, PlanCuenta.codigo,
                PlanCuenta.nombre, PlanCuenta.naturaleza
            )
            .order_by(PlanCuenta.codigo)
            .all()
        )

        # Saldo anterior (acumulado antes de fecha_inicio)
        saldos_ant = {}
        ant_rows = (
            self.db.query(
                Movimiento.cuenta_id,
                func.sum(Movimiento.debito).label("db"),
                func.sum(Movimiento.credito).label("cr"),
            )
            .join(Asiento, Asiento.id == Movimiento.asiento_id)
            .join(PlanCuenta, PlanCuenta.id == Movimiento.cuenta_id)
            .filter(
                PlanCuenta.empresa_id == self.empresa_id,
                Asiento.empresa_id    == self.empresa_id,
                Asiento.estado        == EstadoAsiento.CONFIRMADO,
                Asiento.fecha         < fecha_inicio,
            )
            .group_by(Movimiento.cuenta_id)
            .all()
        )
        for row in ant_rows:
            saldos_ant[row.cuenta_id] = (_r(row.db), _r(row.cr))

        resultado = []
        for m in movs:
            db_ant, cr_ant = saldos_ant.get(m.cuenta_id, (Decimal("0"), Decimal("0")))
            nat = m.naturaleza.value if hasattr(m.naturaleza, "value") else str(m.naturaleza)
            if nat == "debito":
                saldo_ant = db_ant - cr_ant
            else:
                saldo_ant = cr_ant - db_ant

            debitos  = _r(m.debitos)
            creditos = _r(m.creditos)

            if nat == "debito":
                saldo_final = saldo_ant + debitos - creditos
            else:
                saldo_final = saldo_ant + creditos - debitos

            resultado.append({
                "cuenta_id":   m.cuenta_id,
                "codigo":      m.codigo,
                "nombre":      m.nombre,
                "naturaleza":  nat,
                "saldo_ant":   saldo_ant,
                "debitos":     debitos,
                "creditos":    creditos,
                "saldo_final": saldo_final,
            })

        return resultado

    # ══════════════════════════════════════════════════════════
    # Balance de Comprobación (8 columnas)
    # ══════════════════════════════════════════════════════════
    def balance_comprobacion(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> Tuple[List[dict], dict]:
        filas = self.libro_mayor(fecha_inicio, fecha_fin)
        totales = {
            "saldo_ant_db":  Decimal("0"),
            "saldo_ant_cr":  Decimal("0"),
            "mov_db":        Decimal("0"),
            "mov_cr":        Decimal("0"),
            "saldo_fin_db":  Decimal("0"),
            "saldo_fin_cr":  Decimal("0"),
        }
        for f in filas:
            sa = f["saldo_ant"]
            totales["saldo_ant_db"] += max(sa, Decimal("0"))
            totales["saldo_ant_cr"] += max(-sa, Decimal("0"))
            totales["mov_db"]       += f["debitos"]
            totales["mov_cr"]       += f["creditos"]
            sf = f["saldo_final"]
            totales["saldo_fin_db"] += max(sf, Decimal("0"))
            totales["saldo_fin_cr"] += max(-sf, Decimal("0"))
        return filas, totales

    # ══════════════════════════════════════════════════════════
    # Estado de Resultados
    # ══════════════════════════════════════════════════════════
    def estado_resultados(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> dict:
        filas = self.libro_mayor(fecha_inicio, fecha_fin)

        def _suma_clase(clase_val: str) -> Decimal:
            total = Decimal("0")
            for f in filas:
                cuenta = self.db.get(PlanCuenta, f["cuenta_id"])
                if not cuenta:
                    continue
                clase = cuenta.clase.value if (cuenta.clase and hasattr(cuenta.clase, "value")) else str(cuenta.clase or "")
                if clase == clase_val:
                    total += f["saldo_final"]
            return _r(total)

        ingresos_op    = _suma_clase("ingreso")
        ingresos_no_op = Decimal("0")  # separar si hay cuentas marcadas
        costo_venta    = _suma_clase("costo de venta")
        gasto_op       = _suma_clase("gasto")
        costo_prod     = _suma_clase("costo de produccion")

        utilidad_bruta  = ingresos_op - costo_venta - costo_prod
        utilidad_op     = utilidad_bruta + ingresos_no_op - gasto_op
        utilidad_neta   = utilidad_op   # simplificado (sin impuesto de renta)

        return {
            "fecha_inicio":    fecha_inicio,
            "fecha_fin":       fecha_fin,
            "ingresos_op":     ingresos_op,
            "ingresos_no_op":  ingresos_no_op,
            "total_ingresos":  _r(ingresos_op + ingresos_no_op),
            "costo_venta":     costo_venta,
            "costo_produccion":costo_prod,
            "utilidad_bruta":  utilidad_bruta,
            "gastos_op":       gasto_op,
            "utilidad_op":     utilidad_op,
            "utilidad_neta":   utilidad_neta,
        }

    # ══════════════════════════════════════════════════════════
    # Balance General
    # ══════════════════════════════════════════════════════════
    def balance_general(self, fecha_corte: date) -> dict:
        filas = self.libro_mayor(date(1900, 1, 1), fecha_corte)

        grupos: Dict[str, Decimal] = {}
        for f in filas:
            cuenta = self.db.get(PlanCuenta, f["cuenta_id"])
            if not cuenta:
                continue
            clase = cuenta.clase.value if (cuenta.clase and hasattr(cuenta.clase, "value")) else ""
            grupos[clase] = grupos.get(clase, Decimal("0")) + f["saldo_final"]

        activo      = _r(grupos.get("activo", 0))
        pasivo      = _r(grupos.get("pasivo", 0))
        patrimonio  = _r(grupos.get("patrimonio", 0))
        # Agregar resultado del ejercicio al patrimonio
        er = self.estado_resultados(date(fecha_corte.year, 1, 1), fecha_corte)
        patrimonio  = _r(patrimonio + er["utilidad_neta"])

        return {
            "fecha_corte":          fecha_corte,
            "activo":               activo,
            "pasivo":               pasivo,
            "patrimonio":           patrimonio,
            "total_pasivo_patrim":  _r(pasivo + patrimonio),
            "diferencia":           _r(activo - (pasivo + patrimonio)),
            "detalle_clases":       grupos,
            "utilidad_ejercicio":   er["utilidad_neta"],
        }

    # ══════════════════════════════════════════════════════════
    # Cartera — cuentas por cobrar / por pagar por tercero
    # ══════════════════════════════════════════════════════════
    def cartera_clientes(self, fecha_corte: date) -> List[dict]:
        return self._cartera(fecha_corte, es_cobrar=True)

    def cartera_proveedores(self, fecha_corte: date) -> List[dict]:
        return self._cartera(fecha_corte, es_cobrar=False)

    def _cartera(self, fecha_corte: date, es_cobrar: bool) -> List[dict]:
        """Documentos de venta/compra emitidos sin pago total al corte."""
        if es_cobrar:
            tipos = [TipoDocumento.FACTURA_VENTA, TipoDocumento.NOTA_DEBITO_VENTA]
        else:
            tipos = [TipoDocumento.FACTURA_COMPRA, TipoDocumento.NOTA_DEBITO_COMPRA]

        docs = (
            self.db.query(Documento)
            .options(joinedload(Documento.tercero))
            .filter(
                Documento.empresa_id == self.empresa_id,
                Documento.tipo.in_(tipos),
                Documento.estado     == EstadoDocumento.EMITIDO,
                Documento.fecha      <= fecha_corte,
            )
            .order_by(Documento.tercero_id, Documento.fecha)
            .all()
        )

        resultado = []
        for d in docs:
            dias_vencido = 0
            vencido      = False
            if d.fecha_vence:
                delta = (fecha_corte - d.fecha_vence).days
                if delta > 0:
                    dias_vencido = delta
                    vencido      = True
            resultado.append({
                "numero":        d.numero,
                "fecha":         d.fecha,
                "fecha_vence":   d.fecha_vence,
                "tercero":       d.tercero.nombre if d.tercero else "—",
                "documento_id":  d.id,
                "saldo":         _r(d.total),
                "dias_vencido":  dias_vencido,
                "vencido":       vencido,
            })
        return resultado

    # ══════════════════════════════════════════════════════════
    # Ventas por período
    # ══════════════════════════════════════════════════════════
    def resumen_ventas(
        self,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> dict:
        docs = (
            self.db.query(Documento)
            .options(joinedload(Documento.tercero))
            .filter(
                Documento.empresa_id == self.empresa_id,
                Documento.tipo       == TipoDocumento.FACTURA_VENTA,
                Documento.estado     == EstadoDocumento.EMITIDO,
                Documento.fecha.between(fecha_inicio, fecha_fin),
            )
            .order_by(Documento.fecha)
            .all()
        )
        nc = (
            self.db.query(func.sum(Documento.total))
            .filter(
                Documento.empresa_id == self.empresa_id,
                Documento.tipo       == TipoDocumento.NOTA_CREDITO_VENTA,
                Documento.estado     == EstadoDocumento.EMITIDO,
                Documento.fecha.between(fecha_inicio, fecha_fin),
            )
            .scalar() or 0
        )

        total_bruto  = _r(sum(_r(d.total) for d in docs))
        total_nc     = _r(nc)
        total_neto   = _r(total_bruto - total_nc)
        total_iva    = _r(sum(_r(d.total_impuesto or 0) for d in docs))
        total_sub    = _r(sum(_r(d.subtotal or 0) for d in docs))

        # Agrupar por tercero
        por_tercero: Dict[str, Decimal] = {}
        for d in docs:
            nombre = d.tercero.nombre if d.tercero else "Sin tercero"
            por_tercero[nombre] = por_tercero.get(nombre, Decimal("0")) + _r(d.total)
        top_clientes = sorted(
            [{"nombre": k, "total": v} for k, v in por_tercero.items()],
            key=lambda x: x["total"], reverse=True
        )[:10]

        return {
            "fecha_inicio":   fecha_inicio,
            "fecha_fin":      fecha_fin,
            "n_facturas":     len(docs),
            "subtotal":       total_sub,
            "total_iva":      total_iva,
            "total_bruto":    total_bruto,
            "notas_credito":  total_nc,
            "total_neto":     total_neto,
            "documentos":     docs,
            "top_clientes":   top_clientes,
        }
