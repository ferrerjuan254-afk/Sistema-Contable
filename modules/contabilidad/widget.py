from decimal import Decimal, InvalidOperation
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog,
    QLineEdit, QMessageBox, QGroupBox, QHeaderView,
    QAbstractItemView, QTabWidget, QComboBox, QDateEdit,
    QFrame, QSplitter, QSpinBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.database import SessionLocal
from core.models.contabilidad import EstadoPeriodo, EstadoAsiento
from modules.contabilidad.service import ContabilidadService

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

COLOR_CLASE = {
    "1": "#dbeafe", "2": "#fee2e2", "3": "#dcfce7",
    "4": "#d1fae5", "5": "#fef9c3", "6": "#ffe4e6",
    "7": "#f3e8ff", "8": "#e0f2fe", "9": "#fce7f3",
}


# ══════════════════════════════════════════════════════════════
# Tab 1: Plan de Cuentas
# ══════════════════════════════════════════════════════════════
class TabPUC(QWidget):
    def __init__(self, service: ContabilidadService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tb = QHBoxLayout()
        self.f_buscar = QLineEdit()
        self.f_buscar.setPlaceholderText("🔍  Buscar por código o nombre...")
        self.f_buscar.setFixedHeight(32)
        self.f_buscar.textChanged.connect(self._filtrar)

        self.lbl_total = QLabel()
        self.lbl_total.setStyleSheet("color:#64748b; font-size:12px;")

        tb.addWidget(self.f_buscar, stretch=1)
        tb.addWidget(self.lbl_total)
        layout.addLayout(tb)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Código", "Nombre", "Tipo", "Naturaleza", "Mov."])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 110)
        self.tabla.setColumnWidth(2, 120)
        self.tabla.setColumnWidth(3, 100)
        self.tabla.setColumnWidth(4, 50)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(False)
        self.tabla.setFont(QFont("Consolas", 10))
        layout.addWidget(self.tabla)

    def _cargar(self):
        self._cuentas = self.service.listar_puc()
        self._renderizar(self._cuentas)

    def _renderizar(self, cuentas):
        self.tabla.setRowCount(0)
        for c in cuentas:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)

            indent = "    " * (c.nivel - 1)
            nombre_item = QTableWidgetItem(f"{indent}{c.nombre}")
            codigo_item = QTableWidgetItem(c.codigo)
            tipo_item   = QTableWidgetItem(c.tipo.value.capitalize() if hasattr(c.tipo, 'value') else str(c.tipo).capitalize())
            
            nat_val = c.naturaleza.value if hasattr(c.naturaleza, 'value') else str(c.naturaleza)
            nat_item    = QTableWidgetItem("Débito" if nat_val == "debito" else "Crédito")
            
            mov_item    = QTableWidgetItem("✔" if c.acepta_mov else "")
            mov_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            clase = c.codigo[0] if c.codigo else "1"
            bg = QColor(COLOR_CLASE.get(clase, "#f8fafc"))

            if c.nivel <= 2:
                font = QFont("Consolas", 10, QFont.Weight.Bold)
                for item in [codigo_item, nombre_item, tipo_item, nat_item]:
                    item.setFont(font)

            for col, item in enumerate([codigo_item, nombre_item, tipo_item, nat_item, mov_item]):
                if c.nivel <= 2:
                    item.setBackground(bg)
                item.setData(Qt.ItemDataRole.UserRole, c.id)
                self.tabla.setItem(r, col, item)

        self.lbl_total.setText(f"{len(cuentas)} cuentas")

    def _filtrar(self, texto: str):
        if not texto.strip():
            self._renderizar(self._cuentas)
            return
        t = texto.lower()
        filtradas = [
            c for c in self._cuentas
            if t in c.codigo.lower() or t in c.nombre.lower()
        ]
        self._renderizar(filtradas)

    def refresh(self):
        self._cargar()


