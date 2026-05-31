from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from core.models.nomina import (
    Empleado, ConceptoNomina, Liquidacion, DetalleLiquidacion,
    AportesSeguridadSocial, TipoConcepto, EstadoLiquidacion,
)
from core.models.terceros import Tercero, TipoDocumento


# Tarifas legales Colombia 2024
ARL_TARIFAS = {1: Decimal("0.00522"), 2: Decimal("0.01044"),
               3: Decimal("0.02436"), 4: Decimal("0.04350"), 5: Decimal("0.06960")}

SALARIO_MINIMO_2026 = Decimal("1750905")
AUXILIO_TRANSPORTE_2024 = Decimal("249095")
UVT_2024 = Decimal("47065")


def _redondear(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class NominaService:

    def __init__(self, db: Session, empresa_id: int):
        self.db         = db
        self.empresa_id = empresa_id

    # ══════════════════════════════════════════════════════════
    # Terceros disponibles para crear empleado
    # ══════════════════════════════════════════════════════════
    def listar_terceros_sin_empleado(self) -> List[Tercero]:
        ids_con_empleado = [
            e.tercero_id for e in
            self.db.query(Empleado.tercero_id)
            .filter(Empleado.empresa_id == self.empresa_id, Empleado.activo == True)
            .all()
        ]
        q = self.db.query(Tercero).filter(
            Tercero.empresa_id == self.empresa_id,
            Tercero.activo == True,
        )
        if ids_con_empleado:
            q = q.filter(Tercero.id.notin_(ids_con_empleado))
        return q.order_by(Tercero.nombre).all()

    # ══════════════════════════════════════════════════════════
    # Empleados
    # ══════════════════════════════════════════════════════════
    def listar_empleados(self, activos_solo: bool = True) -> List[Empleado]:
        q = (self.db.query(Empleado)
             .options(joinedload(Empleado.tercero))
             .filter(Empleado.empresa_id == self.empresa_id))
        if activos_solo:
            q = q.filter(Empleado.activo == True)
        return q.order_by(Empleado.id).all()

    def obtener_empleado(self, empleado_id: int) -> Optional[Empleado]:
        return (self.db.query(Empleado)
                .options(joinedload(Empleado.tercero))
                .filter(Empleado.id == empleado_id,
                        Empleado.empresa_id == self.empresa_id)
                .first())

    def crear_empleado(self, datos: dict) -> Empleado:
        emp = Empleado(empresa_id=self.empresa_id, **datos)
        # Marcar tercero como empleado
        tercero = self.db.get(Tercero, datos["tercero_id"])
        if tercero:
            tercero.es_empleado = True
        self.db.add(emp)
        self.db.commit()
        self.db.refresh(emp)
        return emp

    def actualizar_empleado(self, empleado_id: int, datos: dict) -> Empleado:
        emp = self.obtener_empleado(empleado_id)
        if not emp:
            raise ValueError("Empleado no encontrado.")
        for k, v in datos.items():
            setattr(emp, k, v)
        self.db.commit()
        return emp

    def retirar_empleado(self, empleado_id: int, fecha_retiro: date) -> Empleado:
        emp = self.obtener_empleado(empleado_id)
        if not emp:
            raise ValueError("Empleado no encontrado.")
        emp.fecha_retiro = fecha_retiro
        emp.activo       = False
        self.db.commit()
        return emp

    # ══════════════════════════════════════════════════════════
    # Conceptos de Nómina
    # ══════════════════════════════════════════════════════════
    def listar_conceptos(self) -> List[ConceptoNomina]:
        return (self.db.query(ConceptoNomina)
                .filter(ConceptoNomina.empresa_id == self.empresa_id,
                        ConceptoNomina.activo == True)
                .order_by(ConceptoNomina.tipo, ConceptoNomina.codigo)
                .all())

    def crear_concepto(self, datos: dict) -> ConceptoNomina:
        existe = self.db.query(ConceptoNomina).filter(
            ConceptoNomina.empresa_id == self.empresa_id,
            ConceptoNomina.codigo == datos["codigo"]
        ).first()
        if existe:
            raise ValueError(f"Ya existe un concepto con código {datos['codigo']}.")
        c = ConceptoNomina(empresa_id=self.empresa_id, **datos)
        self.db.add(c)
        self.db.commit()
        self.db.refresh(c)
        return c

    def actualizar_concepto(self, concepto_id: int, datos: dict) -> ConceptoNomina:
        c = self.db.query(ConceptoNomina).filter(
            ConceptoNomina.id == concepto_id,
            ConceptoNomina.empresa_id == self.empresa_id
        ).first()
        if not c:
            raise ValueError("Concepto no encontrado.")
        for k, v in datos.items():
            setattr(c, k, v)
        self.db.commit()
        return c

    def eliminar_concepto(self, concepto_id: int) -> bool:
        c = self.db.query(ConceptoNomina).filter(
            ConceptoNomina.id == concepto_id,
            ConceptoNomina.empresa_id == self.empresa_id
        ).first()
        if not c:
            return False
        c.activo = False
        self.db.commit()
        return True

    def _seed_conceptos_basicos(self):
        """Inserta conceptos legales mínimos si la empresa no tiene ninguno."""
        if self.db.query(ConceptoNomina).filter_by(empresa_id=self.empresa_id).count() > 0:
            return
        basicos = [
            # Devengados  (codigo, nombre, tipo, porcentaje, es_manual, monto)
            ("001", "Salario Básico",           TipoConcepto.DEVENGADO,  None,              False, None),
            ("002", "Auxilio de Transporte",    TipoConcepto.DEVENGADO,  None,              True,  Decimal("249095")),
            ("003", "Horas Extras Diurnas",     TipoConcepto.DEVENGADO,  Decimal("0.25"),   False, None),
            ("004", "Horas Extras Nocturnas",   TipoConcepto.DEVENGADO,  Decimal("0.75"),   False, None),
            ("005", "Recargo Nocturno",         TipoConcepto.DEVENGADO,  Decimal("0.35"),   False, None),
            ("006", "Horas Extras Dom/Fest",    TipoConcepto.DEVENGADO,  Decimal("1.00"),   False, None),
            ("007", "Comisiones",               TipoConcepto.DEVENGADO,  None,              True,  None),
            ("008", "Bonificaciones",           TipoConcepto.DEVENGADO,  None,              True,  None),
            ("009", "Prima de Servicios",       TipoConcepto.DEVENGADO,  None,              True,  None),
            ("010", "Vacaciones",               TipoConcepto.DEVENGADO,  None,              True,  None),
            ("011", "Cesantías",                TipoConcepto.DEVENGADO,  None,              True,  None),
            ("012", "Intereses de Cesantías",   TipoConcepto.DEVENGADO,  Decimal("0.12"),   False, None),
            # Deducciones
            ("101", "Salud Empleado (4%)",      TipoConcepto.DEDUCCION,  Decimal("0.04"),   False, None),
            ("102", "Pensión Empleado (4%)",    TipoConcepto.DEDUCCION,  Decimal("0.04"),   False, None),
            ("103", "Fondo Solidaridad Pens.",  TipoConcepto.DEDUCCION,  Decimal("0.01"),   False, None),
            ("104", "Retención en la Fuente",   TipoConcepto.DEDUCCION,  None,              True,  None),
            ("105", "Libranza / Crédito",       TipoConcepto.DEDUCCION,  None,              True,  None),
            ("106", "Embargo Judicial",         TipoConcepto.DEDUCCION,  None,              True,  None),
            # Aportes empleador
            ("201", "Salud Empleador (8.5%)",   TipoConcepto.APORTE_EMP, Decimal("0.085"),  False, None),
            ("202", "Pensión Empleador (12%)",  TipoConcepto.APORTE_EMP, Decimal("0.12"),   False, None),
            ("203", "ARL",                      TipoConcepto.APORTE_EMP, None,              False, None),
            ("204", "Caja Compensación (4%)",   TipoConcepto.APORTE_EMP, Decimal("0.04"),   False, None),
            ("205", "SENA (2%)",                TipoConcepto.APORTE_EMP, Decimal("0.02"),   False, None),
            ("206", "ICBF (3%)",                TipoConcepto.APORTE_EMP, Decimal("0.03"),   False, None),
        ]
        for codigo, nombre, tipo, pct, manual, monto in basicos:
            self.db.add(ConceptoNomina(
                empresa_id=self.empresa_id, codigo=codigo,
                nombre=nombre, tipo=tipo, porcentaje=pct,
                es_manual=manual, monto=monto, activo=True
            ))
        self.db.commit()

    # ══════════════════════════════════════════════════════════
    # Liquidaciones
    # ══════════════════════════════════════════════════════════
    def listar_liquidaciones(self, empleado_id: int = None) -> List[Liquidacion]:
        q = (self.db.query(Liquidacion)
             .options(joinedload(Liquidacion.empleado).joinedload(Empleado.tercero))
             .filter(Liquidacion.empresa_id == self.empresa_id))
        if empleado_id:
            q = q.filter(Liquidacion.empleado_id == empleado_id)
        return q.order_by(Liquidacion.fecha_fin.desc()).all()

    def calcular_liquidacion(
        self,
        empleado_id: int,
        fecha_inicio: date,
        fecha_fin: date,
        lineas_extra: list = None,   # [{concepto_id, cantidad, valor_unitario}]
    ) -> dict:
        """
        Calcula la liquidación de nómina para un empleado en el período dado.
        Devuelve un dict con los totales y el detalle de cada concepto,
        sin guardar en base de datos todavía.
        """
        emp = self.obtener_empleado(empleado_id)
        if not emp:
            raise ValueError("Empleado no encontrado.")

        dias = (fecha_fin - fecha_inicio).days + 1
        salario = Decimal(str(emp.salario_base))
        salario_dia = salario / 30

        # IBC (base cotización) = salario; si < 1 SMLV usar SMLV
        ibc = max(salario, SALARIO_MINIMO_2026)

        tiene_auxilio = salario <= (SALARIO_MINIMO_2026 * 2)

        resultados = []

        def add(codigo, nombre, tipo, valor):
            resultados.append({
                "codigo": codigo, "nombre": nombre,
                "tipo": tipo, "valor": _redondear(valor)
            })

        # ── Devengados base ────────────────────────────────────
        salario_periodo = salario_dia * dias
        add("001", "Salario Básico", TipoConcepto.DEVENGADO, salario_periodo)

        if tiene_auxilio:
            aux_dia = AUXILIO_TRANSPORTE_2024 / 30
            add("002", "Auxilio de Transporte", TipoConcepto.DEVENGADO, aux_dia * dias)

        # ── Líneas extra (horas extras, comisiones, etc.) ──────
        if lineas_extra:
            for l in lineas_extra:
                concepto = self.db.get(ConceptoNomina, l["concepto_id"])
                if not concepto:
                    continue
                cantidad = Decimal(str(l.get("cantidad", 1)))
                v_unit   = Decimal(str(l.get("valor_unitario", 0)))
                # Si tiene porcentaje y no viene valor_unitario, calcularlo
                if concepto.porcentaje and v_unit == 0:
                    hora_ord = salario / 240   # 30 días × 8 horas
                    v_unit   = hora_ord * (1 + Decimal(str(concepto.porcentaje)))
                total = cantidad * v_unit
                resultados.append({
                    "codigo": concepto.codigo, "nombre": concepto.nombre,
                    "tipo": concepto.tipo, "valor": _redondear(total),
                    "concepto_id": concepto.id, "cantidad": cantidad,
                    "valor_unitario": _redondear(v_unit),
                })

        # ── Deducciones legales ────────────────────────────────
        add("101", "Salud Empleado (4%)",    TipoConcepto.DEDUCCION, ibc * Decimal("0.04"))
        add("102", "Pensión Empleado (4%)",  TipoConcepto.DEDUCCION, ibc * Decimal("0.04"))
        if salario > SALARIO_MINIMO_2026 * 4:
            add("103", "Fondo Solidaridad (1%)", TipoConcepto.DEDUCCION, ibc * Decimal("0.01"))

        # ── Aportes empleador ──────────────────────────────────
        add("201", "Salud Empleador (8.5%)",  TipoConcepto.APORTE_EMP, ibc * Decimal("0.085"))
        add("202", "Pensión Empleador (12%)", TipoConcepto.APORTE_EMP, ibc * Decimal("0.12"))
        tarifa_arl = ARL_TARIFAS.get(emp.nivel_riesgo_arl or 1, Decimal("0.00522"))
        add("203", f"ARL Nivel {emp.nivel_riesgo_arl or 1}", TipoConcepto.APORTE_EMP, ibc * tarifa_arl)
        add("204", "Caja Compensación (4%)", TipoConcepto.APORTE_EMP, salario * Decimal("0.04"))
        add("205", "SENA (2%)",              TipoConcepto.APORTE_EMP, salario * Decimal("0.02"))
        add("206", "ICBF (3%)",              TipoConcepto.APORTE_EMP, salario * Decimal("0.03"))

        # ── Totales ────────────────────────────────────────────
        devengado  = sum(r["valor"] for r in resultados if r["tipo"] == TipoConcepto.DEVENGADO)
        deduccion  = sum(r["valor"] for r in resultados if r["tipo"] == TipoConcepto.DEDUCCION)
        aporte_emp = sum(r["valor"] for r in resultados if r["tipo"] == TipoConcepto.APORTE_EMP)

        return {
            "empleado":        emp,
            "fecha_inicio":    fecha_inicio,
            "fecha_fin":       fecha_fin,
            "dias":            dias,
            "salario_base":    salario,
            "ibc":             ibc,
            "resultados":      resultados,
            "total_devengado": _redondear(devengado),
            "total_deduccion": _redondear(deduccion),
            "total_aporte_emp":_redondear(aporte_emp),
            "neto_pagar":      _redondear(devengado - deduccion),
        }

    def guardar_liquidacion(self, calculo: dict, periodo_id: int) -> Liquidacion:
        emp = calculo["empleado"]
        liq = Liquidacion(
            empresa_id      = self.empresa_id,
            empleado_id     = emp.id,
            periodo_id      = periodo_id,
            fecha_inicio    = calculo["fecha_inicio"],
            fecha_fin       = calculo["fecha_fin"],
            total_devengado = calculo["total_devengado"],
            total_deduccion = calculo["total_deduccion"],
            neto_pagar      = calculo["neto_pagar"],
            estado          = EstadoLiquidacion.BORRADOR,
        )
        self.db.add(liq)
        self.db.flush()

        for r in calculo["resultados"]:
            det = DetalleLiquidacion(
                liquidacion_id = liq.id,
                concepto_id    = r.get("concepto_id") or self._id_concepto(r["codigo"]),
                cantidad       = r.get("cantidad", Decimal("1")),
                valor_unitario = r.get("valor_unitario", r["valor"]),
                valor_total    = r["valor"],
            )
            self.db.add(det)

        self.db.commit()
        self.db.refresh(liq)
        return liq

    def _id_concepto(self, codigo: str) -> Optional[int]:
        c = self.db.query(ConceptoNomina).filter(
            ConceptoNomina.empresa_id == self.empresa_id,
            ConceptoNomina.codigo     == codigo,
        ).first()
        return c.id if c else None

    def aprobar_liquidacion(self, liq_id: int) -> Liquidacion:
        liq = self.db.get(Liquidacion, liq_id)
        if not liq or liq.empresa_id != self.empresa_id:
            raise ValueError("Liquidación no encontrada.")
        if liq.estado != EstadoLiquidacion.BORRADOR:
            raise ValueError("Solo se pueden aprobar liquidaciones en borrador.")
        liq.estado = EstadoLiquidacion.APROBADA
        self.db.commit()
        return liq

    def marcar_pagada(self, liq_id: int) -> Liquidacion:
        liq = self.db.get(Liquidacion, liq_id)
        if not liq or liq.empresa_id != self.empresa_id:
            raise ValueError("Liquidación no encontrada.")
        if liq.estado != EstadoLiquidacion.APROBADA:
            raise ValueError("La liquidación debe estar aprobada antes de marcarla como pagada.")
        liq.estado = EstadoLiquidacion.PAGADA
        self.db.commit()
        return liq
