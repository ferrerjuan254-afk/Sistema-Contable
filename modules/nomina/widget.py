from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QGroupBox, QHeaderView,
    QAbstractItemView, QComboBox, QFrame, QTabWidget,
    QSplitter, QDateEdit, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import QRegularExpression, Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QColor, QRegularExpressionValidator

from core.database import SessionLocal
from core.models.nomina import (
    TipoContrato, TipoConcepto, EstadoLiquidacion
)
from modules.nomina.service import NominaService, SALARIO_MINIMO_2026, AUXILIO_TRANSPORTE_2024

BTN_PRIMARY = "background:#2563eb;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_SUCCESS = "background:#059669;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_WARN    = "background:#d97706;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_DANGER  = "color:#dc2626;border:1px solid #fca5a5;padding:4px 10px;border-radius:5px;"

CONTRATOS = [
    ("Término Indefinido",  TipoContrato.INDEFINIDO),
    ("Término Fijo",        TipoContrato.FIJO),
    ("Obra o Labor",        TipoContrato.OBRA),
    ("Aprendizaje",         TipoContrato.APRENDIZAJE),
]

ESTADO_COLOR = {
    EstadoLiquidacion.BORRADOR: ("#92400e", "#fef3c7"),
    EstadoLiquidacion.APROBADA: ("#1d4ed8", "#dbeafe"),
    EstadoLiquidacion.PAGADA:   ("#166534", "#dcfce7"),
}

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _fmt(v) -> str:
    return f"${Decimal(str(v)):,.0f}"