# ══════════════════════════════════════════════════════════════
# Tab 2: Periodos Contables
# ══════════════════════════════════════════════════════════════
class TabPeriodos(QWidget):
    periodo_seleccionado = pyqtSignal(int)

    def __init__(self, service: ContabilidadService, parent=None):
        super().__init__(parent)
        self.service = service
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        grp = QGroupBox("Crear nuevo periodo")
        grp.setStyleSheet("QGroupBox { font-weight:bold; }")
        glay = QHBoxLayout(grp)

        self.spin_anio = QSpinBox()
        self.spin_anio.setRange(2000, 2100)
        self.spin_anio.setValue(date.today().year)
        self.spin_anio.setFixedWidth(90)

        self.combo_mes = QComboBox()
        for i, m in enumerate(MESES[1:], 1):
            self.combo_mes.addItem(m, i)
        self.combo_mes.setCurrentIndex(date.today().month - 1)
        self.combo_mes.setFixedWidth(130)

        btn_crear = QPushButton("+ Crear periodo")
        btn_crear.setStyleSheet(
            "background:#2563eb; color:white; padding:5px 16px; "
            "border-radius:5px; font-weight:bold;"
        )
        btn_crear.clicked.connect(self._crear_periodo)

        glay.addWidget(QLabel("Año:"))
        glay.addWidget(self.spin_anio)
        glay.addWidget(QLabel("Mes:"))
        glay.addWidget(self.combo_mes)
        glay.addWidget(btn_crear)
        glay.addStretch()
        layout.addWidget(grp)

        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Año", "Mes", "Estado", "Acciones"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setColumnWidth(0, 70)
        self.tabla.setColumnWidth(2, 110)
        self.tabla.setColumnWidth(3, 140)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        layout.addWidget(self.tabla)

    def _cargar(self):
        self.tabla.setRowCount(0)
        periodos = self.service.listar_periodos()
        for p in periodos:
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)
            
            anio_item = QTableWidgetItem(str(p.anio))
            anio_item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.tabla.setItem(r, 0, anio_item)
            self.tabla.setItem(r, 1, QTableWidgetItem(MESES[p.mes]))
            
            estado_item = QTableWidgetItem(
                "🟢 Abierto" if p.estado == EstadoPeriodo.ABIERTO else "🔒 Cerrado"
            )
            if p.estado == EstadoPeriodo.CERRADO:
                estado_item.setForeground(QColor("#dc2626"))
            else:
                estado_item.setForeground(QColor("#16a34a"))
            self.tabla.setItem(r, 2, estado_item)

            if p.estado == EstadoPeriodo.ABIERTO:
                btn = QPushButton("🔒 Cerrar periodo")
                btn.setStyleSheet("color:#dc2626; font-size:11px;")
                btn.clicked.connect(lambda _, pid=p.id: self._cerrar_periodo(pid))
                self.tabla.setCellWidget(r, 3, btn)
            else:
                self.tabla.setItem(r, 3, QTableWidgetItem(""))

    def _crear_periodo(self):
        anio = self.spin_anio.value()
        mes  = self.combo_mes.currentData()
        try:
            self.service.crear_periodo(anio, mes)
            self._cargar()
        except ValueError as e:
            QMessageBox.warning(self, "Aviso", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _cerrar_periodo(self, periodo_id: int):
        resp = QMessageBox.question(
            self, "Cerrar periodo",
            "¿Cerrar este periodo?\nNo podrás registrar asientos en él.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                self.service.cerrar_periodo(periodo_id)
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._cargar()

    def periodo_id_activo(self):
        periodos = self.service.listar_periodos()
        for p in periodos:
            if p.estado == EstadoPeriodo.ABIERTO:
                return p.id
        return None


# ══════════════════════════════════════════════════════════════
# Diálogo: Nuevo Asiento
# ══════════════════════════════════════════════════════════════
class DialogNuevoAsiento(QDialog):
    def __init__(self, service: ContabilidadService, periodo_id: int, parent=None):
        super().__init__(parent)
        self.service    = service
        self.periodo_id = periodo_id
        self.setWindowTitle("Nuevo asiento contable")
        self.setMinimumSize(900, 600)
        self._build_ui()
        self._agregar_fila()
        self._agregar_fila()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        titulo = QLabel("📝 Nuevo Asiento Contable")
        titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b;")
        layout.addWidget(titulo)

        cab = QHBoxLayout()
        self.f_fecha = QDateEdit(QDate.currentDate())
        self.f_fecha.setCalendarPopup(True)
        self.f_fecha.setFixedWidth(130)
        self.f_desc = QLineEdit()
        self.f_desc.setPlaceholderText("Descripción del asiento...")

        cab.addWidget(QLabel("Fecha:"))
        cab.addWidget(self.f_fecha)
        cab.addWidget(QLabel("Descripción:"), 0)
        cab.addWidget(self.f_desc, 1)
        layout.addLayout(cab)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        layout.addWidget(sep)

        lbl_mov = QLabel("Movimientos")
        lbl_mov.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_mov)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(
            ["Código cuenta", "Nombre cuenta", "Descripción línea", "Débito", "Crédito"]
        )
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.setColumnWidth(0, 130)
        self.tbl.setColumnWidth(2, 200)
        self.tbl.setColumnWidth(3, 120)
        self.tbl.setColumnWidth(4, 120)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.tbl)

        tb_mov = QHBoxLayout()
        btn_add = QPushButton("+ Agregar fila")
        btn_add.clicked.connect(self._agregar_fila)
        btn_del = QPushButton("🗑 Eliminar fila")
        btn_del.clicked.connect(self._eliminar_fila)
        btn_del.setStyleSheet("color:#dc2626;")
        tb_mov.addWidget(btn_add)
        tb_mov.addWidget(btn_del)
        tb_mov.addStretch()
        layout.addLayout(tb_mov)

        tots = QHBoxLayout()
        tots.addStretch()
        self.lbl_total_db = QLabel("Débitos: $0.00")
        self.lbl_total_db.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_total_db.setStyleSheet("color:#1d4ed8;")
        self.lbl_total_cr = QLabel("Créditos: $0.00")
        self.lbl_total_cr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_total_cr.setStyleSheet("color:#16a34a;")
        self.lbl_diff = QLabel("")
        self.lbl_diff.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        tots.addWidget(self.lbl_total_db)
        tots.addWidget(QLabel("  |  "))
        tots.addWidget(self.lbl_total_cr)
        tots.addWidget(QLabel("  "))
        tots.addWidget(self.lbl_diff)
        layout.addLayout(tots)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#e2e8f0;")
        layout.addWidget(sep2)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        self.btn_guardar = QPushButton("💾 Guardar asiento")
        self.btn_guardar.setFixedWidth(160)
        self.btn_guardar.setStyleSheet(
            "background:#2563eb; color:white; padding:6px 20px; "
            "border-radius:6px; font-weight:bold;"
        )
        self.btn_guardar.clicked.connect(self._guardar)
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_guardar)
        layout.addLayout(btns)

        self.tbl.cellChanged.connect(self._on_cell_changed)

    def _agregar_fila(self):
        self.tbl.blockSignals(True)
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)

        codigo_edit = QLineEdit()
        codigo_edit.setPlaceholderText("Código o búsqueda")
        codigo_edit.editingFinished.connect(
            lambda le=codigo_edit: self._buscar_cuenta_por_codigo(le)
        )
        self.tbl.setCellWidget(r, 0, codigo_edit)

        nombre_item = QTableWidgetItem("")
        nombre_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        nombre_item.setForeground(QColor("#64748b"))
        self.tbl.setItem(r, 1, nombre_item)

        self.tbl.setItem(r, 2, QTableWidgetItem(""))

        db_item = QTableWidgetItem("0.00")
        db_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tbl.setItem(r, 3, db_item)

        cr_item = QTableWidgetItem("0.00")
        cr_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tbl.setItem(r, 4, cr_item)

        self.tbl.setRowHeight(r, 34)
        self.tbl.blockSignals(False)

    def _eliminar_fila(self):
        fila = self.tbl.currentRow()
        if fila >= 0 and self.tbl.rowCount() > 1:
            self.tbl.removeRow(fila)
            self._actualizar_totales()

    def _buscar_cuenta_por_codigo(self, le: QLineEdit):
        texto = le.text().strip()
        if not texto:
            return
        cuentas = self.service.buscar_cuentas(texto)
        if not cuentas:
            le.setStyleSheet("border: 1px solid #dc2626;")
            return

        cuenta = next((c for c in cuentas if c.codigo == texto), cuentas[0])
        le.setText(cuenta.codigo)
        le.setStyleSheet("")
        le.setProperty("cuenta_id", cuenta.id)

        for r in range(self.tbl.rowCount()):
            if self.tbl.cellWidget(r, 0) is le:
                nombre_item = self.tbl.item(r, 1)
                if nombre_item:
                    nombre_item.setText(cuenta.nombre)
                break

    def _on_cell_changed(self, row, col):
        if col in (3, 4):
            self._actualizar_totales()

    def _actualizar_totales(self):
        self.tbl.blockSignals(True)  # Evitar recursividad
        total_db = Decimal("0")
        total_cr = Decimal("0")
        for r in range(self.tbl.rowCount()):
            try:
                db_item = self.tbl.item(r, 3)
                cr_item = self.tbl.item(r, 4)
                if db_item:
                    total_db += Decimal(db_item.text().replace(",", ".") or "0")
                if cr_item:
                    total_cr += Decimal(cr_item.text().replace(",", ".") or "0")
            except InvalidOperation:
                pass

        self.lbl_total_db.setText(f"Débitos: ${total_db:,.2f}")
        self.lbl_total_cr.setText(f"Créditos: ${total_cr:,.2f}")

        diff = total_db - total_cr
        if diff == 0 and total_db > 0:
            self.lbl_diff.setText("✅ Cuadra")
            self.lbl_diff.setStyleSheet("color:#16a34a; font-weight:bold;")
        elif diff != 0:
            self.lbl_diff.setText(f"⚠ Diferencia: ${abs(diff):,.2f}")
            self.lbl_diff.setStyleSheet("color:#dc2626; font-weight:bold;")
        else:
            self.lbl_diff.setText("")
        self.tbl.blockSignals(False)

    def _guardar(self):
        if not self.f_desc.text().strip():
            QMessageBox.warning(self, "Falta descripción", "Ingresa una descripción para el asiento.")
            return

        lineas = []
        for r in range(self.tbl.rowCount()):
            le = self.tbl.cellWidget(r, 0)
            cuenta_id = le.property("cuenta_id") if le else None
            if not cuenta_id:
                continue
            try:
                db_text = self.tbl.item(r, 3).text().replace(",", ".") if self.tbl.item(r, 3) else "0"
                cr_text = self.tbl.item(r, 4).text().replace(",", ".") if self.tbl.item(r, 4) else "0"
                debito  = Decimal(db_text or "0")
                credito = Decimal(cr_text or "0")
            except InvalidOperation:
                QMessageBox.warning(self, "Valor inválido", f"Fila {r+1}: valor numérico inválido.")
                return
            
            desc_item = self.tbl.item(r, 2)
            lineas.append({
                "cuenta_id":   cuenta_id,
                "debito":      debito,
                "credito":     credito,
                "descripcion": desc_item.text() if desc_item else "",
            })

        if not lineas:
            QMessageBox.warning(self, "Sin movimientos", "Agrega al menos una línea con cuenta válida.")
            return

        qdate = self.f_fecha.date()
        fecha = date(qdate.year(), qdate.month(), qdate.day())

        try:
            asiento = self.service.crear_asiento(
                periodo_id  = self.periodo_id,
                fecha       = fecha,
                descripcion = self.f_desc.text().strip(),
                lineas      = lineas,
            )
            QMessageBox.information(
                self, "Asiento guardado",
                f"✅ Asiento {asiento.numero} registrado correctamente."
            )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Error de validación", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ══════════════════════════════════════════════════════════════
