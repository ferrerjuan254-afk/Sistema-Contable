from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from core.models.nomina import (
    Empleado, Liquidacion, AportesSeguridadSocial,
    EstadoLiquidacion
)
from core.models.contabilidad import PeriodoContable

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Tarifas vigentes Colombia
TARIFAS = {
    "salud_empleado":    Decimal("0.04"),
    "salud_empleador":   Decimal("0.085"),
    "pension_empleado":  Decimal("0.04"),
    "pension_empleador": Decimal("0.12"),
    "icbf":              Decimal("0.03"),
    "sena":              Decimal("0.02"),
    "caja":              Decimal("0.04"),
}
ARL_TARIFAS = {
    1: Decimal("0.00522"),
    2: Decimal("0.01044"),
    3: Decimal("0.02436"),
    4: Decimal("0.04350"),
    5: Decimal("0.06960"),
}
SALARIO_MINIMO = Decimal("1300000")
UVT = Decimal("47065")


def _r(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class SeguridadSocialService:

    def __init__(self, db: Session, empresa_id: int):
        self.db         = db
        self.empresa_id = empresa_id

    # ══════════════════════════════════════════════════════════
    # Periodos disponibles
    # ══════════════════════════════════════════════════════════
    def listar_periodos(self) -> List[PeriodoContable]:
        return (
            self.db.query(PeriodoContable)
            .filter(PeriodoContable.empresa_id == self.empresa_id)
            .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
            .all()
        )

    # ══════════════════════════════════════════════════════════
    # Aportes guardados
    # ══════════════════════════════════════════════════════════
    def listar_aportes(self, periodo_id: int = None) -> List[AportesSeguridadSocial]:
        q = (
            self.db.query(AportesSeguridadSocial)
            .options(
                joinedload(AportesSeguridadSocial.empleado)
                .joinedload(Empleado.tercero)
            )
            .filter(AportesSeguridadSocial.empresa_id == self.empresa_id)
        )
        if periodo_id:
            q = q.filter(AportesSeguridadSocial.periodo_id == periodo_id)
        return q.order_by(AportesSeguridadSocial.id).all()

    def existe_planilla(self, periodo_id: int) -> bool:
        return self.db.query(AportesSeguridadSocial).filter(
            AportesSeguridadSocial.empresa_id == self.empresa_id,
            AportesSeguridadSocial.periodo_id == periodo_id,
        ).count() > 0

    # ══════════════════════════════════════════════════════════
    # Generación de PILA desde liquidaciones aprobadas
    # ══════════════════════════════════════════════════════════
    def calcular_pila(self, periodo_id: int) -> List[dict]:
        """
        Lee las liquidaciones APROBADAS asociadas al periodo dado
        (o al rango de fechas del periodo si la liquidación tiene otro periodo_id).
        """
        # 1. Intentar match directo por periodo_id
        liqlist = (
            self.db.query(Liquidacion)
            .options(joinedload(Liquidacion.empleado).joinedload(Empleado.tercero))
            .filter(
                Liquidacion.empresa_id == self.empresa_id,
                Liquidacion.periodo_id == periodo_id,
                Liquidacion.estado     == EstadoLiquidacion.APROBADA,
            )
            .all()
        )

        # 2. Si no hay, buscar por rango de fechas del periodo
        if not liqlist:
            periodo = self.db.get(PeriodoContable, periodo_id)
            if periodo:
                import calendar
                primer_dia = date(periodo.anio, periodo.mes, 1)
                ultimo_dia = date(
                    periodo.anio, periodo.mes,
                    calendar.monthrange(periodo.anio, periodo.mes)[1]
                )
                liqlist = (
                    self.db.query(Liquidacion)
                    .options(joinedload(Liquidacion.empleado)
                             .joinedload(Empleado.tercero))
                    .filter(
                        Liquidacion.empresa_id == self.empresa_id,
                        Liquidacion.estado     == EstadoLiquidacion.APROBADA,
                        Liquidacion.fecha_inicio >= primer_dia,
                        Liquidacion.fecha_fin    <= ultimo_dia,
                    )
                    .all()
                )

        # 3. Si sigue sin haber, mostrar todas las aprobadas para debug
        if not liqlist:
            todas = (
                self.db.query(Liquidacion)
                .filter(
                    Liquidacion.empresa_id == self.empresa_id,
                    Liquidacion.estado     == EstadoLiquidacion.APROBADA,
                )
                .all()
            )
            if todas:
                # Hay liquidaciones aprobadas pero en otros periodos — usar las más recientes
                periodo = self.db.get(PeriodoContable, periodo_id)
                periodo_label = f"{periodo.mes}/{periodo.anio}" if periodo else str(periodo_id)
                ids_periodos = sorted(set(l.periodo_id for l in todas))
                periodos_disponibles = []
                for pid in ids_periodos:
                    p = self.db.get(PeriodoContable, pid)
                    if p:
                        periodos_disponibles.append(f"{MESES[p.mes]} {p.anio}")
                    else:
                        periodos_disponibles.append(str(pid))
                raise ValueError(
                    f"No hay liquidaciones aprobadas para {periodo_label}.\n\n"
                    f"Las liquidaciones aprobadas están en:\n"
                    + "\n".join(f"  • {p}" for p in periodos_disponibles)
                    + "\n\nSelecciona el periodo correcto en el combo."
                )
            raise ValueError(
                "No hay liquidaciones aprobadas en ningún periodo. "
                "Aprueba las nóminas desde el módulo de Nómina primero."
            )

        resultados = []
        for liq in liqlist:
            emp = liq.empleado
            salario = Decimal(str(emp.salario_base))

            # IBC = devengado salarial (excluye AUX transporte)
            # Para simplificar: IBC = salario_base, mínimo SMMLV
            ibc = max(salario, SALARIO_MINIMO)

            nivel_riesgo = emp.nivel_riesgo_arl or 1
            tarifa_arl   = ARL_TARIFAS.get(nivel_riesgo, Decimal("0.00522"))

            # Parafiscales: exentos si salario <= 10 SMMLV (Ley 1607/2012)
            paga_parafiscales = salario > SALARIO_MINIMO * 10

            resultados.append({
                "empleado_id":       emp.id,
                "liquidacion_id":    liq.id,
                "nombre":            emp.tercero.nombre if emp.tercero else f"Emp {emp.id}",
                "documento":         emp.tercero.numero_documento if emp.tercero else "",
                "eps":               emp.eps or "—",
                "fondo_pension":     emp.fondo_pension or "—",
                "fondo_cesantias":   emp.fondo_cesantias or "—",
                "arl":               emp.arl or "—",
                "caja_compensacion": emp.caja_compensacion or "—",
                "ibc":               ibc,
                "nivel_riesgo_arl":  nivel_riesgo,
                # Empleado
                "salud_empleado":    _r(ibc * TARIFAS["salud_empleado"]),
                "pension_empleado":  _r(ibc * TARIFAS["pension_empleado"]),
                # Empleador
                "salud_empleador":   _r(ibc * TARIFAS["salud_empleador"]),
                "pension_empleador": _r(ibc * TARIFAS["pension_empleador"]),
                "arl_valor":         _r(ibc * tarifa_arl),
                "icbf":              _r(salario * TARIFAS["icbf"]) if paga_parafiscales else Decimal("0"),
                "sena":              _r(salario * TARIFAS["sena"]) if paga_parafiscales else Decimal("0"),
                "caja":              _r(salario * TARIFAS["caja"]),
            })

        # Calcular totales por fila
        for r in resultados:
            r["total_empleado"]  = r["salud_empleado"] + r["pension_empleado"]
            r["total_empleador"] = (
                r["salud_empleador"] + r["pension_empleador"] +
                r["arl_valor"] + r["icbf"] + r["sena"] + r["caja"]
            )
            r["total_pila"] = r["total_empleado"] + r["total_empleador"]

        return resultados

    def guardar_pila(self, periodo_id: int,
                     filas: List[dict]) -> List[AportesSeguridadSocial]:
        """Persiste los aportes calculados."""
        if self.existe_planilla(periodo_id):
            raise ValueError(
                "Ya existe una planilla generada para este periodo. "
                "Elimínala primero si deseas regenerarla."
            )
        guardados = []
        for f in filas:
            aporte = AportesSeguridadSocial(
                empresa_id          = self.empresa_id,
                empleado_id         = f["empleado_id"],
                periodo_id          = periodo_id,
                ibc                 = f["ibc"],
                salud_empleado      = f["salud_empleado"],
                salud_empleador     = f["salud_empleador"],
                pension_empleado    = f["pension_empleado"],
                pension_empleador   = f["pension_empleador"],
                arl                 = f["arl_valor"],
                icbf                = f["icbf"],
                sena                = f["sena"],
                caja_compensacion   = f["caja"],
            )
            self.db.add(aporte)
            guardados.append(aporte)
        self.db.commit()
        return guardados

    def eliminar_planilla(self, periodo_id: int) -> int:
        """Elimina todos los aportes del periodo para regenerar."""
        n = self.db.query(AportesSeguridadSocial).filter(
            AportesSeguridadSocial.empresa_id == self.empresa_id,
            AportesSeguridadSocial.periodo_id == periodo_id,
        ).delete()
        self.db.commit()
        return n

    # ══════════════════════════════════════════════════════════
    # Resumen por periodo
    # ══════════════════════════════════════════════════════════
    def resumen_periodo(self, periodo_id: int) -> dict:
        filas = self.listar_aportes(periodo_id)
        if not filas:
            return {}

        def _s(campo: str) -> Decimal:
            return sum(Decimal(str(getattr(f, campo) or 0)) for f in filas)

        return {
            "n_empleados":       len(filas),
            "total_ibc":         _s("ibc"),
            "salud_empleado":    _s("salud_empleado"),
            "salud_empleador":   _s("salud_empleador"),
            "pension_empleado":  _s("pension_empleado"),
            "pension_empleador": _s("pension_empleador"),
            "arl":               _s("arl"),
            "icbf":              _s("icbf"),
            "sena":              _s("sena"),
            "caja":              _s("caja_compensacion"),
            "total_empleado":    _s("salud_empleado") + _s("pension_empleado"),
            "total_empleador":   (
                _s("salud_empleador") + _s("pension_empleador") +
                _s("arl") + _s("icbf") + _s("sena") + _s("caja_compensacion")
            ),
        }
