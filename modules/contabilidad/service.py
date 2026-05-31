from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from core.models.contabilidad import (
    PlanCuenta, PeriodoContable, Asiento,
    Movimiento, EstadoPeriodo, EstadoAsiento,
    PucContenido, FuenteContable,
    NaturalezaCuenta, ClaseCuenta, TipoCuenta,
    NivelCuenta, ModuloCuenta
)


class ContabilidadService:
    def __init__(self, db: Session, empresa_id: int):
        self.db = db
        self.empresa_id = empresa_id

    # ══════════════════════════════════════════════════════════════
    # Plan de Cuentas
    # ══════════════════════════════════════════════════════════════
    def listar_puc(self) -> List[PlanCuenta]:
        return (
            self.db.query(PlanCuenta)
            .filter(PlanCuenta.empresa_id == self.empresa_id)
            .order_by(PlanCuenta.codigo)
            .all()
        )

    def buscar_cuentas(self, criterio: str, solo_movibles: bool = False) -> List[PlanCuenta]:
        term = f"%{criterio}%"
        q = (
            self.db.query(PlanCuenta)
            .filter(
                PlanCuenta.empresa_id == self.empresa_id,
                (PlanCuenta.codigo.ilike(term)) | (PlanCuenta.nombre.ilike(term))
            )
        )
        if solo_movibles:
            q = q.filter(PlanCuenta.acepta_mov == True)
        return q.order_by(PlanCuenta.codigo).limit(50).all()

    def crear_cuenta(self, datos: dict) -> PlanCuenta:
        """Crea una nueva cuenta en el PUC de la empresa."""
        # Validar que el código no exista
        existe = self.db.query(PlanCuenta).filter(
            PlanCuenta.empresa_id == self.empresa_id,
            PlanCuenta.codigo == datos["codigo"]
        ).first()
        if existe:
            raise ValueError(f"Ya existe una cuenta con el código {datos['codigo']}.")

        cuenta = PlanCuenta(
            empresa_id   = self.empresa_id,
            codigo       = datos["codigo"],
            nombre       = datos["nombre"],
            naturaleza   = datos["naturaleza"],
            clase        = datos.get("clase"),
            tipo         = datos.get("tipo"),
            nivel_nombre = datos.get("nivel_nombre"),
            nivel        = datos["nivel"],
            cuenta_padre = datos.get("cuenta_padre"),
            acepta_mov   = datos.get("acepta_mov", True),
            es_retencion = datos.get("es_retencion", False),
            es_impuesto  = datos.get("es_impuesto", False),
            tarifa_pct   = datos.get("tarifa_pct"),
            modulo       = datos.get("modulo", ModuloCuenta.GENERAL),
            activa       = True,
        )
        self.db.add(cuenta)
        self.db.commit()
        self.db.refresh(cuenta)
        return cuenta

    def obtener_contenido_puc(self, codigo: str) -> Optional[PucContenido]:
        """Devuelve el HTML unificado (descripción + dinámica) para el código dado."""
        return self.db.query(PucContenido).filter(PucContenido.codigo == codigo).first()

    # ══════════════════════════════════════════════════════════════
    # Fuentes Contables
    # ══════════════════════════════════════════════════════════════
    def listar_fuentes(self) -> List[FuenteContable]:
        return self.db.query(FuenteContable).order_by(FuenteContable.codigo).all()

    # ══════════════════════════════════════════════════════════════
    # Periodos Contables
    # ══════════════════════════════════════════════════════════════
    def listar_periodos(self) -> List[PeriodoContable]:
        return (
            self.db.query(PeriodoContable)
            .filter(PeriodoContable.empresa_id == self.empresa_id)
            .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
            .all()
        )

    def crear_periodo(self, anio: int, mes: int) -> PeriodoContable:
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

        nuevo = PeriodoContable(
            empresa_id=self.empresa_id,
            anio=anio,
            mes=mes,
            estado=EstadoPeriodo.ABIERTO
        )
        self.db.add(nuevo)
        self.db.commit()
        self.db.refresh(nuevo)
        return nuevo

    def cerrar_periodo(self, periodo_id: int) -> PeriodoContable:
        periodo = (
            self.db.query(PeriodoContable)
            .filter(PeriodoContable.id == periodo_id, PeriodoContable.empresa_id == self.empresa_id)
            .first()
        )
        if not periodo:
            raise ValueError("Periodo contable no encontrado.")

        borradores = (
            self.db.query(Asiento)
            .filter(Asiento.periodo_id == periodo_id, Asiento.estado == EstadoAsiento.BORRADOR)
            .count()
        )
        if borradores > 0:
            raise ValueError("No se puede cerrar el periodo: existen asientos en estado Borrador.")

        periodo.estado = EstadoPeriodo.CERRADO
        self.db.commit()
        self.db.refresh(periodo)
        return periodo

    # ══════════════════════════════════════════════════════════════
    # Asientos y Diario
    # ══════════════════════════════════════════════════════════════
    def listar_asientos(self, periodo_id: Optional[int] = None) -> List[Asiento]:
        q = (
            self.db.query(Asiento)
            .options(joinedload(Asiento.movimientos))
            .filter(Asiento.empresa_id == self.empresa_id)
        )
        if periodo_id:
            q = q.filter(Asiento.periodo_id == periodo_id)
        return q.order_by(Asiento.fecha.desc(), Asiento.id.desc()).all()

    def obtener_asiento(self, asiento_id: int) -> Optional[Asiento]:
        return (
            self.db.query(Asiento)
            .options(
                joinedload(Asiento.movimientos)
                .joinedload(Movimiento.cuenta),
                joinedload(Asiento.movimientos)
                .joinedload(Movimiento.tercero),
                joinedload(Asiento.fuente),
            )
            .filter(Asiento.id == asiento_id, Asiento.empresa_id == self.empresa_id)
            .first()
        )

    def crear_asiento(
        self,
        periodo_id: int,
        fecha: date,
        descripcion: str,
        lineas: List[Dict[str, Any]],
        fuente_id: Optional[int] = None,
    ) -> Asiento:
        periodo = self.db.query(PeriodoContable).filter(PeriodoContable.id == periodo_id).first()
        if not periodo or periodo.estado == EstadoPeriodo.CERRADO:
            raise ValueError("El periodo contable seleccionado está cerrado o no existe.")

        if fecha.year != periodo.anio or fecha.month != periodo.mes:
            raise ValueError(f"La fecha no corresponde al periodo ({periodo.mes}/{periodo.anio}).")

        total_db = Decimal("0")
        total_cr = Decimal("0")
        for l in lineas:
            total_db += Decimal(str(l.get("debito", 0)))
            total_cr += Decimal(str(l.get("credito", 0)))

        if total_db != total_cr:
            raise ValueError(f"Asiento descuadrado. Débitos: ${total_db:,.2f} | Créditos: ${total_cr:,.2f}")
        if total_db <= 0:
            raise ValueError("El total del asiento debe ser mayor a cero.")

        max_num = self.db.query(func.max(Asiento.numero)).filter(Asiento.empresa_id == self.empresa_id).scalar()
        try:
            nuevo_numero = str(int(max_num) + 1).zfill(6) if max_num and str(max_num).isdigit() else "000001"
        except (ValueError, TypeError):
            nuevo_numero = "000001"

        asiento = Asiento(
            empresa_id  = self.empresa_id,
            periodo_id  = periodo_id,
            fuente_id   = fuente_id,
            numero      = nuevo_numero,
            fecha       = fecha,
            descripcion = descripcion,
            estado      = EstadoAsiento.CONFIRMADO
        )
        self.db.add(asiento)
        self.db.flush()

        try:
            for l in lineas:
                cuenta = self.db.query(PlanCuenta).filter(PlanCuenta.id == l["cuenta_id"]).first()
                if not cuenta:
                    raise ValueError(f"La cuenta con ID {l['cuenta_id']} no existe.")
                if not cuenta.acepta_mov:
                    raise ValueError(f"La cuenta {cuenta.codigo} no acepta movimientos directos.")

                mov = Movimiento(
                    empresa_id  = self.empresa_id,
                    asiento_id  = asiento.id,
                    cuenta_id   = cuenta.id,
                    tercero_id  = l.get("tercero_id"),
                    debito      = Decimal(str(l["debito"])),
                    credito     = Decimal(str(l["credito"])),
                    descripcion = l.get("descripcion", ""),
                )
                self.db.add(mov)

            self.db.commit()
            return self.obtener_asiento(asiento.id)
        except Exception as e:
            self.db.rollback()
            raise e

    def anular_asiento(self, asiento_id: int) -> Asiento:
        asiento = self.obtener_asiento(asiento_id)
        if not asiento:
            raise ValueError("El asiento contable no existe.")
        if asiento.periodo.estado == EstadoPeriodo.CERRADO:
            raise ValueError("No se puede anular un asiento de un periodo cerrado.")
        if asiento.estado == EstadoAsiento.ANULADO:
            raise ValueError("El asiento ya está anulado.")

        asiento.estado = EstadoAsiento.ANULADO
        for mov in asiento.movimientos:
            mov.debito  = Decimal("0.00")
            mov.credito = Decimal("0.00")

        self.db.commit()
        return asiento