# ══════════════════════════════════════════════════════════════
# Tab 1 — Empleados
# ══════════════════════════════════════════════════════════════
class TabEmpleados(QWidget):
    def __init__(self, service: NominaService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        tb = QHBoxLayout()
        self.lbl_total = QLabel()
        self.lbl_total.setStyleSheet("color:#64748b;font-size:12px;")
        btn_nuevo  = QPushButton("+ Nuevo empleado")
        btn_nuevo.setStyleSheet(BTN_PRIMARY)
        btn_nuevo.clicked.connect(self._nuevo)
        self.btn_editar  = QPushButton("✏️ Editar")
        self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self._editar)
        self.btn_retirar = QPushButton("🚪 Retirar")
        self.btn_retirar.setEnabled(False)
        self.btn_retirar.setStyleSheet(BTN_DANGER)
        self.btn_retirar.clicked.connect(self._retirar)
        tb.addWidget(self.lbl_total)
        tb.addStretch()
        tb.addWidget(btn_nuevo)
        tb.addWidget(self.btn_editar)
        tb.addWidget(self.btn_retirar)
        lay.addLayout(tb)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(
            ["Nombre", "Documento", "Cargo", "Contrato", "Salario Base", "Ingreso", "Riesgo ARL"]
        )
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(1, 120)
        self.tabla.setColumnWidth(2, 150)
        self.tabla.setColumnWidth(3, 120)
        self.tabla.setColumnWidth(4, 110)
        self.tabla.setColumnWidth(5, 90)
        self.tabla.setColumnWidth(6, 85)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Segoe UI", 11))
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        self.tabla.itemDoubleClicked.connect(lambda _: self._editar())
        lay.addWidget(self.tabla)

    def _cargar(self):
        self.tabla.setRowCount(0)
        self._empleados = self.service.listar_empleados()
        for emp in self._empleados:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)
            t = emp.tercero
            nombre = t.nombre if t else "—"
            doc    = t.numero_documento if t else "—"

            nombre_item = QTableWidgetItem(nombre)
            nombre_item.setData(Qt.ItemDataRole.UserRole, emp.id)
            self.tabla.setItem(r, 0, nombre_item)
            self.tabla.setItem(r, 1, QTableWidgetItem(doc))
            self.tabla.setItem(r, 2, QTableWidgetItem(emp.cargo or ""))

            contrato_str = {
                TipoContrato.INDEFINIDO:  "Indefinido",
                TipoContrato.FIJO:        "Fijo",
                TipoContrato.OBRA:        "Obra/Labor",
                TipoContrato.APRENDIZAJE: "Aprendizaje",
            }.get(emp.tipo_contrato, str(emp.tipo_contrato))
            self.tabla.setItem(r, 3, QTableWidgetItem(contrato_str))

            sal_item = QTableWidgetItem(_fmt(emp.salario_base))
            sal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(r, 4, sal_item)
            self.tabla.setItem(r, 5, QTableWidgetItem(str(emp.fecha_ingreso) if emp.fecha_ingreso else ""))
            self.tabla.setItem(r, 6, QTableWidgetItem(f"Nivel {emp.nivel_riesgo_arl or 1}"))

        self.lbl_total.setText(f"{len(self._empleados)} empleados activos")
        self.btn_editar.setEnabled(False)
        self.btn_retirar.setEnabled(False)

    def _on_sel(self):
        tiene = bool(self.tabla.selectedItems())
        self.btn_editar.setEnabled(tiene)
        self.btn_retirar.setEnabled(tiene)

    def _nuevo(self):
        dlg = DialogEmpleado(self.service, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.crear_empleado(dlg.datos())
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _editar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        emp_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        emp    = self.service.obtener_empleado(emp_id)
        dlg    = DialogEmpleado(self.service, parent=self, empleado=emp)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar_empleado(emp_id, dlg.datos())
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _retirar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        nombre = self.tabla.item(fila, 0).text()
        emp_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        dlg = DialogFechaRetiro(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.retirar_empleado(emp_id, dlg.fecha())
                self._cargar()
                QMessageBox.information(self, "Retiro registrado",
                                        f"✅ {nombre} retirado correctamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._cargar()

    def empleados(self):
        return self._empleados


# ══════════════════════════════════════════════════════════════
# Tab 2 — Conceptos de Nómina
# ══════════════════════════════════════════════════════════════
class TabConceptos(QWidget):
    def __init__(self, service: NominaService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        nota = QLabel(
            "ℹ️  Los conceptos legales obligatorios (salud, pensión, ARL, parafiscales) "
            "se calculan automáticamente al liquidar. Aquí puedes agregar o editar conceptos "
            "propios de la empresa. Doble clic en un concepto para editarlo."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet(
            "background:#eff6ff;color:#1d4ed8;padding:8px 12px;"
            "border-radius:6px;font-size:12px;"
        )
        lay.addWidget(nota)

        tb = QHBoxLayout()
        btn_nuevo = QPushButton("+ Nuevo concepto")
        btn_nuevo.setStyleSheet(BTN_PRIMARY)
        btn_nuevo.clicked.connect(self._nuevo)
        self.btn_eliminar = QPushButton("🗑 Eliminar concepto")
        self.btn_eliminar.setStyleSheet("color:#dc2626;border:1px solid #fca5a5;padding:4px 10px;border-radius:5px;")
        self.btn_eliminar.setEnabled(False)
        self.btn_eliminar.clicked.connect(self._eliminar)
        tb.addStretch()
        tb.addWidget(self.btn_eliminar)
        tb.addWidget(btn_nuevo)
        lay.addLayout(tb)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Código", "Nombre", "Tipo", "Cálculo", "Valor/Porcentaje", "Activo"]
        )
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 70)
        self.tabla.setColumnWidth(2, 130)
        self.tabla.setColumnWidth(3, 90)
        self.tabla.setColumnWidth(4, 130)
        self.tabla.setColumnWidth(5, 55)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        self.tabla.itemDoubleClicked.connect(lambda _: self._editar())
        lay.addWidget(self.tabla)

    def _cargar(self):
        self.tabla.setRowCount(0)
        for c in self.service.listar_conceptos():
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)
            cod_item = QTableWidgetItem(c.codigo)
            cod_item.setData(Qt.ItemDataRole.UserRole, c.id)
            self.tabla.setItem(r, 0, cod_item)
            self.tabla.setItem(r, 1, QTableWidgetItem(c.nombre))
            tipo_str = {"devengado": "Devengado", "deduccion": "Deducción",
                        "aporte_empleador": "Aporte Empleador"}.get(
                c.tipo.value if hasattr(c.tipo, 'value') else c.tipo, str(c.tipo))
            tipo_item = QTableWidgetItem(tipo_str)
            color = {"devengado": "#15803d", "deduccion": "#b91c1c",
                     "aporte_empleador": "#1d4ed8"}.get(
                c.tipo.value if hasattr(c.tipo, 'value') else c.tipo, "#374151")
            tipo_item.setForeground(QColor(color))
            self.tabla.setItem(r, 2, tipo_item)
            es_manual = getattr(c, 'es_manual', False)
            calc_item = QTableWidgetItem("Manual" if es_manual else "Porcentaje")
            calc_item.setForeground(QColor("#92400e" if es_manual else "#1d4ed8"))
            self.tabla.setItem(r, 3, calc_item)
            if es_manual:
                monto = getattr(c, 'monto', None)
                val_str = f"${float(monto):,.2f}" if monto else "—"
            else:
                val_str = f"{float(c.porcentaje)*100:.2f}%" if c.porcentaje else "—"
            self.tabla.setItem(r, 4, QTableWidgetItem(val_str))
            act = QTableWidgetItem("✔" if c.activo else "")
            act.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(r, 5, act)
        self.btn_eliminar.setEnabled(False)

    def _on_sel(self):
        self.btn_eliminar.setEnabled(bool(self.tabla.selectedItems()))

    def _nuevo(self):
        dlg = DialogConcepto(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.crear_concepto(dlg.datos())
                self._cargar()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _editar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        concepto_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        concepto = self.service.db.get(
            __import__('core.models.nomina', fromlist=['ConceptoNomina']).ConceptoNomina,
            concepto_id
        )
        dlg = DialogConcepto(self, concepto=concepto)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.actualizar_concepto(concepto_id, dlg.datos())
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _eliminar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        nombre = self.tabla.item(fila, 1).text()
        concepto_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        resp = QMessageBox.question(
            self, "Eliminar concepto",
            f"¿Desactivar el concepto '{nombre}'?\nNo se eliminará permanentemente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.service.eliminar_concepto(concepto_id)
            self._cargar()


# ══════════════════════════════════════════════════════════════
# Tab 3 — Liquidar Nómina
# ══════════════════════════════════════════════════════════════
class TabLiquidar(QWidget):
    def __init__(self, service: NominaService, parent=None):
        super().__init__(parent)
        self.service   = service
        self._calculo  = None
        self._build_ui()
        self._cargar_empleados()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # ── Parámetros ────────────────────────────────────────
        grp = QGroupBox("Parámetros de liquidación")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        gl = QHBoxLayout(grp)

        self.cb_empleado = QComboBox()
        self.cb_empleado.setFixedWidth(280)

        self.de_inicio = QDateEdit()
        self.de_inicio.setCalendarPopup(True)
        hoy = date.today()
        self.de_inicio.setDate(QDate(hoy.year, hoy.month, 1))
        self.de_inicio.setFixedWidth(120)

        self.de_fin = QDateEdit()
        self.de_fin.setCalendarPopup(True)
        import calendar
        ultimo = calendar.monthrange(hoy.year, hoy.month)[1]
        self.de_fin.setDate(QDate(hoy.year, hoy.month, ultimo))
        self.de_fin.setFixedWidth(120)

        btn_calc = QPushButton("🧮 Calcular")
        btn_calc.setStyleSheet(BTN_PRIMARY)
        btn_calc.clicked.connect(self._calcular)

        gl.addWidget(QLabel("Empleado:"))
        gl.addWidget(self.cb_empleado)
        gl.addWidget(QLabel("  Del:"))
        gl.addWidget(self.de_inicio)
        gl.addWidget(QLabel("  Al:"))
        gl.addWidget(self.de_fin)
        gl.addWidget(btn_calc)
        gl.addStretch()
        lay.addWidget(grp)

        # ── Extras (horas extras, comisiones) ─────────────────
        grp_ext = QGroupBox("Conceptos adicionales (opcional)")
        grp_ext.setStyleSheet("QGroupBox{font-weight:bold;}")
        gex = QVBoxLayout(grp_ext)

        ext_tb = QHBoxLayout()
        self.cb_concepto_extra = QComboBox()
        self.cb_concepto_extra.setFixedWidth(240)
        self.spin_cantidad = QDoubleSpinBox()
        self.spin_cantidad.setRange(0, 999)
        self.spin_cantidad.setDecimals(2)
        self.spin_cantidad.setValue(1)
        self.spin_cantidad.setFixedWidth(80)
        self.spin_valor = QDoubleSpinBox()
        self.spin_valor.setRange(0, 99999999)
        self.spin_valor.setDecimals(2)
        self.spin_valor.setPrefix("$ ")
        self.spin_valor.setFixedWidth(140)
        btn_add_extra = QPushButton("+ Agregar")
        btn_add_extra.clicked.connect(self._agregar_extra)

        ext_tb.addWidget(QLabel("Concepto:"))
        ext_tb.addWidget(self.cb_concepto_extra)
        ext_tb.addWidget(QLabel("Cantidad:"))
        ext_tb.addWidget(self.spin_cantidad)
        ext_tb.addWidget(QLabel("Valor unit.:"))
        ext_tb.addWidget(self.spin_valor)
        ext_tb.addWidget(btn_add_extra)
        ext_tb.addStretch()
        gex.addLayout(ext_tb)

        self.tbl_extras = QTableWidget(0, 4)
        self.tbl_extras.setHorizontalHeaderLabels(["Concepto", "Cantidad", "Valor unit.", "Total"])
        self.tbl_extras.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_extras.setColumnWidth(1, 80)
        self.tbl_extras.setColumnWidth(2, 110)
        self.tbl_extras.setColumnWidth(3, 110)
        self.tbl_extras.setFixedHeight(110)
        self.tbl_extras.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_extras.verticalHeader().setVisible(False)
        self.tbl_extras.setAlternatingRowColors(False)

        btn_del_extra = QPushButton("🗑 Quitar fila")
        btn_del_extra.setStyleSheet("color:#dc2626;font-size:11px;")
        btn_del_extra.clicked.connect(self._quitar_extra)

        gex.addWidget(self.tbl_extras)
        gex.addWidget(btn_del_extra, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(grp_ext)

        # ── Resultado ─────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tabla resultado — columna Valor editable para ajustes manuales
        self.tbl_resultado = QTableWidget(0, 3)
        self.tbl_resultado.setHorizontalHeaderLabels(["Concepto", "Tipo", "Valor"])
        hhr = self.tbl_resultado.horizontalHeader()
        hhr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_resultado.setColumnWidth(1, 120)
        self.tbl_resultado.setColumnWidth(2, 120)
        # Solo la columna Valor (2) es editable
        self.tbl_resultado.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                                           QAbstractItemView.EditTrigger.SelectedClicked)
        self.tbl_resultado.verticalHeader().setVisible(False)
        self.tbl_resultado.setAlternatingRowColors(False)
        self.tbl_resultado.cellChanged.connect(self._on_resultado_changed)
        splitter.addWidget(self.tbl_resultado)

        # Resumen
        resumen_w = QWidget()
        resumen_w.setStyleSheet("background:#f8fafc;")
        rlay = QVBoxLayout(resumen_w)
        rlay.setContentsMargins(16, 16, 16, 16)
        rlay.setSpacing(12)

        self.lbl_empleado_res = QLabel("—")
        self.lbl_empleado_res.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_empleado_res.setWordWrap(True)
        rlay.addWidget(self.lbl_empleado_res)

        def kv(label, attr):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#64748b;font-size:12px;")
            val = QLabel("—")
            val.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            rlay.addLayout(row)
            setattr(self, attr, val)

        kv("Total devengado:",   "lbl_devengado")
        kv("Total deducciones:", "lbl_deduccion")
        kv("Neto a pagar:",      "lbl_neto")
        kv("Costo empleador:",   "lbl_costo")

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;"); rlay.addWidget(sep)

        self.btn_guardar = QPushButton("💾 Guardar liquidación")
        self.btn_guardar.setStyleSheet(BTN_SUCCESS)
        self.btn_guardar.setEnabled(False)
        self.btn_guardar.clicked.connect(self._guardar)
        rlay.addWidget(self.btn_guardar)
        rlay.addStretch()
        splitter.addWidget(resumen_w)
        splitter.setSizes([600, 260])
        lay.addWidget(splitter, stretch=1)

        self._extras_data = []   # lista de {concepto_id, cantidad, valor_unitario}

    def _on_resultado_changed(self, row, col):
        """Permite editar solo la columna Valor (col 2); protege Concepto y Tipo."""
        if col != 2:
            # Revertir cambio accidental en otras columnas
            item = self.tbl_resultado.item(row, col)
            if item:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            return
        # Recalcular resumen con los valores actuales de la tabla
        self._recalcular_resumen()

    def _recalcular_resumen(self):
        """Recalcula devengado/deduccion/neto/costo desde los valores actuales de la tabla."""
        self.tbl_resultado.blockSignals(True)
        try:
            devengado = Decimal("0"); deduccion = Decimal("0"); aporte_emp = Decimal("0")
            for r in range(self.tbl_resultado.rowCount()):
                tipo_item = self.tbl_resultado.item(r, 1)
                val_item  = self.tbl_resultado.item(r, 2)
                if not tipo_item or not val_item:
                    continue
                tipo_str = tipo_item.text()
                try:
                    val = Decimal(val_item.text().replace(",", "").replace("$", "").strip() or "0")
                except Exception:
                    val = Decimal("0")
                if tipo_str == "Devengado":
                    devengado += val
                elif tipo_str in ("Deducción", "Deduccion"):
                    deduccion += val
                elif tipo_str == "Aporte Emp.":
                    aporte_emp += val
            neto = devengado - deduccion
            self.lbl_devengado.setText(_fmt(devengado))
            self.lbl_deduccion.setText(_fmt(deduccion))
            self.lbl_neto.setText(_fmt(neto))
            self.lbl_costo.setText(_fmt(devengado + aporte_emp))
            if self._calculo:
                self._calculo["total_devengado"] = devengado
                self._calculo["total_deduccion"] = deduccion
                self._calculo["neto_pagar"]       = neto
                self._calculo["total_aporte_emp"] = aporte_emp
                for r in range(self.tbl_resultado.rowCount()):
                    val_item = self.tbl_resultado.item(r, 2)
                    if val_item and r < len(self._calculo["resultados"]):
                        try:
                            self._calculo["resultados"][r]["valor"] = Decimal(
                                val_item.text().replace(",","").replace("$","").strip() or "0")
                        except Exception:
                            pass
        finally:
            self.tbl_resultado.blockSignals(False)

    def _cargar_empleados(self):
        self.service.db.expire_all()
        self.cb_empleado.clear()
        self.cb_empleado.addItem("— Seleccionar empleado —", None)
        for emp in self.service.listar_empleados():
            nombre = emp.tercero.nombre if emp.tercero else f"Emp {emp.id}"
            self.cb_empleado.addItem(nombre, emp.id)

        self.cb_concepto_extra.clear()
        for c in self.service.listar_conceptos():
            tipo_v = c.tipo.value if hasattr(c.tipo, 'value') else c.tipo
            if tipo_v in ("devengado", "deduccion"):
                self.cb_concepto_extra.addItem(f"{c.codigo} – {c.nombre}", c.id)
    def _agregar_extra(self):
        cid = self.cb_concepto_extra.currentData()
        if not cid:
            return
        nombre   = self.cb_concepto_extra.currentText()
        cantidad = self.spin_cantidad.value()
        valor    = self.spin_valor.value()
        total    = cantidad * valor
        self._extras_data.append({"concepto_id": cid, "cantidad": cantidad, "valor_unitario": valor})
        r = self.tbl_extras.rowCount()
        self.tbl_extras.insertRow(r)
        self.tbl_extras.setItem(r, 0, QTableWidgetItem(nombre))
        self.tbl_extras.setItem(r, 1, QTableWidgetItem(str(cantidad)))
        v_item = QTableWidgetItem(_fmt(valor))
        v_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tbl_extras.setItem(r, 2, v_item)
        t_item = QTableWidgetItem(_fmt(total))
        t_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tbl_extras.setItem(r, 3, t_item)

    def _quitar_extra(self):
        fila = self.tbl_extras.currentRow()
        if fila >= 0:
            self.tbl_extras.removeRow(fila)
            self._extras_data.pop(fila)

    def _calcular(self):
        emp_id = self.cb_empleado.currentData()
        if not emp_id:
            QMessageBox.warning(self, "Falta empleado", "Selecciona un empleado.")
            return
        qd1 = self.de_inicio.date()
        qd2 = self.de_fin.date()
        f1  = date(qd1.year(), qd1.month(), qd1.day())
        f2  = date(qd2.year(), qd2.month(), qd2.day())
        if f2 < f1:
            QMessageBox.warning(self, "Fechas inválidas", "La fecha final debe ser posterior a la inicial.")
            return
        try:
            self._calculo = self.service.calcular_liquidacion(
                emp_id, f1, f2, lineas_extra=self._extras_data or None)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        c = self._calculo
        nombre_emp = c["empleado"].tercero.nombre if c["empleado"].tercero else "?"
        self.lbl_empleado_res.setText(
            f"{nombre_emp}\n{c['fecha_inicio']} → {c['fecha_fin']}  ({c['dias']} días)")
        self.lbl_devengado.setText(_fmt(c["total_devengado"]))
        self.lbl_devengado.setStyleSheet("color:#15803d;font-size:13px;font-weight:bold;")
        self.lbl_deduccion.setText(_fmt(c["total_deduccion"]))
        self.lbl_deduccion.setStyleSheet("color:#b91c1c;font-size:13px;font-weight:bold;")
        self.lbl_neto.setText(_fmt(c["neto_pagar"]))
        self.lbl_neto.setStyleSheet("color:#1d4ed8;font-size:15px;font-weight:bold;")
        self.lbl_costo.setText(_fmt(c["total_devengado"] + c["total_aporte_emp"]))
        self.lbl_costo.setStyleSheet("color:#7c3aed;font-size:13px;font-weight:bold;")
        self.tbl_resultado.blockSignals(True)
        self.tbl_resultado.setRowCount(0)
        for res in c["resultados"]:
            r = self.tbl_resultado.rowCount()
            self.tbl_resultado.insertRow(r)
            nombre_item = QTableWidgetItem(res["nombre"])
            nombre_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.tbl_resultado.setItem(r, 0, nombre_item)
            tipo_v = res["tipo"].value if hasattr(res["tipo"], "value") else res["tipo"]
            tipo_str = {"devengado": "Devengado", "deduccion": "Deducción",
                        "aporte_empleador": "Aporte Emp."}.get(tipo_v, tipo_v)
            tipo_item = QTableWidgetItem(tipo_str)
            tipo_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            tipo_item.setForeground(QColor(
                {"devengado":"#15803d","deduccion":"#b91c1c",
                 "aporte_empleador":"#6d28d9"}.get(tipo_v,"#374151")))
            self.tbl_resultado.setItem(r, 1, tipo_item)
            val_item = QTableWidgetItem(str(res["valor"]))
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_item.setToolTip("Doble clic para editar el valor")
            self.tbl_resultado.setItem(r, 2, val_item)
        self.tbl_resultado.blockSignals(False)
        self.btn_guardar.setEnabled(True)

    def _guardar(self):
        if not self._calculo:
            return
        from core.models.contabilidad import PeriodoContable, EstadoPeriodo
        periodo = (
            self.service.db.query(PeriodoContable)
            .filter(PeriodoContable.empresa_id == self.service.empresa_id,
                    PeriodoContable.estado == EstadoPeriodo.ABIERTO)
            .order_by(PeriodoContable.anio.desc(), PeriodoContable.mes.desc())
            .first()
        )
        if not periodo:
            QMessageBox.warning(self, "Sin periodo",
                "No hay un periodo contable abierto.\nCrea uno en el módulo de Contabilidad.")
            return
        try:
            liq = self.service.guardar_liquidacion(self._calculo, periodo.id)
            QMessageBox.information(self, "Liquidación guardada",
                f"✅ Liquidación #{liq.id} guardada como Borrador.\n"
                f"Neto a pagar: {_fmt(liq.neto_pagar)}")
            self._calculo = None
            self.btn_guardar.setEnabled(False)
            self.tbl_resultado.setRowCount(0)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


    def showEvent(self, event):
        super().showEvent(event)
        self._cargar_empleados()

    def refresh(self):
        self._cargar_empleados()


# ══════════════════════════════════════════════════════════════
# Tab 4 — Historial de Liquidaciones
# ══════════════════════════════════════════════════════════════
class TabHistorial(QWidget):
    def __init__(self, service: NominaService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        tb = QHBoxLayout()
        self.cb_empleado = QComboBox()
        self.cb_empleado.setFixedWidth(260)
        self.cb_empleado.addItem("Todos los empleados", None)
        for emp in self.service.listar_empleados():
            nombre = emp.tercero.nombre if emp.tercero else f"Emp {emp.id}"
            self.cb_empleado.addItem(nombre, emp.id)
        self.cb_empleado.currentIndexChanged.connect(self._cargar)

        btn_ref = QPushButton("🔄")
        btn_ref.setFixedWidth(36)
        btn_ref.clicked.connect(self._cargar)

        self.btn_aprobar = QPushButton("✅ Aprobar")
        self.btn_aprobar.setStyleSheet(BTN_SUCCESS)
        self.btn_aprobar.setEnabled(False)
        self.btn_aprobar.clicked.connect(self._aprobar)

        self.btn_pagar = QPushButton("💳 Marcar pagada")
        self.btn_pagar.setStyleSheet(BTN_WARN)
        self.btn_pagar.setEnabled(False)
        self.btn_pagar.clicked.connect(self._pagar)

        tb.addWidget(QLabel("Empleado:"))
        tb.addWidget(self.cb_empleado)
        tb.addWidget(btn_ref)
        tb.addStretch()
        tb.addWidget(self.btn_aprobar)
        tb.addWidget(self.btn_pagar)
        lay.addLayout(tb)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels(
            ["#", "Empleado", "Período", "Devengado", "Deducciones", "Neto a pagar", "Estado"]
        )
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 50)
        self.tabla.setColumnWidth(2, 180)
        self.tabla.setColumnWidth(3, 110)
        self.tabla.setColumnWidth(4, 100)
        self.tabla.setColumnWidth(5, 110)
        self.tabla.setColumnWidth(6, 100)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.itemSelectionChanged.connect(self._on_sel)
        splitter.addWidget(self.tabla)

        # Detalle de la liquidación seleccionada
        grp = QGroupBox("Detalle de la liquidación seleccionada")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        gl = QVBoxLayout(grp)
        self.tbl_det = QTableWidget(0, 3)
        self.tbl_det.setHorizontalHeaderLabels(["Concepto", "Tipo", "Valor"])
        self.tbl_det.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_det.setColumnWidth(1, 130)
        self.tbl_det.setColumnWidth(2, 120)
        self.tbl_det.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_det.verticalHeader().setVisible(False)
        self.tbl_det.setAlternatingRowColors(False)
        gl.addWidget(self.tbl_det)
        splitter.addWidget(grp)
        splitter.setSizes([280, 220])
        lay.addWidget(splitter)

    def _cargar(self):
        emp_id = self.cb_empleado.currentData()
        self._liqlist = self.service.listar_liquidaciones(empleado_id=emp_id)
        self.tabla.setRowCount(0)
        for liq in self._liqlist:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)
            id_item = QTableWidgetItem(str(liq.id))
            id_item.setData(Qt.ItemDataRole.UserRole, liq.id)
            self.tabla.setItem(r, 0, id_item)
            nombre = liq.empleado.tercero.nombre if (liq.empleado and liq.empleado.tercero) else "—"
            self.tabla.setItem(r, 1, QTableWidgetItem(nombre))
            self.tabla.setItem(r, 2, QTableWidgetItem(
                f"{liq.fecha_inicio} → {liq.fecha_fin}"
            ))
            for col, val in [(3, liq.total_devengado), (4, liq.total_deduccion), (5, liq.neto_pagar)]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabla.setItem(r, col, it)

            estado_v = liq.estado.value if hasattr(liq.estado, "value") else liq.estado
            estado_str = {"borrador": "Borrador", "aprobada": "Aprobada",
                          "pagada": "Pagada"}.get(estado_v, estado_v)
            est_item = QTableWidgetItem(estado_str)
            color_fg, color_bg = ESTADO_COLOR.get(liq.estado, ("#374151", "#f8fafc"))
            est_item.setForeground(QColor(color_fg))
            est_item.setBackground(QColor(color_bg))
            self.tabla.setItem(r, 6, est_item)

        self.btn_aprobar.setEnabled(False)
        self.btn_pagar.setEnabled(False)
        self.tbl_det.setRowCount(0)

    def _on_sel(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        liq_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        liq    = next((l for l in self._liqlist if l.id == liq_id), None)
        if not liq:
            return

        estado_v = liq.estado.value if hasattr(liq.estado, "value") else liq.estado
        self.btn_aprobar.setEnabled(estado_v == "borrador")
        self.btn_pagar.setEnabled(estado_v == "aprobada")

        # Detalle
        from sqlalchemy.orm import joinedload as jl
        from core.models.nomina import DetalleLiquidacion, ConceptoNomina
        detalles = (
            self.service.db.query(DetalleLiquidacion)
            .filter(DetalleLiquidacion.liquidacion_id == liq_id)
            .all()
        )
        self.tbl_det.setRowCount(0)
        for d in detalles:
            r = self.tbl_det.rowCount()
            self.tbl_det.insertRow(r)
            concepto = self.service.db.get(ConceptoNomina, d.concepto_id)
            nombre_c = concepto.nombre if concepto else f"Concepto {d.concepto_id}"
            self.tbl_det.setItem(r, 0, QTableWidgetItem(nombre_c))
            tipo_str = ""
            if concepto:
                tv = concepto.tipo.value if hasattr(concepto.tipo, "value") else concepto.tipo
                tipo_str = {"devengado": "Devengado", "deduccion": "Deducción",
                            "aporte_empleador": "Aporte Emp."}.get(tv, tv)
            tipo_item = QTableWidgetItem(tipo_str)
            self.tbl_det.setItem(r, 1, tipo_item)
            val_item = QTableWidgetItem(_fmt(d.valor_total))
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_det.setItem(r, 2, val_item)

    def _aprobar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        liq_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        try:
            self.service.aprobar_liquidacion(liq_id)
            self._cargar()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _pagar(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        liq_id = self.tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        resp = QMessageBox.question(
            self, "Confirmar pago",
            "¿Marcar esta liquidación como pagada?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                self.service.marcar_pagada(liq_id)
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._cargar()


# ══════════════════════════════════════════════════════════════
# Diálogos auxiliares
# ══════════════════════════════════════════════════════════════
class DialogEmpleado(QDialog):
    def __init__(self, service: NominaService, parent=None, empleado=None):
        super().__init__(parent)
        self.service  = service
        self.empleado = empleado
        self.setWindowTitle("Nuevo empleado" if not empleado else "Editar empleado")
        self.setMinimumWidth(560)
        self._build_ui()
        if empleado:
            self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # Tercero
        grp1 = QGroupBox("Persona")
        grp1.setStyleSheet("QGroupBox{font-weight:bold;}")
        f1 = QFormLayout(grp1)
        self.cb_tercero = QComboBox()
        if not self.empleado:
            terceros = self.service.listar_terceros_sin_empleado()
            self.cb_tercero.addItem("— Seleccionar —", None)
            for t in terceros:
                self.cb_tercero.addItem(f"{t.numero_documento} — {t.nombre}", t.id)
        else:
            t = self.empleado.tercero
            self.cb_tercero.addItem(f"{t.numero_documento} — {t.nombre}" if t else "—",
                                    self.empleado.tercero_id)
            self.cb_tercero.setEnabled(False)
        f1.addRow("Tercero *:", self.cb_tercero)
        lay.addWidget(grp1)

        # Contrato
        grp2 = QGroupBox("Contrato")
        grp2.setStyleSheet("QGroupBox{font-weight:bold;}")
        f2 = QFormLayout(grp2)
        f2.setSpacing(8)

        self.f_cargo = QLineEdit()
        self.f_cargo.setPlaceholderText("Ej: Auxiliar Contable")
        self.f_depto = QLineEdit()
        self.f_depto.setPlaceholderText("Ej: Contabilidad")

        self.cb_contrato = QComboBox()
        for label, val in CONTRATOS:
            self.cb_contrato.addItem(label, val)

        
        
        self.line_salario = QLineEdit()
        self.line_salario.setPlaceholderText('$ 0,00')
        
        # Validación: Permite números y una sola coma decimal
        regex = QRegularExpression(r'^[0-9]*,?[0-9]*$')
        validador = QRegularExpressionValidator(regex)
        self.line_salario.setValidator(validador)
        
        # Conectar señal de cambio de texto
        self.line_salario.textChanged.connect(self.aplicar_formato)

        self.de_ingreso = QDateEdit(QDate.currentDate())
        self.de_ingreso.setCalendarPopup(True)

        self.spin_riesgo = QSpinBox()
        self.spin_riesgo.setRange(1, 5)
        self.spin_riesgo.setValue(1)

        f2.addRow("Cargo:", self.f_cargo)
        f2.addRow("Departamento:", self.f_depto)
        f2.addRow("Tipo contrato *:", self.cb_contrato)
        f2.addRow("Salario base *:", self.line_salario)
        f2.addRow("Fecha de ingreso *:", self.de_ingreso)
        f2.addRow("Nivel riesgo ARL (1-5):", self.spin_riesgo)
        lay.addWidget(grp2)

        # Seguridad social
        grp3 = QGroupBox("Entidades de Seguridad Social")
        grp3.setStyleSheet("QGroupBox{font-weight:bold;}")
        f3 = QFormLayout(grp3)
        f3.setSpacing(8)
        self.f_eps   = QLineEdit(); self.f_eps.setPlaceholderText("Ej: Sura, Sanitas")
        self.f_pension = QLineEdit(); self.f_pension.setPlaceholderText("Ej: Colpensiones, Porvenir")
        self.f_cesantias = QLineEdit(); self.f_cesantias.setPlaceholderText("Ej: Porvenir, Protección")
        self.f_arl    = QLineEdit(); self.f_arl.setPlaceholderText("Ej: Positiva, Sura")
        self.f_caja   = QLineEdit(); self.f_caja.setPlaceholderText("Ej: Compensar, Cafam")
        f3.addRow("EPS:", self.f_eps)
        f3.addRow("Fondo Pensión:", self.f_pension)
        f3.addRow("Fondo Cesantías:", self.f_cesantias)
        f3.addRow("ARL:", self.f_arl)
        f3.addRow("Caja Compensación:", self.f_caja)
        lay.addWidget(grp3)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar"); btn_ok.setDefault(True)
        btn_ok.setStyleSheet(BTN_PRIMARY); btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)
        
    def aplicar_formato(self, texto):
        # 1. Desconectar señal para evitar bucle infinito
        self.line_salario.textChanged.disconnect(self.aplicar_formato)
        
        # Guardar la posición actual del cursor para que no se salte al final
        posicion_cursor = self.line_salario.cursorPosition()
        longitud_original = len(texto)
        
        # 2. Limpiar el texto de caracteres de formato anteriores
        texto_limpio = texto.replace("$", "").replace(".", "").strip()
        
        if not texto_limpio or texto_limpio == ",":
            self.line_salario.setText("")
            self.line_salario.valor = 0.0
        else:
            # 3. Separar parte entera y parte decimal
            if "," in texto_limpio:
                partes = texto_limpio.split(",")
                entera = partes[0]
                # Limitar a 2 decimales para evitar desbordamiento visual
                decimal = partes[1][:2] if len(partes) > 1 else ""
                tiene_coma = True
            else:
                entera = texto_limpio
                decimal = ""
                tiene_coma = False
            
            # Formatear la parte entera con puntos de miles
            if entera:
                entera_formateada = f"{int(entera):,}".replace(",", ".")
            else:
                entera_formateada = "0" if tiene_coma else ""
            
            # Reconstruir el texto visual
            nuevo_texto = f"$ {entera_formateada}"
            if tiene_coma:
                nuevo_texto += f",{decimal}"
            
            self.line_salario.setText(nuevo_texto)
            
            # 4. Ajustar la posición del cursor de forma inteligente
            nueva_longitud = len(nuevo_texto)
            desplazamiento = nueva_longitud - longitud_original
            self.line_salario.setCursorPosition(max(0, posicion_cursor + desplazamiento))
            
            # 5. Guardar el valor numérico real (Float interno)
            # Reemplazamos la coma por punto para que Python lo entienda como float
            float_string = texto_limpio.replace(",", ".")
            try:
                self.line_salario.valor = float(float_string)
            except ValueError:
                self.line_salario.valor = 0.0

        # 6. Reconectar la señal e imprimir valor interno
        self.line_salario.textChanged.connect(self.aplicar_formato)

    def _cargar(self):
        e = self.empleado
        self.f_cargo.setText(e.cargo or "")
        self.f_depto.setText(e.departamento or "")
        for i in range(self.cb_contrato.count()):
            if self.cb_contrato.itemData(i) == e.tipo_contrato:
                self.cb_contrato.setCurrentIndex(i); break
        self.line_salario.setText(str(e.salario_base).replace(".",","))
        if e.fecha_ingreso:
            self.de_ingreso.setDate(QDate(e.fecha_ingreso.year, e.fecha_ingreso.month, e.fecha_ingreso.day))
        self.spin_riesgo.setValue(e.nivel_riesgo_arl or 1)
        self.f_eps.setText(e.eps or "")
        self.f_pension.setText(e.fondo_pension or "")
        self.f_cesantias.setText(e.fondo_cesantias or "")
        self.f_arl.setText(e.arl or "")
        self.f_caja.setText(e.caja_compensacion or "")

    def _guardar(self):
        if not self.empleado and not self.cb_tercero.currentData():
            QMessageBox.warning(self, "Falta persona", "Selecciona una persona para el empleado.")
            return
        self.accept()

    def datos(self) -> dict:
        qd = self.de_ingreso.date()
        d = {
            "tercero_id":        self.cb_tercero.currentData(),
            "cargo":             self.f_cargo.text().strip() or None,
            "departamento":      self.f_depto.text().strip() or None,
            "tipo_contrato":     self.cb_contrato.currentData(),
            "salario_base":      Decimal(str(float(self.line_salario.valor))),
            "fecha_ingreso":     date(qd.year(), qd.month(), qd.day()),
            "nivel_riesgo_arl":  self.spin_riesgo.value(),
            "eps":               self.f_eps.text().strip() or None,
            "fondo_pension":     self.f_pension.text().strip() or None,
            "fondo_cesantias":   self.f_cesantias.text().strip() or None,
            "arl":               self.f_arl.text().strip() or None,
            "caja_compensacion": self.f_caja.text().strip() or None,
        }
        if self.empleado:
            d.pop("tercero_id")
        return d


class DialogConcepto(QDialog):
    def __init__(self, parent=None, concepto=None):
        super().__init__(parent)
        self.concepto = concepto
        self.setWindowTitle("Nuevo concepto de nómina" if not concepto else "Editar concepto")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(10)

        self.f_codigo = QLineEdit(); self.f_codigo.setMaxLength(20)
        self.f_nombre = QLineEdit()

        self.cb_tipo = QComboBox()
        self.cb_tipo.addItem("Devengado",        TipoConcepto.DEVENGADO)
        self.cb_tipo.addItem("Deducción",        TipoConcepto.DEDUCCION)
        self.cb_tipo.addItem("Aporte Empleador", TipoConcepto.APORTE_EMP)

        # Cálculo: Porcentaje o Manual
        self.cb_calculo = QComboBox()
        self.cb_calculo.addItem("Porcentaje", False)   # es_manual=False
        self.cb_calculo.addItem("Manual",     True)    # es_manual=True
        self.cb_calculo.currentIndexChanged.connect(self._on_calculo_changed)

        # Campo porcentaje (visible cuando es porcentaje)
        self.spin_pct = QDoubleSpinBox()
        self.spin_pct.setRange(0, 100); self.spin_pct.setDecimals(4)
        self.spin_pct.setSuffix(" %")

        # Campo monto predeterminado (visible cuando es manual, opcional)
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0, 99_999_999); self.spin_monto.setDecimals(2)
        self.spin_monto.setPrefix("$ "); self.spin_monto.setSingleStep(1000)
        self.lbl_monto_hint = QLabel("Opcional. Deja en 0 si el usuario lo ingresará manualmente.")
        self.lbl_monto_hint.setStyleSheet("color:#64748b;font-size:11px;")
        self.lbl_monto_hint.setWordWrap(True)

        form.addRow("Código *:",   self.f_codigo)
        form.addRow("Nombre *:",   self.f_nombre)
        form.addRow("Tipo *:",     self.cb_tipo)
        form.addRow("Cálculo:",    self.cb_calculo)
        self._row_pct   = form.rowCount()
        form.addRow("Porcentaje:", self.spin_pct)
        self._row_monto = form.rowCount()
        form.addRow("Valor predeterminado:", self.spin_monto)
        form.addRow("", self.lbl_monto_hint)
        lay.addLayout(form)

        self._form = form
        self._on_calculo_changed()   # set initial visibility

        btns = QHBoxLayout(); btns.addStretch()
        btn_c = QPushButton("Cancelar"); btn_c.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar"); btn_ok.setDefault(True)
        btn_ok.setStyleSheet(BTN_PRIMARY); btn_ok.clicked.connect(self._guardar)
        btns.addWidget(btn_c); btns.addWidget(btn_ok)
        lay.addLayout(btns)

        if concepto:
            self._cargar()

    def _on_calculo_changed(self):
        es_manual = self.cb_calculo.currentData()
        self.spin_pct.setVisible(not es_manual)
        self._form.labelForField(self.spin_pct).setVisible(not es_manual) if self._form.labelForField(self.spin_pct) else None
        self.spin_monto.setVisible(es_manual)
        self.lbl_monto_hint.setVisible(es_manual)
        lbl_m = self._form.labelForField(self.spin_monto)
        if lbl_m:
            lbl_m.setVisible(es_manual)
        self.adjustSize()

    def _cargar(self):
        c = self.concepto
        self.f_codigo.setText(c.codigo or "")
        self.f_codigo.setEnabled(False)   # no cambiar código al editar
        self.f_nombre.setText(c.nombre or "")
        for i in range(self.cb_tipo.count()):
            if self.cb_tipo.itemData(i) == c.tipo:
                self.cb_tipo.setCurrentIndex(i); break
        es_manual = getattr(c, 'es_manual', False)
        self.cb_calculo.setCurrentIndex(1 if es_manual else 0)
        if es_manual:
            monto = getattr(c, 'monto', None)
            self.spin_monto.setValue(float(monto) if monto else 0.0)
        else:
            self.spin_pct.setValue(float(c.porcentaje) * 100 if c.porcentaje else 0.0)

    def _guardar(self):
        if not self.f_codigo.text().strip() or not self.f_nombre.text().strip():
            QMessageBox.warning(self, "Campos requeridos", "Código y nombre son obligatorios.")
            return
        self.accept()

    def datos(self) -> dict:
        es_manual = self.cb_calculo.currentData()
        pct   = self.spin_pct.value()
        monto = self.spin_monto.value()
        return {
            "codigo":     self.f_codigo.text().strip(),
            "nombre":     self.f_nombre.text().strip(),
            "tipo":       self.cb_tipo.currentData(),
            "es_manual":  es_manual,
            "porcentaje": None if es_manual else (Decimal(str(pct / 100)) if pct > 0 else None),
            "monto":      Decimal(str(monto)) if (es_manual and monto > 0) else None,
        }


class DialogFechaRetiro(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fecha de retiro")
        self.setFixedSize(300, 130)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.de = QDateEdit(QDate.currentDate())
        self.de.setCalendarPopup(True)
        form.addRow("Fecha de retiro:", self.de)
        lay.addLayout(form)
        btns = QHBoxLayout(); btns.addStretch()
        btn_c = QPushButton("Cancelar"); btn_c.clicked.connect(self.reject)
        btn_ok = QPushButton("Confirmar"); btn_ok.setDefault(True)
        btn_ok.setStyleSheet(BTN_PRIMARY); btn_ok.clicked.connect(self.accept)
        btns.addWidget(btn_c); btns.addWidget(btn_ok)
        lay.addLayout(btns)

    def fecha(self) -> date:
        qd = self.de.date()
        return date(qd.year(), qd.month(), qd.day())


# ══════════════════════════════════════════════════════════════
# Widget principal: Módulo Nómina
# ══════════════════════════════════════════════════════════════
class NominaWidget(QWidget):
    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        self.session = SessionLocal()
        self.service = NominaService(self.session, empresa_id)
        # Sembrar conceptos básicos si no existen
        self.service._seed_conceptos_basicos()
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        titulo = QLabel("👷  Nómina")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b; padding:16px 20px 4px 20px;")
        lay.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 20px;font-size:13px;}"
            "QTabBar::tab:selected{font-weight:bold;color:#2563eb;}"
        )

        self.tab_emp  = TabEmpleados(self.service)
        self.tab_con  = TabConceptos(self.service)
        self.tab_liq  = TabLiquidar(self.service)
        self.tab_hist = TabHistorial(self.service)

        self.tabs.addTab(self.tab_emp,  "👤 Empleados")
        self.tabs.addTab(self.tab_con,  "📄 Conceptos")
        self.tabs.addTab(self.tab_liq,  "🧮 Liquidar")
        self.tabs.addTab(self.tab_hist, "📋 Historial")

        lay.addWidget(self.tabs)

    def closeEvent(self, event):
        self.session.close()
        super().closeEvent(event)
