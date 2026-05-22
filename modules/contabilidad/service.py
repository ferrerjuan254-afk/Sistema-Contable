from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from core.models.contabilidad import (
    PlanCuenta, PeriodoContable, Asiento, 
    Movimiento, EstadoPeriodo, EstadoAsiento
)

class ContabilidadService:
    def __init__(self, db: Session, empresa_id: int):
        self.db = db
        self.empresa_id = empresa_id

    # ══════════════════════════════════════════════════════════════
    # MÉTODOS: Plan de Cuentas (PUC)
    # ══════════════════════════════════════════════════════════════
    def listar_puc(self) -> List[PlanCuenta]:
        """Retorna el árbol del Plan Único de Cuentas ordenado por código."""
        return (
            self.db.query(PlanCuenta)
            .filter(PlanCuenta.empresa_id == self.empresa_id)
            .order_by(PlanCuenta.codigo)
            .all()
        )

    def buscar_cuentas(self, criterio: str) -> List[PlanCuenta]:
        """Busca cuentas auxiliares o mayores que coincidan con código o nombre."""
        term = f"%{criterio}%"
        return (
            self.db.query(PlanCuenta)
            .filter(
                PlanCuenta.empresa_id == self.empresa_id,
                (PlanCuenta.codigo.ilike(term)) | (PlanCuenta.nombre.ilike(term))
            )
            .order_by(PlanCuenta.codigo)
            .all()
        )

    # ══════════════════════════════════════════════════════════════
    # MÉTODOS: Periodos Contables
    # ══════════════════════════════════════════════════════════════
    def listar_periodos(self) -> List[PeriodoContable]:
        return (
            self.db.query(PeriodoContable)
            .filter(PeriodoContable.empresa_id == self.empresa_id)
            .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
            .all()
        )

    def crear_periodo(self, anio: int, mes: int) -> PeriodoContable:
        # Validar duplicados
        existe = (
            self.db.query(PeriodoContable)
            .filter(
                PeriodoContable.empresa_id == self.empresa_id,
                PeriodoContable.anio == anio,
                PeriodoContable.mes == mes
            ).first()
        )
        if existe:
            raise ValueError(f"El periodo contable {mes}/{anio} ya existe para esta empresa.")

        nuevo_periodo = PeriodoContable(
            empresa_id=self.empresa_id,
            anio=anio,
            mes=mes,
            estado=EstadoPeriodo.ABIERTO
        )
        self.db.add(nuevo_periodo)
        self.db.commit()
        self.db.refresh(nuevo_periodo)
        return nuevo_periodo

    def cerrar_periodo(self, periodo_id: int) -> PeriodoContable:
        periodo = (
            self.db.query(PeriodoContable)
            .filter(PeriodoContable.id == periodo_id, PeriodoContable.empresa_id == self.empresa_id)
            .first()
        )
        if not periodo:
            raise ValueError("Periodo contable no encontrado.")
        
        # Opcional: Validar que no existan asientos descuadrados o en borrador antes de cerrar
        asientos_abiertos = (
            self.db.query(Asiento)
            .filter(
                Asiento.periodo_id == periodo_id,
                Asiento.estado == EstadoAsiento.BORRADOR
            ).count()
        )
        if asientos_abiertos > 0:
            raise ValueError("No se puede cerrar el periodo: Existen asientos en estado Borrador.")

        periodo.estado = EstadoPeriodo.CERRADO
        self.db.commit()
        self.db.refresh(periodo)
        return periodo

    # ══════════════════════════════════════════════════════════════
    # MÉTODOS: Asientos y Diario
    # ══════════════════════════════════════════════════════════════
    def listar_asientos(self, periodo_id: Optional[int] = None) -> List[Asiento]:
        query = (
            self.db.query(Asiento)
            .options(joinedload(Asiento.movimientos))
            .filter(Asiento.empresa_id == self.empresa_id)
        )
        if periodo_id:
            query = query.filter(Asiento.periodo_id == periodo_id)
        
        return query.order_by(Asiento.fecha.desc(), Asiento.id.desc()).all()

    def obtener_asiento(self, asiento_id: int) -> Optional[Asiento]:
        return (
            self.db.query(Asiento)
            .options(
                joinedload(Asiento.movimientos)
                .joinedload(Movimiento.cuenta)
            )
            .filter(Asiento.id == asiento_id, Asiento.empresa_id == self.empresa_id)
            .first()
        )

    def crear_asiento(self, periodo_id: int, fecha: date, descripcion: str, lineas: List[Dict[str, Any]]) -> Asiento:
        # 1. Validar estado del periodo
        periodo = self.db.query(PeriodoContable).filter(PeriodoContable.id == periodo_id).first()
        if not periodo or periodo.estado == EstadoPeriodo.CERRADO:
            raise ValueError("El periodo contable seleccionado está cerrado o no existe.")

        if fecha.year != periodo.anio or fecha.month != periodo.mes:
            raise ValueError(f"La fecha del asiento no corresponde al año/mes del periodo ({periodo.mes}/{periodo.anio}).")

        # 2. Validar principio de Partida Doble
        total_debito = Decimal("0")
        total_credito = Decimal("0")
        
        for l in lineas:
            total_debito += Decimal(str(l.get("debito", 0)))
            total_credito += Decimal(str(l.get("credito", 0)))

        if total_debito != total_credito:
            raise ValueError(f"Asiento descuadrado. Débitos: ${total_debito:,.2f} | Créditos: ${total_credito:,.2f}")
        
        if total_debito <= 0:
            raise ValueError("El total del asiento debe ser mayor a cero.")

        # 3. Generar consecutivo numérico único por Empresa
        max_num = self.db.query(func.max(Asiento.numero)).filter(Asiento.empresa_id == self.empresa_id).scalar()
        try:
            nuevo_numero = str(int(max_num) + 1).zfill(6) if max_num and max_num.isdigit() else "000001"
        except (ValueError, TypeError):
            nuevo_numero = "000001"

        # 4. Crear Cabecera del Asiento
        asiento = Asiento(
            empresa_id=self.empresa_id,
            periodo_id=periodo_id,
            numero=nuevo_numero,
            fecha=fecha,
            descripcion=descripcion,
            estado=EstadoAsiento.CONFIRMADO
        )
        self.db.add(asiento)
        self.db.flush()  # Obtener ID del asiento


        # 5. Registrar movimientos apuntados a cuentas válidas que acepten movimientos
        try:
            for l in lineas:
                cuenta = self.db.query(PlanCuenta).filter(PlanCuenta.id == l["cuenta_id"]).first()
                if not cuenta:
                    raise ValueError(f"La cuenta con ID {l['cuenta_id']} no existe.")
                if not cuenta.acepta_mov:
                    raise ValueError(f"La cuenta {cuenta.codigo} es una cuenta de grupo/mayor y no acepta movimientos directos.")

                movimiento = Movimiento(
                    empresa_id=self.empresa_id,
                    asiento_id=asiento.id,
                    cuenta_id=cuenta.id,
                    debito=Decimal(str(l["debito"])),
                    credito=Decimal(str(l["credito"])),
                    descripcion=l.get("descripcion", "")
                )
                self.db.add(movimiento)

            self.db.commit()
            return self.obtener_asiento(asiento.id)
            
        except Exception as e:
            self.db.rollback()  # 🧼 Cancela el flush previo y libera la sesión si algo sale mal
            raise e

    def anular_asiento(self, asiento_id: int) -> Asiento:
        asiento = self.obtener_asiento(asiento_id)
        if not asiento:
            raise ValueError("El asiento contable no existe.")
        
        if asiento.periodo.estado == EstadoPeriodo.CERRADO:
            raise ValueError("No se puede anular un asiento de un periodo contable cerrado.")
            
        if asiento.estado == EstadoAsiento.ANULADO:
            raise ValueError("El asiento ya se encuentra anulado.")

        asiento.estado = EstadoAsiento.ANULADO
        
        # En contabilidad formal, los movimientos de un asiento anulado se llevan a cero
        for mov in asiento.movimientos:
            mov.debito = Decimal("0.00")
            mov.credito = Decimal("0.00")

        self.db.commit()
        return asiento
