from decimal import Decimal
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QGroupBox,
    QHeaderView, QAbstractItemView, QComboBox, QFrame,
    QTabWidget, QSplitter, QSizePolicy, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from modules.seguridad_social.service import SeguridadSocialService

BTN_PRIMARY = "background:#2563eb;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_SUCCESS = "background:#059669;color:white;padding:5px 14px;border-radius:5px;font-weight:bold;"
BTN_DANGER  = "color:#dc2626;border:1px solid #fca5a5;padding:4px 10px;border-radius:5px;"

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _fmt(v) -> str:
    try:
        return f"${Decimal(str(v)):,.0f}"
    except Exception:
        return "$0"


# ══════════════════════════════════════════════════════════════
# Tab 1 — Generar PILA
# ══════════════════════════════════════════════════════════════
class TabGenerarPILA(QWidget):
    def __init__(self, service: SeguridadSocialService, parent=None):
        super().__init__(parent)
        self.service  = service
        self._filas   = []     # cálculo pendiente de guardar
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Info
        info = QLabel(
            "ℹ️  Selecciona el periodo y presiona <b>Calcular</b> para generar la planilla "
            "de aportes a partir de las liquidaciones de nómina <b>aprobadas</b>. "
            "Luego revisa los valores y presiona <b>Guardar PILA</b>."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#eff6ff;color:#1d4ed8;padding:8px 12px;"
            "border-radius:6px;font-size:12px;"
        )
        lay.addWidget(info)

        # Barra superior
        tb = QHBoxLayout()
        self.cb_periodo = QComboBox(); self.cb_periodo.setFixedWidth(220)
        self._llenar_periodos()

        btn_calc = QPushButton("🧮 Calcular")
        btn_calc.setStyleSheet(BTN_PRIMARY)
        btn_calc.clicked.connect(self._calcular)

        self.btn_guardar = QPushButton("💾 Guardar PILA")
        self.btn_guardar.setStyleSheet(BTN_SUCCESS)
        self.btn_guardar.setEnabled(False)
        self.btn_guardar.clicked.connect(self._guardar)

        self.btn_eliminar = QPushButton("🗑 Eliminar planilla")
        self.btn_eliminar.setStyleSheet(BTN_DANGER)
        self.btn_eliminar.clicked.connect(self._eliminar)

        self.btn_exportar = QPushButton("📥 Exportar CSV")
        self.btn_exportar.setEnabled(False)
        self.btn_exportar.clicked.connect(self._exportar_csv)

        tb.addWidget(QLabel("Periodo:")); tb.addWidget(self.cb_periodo)
        tb.addWidget(btn_calc); tb.addWidget(self.btn_guardar)
        tb.addWidget(self.btn_eliminar); tb.addStretch()
        tb.addWidget(self.btn_exportar)
        lay.addLayout(tb)

        # Resumen
        self.grp_resumen = QGroupBox("Resumen del periodo")
        self.grp_resumen.setStyleSheet("QGroupBox{font-weight:bold;}")
        self.grp_resumen.setVisible(False)
        rl = QHBoxLayout(self.grp_resumen)
        self._lbls_res = {}
        for key, label in [
            ("n_empleados",    "Empleados"),
            ("total_ibc",      "Total IBC"),
            ("total_empleado", "Aporte empleado"),
            ("total_empleador","Aporte empleador"),
            ("total_pila",     "TOTAL PILA"),
        ]:
            col = QVBoxLayout()
            lbl_k = QLabel(label)
            lbl_k.setStyleSheet("color:#64748b;font-size:11px;")
            lbl_v = QLabel("—")
            lbl_v.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl_k, alignment=Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl_v, alignment=Qt.AlignmentFlag.AlignCenter)
            self._lbls_res[key] = lbl_v
            rl.addLayout(col)
            if key != "total_pila":
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
                sep.setStyleSheet("color:#e2e8f0;"); rl.addWidget(sep)
        lay.addWidget(self.grp_resumen)

        # Tabla de detalle por empleado
        self.tabla = QTableWidget(0, 13)
        self.tabla.setHorizontalHeaderLabels([
            "Empleado", "Documento", "EPS", "Fondo Pens.", "ARL", "Caja",
            "IBC", "Salud Emp.", "Pensión Emp.", "Salud Emp.*", "Pensión Emp.*",
            "ARL", "ICBF+SENA+Caja"
        ])
        # Nota: "Emp." = empleado, "Emp.*" = empleador
        hh = self.tabla.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 13):
            self.tabla.setColumnWidth(col, 90)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Segoe UI", 10))
        lay.addWidget(self.tabla)

        nota_cols = QLabel(
            "* Columnas marcadas con asterisco son aportes a cargo del empleador."
        )
        nota_cols.setStyleSheet("color:#94a3b8;font-size:11px;")
        lay.addWidget(nota_cols)

    def _llenar_periodos(self):
        self.cb_periodo.clear()
        self.cb_periodo.addItem("— Seleccionar periodo —", None)
        for p in self.service.listar_periodos():
            label = f"{MESES[p.mes]} {p.anio}"
            self.cb_periodo.addItem(label, p.id)

    def showEvent(self, event):
        super().showEvent(event)
        self.service.db.expire_all()
        self._llenar_periodos()

    def _calcular(self):
        pid = self.cb_periodo.currentData()
        if not pid:
            QMessageBox.warning(self, "Sin periodo", "Selecciona un periodo.")
            return

        # Si ya hay planilla guardada, mostrarla en lugar de recalcular
        if self.service.existe_planilla(pid):
            self._cargar_planilla_existente(pid)
            return

        try:
            self._filas = self.service.calcular_pila(pid)
        except ValueError as e:
            QMessageBox.warning(self, "Sin datos", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._renderizar(self._filas, guardada=False)

    def _cargar_planilla_existente(self, pid: int):
        """Muestra una planilla ya guardada en BD."""
        aportes = self.service.listar_aportes(pid)
        filas = []
        for a in aportes:
            emp  = a.empleado
            t    = emp.tercero if emp else None
            filas.append({
                "nombre":            t.nombre if t else f"Emp {a.empleado_id}",
                "documento":         t.numero_documento if t else "",
                "eps":               emp.eps or "—" if emp else "—",
                "fondo_pension":     emp.fondo_pension or "—" if emp else "—",
                "arl":               emp.arl or "—" if emp else "—",
                "caja_compensacion": emp.caja_compensacion or "—" if emp else "—",
                "ibc":               Decimal(str(a.ibc or 0)),
                "salud_empleado":    Decimal(str(a.salud_empleado or 0)),
                "pension_empleado":  Decimal(str(a.pension_empleado or 0)),
                "salud_empleador":   Decimal(str(a.salud_empleador or 0)),
                "pension_empleador": Decimal(str(a.pension_empleador or 0)),
                "arl_valor":         Decimal(str(a.arl or 0)),
                "icbf":              Decimal(str(a.icbf or 0)),
                "sena":              Decimal(str(a.sena or 0)),
                "caja":              Decimal(str(a.caja_compensacion or 0)),
                "total_empleado":    Decimal(str(a.salud_empleado or 0)) + Decimal(str(a.pension_empleado or 0)),
                "total_empleador":   sum(Decimal(str(getattr(a, c) or 0)) for c in
                                         ["salud_empleador","pension_empleador","arl","icbf","sena","caja_compensacion"]),
            })
        for r in filas:
            r["total_pila"] = r["total_empleado"] + r["total_empleador"]

        self._filas = filas
        self._renderizar(filas, guardada=True)
        QMessageBox.information(
            self, "Planilla existente",
            f"Este periodo ya tiene planilla guardada ({len(filas)} empleados).\n"
            f"Si deseas regenerarla, usa 'Eliminar planilla'."
        )

    def _renderizar(self, filas: list, guardada: bool):
        self.tabla.blockSignals(True)
        self.tabla.setRowCount(0)

        total_emp_sum  = Decimal("0")
        total_empr_sum = Decimal("0")
        total_ibc_sum  = Decimal("0")

        for f in filas:
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            parafiscales = f["icbf"] + f["sena"] + f["caja"]

            values = [
                f["nombre"], f["documento"], f["eps"],
                f["fondo_pension"], f["arl"], f["caja_compensacion"],
                _fmt(f["ibc"]),
                _fmt(f["salud_empleado"]), _fmt(f["pension_empleado"]),
                _fmt(f["salud_empleador"]), _fmt(f["pension_empleador"]),
                _fmt(f["arl_valor"]),       _fmt(parafiscales),
            ]
            right_cols = set(range(6, 13))
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col in right_cols:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabla.setItem(r, col, item)

            # Colorear columnas empleado vs empleador
            for col in range(7, 9):   # empleado
                it = self.tabla.item(r, col)
                if it: it.setForeground(QColor("#1d4ed8"))
            for col in range(9, 13):  # empleador
                it = self.tabla.item(r, col)
                if it: it.setForeground(QColor("#6d28d9"))

            total_emp_sum  += f["total_empleado"]
            total_empr_sum += f["total_empleador"]
            total_ibc_sum  += f["ibc"]

        self.tabla.blockSignals(False)

        # Resumen
        total_pila = total_emp_sum + total_empr_sum
        self._lbls_res["n_empleados"].setText(str(len(filas)))
        self._lbls_res["total_ibc"].setText(_fmt(total_ibc_sum))
        self._lbls_res["total_empleado"].setText(_fmt(total_emp_sum))
        self._lbls_res["total_empleador"].setText(_fmt(total_empr_sum))
        self._lbls_res["total_pila"].setText(_fmt(total_pila))
        self._lbls_res["total_pila"].setStyleSheet(
            "color:#1d4ed8;font-size:16px;font-weight:bold;")
        self.grp_resumen.setVisible(True)

        self.btn_guardar.setEnabled(not guardada)
        self.btn_exportar.setEnabled(True)

    def _guardar(self):
        pid = self.cb_periodo.currentData()
        if not pid or not self._filas:
            return
        try:
            guardados = self.service.guardar_pila(pid, self._filas)
            QMessageBox.information(
                self, "PILA guardada",
                f"✅ Planilla de {len(guardados)} empleados guardada correctamente."
            )
            self.btn_guardar.setEnabled(False)
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _eliminar(self):
        pid = self.cb_periodo.currentData()
        if not pid:
            QMessageBox.warning(self, "Sin periodo", "Selecciona un periodo.")
            return
        if not self.service.existe_planilla(pid):
            QMessageBox.information(self, "Sin planilla",
                                    "No hay planilla guardada para este periodo.")
            return
        resp = QMessageBox.question(
            self, "Eliminar planilla",
            "¿Eliminar la planilla de este periodo?\n"
            "Podrás regenerarla desde las liquidaciones.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            n = self.service.eliminar_planilla(pid)
            QMessageBox.information(self, "Eliminada",
                                    f"✅ {n} registros eliminados.")
            self.tabla.setRowCount(0)
            self.grp_resumen.setVisible(False)
            self._filas = []
            self.btn_guardar.setEnabled(False)
            self.btn_exportar.setEnabled(False)

    def _exportar_csv(self):
        if not self._filas:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar PILA", "pila_aportes.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            cols = [
                "nombre", "documento", "eps", "fondo_pension", "arl",
                "caja_compensacion", "ibc",
                "salud_empleado", "pension_empleado",
                "salud_empleador", "pension_empleador",
                "arl_valor", "icbf", "sena", "caja",
                "total_empleado", "total_empleador", "total_pila",
            ]
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self._filas)
            QMessageBox.information(self, "Exportado",
                                    f"✅ Archivo exportado:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error al exportar", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 2 — Historial de PILA
# ══════════════════════════════════════════════════════════════
class TabHistorialPILA(QWidget):
    def __init__(self, service: SeguridadSocialService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        tb = QHBoxLayout()
        self.cb_periodo = QComboBox(); self.cb_periodo.setFixedWidth(220)
        self.cb_periodo.addItem("Todos los periodos", None)
        for p in self.service.listar_periodos():
            if self.service.existe_planilla(p.id):
                label = f"{MESES[p.mes]} {p.anio}"
                self.cb_periodo.addItem(label, p.id)
        self.cb_periodo.currentIndexChanged.connect(self._cargar)
        btn_ref = QPushButton("🔄"); btn_ref.setFixedWidth(36)
        btn_ref.clicked.connect(self._cargar)
        tb.addWidget(QLabel("Periodo:")); tb.addWidget(self.cb_periodo)
        tb.addWidget(btn_ref); tb.addStretch()
        lay.addLayout(tb)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Tabla resumen por periodo
        self.tbl_periodos = QTableWidget(0, 7)
        self.tbl_periodos.setHorizontalHeaderLabels([
            "Periodo", "Empleados", "Total IBC",
            "Aporte Empleado", "Aporte Empleador", "TOTAL PILA", "Estado"
        ])
        hh = self.tbl_periodos.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            self.tbl_periodos.setColumnWidth(col, 120)
        self.tbl_periodos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_periodos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_periodos.verticalHeader().setVisible(False)
        self.tbl_periodos.setAlternatingRowColors(False)
        self.tbl_periodos.itemSelectionChanged.connect(self._on_periodo_sel)
        splitter.addWidget(self.tbl_periodos)

        # Detalle por empleado
        grp = QGroupBox("Detalle del periodo seleccionado")
        grp.setStyleSheet("QGroupBox{font-weight:bold;}")
        gl = QVBoxLayout(grp)
        self.tbl_detalle = QTableWidget(0, 9)
        self.tbl_detalle.setHorizontalHeaderLabels([
            "Empleado", "IBC",
            "Salud Emp.", "Pensión Emp.",
            "Salud Emp.*", "Pensión Emp.*", "ARL", "Parafiscales",
            "TOTAL"
        ])
        hd = self.tbl_detalle.horizontalHeader()
        hd.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 9):
            self.tbl_detalle.setColumnWidth(col, 105)
        self.tbl_detalle.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_detalle.verticalHeader().setVisible(False)
        self.tbl_detalle.setAlternatingRowColors(False)
        gl.addWidget(self.tbl_detalle)
        splitter.addWidget(grp)
        splitter.setSizes([220, 280])
        lay.addWidget(splitter)

    def _cargar(self):
        self.service.db.expire_all()
        pid = self.cb_periodo.currentData()
        self.tbl_periodos.setRowCount(0)
        self.tbl_detalle.setRowCount(0)

        # Obtener periodos con planilla
        periodos = self.service.listar_periodos()
        for p in periodos:
            if pid and p.id != pid:
                continue
            if not self.service.existe_planilla(p.id):
                continue
            res = self.service.resumen_periodo(p.id)
            r   = self.tbl_periodos.rowCount()
            self.tbl_periodos.insertRow(r)
            label = f"{MESES[p.mes]} {p.anio}"
            lbl_item = QTableWidgetItem(label)
            lbl_item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.tbl_periodos.setItem(r, 0, lbl_item)
            self.tbl_periodos.setItem(r, 1, QTableWidgetItem(str(res.get("n_empleados", 0))))

            total_emp  = res.get("total_empleado", 0)
            total_empr = res.get("total_empleador", 0)
            total_pila = total_emp + total_empr if isinstance(total_emp, Decimal) \
                         else Decimal(str(total_emp)) + Decimal(str(total_empr))

            for col, val in [
                (2, res.get("total_ibc", 0)),
                (3, total_emp),
                (4, total_empr),
                (5, total_pila),
            ]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col == 5:
                    it.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                    it.setForeground(QColor("#1d4ed8"))
                self.tbl_periodos.setItem(r, col, it)

            est_item = QTableWidgetItem("✅ Generada")
            est_item.setForeground(QColor("#15803d"))
            self.tbl_periodos.setItem(r, 6, est_item)

    def _on_periodo_sel(self):
        fila = self.tbl_periodos.currentRow()
        if fila < 0:
            return
        pid = self.tbl_periodos.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        aportes = self.service.listar_aportes(pid)
        self.tbl_detalle.setRowCount(0)
        for a in aportes:
            r   = self.tbl_detalle.rowCount()
            self.tbl_detalle.insertRow(r)
            emp = a.empleado
            nombre = emp.tercero.nombre if (emp and emp.tercero) else f"Emp {a.empleado_id}"
            self.tbl_detalle.setItem(r, 0, QTableWidgetItem(nombre))

            parafiscales = (
                Decimal(str(a.icbf or 0)) +
                Decimal(str(a.sena or 0)) +
                Decimal(str(a.caja_compensacion or 0))
            )
            total = (
                Decimal(str(a.salud_empleado or 0)) +
                Decimal(str(a.pension_empleado or 0)) +
                Decimal(str(a.salud_empleador or 0)) +
                Decimal(str(a.pension_empleador or 0)) +
                Decimal(str(a.arl or 0)) + parafiscales
            )
            for col, val in [
                (1, a.ibc),
                (2, a.salud_empleado), (3, a.pension_empleado),
                (4, a.salud_empleador), (5, a.pension_empleador),
                (6, a.arl), (7, parafiscales), (8, total),
            ]:
                it = QTableWidgetItem(_fmt(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col in (2, 3):
                    it.setForeground(QColor("#1d4ed8"))
                elif col in (4, 5, 6, 7):
                    it.setForeground(QColor("#6d28d9"))
                elif col == 8:
                    it.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                self.tbl_detalle.setItem(r, col, it)

    def showEvent(self, event):
        super().showEvent(event)
        self._cargar()


# ══════════════════════════════════════════════════════════════
# Tab 3 — Tarifas y referencia legal
# ══════════════════════════════════════════════════════════════
class TabTarifas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        from PyQt6.QtWidgets import QTextBrowser
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)

        browser = QTextBrowser()
        browser.setStyleSheet(
            "background:white;border:1px solid #e2e8f0;"
            "border-radius:6px;font-size:13px;padding:12px;"
        )
        browser.setHtml("""
<h2 style='color:#1e293b;'>Tarifas Seguridad Social Colombia 2024</h2>

<h3 style='color:#1d4ed8;'>Salud</h3>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;'>
<tr style='background:#dbeafe;'><th>Concepto</th><th>Empleado</th><th>Empleador</th><th>Total</th></tr>
<tr><td>Salud</td><td>4.0%</td><td>8.5%</td><td>12.5%</td></tr>
</table>

<h3 style='color:#6d28d9;'>Pensión</h3>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;'>
<tr style='background:#ede9fe;'><th>Concepto</th><th>Empleado</th><th>Empleador</th><th>Total</th></tr>
<tr><td>Pensión</td><td>4.0%</td><td>12.0%</td><td>16.0%</td></tr>
<tr><td>Fondo Solidaridad Pensional (salario &gt; 4 SMMLV)</td><td>1.0%</td><td>—</td><td>1.0%</td></tr>
<tr><td>Subsistencia (salario &gt; 16 SMMLV)</td><td>+1.0%</td><td>—</td><td>+1.0%</td></tr>
</table>

<h3 style='color:#b45309;'>ARL — Riesgos Laborales (solo empleador)</h3>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;'>
<tr style='background:#fef3c7;'><th>Nivel de Riesgo</th><th>Tarifa</th><th>Actividades típicas</th></tr>
<tr><td>I</td><td>0.522%</td><td>Oficinas, financiero, seguros</td></tr>
<tr><td>II</td><td>1.044%</td><td>Procesos industriales livianos</td></tr>
<tr><td>III</td><td>2.436%</td><td>Industrias medianas</td></tr>
<tr><td>IV</td><td>4.350%</td><td>Minería, pesca, construcción</td></tr>
<tr><td>V</td><td>6.960%</td><td>Explosivos, manejo de amianto</td></tr>
</table>

<h3 style='color:#15803d;'>Parafiscales (solo empleador)</h3>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;'>
<tr style='background:#dcfce7;'><th>Concepto</th><th>Tarifa</th><th>Entidad</th></tr>
<tr><td>Caja de Compensación Familiar</td><td>4.0%</td><td>Cafam, Compensar, etc.</td></tr>
<tr><td>SENA</td><td>2.0%</td><td>Servicio Nacional de Aprendizaje</td></tr>
<tr><td>ICBF</td><td>3.0%</td><td>Instituto Colombiano de Bienestar Familiar</td></tr>
</table>
<p style='color:#64748b;font-size:11px;'>
⚠️ Empresas que tributan por el CREE (Ley 1607/2012) están exentas de SENA e ICBF cuando
el salario del trabajador no supera 10 SMMLV.
</p>

<h3 style='color:#1e293b;'>Valores de referencia 2024</h3>
<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;'>
<tr style='background:#f1f5f9;'><th>Concepto</th><th>Valor</th></tr>
<tr><td>Salario Mínimo Mensual Legal Vigente (SMMLV)</td><td>$1.300.000</td></tr>
<tr><td>Auxilio de Transporte</td><td>$162.000</td></tr>
<tr><td>Unidad de Valor Tributario (UVT)</td><td>$47.065</td></tr>
</table>
        """)
        lay.addWidget(browser)


# ══════════════════════════════════════════════════════════════
# Widget principal: Seguridad Social
# ══════════════════════════════════════════════════════════════
class SeguridadSocialWidget(QWidget):
    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        self.session = SessionLocal()
        self.service = SeguridadSocialService(self.session, empresa_id)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)

        titulo = QLabel("🛡️  Seguridad Social — PILA")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b; padding:16px 20px 4px 20px;")
        lay.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:8px 20px;font-size:13px;}"
            "QTabBar::tab:selected{font-weight:bold;color:#2563eb;}"
        )

        self.tab_generar  = TabGenerarPILA(self.service)
        self.tab_historial = TabHistorialPILA(self.service)
        self.tab_tarifas  = TabTarifas()

        self.tabs.addTab(self.tab_generar,   "📋 Generar PILA")
        self.tabs.addTab(self.tab_historial, "📂 Historial")
        self.tabs.addTab(self.tab_tarifas,   "📖 Tarifas legales")

        self.tabs.currentChanged.connect(self._on_tab)
        lay.addWidget(self.tabs)

    def _on_tab(self, _):
        self.session.expire_all()

    def closeEvent(self, event):
        self.session.close(); super().closeEvent(event)
