from decimal import Decimal
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from core.models.tesoreria import (
    CuentaTesoreria, Transaccion, LineaExtracto,
    TipoCuenta, TipoTransaccion, EstadoTransaccion, EstadoConciliacion
)
from core.models.terceros import Tercero


class TesoreriaService:

    def __init__(self, db: Session, empresa_id: int):
        self.db         = db
        self.empresa_id = empresa_id

    # ══════════════════════════════════════════════════════════
    # Cuentas de Tesorería
    # ══════════════════════════════════════════════════════════
    def listar_cuentas(self, solo_activas: bool = True) -> List[CuentaTesoreria]:
        q = self.db.query(CuentaTesoreria).filter(
            CuentaTesoreria.empresa_id == self.empresa_id)
        if solo_activas:
            q = q.filter(CuentaTesoreria.activa == True)
        return q.order_by(CuentaTesoreria.tipo, CuentaTesoreria.nombre).all()

    def obtener_cuenta(self, cuenta_id: int) -> Optional[CuentaTesoreria]:
        return self.db.query(CuentaTesoreria).filter(
            CuentaTesoreria.id == cuenta_id,
            CuentaTesoreria.empresa_id == self.empresa_id
        ).first()

    def crear_cuenta(self, datos: dict) -> CuentaTesoreria:
        c = CuentaTesoreria(empresa_id=self.empresa_id, **datos)
        c.saldo_actual = datos.get("saldo_inicial", Decimal("0"))
        self.db.add(c)
        self.db.commit()
        self.db.refresh(c)
        return c

    def actualizar_cuenta(self, cuenta_id: int, datos: dict) -> CuentaTesoreria:
        c = self.obtener_cuenta(cuenta_id)
        if not c:
            raise ValueError("Cuenta no encontrada.")
        for k, v in datos.items():
            setattr(c, k, v)
        self.db.commit()
        return c

    def desactivar_cuenta(self, cuenta_id: int):
        c = self.obtener_cuenta(cuenta_id)
        if c:
            c.activa = False
            self.db.commit()

    def saldo_total(self) -> Decimal:
        result = self.db.query(func.sum(CuentaTesoreria.saldo_actual)).filter(
            CuentaTesoreria.empresa_id == self.empresa_id,
            CuentaTesoreria.activa == True
        ).scalar()
        return Decimal(str(result or 0))

    # ══════════════════════════════════════════════════════════
    # Transacciones
    # ══════════════════════════════════════════════════════════
    def listar_transacciones(
        self,
        cuenta_id: int = None,
        tipo: TipoTransaccion = None,
        fecha_desde: date = None,
        fecha_hasta: date = None,
        limite: int = 300,
    ) -> List[Transaccion]:
        q = (self.db.query(Transaccion)
             .options(
                 joinedload(Transaccion.cuenta),
                 joinedload(Transaccion.tercero),
                 joinedload(Transaccion.cuenta_destino),
             )
             .filter(Transaccion.empresa_id == self.empresa_id,
                     Transaccion.estado != EstadoTransaccion.ANULADA))
        if cuenta_id:
            q = q.filter(
                (Transaccion.cuenta_id == cuenta_id) |
                (Transaccion.cuenta_destino_id == cuenta_id)
            )
        if tipo:
            q = q.filter(Transaccion.tipo == tipo)
        if fecha_desde:
            q = q.filter(Transaccion.fecha >= fecha_desde)
        if fecha_hasta:
            q = q.filter(Transaccion.fecha <= fecha_hasta)
        return q.order_by(Transaccion.fecha.desc(), Transaccion.id.desc()).limit(limite).all()

    def registrar_ingreso(
        self,
        cuenta_id: int,
        fecha: date,
        concepto: str,
        valor: Decimal,
        tercero_id: int = None,
        referencia: str = None,
        notas: str = None,
        periodo_id: int = None,
    ) -> Transaccion:
        return self._crear_transaccion(
            cuenta_id=cuenta_id, tipo=TipoTransaccion.INGRESO,
            fecha=fecha, concepto=concepto, valor=valor,
            tercero_id=tercero_id, referencia=referencia,
            notas=notas, periodo_id=periodo_id,
        )

    def registrar_egreso(
        self,
        cuenta_id: int,
        fecha: date,
        concepto: str,
        valor: Decimal,
        tercero_id: int = None,
        referencia: str = None,
        notas: str = None,
        periodo_id: int = None,
    ) -> Transaccion:
        cuenta = self.obtener_cuenta(cuenta_id)
        if cuenta and cuenta.saldo_actual < valor:
            raise ValueError(
                f"Saldo insuficiente. Disponible: ${cuenta.saldo_actual:,.2f} | "
                f"Requerido: ${valor:,.2f}"
            )
        return self._crear_transaccion(
            cuenta_id=cuenta_id, tipo=TipoTransaccion.EGRESO,
            fecha=fecha, concepto=concepto, valor=valor,
            tercero_id=tercero_id, referencia=referencia,
            notas=notas, periodo_id=periodo_id,
        )

    def registrar_traslado(
        self,
        cuenta_origen_id: int,
        cuenta_destino_id: int,
        fecha: date,
        concepto: str,
        valor: Decimal,
        referencia: str = None,
        notas: str = None,
        periodo_id: int = None,
    ) -> Transaccion:
        if cuenta_origen_id == cuenta_destino_id:
            raise ValueError("La cuenta origen y destino no pueden ser la misma.")
        origen = self.obtener_cuenta(cuenta_origen_id)
        if origen and origen.saldo_actual < valor:
            raise ValueError(
                f"Saldo insuficiente en cuenta origen. "
                f"Disponible: ${origen.saldo_actual:,.2f}"
            )
        return self._crear_transaccion(
            cuenta_id=cuenta_origen_id,
            cuenta_destino_id=cuenta_destino_id,
            tipo=TipoTransaccion.TRASLADO,
            fecha=fecha, concepto=concepto, valor=valor,
            referencia=referencia, notas=notas, periodo_id=periodo_id,
        )

    def _crear_transaccion(self, **kwargs) -> Transaccion:
        txn = Transaccion(
            empresa_id=self.empresa_id,
            estado=EstadoTransaccion.APLICADA,
            **kwargs
        )
        self.db.add(txn)
        self.db.flush()
        self._actualizar_saldo(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def _actualizar_saldo(self, txn: Transaccion):
        cuenta = self.db.get(CuentaTesoreria, txn.cuenta_id)
        if not cuenta:
            return
        valor = Decimal(str(txn.valor))
        if txn.tipo == TipoTransaccion.INGRESO:
            cuenta.saldo_actual += valor
        elif txn.tipo == TipoTransaccion.EGRESO:
            cuenta.saldo_actual -= valor
        elif txn.tipo == TipoTransaccion.TRASLADO:
            cuenta.saldo_actual -= valor
            if txn.cuenta_destino_id:
                destino = self.db.get(CuentaTesoreria, txn.cuenta_destino_id)
                if destino:
                    destino.saldo_actual += valor

    def anular_transaccion(self, txn_id: int) -> Transaccion:
        txn = self.db.query(Transaccion).filter(
            Transaccion.id == txn_id,
            Transaccion.empresa_id == self.empresa_id
        ).first()
        if not txn:
            raise ValueError("Transacción no encontrada.")
        if txn.estado == EstadoTransaccion.ANULADA:
            raise ValueError("La transacción ya está anulada.")
        if txn.conciliacion == EstadoConciliacion.CONCILIADO:
            raise ValueError("No se puede anular una transacción ya conciliada.")

        # Revertir saldo
        cuenta = self.db.get(CuentaTesoreria, txn.cuenta_id)
        valor  = Decimal(str(txn.valor))
        if txn.tipo == TipoTransaccion.INGRESO:
            cuenta.saldo_actual -= valor
        elif txn.tipo == TipoTransaccion.EGRESO:
            cuenta.saldo_actual += valor
        elif txn.tipo == TipoTransaccion.TRASLADO:
            cuenta.saldo_actual += valor
            if txn.cuenta_destino_id:
                destino = self.db.get(CuentaTesoreria, txn.cuenta_destino_id)
                if destino:
                    destino.saldo_actual -= valor

        txn.estado = EstadoTransaccion.ANULADA
        self.db.commit()
        return txn

    # ══════════════════════════════════════════════════════════
    # Terceros (para búsqueda en formularios)
    # ══════════════════════════════════════════════════════════
    def buscar_terceros(self, criterio: str) -> List[Tercero]:
        term = f"%{criterio}%"
        return (self.db.query(Tercero)
                .filter(Tercero.empresa_id == self.empresa_id,
                        Tercero.activo == True,
                        (Tercero.nombre.ilike(term) |
                         Tercero.numero_documento.ilike(term)))
                .order_by(Tercero.nombre).limit(25).all())

    # ══════════════════════════════════════════════════════════
    # Conciliación bancaria
    # ══════════════════════════════════════════════════════════
    def listar_extracto(self, cuenta_id: int,
                        solo_no_conciliado: bool = True) -> List[LineaExtracto]:
        q = self.db.query(LineaExtracto).filter(
            LineaExtracto.cuenta_id == cuenta_id)
        if solo_no_conciliado:
            q = q.filter(LineaExtracto.conciliado == False)
        return q.order_by(LineaExtracto.fecha.desc()).all()

    def importar_extracto(self, cuenta_id: int,
                          lineas: List[dict]) -> int:
        """Importa líneas del extracto bancario (desde CSV o manual)."""
        creadas = 0
        for l in lineas:
            le = LineaExtracto(
                cuenta_id   = cuenta_id,
                fecha       = l["fecha"],
                descripcion = l.get("descripcion", ""),
                referencia  = l.get("referencia"),
                debito      = Decimal(str(l.get("debito", 0))),
                credito     = Decimal(str(l.get("credito", 0))),
                saldo       = Decimal(str(l.get("saldo", 0))) if l.get("saldo") else None,
            )
            self.db.add(le)
            creadas += 1
        self.db.commit()
        return creadas

    def conciliar(self, linea_extracto_id: int,
                  transaccion_id: int) -> bool:
        """Marca una línea de extracto y una transacción como conciliadas."""
        le  = self.db.get(LineaExtracto, linea_extracto_id)
        txn = self.db.query(Transaccion).filter(
            Transaccion.id == transaccion_id,
            Transaccion.empresa_id == self.empresa_id
        ).first()
        if not le or not txn:
            raise ValueError("Línea o transacción no encontrada.")
        le.conciliado     = True
        le.transaccion_id = transaccion_id
        txn.conciliacion  = EstadoConciliacion.CONCILIADO
        self.db.commit()
        return True

    def desconciliar(self, linea_extracto_id: int):
        le = self.db.get(LineaExtracto, linea_extracto_id)
        if not le:
            return
        if le.transaccion_id:
            txn = self.db.get(Transaccion, le.transaccion_id)
            if txn:
                txn.conciliacion = EstadoConciliacion.NO_CONCILIADO
        le.conciliado     = False
        le.transaccion_id = None
        self.db.commit()

    def resumen_conciliacion(self, cuenta_id: int) -> dict:
        cuenta = self.obtener_cuenta(cuenta_id)
        total_extracto_db = self.db.query(
            func.sum(LineaExtracto.debito)
        ).filter(LineaExtracto.cuenta_id == cuenta_id,
                 LineaExtracto.conciliado == False).scalar() or 0
        total_extracto_cr = self.db.query(
            func.sum(LineaExtracto.credito)
        ).filter(LineaExtracto.cuenta_id == cuenta_id,
                 LineaExtracto.conciliado == False).scalar() or 0
        pendientes = self.db.query(func.count(LineaExtracto.id)).filter(
            LineaExtracto.cuenta_id == cuenta_id,
            LineaExtracto.conciliado == False
        ).scalar() or 0
        return {
            "cuenta":              cuenta,
            "saldo_libros":        Decimal(str(cuenta.saldo_actual if cuenta else 0)),
            "extracto_debitos_nc": Decimal(str(total_extracto_db)),
            "extracto_creditos_nc":Decimal(str(total_extracto_cr)),
            "lineas_pendientes":   pendientes,
        }