# Tab 3: Libro Diario / Asientos
# ══════════════════════════════════════════════════════════════
class TabAsientos(QWidget):
    def __init__(self, service: ContabilidadService, get_periodo_fn, parent=None):
        super().__init__(parent)
        self.service       = service
        self.get_periodo   = get_periodo_fn
        self._build_ui()
        self._cargar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tb = QHBoxLayout()
        self.combo_periodo = QComboBox()
        self.combo_periodo.setFixedWidth(200)
        self.combo_periodo.currentIndexChanged.connect(self._cargar)
        self._llenar_periodos()

        btn_nuevo = QPushButton("+ Nuevo asiento")
        btn_nuevo.setStyleSheet(
            "background:#2563eb; color:white; padding:5px 16px; "
            "border-radius:5px; font-weight:bold;"
        )
        btn_nuevo.clicked.connect(self._nuevo_asiento)

        btn_anular = QPushButton("🚫 Anular")
        btn_anular.setStyleSheet("color:#dc2626;")
        btn_anular.clicked.connect(self._anular_asiento)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(36)
        btn_refresh.clicked.connect(self._cargar)

        tb.addWidget(QLabel("Periodo:"))
        tb.addWidget(self.combo_periodo)
        tb.addWidget(btn_nuevo)
        tb.addWidget(btn_anular)
        tb.addStretch()
        tb.addWidget(btn_refresh)
        layout.addLayout(tb)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.tbl_asientos = QTableWidget(0, 5)
        self.tbl_asientos.setHorizontalHeaderLabels(
            ["Número", "Fecha", "Descripción", "Estado", "Total"]
        )
        self.tbl_asientos.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_asientos.setColumnWidth(0, 90)
        self.tbl_asientos.setColumnWidth(1, 100)
        self.tbl_asientos.setColumnWidth(3, 100)
        self.tbl_asientos.setColumnWidth(4, 110)
        self.tbl_asientos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_asientos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_asientos.verticalHeader().setVisible(False)
        self.tbl_asientos.setAlternatingRowColors(True)
        self.tbl_asientos.itemSelectionChanged.connect(self._on_asiento_sel)
        splitter.addWidget(self.tbl_asientos)

        grp = QGroupBox("Movimientos del asiento seleccionado")
        grp.setStyleSheet("QGroupBox { font-weight:bold; }")
        glay = QVBoxLayout(grp)
        self.tbl_movs = QTableWidget(0, 4)
        self.tbl_movs.setHorizontalHeaderLabels(["Cuenta", "Nombre cuenta", "Débito", "Crédito"])
        self.tbl_movs.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_movs.setColumnWidth(0, 110)
        self.tbl_movs.setColumnWidth(2, 120)
        self.tbl_movs.setColumnWidth(3, 120)
        self.tbl_movs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_movs.verticalHeader().setVisible(False)
        self.tbl_movs.setAlternatingRowColors(True)
        glay.addWidget(self.tbl_movs)
        splitter.addWidget(grp)

        splitter.setSizes([320, 200])
        layout.addWidget(splitter)

    def _llenar_periodos(self):
        self.combo_periodo.blockSignals(True)
        self.combo_periodo.clear()
        self.combo_periodo.addItem("Todos los periodos", None)
        periodos = self.service.listar_periodos()
        for p in periodos:
            label = f"{MESES[p.mes]} {p.anio}"
            if p.estado == EstadoPeriodo.ABIERTO:
                label += " 🟢"
            self.combo_periodo.addItem(label, p.id)
        self.combo_periodo.blockSignals(False)

    def _cargar(self):
        periodo_id = self.combo_periodo.currentData()
        asientos   = self.service.listar_asientos(periodo_id=periodo_id)
        self.tbl_asientos.setRowCount(0)
        for a in asientos:
            r = self.tbl_asientos.rowCount()
            self.tbl_asientos.insertRow(r)

            num_item = QTableWidgetItem(a.numero)
            num_item.setData(Qt.ItemDataRole.UserRole, a.id)
            self.tbl_asientos.setItem(r, 0, num_item)
            self.tbl_asientos.setItem(r, 1, QTableWidgetItem(str(a.fecha)))
            self.tbl_asientos.setItem(r, 2, QTableWidgetItem(a.descripcion or ""))

            estado_val = a.estado.value if hasattr(a.estado, 'value') else str(a.estado)
            estado_item = QTableWidgetItem(estado_val.capitalize())
            
            if a.estado == EstadoAsiento.ANULADO:
                estado_item.setForeground(QColor("#dc2626"))
            self.tbl_asientos.setItem(r, 3, estado_item)

            total = sum(m.debito for m in a.movimientos)
            total_item = QTableWidgetItem(f"${total:,.2f}")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_asientos.setItem(r, 4, total_item)

            if a.estado == EstadoAsiento.ANULADO:
                for col in range(5):
                    item = self.tbl_asientos.item(r, col)
                    if item:
                        item.setForeground(QColor("#94a3b8"))

        self.tbl_movs.setRowCount(0)

    def _on_asiento_sel(self):
        fila = self.tbl_asientos.currentRow()
        if fila < 0:
            return
        
        item_num = self.tbl_asientos.item(fila, 0)
        if not item_num:
            return
            
        asiento_id = item_num.data(Qt.ItemDataRole.UserRole)
        asiento    = self.service.obtener_asiento(asiento_id)
        if not asiento:
            return
        self.tbl_movs.setRowCount(0)
        for m in asiento.movimientos:
            r = self.tbl_movs.rowCount()
            self.tbl_movs.insertRow(r)
            self.tbl_movs.setItem(r, 0, QTableWidgetItem(m.cuenta.codigo if m.cuenta else ""))
            self.tbl_movs.setItem(r, 1, QTableWidgetItem(m.cuenta.nombre if m.cuenta else ""))
            
            db_item = QTableWidgetItem(f"${m.debito:,.2f}" if m.debito else "")
            cr_item = QTableWidgetItem(f"${m.credito:,.2f}" if m.credito else "")
            db_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cr_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            db_item.setForeground(QColor("#1d4ed8"))
            cr_item.setForeground(QColor("#16a34a"))
            self.tbl_movs.setItem(r, 2, db_item)
            self.tbl_movs.setItem(r, 3, cr_item)

    def _nuevo_asiento(self):
        periodo_id = self.get_periodo()
        if not periodo_id:
            QMessageBox.warning(
                self, "Sin periodo activo",
                "No hay un periodo contable abierto.\n"
                "Ve a la pestaña Periodos y crea uno."
            )
            return
        dlg = DialogNuevoAsiento(self.service, periodo_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._llenar_periodos()
            self._cargar()

    def _anular_asiento(self):
        fila = self.tbl_asientos.currentRow()
        if fila < 0:
            return
        asiento_id = self.tbl_asientos.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        numero     = self.tbl_asientos.item(fila, 0).text()
        resp = QMessageBox.question(
            self, "Confirmar anulación",
            f"¿Anular el asiento {numero}?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                self.service.anular_asiento(asiento_id)
                self._cargar()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._llenar_periodos()
        self._cargar()


# ══════════════════════════════════════════════════════════════
# Widget principal del módulo Contabilidad
# ══════════════════════════════════════════════════════════════
class ContabilidadWidget(QWidget):
    def __init__(self, empresa_id: int, parent=None):
        super().__init__(parent)
        if not empresa_id:
            self._build_sin_empresa()
            return
        self.session    = SessionLocal()
        self.service    = ContabilidadService(self.session, empresa_id)
        self._build_ui()

    def _build_sin_empresa(self):
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("⚠️  Selecciona una empresa en la barra superior para acceder a Contabilidad.")
        lbl.setFont(QFont("Segoe UI", 13))
        lbl.setStyleSheet("color:#94a3b8;")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        titulo = QLabel("📒  Contabilidad")
        titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        titulo.setStyleSheet("color:#1e293b; padding:16px 20px 4px 20px;")
        layout.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { padding: 8px 20px; font-size: 13px; }
            QTabBar::tab:selected { font-weight: bold; color: #2563eb; }
        """)

        self.tab_periodos = TabPeriodos(self.service)
        self.tab_asientos = TabAsientos(
            self.service,
            get_periodo_fn=self.tab_periodos.periodo_id_activo
        )
        self.tab_puc = TabPUC(self.service)

        self.tabs.addTab(self.tab_periodos, "📅 Periodos")
        self.tabs.addTab(self.tab_asientos, "📝 Libro Diario")
        self.tabs.addTab(self.tab_puc,      "📋 Plan de Cuentas")

        layout.addWidget(self.tabs)

    def closeEvent(self, event):
        if hasattr(self, "session"):
            self.session.close()
        super().closeEvent(event)
